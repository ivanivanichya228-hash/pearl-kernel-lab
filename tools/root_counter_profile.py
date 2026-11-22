"""Fixed root-only profiler entry; trusted frozen tree, no general command interface."""
import argparse,asyncio,errno,hashlib,json,os,platform,stat,struct,subprocess,sys
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
GPU='GPU-14cc341d-41f4-a977-1a1d-12785f4079da'
NCU=Path('/usr/lib/nsight-compute/ncu')
NCU_SHA='f2a737629d325c771b9564113088fc144ad182cf9ebc8847dc0b6d565dcb6274'
ENGINE_SHA='3e935b1171b3e925db9aeadd901564eaa3d4500bcb19a29dd2aa50df40e5f7c1'
SYS_ADMIN=1<<21
OUTPUT_ROOT=Path('/var/lib/pearl-root-counter-profile')
# Filled from this pinned repository; these are the ONLY project modules imported.
DEPENDENCIES = {'tools/guard_checks.py': '56cf38e871a783a465e181dbb4372744b4cb3130f2f79e913094254a72478522', 'tools/diagnose_compute.py': 'caa532c0b553a962212aef7b867963d7d64e6a3cadd5cc373b26044d6310d29b', 'tools/counter_access.py': '4fb92af46ccb091ed57cb6e2d4f96336cf73dc5c24544fc97449b3ab6f3a5c07', 'tools/pearl_miner.py': '05999c60987ecce8d6279fcafa66f12447a0bcefbe077897f771554b9d76438d', 'tools/luckypool_adapter.py': 'd92ddea02c3215d15df96e6b805e5d9ae4d66af9fca45d96ad41a5a49b7b7764', 'tools/miner_metrics.py': '1429cd65c342fb901aa09f8cbcb24e428d7041120b1d7b7a5a5c18e69d44b254'}

def root_scope(status,auxv,uid,gid):
 fields=dict(line.split(':',1) for line in status.splitlines() if ':' in line)
 caps={k:int(fields.get(k,'0').strip(),16) for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')}
 secure=None;terminated=False
 if len(auxv)%16:raise ValueError('Malformed Linux x86_64 auxv')
 for key,value in struct.iter_unpack('=QQ',auxv):
  if key==0:terminated=True;break
  if key==23:secure=value
 valid=(uid==0 and gid==0 and fields.get('NoNewPrivs','').strip()=='1'
        and terminated and secure==0 and all(v==SYS_ADMIN for v in caps.values()))
 return {'valid':valid,'uid':uid,'gid':gid,'AT_SECURE':secure,'NoNewPrivs':fields.get('NoNewPrivs','').strip(),
         'capabilities':{k:f'{v:016x}' for k,v in caps.items()},'GPU_executed':False}

def current_scope():
 return root_scope(Path('/proc/self/status').read_text(),Path('/proc/self/auxv').read_bytes(),os.geteuid(),os.getegid())

def trusted_path(path,executable=False):
 if not path.is_absolute():raise ValueError('Absolute trusted path required')
 real=path.resolve(strict=True)
 # Check both lexical and resolved paths: a writable symlink parent is not trusted.
 for item in dict.fromkeys((path,*path.parents,real,*real.parents)):
  info=item.lstat()
  if info.st_uid!=0 or (not stat.S_ISLNK(info.st_mode) and info.st_mode&0o022):raise ValueError('Untrusted owner/write permissions: '+str(item))
 info=real.stat()
 if not stat.S_ISREG(info.st_mode) or info.st_mode&0o6000:raise ValueError('Ordinary non-setuid file required')
 if executable and not os.access(real,os.X_OK):raise ValueError('Trusted file not executable')
 try:cap=os.getxattr(real,'security.capability')
 except OSError as e:
  if e.errno not in (errno.ENODATA,errno.ENOTSUP):raise
  cap=b''
 if cap:raise ValueError('Persistent file capabilities are prohibited')
 return real

def verify_tree():
 if not sys.flags.isolated or platform.machine()!='x86_64':raise ValueError('Use isolated Python -I on Linux x86_64')
 scope=current_scope()
 if not scope['valid']:raise ValueError('Require root/GID0 with only transient SYS_ADMIN and NoNewPrivs1/AT_SECURE0')
 for name in ('LD_PRELOAD','LD_AUDIT','LD_LIBRARY_PATH','PYTHONPATH','PYTHONHOME','PYTHONSTARTUP','PYTHONINSPECT'):
  if os.environ.get(name):raise ValueError('Injected environment is prohibited: '+name)
 if os.environ.get('PATH')!='/usr/sbin:/usr/bin:/sbin:/bin':raise ValueError('Use the fixed trusted system PATH')
 trusted_path(Path('/usr/bin/nvidia-smi'),True)
 trusted_path(Path(__file__));trusted_path(Path(sys.executable),True)
 for name,digest in DEPENDENCIES.items():
  file=trusted_path(ROOT/name)
  if hashlib.sha256(file.read_bytes()).hexdigest()!=digest:raise ValueError('Trusted module checksum mismatch: '+name)
 ncu=trusted_path(NCU,True);engine=trusted_path(ROOT/'build/pearl-bench',True)
 for file,digest in ((ncu,NCU_SHA),(engine,ENGINE_SHA)):
  if hashlib.sha256(file.read_bytes()).hexdigest()!=digest:raise ValueError('Pinned executable checksum mismatch: '+str(file))
 return scope,ncu,engine

def new_output(path):
 if not path.is_absolute() or path.parent!=OUTPUT_ROOT or path.name in ('','.','..'):raise ValueError('Use a new direct child of '+str(OUTPUT_ROOT))
 # Parent must already have been created by the trusted preparation step.
 for item in (OUTPUT_ROOT,*OUTPUT_ROOT.parents):
  info=item.lstat()
  if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:raise ValueError('Untrusted output parent')
 if path.exists() or path.is_symlink():raise ValueError('Output must be NEW')
 path.mkdir(mode=0o700)
 return path

def parser():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['preflight','collect']);p.add_argument('--out',type=Path,required=True);p.add_argument('--paused-pid',type=int);p.add_argument('--paused-start-ticks',type=int);return p

