import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('memguard',Path(__file__).resolve().parents[1]/'tools/test_4090_mint.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class EvidenceTests(unittest.TestCase):
 def test_only_actual_correctness_and_clean_summary_pass(self):
  g.validate_memcheck('{"phase":"correctness","passed":true,"non_debug_transcript_checked":true}\n========= ERROR SUMMARY: 0 errors\n',0)
 def test_zero_exit_without_validation_is_not_success(self):
  for text in ('',"========= Error: couldn't find exit code.", '========= ERROR SUMMARY: 0 errors'):
   with self.assertRaises(ValueError):g.validate_memcheck(text,0)
 def test_failure_or_error_line_overrides_other_pass_markers(self):
  good='{"phase":"correctness","passed":true,"non_debug_transcript_checked":true}\nERROR SUMMARY: 0 errors\n'
  with self.assertRaises(ValueError):g.validate_memcheck(good,255)
  with self.assertRaises(ValueError):g.validate_memcheck(good+'========= Error: launcher failed',0)

class FilterEvidenceTests(unittest.TestCase):
 def test_filter_requires_its_own_completed_checks(self):
  good='{"phase":"hash_filter_correctness","passed":true,"official_vectors":195,"uniform_context_passed":true,"capacity_edges_passed":true}\nERROR SUMMARY: 0 errors\n'
  g.validate_memcheck(good,0,'filter-check')
  with self.assertRaises(ValueError):g.validate_memcheck(good.replace('195','194'),0,'filter-check')
  with self.assertRaises(ValueError):g.validate_memcheck(good,0,'check')

class NoiseEvidenceTests(unittest.TestCase):
 def test_requires_full_byte_comparison(self):
  import json
  good={'phase':'noise_correctness','passed':True,'all_A_B_bytes_checked':True,'matrix_bytes':131072,'rank':128}
  g.validate_memcheck(json.dumps(good)+'\nERROR SUMMARY: 0 errors',0,'noise-check')
  for changed in ({'all_A_B_bytes_checked':False},{'passed':False},{'matrix_bytes':0},{'rank':1}):
   with self.assertRaises(ValueError):g.validate_memcheck(json.dumps({**good,**changed})+'\nERROR SUMMARY: 0 errors',0,'noise-check')
 def test_noise_sanitizer_allowed_with_budget(self):
  self.assertEqual(g.validation_budget(2,0,1,60,'noise-check',True),0)

class CompactEvidenceTests(unittest.TestCase):
 def test_requires_new_path_and_clean_leaks(self):
  import json
  good={'phase':'compact_filter_correctness','passed':True,'official_vectors':195,'capacity_cases':8,'append_and_transcript_retention':True,'exact_target_passed':True,'empty_preserves_count':True}
  suffix='\nERROR SUMMARY: 0 errors\nLEAK SUMMARY: 0 bytes leaked in 0 allocations\n'
  g.validate_memcheck(json.dumps(good)+suffix,0,'compact-check')
  for change in ({'capacity_cases':7},{'append_and_transcript_retention':False},{'exact_target_passed':False}):
   with self.assertRaises(ValueError):g.validate_memcheck(json.dumps({**good,**change})+suffix,0,'compact-check')
  for suffix_bad in ('\nERROR SUMMARY: 0 errors',suffix.replace('0 bytes','4 bytes'),suffix+'LEAK SUMMARY: 4 bytes leaked in 1 allocations'):
   with self.assertRaises(ValueError):g.validate_memcheck(json.dumps(good)+suffix_bad,0,'compact-check')
 def test_new_mode_budget_allowed(self):self.assertEqual(g.validation_budget(2,0,1,20,'compact-check',True),0)

class Kernel384EvidenceTests(unittest.TestCase):
 def test_requires_new_matrix_and_checkpoint_result(self):
  import json
  good={'phase':'kernel384_correctness','passed':True,'fixtures':6,'full_matrix_and_transcript':True,'non_debug_transcript_checked':True,'other_kernels_executed':False}
  suffix='\nERROR SUMMARY: 0 errors\nLEAK SUMMARY: 0 bytes leaked in 0 allocations'
  g.validate_memcheck(json.dumps(good)+suffix,0,'kernel384-check')
  for change in ({'fixtures':5},{'full_matrix_and_transcript':False},{'non_debug_transcript_checked':False},{'other_kernels_executed':True}):
   with self.assertRaises(ValueError):g.validate_memcheck(json.dumps({**good,**change})+suffix,0,'kernel384-check')
  with self.assertRaises(ValueError):g.validate_memcheck(json.dumps(good)+'\nERROR SUMMARY: 0 errors',0,'kernel384-check')
 def test_exact_short_comparison_budget(self):
  self.assertEqual(g.validation_budget(1,.25,1,20,'kernel384-compare',False),5)
  for duration,warmup,rounds in ((2,.25,1),(1,0,1),(1,.25,2)):
   with self.assertRaises(ValueError):g.validation_budget(duration,warmup,rounds,30,'kernel384-compare',False)
 def test_comparison_must_not_run_under_sanitizer(self):
  with self.assertRaises(ValueError):g.validation_budget(1,.25,1,20,'kernel384-compare',True)
