#!/usr/bin/env python3
"""Experimental Pearl miner loop. Explicit live/submit switches; no GPU state setters."""
import argparse,asyncio,contextlib,hashlib,ipaddress,json,os,signal,socket,stat,subprocess,sys,tempfile,time
from dataclasses import dataclass,field
from decimal import Decimal
from pathlib import Path
from luckypool_adapter import Job,Profile,JobBook,submit_frame
ROOT=Path(__file__).resolve().parents[1]
MAX_LINE=8*1024*1024
class ProtocolError(Exception):pass
class StaleWork(Exception):pass
class ChildFailure(Exception):pass
@dataclass
class Counts:
 batches:int=0;sent:int=0;accepted:int=0;rejected:int=0;unknown:int=0;stale:int=0;reconnects:int=0
 def public(self):return dict(vars(self))
def emit(event,**fields):print(json.dumps({'event':event,**fields}),flush=True)
def read_credentials(path):
 st=path.lstat()
 if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or st.st_mode&0o077:raise ValueError('Credentials must be a regular owner-only file belonging to this user')
 data=json.loads(path.read_text())
 for k in ('wallet','worker'):
  v=data.get(k)
  if not isinstance(v,str) or not 1<=len(v)<=256 or any(ord(c)<32 for c in v):raise ValueError('Missing or invalid local credential')
 return data
class Session:
 def __init__(self,reader,writer,wallet,worker,profile,counts):
  self.reader=reader;self.writer=writer;self.wallet=wallet;self.worker=worker;self.profile=profile;self.counts=counts
  self.book=JobBook();self.raw=None;self.generation=0;self.changed=asyncio.Event();self.authorized=asyncio.get_running_loop().create_future();self.pending={};self.stop_on_reject=False;self.next_id=2;self.closed=False;self.sent_hashes=set()
  # Reader shutdown can precede the authorize waiter; keep its error observable without orphan warnings.
  self.authorized.add_done_callback(lambda f: None if f.cancelled() else f.exception())
 async def authorize(self):
  self.writer.write((json.dumps({'id':1,'method':'mining.authorize','params':{'wallet':self.wallet,'worker':self.worker}})+'\n').encode());await self.writer.drain()
  await asyncio.wait_for(asyncio.shield(self.authorized),15)
 def invalidate(self):self.generation+=1;self.book.current=None;self.raw=None;self.changed.set()
 async def read(self):
  try:
   while True:
    line=await asyncio.wait_for(self.reader.readline(),90)
    if not line:raise ConnectionError('Pool disconnected')
    if len(line)>MAX_LINE:raise ProtocolError('Pool line too large')
    try:msg=json.loads(line)
    except (ValueError,UnicodeError):raise ProtocolError('Malformed pool JSON') from None
    if not isinstance(msg,dict):raise ProtocolError('Pool message is not an object')
    if msg.get('id')==1:
     if msg.get('result') is not True or msg.get('error') is not None or msg.get('type')!='plain':raise ProtocolError('Authorization failed or non-plain protocol')
     if not self.authorized.done():self.authorized.set_result(True)
    elif msg.get('method')=='mining.notify':
     job=Job.parse(msg);self.profile.bound(job)
     if self.book.current is None or self.book.current.fingerprint()!=job.fingerprint():
      self.generation+=1;self.book.update(job);self.raw=msg;self.changed.set();emit('new_job',generation=self.generation)
    elif msg.get('method') in ('mining.set_difficulty','mining.set_target'):
     # Do not guess standalone target encoding or continue work under an old bound.
     self.invalidate();emit('waiting_for_explicit_notify_target')
    elif isinstance(msg.get('id'),int) and msg['id'] in self.pending:
     future=self.pending.pop(msg['id'])
     if not future.done():future.set_result(msg)
  finally:
   self.closed=True;self.invalidate()
   if not self.authorized.done():self.authorized.set_exception(ConnectionError('Authorization interrupted'))
   for f in self.pending.values():
    if not f.done():
     self.counts.unknown+=1;f.set_result({'_unknown':True})
   self.pending.clear()
 async def submit(self,job,proof,report):
  # No await between final freshness check, ID registration and write.
  self.book.require_current(job)
  if self.closed:raise ConnectionError('Session closed')
  digest=hashlib.sha256(proof).hexdigest()
  if digest in self.sent_hashes:raise ProtocolError('Duplicate proof suppressed')
  if len(self.sent_hashes)>=65536:raise ProtocolError('Session deduplication bound reached')
  frame=json.loads(submit_frame(job,self.profile,proof,report,self.wallet,self.worker,self.book))
  mid=self.next_id;self.next_id+=1;frame['id']=mid;future=asyncio.get_running_loop().create_future();self.pending[mid]=future;self.sent_hashes.add(digest)
  self.writer.write((json.dumps(frame,separators=(',',':'))+'\n').encode());self.counts.sent+=1
  try:
   await self.writer.drain();reply=await asyncio.wait_for(asyncio.shield(future),15)
  except (asyncio.TimeoutError,ConnectionError,OSError):
   self.pending.pop(mid,None);future.cancel();self.counts.unknown+=1;emit('share_unknown');return
  if reply.get('_unknown'):emit('share_unknown');return
  if reply.get('result') is True and reply.get('error') is None:self.counts.accepted+=1;emit('share_accepted')
  else:
   self.counts.rejected+=1;emit('share_rejected')
   if self.stop_on_reject:raise ProtocolError('Pool rejected first share; live experiment stopped')
