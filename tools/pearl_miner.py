#!/usr/bin/env python3
"""Experimental Pearl miner loop. Explicit live/submit switches; no GPU state setters."""
import argparse,asyncio,contextlib,hashlib,ipaddress,json,os,signal,socket,stat,subprocess,sys,tempfile,time
from dataclasses import dataclass,field
from decimal import Decimal
from pathlib import Path
from luckypool_adapter import Job,Profile,JobBook,submit_frame
from miner_metrics import Performance
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
 def __init__(self,reader,writer,wallet,worker,profile,counts,evidence=None):
  self.reader=reader;self.writer=writer;self.wallet=wallet;self.worker=worker;self.profile=profile;self.counts=counts;self.evidence=evidence
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
    # A quiet but connected pool is not a failed session. run() owns the total
    # deadline; authorization/submission keep their separate response deadlines.
    line=await self.reader.readline()
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
   self.pending.pop(mid,None);future.cancel();self.counts.unknown+=1;emit('share_unknown')
   if self.stop_on_reject:raise ProtocolError('Submission outcome unknown; experiment stopped')
   return
  if reply.get('_unknown'):
   emit('share_unknown')
   if self.stop_on_reject:raise ProtocolError('Submission outcome unknown; experiment stopped')
   return
  if reply.get('result') is True and reply.get('error') is None:
   self.counts.accepted+=1
   if self.evidence:
    dest=self.evidence/'accepted';dest.mkdir(mode=0o700,exist_ok=True)
    (dest/(digest+'.proof.bin')).write_bytes(proof)
    (dest/(digest+'.report.json')).write_text(json.dumps(report))
    (dest/(digest+'.receipt.json')).write_text(json.dumps({'request_id':mid,'result':True,'error':None,'job_fingerprint':job.fingerprint(),'proof_sha256':digest}))
   emit('share_accepted',proof_sha256=digest)
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
 env=os.environ.copy();env.setdefault('RAYON_NUM_THREADS','4');proc=None;output=None;outcome='running';started=time.monotonic()
 def record(event,**fields):
  if log_path:
   row={'event':event,'stage':log_path.stem,'batch':log_path.parent.name,'wall_time':time.time(),'monotonic':time.monotonic(),**fields}
   with (log_path.parent/'events.jsonl').open('a') as trace:trace.write(json.dumps(row)+'\n')
   emit(event,stage=log_path.stem,batch=log_path.parent.name,**fields)
 record('work_stage_start')
 try:
  if log_path:output=log_path.open('xb')
  proc=await asyncio.create_subprocess_exec(*map(str,argv),stdout=output or asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.STDOUT if output else asyncio.subprocess.DEVNULL,start_new_session=True,env=env)
  while proc.returncode is None:
   if guard:guard()
   if time.monotonic()-started>timeout:outcome='deadline';raise ChildFailure('Work stage exceeded deadline')
   try:await asyncio.wait_for(proc.wait(),.2)
   except asyncio.TimeoutError:pass
  if proc.returncode:outcome='child_failed';raise ChildFailure('Work stage failed; no share sent')
  outcome='completed'
 except BaseException as e:
  if outcome=='running':outcome='cancelled' if isinstance(e,asyncio.CancelledError) else type(e).__name__
  raise
 finally:
  if proc:await stop_child(proc)
  if output:output.close()
  record('work_stage_end',outcome=outcome,elapsed_seconds=time.monotonic()-started,returncode=proc.returncode if proc else None)

