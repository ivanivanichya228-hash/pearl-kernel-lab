"""Bounded private tmpfs workspaces; no automatic disk fallback."""
import json,os,tempfile
from pathlib import Path
class RamWorkspace:
 def __init__(self,profile,parent=Path('/dev/shm'),slots=2,extra_resident_bytes=0):
  self.extra_resident_bytes=extra_resident_bytes
  self.parent=parent.resolve();self.slots=slots;self.per_slot=2*(profile.m+profile.n)*profile.k+1024*1024
  # Explicitly require a RAM filesystem for the large raw/noisy work arrays.
  mounts=[]
  for line in Path('/proc/self/mountinfo').read_text().splitlines():
   left,right=line.split(' - ',1);parts=left.split();mount=parts[4].replace('\\040',' ')
   if self.parent==Path(mount) or str(self.parent).startswith(mount.rstrip('/')+'/'):mounts.append((len(mount),right.split()[0]))
  if not mounts or max(mounts)[1]!='tmpfs':raise ValueError('Pipeline workspace must be tmpfs; disk fallback disabled')
  available=os.statvfs(self.parent);free=available.f_bavail*available.f_frsize;headroom=max(4*1024*1024,self.per_slot//4)
  if free<slots*self.per_slot+headroom:raise ValueError('Insufficient tmpfs capacity for two full work buffers')
  info={line.split(':',1)[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line and len(line.split())>=2 and line.split()[1].isdecimal()}
  if info.get('MemAvailable',0)<slots*self.per_slot+6*(profile.m+profile.n)*profile.k+headroom+extra_resident_bytes:raise ValueError('Insufficient available RAM for pipeline')
  self.temp=tempfile.TemporaryDirectory(prefix='pearl-pipeline-',dir=self.parent);self.path=Path(self.temp.name);self.path.chmod(0o700)
 def cleanup(self):self.temp.cleanup()
 def describe(self):return {'path':str(self.path),'filesystem':'tmpfs','maximum_workspaces':self.slots,'estimated_bytes_per_workspace':self.per_slot,'extra_resident_bytes':self.extra_resident_bytes,'disk_fallback':False}
