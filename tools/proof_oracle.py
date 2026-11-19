#!/usr/bin/env python3
"""Optional CPU-only rebuild of the upstream Pearl plain-proof compatibility oracle."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMMIT='38dd764ab0aec528e81fc467665c6762ef6739e9'
URL='https://github.com/pearl-research-labs/pearl.git'
def run(args,**kwargs):return subprocess.run([str(x) for x in args],check=True,**kwargs)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cargo',default=shutil.which('cargo'))
 p.add_argument('--upstream',type=Path);p.add_argument('--generate',type=Path)
 p.add_argument('--verify',type=Path,help='external transcript JSONL');p.add_argument('--fixtures',type=Path)
 args=p.parse_args()
 if not args.cargo:raise SystemExit('Cargo absent; prepared fixtures require no Rust on the rig')
 if bool(args.generate)==bool(args.verify):p.error('choose generate or verify')
 cache=ROOT/'.proof-cache';cache.mkdir(exist_ok=True)
 upstream=args.upstream.resolve() if args.upstream else cache/'upstream'
 if not upstream.exists():
  if args.upstream:raise SystemExit('Requested upstream directory is missing')
  run(['git','clone','--depth','1',URL,upstream])
  run(['git','-C',upstream,'fetch','--depth','1','origin',COMMIT])
  run(['git','-C',upstream,'checkout','--detach',COMMIT])
 head=subprocess.check_output(['git','-C',str(upstream),'rev-parse','HEAD'],text=True).strip()
 if head!=COMMIT:raise SystemExit('Upstream commit differs; no checkout reset performed')
 run(['git','-C',upstream,'diff','--exit-code','HEAD','--','zk-pow','pearl-blake3','plonky2'])
 default=cache/'upstream'
 if upstream!=default.resolve():
  if default.exists() or default.is_symlink():
   if default.resolve()!=upstream:raise SystemExit('Existing upstream cache points elsewhere')
  else:default.symlink_to(upstream,target_is_directory=True)
 run([args.cargo,'build','--locked','--release','--jobs','4','--manifest-path',ROOT/'proof-oracle/Cargo.toml'])
 binary=ROOT/'proof-oracle/target/release/pearl-protocol-oracle'
 if args.generate:
  if args.generate.exists() and any(args.generate.iterdir()):raise SystemExit('Output directory not empty; refusing overwrite')
  run([binary,args.generate.resolve()])
  manifest_path=args.generate/'manifest.json';manifest=json.loads(manifest_path.read_text())
  for case in manifest['cases']:
   case['fixture_sha256']=hashlib.sha256((args.generate/f"case-{case['case']}.bin").read_bytes()).hexdigest()
  manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
 else:
  if not args.fixtures:p.error('verify requires fixtures directory')
  run([binary,'verify',args.fixtures.resolve(),args.verify.resolve()])
if __name__=='__main__':main()
