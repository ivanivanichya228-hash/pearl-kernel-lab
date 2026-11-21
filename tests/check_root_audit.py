"""Independent full-tree audit must reject changed seeds, target and matrix content."""
import argparse,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--oracle',type=Path,required=True);p.add_argument('--cases',type=Path,required=True);args=p.parse_args();engine=args.oracle.resolve();cases=json.loads(args.cases.read_text())['cases'];checked=0;rejected=0
 with tempfile.TemporaryDirectory(prefix='root-audit-',dir=ROOT/'build') as temp:
  temp=Path(temp)
  for case in cases:
   work=Path(case['raw_manifest']).parent;out=temp/f"good-{case['case']}.json"
   subprocess.run([str(engine),'work-audit-roots',str(work),str(out)],check=True,capture_output=True);assert json.loads(out.read_text())['passed'];checked+=1
  work=Path(cases[0]['raw_manifest']).parent
  for file,offset in [('work.bin',92),('work.bin',124),('work.bin',156),('raw-a.bin',0)]:
   path=work/file;original=path.read_bytes();mutated=bytearray(original);mutated[offset]^=1
   try:
    path.write_bytes(mutated);out=temp/f'bad-{rejected}.json';run=subprocess.run([str(engine),'work-audit-roots',str(work),str(out)],capture_output=True)
    assert run.returncode!=0 and not out.exists(),'audit accepted tampered input';rejected+=1
   finally:path.write_bytes(original)
 evidence={'official_full_tree_header_audits_passed':checked,'tampered_A_seed_B_seed_target_matrix_rejected':rejected,'GPU_executed':False,'external_network_used':False}
 (ROOT/'miner/ROOT-AUDIT-CPU-RESULT.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence))
if __name__=='__main__':main()
