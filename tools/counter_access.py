"""Read-only verification of a transient CAP_PERFMON scope. No GPU calls/setters."""
import json,os,re,struct
from pathlib import Path
PERFMON=1<<38
CAP_FIELDS=('CapInh','CapPrm','CapEff','CapBnd','CapAmb')

def inspect_access(status,auxv,uid,driver_major):
 fields=dict(line.split(':',1) for line in status.splitlines() if ':' in line)
 caps={name:int(fields.get(name,'0').strip(),16) for name in CAP_FIELDS}
 secure=None;terminated=False
 if len(auxv)%16:raise ValueError('Malformed Linux x86_64 auxv')
 for key,value in struct.iter_unpack('=QQ',auxv):
  if key==0:terminated=True;break
  if key==23:secure=value
 valid=(uid==1000 and type(driver_major) is int and driver_major>=565 and terminated
        and secure==0 and all(value==PERFMON for value in caps.values())
        and fields.get('NoNewPrivs','').strip()=='1')
 return {'uid':uid,'driver_major':driver_major,'AT_SECURE':secure,'auxv_terminated':terminated,
         'NoNewPrivs':fields.get('NoNewPrivs','').strip(),
         'capabilities':{k:f'{v:016x}' for k,v in caps.items()},
         'ambient_perfmon_scope_valid':valid,'GPU_executed':False,
         'system_permissions_changed':False}

def current_access():
 driver=None
 try:
  version=Path('/sys/module/nvidia/version').read_text().strip();driver=int(version.split('.')[0])
 except (OSError,ValueError):pass
 if driver is None:
  try:
   match=re.search(r'Kernel Module\s+(\d+)\.',Path('/proc/driver/nvidia/version').read_text())
   if match:driver=int(match.group(1))
  except OSError:pass
 return inspect_access(Path('/proc/self/status').read_text(),Path('/proc/self/auxv').read_bytes(),os.geteuid(),driver)

if __name__=='__main__':print(json.dumps(current_access(),indent=2))
