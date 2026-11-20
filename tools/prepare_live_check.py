#!/usr/bin/env python3
"""Prepare one small real-work-format check, before any miner pause. No network/GPU."""
import argparse,json,subprocess
from pathlib import Path
from luckypool_adapter import Profile,MAX256
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--oracle',type=Path,default=ROOT/'build/pearl-protocol-oracle');args=p.parse_args()
 if args.out.exists():raise ValueError('Use a new output directory')
 args.out.mkdir(parents=True);raw=json.loads((ROOT/'pool/captured-notify.json').read_text());profile=Profile.parse(json.loads((ROOT/'pool/pipeline-lab.json').read_text()));raw['params']['target']=f'{MAX256//profile.factor():064x}';raw['params']['job_id']='LOCAL-WORKER-CHECK-NEVER-SUBMIT'
 job=args.out/'job.json';job.write_text(json.dumps(raw));subprocess.run([str(args.oracle),'work-prepare',str(job),str(ROOT/'pool/pipeline-lab.json'),str(args.out/'work')],check=True)
 print('Prepared four guaranteed-hit candidates; no share sent, no GPU work')
if __name__=='__main__':main()