async def main(args):
 scope,ncu,engine=verify_tree();out=new_output(args.out)
 facts={'root_scope':scope,'ncu':str(ncu),'ncu_sha256':NCU_SHA,'engine':str(engine),'engine_sha256':ENGINE_SHA,
        'GPU':GPU,'PL_W':310,'system_permissions_changed':False,'GPU_profile_success':False}
 (out/'prelaunch.json').write_text(json.dumps(facts,indent=2)+'\n')
 if args.action=='preflight':
  # Fixed --version/--help only; no CUDA kernels or miner stop/resume.
  version=subprocess.run([str(ncu),'--version'],capture_output=True,text=True,check=True,timeout=5)
  help_result=subprocess.run([str(engine),'--help'],capture_output=True,text=True,check=True,timeout=5)
  if 'kernel-counters' not in help_result.stdout:raise ValueError('Wrong engine')
  facts.update(passed=True,GPU_executed=False,ncu_version=version.stdout.strip(),GPU_driver_tool_compatibility_verified=False)
  (out/'result.json').write_text(json.dumps(facts,indent=2)+'\n');print(json.dumps(facts));return
 if not args.paused_pid or args.paused_pid<=1 or not args.paused_start_ticks or args.paused_start_ticks<=0:raise ValueError('Current stopped original PID/start ticks required')
 # Only now import the previously hash/owner-verified module closure.
 sys.path.insert(0,str(ROOT/'tools'))
 from diagnose_compute import counter_command,counter_summary
 from pearl_miner import child,gpu_guard
 guard=gpu_guard(GPU,Decimal(310),args.paused_pid,args.paused_start_ticks);guard()
 os.environ['CUDA_DEVICE_ORDER']='PCI_BUS_ID';os.environ['CUDA_VISIBLE_DEVICES']=GPU
 argv=counter_command(ncu,engine,args.paused_pid,args.paused_start_ticks,out/'hardware')
 (out/'fixed-command.json').write_text(json.dumps(argv,indent=2)+'\n')
 try:
  await child(argv,30,guard,out/'raw.log');guard()
  report=out/'hardware.ncu-rep'
  if not report.is_file() or not report.stat().st_size:raise ValueError('Hardware report absent/empty')
  detail=counter_summary((out/'raw.log').read_text())
  facts.update(passed=True,GPU_executed=True,GPU_profile_success=True,**detail,shares_sent=0,real_hashrate_measured=False,
               instrumented_timings_are_not_benchmark_results=True)
  (out/'result.json').write_text(json.dumps(facts,indent=2)+'\n');print(json.dumps(facts))
 except BaseException as e:
  (out/'failure.json').write_text(json.dumps({'passed':False,'error_type':type(e).__name__,'error':str(e),'GPU_profile_success':False,'raw_log_preserved':(out/'raw.log').is_file()},indent=2)+'\n')
  raise

if __name__=='__main__':asyncio.run(main(parser().parse_args()))
