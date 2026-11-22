#!/usr/bin/env python3
"""Repack0.5.0 using an explicitly supplied NEW CUDA engine from the committed0.2.0 archive. No CUDA/compiler/network/root."""
import argparse,hashlib,json,os,subprocess,sys,tarfile,tempfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
BASE_SHA='36c522d335e3330987d48b394ce616b85544e350bb02b99b90fc043bd2fe952a'
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--producer',type=Path,required=True);p.add_argument('--engine',type=Path,required=True);a=p.parse_args()
 if os.geteuid()==0:raise ValueError('Run as the ordinary user, not root')
 out=a.out.expanduser().absolute()
 if out.exists():raise ValueError('Output must be a NEW directory')
 archive=ROOT/'dist/pearl-test-0.2.0-linux-x86_64.tar.gz'
 if hashlib.sha256(archive.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Base archive SHA mismatch')
 out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.pearl-repack-',dir=out.parent) as tmp:
  staged=Path(tmp)
  with tarfile.open(archive) as tf:
   seen=set()
   for m in tf.getmembers():
    name=PurePosixPath(m.name)
    if name.is_absolute() or '..' in name.parts or not name.parts or name.parts[0]!='pearl-test-0.2.0-linux-x86_64':raise ValueError('Unsafe archive path')
    if m.name in seen or not(m.isfile() or m.isdir()) or m.mode&0o7000:raise ValueError('Unsafe archive member')
    seen.add(m.name)
   tf.extractall(staged)
  base=staged/'pearl-test-0.2.0-linux-x86_64'
  manifest=json.loads((base/'manifest.json').read_text())
  for name,digest in manifest['files'].items():
   rel=PurePosixPath(name)
   if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe manifest')
   path=base.joinpath(*rel.parts)
   if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Base manifest mismatch')
  subprocess.run([sys.executable,str(ROOT/'release/build_test_release.py'),'--out',str(out),'--engine',str(a.engine.resolve()),'--oracle',str(base/'bin/pearl-protocol-oracle'),'--producer',str(a.producer.resolve())],check=True)
  new=out/'pearl-test-0.5.0-linux-x86_64'
  for name in ('bin/pearl-protocol-oracle',):
   if hashlib.sha256((new/name).read_bytes()).digest()!=hashlib.sha256((base/name).read_bytes()).digest():raise ValueError('Executable unexpectedly changed')
 print('Repacked using supplied CUDA engine and original oracle; no GPU computation or pool connection')
if __name__=='__main__':main()
