"""One engine process/context for the whole run. One ordered GPU request at a time."""
import asyncio,contextlib,json,os,signal,time
from guard_checks import check_guard
async def terminate(proc):
 if proc and proc.returncode is None:
  with contextlib.suppress(ProcessLookupError):os.killpg(proc.pid,signal.SIGTERM)
  try:await asyncio.wait_for(proc.wait(),2)
  except asyncio.TimeoutError:
   with contextlib.suppress(ProcessLookupError):os.killpg(proc.pid,signal.SIGKILL)
   await proc.wait()
class PersistentEngine:
 def __init__(self,argv,guard=None,evidence=None,timeout=45,expected_protocol=1):
  self.expected_protocol=expected_protocol
  self.argv=list(map(str,argv));self.guard=guard;self.evidence=evidence;self.timeout=timeout;self.proc=None;self.seq=0;self.lock=asyncio.Lock();self.log=None;self.events=None;self.closed=False;self.generations=[];self.pid=None;self.starts=0;self.busy=False;self.shutdown_forced=False
 async def line(self,deadline):
  task=asyncio.create_task(self.proc.stdout.readline())
  try:
   while True:
    if time.monotonic()>deadline:raise TimeoutError('Persistent engine deadline')
    try:line=await asyncio.wait_for(asyncio.shield(task),.2);break
    except asyncio.TimeoutError:await check_guard(self.guard)
   if not line:raise RuntimeError('Persistent engine exited before acknowledgement')
   if self.events:self.events.write(line);self.events.flush()
   record=json.loads(line)
   if not isinstance(record,dict):raise RuntimeError('Invalid engine response')
   return record
  finally:
   if not task.done():task.cancel()
   await asyncio.gather(task,return_exceptions=True)
 async def start(self):
  if self.closed:raise RuntimeError('Closed engine cannot restart')
  if self.proc:return
  await check_guard(self.guard)
  if self.evidence:
   self.log=(self.evidence/'persistent-engine.stderr.log').open('xb')
   self.events=(self.evidence/'persistent-engine.events.jsonl').open('xb')
  self.proc=await asyncio.create_subprocess_exec(*self.argv,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=self.log or asyncio.subprocess.DEVNULL,start_new_session=True,limit=1024*1024)
  self.starts+=1;deadline=time.monotonic()+15
  try:
   for _ in range(8):
    record=await self.line(deadline)
    if record.get('phase')=='worker_ready':
     if record.get('protocol')!=self.expected_protocol or record.get('pid')!=self.proc.pid:raise RuntimeError('Engine protocol/identity mismatch')
     self.pid=self.proc.pid;self.ready_record=record;return
    if record.get('phase')!='device':raise RuntimeError('Unexpected engine startup response')
   raise RuntimeError('Engine startup did not finish')
  except BaseException:await self.close();raise
 async def compute(self,input_path,output_path):
  async with self.lock:
   await self.start();paths=[str(input_path.resolve()),str(output_path.resolve())]
   if any(any(ord(c)<32 or ord(c)==127 for c in p) for p in paths):raise ValueError('Control characters in engine path')
   await check_guard(self.guard,force=True)
   self.seq+=1;deadline=time.monotonic()+self.timeout;self.busy=True
   try:
    self.proc.stdin.write((str(self.seq)+'\t'+'\t'.join(paths)+'\n').encode());await self.proc.stdin.drain()
    for _ in range(8):
     r=await self.line(deadline)
     if r.get('phase')=='worker_done':
      if r.get('seq')!=self.seq or r.get('requests_completed')!=self.seq or r.get('pid')!=self.pid:raise RuntimeError('Engine acknowledgement differs')
      self.generations.append(r.get('resource_generation'));return r
     if r.get('phase')!='mining_batch':raise RuntimeError('Unexpected engine work response')
    raise RuntimeError('Missing engine completion')
   except BaseException:
    # Global cancellation/failure kills CUDA before the mapped RAM input may be freed.
    await self.close();raise
   finally:self.busy=False
 async def close(self):
  if self.closed and (self.proc is None or self.proc.returncode is not None):
   if self.log:self.log.close();self.log=None
   if self.events:self.events.close();self.events=None
   return
  self.closed=True
  if self.proc and self.proc.returncode is None and not self.busy:
   try:
    self.proc.stdin.write(b'QUIT\n');await asyncio.wait_for(self.proc.stdin.drain(),.5);await asyncio.wait_for(self.proc.wait(),2)
   except (OSError,ConnectionError,asyncio.TimeoutError):pass
  if self.proc and self.proc.returncode is None:self.shutdown_forced=True
  await terminate(self.proc)
  if self.log:self.log.close();self.log=None
  if self.events:self.events.close();self.events=None
 def describe(self):return {'process_starts':self.starts,'pid':self.pid,'completed_requests':len(self.generations),'resource_generations':self.generations,'automatic_restarts':False,'shutdown_forced':self.shutdown_forced,'exit_code':self.proc.returncode if self.proc else None,'process_reaped':self.proc is None or self.proc.returncode is not None}
