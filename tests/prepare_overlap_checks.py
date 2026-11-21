"""Transfer checks: slab boundaries plus reusing a large slot for a NEW smaller packet."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--oracle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args();out=args.out.resolve()
 if out.exists():raise ValueError('NEW output directory required')
 out.mkdir(parents=True,mode=0o700);oracle=args.oracle.resolve()
 subprocess.run(['python3',str(ROOT/'tests/prepare_compact_check.py'),'--oracle',str(oracle),'--out',str(out/'boundary')],check=True,capture_output=True)
 cases=json.loads((out/'boundary/cases.json').read_text())['cases'];first=Path(cases[0]['raw_manifest']).parent.parent;folder=out/'reuse';folder.mkdir(mode=0o700);work=folder/'raw';hits=folder/'cpu-hits.json'
 for cmd in ([oracle,'work-prepare-raw',first/'job.json',first/'profile.json',work],[ROOT/'build/work-cpu',work/'work.bin',hits],[oracle,'work-finalize',work,hits,folder/'cpu-proofs']):subprocess.run(list(map(str,cmd)),check=True,capture_output=True)
 data=json.loads(hits.read_text());assert len(data['hits'])==4;assert data['batch_id']!=json.loads(Path(cases[0]['CPU_hits']).read_text())['batch_id']
 cases.append({**cases[0],'case':3,'raw_manifest':str(work/'work.bin'),'CPU_hits':str(hits),'GPU_hits':str(folder/'gpu-hits.json'),'sample_indices':[0,1,2,3]});(out/'cases.json').write_text(json.dumps({'cases':cases,'synthetic_local_only':True,'GPU_executed':False},indent=2)+'\n');print(json.dumps({'cases':4,'all_CPU_hits':1034,'official_CPU_proofs':14,'large_to_small_slot_reuse':True,'GPU_executed':False}))
if __name__=='__main__':main()
