import asyncio,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from queued_engine import QueuedEngine
READY='import os,json,sys,time;print(json.dumps({"phase":"worker_ready","protocol":2,"transfer_slots":2,"pid":os.getpid()}),flush=True);'
class QueuedTests(unittest.IsolatedAsyncioTestCase):
 async def test_two_inflight_and_hard_bound(self):
  script=READY+'a=sys.stdin.readline();b=sys.stdin.readline();time.sleep(.02);'+''.join('print(json.dumps({"phase":"worker_done","seq":'+str(i)+',"requests_completed":'+str(i)+',"resource_generation":1,"pid":os.getpid()}),flush=True);' for i in (1,2))+'sys.stdin.readline()'
  engine=QueuedEngine([sys.executable,'-u','-c',script]);a=await engine.submit(Path('/a'),Path('/b'));b=await engine.submit(Path('/c'),Path('/d'))
  with self.assertRaisesRegex(RuntimeError,'bound'):await engine.submit(Path('/e'),Path('/f'))
  await asyncio.wait_for(asyncio.gather(engine.wait(a),engine.wait(b)),2);await engine.close();self.assertEqual(engine.max_pending,2);self.assertEqual(engine.generations,[1,1]);self.assertTrue(engine.describe()['process_reaped']);self.assertFalse(engine.describe()['completed_unconsumed_sequences'])
 async def test_unawaited_prefetch_deadline(self):
  engine=QueuedEngine([sys.executable,'-u','-c',READY+'sys.stdin.readline();time.sleep(30)'],timeout=.05);t=await engine.submit(Path('/a'),Path('/b'));await asyncio.sleep(.25)
  with self.assertRaises(TimeoutError):await engine.wait(t)
  await engine.close();self.assertIsNotNone(engine.proc.returncode)
 async def test_cancel_wait_then_reap(self):
  engine=QueuedEngine([sys.executable,'-u','-c',READY+'sys.stdin.readline();time.sleep(30)']);t=await engine.submit(Path('/a'),Path('/b'));task=asyncio.create_task(engine.wait(t));await asyncio.sleep(.01);task.cancel()
  with self.assertRaises(asyncio.CancelledError):await task
  self.assertFalse(t.future.done());await engine.close();self.assertTrue(t.future.cancelled());self.assertIsNotNone(engine.proc.returncode)
 async def test_bad_ack_fails_without_restart(self):
  script=READY+'sys.stdin.readline();print(json.dumps({"phase":"worker_done","seq":2,"requests_completed":2,"resource_generation":1,"pid":os.getpid()}),flush=True);time.sleep(30)'
  engine=QueuedEngine([sys.executable,'-u','-c',script]);t=await engine.submit(Path('/a'),Path('/b'))
  with self.assertRaisesRegex(RuntimeError,'acknowledgement'):await engine.wait(t)
  await engine.close();self.assertEqual(engine.starts,1)
