//! Real-target, freshly randomized work. No fixture goldens, no network code.
use anyhow::{Result,ensure};
use std::{fs,io::Write,path::Path,collections::BTreeSet};
use rand::{SeedableRng,Rng,rngs::StdRng};
use serde_json::json;
use zk_pow::{circuit::pearl_noise::compute_noise_for_indices,api::sanity_checks::penalized_target_bound};
use super::{pool,pipeline};
pub fn prepare(job_path:&Path,profile_path:&Path,out:&Path)->Result<()>{
 ensure!(!out.exists(),"new work directory required");let job=pool::load(job_path)?;let profile=pool::load(profile_path)?;let cfg=pool::config(&profile)?;
 let (m,n,k)=(pool::uint(&profile,"m")?,pool::uint(&profile,"n")?,pool::uint(&profile,"k")?);
 ensure!(m<=131072&&n<=131072&&k<=8192&&(m+n)*k<=(1usize<<31),"work memory bounds");
 let (_,_,target,fp)=pool::context(&job)?;let bound=penalized_target_bound(target,&cfg).ok_or_else(||anyhow::anyhow!("invalid target scaling"))?;
 let mut rng=StdRng::from_os_rng();let a:Vec<u8>=(0..m*k).map(|_|rng.random_range(-64i8..=64) as u8).collect();let bt:Vec<u8>=(0..n*k).map(|_|rng.random_range(-64i8..=64) as u8).collect();
 let (at,btree,public)=pipeline::trees(&job,&profile,&a,&bt)?;let id=pipeline::batch_id(&job,&at,&btree)?;let seeds=public.commitment_hash(public.job_key());
 fs::create_dir(out)?;fs::write(out.join("job.json"),serde_json::to_vec(&job)?)?;fs::write(out.join("profile.json"),serde_json::to_vec(&profile)?)?;
 fs::write(out.join("raw-a.bin"),&a)?;fs::write(out.join("raw-bt.bin"),&bt)?;
 let mut file=fs::File::create(out.join("work.bin"))?;file.write_all(b"PRLWORK1")?;
 for x in [m,n,k,cfg.rank as usize,cfg.cols_pattern.size() as usize]{file.write_all(&(x as u32).to_le_bytes())?;}
 file.write_all(&pool::unhex(&fp)?)?;file.write_all(&pool::unhex(&id)?)?;file.write_all(&seeds.1)?;let mut bound_bytes=[0u8;32];bound.to_little_endian(&mut bound_bytes);file.write_all(&bound_bytes)?;
 // Chunk noise generation: whole commitments, global row indices; no giant noise matrix.
 for (raw,rows,is_a) in [(&a,m,true),(&bt,n,false)]{
  for first in (0..rows).step_by(1024){let indices=(first..rows.min(first+1024)).collect::<Vec<_>>();
   let noise=if is_a{compute_noise_for_indices(k,cfg.rank as usize,seeds,&indices,&[])}else{compute_noise_for_indices(k,cfg.rank as usize,seeds,&[],&indices)};
   let additions=if is_a{noise.a}else{noise.b};let mut bytes=Vec::with_capacity(indices.len()*k);
   for (local,&global) in indices.iter().enumerate(){for c in 0..k{let x=raw[global*k+c] as i8 as i32+additions[local][c] as i32;ensure!((-127..=127).contains(&x),"noise sum out of range");bytes.push(x as i8 as u8);}}
   file.write_all(&bytes)?;
  }
 }
 file.sync_all()?;
 fs::write(out.join("work.json"),serde_json::to_vec(&json!({"job_fingerprint":fp,"batch_id":id,"groups":(m/16)*(n/cfg.cols_pattern.size() as usize),"target_modified":false,"fresh_OS_randomness":true}))?)?;
 println!("Fresh real-target work prepared (no CPU GEMM / no network)");Ok(())
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
