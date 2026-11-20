import importlib.util,json,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('guard',Path(__file__).resolve().parents[1]/'tools/test_4090_mint.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
FILTER={'phase':'hash_filter_correctness','passed':True,'official_vectors':195,'uniform_context_passed':True,'capacity_edges_passed':True}
PIPE={'phase':'pipeline_correctness','passed':True,'groups':4,'hits':2,'debug_matrix_checked':True,'non_debug_transcript_checked':True,'ordered_stream':True,'network_used':False}
def log(*rows):return '\n'.join(map(json.dumps,rows))+'\n========= ERROR SUMMARY: 0 errors\n'
class PipelineGuard(unittest.TestCase):
 def test_complete(self):g.validate_memcheck(log(FILTER,PIPE),0,'pipeline-check')
 def test_no_filter(self):
  with self.assertRaises(ValueError):g.validate_memcheck(log(PIPE),0,'pipeline-check')
 def test_no_pipeline(self):
  with self.assertRaises(ValueError):g.validate_memcheck(log(FILTER),0,'pipeline-check')
 def test_wrong_counts(self):
  with self.assertRaises(ValueError):g.validate_memcheck(log(FILTER,{**PIPE,'hits':0}),0,'pipeline-check')
 def test_no_ordering(self):
  with self.assertRaises(ValueError):g.validate_memcheck(log(FILTER,{**PIPE,'ordered_stream':False}),0,'pipeline-check')
 def test_budget(self):self.assertEqual(g.validation_budget(2,0,1,50,'pipeline-check',True),0)
if __name__=='__main__':unittest.main()
