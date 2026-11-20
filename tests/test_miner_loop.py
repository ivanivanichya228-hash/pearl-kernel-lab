"""Protocol lifecycle tests over real loopback sockets; no GPU or external pool."""
import asyncio,contextlib,copy,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import pearl_miner as m
from luckypool_adapter import Job,Profile,MAX256
BASE=json.loads((ROOT/'pool/captured-notify.json').read_text());PROFILE=Profile.parse(json.loads((ROOT/'pool/pipeline-lab.json').read_text()))
def job(name='fresh'):
 raw=copy.deepcopy(BASE);raw['params']['job_id']=name;raw['params']['target']=f'{MAX256//PROFILE.factor():064x}';return raw
class WaitingBackend:
 def __init__(self):self.started=asyncio.Event();self.cancelled=False;self.jobs=[]
 async def batch(self,raw,path):
  self.jobs.append(raw['params']['job_id']);self.started.set()
  if len(self.jobs)==1:
   try:await asyncio.sleep(10)
   except asyncio.CancelledError:self.cancelled=True;raise
  return []
class Tests(unittest.IsolatedAsyncioTestCase):
 async def pair(self):
  future=asyncio.get_running_loop().create_future()
  async def accept(r,w):future.set_result((r,w))
  server=await asyncio.start_server(accept,'127.0.0.1',0);client=await asyncio.open_connection('127.0.0.1',server.sockets[0].getsockname()[1]);peer=await future
  self.addAsyncCleanup(self.close,server,client[1],peer[1]);return client,peer
 async def close(self,server,*writers):
  for w in writers:w.close()
  await asyncio.gather(*(w.wait_closed() for w in writers),return_exceptions=True);server.close();await server.wait_closed()
 async def test_same_id_changed_target_cancels_work(self):
  client,peer=await self.pair();counts=m.Counts();session=m.Session(*client,'fake','test',PROFILE,counts);reader=asyncio.create_task(session.read());backend=WaitingBackend()
  with tempfile.TemporaryDirectory() as path:
   loop=asyncio.create_task(m.mining(session,backend,Path(path),counts,1,False));peer[1].write((json.dumps(job('same'))+'\n').encode());await peer[1].drain();await backend.started.wait()
   changed=job('same');changed['params']['target']=f'{MAX256//PROFILE.factor()-1:064x}';peer[1].write((json.dumps(changed)+'\n').encode());await peer[1].drain();await asyncio.wait_for(loop,3)
   self.assertTrue(backend.cancelled);self.assertEqual(counts.stale,1);self.assertEqual(counts.sent,0)
  reader.cancel();await asyncio.gather(reader,return_exceptions=True)
 async def test_difficulty_invalidates_instead_of_guessing(self):
  client,peer=await self.pair();session=m.Session(*client,'fake','test',PROFILE,m.Counts());session.book.update(Job.parse(job()));reader=asyncio.create_task(session.read());peer[1].write(b'{"method":"mining.set_difficulty","params":[1]}\n');await peer[1].drain();await asyncio.wait_for(session.changed.wait(),1);self.assertIsNone(session.book.current);reader.cancel();await asyncio.gather(reader,return_exceptions=True)
 async def test_nonplain_auth_rejected(self):
  client,peer=await self.pair();session=m.Session(*client,'fake','test',PROFILE,m.Counts());reader=asyncio.create_task(session.read());auth=asyncio.create_task(session.authorize());await peer[0].readline();peer[1].write(b'{"id":1,"result":true,"error":null,"type":"zk"}\n');await peer[1].drain()
  with self.assertRaises(m.ProtocolError):await reader
  await asyncio.gather(auth,return_exceptions=True)
 async def test_reader_disconnect_invalidates_context(self):
  client,peer=await self.pair();session=m.Session(*client,'fake','test',PROFILE,m.Counts());session.book.update(Job.parse(job()));session.authorized.set_result(True);reader=asyncio.create_task(session.read());peer[1].close()
  with self.assertRaises(ConnectionError):await reader
  self.assertIsNone(session.book.current);self.assertTrue(session.closed)
 async def test_pending_response_unknown_on_disconnect(self):
  client,peer=await self.pair();counts=m.Counts();session=m.Session(*client,'fake','test',PROFILE,counts);session.authorized.set_result(True);future=asyncio.get_running_loop().create_future();session.pending[99]=future;reader=asyncio.create_task(session.read());peer[1].close()
  with self.assertRaises(ConnectionError):await reader
  self.assertEqual(counts.unknown,1);self.assertTrue((await future)['_unknown']);self.assertEqual(counts.accepted,0)
 async def test_private_credential_file_permissions(self):
  with tempfile.TemporaryDirectory() as path:
   p=Path(path)/'credentials';p.write_text('{"wallet":"fake","worker":"test"}');p.chmod(0o644)
   with self.assertRaises(ValueError):m.read_credentials(p)
   p.chmod(0o600);self.assertEqual(m.read_credentials(p)['worker'],'test')
 async def test_cancelled_stage_log_survives_next_batch(self):
  with tempfile.TemporaryDirectory() as path:
   first=Path(path)/'batch-first';second=Path(path)/'batch-second';first.mkdir();second.mkdir();log=first/'prepare.log'
   task=asyncio.create_task(m.child([sys.executable,'-u','-c','import time;print("FIRST",flush=True);time.sleep(30)'],20,log_path=log))
   for _ in range(100):
    if log.exists() and 'FIRST' in log.read_text():break
    await asyncio.sleep(.01)
   else:self.fail('child did not start')
   task.cancel()
   with self.assertRaises(asyncio.CancelledError):await task
   await m.child([sys.executable,'-c','print("SECOND")'],5,log_path=second/'prepare.log')
   self.assertEqual(log.read_text().strip(),'FIRST');self.assertEqual((second/'prepare.log').read_text().strip(),'SECOND')
   events=[json.loads(line) for line in (first/'events.jsonl').read_text().splitlines()];self.assertEqual(events[-1]['outcome'],'cancelled');self.assertGreater(events[-1]['elapsed_seconds'],0)
 async def test_child_cancel_reaps_process(self):
  task=asyncio.create_task(m.child([sys.executable,'-c','import time;time.sleep(30)'],20));await asyncio.sleep(.1);task.cancel()
  with self.assertRaises(asyncio.CancelledError):await task
if __name__=='__main__':unittest.main()
