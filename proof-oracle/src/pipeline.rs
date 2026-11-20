//! Bounded offline full-batch preparation and proof construction from reported hits.
use anyhow::{Result,ensure};
use std::{fs,path::Path,collections::BTreeSet};
use rand::{SeedableRng,Rng,rngs::StdRng};
use serde_json::{Value,json};
use sha2::{Digest,Sha256};
use primitive_types::U256;
use pearl_blake3::{MerkleTree,pad_to_chunk_boundary};
use zk_pow::{api::proof::{PublicProofParams,SeedDerivation},circuit::pearl_noise::compute_noise_for_indices,ffi::plain_proof::{PlainProof,MatrixMerkleProof}};
use super::pool;
pub(super) fn trees(job:&Value,profile:&Value,a:&[u8],bt:&[u8])->Result<(MerkleTree,MerkleTree,PublicProofParams)>{
 let (_,header,_,_)=pool::context(job)?;let cfg=pool::config(profile)?;
 let m=pool::uint(profile,"m")?;let n=pool::uint(profile,"n")?;let k=pool::uint(profile,"k")?;
 ensure!(a.len()==m*k&&bt.len()==n*k,"raw input length");
 ensure!(m<=131072&&n<=131072&&k<=8192&&(m+n)*k<=(1usize<<31),"work allocation bounds");
 let h=cfg.rows_pattern.size() as usize;let w=cfg.cols_pattern.size() as usize;
 ensure!(m%h==0&&n%w==0&&cfg.rows_pattern.to_list()==(0..h as u32).collect::<Vec<_>>()&&cfg.cols_pattern.to_list()==(0..w as u32).collect::<Vec<_>>(),"contiguous complete tiles required");
 let mut public=PublicProofParams{block_header:header,seed_derivation:SeedDerivation::Salted,mining_config:cfg,
 hash_a:[0;32],hash_b:[0;32],hash_jackpot:[0;32],m:m.try_into()?,n:n.try_into()?,t_rows:0,t_cols:0,moe:None};
 public.sanity_check()?;let key=public.job_key();
 let at=MerkleTree::new(&pad_to_chunk_boundary(a),key);let btree=MerkleTree::new(&pad_to_chunk_boundary(bt),key);
 public.hash_a=at.root();public.hash_b=btree.root();Ok((at,btree,public))
}
pub(super) fn proof_for(index:usize,profile:&Value,at:&MerkleTree,bt:&MerkleTree)->Result<PlainProof>{
 let cfg=pool::config(profile)?;let m=pool::uint(profile,"m")?;let n=pool::uint(profile,"n")?;let k=pool::uint(profile,"k")?;
 let h=cfg.rows_pattern.size() as usize;let w=cfg.cols_pattern.size() as usize;ensure!(index<(m/h)*(n/w),"hit index out of range");
 let rows:Vec<usize>=((index/(n/w))*h..(index/(n/w)+1)*h).collect();let cols:Vec<usize>=((index%(n/w))*w..(index%(n/w)+1)*w).collect();
 Ok(PlainProof{m,n,k,noise_rank:cfg.rank as usize,
  a:MatrixMerkleProof{proof:at.get_multileaf_proof(&MerkleTree::compute_leaf_indices_from_rows(&rows,(m,k))),row_indices:rows},
  bt:MatrixMerkleProof{proof:bt.get_multileaf_proof(&MerkleTree::compute_leaf_indices_from_rows(&cols,(n,k))),row_indices:cols},moe:None})
}
pub(super) fn batch_id(job:&Value,at:&MerkleTree,bt:&MerkleTree)->Result<String>{let (_,_,_,fp)=pool::context(job)?;let mut b=b"pearl-batch-v1\0".to_vec();b.extend(pool::unhex(&fp)?);b.extend(at.root());b.extend(bt.root());Ok(pool::hex(&Sha256::digest(&b)))}
pub fn prepare(job_path:&Path,profile_path:&Path,out:&Path,synthetic_mid:bool)->Result<()>{
 ensure!(!out.exists(),"output directory exists");let mut job=pool::load(job_path)?;let profile=pool::load(profile_path)?;let cfg=pool::config(&profile)?;
 let (m,n,k)=(pool::uint(&profile,"m")?,pool::uint(&profile,"n")?,pool::uint(&profile,"k")?);let h=cfg.rows_pattern.size() as usize;let w=cfg.cols_pattern.size() as usize;
 ensure!(m<=128&&n<=128&&k<=8192&&m*n*k<=(1<<26),"bounded offline batch only, no implicit downsizing");
 ensure!(m%h==0&&n%w==0&&cfg.rows_pattern.to_list()==(0..h as u32).collect::<Vec<_>>()&&cfg.cols_pattern.to_list()==(0..w as u32).collect::<Vec<_>>(),"this batch path requires contiguous complete tiles");
 let mut rng=StdRng::from_seed([82;32]);let a:Vec<u8>=(0..m*k).map(|_|rng.random_range(-64i8..=64) as u8).collect();let bt:Vec<u8>=(0..n*k).map(|_|rng.random_range(-64i8..=64) as u8).collect();
 let (at,btree,public)=trees(&job,&profile,&a,&bt)?;let groups=(m/h)*(n/w);let mut reports=Vec::new();
 for i in 0..groups{reports.push(pool::evaluate(&job,&profile,&proof_for(i,&profile,&at,&btree)?)?);}
 if synthetic_mid {
  ensure!(groups>=2,"need multiple candidates for middle target");let mut hashes:Vec<U256>=reports.iter().map(|r|Ok(U256::from_little_endian(&pool::unhex(r["jackpot_hash"].as_str().unwrap())?))).collect::<Result<_>>()?;hashes.sort();
  let factor=U256::from(h*w*(k/cfg.rank as usize)*128);let target=hashes[groups/2]/factor;ensure!(!target.is_zero(),"synthetic target too small");
  let param_key=if job.get("notify_params").is_some(){"notify_params"}else{"params"};job[param_key]["target"]=json!(format!("{target:064x}"));job[param_key]["job_id"]=json!("SYNTHETIC-MID-PIPELINE-NOT-FOR-SUBMISSION");
  reports.clear();for i in 0..groups{reports.push(pool::evaluate(&job,&profile,&proof_for(i,&profile,&at,&btree)?)?);}
 }
 let (_,_,_,fp)=pool::context(&job)?;let id=batch_id(&job,&at,&btree)?;let (_,aseed)=public.commitment_hash(public.job_key());
 let rows=(0..m).collect::<Vec<_>>();let cols=(0..n).collect::<Vec<_>>();let noise=compute_noise_for_indices(k,cfg.rank as usize,public.commitment_hash(public.job_key()),&rows,&cols);
 let mut an=Vec::with_capacity(a.len());let mut bn=Vec::with_capacity(bt.len());
 for (raw,add,dst) in [(&a,&noise.a,&mut an),(&bt,&noise.b,&mut bn)] {for row in 0..raw.len()/k{for c in 0..k{let x=raw[row*k+c] as i8 as i32+add[row][c] as i32;ensure!((-127..=127).contains(&x),"input overflow");dst.push(x as i8);}}}
 let mut matrix=Vec::with_capacity(m*n);for r in 0..m{for c in 0..n{let sum:i64=(0..k).map(|l|i64::from(an[r*k+l])*i64::from(bn[c*k+l])).sum();matrix.push(i32::try_from(sum)?);}}
 let bound=reports[0]["share_bound_hex"].as_str().unwrap();let mut target_bytes=pool::unhex(bound)?;target_bytes.reverse();
 let mut bytes=b"PRLPIPE1".to_vec();for d in [m,n,k,cfg.rank as usize,w]{bytes.extend((d as u32).to_le_bytes());}
 bytes.extend(pool::unhex(&fp)?);bytes.extend(pool::unhex(&id)?);bytes.extend(aseed);bytes.extend(&target_bytes);bytes.extend(an.iter().map(|&x|x as u8));bytes.extend(bn.iter().map(|&x|x as u8));
 for value in matrix{bytes.extend(value.to_le_bytes());}
 let mut transcripts=Vec::new();let mut hits=Vec::new();
 for (i,r) in reports.iter().enumerate(){let t=r["jackpot"].as_array().unwrap().iter().map(|x|x.as_u64().unwrap() as u32).collect::<Vec<_>>();for x in &t{bytes.extend(x.to_le_bytes());}transcripts.push(t);if r["share_target_passed"]==true{hits.push(i as u32);}}
 bytes.extend((hits.len() as u32).to_le_bytes());for i in &hits{bytes.extend(i.to_le_bytes());}
 if synthetic_mid{ensure!(!hits.is_empty()&&hits.len()<groups,"synthetic subset must be nontrivial");}
 fs::create_dir_all(out)?;fs::write(out.join("job.json"),serde_json::to_vec_pretty(&job)?)?;fs::write(out.join("profile.json"),serde_json::to_vec_pretty(&profile)?)?;
 fs::write(out.join("raw-a.bin"),a)?;fs::write(out.join("raw-bt.bin"),bt)?;fs::write(out.join("batch.fixture"),&bytes)?;
 let manifest=json!({"job_fingerprint":fp,"batch_id":id,"groups":groups,"expected_hits":hits,"transcripts":transcripts,"batch_fixture_sha256":pool::hex(&Sha256::digest(&bytes)),"synthetic_target":synthetic_mid,"network_used":false,"GPU_used":false});
 fs::write(out.join("manifest.json"),serde_json::to_vec_pretty(&manifest)?)?;println!("Offline batch: groups={groups}, qualified hits={}, synthetic_target={synthetic_mid}",hits.len());Ok(())
}
pub fn finalize(batch:&Path,hit_file:&Path,out:&Path)->Result<()>{
 ensure!(!out.exists(),"output directory exists");let job=pool::load(&batch.join("job.json"))?;let profile=pool::load(&batch.join("profile.json"))?;let manifest=pool::load(&batch.join("manifest.json"))?;let supplied=pool::load(hit_file)?;
 let (at,bt,public)=trees(&job,&profile,&fs::read(batch.join("raw-a.bin"))?,&fs::read(batch.join("raw-bt.bin"))?)?;
 let (_,_,_,fp)=pool::context(&job)?;let id=batch_id(&job,&at,&bt)?;
 ensure!(manifest["job_fingerprint"]==fp&&manifest["batch_fixture_sha256"]==pool::hex(&Sha256::digest(fs::read(batch.join("batch.fixture"))?)),"fixture or manifest context changed");
 ensure!(supplied["job_fingerprint"]==fp&&supplied["batch_id"]==id&&manifest["batch_id"]==id,"stale or wrong batch context");
 let hits=supplied["hit_indices"].as_array().ok_or_else(||anyhow::anyhow!("hit indices"))?;let mut seen=BTreeSet::new();for h in hits{ensure!(seen.insert(h.as_u64().ok_or_else(||anyhow::anyhow!("bad index"))? as usize),"duplicate hit");}
 let expected:BTreeSet<usize>=manifest["expected_hits"].as_array().ok_or_else(||anyhow::anyhow!("expected hits"))?.iter().map(|x|x.as_u64().unwrap() as usize).collect();ensure!(seen==expected,"diagnostic hit set differs from official CPU oracle");
 let received=supplied["transcripts"].as_array().ok_or_else(||anyhow::anyhow!("transcripts"))?;let cfg=pool::config(&profile)?;let groups=(public.m as usize/cfg.rows_pattern.size() as usize)*(public.n as usize/cfg.cols_pattern.size() as usize);
 ensure!(received.len()==groups&&manifest["groups"]==groups,"transcript group count");
 // Recheck EVERY reported transcript against unmodified official proof/noise/hash code.
 let mut official_hits=BTreeSet::new();let mut proofs=Vec::new();for i in 0..received.len(){let proof=proof_for(i,&profile,&at,&bt)?;let report=pool::evaluate(&job,&profile,&proof)?;ensure!(report["jackpot"]==received[i],"external transcript mismatch");if report["share_target_passed"]==true{official_hits.insert(i);}
 if seen.contains(&i){ensure!(report["share_target_passed"]==true,"unqualified hit");proofs.push((i,proof,report));}}
 ensure!(seen==official_hits,"missing or unexpected hit against independent exact-target recheck");
 fs::create_dir_all(out)?;for (i,proof,report) in &proofs{fs::write(out.join(format!("hit-{i}.proof.bin")),bincode::serialize(proof)?)?;fs::write(out.join(format!("hit-{i}-report.json")),serde_json::to_vec_pretty(report)?)?;}
 fs::write(out.join("result.json"),serde_json::to_vec_pretty(&json!({"job_fingerprint":fp,"batch_id":id,"official_structural_and_exact_target_checks_passed":true,"hit_count":proofs.len(),"all_transcripts_rechecked":received.len(),"synthetic_target":manifest["synthetic_target"],"input_claims_GPU_execution":supplied.get("GPU_executed").unwrap_or(&Value::Null),"network_used":false,"share_sent":false,"job_key":pool::hex(&public.job_key())}))?)?;
 println!("{} hit proofs built and checked against official verifier and exact target; no transmission",proofs.len());Ok(())
}
