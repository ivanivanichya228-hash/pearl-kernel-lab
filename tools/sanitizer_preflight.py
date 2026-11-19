#!/usr/bin/env python3
"""Audit installed Compute Sanitizer; smoke-test a CPU-only /usr/bin/true.
No package installation, symlinks, system configuration, miner or CUDA workload.
"""
import argparse,json,os,shutil,stat,struct,subprocess,sys
from pathlib import Path

LIBRARIES=('libsanitizer-collection.so','libsanitizer-public.so')

def run(args,timeout=10,env=None):
    return subprocess.run(args,capture_output=True,text=True,timeout=timeout,env=env)

def trusted(path):
    p=Path(path).resolve(strict=True)
    for part in (p,*p.parents):
        s=part.stat()
        if s.st_uid!=0 or s.st_mode & (stat.S_IWGRP|stat.S_IWOTH):
            raise ValueError('Installed tool/library path is not root-owned and non-writable: '+str(part))
    return p

def check_elf(path):
    with Path(path).open('rb') as f:h=f.read(20)
    if len(h)<20 or h[:4]!=b'\x7fELF' or h[4:6]!=bytes((2,1)) or struct.unpack('<H',h[18:20])[0]!=62:
        raise ValueError('Expected x86-64 little-endian ELF: '+str(path))

def owner(path):
    if not shutil.which('dpkg-query'):return None
    r=run(['dpkg-query','-S',str(path)])
    matches=[]
    for line in r.stdout.splitlines():
        if ': ' in line:
            package,listed=line.rsplit(': ',1)
            if listed==str(path):matches.append(package)
    if len(set(matches))==1:return matches[0]
    return None

def candidate_dirs(exe,package):
    dirs=[exe.parent,exe.parent/'../lib',Path('/usr/lib/nvidia-cuda-toolkit/compute-sanitizer')]
    if package:
        r=run(['dpkg-query','-L',package])
        dirs.extend(Path(x).parent for x in r.stdout.splitlines() if x.endswith('/libsanitizer-collection.so'))
    seen=set()
    for d in dirs:
        d=d.resolve()
        if d not in seen:seen.add(d);yield d

def prepare():
    name=shutil.which('compute-sanitizer')
    if not name:raise ValueError('compute-sanitizer is not installed')
    exe=trusted(name);check_elf(exe)
    help_result=run([str(exe),'--help']);version=run([str(exe),'--version'])
    if help_result.returncode or version.returncode:raise ValueError('Tool version/help failed')
    help_text=help_result.stdout+help_result.stderr
    for option in ('injection-path','require-cuda-init','error-exitcode','leak-check'):
        if option not in help_text:raise ValueError('Installed tool does not advertise '+option)
    package=owner(exe) or owner(Path(name))
    rejected=[]
    for folder in candidate_dirs(exe,package):
        try:
            for library in LIBRARIES:
                p=trusted(folder/library);check_elf(p)
                if package and owner(folder/library)!=package and owner(p)!=package:
                    raise ValueError('Injection library is not from the executable package: '+str(p))
                ldd=shutil.which('ldd')
                if not ldd:raise ValueError('ldd unavailable; dependency check incomplete')
                result=run([ldd,str(p)])
                if result.returncode or 'not found' in result.stdout+result.stderr:
                    raise ValueError('Unresolved shared dependencies: '+str(p))
            return {'executable':str(exe),'injection_path':str(folder),'package':package,
                    'version':(version.stdout+version.stderr).strip(),
                    'libraries':list(LIBRARIES),'dependencies_resolved':True,'GPU_tested':False}
        except (OSError,ValueError) as e:rejected.append(str(e))
    raise ValueError('No complete matching injection directory; '+'; '.join(rejected))

def smoke_test(config):
    target=trusted('/usr/bin/true');check_elf(target)
    env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']='-1'
    command=[config['executable'],'--injection-path',config['injection_path'],
             '--tool','memcheck','--require-cuda-init','no','--error-exitcode','86',str(target)]
    result=run(command,timeout=15,env=env)
    output=result.stdout+result.stderr
    if result.returncode or 'Unable to find injection library' in output:
        raise ValueError('CPU-only injection smoke test failed, exit '+str(result.returncode)+': '+output[-1500:])
    config=dict(config);config.update(CPU_smoke_passed=True,CPU_smoke_output=output.strip(),GPU_tested=False)
    return config

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit-only',action='store_true',help='inspect paths/dependencies without launching sanitizer')
    args=p.parse_args()
    config=prepare()
    if not args.audit_only:config=smoke_test(config)
    print(json.dumps(config,indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        print(json.dumps({'ready':False,'GPU_tested':False,'error':str(e)},indent=2));sys.exit(1)
