"""Full loopback pool + official Rust proofs + independent C++ arithmetic; no GPU."""
import argparse,asyncio,base64,copy,hashlib,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import pearl_miner as m
from luckypool_adapter import MAX256,Profile
async def test(args):
 profile_path=ROOT/'pool/pipeline-lab.json';profile=Profile.parse(json.loads(profile_path.read_text()));raw=json.loads((ROOT/'pool/captured-notify.json').read_text());raw['params']['job_id']='MOCK-POOL-ONLY';raw['params']['target']=f'{MAX256//profile.factor():064x}'
 seen=set();accepted=0;rejected=0;errors=[];handlers=set()
 with tempfile.TemporaryDirectory(prefix='live-loop-',dir=ROOT/'build') as tmp:
  tmp=Path(tmp);jobfile=tmp/'notify.json';jobfile.write_text(json.dumps(raw))
  async def serve(reader,writer):
   nonlocal accepted,rejected
   task=asyncio.current_task();handlers.add(task)
   try:
    request=json.loads(await reader.readline());assert request['method']=='mining.authorize'
    writer.write(b'{"id":1,"result":true,"error":null,"type":"plain"}\n');writer.write((json.dumps(raw)+'\n').encode());await writer.drain()
    while line:=await reader.readline():
     req=json.loads(line);assert req['method']=='mining.submit' and req['params']['job_id']=='MOCK-POOL-ONLY';proof=base64.b64decode(req['params']['plain_proof'],validate=True);sha=hashlib.sha256(proof).hexdigest();assert sha not in seen,'duplicate work';seen.add(sha)
     folder=tmp/f'check-{len(seen)}';folder.mkdir();proofpath=folder/'proof.bin';reportpath=folder/'report.json';proofpath.write_bytes(proof)
     await m.child([args.oracle,'pool-verify',jobfile,profile_path,proofpath,reportpath],10)
     report=json.loads(reportpath.read_text());assert report['structural_verifier_passed'] and report['share_target_passed']
     # One intentional pool rejection per batch verifies accounting, not invalid arithmetic.
     reject=len(seen)%4==0
     if reject:rejected+=1
     else:accepted+=1
     writer.write((json.dumps({'id':req['id'],'result':not reject,'error':'intentional_mock_rejection' if reject else None})+'\n').encode());await writer.drain()
   except Exception as e:errors.append(repr(e))
   finally:writer.close();await writer.wait_closed();handlers.discard(task)
  server=await asyncio.start_server(serve,'127.0.0.1',0,limit=8*1024*1024)
  backend=m.Backend(args.oracle,args.engine,profile_path,cpu=True);workdir=tmp/'private';workdir.mkdir(mode=0o700)
  config=tmp/'config.json';config.write_text(json.dumps({'host':'127.0.0.1','port':server.sockets[0].getsockname()[1],'wallet':'MOCK-NOT-A-WALLET','worker':'offline','profile':str(profile_path)}));config.chmod(0o600)
  try:
   proc=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'tools/pearl_miner.py'),'--config',str(config),'--oracle',str(args.oracle),'--engine',str(args.engine),'--mock-cpu',*(['--pipeline'] if args.pipeline else []),'--measure-stability','--enable-submit','--max-batches','2','--duration','25','--workdir',str(workdir),'--evidence',str(tmp/'evidence'),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
   stdout,stderr=await asyncio.wait_for(proc.communicate(),28)
   assert proc.returncode==0,(stdout.decode(),stderr.decode())
   records=[json.loads(line) for line in stdout.decode().splitlines()];final=next(r for r in records if r.get('event')=='final');assert final['scope']=='mock';performance=final['performance'];assert performance['completed_candidate_groups']==8 and performance['fresh_finished_candidate_groups']==8 and performance['unclassified_completed_candidate_groups']==0;assert performance['wall_seconds']>0 and performance['stages']['prepare']['completed']>=2 and all(performance['stages'][name]['completed']==2 for name in ('GPU','proofs'));counts=m.Counts(**{k:final[k] for k in vars(m.Counts())})
   assert len(list((tmp/'evidence').glob('*/proofs.log')))==2
   assert len(list((tmp/'evidence').glob('*/events.jsonl')))>=2
   if args.pipeline:assert (tmp/'evidence/persistent-engine.stderr.log').is_file()
   else:assert len(list((tmp/'evidence').glob('*/GPU.log')))==2
   assert len(list((tmp/'evidence/accepted').glob('*.proof.bin')))==6
   assert len(list((tmp/'evidence/accepted').glob('*.receipt.json')))==6

  finally:
   server.close();await server.wait_closed()
   if handlers:await asyncio.gather(*list(handlers))
  if args.pipeline:
   assert performance['persistent_engine']['process_starts']==1 and performance['persistent_engine']['completed_requests']==2 and performance['persistent_engine']['process_reaped']
   assert performance['RAM_workspace_cleaned'];assert performance['persistent_engine']['exit_code']==0 and not performance['persistent_engine']['shutdown_forced']
  assert not errors,errors
  assert counts.batches==2 and counts.sent==8 and counts.accepted==6 and counts.rejected==2 and counts.unknown==0,counts.public()
  assert not any(workdir.iterdir()),'temporary work not removed'
  result={'pipeline_enabled':args.pipeline,'single_persistent_process_verified':args.pipeline,'RAM_workspace_cleaned':performance.get('RAM_workspace_cleaned'),'actual_CLI_entry_tested':True,'full_wall_rate_accounting_checked':True,'completed_fresh_candidate_groups':8,'loopback_pool_only':True,'external_pool_contacted':False,'GPU_executed':False,'arithmetic_backend':'independent C++ CPU reference','official_verifier_checked_each_received_proof':True,'fresh_unique_proof_hashes':len(seen),'counts':counts.public(),'real_pool_share_accepted':False,'GPU_live_worker_tested':False,'temporary_work_cleaned':True}
  (ROOT/('miner/PIPELINE-LOOPBACK-RESULT.json' if args.pipeline else 'miner/LOOPBACK-RESULT.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
def main():
 p=argparse.ArgumentParser();p.add_argument('--pipeline',action='store_true');p.add_argument('--oracle',type=Path,required=True);p.add_argument('--engine',type=Path,required=True);args=p.parse_args();args.oracle=args.oracle.resolve();args.engine=args.engine.resolve();asyncio.run(test(args))
if __name__=='__main__':main()
