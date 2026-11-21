"""Run the unchanged blocking GPU/identity check without blocking pool/CPU scheduling.

One check at a time. No cached results. Cancellation drains the bounded check
before releasing the caller, so no check thread outlives experimental cleanup.
"""
import asyncio
import contextlib
import time


class AsyncGuardChecks:
 def __init__(self,check):
  self.check=check;self.lock=asyncio.Lock();self.calls=0;self.failed=0
  self.seconds=0.;self.queue_seconds=0.;self.cancelled_and_drained=0

 def __call__(self):
  start=time.monotonic();self.calls+=1
  try:return self.check()
  except BaseException:
   self.failed+=1;raise
  finally:self.seconds+=time.monotonic()-start

 async def check_async(self):
  start=time.monotonic()
  async with self.lock:
   self.queue_seconds+=time.monotonic()-start
   task=asyncio.create_task(asyncio.to_thread(self))
   try:return await asyncio.shield(task)
   except asyncio.CancelledError:
    # The original nvidia-smi invocation already has a3s subprocess timeout.
    # Do not abandon it when the mining session is cancelled.
    while not task.done():
     try:await asyncio.shield(task)
     except asyncio.CancelledError:continue
     except Exception:break
    with contextlib.suppress(Exception):task.result()
    self.cancelled_and_drained+=1
    raise

 def describe(self):
  return dict(calls=self.calls,failed=self.failed,execution_seconds=self.seconds,
              queue_seconds=self.queue_seconds,cancelled_and_drained=self.cancelled_and_drained,
              cached_results=False,maximum_parallel_checks=1,nonblocking_checks=True)


async def check_guard(guard):
 if guard is None:return
 if hasattr(guard,'check_async'):return await guard.check_async()
 return guard()
