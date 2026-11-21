import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from diagnose_compute import counter_command,timing_summary

class Diagnostics(unittest.TestCase):
 def records(self):
  rows=[dict(phase='diagnostic_sample',iteration=i,gemm_ms=4.,filter_ms=1.) for i in range(32)]
  rows.append(dict(phase='diagnostic_summary',samples=32,kernel_threads=384,stage_k=64,matrix_loads=False,resident_input_only=True,gemm_total_ms=128.,filter_total_ms=32.,host_wall_ms=165.,includes_CPU_prepare=False,includes_H2D=False,event_instrumented=True,pool_connected=False,shares_sent=0,hashrate_measured=False))
  return rows
 def text(self,rows):return '\n'.join(json.dumps(r) for r in rows)
 def test_phase_accounting_scope(self):
  r=timing_summary(self.text(self.records()));self.assertEqual(r['gemm_fraction'],.8);self.assertEqual(r['filter_fraction'],.2);self.assertFalse(r['real_hashrate_measured']);self.assertFalse(r['cause_of_kernel_stalls_established'])
 def test_reject_partial_or_corrupt_sequence(self):
  for mutation in ('drop','repeat','nan','negative','sum','scope'):
   rows=self.records()
   if mutation=='drop':rows.pop(0)
   if mutation=='repeat':rows[2]['iteration']=1
   if mutation=='nan':rows[0]['gemm_ms']=float('nan')
   if mutation=='negative':rows[0]['filter_ms']=-1
   if mutation=='sum':rows[-1]['gemm_total_ms']=200
   if mutation=='scope':rows[-1]['hashrate_measured']=True
   with self.assertRaises(ValueError,msg=mutation):timing_summary(self.text(rows))
 def test_profiler_limits_and_no_clock_reset(self):
  command=counter_command('/ncu','/bench',12,345,'/new/report')
  for flag,value in (('--clock-control','none'),('--cache-control','none'),('--launch-skip','6'),('--launch-count','2'),('--replay-mode','kernel'),('--mode','kernel-counters'),('--candidate','384')):
   self.assertEqual(command[command.index(flag)+1],value)
  self.assertNotIn('--matrix-loads',command);self.assertNotIn('--transfer-overlap',command);self.assertNotIn('--force-overwrite',command)
 def test_counter_target_filter_is_limited_to_our_kernels(self):
  command=counter_command('/ncu','/bench',12,345,'/new/report');self.assertEqual(command[command.index('--kernel-name')+1],'regex:.*(pearl_int8|compact_filter_kernel).*');self.assertIn('WarpStateStats',command);self.assertIn('MemoryWorkloadAnalysis',command)
if __name__=='__main__':unittest.main()
