"""Offline end-to-end oracle/packet test; GPU data below is explicitly CPU-simulated."""
import argparse,base64,copy,importlib.util,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('adapter',ROOT/'tools/luckypool_adapter.py');a=importlib.util.module_from_spec(s);sys.modules[s.name]=a;s.loader.exec_module(a)
def main():
 p=argparse.ArgumentParser();p.add_argument('--oracle',type=Path,required=True);p.add_argument('--batch',type=Path,required=True);args=p.parse_args();oracle=args.oracle.resolve();batch=args.batch.resolve()
 manifest=json.loads((batch/'manifest.json').read_text());raw=json.loads((batch/'job.json').read_text());profile=a.Profile.parse(json.loads((batch/'profile.json').read_text()));job=a.Job.parse(raw)
 simulated={k:manifest[k] for k in ('job_fingerprint','batch_id','transcripts')};simulated.update(hit_indices=manifest['expected_hits'],GPU_executed=False)
 with tempfile.TemporaryDirectory(prefix='pipeline-',dir=ROOT/'build') as tmp:
  tmp=Path(tmp);inp=tmp/'cpu-simulated.json';inp.write_text(json.dumps(simulated));out=tmp/'proofs'
  subprocess.run([str(oracle),'batch-finalize',str(batch),str(inp),str(out)],check=True)
  result=json.loads((out/'result.json').read_text());assert result['hit_count']==2 and result['input_claims_GPU_execution'] is False
  book=a.JobBook();book.update(job);frames=0
  for i in simulated['hit_indices']:
   proof=(out/f'hit-{i}.proof.bin').read_bytes();report=json.loads((out/f'hit-{i}-report.json').read_text())
   frame=a.submit_frame(job,profile,proof,report,'SYNTHETIC-NOT-A-WALLET','offline-pipeline',book);packet=json.loads(frame)
   assert base64.b64decode(packet['params']['plain_proof'],validate=True)==proof and frame.endswith(b'\n');frames+=1
  changes={
   'stale_job':lambda x:x.update(job_fingerprint='00'*32),
   'wrong_batch':lambda x:x.update(batch_id='00'*32),
   'missing_hit':lambda x:x['hit_indices'].pop(),
   'false_hit':lambda x:x['hit_indices'].append(next(i for i in range(4) if i not in x['hit_indices'])),
   'duplicate_hit':lambda x:x['hit_indices'].append(x['hit_indices'][0]),
   'transcript_corruption':lambda x:x['transcripts'][0].__setitem__(0,x['transcripts'][0][0]^1),
   'missing_transcript':lambda x:x['transcripts'].pop(),
   'out_of_range_hit':lambda x:x['hit_indices'].append(0xffffffff),
  }
  rejected=[]
  for name,change in changes.items():
   x=copy.deepcopy(simulated);change(x);inp.write_text(json.dumps(x));r=subprocess.run([str(oracle),'batch-finalize',str(batch),str(inp),str(tmp/name)],capture_output=True,text=True)
   assert r.returncode!=0,name;assert not (tmp/name).exists(),name;rejected.append(name)
  evidence={'official_proof_and_exact_target_passed':True,'candidates':4,'qualified_hits':2,'submit_frames_roundtripped':frames,'negative_cases_rejected':rejected,'GPU_executed':False,'GPU_input_source':'CPU-simulated only','synthetic_target':True,'real_pool_share_accepted':False,'network_used':False,'share_sent':False}
  (ROOT/'pool/PIPELINE-CPU-RESULT.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2))
if __name__=='__main__':main()
