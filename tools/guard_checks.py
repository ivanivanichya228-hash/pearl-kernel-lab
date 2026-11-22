"""Run the unchanged blocking GPU/identity check without blocking pool/CPU scheduling.

One full check at a time. Periodic callers share a bounded0.5s observation,
while every GPU submission forces a new full check. Cancellation drains the check
before releasing the caller, so no check thread outlives experimental cleanup.
"""
import asyncio
import contextlib
import time


class AsyncGuardChecks:
 def __init__(self,check):
  self.check=check;self.lock=asyncio.Lock();self.calls=0;self.failed=0
  self.seconds=0.;self.queue_seconds=0.;self.cancelled_and_drained=0
  self.fast=getattr(check,"fast_check",None);self.last_full_start=None;self.error=None
  self.fast_calls=0;self.fast_seconds=0.;self.periodic_reuses=0;self.forced_full_checks=0

 def __call__(self):
  if self.error is not None:raise self.error
  start=time.monotonic();self.calls+=1
  try:
   result=self.check();self.last_full_start=start;return result
  except BaseException as error:
   self.failed+=1;self.error=error;raise
  finally:self.seconds+=time.monotonic()-start

 def fast_check(self):
  if self.error is not None:raise self.error
  if self.fast is None:return
  start=time.monotonic();self.fast_calls+=1
  try:self.fast()
  except BaseException as error:
   self.failed+=1;self.error=error;raise
  finally:self.fast_seconds+=time.monotonic()-start

 def scheduled_check(self,force):
  # This entire decision and its filesystem/subprocess work run in the worker.
  if self.error is not None:raise self.error
  if self.fast is not None and not force and self.last_full_start is not None and time.monotonic()-self.last_full_start<.5:
   self.periodic_reuses+=1
   return self.fast_check()
  if force:self.forced_full_checks+=1
  # Full validation already includes identity validation; never duplicate it.
  return self()

 async def check_async(self,force=False):
  start=time.monotonic()
  async with self.lock:
   self.queue_seconds+=time.monotonic()-start
   task=asyncio.create_task(asyncio.to_thread(self.scheduled_check,force))
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
              cached_results=self.fast is not None,maximum_parallel_checks=1,nonblocking_checks=True,
              full_observation_period_seconds=.5 if self.fast is not None else 0,
              fresh_full_check_before_GPU_request=True,forced_full_checks=self.forced_full_checks,
              fast_calls=self.fast_calls,fast_seconds=self.fast_seconds,periodic_reuses=self.periodic_reuses,
              fast_checks_nonblocking=True,duplicated_identity_checks=False)


async def check_guard(guard,force=False):
 if guard is None:return
 if hasattr(guard,'check_async'):return await guard.check_async(force=force)
 return guard()