async def stop_child(proc):
 if proc.returncode is None:
  with contextlib.suppress(ProcessLookupError):os.killpg(proc.pid,signal.SIGTERM)
  try:await asyncio.wait_for(proc.wait(),2)
  except asyncio.TimeoutError:
   with contextlib.suppress(ProcessLookupError):os.killpg(proc.pid,signal.SIGKILL)
   await proc.wait()
async def child(argv,timeout,guard=None,log_path=None):
 if guard:guard()
 env=os.environ.copy();env.setdefault('RAYON_NUM_THREADS','4');proc=None;output=None
 try:
  if log_path:output=log_path.open('wb')
  proc=await asyncio.create_subprocess_exec(*map(str,argv),stdout=output or asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.STDOUT if output else asyncio.subprocess.DEVNULL,start_new_session=True,env=env)
  start=time.monotonic()
  while proc.returncode is None:
   if guard:guard()
   if time.monotonic()-start>timeout:raise ChildFailure('Work stage exceeded deadline')
   try:await asyncio.wait_for(proc.wait(),.2)
   except asyncio.TimeoutError:pass
  if proc.returncode:raise ChildFailure('Work stage failed; no share sent')
 finally:
  if proc:await stop_child(proc)
  if output:output.close()

class Backend:
 def __init__(self,oracle,engine,profile_path,cpu=False,guard=None,timeout=45,evidence=None):
  self.oracle=oracle;self.engine=engine;self.profile_path=profile_path;self.cpu=cpu;self.guard=guard;self.timeout=timeout;self.evidence=evidence
 async def batch(self,raw,root):
  jobfile=root/'notify.json';jobfile.write_text(json.dumps(raw));work=root/'work';hits=root/'hits.json';proofs=root/'proofs'
  await child([self.oracle,'work-prepare',jobfile,self.profile_path,work],self.timeout,self.guard,self.evidence/'prepare.log' if self.evidence else None)
  cmd=[self.engine,work/'work.bin',hits] if self.cpu else [self.engine,'--run-gpu','--mode','mine-batch','--work-input',work/'work.bin','--work-output',hits,'--allow-concurrent-miner']
  await child(cmd,self.timeout,self.guard,self.evidence/'GPU.log' if self.evidence else None)
  result=json.loads(hits.read_text())
  if not isinstance(result.get('hits'),list):raise ChildFailure('Missing hit list')
  if not result['hits']:return []
  await child([self.oracle,'work-finalize',work,hits,proofs],self.timeout,self.guard,self.evidence/'proofs.log' if self.evidence else None)
  result=json.loads((proofs/'proofs.json').read_text());return [((proofs/f'hit-{i}.proof.bin').read_bytes(),json.loads((proofs/f'hit-{i}-report.json').read_text())) for i in result['indices']]
