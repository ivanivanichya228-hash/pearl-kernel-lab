import asyncio,json,sys,threading,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from guard_checks import AsyncGuardChecks
from persistent_engine import PersistentEngine


class AsyncGuards(unittest.IsolatedAsyncioTestCase):
 async def test_slow_check_does_not_block_pool_event_loop(self):
  started=threading.Event();release=threading.Event()
  def check():started.set();release.wait(1)
  guard=AsyncGuardChecks(check);task=asyncio.create_task(guard.check_async())
  try:
   for _ in range(100):
    if started.is_set():break
    await asyncio.sleep(.001)
   self.assertTrue(started.is_set())
   # Pool events can run while nvidia-smi/check is still in flight.
   await asyncio.wait_for(asyncio.sleep(.01),.1)
   self.assertFalse(task.done())
  finally:release.set();await task

 async def test_checks_are_serial_and_never_cached(self):
  active=0;peak=0;calls=0
  def check():
   nonlocal active,peak,calls
   active+=1;peak=max(peak,active);calls+=1;time.sleep(.01);active-=1
  guard=AsyncGuardChecks(check)
  await asyncio.gather(*(guard.check_async() for _ in range(5)))
  self.assertEqual((calls,peak),(5,1));self.assertEqual(guard.describe()['calls'],5)

 async def test_cancellation_drains_inflight_check(self):
  started=threading.Event();release=threading.Event();finished=threading.Event()
  def check():started.set();release.wait(1);finished.set()
  guard=AsyncGuardChecks(check);task=asyncio.create_task(guard.check_async())
  for _ in range(100):
   if started.is_set():break
   await asyncio.sleep(.001)
  self.assertTrue(started.is_set());task.cancel();await asyncio.sleep(.01)
  self.assertFalse(task.done());task.cancel();release.set()
  with self.assertRaises(asyncio.CancelledError):await task
  self.assertTrue(finished.is_set());self.assertEqual(guard.cancelled_and_drained,1)

 async def test_failed_pre_request_check_sends_no_request_and_reaps(self):
  script='import os,json,sys,time;print(json.dumps(dict(phase="worker_ready",protocol=1,pid=os.getpid())),flush=True);sys.stdin.readline();time.sleep(30)'
  calls=0
  def check():
   nonlocal calls
   calls+=1
   if calls==2:raise RuntimeError('GPU identity changed')
  engine=PersistentEngine([sys.executable,'-u','-c',script],AsyncGuardChecks(check))
  try:
   await engine.start()
   with self.assertRaisesRegex(RuntimeError,'identity changed'):await engine.compute(Path('/input'),Path('/output'))
   self.assertEqual(engine.seq,0)
  finally:await engine.close()
  self.assertTrue(engine.describe()['process_reaped'])

 async def test_waiting_worker_still_checked_and_failure_kills_it(self):
  script='import os,json,sys,time;print(json.dumps(dict(phase="worker_ready",protocol=1,pid=os.getpid())),flush=True);sys.stdin.readline();time.sleep(30)'
  calls=0
  def check():
   nonlocal calls
   calls+=1
   if calls>=3:raise RuntimeError('Miner resumed')
  engine=PersistentEngine([sys.executable,'-u','-c',script],AsyncGuardChecks(check))
  with self.assertRaisesRegex(RuntimeError,'Miner resumed'):await engine.compute(Path('/input'),Path('/output'))
  self.assertTrue(engine.describe()['process_reaped']);self.assertEqual(engine.starts,1)

if __name__=='__main__':unittest.main()
