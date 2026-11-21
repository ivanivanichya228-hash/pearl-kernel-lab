"""Inert pre-pause probe of the exact trusted transient profiling scope."""
import argparse,hashlib,json,os,stat,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from counter_access import current_access

def trusted_file(path,executable=False):
 path=path.resolve(strict=True)
 for parent in (path,*path.parents):
  info=parent.stat()
  if info.st_uid!=0 or info.st_mode&0o022:raise ValueError('Counter-scope code/path must be root-owned and not group/other writable: '+str(parent))
 info=path.stat()
 if not stat.S_ISREG(info.st_mode) or info.st_mode&0o6000:raise ValueError('Expected ordinary non-setuid/non-setgid file')
 if executable and not os.access(path,os.X_OK):raise ValueError('Executable access missing')
 try:cap=os.getxattr(path,'security.capability')
 except OSError as e:
  import errno
  if e.errno not in (errno.ENODATA,errno.ENOTSUP):raise
  cap=b''
 if cap:raise ValueError('File capabilities are not allowed; use transient ambient capability only')
 return path

def probe(ncu,engine,expected_ncu,expected_engine):
 access=current_access()
 if not access['ambient_perfmon_scope_valid']:raise ValueError('Transient PERFMON-only UID1000 scope is not active')
 for name in ('LD_PRELOAD','LD_AUDIT','PYTHONPATH','PYTHONHOME'):
  if os.environ.get(name):raise ValueError('Unsafe inherited environment: '+name)
 interpreter=trusted_file(Path(sys.executable),True)
 trusted_file(Path(__file__));helper=trusted_file(Path(__file__).with_name('counter_access.py'))
 ncu=trusted_file(ncu,True);engine=trusted_file(engine,True)
 for path,digest in ((ncu,expected_ncu),(engine,expected_engine)):
  if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Pinned executable checksum mismatch: '+str(path))
 child=subprocess.run([str(interpreter),'-I',str(helper)],capture_output=True,text=True,check=True,timeout=5)
 inherited=json.loads(child.stdout)
 if not inherited['ambient_perfmon_scope_valid']:raise ValueError('Capability did not survive subprocess exec')
 version=subprocess.run([str(ncu),'--version'],capture_output=True,text=True,check=True,timeout=5)
 return {'passed':True,'GPU_executed':False,'driver_permissions_changed':False,
  'file_capabilities_installed':False,'runner_access':access,'exec_child_access':inherited,
  'ncu':str(ncu),'engine':str(engine),'ncu_sha256':expected_ncu,'engine_sha256':expected_engine,
  'ncu_version':version.stdout.strip(),'GPU_driver_tool_compatibility_verified':False}

def main():
 p=argparse.ArgumentParser();p.add_argument('--ncu',type=Path,required=True);p.add_argument('--engine',type=Path,required=True);p.add_argument('--expected-ncu-sha256',required=True);p.add_argument('--expected-engine-sha256',required=True);args=p.parse_args()
 try:r=probe(args.ncu,args.engine,args.expected_ncu_sha256,args.expected_engine_sha256)
 except Exception as e:
  print(json.dumps({'passed':False,'GPU_executed':False,'error':str(e),'access':current_access()}));raise SystemExit(1)
 print(json.dumps(r,indent=2))
if __name__=='__main__':main()