async def mining(session,backend,workdir,counts,max_batches,enable_submit):
 while not max_batches or counts.batches<max_batches:
  while session.raw is None:
   session.changed.clear()
   if session.raw is not None:break
   await session.changed.wait()
  job=session.book.current;raw=session.raw;generation=session.generation;session.changed.clear()
  with tempfile.TemporaryDirectory(prefix='batch-',dir=workdir) as path:
   task=asyncio.create_task(backend.batch(raw,Path(path)));changed=asyncio.create_task(session.changed.wait())
   try:
    done,_=await asyncio.wait([task,changed],return_when=asyncio.FIRST_COMPLETED)
    if generation!=session.generation:
     counts.stale+=1;task.cancel()
     with contextlib.suppress(asyncio.CancelledError):await task
     emit('stale_batch_cancelled');continue
    proofs=await task;counts.batches+=1
    for proof,report in proofs:
     if generation!=session.generation:counts.stale+=1;break
     if enable_submit:await session.submit(job,proof,report)
     else:emit('qualified_share_not_sent')
    emit('status',**counts.public())
   finally:
    changed.cancel();task.cancel()
    with contextlib.suppress(asyncio.CancelledError):await changed
    with contextlib.suppress(asyncio.CancelledError):await task
async def run(host,port,credentials,profile,backend,workdir,*,duration=45,max_batches=0,enable_submit=False,reconnects=0,counts=None,stop_on_reject=False):
 counts=counts or Counts();end=time.monotonic()+duration
 for attempt in range(reconnects+1):
  tasks=[];writer=None
  try:
   reader,writer=await asyncio.wait_for(asyncio.open_connection(host,port,limit=MAX_LINE),8)
   session=Session(reader,writer,credentials['wallet'],credentials['worker'],profile,counts);session.stop_on_reject=stop_on_reject;reader_task=asyncio.create_task(session.read());tasks.append(reader_task)
   auth=asyncio.create_task(session.authorize());tasks.append(auth)
   done,_=await asyncio.wait([auth,reader_task],timeout=min(15,max(0,end-time.monotonic())),return_when=asyncio.FIRST_COMPLETED)
   if reader_task in done:await reader_task
   if auth not in done:raise TimeoutError('Authorization deadline')
   await auth
   worker=asyncio.create_task(mining(session,backend,workdir,counts,max_batches,enable_submit));tasks.append(worker)
   done,_=await asyncio.wait([reader_task,worker],timeout=max(0,end-time.monotonic()),return_when=asyncio.FIRST_COMPLETED)
   if worker in done:await worker;return counts
   if reader_task in done:await reader_task
   return counts
  except (ConnectionError,OSError,asyncio.TimeoutError):
   if attempt>=reconnects or time.monotonic()>=end:raise
   counts.reconnects+=1
  finally:
   for task in tasks:task.cancel()
   if tasks:await asyncio.gather(*tasks,return_exceptions=True)
   if writer:
    writer.close()
    try:await asyncio.wait_for(writer.wait_closed(),3)
    except (OSError,asyncio.TimeoutError):writer.transport.abort()
  await asyncio.sleep(min(2**attempt,max(0,end-time.monotonic())))
 return counts

