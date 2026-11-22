"""Independent bounded proof/target/freshness checks of the mapped CPU producer."""
import json,subprocess,tempfile,sys
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--oracle',type=Path,required=True);p.add_argument('--producer',type=Path,required=True);p.add_argument('--engine',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
if args.out.exists():raise ValueError('NEW result file required')
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
from luckypool_adapter import Profile,MAX256
oracle=args.oracle.resolve();producer=args.producer.resolve();engine=args.engine.resolve()
def run(argv):return subprocess.run(list(map(str,argv)),check=True,capture_output=True,text=True)
res=[]
with tempfile.TemporaryDirectory(prefix='pearl-mapped-cpu-',dir='/dev/shm') as tmp:
 t=Path(tmp)
 for i,(rank,k,cols,m,n) in enumerate([(128,2048,16,32,32),(128,2048,8,48,24),(256,4096,16,32,32),(256,4096,8,48,24)]):
  p={'m':m,'n':n,'k':k,'rank':rank,'mma_type':0,'row_pattern':list(range(16)),'column_pattern':list(range(cols))}
  j=json.loads((root/'pool/captured-notify.json').read_text());j['params']['target']=f'{MAX256//Profile.parse(p).factor():064x}';j['params']['job_id']='MAPPED-CPU-NEVER-SUBMIT'
  pf=t/'profile.json';jf=t/'job.json';pf.write_text(json.dumps(p));jf.write_text(json.dumps(j))
  w=t/f'work{i}';run([producer,'work-prepare-mapped',jf,pf,w]);run([oracle,'work-audit-roots',w,t/f'audit{i}.json']);hits=t/f'hits{i}.json';run([engine,w/'work.bin',hits]);proofs=t/f'proofs{i}';run([oracle,'work-finalize',w,hits,proofs])
  indices=json.loads((proofs/'proofs.json').read_text())['indices'];assert len(indices)==(m//16)*(n//cols)
  for index in indices:
   report=t/f'report{i}-{index}.json';run([oracle,'pool-verify',jf,pf,proofs/f'hit-{index}.proof.bin',report]);d=json.loads(report.read_text());assert d['structural_verifier_passed'] and d['share_target_passed']
  res.append({'rank':rank,'k':k,'cols':cols,'proofs':len(indices),'all_header_bytes_audited':188})
 # identical context must still generate fresh raw operands and batch id
 pf.write_text((root/'pool/pipeline-lab.json').read_text());j['params']['target']=f'{MAX256//Profile.parse(json.loads(pf.read_text())).factor():064x}';jf.write_text(json.dumps(j))
 for i in range(2):run([producer,'work-prepare-mapped',jf,pf,t/f'fresh{i}'])
 assert (t/'fresh0/raw-a.bin').read_bytes()!=(t/'fresh1/raw-a.bin').read_bytes()
 assert json.loads((t/'fresh0/work.json').read_text())['batch_id']!=json.loads((t/'fresh1/work.json').read_text())['batch_id']
print(json.dumps({'cases':res,'total_official_proofs':sum(x['proofs'] for x in res),'freshness_passed':True,'GPU_executed':False,'real_pool_share':False}))
args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps({'cases':res,'total_official_proofs':sum(x['proofs'] for x in res),'freshness_passed':True,'GPU_executed':False,'real_pool_share':False},indent=2)+'\n')
