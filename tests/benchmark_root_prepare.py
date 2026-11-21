"""Bounded CPU-only ABBA preparation benchmark, never contacts a pool or GPU."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--before-oracle',type=Path,required=True);p.add_argument('--after-oracle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--threads',type=int,default=4);args=p.parse_args()
 if not 1<=args.threads<=32 or args.out.exists():raise ValueError('Use a NEW result path and bounded thread count')
 before=args.before_oracle.resolve();after=args.after_oracle.resolve();assert before.is_file() and after.is_file()
 if shutil.disk_usage('/dev/shm').free < 2*1024**3:raise ValueError('Need at least 2GiB free tmpfs; no disk fallback')
 env=os.environ.copy();env['RAYON_NUM_THREADS']=str(args.threads);runs=[]
 with tempfile.TemporaryDirectory(prefix='pearl-CPU-ABBA-',dir='/dev/shm') as tmp:
  base=Path(tmp);base.chmod(0o700)
  for i,variant in enumerate(('before','after','before','after','after','before')):
   engine=before if variant=='before' else after;work=base/'work';started=time.monotonic()
   r=subprocess.run([str(engine),'work-prepare-raw',str(ROOT/'pool/captured-notify.json'),str(ROOT/'pool/client-reference.json'),str(work)],capture_output=True,text=True,env=env,timeout=120,check=True)
   wall=time.monotonic()-started;stages={}
   for line in r.stderr.splitlines():
    try:d=json.loads(line)
    except ValueError:continue
    if d.get('phase')=='prepare_timing':stages[d['stage']]=d['elapsed_seconds']
   meta=json.loads((work/'work.json').read_text());assert (work/'work.bin').stat().st_size==188 and meta['input_mode']=='raw-for-GPU-noise'
   audit=base/'audit.json'
   if i>=2:
    subprocess.run([str(after),'work-audit-roots',str(work),str(audit)],capture_output=True,text=True,timeout=120,check=True)
    assert json.loads(audit.read_text())['passed'];audit.unlink()
   runs.append({'warmup_excluded':i<2,'full_official_root_audit_passed':i>=2,'order':i,'variant':variant,'wall_seconds':wall,'stage_seconds':stages,'batch_id':meta['batch_id'],'raw_array_bytes':sum((work/name).stat().st_size for name in ('raw-a.bin','raw-bt.bin')),'commitment_backend':meta.get('commitment_backend','full-official-trees')})
   shutil.rmtree(work)
 assert len({r['batch_id'] for r in runs})==6
 means={v:sum(r['wall_seconds'] for r in runs if r['variant']==v and not r['warmup_excluded'])/2 for v in ('before','after')}
 result={'scope':'same-host CPU-only full-profile preparation ABBA; not GPU/live-miner or SRBMiner comparison','GPU_executed':False,'external_network_used':False,'rayon_threads':args.threads,'profile':{'m':131072,'n':131072,'k':4096,'rank':256,'proof_columns':16},'before_sha256':hashlib.sha256(before.read_bytes()).hexdigest(),'after_sha256':hashlib.sha256(after.read_bytes()).hexdigest(),'runs':runs,'mean_wall_seconds':means,'ratio_before_over_after':means['before']/means['after'],'temporary_RAM_cleaned':not base.exists()}
 args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'saved':str(args.out),'mean_wall_seconds':means,'CPU_prepare_speed_ratio':result['ratio_before_over_after'],'GPU_executed':False},indent=2))
if __name__=='__main__':main()