def gpu_guard(uuid,expected,pid,ticks):
 def check():
  row=subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-gpu=uuid,name,power.limit','--format=csv,noheader,nounits'],text=True,timeout=3).strip().split(',')
  if len(row)!=3 or row[0].strip()!=uuid or 'RTX 4090' not in row[1] or Decimal(row[2].strip())!=expected:raise ChildFailure('GPU identity or power limit changed')
  if not pid or not ticks:raise ChildFailure('Independent stopped-miner identity required')
  proc=Path('/proc')/str(pid);s=(proc/'stat').read_text().rsplit(')',1)[1].split()
  if int(s[19])!=ticks or s[0]!='T':raise ChildFailure('Original process is not the expected stopped miner')
  for t in (proc/'task').iterdir():
   if (t/'stat').read_text().rsplit(')',1)[1].split()[0]!='T':raise ChildFailure('A miner thread is running')
  for item in Path('/proc').iterdir():
   if not item.name.isdecimal() or item.name==str(pid):continue
   try:
    if 'srbminer' in (item/'comm').read_text().lower():raise ChildFailure('Another SRBMiner process exists')
   except (FileNotFoundError,ProcessLookupError):pass
 return check
async def main_async(args):
 config=read_credentials(args.config);profile_path=Path(config['profile']).resolve();profile=Profile.parse(json.loads(profile_path.read_text()));host=config['host'];port=config['port']
 if type(port) is not int or not 1<=port<=65535:raise ValueError('Invalid port')
 if args.mock_cpu:
  if host not in ('127.0.0.1','::1'):raise ValueError('CPU integration backend restricted to literal loopback')
 else:
  if not args.allow_live or not args.expected_power_limit_w or not args.gpu or not args.paused_pid or not args.paused_start_ticks:raise ValueError('Live execution needs explicit flags and independent pause identity')
  if args.sanitizer:
   raise ValueError('Use the bounded mine-batch check under external sanitizer/controller, not a persistent sanitizer wrapper')
 guard=None if args.mock_cpu else gpu_guard(args.gpu,args.expected_power_limit_w,args.paused_pid,args.paused_start_ticks)
 if guard:guard()
 if not 1<=args.duration<=50 or not 0<=args.max_batches<=100:raise ValueError('Alpha runtime budget is1..50s, max batches0..100')
 if args.gpu:os.environ['CUDA_DEVICE_ORDER']='PCI_BUS_ID';os.environ['CUDA_VISIBLE_DEVICES']=args.gpu
 args.workdir.mkdir(parents=True,exist_ok=True,mode=0o700)
 if args.workdir.stat().st_mode&0o077:raise ValueError('Use an owner-only work directory')
 args.evidence.mkdir(parents=True,exist_ok=True,mode=0o700)
 if args.evidence.stat().st_mode&0o077:raise ValueError('Use owner-only evidence directory')
 backend=Backend(args.oracle.resolve(),args.engine.resolve(),profile_path,args.mock_cpu,guard,evidence=args.evidence)
 counts=await run(host,port,config,profile,backend,args.workdir,duration=args.duration,max_batches=args.max_batches,enable_submit=args.enable_submit,reconnects=0,stop_on_reject=not args.mock_cpu)
 emit('final',scope='mock' if args.mock_cpu else 'live-pool',**counts.public())
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--oracle',type=Path,default=ROOT/'build/pearl-protocol-oracle');p.add_argument('--engine',type=Path,default=ROOT/'build/pearl-bench');p.add_argument('--workdir',type=Path,default=ROOT/'build/private-work');p.add_argument('--evidence',type=Path,default=ROOT/'build/private-evidence');p.add_argument('--duration',type=float,default=40);p.add_argument('--max-batches',type=int,default=0);p.add_argument('--allow-live',action='store_true');p.add_argument('--enable-submit',action='store_true');p.add_argument('--mock-cpu',action='store_true');p.add_argument('--gpu');p.add_argument('--expected-power-limit-w',type=Decimal);p.add_argument('--paused-pid',type=int);p.add_argument('--paused-start-ticks',type=int);p.add_argument('--sanitizer',action='store_true');args=p.parse_args()
 try:asyncio.run(main_async(args))
 except KeyboardInterrupt:raise SystemExit(130)
 except Exception as e:emit('failed',category=type(e).__name__);raise SystemExit(1)
if __name__=='__main__':main()
