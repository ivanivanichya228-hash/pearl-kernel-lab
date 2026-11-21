import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from test_4090_mint import validation_budget,validate_memcheck
class TwoCTAGuard(unittest.TestCase):
 def output(self):
  rows=[dict(phase='two_cta_resources',two_cta=True,matrix_loads=False,proof_n=p,registers=107,local_bytes=0,active_blocks=2) for p in (8,16)]
  rows.append(dict(phase='two_cta_correctness',two_cta=True,matrix_loads=False,passed=True,fixtures=6,full_matrix_and_transcript=True,non_debug_transcript_checked=True,other_kernels_executed=False))
  return rows
 def text(self,rows):return '\n'.join(json.dumps(r) for r in rows)+'\nERROR SUMMARY: 0 errors\nLEAK SUMMARY: 0 bytes leaked in 0 allocations\n'
 def test_full_correctness_and_two_resident_blocks_required(self):validate_memcheck(self.text(self.output()),0,'two-cta-check')
 def test_reject_missing_resources_or_insufficient_occupancy(self):
  for change in ('missing','one_block','spill','registers','wrong_geometry'):
   rows=self.output()
   if change=='missing':rows.pop(0)
   if change=='one_block':rows[0]['active_blocks']=1
   if change=='spill':rows[0]['local_bytes']=4
   if change=='registers':rows[0]['registers']=129
   if change=='wrong_geometry':rows[-1]['two_cta']=False
   with self.assertRaises(ValueError,msg=change):validate_memcheck(self.text(rows),0,'two-cta-check')
 def test_comparison_budget_is_fixed(self):
  self.assertEqual(validation_budget(1,.25,1,20,'two-cta-compare',False),5)
  for d,w,r,t,s in [(2,.25,1,20,False),(1,0,1,20,False),(1,.25,1,14,False),(1,.25,1,20,True)]:
   with self.assertRaises(ValueError):validation_budget(d,w,r,t,'two-cta-compare',s)
if __name__=='__main__':unittest.main()
