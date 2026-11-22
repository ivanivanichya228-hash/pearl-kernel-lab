"""CPU-only full-profile A/B/B/A, with separate warmups and original-oracle audits."""
import argparse,hashlib,json,os,platform,shutil,statistics,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--oracle',type=Path,required=True);p.add_argument('--producer',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--threads',type=int,default=4);p.add_argument('--ram-dir',type=Path,default=Path('/dev/shm'));a=p.parse_args()
 if a.out.exists() or not 1<=a.threads<=32:raise ValueError('NEW output and1..32threads required')
 if shutil.disk_usage(a.ram_dir).free<2*1024**3:raise ValueError('Need2GiB free temporary RAM space')
 env={**os.environ,'RAYON_NUM_THREADS':str(a.threads)};rows=[]
 oracle=a.oracle.resolve();producer=a.producer.resolve()
 with tempfile.TemporaryDirectory(prefix='mapped-prep-',dir=a.ram_dir) as tmp:
  base=Path(tmp)
  for i,kind in enumerate(['original','mapped','original','mapped','mapped','original']):
   work=base/'work';start=time.monotonic()
   proc=subprocess.run([str(producer if kind=='mapped' else oracle),'work-prepare-mapped' if kind=='mapped' else 'work-prepare-raw',str(ROOT/'pool/captured-notify.json'),str(ROOT/'miner/luckypool-profile.json'),str(work)],capture_output=True,text=True,check=True,env=env,timeout=120)
   elapsed=time.monotonic()-start;phases=[]
   for line in proc.stderr.splitlines():
    try:d=json.loads(line)
    except ValueError:continue
    if d.get('phase')=='prepare_timing':phases.append(d)
   row={'order':i,'warmup_excluded':i<2,'kind':kind,'wall_seconds':elapsed,'phases':phases,'raw_bytes':sum((work/n).stat().st_size for n in ['raw-a.bin','raw-bt.bin'])}
   meta=json.loads((work/'work.json').read_text());row['batch_id']=meta['batch_id']
   assert row['raw_bytes']==1073741824 and (work/'work.bin').stat().st_size==188
   if i>=2:
    audit=base/f'audit{i}.json';subprocess.run([str(oracle),'work-audit-roots',str(work),str(audit)],check=True,capture_output=True,env=env,timeout=120);assert json.loads(audit.read_text())['passed'];row['independent_full_root_audit']=True
   rows.append(row);shutil.rmtree(work);print(json.dumps(row),flush=True)
 assert len({r['batch_id']for r in rows})==6
 means={k:statistics.mean(r['wall_seconds']for r in rows if r['kind']==k and not r['warmup_excluded'])for k in ['original','mapped']}
 result={'scope':'cloud CPU preparation only; not GPU hashrate','order':[r['kind']for r in rows],'rows':rows,'mean_wall_seconds':means,'ratio_original_over_mapped':means['original']/means['mapped'],'reduction_fraction':1-means['mapped']/means['original'],'rayon_threads':a.threads,'system':platform.platform(),'oracle_sha256':hashlib.sha256(oracle.read_bytes()).hexdigest(),'producer_sha256':hashlib.sha256(producer.read_bytes()).hexdigest(),'GPU_executed':False,'external_network_used':False,'temporary_RAM_cleaned':not base.exists()}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['mean_wall_seconds','ratio_original_over_mapped','reduction_fraction']}))
if __name__=='__main__':main()
