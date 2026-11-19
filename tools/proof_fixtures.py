#!/usr/bin/env python3
"""Unpack verified synthetic proof fixtures or compare external transcripts to their official oracle.
Comparison to pinned fixtures is NOT execution of the official verifier; use proof_oracle.py for that.
"""
import argparse,hashlib,json,tarfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def unpack(dest):
 lock=json.loads((ROOT/'protocol/fixture-lock.json').read_text());archive=ROOT/'protocol'/lock['archive']
 if sha(archive)!=lock['sha256'] or archive.stat().st_size!=lock['size']:raise ValueError('Archive identity mismatch')
 dest=dest.resolve();dest.mkdir(parents=True,exist_ok=True)
 seen=set()
 with tarfile.open(archive) as tf:
  for item in tf:
   parts=PurePosixPath(item.name).parts
   if len(parts)!=2 or parts[0]!='proof-fixtures' or parts[1] not in lock['files'] or not item.isfile():raise ValueError('Unexpected archive member')
   name=parts[1]
   if name in seen:raise ValueError('Duplicate archive member')
   seen.add(name);data=tf.extractfile(item).read()
   if hashlib.sha256(data).hexdigest()!=lock['files'][name]:raise ValueError('Member hash mismatch')
   target=dest/name
   if target.is_symlink() or (target.exists() and sha(target)!=lock['files'][name]):raise ValueError('Refusing to replace existing fixture')
   target.write_bytes(data)
 if seen!=set(lock['files']):raise ValueError('Incomplete archive')
 print(json.dumps({'fixtures':str(dest),'verified_files':len(seen),'GPU_tested':False}))
def compare(path):
 manifest=json.loads((ROOT/'protocol/manifest.json').read_text());seen=set()
 for line in path.read_text().splitlines():
  if not line.strip():continue
  record=json.loads(line);i=record['case']
  if type(i) is not int or not 0<=i<6 or i in seen:raise ValueError('Unknown or duplicate case')
  words=record['transcript']
  if len(words)!=16 or any(type(x) is not int or not 0<=x<=0xffffffff for x in words):raise ValueError('Invalid transcript words')
  if words!=manifest['cases'][i]['jackpot']:raise ValueError('Transcript mismatch case '+str(i))
  seen.add(i)
 if seen!=set(range(6)):raise ValueError('Missing proof cases')
 print('6 external transcripts match pinned official-verifier fixtures (offline fixture comparison)')
def main():
 p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
 g.add_argument('--unpack',type=Path);g.add_argument('--compare',type=Path);args=p.parse_args()
 if args.unpack:unpack(args.unpack)
 else:compare(args.compare)
if __name__=='__main__':main()
