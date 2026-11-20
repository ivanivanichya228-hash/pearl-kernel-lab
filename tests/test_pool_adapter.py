import importlib.util,json,sys,unittest
from pathlib import Path
from dataclasses import replace
root=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('pool_adapter',root/'tools/luckypool_adapter.py');a=importlib.util.module_from_spec(s);sys.modules[s.name]=a;s.loader.exec_module(a)
class AdapterTests(unittest.TestCase):
 def setUp(self):
  self.raw=json.loads((root/'pool/captured-notify.json').read_text());self.job=a.Job.parse(self.raw)
  self.config=json.loads((root/'pool/client-reference.json').read_text());self.profile=a.Profile.parse(self.config)
 def test_header_and_rank_factor(self):
  self.assertEqual(self.job.describe()['block_nbits'],'1743e183');self.assertEqual(self.job.describe()['timestamp'],1795126315)
  self.assertEqual(self.profile.factor(),524288)
 def test_exact_target_boundary_and_endianness(self):
  bound=self.profile.bound(self.job)
  self.assertTrue(self.profile.qualifies(self.job,bound.to_bytes(32,'little')))
  self.assertFalse(self.profile.qualifies(self.job,(bound+1).to_bytes(32,'little')))
  self.assertFalse(self.profile.qualifies(self.job,bound.to_bytes(32,'big')))
 def test_no_saturating_impossible_targets(self):
  with self.assertRaises(ValueError):self.profile.bound(replace(self.job,target=a.MAX256))
 def test_target_or_header_update_invalidates_candidate(self):
  book=a.JobBook();book.update(self.job)
  for changed in (replace(self.job,target=self.job.target+1),replace(self.job,job_id='new-job'),replace(self.job,header=bytes(76))):
   book.update(changed)
   with self.assertRaises(ValueError):book.require_current(self.job)
 def test_missing_or_unsupported_parameters_refused(self):
  for update in ({'rank':0},{'rank':192},{'k':4160},{'mma_type':False},{'row_pattern':[0,0]},{'m':0}):
   with self.assertRaises(ValueError):a.Profile.parse({**self.config,**update})
 def test_malformed_jobs_refused(self):
  for update in ({'header':'ab'},{'target':'0'*64},{'cert_version':True},{'job_id':'x\ny'},{'target':'z'*64}):
   with self.assertRaises(ValueError):a.Job.parse({**self.raw,'params':{**self.raw['params'],**update}})