class Backend:
 def __init__(self,oracle,engine,profile_path,cpu=False,guard=None,timeout=45,evidence=None,persistent=False,engine_args=(),gpu_noise=False,transfer_overlap=False):
  self.oracle=oracle;self.engine=engine;self.profile_path=profile_path;self.cpu=cpu;self.guard=guard;self.timeout=timeout;self.evidence=evidence;self.profile=Profile.parse(json.loads(profile_path.read_text()));self.metrics=Performance(self.profile);self.service=None;self.gpu_noise=gpu_noise;self.transfer_overlap=transfer_overlap
  if persistent:
   from persistent_engine import PersistentEngine
   argv=[self.engine,'--queued-serve' if transfer_overlap else '--serve'] if cpu else [self.engine,'--run-gpu','--mode','overlap-worker' if transfer_overlap else 'worker','--allow-concurrent-miner',*map(str,engine_args)]
   if transfer_overlap:
    from queued_engine import QueuedEngine
    self.service=QueuedEngine(argv,guard,evidence,timeout,expected_protocol=2)
   else:self.service=PersistentEngine(argv,guard,evidence,timeout)
 async def stage(self,name,argv,evidence):
  start=time.monotonic();outcome='completed'
  try:await child(argv,self.timeout,self.guard,evidence/(name+'.log') if evidence else None)
  except BaseException as e:outcome='cancelled' if isinstance(e,asyncio.CancelledError) else 'failed';raise
  finally:self.metrics.stage(name,time.monotonic()-start,outcome)
 async def prepare(self,raw,root):
  evidence=self.evidence/root.name if self.evidence else None
  if evidence:
   evidence.mkdir(mode=0o700);(evidence/'context.json').write_text(json.dumps({'job_fingerprint':Job.parse(raw).fingerprint()}))
  jobfile=root/'notify.json';jobfile.write_text(json.dumps(raw));work=root/'work';hits=root/'hits.json';proofs=root/'proofs'
  await self.stage('prepare',[self.oracle,'work-prepare-raw' if self.gpu_noise else 'work-prepare',jobfile,self.profile_path,work],evidence)
  return {'raw':raw,'root':root,'work':work,'hits':hits,'proofs':proofs,'evidence':evidence}
 async def enqueue(self,prepared):
  if self.transfer_overlap:prepared['ticket']=await self.service.submit(prepared['work']/'work.bin',prepared['hits'])
 async def finish(self,prepared,service=None):
  raw,root,work,hits,proofs,evidence=(prepared[x] for x in ('raw','root','work','hits','proofs','evidence'))
  if service:
   start=time.monotonic();outcome='completed'
   ticket=prepared.get('ticket')
   try:
    if ticket:await service.wait(ticket)
    else:await service.compute(work/'work.bin',hits)
   except BaseException as e:outcome='cancelled' if isinstance(e,asyncio.CancelledError) else 'failed';raise
   finally:
    elapsed=((ticket.completed or time.monotonic())-ticket.submitted) if ticket else time.monotonic()-start;self.metrics.stage('GPU',elapsed,outcome)
    if evidence:
     with (evidence/'events.jsonl').open('a') as log:log.write(json.dumps({'event':'persistent_compute_end','outcome':outcome,'elapsed_seconds':elapsed,'wall_time':time.time()})+'\n')
  else:
   cmd=[self.engine,work/'work.bin',hits] if self.cpu else [self.engine,'--run-gpu','--mode','mine-batch','--work-input',work/'work.bin','--work-output',hits,'--allow-concurrent-miner']
   await self.stage('GPU',cmd,evidence)
  result=json.loads(hits.read_text())
  if self.gpu_noise and (result.get('raw_noise_input') is not True or result.get('noise_backend')!=('CPU-reference' if self.cpu else 'GPU')):raise ChildFailure('Requested GPU-noise mode did not execute')
  if not isinstance(result.get('hits'),list):raise ChildFailure('Missing hit list')
  metadata=json.loads((work/'work.json').read_text());expected=(self.profile.m//len(self.profile.rows))*(self.profile.n//len(self.profile.columns))
  if metadata.get('groups')!=expected or metadata.get('job_fingerprint')!=Job.parse(raw).fingerprint() or any(result.get(k)!=metadata.get(k) for k in ('batch_id','job_fingerprint')):raise ChildFailure('Measured work context differs')
  seen=set()
  for hit in result['hits']:
   i=hit.get('index');words=hit.get('transcript')
   if type(i) is not int or not 0<=i<expected or i in seen or not isinstance(words,list) or len(words)!=16 or any(type(x) is not int or not 0<=x<=0xffffffff for x in words):raise ChildFailure('Invalid measured hit')
   seen.add(i)
  if evidence:(evidence/'hits.json').write_text(json.dumps(result))
  self.metrics.gpu_complete(root.name,metadata['batch_id'],expected)
  if not result['hits']:return []
  await self.stage('proofs',[self.oracle,'work-finalize',work,hits,proofs],evidence)
  result=json.loads((proofs/'proofs.json').read_text());ready=[]
  if evidence:(evidence/'candidates').mkdir(mode=0o700)
  for i in result['indices']:
   proof=(proofs/f'hit-{i}.proof.bin').read_bytes();report=json.loads((proofs/f'hit-{i}-report.json').read_text())
   if evidence:
    (evidence/'candidates'/f'hit-{i}.proof.bin').write_bytes(proof)
    (evidence/'candidates'/f'hit-{i}-report.json').write_text(json.dumps(report))
   ready.append((proof,report))
  return ready
 async def batch(self,raw,root):return await self.finish(await self.prepare(raw,root))
 def status(self,counts):emit('status',**counts.public(),performance=self.metrics.snapshot(),engine=self.service.describe() if self.service else None)
async def mining(session,backend,workdir,counts,max_batches,enable_submit,stop_after_accepted=0):
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
     if hasattr(backend,'metrics'):backend.metrics.classify(Path(path).name,'stale')
     counts.stale+=1;task.cancel()
     with contextlib.suppress(asyncio.CancelledError):await task
     emit('stale_batch_cancelled');continue
    proofs=await task;counts.batches+=1
    if hasattr(backend,'metrics'):backend.metrics.classify(Path(path).name,'fresh')
    for proof,report in proofs:
     if generation!=session.generation:counts.stale+=1;break
     if enable_submit:
      await session.submit(job,proof,report)
      if stop_after_accepted and counts.accepted>=stop_after_accepted:return
     else:emit('qualified_share_not_sent')
    emit('status',**counts.public(),**({'performance':backend.metrics.snapshot()} if hasattr(backend,'metrics') else {}))
   finally:
    changed.cancel();task.cancel()
    with contextlib.suppress(asyncio.CancelledError):await changed
    with contextlib.suppress(asyncio.CancelledError):await task
async def run(host,port,credentials,profile,backend,workdir,*,duration=45,max_batches=0,enable_submit=False,reconnects=0,counts=None,stop_on_reject=False,stop_after_accepted=0,evidence=None,pipeline=False):
 counts=counts or Counts();end=time.monotonic()+duration
 for attempt in range(reconnects+1):
  tasks=[];writer=None
  try:
   reader,writer=await asyncio.wait_for(asyncio.open_connection(host,port,limit=MAX_LINE),8)
   session=Session(reader,writer,credentials['wallet'],credentials['worker'],profile,counts,evidence=evidence);session.stop_on_reject=stop_on_reject;reader_task=asyncio.create_task(session.read());tasks.append(reader_task)
   auth=asyncio.create_task(session.authorize());tasks.append(auth)
   done,_=await asyncio.wait([auth,reader_task],timeout=min(15,max(0,end-time.monotonic())),return_when=asyncio.FIRST_COMPLETED)
   if reader_task in done:await reader_task
   if auth not in done:raise TimeoutError('Authorization deadline')
   await auth
   selected_mining=mining
   if pipeline:
    from miner_pipeline import mining as selected_mining
   worker=asyncio.create_task(selected_mining(session,backend,workdir,counts,max_batches,enable_submit,stop_after_accepted));tasks.append(worker)
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
def validate_runtime(duration,extended,stop_after_accepted,stability=False):
 if not isinstance(duration,(int,float)) or not 1<=duration<=600:raise ValueError('Invalid duration')
 if stop_after_accepted not in (0,1):raise ValueError('Stop target must be0 or1')
 if stability and stop_after_accepted:raise ValueError('Stability window and first-share stop are mutually exclusive')
 if duration>50 and (not extended or not (stop_after_accepted==1 or stability)):raise ValueError('Longer test requires explicit first-share or stability mode')
 return duration
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
 if args.transfer_overlap and (not args.pipeline or not args.gpu_noise):raise ValueError('Transfer overlap requires raw-noise GPU pipeline')
 if args.transfer_overlap and not args.mock_cpu:
  available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
  if available<16*1024**3:raise ValueError('Pinned two-slot path needs at least16GiB available RAM')
 if args.matrix_loads and (args.kernel_threads!=384 or not args.pipeline or args.mock_cpu or args.transfer_overlap):raise ValueError('Matrix loads require384 persistent GPU without transfer overlap')
 if args.kernel_threads==384 and (not args.pipeline or args.mock_cpu):raise ValueError('kernel384 requires live persistent GPU pipeline')
 if args.gpu_noise and not args.pipeline:raise ValueError('GPU noise requires the persistent RAM pipeline')
 validate_runtime(args.duration,args.extended_test,args.stop_after_accepted,args.measure_stability)
 if not 0<=args.max_batches<=100:raise ValueError('Invalid max batches')
 if args.gpu:os.environ['CUDA_DEVICE_ORDER']='PCI_BUS_ID';os.environ['CUDA_VISIBLE_DEVICES']=args.gpu
 args.workdir.mkdir(parents=True,exist_ok=True,mode=0o700)
 if args.workdir.stat().st_mode&0o077:raise ValueError('Use an owner-only work directory')
 args.evidence.mkdir(parents=True,exist_ok=True,mode=0o700)
 if args.evidence.stat().st_mode&0o077:raise ValueError('Use owner-only evidence directory')
 ram=None
 if args.pipeline:
  from ram_workspace import RamWorkspace
  ram=RamWorkspace(profile,args.ram_dir,extra_resident_bytes=2*(profile.m+profile.n)*profile.k if args.transfer_overlap else 0)
  (args.evidence/'ram-workspace.json').write_text(json.dumps(ram.describe()))
 backend=Backend(args.oracle.resolve(),args.engine.resolve(),profile_path,args.mock_cpu,guard,evidence=args.evidence,persistent=args.pipeline,engine_args=['--paused-pid',args.paused_pid,'--paused-start-ticks',args.paused_start_ticks,'--candidate',args.kernel_threads,*(['--matrix-loads'] if args.matrix_loads else [])] if args.pipeline and not args.mock_cpu else [],gpu_noise=args.gpu_noise,transfer_overlap=args.transfer_overlap)
 counts=Counts();finished=False
 try:
  await run(host,port,config,profile,backend,ram.path if ram else args.workdir,duration=args.duration,max_batches=args.max_batches,enable_submit=args.enable_submit,reconnects=0,stop_on_reject=not args.mock_cpu,stop_after_accepted=args.stop_after_accepted,counts=counts,evidence=args.evidence,pipeline=args.pipeline);finished=True
 finally:
  if backend.service:await backend.service.close()
  if ram:ram.cleanup()
  performance=backend.metrics.snapshot();performance['compute_backend']='CPU-reference' if args.mock_cpu else 'GPU';performance['overlap_enabled']=args.pipeline;performance['GPU_noise_requested']=args.gpu_noise;performance['requested_kernel_threads']=args.kernel_threads;performance['matrix_loads_requested']=args.matrix_loads;performance['transfer_overlap_requested']=args.transfer_overlap;performance['GPU_stage_scope']='submission-to-native-done including queue' if args.transfer_overlap else 'consumer compute wait'
  if backend.service:performance['persistent_engine']=backend.service.describe()
  if ram:performance['RAM_workspace_cleaned']=not ram.path.exists()
  (args.evidence/'performance.json').write_text(json.dumps(performance,indent=2))
  emit('final',scope='mock' if args.mock_cpu else 'live-pool',outcome='finished' if finished else 'interrupted',**counts.public(),performance=performance)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--pipeline',action='store_true');p.add_argument('--gpu-noise',action='store_true');p.add_argument('--transfer-overlap',action='store_true');p.add_argument('--matrix-loads',action='store_true');p.add_argument('--kernel-threads',type=int,choices=[256,384],default=256);p.add_argument('--ram-dir',type=Path,default=Path('/dev/shm'));p.add_argument('--oracle',type=Path,default=ROOT/'build/pearl-protocol-oracle');p.add_argument('--engine',type=Path,default=ROOT/'build/pearl-bench');p.add_argument('--workdir',type=Path,default=ROOT/'build/private-work');p.add_argument('--evidence',type=Path,default=ROOT/'build/private-evidence');p.add_argument('--duration',type=float,default=40);p.add_argument('--max-batches',type=int,default=0);p.add_argument('--extended-test',action='store_true');p.add_argument('--measure-stability',action='store_true');p.add_argument('--stop-after-accepted',type=int,choices=[0,1],default=0);p.add_argument('--allow-live',action='store_true');p.add_argument('--enable-submit',action='store_true');p.add_argument('--mock-cpu',action='store_true');p.add_argument('--gpu');p.add_argument('--expected-power-limit-w',type=Decimal);p.add_argument('--paused-pid',type=int);p.add_argument('--paused-start-ticks',type=int);p.add_argument('--sanitizer',action='store_true');args=p.parse_args()
 try:asyncio.run(main_async(args))
 except KeyboardInterrupt:raise SystemExit(130)
 except Exception as e:emit('failed',category=type(e).__name__);raise SystemExit(1)
if __name__=='__main__':main()
