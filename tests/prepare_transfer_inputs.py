"""Prepare TWO fixed LOCAL benchmark inputs, never a network session or GPU call."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from luckypool_adapter import Profile,MAX256

def main():
 p=argparse.ArgumentParser();p.add_argument('--oracle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--small',action='store_true');args=p.parse_args();out=args.out.resolve()
 if out.exists():raise ValueError('NEW output directory required')
 out.mkdir(parents=True,mode=0o700);profile_path=ROOT/('pool/pipeline-lab.json' if args.small else 'pool/client-reference.json');profile=json.loads(profile_path.read_text());cfg=Profile.parse(profile);inputs=[]
 for i in range(2):
  folder=out/str(i);folder.mkdir(mode=0o700);job=json.loads((ROOT/'pool/captured-notify.json').read_text());job['params']['job_id']=f'LOCAL-TRANSFER-BENCH-{i}-NEVER-SUBMIT'
  if args.small:job['params']['target']=f'{MAX256//cfg.factor():064x}'
  (folder/'job.json').write_text(json.dumps(job));(folder/'profile.json').write_text(json.dumps(profile));work=folder/'raw'
  subprocess.run([str(args.oracle.resolve()),'work-prepare-raw',str(folder/'job.json'),str(folder/'profile.json'),str(work)],check=True,capture_output=True)
  meta=json.loads((work/'work.json').read_text());inputs.append({'raw_manifest':str(work/'work.bin'),'batch_id':meta['batch_id'],'profile':profile,'groups':meta['groups']})
 assert inputs[0]['batch_id']!=inputs[1]['batch_id'];(out/'inputs.json').write_text(json.dumps({'inputs':inputs,'local_benchmark_only':True,'GPU_executed':False},indent=2)+'\n');print(json.dumps({'inputs':2,'small':args.small,'GPU_executed':False,'sent_shares':0}))
if __name__=='__main__':main()
