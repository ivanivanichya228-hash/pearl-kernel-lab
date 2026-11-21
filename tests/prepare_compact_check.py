"""Three local-only raw inputs, including BOTH 8192 slab boundaries; no GPU/network."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from luckypool_adapter import Profile,MAX256

def main():
 p=argparse.ArgumentParser();p.add_argument('--oracle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args();oracle=args.oracle.resolve();out=args.out.resolve()
 if out.exists():raise ValueError('NEW output directory required')
 out.mkdir(parents=True,mode=0o700);cases=[]
 for index,(m,n,k,rank,pn) in enumerate([(32,32,4096,256,16),(8208,8,2048,128,8),(16,8208,2048,128,16)]):
  folder=out/str(index);folder.mkdir(mode=0o700);profile={'m':m,'n':n,'k':k,'rank':rank,'mma_type':0,'row_pattern':list(range(16)),'column_pattern':list(range(pn))};config=Profile.parse(profile)
  job=json.loads((ROOT/'pool/captured-notify.json').read_text());job['params']['target']=f'{MAX256//config.factor():064x}';job['params']['job_id']=f'LOCAL-COMPACT-CHECK-{index}-NEVER-SUBMIT'
  (folder/'job.json').write_text(json.dumps(job));(folder/'profile.json').write_text(json.dumps(profile));work=folder/'raw';hits=folder/'cpu-hits.json'
  def run(cmd):subprocess.run(list(map(str,cmd)),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  run([oracle,'work-prepare-raw',folder/'job.json',folder/'profile.json',work]);run([ROOT/'build/work-cpu',work/'work.bin',hits]);data=json.loads(hits.read_text());expected=(m//16)*(n//pn);assert len(data['hits'])==expected
  sampled=[0,1,2,3] if index==0 else [0,511,512];sample={**data,'hits':[h for h in data['hits'] if h['index'] in sampled]};assert len(sample['hits'])==len(sampled);(folder/'cpu-sample.json').write_text(json.dumps(sample));run([oracle,'work-finalize',work,folder/'cpu-sample.json',folder/'cpu-proofs'])
  cases.append({'case':index,'m':m,'n':n,'k':k,'rank':rank,'proof_columns':pn,'groups':expected,'slabs':((m+8191)//8192)*((n+8191)//8192),'raw_manifest':str(work/'work.bin'),'CPU_hits':str(hits),'GPU_hits':str(folder/'gpu-hits.json'),'sample_indices':sampled})
 (out/'cases.json').write_text(json.dumps({'cases':cases,'synthetic_local_only':True,'GPU_executed':False},indent=2)+'\n');print(json.dumps({'cases':len(cases),'crosses_row_and_column_slab_boundaries':True,'CPU_groups_compared':sum(c['groups'] for c in cases),'official_CPU_proofs':10,'GPU_executed':False}))
if __name__=='__main__':main()
