//! Real-target, freshly randomized work. No fixture goldens, no network code.
use anyhow::{Result,ensure};
use std::{fs,io::Write,path::Path,collections::BTreeSet,time::Instant};
fn timed(stage:&str,start:Instant){eprintln!("{}",json!({"phase":"prepare_timing","stage":stage,"elapsed_seconds":start.elapsed().as_secs_f64()}));}
use rand::{SeedableRng,RngCore,rngs::StdRng};
use serde_json::json;
use rayon::prelude::*;
use zk_pow::{circuit::pearl_noise::{generate_uniform_random_matrix,generate_permutation_matrix},api::sanity_checks::penalized_target_bound};
use super::{pool,pipeline};
// Every lower seven-bit pattern is equiprobable; [-64,63] is canonical signed INT7.
// One CSPRNG fill amortizes RNG/distribution calls; no fixed seeds or repeated batches.
fn random_matrix(len:usize,rng:&mut impl RngCore)->Vec<u8>{let mut data=vec![0u8;len];rng.fill_bytes(&mut data);for x in &mut data{*x=(((*x&127) as i16)-64) as i8 as u8;}data}
fn noisy_chunk(raw:&[u8],first:usize,k:usize,rank:usize,seed:&[u8;32],key:&[u8;32],perm:&[[u32;2]])->Result<Vec<u8>>{
 let mut data=vec![0u8;raw.len()];
 data.par_chunks_mut(k).enumerate().try_for_each(|(local,row)|->Result<()>{
  let uniform=generate_uniform_random_matrix(seed,key,&[first+local],rank);let v=&uniform[0];
  for (c,x) in row.iter_mut().enumerate(){let [a,b]=perm[c];let sum=raw[local*k+c] as i8 as i32+v[a as usize] as i32-v[b as usize] as i32;ensure!((-127..=127).contains(&sum),"noise sum out of range");*x=sum as i8 as u8;}Ok(())
 })?;Ok(data)
}
pub fn prepare(job_path:&Path,profile_path:&Path,out:&Path)->Result<()>{prepare_mode(job_path,profile_path,out,false)}
pub fn prepare_raw(job_path:&Path,profile_path:&Path,out:&Path)->Result<()>{prepare_mode(job_path,profile_path,out,true)}
fn prepare_mode(job_path:&Path,profile_path:&Path,out:&Path,gpu_noise:bool)->Result<()>{
 ensure!(!out.exists(),"new work directory required");let job=pool::load(job_path)?;let profile=pool::load(profile_path)?;let cfg=pool::config(&profile)?;
 let (m,n,k)=(pool::uint(&profile,"m")?,pool::uint(&profile,"n")?,pool::uint(&profile,"k")?);
 ensure!(m<=131072&&n<=131072&&k<=8192&&(m+n)*k<=(1usize<<31),"work memory bounds");
 let (_,_,target,fp)=pool::context(&job)?;let bound=penalized_target_bound(target,&cfg).ok_or_else(||anyhow::anyhow!("invalid target scaling"))?;
 let total=Instant::now();let started=Instant::now();
 let mut rng=StdRng::from_os_rng();
 let a=random_matrix(m*k,&mut rng);let bt=random_matrix(n*k,&mut rng);
 timed("raw_random_matrices",started);let started=Instant::now();
 let (at,btree,public)=pipeline::trees(&job,&profile,&a,&bt)?;let id=pipeline::batch_id(&job,&at,&btree)?;let seeds=public.commitment_hash(public.job_key());
 timed("commitments",started);let started=Instant::now();
 fs::create_dir(out)?;fs::write(out.join("job.json"),serde_json::to_vec(&job)?)?;fs::write(out.join("profile.json"),serde_json::to_vec(&profile)?)?;
 fs::write(out.join("raw-a.bin"),&a)?;fs::write(out.join("raw-bt.bin"),&bt)?;
 timed("raw_files",started);
 let mut file=fs::File::create(out.join("work.bin"))?;file.write_all(if gpu_noise{b"PRLRAWN1"}else{b"PRLWORK1"})?;
 for x in [m,n,k,cfg.rank as usize,cfg.cols_pattern.size() as usize]{file.write_all(&(x as u32).to_le_bytes())?;}
 file.write_all(&pool::unhex(&fp)?)?;file.write_all(&pool::unhex(&id)?)?;file.write_all(&seeds.1)?;if gpu_noise{file.write_all(&seeds.0)?;}let mut bound_bytes=[0u8;32];bound.to_little_endian(&mut bound_bytes);file.write_all(&bound_bytes)?;
 // Chunk noise generation: whole commitments, global row indices; no giant noise matrix.
 let started=Instant::now();
 if !gpu_noise{for (raw,rows,is_a) in [(&a,m,true),(&bt,n,false)]{
  let mut label=[0u8;32];label[..8].copy_from_slice(if is_a{b"A_tensor"}else{b"B_tensor"});let key=if is_a{seeds.1}else{seeds.0};let perm=generate_permutation_matrix(&label,&key,k,cfg.rank as usize);
  for first in (0..rows).step_by(1024){let indices=(first..rows.min(first+1024)).collect::<Vec<_>>();
   let bytes=noisy_chunk(&raw[first*k..(first+indices.len())*k],first,k,cfg.rank as usize,&label,&key,&perm)?;
   file.write_all(&bytes)?;
  }
 }
 }
 timed(if gpu_noise{"raw_manifest_write"}else{"noise_and_work_write"},started);let started=Instant::now();// All writes use unbuffered std::fs::File and write_all. The next process starts only
 // after success; cancelled work is deleted. Crash-durable storage is unnecessary here.
 file.flush()?;drop(file);timed("file_close",started);timed("total",total);
 fs::write(out.join("work.json"),serde_json::to_vec(&json!({"job_fingerprint":fp,"batch_id":id,"groups":(m/16)*(n/cfg.cols_pattern.size() as usize),"target_modified":false,"fresh_OS_randomness":true,"input_mode":if gpu_noise{"raw-for-GPU-noise"}else{"CPU-noised"}}))?)?;
 println!("Fresh real-target work prepared (no CPU GEMM / no network)");Ok(())
}
pub fn reference_noise(batch:&Path,out:&Path)->Result<()>{
 ensure!(!out.exists(),"new reference path required");let job=pool::load(&batch.join("job.json"))?;let profile=pool::load(&batch.join("profile.json"))?;let cfg=pool::config(&profile)?;
 let (m,n,k)=(pool::uint(&profile,"m")?,pool::uint(&profile,"n")?,pool::uint(&profile,"k")?);ensure!(m<=256&&n<=256&&k<=8192,"reference is bounded CPU validation only");
 let a=fs::read(batch.join("raw-a.bin"))?;let bt=fs::read(batch.join("raw-bt.bin"))?;let (at,btree,public)=pipeline::trees(&job,&profile,&a,&bt)?;let (_,_,target,fp)=pool::context(&job)?;let id=pipeline::batch_id(&job,&at,&btree)?;let seeds=public.commitment_hash(public.job_key());
 let noise=zk_pow::circuit::pearl_noise::compute_noise_for_indices(k,cfg.rank as usize,seeds,&(0..m).collect::<Vec<_>>(),&(0..n).collect::<Vec<_>>());
 let mut f=fs::File::create(out)?;f.write_all(b"PRLWORK1")?;for d in [m,n,k,cfg.rank as usize,cfg.cols_pattern.size() as usize]{f.write_all(&(d as u32).to_le_bytes())?;}f.write_all(&pool::unhex(&fp)?)?;f.write_all(&pool::unhex(&id)?)?;f.write_all(&seeds.1)?;
 let bound=penalized_target_bound(target,&cfg).ok_or_else(||anyhow::anyhow!("bound"))?;let mut b=[0u8;32];bound.to_little_endian(&mut b);f.write_all(&b)?;
 for(raw,add)in[(&a,&noise.a),(&bt,&noise.b)]{let mut values=Vec::with_capacity(raw.len());for row in 0..raw.len()/k{for c in 0..k{let v=raw[row*k+c] as i8 as i32+add[row][c] as i32;ensure!((-127..=127).contains(&v),"reference overflow");values.push(v as i8 as u8);}}f.write_all(&values)?;}Ok(())
}
pub fn finalize(batch:&Path,hits_path:&Path,out:&Path)->Result<()>{
 ensure!(!out.exists(),"new proof directory required");let job=pool::load(&batch.join("job.json"))?;let profile=pool::load(&batch.join("profile.json"))?;let hits=pool::load(hits_path)?;
 let (at,bt,_)=pipeline::trees(&job,&profile,&fs::read(batch.join("raw-a.bin"))?,&fs::read(batch.join("raw-bt.bin"))?)?;
 let (_,_,_,fp)=pool::context(&job)?;let id=pipeline::batch_id(&job,&at,&bt)?;ensure!(hits["job_fingerprint"]==fp&&hits["batch_id"]==id,"stale/wrong work context");
 let list=hits["hits"].as_array().ok_or_else(||anyhow::anyhow!("hit list"))?;ensure!(list.len()<=4096,"proof queue bound exceeded");let mut seen=BTreeSet::new();let mut ready=Vec::new();
 for h in list{let index=pool::uint(h,"index")?;ensure!(seen.insert(index),"duplicate hit");let proof=pipeline::proof_for(index,&profile,&at,&bt)?;let report=pool::evaluate(&job,&profile,&proof)?;
  ensure!(report["share_target_passed"]==true&&report["jackpot"]==h["transcript"],"GPU hit failed official proof/target/transcript check");ready.push((index,proof,report));}
 fs::create_dir(out)?;let mut indexes=Vec::new();for (index,proof,report) in ready{fs::write(out.join(format!("hit-{index}.proof.bin")),bincode::serialize(&proof)?)?;fs::write(out.join(format!("hit-{index}-report.json")),serde_json::to_vec(&report)?)?;indexes.push(index);}
 fs::write(out.join("proofs.json"),serde_json::to_vec(&json!({"job_fingerprint":fp,"batch_id":id,"indices":indexes,"target_modified":false,"official_checks_passed":true}))?)?;Ok(())
}

