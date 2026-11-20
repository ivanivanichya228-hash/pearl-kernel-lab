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
