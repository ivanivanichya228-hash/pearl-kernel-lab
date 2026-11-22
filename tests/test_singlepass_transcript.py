"""Check the algebra, writer coverage and CPU-backend refusal."""
import unittest
import numpy as np
class SinglePass(unittest.TestCase):
 def test_prefix_recurrence_exactly_matches_single_write_only_at_sixteen_checkpoints(self):
  rng=np.random.default_rng(20261122)
  for count in (1,8,15,16,17,32,64):
   words=rng.integers(0,2**32,(count,37),dtype=np.uint32);history=np.zeros((16,37),dtype=np.uint32)
   for cp,x in enumerate(words):
    h=history[cp&15];history[cp&15]=((h<<13)|(h>>19))^x
   if count==16:np.testing.assert_array_equal(history,words)
   if count>16:self.assertFalse(np.array_equal(history,words[-16:]))
 def test_all_slots_written_before_transpose_even_on_edge_tiles(self):
  for pn in (8,16):
   writes={}
   for warp in range(12):
    wm,wn=divmod(warp,4)
    for im in range(4):
     for col in range(8//(pn//8)):
      proof=(wm*4+im)*(256//pn)+wn*(64//pn)+col
      for slot in range(16):writes[proof,slot]=writes.get((proof,slot),0)+1
   self.assertEqual(len(writes),12*(256//pn)*16);self.assertTrue(all(n==1 for n in writes.values()))
 def test_cpu_backend_rejects_singlepass_gpu_claim(self):
  import sys,asyncio,tempfile,json
  from pathlib import Path
  from types import SimpleNamespace
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'));import pearl_miner as m
  with tempfile.TemporaryDirectory() as tmp:
   c=Path(tmp)/'config';c.write_text(json.dumps(dict(host='127.0.0.1',port=1,wallet='TEST_ONLY',worker='test',profile=str(Path(__file__).resolve().parents[1]/'pool/pipeline-lab.json'))));c.chmod(0o600)
   args=SimpleNamespace(config=c,mock_cpu=True,transfer_overlap=False,triple_stage=False,fused_stage=True,singlepass_transcript=True,kernel_threads=384,pipeline=True,matrix_loads=False,two_cta=False)
   with self.assertRaisesRegex(ValueError,'singlepass'):asyncio.run(m.main_async(args))
if __name__=='__main__':unittest.main()
