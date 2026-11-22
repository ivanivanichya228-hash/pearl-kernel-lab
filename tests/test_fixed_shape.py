import unittest,importlib.util,json
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'release/pearl_test.py';spec=importlib.util.spec_from_file_location('fixed_shape_release',p);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class FixedShape(unittest.TestCase):
 def rows(self):return [dict(phase='fused_correctness',passed=True,fixtures=12,singlepass_candidate=True,fixed_shape_candidate=True),*[dict(phase='fused_benchmark',leg=i,fused=i in(1,2),combined_compute_filter_ms=t)for i,t in enumerate([11,9,9,11])],dict(phase='fused_comparison',baseline='singlepass-fused-triple384',candidate='fixed-shape-fused-triple384',speed_ratio=11/9)]
 def check(self,rows):return r.validate_fixed_shape_gate('\n'.join(map(json.dumps,rows)))
 def test_new_control_is_04_not_03(self):
  self.assertAlmostEqual(self.check(self.rows())['ratio'],11/9)
  rows=self.rows();rows[-1]['baseline']='original-fused-triple384'
  with self.assertRaises(ValueError):self.check(rows)
 def test_old_fixture_pass_cannot_unlock_new_kernel(self):
  for key,value in [('fixed_shape_candidate',False),('fixtures',10),('passed',False)]:
   rows=self.rows();rows[0][key]=value
   with self.assertRaises(ValueError):self.check(rows)
 def test_01818_gain_does_not_unlock_live(self):
  rows=self.rows()
  for row,t in zip(rows[1:5],[1.24218,1.22003,1.22010,1.24230]):row['combined_compute_filter_ms']=t
  rows[-1]['speed_ratio']=(1.24218+1.24230)/(1.22003+1.22010)
  with self.assertRaises(ValueError):self.check(rows)
 def test_unchecked_interior_vectors_stay_within_each_full_tile(self):
  for row0 in(0,7872):
   for col0 in(0,7936):
    for tid in range(384):
     for v in range(tid,448*4,384):
      row,part=divmod(v,4);a=row<192;global_row=row0+row if a else col0+row-192
      self.assertTrue(0<=global_row<(8064 if a else 8192))
      for kk in(0,4032):self.assertTrue(0<=kk+part*16 and kk+part*16+16<=4096)
if __name__=='__main__':unittest.main()