#[cfg(test)]
mod tests{
 use super::*;
 #[test]fn noise_is_byte_identical_to_official(){
  use zk_pow::circuit::pearl_noise::compute_noise_for_indices;
  for rank in [128,256]{let k=4096;let first=1008;let rows=32;let raw=vec![0u8;rows*k];let seeds=([17u8;32],[39u8;32]);let indices=(first..first+rows).collect::<Vec<_>>();
   let expected=compute_noise_for_indices(k,rank,seeds,&indices,&indices);
   for is_a in [true,false]{let mut label=[0u8;32];label[..8].copy_from_slice(if is_a{b"A_tensor"}else{b"B_tensor"});let key=if is_a{seeds.1}else{seeds.0};let p=generate_permutation_matrix(&label,&key,k,rank);let got=noisy_chunk(&raw,first,k,rank,&label,&key,&p).unwrap();let want=if is_a{&expected.a}else{&expected.b};assert_eq!(got,want.iter().flatten().map(|&x|x as u8).collect::<Vec<_>>());}
  }
 }
 #[test]fn packed_random_int7_range_and_freshness(){let a=random_matrix(65536,&mut StdRng::from_os_rng());let b=random_matrix(65536,&mut StdRng::from_os_rng());assert_ne!(a,b);assert!(a.iter().all(|&v|(-64..=63).contains(&(v as i8))));}
}
