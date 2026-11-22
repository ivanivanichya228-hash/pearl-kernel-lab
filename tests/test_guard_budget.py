import ast,asyncio,subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from guard_checks import AsyncGuardChecks

class GuardBudget(unittest.IsolatedAsyncioTestCase):
 def fixture(self):
  state=dict(full=0,fast=0,bad_full=False,bad_fast=False)
  def full():
   state['full']+=1
   if state['bad_full']:raise RuntimeError('PL changed')
   fast()
  def fast():
   state['fast']+=1
   if state['bad_fast']:raise RuntimeError('Miner resumed')
  full.fast_check=fast
  return AsyncGuardChecks(full),state

 async def test_periodic_calls_reuse_but_every_gpu_gate_forces_full_check(self):
  g,s=self.fixture();await g.check_async()
  for _ in range(10):await g.check_async()
  self.assertEqual(s['full'],1);self.assertGreaterEqual(s['fast'],11)
  await g.check_async(force=True);await g.check_async(force=True)
  self.assertEqual(s['full'],3);self.assertEqual(g.forced_full_checks,2)

 async def test_expired_observation_is_never_reused(self):
  g,s=self.fixture();await g.check_async();g.last_full_start-=.501
  await g.check_async();self.assertEqual(s['full'],2)

 async def test_identity_failure_is_immediate_even_with_recent_good_full_check(self):
  g,s=self.fixture();await g.check_async();s['bad_fast']=True
  with self.assertRaisesRegex(RuntimeError,'Miner resumed'):await g.check_async()
  self.assertEqual(s['full'],1)
  s['bad_fast']=False
  with self.assertRaisesRegex(RuntimeError,'Miner resumed'):await g.check_async(force=True)
  self.assertEqual(s['full'],1)

 async def test_forced_full_gate_rejects_changed_pl_despite_recent_success(self):
  g,s=self.fixture();await g.check_async();s['bad_full']=True
  with self.assertRaisesRegex(RuntimeError,'PL changed'):await g.check_async(force=True)
  self.assertEqual(s['full'],2)
  s['bad_full']=False
  with self.assertRaisesRegex(RuntimeError,'PL changed'):await g.check_async()
  self.assertEqual(s['full'],2)

 async def test_simultaneous_periodic_callers_do_not_duplicate_probe(self):
  g,s=self.fixture();await asyncio.gather(*(g.check_async() for _ in range(8)))
  self.assertEqual(s['full'],1);self.assertEqual(g.periodic_reuses,7)

 async def test_exactly_one_identity_check_per_call(self):
  g,s=self.fixture()
  for _ in range(5):await g.check_async()
  await g.check_async(force=True);await g.check_async(force=True)
  self.assertEqual(s['fast'],7)
  self.assertEqual(g.calls+g.fast_calls,7)

 async def test_slow_periodic_identity_check_runs_outside_event_loop(self):
  import threading
  started=threading.Event();release=threading.Event();threads=[]
  def full():pass
  def fast():
   threads.append(threading.get_ident());started.set();release.wait(1)
  full.fast_check=fast
  guard=AsyncGuardChecks(full);await guard.check_async(force=True)
  timer=threading.Timer(1,release.set);timer.start()
  task=asyncio.create_task(guard.check_async())
  try:
   for _ in range(100):
    if started.is_set():break
    await asyncio.sleep(.001)
   self.assertTrue(started.is_set())
   await asyncio.sleep(.01)
   self.assertFalse(task.done(),'The event loop was blocked by the identity check')
  finally:release.set();timer.cancel();await task
  self.assertEqual(len(threads),1)
  self.assertNotEqual(threads[0],threading.get_ident())

 def test_original_full_validation_and_fast_identity_checks_are_preserved(self):
  root=Path(__file__).resolve().parents[1]
  old=ast.parse(subprocess.check_output(['git','show','HEAD:tools/pearl_miner.py'],cwd=root,text=True))
  new=ast.parse((root/'tools/pearl_miner.py').read_text())
  def inner(tree,name):
   outer=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
   return next(n for n in outer.body if isinstance(n,ast.FunctionDef))
  original=inner(old,'gpu_guard');current=inner(new,'gpu_guard');fast=inner(new,'identity_guard')
  dump=lambda nodes:ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False)
  self.assertEqual(dump(original.body),dump(current.body))
  self.assertEqual(dump(original.body[2:]),dump(fast.body))

if __name__=='__main__':unittest.main()
