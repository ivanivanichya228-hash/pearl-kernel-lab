"""Prepare bounded independent official-noise fixtures and CPU proofs. No GPU/network."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from luckypool_adapter import Profile,MAX256

def main():
 p=argparse.ArgumentParser();p.add_argument('--oracle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args();oracle=args.oracle.resolve();out=args.out.resolve()
 if out.exists():raise ValueError('Use a NEW output directory')
 out.mkdir(parents=True,mode=0o700);cases=[];total_bytes=0;total_proofs=0
 for index,(rank,k,columns,m,n) in enumerate([(128,2048,16,32,32),(128,2048,8,48,24),(256,4096,16,32,32),(256,4096,8,48,24)]):
  folder=out/str(index);folder.mkdir(mode=0o700);profile={'m':m,'n':n,'k':k,'rank':rank,'mma_type':0,'row_pattern':list(range(16)),'column_pattern':list(range(columns))};config=Profile.parse(profile)
  job=json.loads((ROOT/'pool/captured-notify.json').read_text());job['params']['target']=f'{MAX256//config.factor():064x}';job['params']['job_id']=f'LOCAL-GPU-NOISE-CHECK-{index}-NEVER-SUBMIT'
  (folder/'job.json').write_text(json.dumps(job));(folder/'profile.json').write_text(json.dumps(profile));work=folder/'raw';ref=folder/'official-noised.bin';hits=folder/'cpu-hits.json';proofs=folder/'cpu-proofs'
  def run(cmd):subprocess.run(list(map(str,cmd)),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  run([oracle,'work-prepare-raw',folder/'job.json',folder/'profile.json',work]);run([oracle,'work-reference-noise',work,ref]);run([ROOT/'build/test-noise-reference',work/'work.bin',ref]);run([ROOT/'build/work-cpu',work/'work.bin',hits]);run([oracle,'work-finalize',work,hits,proofs])
  received=json.loads(hits.read_text());expected=(m//16)*(n//columns);assert received['noise_backend']=='CPU-reference' and len(received['hits'])==expected
  assert (work/'work.bin').stat().st_size==188,'raw manifest unexpectedly carries a large noised payload'
  assert json.loads((work/'work.json').read_text())['input_mode']=='raw-for-GPU-noise'
  count=json.loads((proofs/'proofs.json').read_text())['indices'];assert len(count)==expected;checked_bytes=(m+n)*k;total_bytes+=checked_bytes;total_proofs+=expected
  cases.append({'case':index,'rank':rank,'k':k,'proof_columns':columns,'m':m,'n':n,'raw_manifest':str(work/'work.bin'),'official_reference':str(ref),'CPU_hits':str(hits),'all_bytes_matched':checked_bytes,'official_proofs_verified':expected})
 (out/'cases.json').write_text(json.dumps({'cases':cases,'synthetic_local_only':True},indent=2)+'\n')
 evidence={'unmodified_official_noise_arrays_matched':True,'cases':len(cases),'rank_values':[128,256],'proof_column_values':[8,16],'all_A_B_bytes_compared':total_bytes,'official_plain_proofs_verified':total_proofs,'raw_manifest_bytes':188,'CPU_noise_skipped_in_raw_preparation':True,'GPU_executed':False,'external_network_used':False,'real_pool_share_accepted':False,'note':'Independent C++ implementation of intended GPU algorithm versus unmodified official Rust arrays and verifier; actual GPU check pending.'}
 (ROOT/'miner/GPU-NOISE-CPU-RESULT.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2))
if __name__=='__main__':main()
