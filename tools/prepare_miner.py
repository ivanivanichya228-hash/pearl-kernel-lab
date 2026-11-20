#!/usr/bin/env python3
"""Install the pinned private oracle executable into build/, without Rust or system writes."""
import gzip,hashlib,json,os,platform,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def prepare():
 if platform.system()!='Linux' or platform.machine()!='x86_64':raise ValueError('Prepared oracle requires Linux x86_64')
 lock=json.loads((ROOT/'miner/oracle-lock.json').read_text());archive=ROOT/'miner'/lock['archive']
 for p,digest in lock['sources_sha256'].items():
  if sha((ROOT/p).read_bytes())!=digest:raise ValueError('Source differs from prepared executable: '+p)
 data=archive.read_bytes()
 if len(data)!=lock['archive_size'] or sha(data)!=lock['archive_sha256']:raise ValueError('Archive checksum differs')
 data=gzip.decompress(data)
 if len(data)!=lock['binary_size'] or sha(data)!=lock['binary_sha256']:raise ValueError('Executable checksum differs')
 build=ROOT/'build';build.mkdir(exist_ok=True);dest=build/'pearl-protocol-oracle'
 if dest.is_symlink():raise ValueError('Refusing symlink executable')
 if dest.exists() and sha(dest.read_bytes())!=lock['binary_sha256']:raise ValueError('Refusing to replace different executable')
 fd,tmp=tempfile.mkstemp(prefix='oracle-',dir=build)
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);os.fchmod(f.fileno(),0o700)
  os.replace(tmp,dest)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
 print(json.dumps({'oracle':str(dest),'sha256':lock['binary_sha256'],'GPU_used':False,'network_used':False,'system_changed':False}))
if __name__=='__main__':prepare()
