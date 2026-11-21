import asyncio,tempfile,unittest,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from miner_pipeline import mining
from pearl_miner import Counts
class FakeService:
 def __init__(self):self.tasks=[];self.lock=asyncio.Lock();self.closed=False
 async def start(self):pass
 async def close(self):
  async with self.lock:
   self.closed=True
   for t in self.tasks:
    if not t.done():t.cancel()
   await asyncio.gather(*self.tasks,return_exceptions=True)
class Backend:
 transfer_overlap=True
 def __init__(self,session):self.session=session;self.service=FakeService();self.second=asyncio.Event();self.prepares=0;self.finished=[];self.lifetimes=[];self.metrics=SimpleNamespace(classify=lambda *x:None)
 async def prepare(self,raw,root):self.prepares+=1;(root/'input').write_text('alive');return {'index':self.prepares,'root':root}
 async def enqueue(self,data):
  async def gpu():
   try:await asyncio.sleep(.04 if data['index']==2 else .01)
   finally:self.lifetimes.append((data['index'],(data['root']/'input').exists()))
  data['ticket']=asyncio.create_task(gpu());self.service.tasks.append(data['ticket'])
  if data['index']==2:self.second.set()
 async def finish(self,data,service):
  if data['index']==1:
   await self.second.wait();self.session.generation+=1;self.session.raw={'job':'new'};self.session.changed.set()
  await asyncio.shield(data['ticket']);self.finished.append(data['index']);return []
class OverlapLifetime(unittest.IsolatedAsyncioTestCase):
 async def test_prefetched_stale_packet_remains_alive_and_is_consumed(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);s=SimpleNamespace(raw={'job':'old'},generation=1,book=SimpleNamespace(current=object()),changed=asyncio.Event());b=Backend(s);counts=Counts();await asyncio.wait_for(mining(s,b,root,counts,1,False),2)
   self.assertIn(2,b.finished);self.assertGreaterEqual(counts.stale,2);self.assertEqual(counts.batches,1);self.assertTrue(all(live for _,live in b.lifetimes));self.assertFalse(list(root.iterdir()));self.assertTrue(b.service.closed)
 async def test_global_cancel_reaps_before_workspace_cleanup(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);s=SimpleNamespace(raw={'job':'old'},generation=1,book=SimpleNamespace(current=object()),changed=asyncio.Event());b=Backend(s);task=asyncio.create_task(mining(s,b,root,Counts(),0,False));await b.second.wait();task.cancel()
   with self.assertRaises(asyncio.CancelledError):await task
   self.assertTrue(all(t.done() for t in b.service.tasks));self.assertTrue(all(live for _,live in b.lifetimes));self.assertFalse(list(root.iterdir()))
