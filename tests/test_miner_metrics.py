import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from miner_metrics import Performance
from luckypool_adapter import Profile
import pearl_miner as miner
class MetricsTests(unittest.TestCase):
 def setUp(self):
  self.p=Profile(32,32,4096,256,tuple(range(16)),tuple(range(16)));self.now=0;self.m=Performance(self.p,lambda:self.now)
 def test_wall_time_and_distinct_units(self):
  self.m.gpu_complete('a','id-a',4);self.m.classify('a','fresh');self.m.stage('prepare',3,'completed');self.m.stage('GPU',1,'completed');self.now=10;r=self.m.snapshot()
  self.assertEqual(r['completed_candidates_per_second'],.4);self.assertEqual(r['fresh_finished_dense_arithmetic_TOP_s'],2*32*32*4096/10/1e12);self.assertEqual(r['official_target_weight_units_per_second'],4*524288/10);self.assertFalse(r['pool_hashrate_measured'])
 def test_stale_does_not_inflate_effective_rate(self):
  self.m.gpu_complete('a','one',4);self.m.classify('a','stale');self.now=2;r=self.m.snapshot();self.assertEqual(r['completed_candidate_groups'],4);self.assertEqual(r['fresh_finished_candidates_per_second'],0)
 def test_partial_work_is_never_credited(self):
  self.m.stage('GPU',3,'cancelled');self.now=4;r=self.m.snapshot();self.assertEqual(r['completed_candidate_groups'],0);self.assertEqual(r['stages']['GPU']['cancelled'],1)
 def test_duplicate_or_wrong_size_rejected(self):
  self.m.gpu_complete('a','one',4)
  for batch,identity,groups in [('a','two',4),('b','one',4),('b','two',5)]:
   with self.assertRaises(ValueError):self.m.gpu_complete(batch,identity,groups)
 def test_stability_is_explicit_bounded_mode(self):
  self.assertEqual(miner.validate_runtime(540,True,0,True),540)
  for duration,extended,stop,stability in [(540,False,0,True),(540,True,0,False),(540,True,1,True),(601,True,0,True)]:
   with self.assertRaises(ValueError):miner.validate_runtime(duration,extended,stop,stability)
if __name__=='__main__':unittest.main()
