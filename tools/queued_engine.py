"""At most two submitted packets, one stdout owner, process reaped before workspace cleanup."""
import asyncio,contextlib,time
from dataclasses import dataclass
from persistent_engine import PersistentEngine,terminate
from guard_checks import check_guard
@dataclass
class Ticket:
 seq:int;future:object;submitted:float;completed:float|None=None;consumed:bool=False
class QueuedEngine(PersistentEngine):
 def __init__(self,*args,expected_protocol=2,**kwargs):
  super().__init__(*args,expected_protocol=expected_protocol,**kwargs);self.close_lock=asyncio.Lock();self.start_lock=asyncio.Lock();self.write_lock=asyncio.Lock();self.pending={};self.tickets=[];self.reader=None;self.watcher=None;self.max_pending=0
 async def start(self):
  async with self.start_lock:
   if self.closed:raise RuntimeError('Closed queued engine cannot restart')
   if self.reader:return
   await super().start()
   if self.expected_protocol==2 and self.ready_record.get('transfer_slots')!=2:
    await self.close();raise RuntimeError('Worker did not advertise exactly two transfer slots')
   self.reader=asyncio.create_task(self.pump());self.watcher=asyncio.create_task(self.watch())
 async def fail(self,error):
  self.closed=True
  for t in list(self.pending.values()):
   if not t.future.done():t.future.set_exception(error)
  self.pending.clear();await terminate(self.proc)
 async def pump(self):
  try:
   while True:
    r=await self.line(float('inf'))
    if r.get('phase') in ('mining_batch','transfer_stage','transfer_queued'):continue
    if r.get('phase')!='worker_done':raise RuntimeError('Unexpected queued engine response')
    seq=r.get('seq');t=self.pending.get(seq)
    if t is None or seq!=len(self.generations)+1 or r.get('requests_completed')!=seq or r.get('pid')!=self.pid:raise RuntimeError('Queued acknowledgement mismatch')
    del self.pending[seq];self.generations.append(r.get('resource_generation'));t.completed=time.monotonic()
    if not t.future.done():t.future.set_result(r)
  except asyncio.CancelledError:raise
  except BaseException as e:await self.fail(e)
 async def watch(self):
  try:
   while True:
    await asyncio.sleep(.1)
    if any(time.monotonic()-t.submitted>self.timeout for t in self.pending.values()):raise TimeoutError('Queued request deadline')
  except asyncio.CancelledError:raise
  except BaseException as e:await self.fail(e)
 async def submit(self,input_path,output_path):
  await self.start()
  async with self.write_lock:
   if self.closed or self.proc.returncode is not None:raise RuntimeError('Queued worker unavailable')
   if len(self.pending)>=2:raise RuntimeError('Two-packet submission bound exceeded')
   paths=[str(input_path.resolve()),str(output_path.resolve())]
   if any(any(ord(c)<32 or ord(c)==127 for c in p) for p in paths):raise ValueError('Control characters in queued path')
   await check_guard(self.guard)
   self.seq+=1;future=asyncio.get_running_loop().create_future()
   # Retrieve on abandoned-ticket shutdown too; awaiting still receives the original error.
   future.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
   ticket=Ticket(self.seq,future,time.monotonic());self.pending[self.seq]=ticket;self.tickets.append(ticket);self.max_pending=max(self.max_pending,len(self.pending))
   try:self.proc.stdin.write((str(self.seq)+'\t'+'\t'.join(paths)+'\n').encode());await self.proc.stdin.drain()
   except BaseException:await self.close();raise
   return ticket
 async def wait(self,ticket):
  result=await asyncio.shield(ticket.future);ticket.consumed=True;return result
 async def compute(self,input_path,output_path):return await self.wait(await self.submit(input_path,output_path))
 async def close(self):
  async with self.close_lock:await self.close_locked()
 async def close_locked(self):
  self.busy=bool(self.pending)
  for task in (self.reader,self.watcher):
   if task:task.cancel()
  await asyncio.gather(*(t for t in (self.reader,self.watcher) if t),return_exceptions=True)
  for t in list(self.pending.values()):
   if not t.future.done():t.future.cancel()
  self.pending.clear();await super().close()
 def describe(self):
  result=super().describe();result.update({'protocol':self.expected_protocol,'submission_bound':2,'maximum_pending':self.max_pending,'submitted_requests':len(self.tickets),'completed_unconsumed_sequences':[t.seq for t in self.tickets if t.completed is not None and not t.consumed]});return result
