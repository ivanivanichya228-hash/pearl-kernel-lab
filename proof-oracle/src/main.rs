//! Synthetic CPU compatibility oracle. Calls the unmodified pinned upstream verifier.
mod pool;
mod pipeline;
use anyhow::{Result,ensure,bail};
use std::{fs,path::Path};
use rand::{SeedableRng,rngs::StdRng};
use serde_json::json;
use zk_pow::{api::{proof::{IncompleteBlockHeader,MiningConfiguration,MMAType,PeriodicPattern,SeedDerivation},
    proof_utils::{CompiledPublicParams,compute_jackpot_hash},verify::verify_plain_proof},
    circuit::{chip::compute_jackpot,pearl_noise::compute_noise},ffi::mine::try_mine_one};
const COMMIT:&str="38dd764ab0aec528e81fc467665c6762ef6739e9";
fn hex(b:&[u8])->String {b.iter().map(|x|format!("{x:02x}")).collect()}
fn verify_outputs(out:&Path,file:&Path)->Result<()> {
 use zk_pow::ffi::plain_proof::PlainProof;
 let manifest:serde_json::Value=serde_json::from_slice(&fs::read(out.join("manifest.json"))?)?;
 ensure!(manifest["upstream_commit"]==COMMIT,"different upstream context");
 let lines=fs::read_to_string(file)?;let mut seen=std::collections::BTreeSet::new();
 for line in lines.lines().filter(|x|!x.trim().is_empty()) {
  let record:serde_json::Value=serde_json::from_str(line)?;
  let i=record["case"].as_u64().ok_or_else(||anyhow::anyhow!("case missing"))? as usize;
  ensure!(i<6 && seen.insert(i),"unknown or duplicate case");
  let data=record["transcript"].as_array().ok_or_else(||anyhow::anyhow!("transcript missing"))?;
  ensure!(data.len()==16,"transcript length");let mut transcript=[0u32;16];
  for (j,v) in data.iter().enumerate(){transcript[j]=v.as_u64().filter(|x|*x<=u32::MAX as u64).ok_or_else(||anyhow::anyhow!("invalid word"))? as u32;}
  let proof:PlainProof=bincode::deserialize(&fs::read(out.join(format!("case-{i}.proof.bin")))?)?;
  let header=IncompleteBlockHeader::from_bytes(&fs::read(out.join(format!("case-{i}.header.bin")))?)?;
  let derivation=match manifest["cases"][i]["certificate_seed_rule"].as_str() {
   Some("Legacy_V2")=>SeedDerivation::Legacy,Some("Salted_V3")=>SeedDerivation::Salted,_=>bail!("unknown seed derivation")};
  verify_plain_proof(&header,&proof,None,derivation)?;
  let (secret,public)=proof.parse_proof(header,derivation)?;let compiled=CompiledPublicParams::from(&public);
  let noise=compute_noise(&compiled);let expected=compute_jackpot(&compiled,&secret.s_a,&secret.s_b,&noise);
  ensure!(transcript==expected,"external transcript differs from official proof case{i}");
  ensure!(compute_jackpot_hash(&transcript,compiled.a_noise_seed())==compute_jackpot_hash(&expected,compiled.a_noise_seed()),"keyed jackpot hash mismatch");
 }
 ensure!(seen.len()==6,"not all proof cases supplied");
 println!("6 external transcripts match official proof/noise/seed/jackpot hash; official plain verifier passed");Ok(())
}
fn main()->Result<()> {
 let args:Vec<String>=std::env::args().collect();
 if args.len()==6 && args[1]=="batch-prepare" {ensure!(args[5]=="actual" || args[5]=="synthetic-mid", "batch target mode must be actual or synthetic-mid");
        return pipeline::prepare(Path::new(&args[2]),Path::new(&args[3]),Path::new(&args[4]),args[5]=="synthetic-mid");}
 if args.len()==5 && args[1]=="batch-finalize" {return pipeline::finalize(Path::new(&args[2]),Path::new(&args[3]),Path::new(&args[4]));}
 if args.len()==5 && args[1]=="hash-vectors" {return pool::hash_vectors(Path::new(&args[2]),Path::new(&args[3]),Path::new(&args[4]));}
 if args.len()==5 && args[1]=="pool-candidate" {return pool::candidate(Path::new(&args[2]),Path::new(&args[3]),Path::new(&args[4]));}
 if args.len()==6 && args[1]=="pool-verify" {return pool::verify(Path::new(&args[2]),Path::new(&args[3]),Path::new(&args[4]),Path::new(&args[5]));}if args.len()==4 && args[1]=="verify"{return verify_outputs(Path::new(&args[2]),Path::new(&args[3]));}
 ensure!(args.len()==2,"usage: pearl-protocol-oracle OUTPUT_DIR | verify DIR TRANSCRIPTS");
 let out=Path::new(&args[1]);fs::create_dir_all(out)?;let mut cases=Vec::new();
 for i in 0..6usize {
  let pn=if i==0||i==1||i==4{8}else{16};let strided=i>=4;
  let derivation=if i==0||i==2{SeedDerivation::Legacy}else{SeedDerivation::Salted};
  let header=IncompleteBlockHeader{version:0,prev_block:[1;32],merkle_root:[2;32],timestamp:0x66666666+i as u32,nbits:0x207fffff};
  let row_indices:Vec<u32>=(0..16).map(|x|x*if strided{2}else{1}).collect();
  let col_indices:Vec<u32>=(0..pn as u32).map(|x|x*if strided{4}else{1}).collect();
  let config=MiningConfiguration{common_dim:4096,rank:128,mma_type:MMAType::Int7xInt7ToInt32,
    rows_pattern:PeriodicPattern::from_list(&row_indices)?,cols_pattern:PeriodicPattern::from_list(&col_indices)?,moe:None};
  let mut rng=StdRng::from_seed([11+i as u8;32]);let mut found=None;let mut attempts=0;
  for _ in 0..64 {attempts+=1;if let Some(p)=try_mine_one(&mut rng,64,64,4096,header,config,None,false,derivation)?{found=Some(p);break}}
  let proof=found.ok_or_else(||anyhow::anyhow!("no synthetic easy-target proof within bound"))?;
  verify_plain_proof(&header,&proof,None,derivation)?;
  let (secret,public)=proof.parse_proof(header,derivation)?;let compiled=CompiledPublicParams::from(&public);
  ensure!(compiled.h==16 && compiled.w==pn && compiled.k==4096 && compiled.r==128,"unexpected compiled shape");
  let noise=compute_noise(&compiled);let jackpot=compute_jackpot(&compiled,&secret.s_a,&secret.s_b,&noise);
  let hash=compute_jackpot_hash(&jackpot,compiled.a_noise_seed());
  let mut a=Vec::new();let mut bt=Vec::new();let mut min_value=127i32;let mut max_value=-127i32;
  for (raw,n,output) in [(&secret.s_a,&noise.a,&mut a),(&secret.s_b,&noise.b,&mut bt)] {
   for (row,nrow) in raw.iter().zip(n) {for (&s,&e) in row.iter().zip(nrow) {
    let v=i32::from(s)+i32::from(e);ensure!((-127..=127).contains(&v),"noised operand out of contract");
    min_value=min_value.min(v);max_value=max_value.max(v);output.push(v as i8);
   }}
  }
  let mut matrix=Vec::new();for row in 0..16 {for col in 0..pn {
   let sum:i64=(0..4096).map(|k|i64::from(a[row*4096+k])*i64::from(bt[col*4096+k])).sum();
   ensure!((i32::MIN as i64..=i32::MAX as i64).contains(&sum),"C overflow");matrix.push(sum as i32);
  }}
  let mut bytes=b"PRLFX001".to_vec();for dim in [16u32,pn as u32,4096,128,pn as u32]{bytes.extend(dim.to_le_bytes())}
  bytes.extend(a.iter().map(|&x|x as u8));bytes.extend(bt.iter().map(|&x|x as u8));
  for x in &matrix{bytes.extend(x.to_le_bytes())}for x in jackpot{bytes.extend(x.to_le_bytes())}
  fs::write(out.join(format!("case-{i}.bin")),&bytes)?;
  fs::write(out.join(format!("case-{i}.header.bin")),header.to_bytes())?;
  fs::write(out.join(format!("case-{i}.proof.bin")),bincode::serialize(&proof)?)?;
  // These corruptions must fail the ACTUAL upstream verifier, not a local predicate.
  let mut negatives=Vec::new();
  let mut bad=proof.clone();bad.a.proof.root[0]^=1;ensure!(verify_plain_proof(&header,&bad,None,derivation).is_err());negatives.push("root");
  let mut bad=proof.clone();bad.a.proof.leaf_data[0][0]^=1;ensure!(verify_plain_proof(&header,&bad,None,derivation).is_err());negatives.push("leaf");
  let mut bad=proof.clone();bad.a.proof.siblings[0][0]^=1;ensure!(verify_plain_proof(&header,&bad,None,derivation).is_err());negatives.push("sibling");
  let mut bad_header=header;bad_header.timestamp^=0x80000000;ensure!(verify_plain_proof(&bad_header,&proof,None,derivation).is_err());negatives.push("job_header");
  let mut bad=proof.clone();bad.m+=1usize<<40;ensure!(verify_plain_proof(&header,&bad,None,derivation).is_err());negatives.push("dimension_wrap");
  ensure!(verify_plain_proof(&header,&proof,Some(0x01010000),derivation).is_err());negatives.push("target");
  let mut corrupted_jackpot=jackpot;corrupted_jackpot[0]^=1;
  ensure!(compute_jackpot_hash(&corrupted_jackpot,compiled.a_noise_seed())!=hash);
  let mut wrong_key=compiled.a_noise_seed();wrong_key[0]^=1;ensure!(compute_jackpot_hash(&jackpot,wrong_key)!=hash);
  cases.push(json!({"case":i,"upstream_commit":COMMIT,"certificate_seed_rule":if derivation==SeedDerivation::Legacy{"Legacy_V2"}else{"Salted_V3"},
    "synthetic_header_hex":hex(&header.to_bytes()),"synthetic_job":true,"network_job_verified":false,
    "dimensions":[64,64,4096],"gathered_shape":[16,pn,4096],"rank":128,"proof_n":pn,
    "row_indices":compiled.a_rows_indices,"column_indices":compiled.b_cols_indices,
    "job_key":hex(&compiled.job_key),"root_a":hex(&proof.a.proof.root),"root_b":hex(&proof.bt.proof.root),
    "b_noise_seed":hex(&compiled.b_noise_seed()),"a_noise_seed":hex(&compiled.a_noise_seed()),
    "noised_min":min_value,"noised_max":max_value,"jackpot":jackpot,"jackpot_hash":hex(&hash),
    "upstream_plain_verifier_passed":true,"verifier_negative_cases_rejected":negatives,
    "local_hash_negative_cases":["transcript_bit","key_bit"],"attempts":attempts,
    "fixture_sha256":null}));
  println!("case{i}: official plain verifier passed; 6 corruptions rejected; proof_n={pn}");
 }
 fs::write(out.join("manifest.json"),serde_json::to_vec_pretty(&json!({"upstream_commit":COMMIT,"GPU_executed":false,
  "plain_proof_verified":true,"recursive_ZK_certificate_generated":false,"active_pool_job_verified":false,"cases":cases}))?)?;
 Ok(())
}
