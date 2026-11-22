import importlib.util,json,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'release/pearl_test.py';spec=importlib.util.spec_from_file_location('singlepass_release',p);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class Gate(unittest.TestCase):
 def rows(self,times=(11,9,9,11)):
  return [dict(phase='fused_correctness',passed=True,fixtures=10,singlepass_candidate=True),*[dict(phase='fused_benchmark',leg=i,fused=i in(1,2),combined_compute_filter_ms=t)for i,t in enumerate(times)],dict(phase='fused_comparison',baseline='original-fused-triple384',candidate='singlepass-fused-triple384',speed_ratio=(times[0]+times[3])/(times[1]+times[2]))]
 def call(self,rows):return r.validate_singlepass_gate('\n'.join(map(json.dumps,rows)))
 def test_pass_recomputes_actual_leg_ratio(self):self.assertAlmostEqual(self.call(self.rows())['ratio'],11/9)
 def test_reject_regression_or_mixed_fast_slow_legs(self):
  for times in[(10,11,11,10),(10,9,11,14),(10,9.9,9.9,10)]:
   with self.assertRaises(ValueError):self.call(self.rows(times))
 def test_missing_new_path_or_wrong_control_rejected(self):
  for key,value in [('singlepass_candidate',False),('fixtures',6),('passed',False)]:
   rows=self.rows();rows[0][key]=value
   with self.assertRaises(ValueError):self.call(rows)
  rows=self.rows();rows[-1]['baseline']='triple384+filter'
  with self.assertRaises(ValueError):self.call(rows)
 def test_incomplete_nan_or_claimed_speed_without_evidence_rejected(self):
  for modify in ('missing','nan','fake'):
   rows=self.rows()
   if modify=='missing':rows.pop(1)
   elif modify=='nan':rows[1]['combined_compute_filter_ms']=float('nan')
   else:rows[-1]['speed_ratio']=10
   with self.assertRaises(ValueError):self.call(rows)
if __name__=='__main__':unittest.main()
