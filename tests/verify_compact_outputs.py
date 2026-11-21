"""Compare ALL actual GPU compact hits; independently verify boundary proofs. No GPU calls."""
import argparse,json,subprocess
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--oracle',type=Path,required=True);p.add_argument('--cases',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args();cases=json.loads(args.cases.read_text())['cases']
 if args.out.exists():raise ValueError('NEW output directory required')
 args.out.mkdir(parents=True,mode=0o700);proofs=0;groups=0
 for c in cases:
  cpu=json.loads(Path(c['CPU_hits']).read_text());gpu=json.loads(Path(c['GPU_hits']).read_text());assert gpu['GPU_executed'] is True and gpu['noise_backend']=='GPU' and gpu['raw_noise_input'] is True
  for k in ('job_fingerprint','batch_id'):assert cpu[k]==gpu[k]
  key=lambda h:h['index'];assert sorted(cpu['hits'],key=key)==sorted(gpu['hits'],key=key),'actual GPU hits/transcripts differ'
  selected={**gpu,'hits':[h for h in gpu['hits'] if h['index'] in c['sample_indices']]};assert len(selected['hits'])==len(c['sample_indices']);sample=args.out/f"sample-{c['case']}.json";sample.write_text(json.dumps(selected));dest=args.out/f"proofs-{c['case']}"
  subprocess.run([str(args.oracle.resolve()),'work-finalize',str(Path(c['raw_manifest']).parent),str(sample.resolve()),str(dest.resolve())],check=True,capture_output=True);assert json.loads((dest/'proofs.json').read_text())['official_checks_passed'];proofs+=len(selected['hits']);groups+=len(gpu['hits'])
 result={'GPU_all_hits_compared':groups,'official_GPU_proofs':proofs,'row_and_column_boundary_cases_passed':True,'pool_share_sent':False};(args.out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
