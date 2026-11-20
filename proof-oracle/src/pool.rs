//! Offline bridge: real captured job binding and exact explicit pool-target checks.
//! Structure-only verification uses an explicit EASY override and is never reported as share qualification.
use anyhow::{Result,ensure};
use std::{fs,path::Path};
use serde_json::{Value,json};
use rand::{SeedableRng,rngs::StdRng};
use sha2::{Digest,Sha256};
use primitive_types::U256;
use zk_pow::{api::{proof::{IncompleteBlockHeader,MiningConfiguration,MMAType,PeriodicPattern},proof_utils::{CompiledPublicParams,compute_jackpot_hash},verify::verify_plain_proof,sanity_checks::penalized_target_bound},
 circuit::{chip::compute_jackpot,pearl_noise::compute_noise},ffi::{plain_proof::{PlainProof,check_cert_version_eligible},mine::try_mine_one}};
pub(super) fn hex(b:&[u8])->String{b.iter().map(|x|format!("{x:02x}")).collect()}
pub(super) fn unhex(s:&str)->Result<Vec<u8>>{ensure!(s.len()%2==0&&s.is_ascii()&&s.bytes().all(|c|c.is_ascii_hexdigit()),"invalid hex");(0..s.len()).step_by(2).map(|i|Ok(u8::from_str_radix(&s[i..i+2],16)?)).collect()}
pub(super) fn load(path:&Path)->Result<Value>{Ok(serde_json::from_slice(&fs::read(path)?)?)}
pub(super) fn uint(v:&Value,name:&str)->Result<usize>{Ok(v[name].as_u64().ok_or_else(||anyhow::anyhow!("missing integer {name}"))?.try_into()?)}
pub(super) fn context(job:&Value)->Result<(&Value,IncompleteBlockHeader,U256,String)>{
 let p=if job.get("notify_params").is_some(){&job["notify_params"]}else{ensure!(job["method"]=="mining.notify","wrong method");&job["params"]};
 ensure!(p["cert_version"]==3,"only V3 supported");let raw=unhex(p["header"].as_str().ok_or_else(||anyhow::anyhow!("header"))?)?;
 let header=IncompleteBlockHeader::from_bytes(&raw)?;
 let target_s=p["target"].as_str().ok_or_else(||anyhow::anyhow!("target"))?;
 ensure!(target_s.len()==64,"target length");let target_bytes=unhex(target_s)?;let target=U256::from_big_endian(&target_bytes);ensure!(!target.is_zero(),"zero target");
 let jid=p["job_id"].as_str().ok_or_else(||anyhow::anyhow!("job_id"))?;ensure!(!jid.is_empty()&&jid.len()<=256&&!jid.chars().any(|c|c.is_control()),"job_id");
 let mut binding=b"pearl-pool-job-v1\0".to_vec();binding.extend(&raw);binding.extend(3u32.to_le_bytes());binding.extend(&target_bytes);binding.extend((jid.len() as u32).to_le_bytes());binding.extend(jid.as_bytes());
 Ok((p,header,target,hex(&Sha256::digest(&binding))))
}
pub(super) fn config(profile:&Value)->Result<MiningConfiguration>{
 let m=uint(profile,"m")?;let n=uint(profile,"n")?;let k=uint(profile,"k")?;let rank=uint(profile,"rank")?;
 ensure!(m>0&&n>0&&m<=(1<<24)&&n<=(1<<24),"matrix dimensions");
 ensure!((128..=1024).contains(&rank)&&rank.is_power_of_two(),"rank");
 ensure!((1024..=65536).contains(&k)&&k%64==0&&k%rank==0&&16*rank<=k&&k<=4*rank*rank,"K/rank");
 ensure!(uint(profile,"mma_type")?==0,"MMA type");
 let rows:Vec<u32>=profile["row_pattern"].as_array().ok_or_else(||anyhow::anyhow!("rows"))?.iter().map(|x|Ok(x.as_u64().ok_or_else(||anyhow::anyhow!("row"))?.try_into()?)).collect::<Result<_>>()?;
 let cols:Vec<u32>=profile["column_pattern"].as_array().ok_or_else(||anyhow::anyhow!("cols"))?.iter().map(|x|Ok(x.as_u64().ok_or_else(||anyhow::anyhow!("col"))?.try_into()?)).collect::<Result<_>>()?;
 ensure!(rows.len()==16 && (cols.len()==8||cols.len()==16),"unsupported stage64 proof geometry");
 ensure!(rows.iter().all(|&x|(x as usize)<m)&&cols.iter().all(|&x|(x as usize)<n),"pattern out of bounds");
 Ok(MiningConfiguration{common_dim:uint(profile,"k")?.try_into()?,rank:uint(profile,"rank")?.try_into()?,mma_type:MMAType::Int7xInt7ToInt32,
 rows_pattern:PeriodicPattern::from_list(&rows)?,cols_pattern:PeriodicPattern::from_list(&cols)?,moe:None})
}
pub(super) fn evaluate(job:&Value,profile:&Value,proof:&PlainProof)->Result<Value>{
 let (p,header,target,fingerprint)=context(job)?;let configuration=config(profile)?;
 ensure!(proof.m==uint(profile,"m")? && proof.n==uint(profile,"n")? && proof.k==uint(profile,"k")? && proof.noise_rank==uint(profile,"rank")?,"profile/proof dimensions differ");
 let version=check_cert_version_eligible(3,proof)?;let derivation=version.seed_derivation();
 let (secret,public)=proof.parse_proof(header,derivation)?;
 ensure!(public.mining_config.to_bytes()==configuration.to_bytes(),"proof pattern/config differs");
 // This validates structure/job/Merkle/range/config using the official verifier, but NOT actual target.
 verify_plain_proof(&header,proof,Some(0x207fffff),derivation)?;
 let compiled=CompiledPublicParams::from(&public);let noise=compute_noise(&compiled);
 let transcript=compute_jackpot(&compiled,&secret.s_a,&secret.s_b,&noise);
 let hash=compute_jackpot_hash(&transcript,compiled.a_noise_seed());
 let bound=penalized_target_bound(target,&configuration).ok_or_else(||anyhow::anyhow!("scaled target overflow/invalid"))?;
 let bytes=bincode::serialize(proof)?;
 Ok(json!({"job_id":p["job_id"],"job_fingerprint":fingerprint,"header_hex":hex(&header.to_bytes()),"cert_version":3,
  "m":proof.m,"n":proof.n,"k":proof.k,"rank":proof.noise_rank,"row_pattern":configuration.rows_pattern.to_list(),"column_pattern":configuration.cols_pattern.to_list(),
  "mining_config_hex":hex(&configuration.to_bytes()),"job_key":hex(&compiled.job_key),"root_a":hex(&proof.a.proof.root),"root_b":hex(&proof.bt.proof.root),
  "a_noise_seed":hex(&compiled.a_noise_seed()),"b_noise_seed":hex(&compiled.b_noise_seed()),"jackpot":transcript,"jackpot_hash":hex(&hash),
  "proof_sha256":hex(&Sha256::digest(&bytes)),"structural_verifier_passed":true,"structural_verifier_override":"207fffff (easy; NOT actual pool target)",
  "share_base_target_hex":format!("{target:064x}"),"share_bound_hex":format!("{bound:064x}"),
  "share_target_passed":U256::from_little_endian(&hash)<=bound,"pool_policy_verified":false,"network_used":false,"share_sent":false}))
}
pub fn verify(job_path:&Path,profile_path:&Path,proof_path:&Path,out:&Path)->Result<()>{
 let job=load(job_path)?;let profile=load(profile_path)?;let bytes=fs::read(proof_path)?;
 let proof=PlainProof::deserialize_compat(&bytes)?;let report=evaluate(&job,&profile,&proof)?;
 fs::write(out,serde_json::to_vec_pretty(&report)?)?;println!("Official structural verification and exact share-target evaluation completed (offline)");Ok(())
}
pub fn candidate(job_path:&Path,profile_path:&Path,out:&Path)->Result<()>{
 let job=load(job_path)?;let profile=load(profile_path)?;let (_,header,_,_)=context(&job)?;let configuration=config(&profile)?;
 let (m,n,k)=(uint(&profile,"m")?,uint(&profile,"n")?,uint(&profile,"k")?);
 ensure!(m<=256&&n<=256&&k<=8192,"CPU diagnostic candidate is limited to small lab profiles, never silently shrink a live profile");
 ensure!(!out.exists(),"refusing to overwrite candidate directory");fs::create_dir_all(out)?;
 let mut rng=StdRng::from_seed([63;32]);
 // Deliberately selects a non-block-winning candidate. It need not meet the pool target.
 let proof=try_mine_one(&mut rng,m,n,k,header,configuration,None,true,zk_pow::api::proof::SeedDerivation::Salted)?.ok_or_else(||anyhow::anyhow!("no diagnostic candidate"))?;
 let report=evaluate(&job,&profile,&proof)?;fs::write(out.join("candidate.proof.bin"),bincode::serialize(&proof)?)?;
 fs::write(out.join("candidate-report.json"),serde_json::to_vec_pretty(&report)?)?;
 println!("Real-header diagnostic candidate built; structure passed; exact share_target_passed={}; no share transmitted",report["share_target_passed"]);
 Ok(())
}

