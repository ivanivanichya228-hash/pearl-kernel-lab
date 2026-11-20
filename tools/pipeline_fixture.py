#!/usr/bin/env python3
"""Unpack the SHA-pinned, offline, synthetic-target batch; no GPU or network work."""
import argparse,hashlib,json,tarfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
def unpack(dest):
 lock=json.loads((ROOT/'pool/pipeline-lock.json').read_text());archive=ROOT/'pool'/lock['archive']
 if archive.stat().st_size!=lock['size'] or hashlib.sha256(archive.read_bytes()).hexdigest()!=lock['sha256']:raise ValueError('Archive identity mismatch')
 dest=dest.resolve()
 if dest.exists():raise ValueError('Use a new output directory')
 data={}
 with tarfile.open(archive) as tf:
  for item in tf:
   parts=PurePosixPath(item.name).parts
   if len(parts)!=2 or parts[0]!='pipeline-lab' or parts[1] not in lock['files'] or not item.isfile() or item.size>1048576:raise ValueError('Unexpected archive member')
   name=parts[1]
   if name in data:raise ValueError('Duplicate archive member')
   b=tf.extractfile(item).read()
   if hashlib.sha256(b).hexdigest()!=lock['files'][name]:raise ValueError('Member hash mismatch')
   data[name]=b
 if set(data)!=set(lock['files']):raise ValueError('Incomplete archive')
 dest.mkdir(parents=True)
 for name,b in data.items():(dest/name).write_bytes(b)
 print(json.dumps({'batch':str(dest),'verified_files':len(data),'synthetic_target':True,'GPU_executed':False}))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--unpack',type=Path,required=True);unpack(p.parse_args().unpack)
