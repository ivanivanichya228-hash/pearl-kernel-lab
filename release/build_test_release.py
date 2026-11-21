"""Build a ready pilot archive from existing verified local binaries; no GPU/network."""
import argparse,hashlib,json,re,shutil,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
KERNEL='711db036ef1ee512483ab619df0d67d2655e66c7'
MODULES=['guard_checks.py','pearl_miner.py','luckypool_adapter.py','miner_metrics.py','miner_pipeline.py','persistent_engine.py','queued_engine.py','ram_workspace.py']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def build(output,engine,oracle):
 output=output.absolute()
 if output.exists():raise ValueError('NEW output directory required')
 output.mkdir(parents=True);package=output/'pearl-test-0.2.1-linux-x86_64';package.mkdir()
 for n in ('bin','lib','share','licenses','integration'):(package/n).mkdir()
 shutil.copyfile(ROOT/'release/pearl_test.py',package/'pearl-test');(package/'pearl-test').chmod(0o755)
 for n in MODULES:shutil.copyfile(ROOT/'tools'/n,package/'lib'/n)
 shutil.copyfile(engine,package/'bin/pearl-engine');shutil.copyfile(oracle,package/'bin/pearl-protocol-oracle')
 for p in (package/'bin').iterdir():p.chmod(0o755)
 lock=json.loads((ROOT/'miner/oracle-lock.json').read_text())
 if digest(oracle)!=lock['binary_sha256']:raise ValueError('Oracle is not the pinned verified executable')
 (package/'share/profile.json').write_bytes((ROOT/'miner/luckypool-profile.json').read_bytes())
 (package/'config.example.json').write_text(json.dumps(dict(host='pearl-eu2.luckypool.io',port=3360,wallet='',worker='pearl-test-4090'),indent=2)+'\n')
 shutil.copyfile(ROOT/'release/README_RU.md',package/'README_RU.md')
 shutil.copyfile(ROOT/'release/issue_session.py',package/'integration/issue_session.py')
 shutil.copyfile(ROOT/'release/CONTROLLER.md',package/'integration/CONTROLLER.md')
 shutil.copyfile(ROOT/'LICENSE',package/'licenses/PROJECT-MIT.txt')
 shutil.copyfile(ROOT/'third_party/NVIDIA-CUDA-LICENSE.txt',package/'licenses/NVIDIA-CUDA-LICENSE.txt')
 for source,name in [('PEARL-UPSTREAM.txt','PEARL-UPSTREAM.txt'),('PLONKY2-MIT.txt','PLONKY2-MIT.txt'),('PLONKY2-APACHE.txt','PLONKY2-APACHE.txt')]:
  shutil.copyfile(ROOT/'release/licenses'/source,package/'licenses'/name)
 versions=[]
 for binary in (engine,oracle):
  text=subprocess.check_output(['readelf','--version-info',str(binary)],text=True)
  versions.extend(tuple(map(int,m)) for m in re.findall(r'Name: GLIBC_(\d+)\.(\d+)\b',text))
 manifest=dict(version='0.2.1-fused-async',kernel='fused-triple384',kernel_commit=KERNEL,source_url='https://github.com/ivanivanichya228-hash/pearl-kernel-lab',engine_build='CUDA13.0.88 / SM86+SM89 / static CUDA runtime',driver_major_min=580,glibc_min=list(max(versions)),developer_fee_percent=0,GPU_release_package_tested=False,controller_required=True,maximum_duration_seconds=420,files={})
 manifest['files']={str(p.relative_to(package)):digest(p) for p in sorted(package.rglob('*')) if p.is_file()}
 (package/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 subprocess.run([str(package/'pearl-test'),'verify','--offline'],check=True)
 archive=output/'pearl-test-0.2.1-linux-x86_64.tar.gz'
 with tarfile.open(archive,'w:gz') as tar:tar.add(package,arcname=package.name,filter=lambda i:None if '__pycache__' in i.name else i)
 (output/'SHA256SUMS.txt').write_text(digest(archive)+'  '+archive.name+'\n')
 result={'archive':str(archive),'bytes':archive.stat().st_size,'sha256':digest(archive),'package':str(package),'GPU_executed':False}
 (output/'BUILD-RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--engine',type=Path,required=True);p.add_argument('--oracle',type=Path,required=True);args=p.parse_args();build(args.out,args.engine.resolve(),args.oracle.resolve())
