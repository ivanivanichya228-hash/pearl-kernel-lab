#!/usr/bin/env python3
"""Build only. Optional isolated, SHA-pinned NVIDIA compiler; never runs GPU tests."""
import argparse,hashlib,json,os,shutil,subprocess,tarfile,urllib.request
from pathlib import Path,PurePosixPath
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--download-toolchain',action='store_true')
p.add_argument('--toolchain-dir',type=Path,default=Path.home()/'.cache'/'pearl-kernel-toolchain-13.0.2')
args=p.parse_args()
for tool in ('g++','make'):
    if not shutil.which(tool):raise SystemExit(f'Missing {tool}; no system packages were changed')
if args.download_toolchain:
    dest=args.toolchain_dir.expanduser().resolve();dest.mkdir(parents=True,exist_ok=True)
    lock=json.loads((root/'tools/toolchain-lock.json').read_text())
    for key,a in lock['packages'].items():
        archive=dest/(key+'.tar.xz')
        if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest()!=a['sha256']:
            url='https://developer.download.nvidia.com/compute/cuda/redist/'+a['relative_path']
            partial=archive.with_suffix('.part');total=0
            with urllib.request.urlopen(url,timeout=60) as src,partial.open('wb') as out:
                while chunk:=src.read(1024*1024):
                    total+=len(chunk)
                    if total>int(a['size']):raise ValueError('Download exceeds locked size')
                    out.write(chunk)
            if partial.stat().st_size!=int(a['size']) or hashlib.sha256(partial.read_bytes()).hexdigest()!=a['sha256']:
                raise ValueError('Toolchain checksum/size mismatch')
            partial.replace(archive)
        links=[];unpacked=0
        with tarfile.open(archive) as tf:
            for member in tf:
                name=PurePosixPath(member.name)
                if name.is_absolute() or '..' in name.parts or not name.parts:raise ValueError('Unsafe archive path')
                target=dest.joinpath(*name.parts[1:])
                if not target.resolve().is_relative_to(dest):raise ValueError('Path escapes toolchain')
                if member.isfile():
                    unpacked+=member.size
                    if unpacked>1024**3:raise ValueError('Unpacked size limit')
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with tf.extractfile(member) as src,target.open('wb') as out:shutil.copyfileobj(src,out)
                    target.chmod(0o755 if 'bin' in name.parts[1:] else 0o644)
                elif member.issym():links.append((target,member.linkname))
                elif not member.isdir():raise ValueError('Special archive entry')
        for target,link in links:
            source=(target.parent/link).resolve()
            if not source.is_relative_to(dest):raise ValueError('Symlink escapes toolchain')
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.is_symlink():target.unlink()
            elif target.exists():continue
            target.symlink_to(link)
        print(key+': SHA-256 verified',flush=True)
    cuda_home=dest
else:
    compiler=shutil.which('nvcc')
    if not compiler:raise SystemExit('nvcc missing. Use --download-toolchain for isolated compiler installation without drivers or sudo.')
    cuda_home=Path(compiler).resolve().parents[1]
subprocess.run(['make','cpu-check'],cwd=root,check=True)
subprocess.run(['make',f'CUDA_HOME={cuda_home}'],cwd=root,check=True)
print('Build completed. No GPU tests were run.')
