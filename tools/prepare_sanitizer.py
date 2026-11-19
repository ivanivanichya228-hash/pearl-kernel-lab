#!/usr/bin/env python3
"""Prepare a SHA-pinned standalone NVIDIA sanitizer, never install or run GPU work."""
import argparse,hashlib,json,os,platform,re,shutil,subprocess,sys,tarfile,tempfile,urllib.request
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
LOCK={'version':'13.0.85','tool_version':'2025.3.1','size':11399964,
 'sha256':'8eeba425f66fdd17e78d0dff49baa8b3e4599fc0579984eab7ad9c486a95ebf2',
 'url':'https://developer.download.nvidia.com/compute/cuda/redist/cuda_sanitizer_api/linux-x86_64/cuda_sanitizer_api-linux-x86_64-13.0.85-archive.tar.xz',
 'metadata_url':'https://developer.download.nvidia.com/compute/cuda/redist/redistrib_13.0.2.json'}
CACHE=ROOT/'.sanitizer-cache'
REQUIRED=('compute-sanitizer','TreeLauncherSubreaper','TreeLauncherTargetLdPreloadHelper',
 'libsanitizer-collection.so','libsanitizer-public.so','libTreeLauncherTargetInjection.so','libInterceptorInjectionTarget.so')

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  while chunk:=f.read(1024*1024):h.update(chunk)
 return h.hexdigest()

def checked_members(tf):
 entries=list(tf.getmembers());tops=set();total=0
 for m in entries:
  p=PurePosixPath(m.name)
  if p.is_absolute() or '..' in p.parts or not p.parts:raise ValueError('Unsafe archive path')
  tops.add(p.parts[0]);total+=m.size
  if not (m.isfile() or m.isdir() or m.issym()):raise ValueError('Unsupported archive entry')
  if m.issym():
   if PurePosixPath(m.linkname).is_absolute():raise ValueError('Absolute symlink')
   # Resolve lexical symlink target within the archive root.
   parts=list(p.parts[:-1])
   for bit in PurePosixPath(m.linkname).parts:
    if bit=='..':
     if len(parts)<=1:raise ValueError('Escaping symlink')
     parts.pop()
    elif bit!='.':parts.append(bit)
 if len(tops)!=1 or total>256*1024*1024:raise ValueError('Unexpected archive layout/size')
 return entries,tops.pop()

def validate_archive(path):
 if path.stat().st_size!=LOCK['size'] or digest(path)!=LOCK['sha256']:
  raise ValueError('Archive checksum/size mismatch')

def resolve_bundle():
 archive=CACHE/'sanitizer.tar.xz';validate_archive(archive)
 dest=CACHE/('bundle-'+LOCK['sha256'][:12])
 with tarfile.open(archive) as tf:
  entries,top=checked_members(tf)
  for m in entries:
   rel=PurePosixPath(m.name);p=dest.joinpath(*rel.parts)
   if not p.resolve().is_relative_to(dest.resolve()):raise ValueError('Installed path escapes bundle')
   if m.isfile():
    source=tf.extractfile(m)
    if not p.is_file() or p.is_symlink() or digest(p)!=hashlib.sha256(source.read()).hexdigest():
     raise ValueError('Bundle file changed/missing: '+m.name)
   elif m.issym():
    if not p.is_symlink() or os.readlink(p)!=m.linkname:raise ValueError('Bundle symlink differs')
 folder=dest/top/'compute-sanitizer'
 for name in REQUIRED:
  if not (folder/name).is_file():raise ValueError('Missing required component: '+name)
 for name in REQUIRED[:3]:
  if not os.access(folder/name,os.X_OK):raise ValueError('Launcher is not executable')
 return {'executable':str(folder/'compute-sanitizer'),'injection_path':str(folder),
         'library_search_path':str(folder),'archive_sha256':LOCK['sha256'],'GPU_tested':False}

def child_env(config):
 env=os.environ.copy()
 old=env.get('LD_LIBRARY_PATH','').split(':')
 old=[p for p in old if p and 'compute-sanitizer' not in p]
 env['LD_LIBRARY_PATH']=':'.join([config['library_search_path'],*old])
 return env

def prepare(source_archive=None):
 if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64'):raise ValueError('Linux x86-64 required')
 CACHE.mkdir(mode=0o700,exist_ok=True)
 if CACHE.is_symlink() or CACHE.stat().st_uid!=os.getuid():raise ValueError('Unexpected cache ownership/link')
 archive=CACHE/'sanitizer.tar.xz'
 if not archive.exists():
  partial=CACHE/'download.part'
  try:
   if source_archive:shutil.copyfile(source_archive,partial)
   else:
    total=0
    with urllib.request.urlopen(LOCK['url'],timeout=30) as src,partial.open('wb') as out:
     while chunk:=src.read(1024*1024):
      total+=len(chunk)
      if total>LOCK['size']:raise ValueError('Download exceeds pinned size')
      out.write(chunk)
   validate_archive(partial);partial.replace(archive)
  finally:
   if partial.exists():partial.unlink()
 validate_archive(archive)
 dest=CACHE/('bundle-'+LOCK['sha256'][:12])
 if not dest.exists():
  staging=Path(tempfile.mkdtemp(prefix='extract-',dir=CACHE))
  try:
   with tarfile.open(archive) as tf:
    entries,top=checked_members(tf)
    # Verified official archive. Materialize regular files first, symlinks last.
    for m in entries:
     target=staging.joinpath(*PurePosixPath(m.name).parts)
     if m.isdir():target.mkdir(parents=True,exist_ok=True)
     elif m.isfile():
      target.parent.mkdir(parents=True,exist_ok=True)
      with tf.extractfile(m) as src,target.open('wb') as out:shutil.copyfileobj(src,out)
      target.chmod(0o755 if m.mode&0o111 else 0o644)
    for m in entries:
     if m.issym():
      target=staging.joinpath(*PurePosixPath(m.name).parts);target.parent.mkdir(parents=True,exist_ok=True);target.symlink_to(m.linkname)
   staging.rename(dest)
  finally:
   if staging.exists():shutil.rmtree(staging)
 config=resolve_bundle();env=child_env(config)
 for flag in ('--version','--help'):
  r=subprocess.run([config['executable'],flag],capture_output=True,text=True,timeout=10,env=env)
  if r.returncode:raise ValueError('Tool version/help failed: '+r.stderr[-1000:])
  if flag=='--version':
   if LOCK['tool_version'] not in r.stdout+r.stderr:raise ValueError('Unexpected tool version')
   config['version_output']=(r.stdout+r.stderr).strip()
 missing=[]
 for p in Path(config['injection_path']).glob('*.so'):
  r=subprocess.run(['ldd',str(p)],capture_output=True,text=True,timeout=10,env=env)
  if r.returncode or 'not found' in r.stdout+r.stderr:missing.append({'file':p.name,'output':r.stdout+r.stderr})
 if missing:raise ValueError('Unresolved bundle dependencies: '+json.dumps(missing))
 config['dependencies_resolved']=True
 return config

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,help='optional existing official archive; still hash checked')
 args=p.parse_args();print(json.dumps(prepare(args.archive),indent=2))
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,subprocess.SubprocessError) as e:
  print(json.dumps({'ready':False,'GPU_tested':False,'error':str(e)},indent=2));sys.exit(1)
