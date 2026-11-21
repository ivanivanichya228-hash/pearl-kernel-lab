"""Imported ONLY by the existing trusted root controller; no stop/resume or subprocess API."""
import json,math,os,re,stat,tempfile,time
from pathlib import Path
BASE=Path('/run/pearl-test-sessions')
def issue_session(*,original_pid,original_start_ticks,gpu_uuid,power_limit_w,pause_started_monotonic,deadline_monotonic,cgroup_path,watchdog_unit):
 if os.geteuid()!=0:raise PermissionError('Only the existing root controller may issue a session')
 if type(original_pid) is not int or original_pid<=1 or type(original_start_ticks) is not int or original_start_ticks<=0:raise ValueError('Original process identity required')
 if gpu_uuid!='GPU-14cc341d-41f4-a977-1a1d-12785f4079da' or power_limit_w!=310:raise ValueError('Only selected Mint4090/310W')
 now=time.monotonic()
 if not all(type(x) in (int,float) and math.isfinite(x) for x in (pause_started_monotonic,deadline_monotonic)) or not 0<=now-pause_started_monotonic or not now+20<deadline_monotonic<=pause_started_monotonic+600:raise ValueError('Bounded monotonic deadline required')
 if not isinstance(cgroup_path,str) or not re.fullmatch(r'/system.slice/pearl-[A-Za-z0-9_.@-]+\.service',cgroup_path):raise ValueError('Existing experiment cgroup required')
 if not isinstance(watchdog_unit,str) or not re.fullmatch(r'pearl-[A-Za-z0-9_.@-]+\.timer',watchdog_unit):raise ValueError('Existing watchdog required')
 proc=Path('/proc')/str(original_pid);row=(proc/'stat').read_text().rsplit(')',1)[1].split()
 if row[0]!='T' or int(row[19])!=original_start_ticks:raise ValueError('Original miner is not the expected stopped process')
 for t in (proc/'task').iterdir():
  if (t/'stat').read_text().rsplit(')',1)[1].split()[0]!='T':raise ValueError('A miner thread is still running')
 if not BASE.exists():BASE.mkdir(mode=0o711)
 for p in (BASE,*BASE.parents):
  info=p.lstat()
  if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:raise ValueError('Session directory must be root-owned and protected')
 if not BASE.stat().st_mode&0o001:raise ValueError('Session parent must be traversable by the unprivileged miner')
 folder=Path(tempfile.mkdtemp(prefix='pilot-',dir=BASE));folder.chmod(0o711)
 data=dict(schema='pearl-test-session-v1',original_pid=original_pid,original_start_ticks=original_start_ticks,gpu_uuid=gpu_uuid,power_limit_w=310,pause_started_monotonic=pause_started_monotonic,deadline_monotonic=deadline_monotonic,cgroup_path=cgroup_path,watchdog_unit=watchdog_unit)
 path=folder/'session.json';fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o644)
 with os.fdopen(fd,'w') as out:json.dump(data,out,indent=2);out.write('\n');os.fchmod(out.fileno(),0o644)
 return path
