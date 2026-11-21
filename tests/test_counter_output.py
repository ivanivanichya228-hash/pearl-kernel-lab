import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from diagnose_compute import counter_summary
class CounterOutput(unittest.TestCase):
 def fixture(self):
  r=dict(phase='counter_targets_completed',kernel_threads=384,matrix_loads=False,warm_matching_launches=6,profile_matching_launches=2,timings_valid=False,pool_connected=False,shares_sent=0)
  lines=[json.dumps(r),'"ID","Kernel Name","Metric Name","Metric Value"']
  for i,k in enumerate(('pearl_int8<384>','compact_filter_kernel')):
   for m,v in [('gpu__time_duration.sum','4123456'),('sm__throughput.avg.pct_of_peak_sustained_elapsed','35.25')]:lines.append(f'"{i}","{k}","{m}","{v}"')
  return '\n'.join(lines)
 def test_actual_metrics_and_completion_required(self):self.assertEqual(len(counter_summary(self.fixture())['kernel_names']),2)
 def test_reject_partial_invalid_or_error_results(self):
  for text in (self.fixture().split('\n',1)[1],self.fixture().replace('4123456','N/A'),self.fixture().replace('35.25','nan'),self.fixture()+'\n==ERROR== failed',self.fixture().replace('compact_filter_kernel','unrelated_kernel')):
   with self.assertRaises(ValueError):counter_summary(text)
if __name__=='__main__':unittest.main()