pub fn hash_vectors(manifest_path:&Path,real_path:&Path,out:&Path)->Result<()> {
 use rand::Rng;
 let manifest=load(manifest_path)?;let real=load(real_path)?;let mut inputs=Vec::new();
 for case in manifest["cases"].as_array().ok_or_else(||anyhow::anyhow!("cases"))?.iter().chain(std::iter::once(&real)) {
  let key: [u8;32]=unhex(case["a_noise_seed"].as_str().ok_or_else(||anyhow::anyhow!("key"))?)?.try_into().map_err(|_|anyhow::anyhow!("key length"))?;
  let words=case["jackpot"].as_array().ok_or_else(||anyhow::anyhow!("jackpot"))?;ensure!(words.len()==16,"jackpot length");
  let mut msg=[0u8;64];for (i,v) in words.iter().enumerate(){msg[i*4..i*4+4].copy_from_slice(&(v.as_u64().ok_or_else(||anyhow::anyhow!("word"))? as u32).to_le_bytes());}
  inputs.push((key,msg));
 }
 let mut rng=StdRng::from_seed([39;32]);for _ in 0..32 {let mut key=[0u8;32];let mut msg=[0u8;64];rng.fill(&mut key);rng.fill(&mut msg);inputs.push((key,msg));}
 let target=U256::from_str_radix(real["share_bound_hex"].as_str().ok_or_else(||anyhow::anyhow!("bound"))?,16)?;
 let mut bytes=b"PRLHSH01".to_vec();bytes.extend(((inputs.len()*5) as u32).to_le_bytes());
 for (key,msg) in inputs {
  let hash=pearl_blake3::blake3_digest(&msg,Some(key));let value=U256::from_little_endian(&hash);ensure!(!value.is_zero(),"unexpected zero digest");
  for bound in [target,value,value-U256::one(),U256::MAX,U256::zero()] {
   bytes.extend(key);bytes.extend(msg);bytes.extend(hash);let mut bound_bytes=[0u8;32];bound.to_little_endian(&mut bound_bytes);bytes.extend(bound_bytes);bytes.extend(u32::from(value<=bound).to_le_bytes());
  }
 }
 fs::write(out,&bytes)?;println!("195 keyed jackpot hash/target vectors written from official Pearl BLAKE3 (CPU)");Ok(())
}
