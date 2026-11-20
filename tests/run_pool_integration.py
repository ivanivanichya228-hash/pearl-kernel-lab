"""CPU-only integration against the built official Rust bridge. Never opens a socket."""
import argparse,base64,hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('adapter',ROOT/'tools/luckypool_adapter.py');a=importlib.util.module_from_spec(s);sys.modules[s.name]=a;s.loader.exec_module(a)
def main():
 p=argparse.ArgumentParser();p.add_argument('--oracle',type=Path,required=True);p.add_argument('--fixtures',type=Path,required=True);args=p.parse_args()
 out=ROOT/'build/pool-integration';out.mkdir(parents=True,exist_ok=True)
 profile={'name':'synthetic-wire-test','m':64,'n':64,'k':4096,'rank':128,'mma_type':0,'row_pattern':list(range(16)),'column_pattern':list(range(16))}
 config=a.Profile.parse(profile);target=a.MAX256//config.factor()
 raw={'id':None,'method':'mining.notify','params':{'cert_version':3,'header':(args.fixtures/'case-3.header.bin').read_bytes().hex(),'target':f'{target:064x}','job_id':'SYNTHETIC-WIRE-TEST','height':0}}
 (out/'job.json').write_text(json.dumps(raw));(out/'profile.json').write_text(json.dumps(profile))
 proof_path=args.fixtures/'case-3.proof.bin';report_path=out/'verification.json'
 subprocess.run([str(args.oracle),'pool-verify',str(out/'job.json'),str(out/'profile.json'),str(proof_path),str(report_path)],check=True)
 report=json.loads(report_path.read_text());job=a.Job.parse(raw);book=a.JobBook();book.update(job);proof=proof_path.read_bytes()
 assert report['share_target_passed'] is True
 assert report['job_fingerprint']==job.fingerprint()
 assert int(report['share_bound_hex'],16)==config.bound(job)
 frame=a.submit_frame(job,config,proof,report,'SYNTHETIC-NOT-A-WALLET','wire-test',book)
 wire=json.loads(frame)
 assert frame.endswith(b'\n') and frame.count(b'\n')==1 and wire['method']=='mining.submit'
 assert base64.b64decode(wire['params']['plain_proof'],validate=True)==proof
 negatives=[]
 try:a.submit_frame(job,config,proof+b'X',report,'fake','fake',book)
 except ValueError:negatives.append('altered_proof_bytes')
 book.update(a.Job.parse({**raw,'params':{**raw['params'],'job_id':'different-job'}}))
 try:a.submit_frame(job,config,proof,report,'fake','fake',book)
 except ValueError:negatives.append('stale_job')
 # Same proof cannot be rebound to the captured real header.
 wrong=subprocess.run([str(args.oracle),'pool-verify',str(ROOT/'pool/captured-notify.json'),str(out/'profile.json'),str(proof_path),str(out/'wrong-report.json')],capture_output=True,text=True)
 assert wrong.returncode!=0;negatives.append('foreign_job_header')
 real=json.loads((ROOT/'build/real-header-candidate/candidate-report.json').read_text())
 realjob=a.Job.parse(json.loads((ROOT/'pool/captured-notify.json').read_text()));realprofile=a.Profile.parse(json.loads((ROOT/'pool/lab-small.json').read_text()))
 realproof=(ROOT/'build/real-header-candidate/candidate.proof.bin').read_bytes();book.update(realjob)
 assert real['job_fingerprint']==realjob.fingerprint() and int(real['share_bound_hex'],16)==realprofile.bound(realjob)
 assert real['structural_verifier_passed'] is True and real['share_target_passed'] is False
 try:a.submit_frame(realjob,realprofile,realproof,real,'fake','fake',book)
 except ValueError:negatives.append('real_target_not_met')
 assert len(negatives)==4
 result={'synthetic_submit_frame_roundtrip_passed':True,'official_proof_bytes_preserved':True,'Rust_and_Python_context_and_bounds_match':True,'negative_cases_rejected':negatives,'real_header_structural_verifier_passed':True,'real_candidate_share_target_passed':False,'pool_policy_verified':False,'real_pool_share_accepted':False,'GPU_used':False,'network_used':False,'synthetic_frame_sha256':hashlib.sha256(frame).hexdigest()}
 (ROOT/'pool/CPU-RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
