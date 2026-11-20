"""Two-slot producer/consumer. Only CPU preparation is cancelled on new pool jobs."""
import asyncio,contextlib,tempfile
from dataclasses import dataclass
from pathlib import Path
@dataclass
class Prepared:
 temporary:object;raw:dict;generation:int;job:object;data:object
 @property
 def root(self):return Path(self.temporary.name)
async def mining(session,backend,workdir,counts,max_batches,enable_submit,stop_after_accepted=0):
 queue=asyncio.Queue(maxsize=1);slots=asyncio.Semaphore(2)
 async def release(work):work.temporary.cleanup();slots.release()
 async def producer():
  while True:
   while session.raw is None:
    session.changed.clear()
    if session.raw is not None:break
    await session.changed.wait()
   await slots.acquire();temporary=None;transferred=False;prep=None;changed=None
   try:
    if session.raw is None:continue
    raw=session.raw;generation=session.generation;job=session.book.current;session.changed.clear()
    temporary=tempfile.TemporaryDirectory(prefix='batch-',dir=workdir)
    prep=asyncio.create_task(backend.prepare(raw,Path(temporary.name)));changed=asyncio.create_task(session.changed.wait())
    await asyncio.wait([prep,changed],return_when=asyncio.FIRST_COMPLETED)
    if generation!=session.generation:
     counts.stale+=1;prep.cancel();await asyncio.gather(prep,return_exceptions=True);continue
    data=await prep
    if generation!=session.generation:counts.stale+=1;continue
    work=Prepared(temporary,raw,generation,job,data);await queue.put(work);transferred=True
   finally:
    if changed:changed.cancel();await asyncio.gather(changed,return_exceptions=True)
    if prep and not prep.done():prep.cancel();await asyncio.gather(prep,return_exceptions=True)
    if not transferred:
     if temporary:temporary.cleanup()
     slots.release()
 producer_task=asyncio.create_task(producer());current=None;get_task=None
 try:
  await backend.service.start()
  while not max_batches or counts.batches<max_batches:
   get_task=asyncio.create_task(queue.get())
   done,_=await asyncio.wait([get_task,producer_task],return_when=asyncio.FIRST_COMPLETED)
   if producer_task in done:await producer_task;raise RuntimeError('Preparation producer ended unexpectedly')
   current=await get_task;get_task=None
   if current.generation!=session.generation:counts.stale+=1;await release(current);current=None;continue
   # A job update does not tear down the persistent context: finish this request,
   # discard stale output, and keep the next CPU preparation running independently.
   proofs=await backend.finish(current.data,backend.service)
   if current.generation!=session.generation:
    backend.metrics.classify(current.root.name,'stale');counts.stale+=1
   else:
    backend.metrics.classify(current.root.name,'fresh');counts.batches+=1
    for proof,report in proofs:
     if current.generation!=session.generation:counts.stale+=1;break
     if enable_submit:
      await session.submit(current.job,proof,report)
      if stop_after_accepted and counts.accepted>=stop_after_accepted:return
   if hasattr(backend,'status'):backend.status(counts)
   await release(current);current=None
 finally:
  producer_task.cancel()
  if get_task:
   get_task.cancel();await asyncio.gather(get_task,return_exceptions=True)
   if get_task.done() and not get_task.cancelled() and get_task.exception() is None:
    extra=get_task.result()
    if extra is not current:await release(extra)
  await backend.service.close()
  await asyncio.gather(producer_task,return_exceptions=True)
  if current:await release(current)
  while not queue.empty():await release(queue.get_nowait())
