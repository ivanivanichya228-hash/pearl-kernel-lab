"""Producer/consumer ownership, overlap, stale work and global cancellation; no GPU."""
import asyncio,contextlib,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from miner_pipeline import mining
from persistent_engine import PersistentEngine
from pearl_miner import Counts
class Service:
 def __init__(self):self.starts=0;self.closes=0
 async def start(self):self.starts+=1
 async def close(self):self.closes+=1
class Backend:
 def __init__(self,root,session,mode='overlap'):
  self.root=root;self.session=session;self.mode=mode;self.service=Service();self.metrics=SimpleNamespace(classify=lambda *x:None);self.prepares=0;self.finishes=0;self.max_live=0;self.started=asyncio.Event();self.second=asyncio.Event();self.overlap=False
 def sample(self):self.max_live=max(self.max_live,len(list(self.root.glob('batch-*'))))
 async def prepare(self,raw,root):
  self.prepares+=1;index=self.prepares;self.sample()
  if index==2:
   await self.started.wait();self.overlap=True;self.second.set()
   if self.mode=='prepare_failure':raise RuntimeError('intentional prepare failure')
  if index>2:await asyncio.sleep(.01)
  return {'index':index,'root':root}
 async def finish(self,data,service):
  self.finishes+=1;self.sample();self.started.set()
  if self.mode=='cancel':await asyncio.sleep(30)
  if self.finishes==1:
   await asyncio.wait_for(self.second.wait(),1)
   if self.mode=='stale':
    self.session.generation+=1;self.session.raw={'job':'new'};self.session.changed.set()
   await asyncio.sleep(.02)
  return []
def session():return SimpleNamespace(raw={'job':'old'},generation=1,book=SimpleNamespace(current=object()),changed=asyncio.Event())
class PipelineTests(unittest.IsolatedAsyncioTestCase):
 async def test_overlap_and_two_slot_bound(self):
  with tempfile.TemporaryDirectory() as p:
   root=Path(p);s=session();b=Backend(root,s);counts=Counts();await asyncio.wait_for(mining(s,b,root,counts,2,False),2)
   self.assertTrue(b.overlap);self.assertLessEqual(b.max_live,2);self.assertEqual(counts.batches,2);self.assertEqual(b.service.starts,1);self.assertEqual(b.service.closes,1);self.assertFalse(list(root.iterdir()))
 async def test_prepare_failure_cleans_every_workspace(self):
  with tempfile.TemporaryDirectory() as p:
   root=Path(p);s=session();b=Backend(root,s,'prepare_failure')
   with self.assertRaisesRegex(RuntimeError,'intentional'):await asyncio.wait_for(mining(s,b,root,Counts(),0,False),2)
   self.assertEqual(b.service.closes,1);self.assertFalse(list(root.iterdir()))
 async def test_new_job_does_not_restart_engine(self):
  with tempfile.TemporaryDirectory() as p:
   root=Path(p);s=session();b=Backend(root,s,'stale');counts=Counts();await asyncio.wait_for(mining(s,b,root,counts,1,False),2)
   self.assertGreaterEqual(counts.stale,1);self.assertEqual(counts.batches,1);self.assertEqual(b.service.starts,1);self.assertEqual(b.service.closes,1);self.assertFalse(list(root.iterdir()))
 async def test_cancel_during_compute_cleans_every_workspace(self):
  with tempfile.TemporaryDirectory() as p:
   root=Path(p);s=session();b=Backend(root,s,'cancel');task=asyncio.create_task(mining(s,b,root,Counts(),0,False));await b.started.wait();task.cancel()
   with self.assertRaises(asyncio.CancelledError):await task
   self.assertEqual(b.service.closes,1);self.assertFalse(list(root.iterdir()))
 async def test_persistent_process_is_reaped_on_request_cancel(self):
  script='import os,json,sys,time;print(json.dumps({"phase":"worker_ready","protocol":1,"pid":os.getpid()}),flush=True);sys.stdin.readline();time.sleep(30)'
  service=PersistentEngine([sys.executable,'-u','-c',script],timeout=10)
  await service.start();task=asyncio.create_task(service.compute(Path('/unused-in'),Path('/unused-out')));await asyncio.sleep(.05);task.cancel()
  with self.assertRaises(asyncio.CancelledError):await task
  self.assertIsNotNone(service.proc.returncode);self.assertTrue(service.describe()['process_reaped']);self.assertEqual(service.starts,1)
 async def test_bad_ack_fails_without_restart(self):
  script='import os,json,sys;print(json.dumps({"phase":"worker_ready","protocol":1,"pid":os.getpid()}),flush=True);sys.stdin.readline();print(json.dumps({"phase":"worker_done","seq":99,"requests_completed":99,"pid":os.getpid()}),flush=True)'
  service=PersistentEngine([sys.executable,'-u','-c',script])
  with self.assertRaisesRegex(RuntimeError,'acknowledgement'):await service.compute(Path('/unused-in'),Path('/unused-out'))
  self.assertIsNotNone(service.proc.returncode);self.assertEqual(service.starts,1)
if __name__=='__main__':unittest.main()
