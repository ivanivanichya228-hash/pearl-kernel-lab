"""CPU-only Rust producer build from an explicit, already-built dependency cache.

This path installs/downloads nothing and does not replace the pinned verifier.
For a clean dependency build, see MAPPED-INPUT.md (Cargo path).
"""
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CRATES={'zk_pow':'22708380f83a0de6','pearl_blake3':'ac63eb3eaa3a5450','rand':'17b307039858d2ad','primitive_types':'96665a351ddeca11','anyhow':'c1e387e759ddf845','bincode':'56d906212465e384','rayon':'02f9ce23613aa2d0','serde_json':'44ad4adabbd78393','sha2':'57da566749e67d26'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--rustc',type=Path,required=True);p.add_argument('--cached-deps',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--test',action='store_true');a=p.parse_args()
 if a.out.exists():raise ValueError('NEW output path required')
 dep=a.cached_deps.resolve(strict=True);compiler=a.rustc.resolve(strict=True)
 cmd=[str(compiler),'--edition=2024','-C','opt-level=3','-C','strip=symbols','-L',f'dependency={dep}']
 files={}
 for name,key in CRATES.items():
  file=dep/f'lib{name}-{key}.rlib';files[file.name]=hashlib.sha256(file.read_bytes()).hexdigest();cmd+=['--extern',f'{name}={file}']
 if a.test:cmd+=['--test']
 a.out.parent.mkdir(parents=True,exist_ok=True);cmd += [str(ROOT/'proof-oracle/src/main.rs'),'-o',str(a.out)]
 subprocess.run(cmd,check=True)
 result={'compiler':subprocess.check_output([str(compiler),'--version'],text=True).strip(),'direct_dependency_rlib_sha256':files,'producer_sha256':hashlib.sha256(a.out.read_bytes()).hexdigest(),'test_binary':a.test,'GPU_executed':False,'external_network_used':False,'upstream_commit':'38dd764ab0aec528e81fc467665c6762ef6739e9'}
 a.out.with_suffix('.build.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
