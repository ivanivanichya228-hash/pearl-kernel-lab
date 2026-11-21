import asyncio,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import pearl_miner as miner
class FusedLive(unittest.TestCase):
 def test_cpu_backend_cannot_claim_fused_gpu_execution(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cfg=root/'config.json';cfg.write_text(json.dumps({'host':'127.0.0.1','port':3360,'wallet':'TEST_ONLY','worker':'test','profile':str(ROOT/'miner/luckypool-profile.json')}));cfg.chmod(0o600)
   args=SimpleNamespace(config=cfg,mock_cpu=True,transfer_overlap=False,triple_stage=False,fused_stage=True,kernel_threads=384,pipeline=True,matrix_loads=False,two_cta=False)
   with self.assertRaisesRegex(ValueError,'fused-stage'):
    asyncio.run(miner.main_async(args))
 def test_native_stage_and_global_identity_across_slabs(self):
  for pn in (8,16):
   m,n=8320,8464
   expected=(m//16)*(n//pn)
   seen=set()
   for r in range(0,m,8192):
    for c in range(0,n,8192):
     rows,cols=min(8192,m-r)//16,min(8192,n-c)//pn
     for row in range(rows):
      start=(r//16+row)*(n//pn)+c//pn
      ids=set(range(start,start+cols))
      self.assertFalse(seen&ids);seen.update(ids)
   self.assertEqual(len(seen),expected);self.assertEqual(max(seen),expected-1)
 def test_release_selects_fused_pipeline(self):
  # Read actual AST, not a textual flag occurrence: verify the packaged dispatch.
  import ast
  tree=ast.parse((ROOT/'release/pearl_test.py').read_text())
  options=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='SimpleNamespace')
  values={k.arg:ast.literal_eval(k.value) for k in options.keywords if k.arg in ('fused_stage','triple_stage','kernel_threads','matrix_loads','two_cta','transfer_overlap')}
  self.assertEqual(values,dict(fused_stage=True,triple_stage=True,kernel_threads=384,matrix_loads=False,two_cta=False,transfer_overlap=False))
if __name__=='__main__':unittest.main()
