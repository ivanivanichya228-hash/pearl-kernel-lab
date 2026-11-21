import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from test_4090_mint import validation_budget,validate_memcheck

def schedule(total,depth):
 pending=[];ready=set();retired=set();slots=[None]*depth
 def issue(g):
  old=slots[g%depth]
  assert old is None or old in retired,'overwrite before CTA read barrier'
  slots[g%depth]=g;pending.append(g)
 def wait(n):
  while len(pending)>n:ready.add(pending.pop(0))
 for g in range(min(depth-1,total)):issue(g)
 wait(min(depth-2,total-1))
 for current in range(total):
  if current+depth-1<total:issue(current+depth-1)
  assert current in ready and slots[current%depth]==current,'read before copy completion'
  retired.add(current)
  wait(1 if depth==3 and current+2<total else 0)
 assert not pending and len(retired)==total
class TripleGuard(unittest.TestCase):
 def rows(self):
  rows=[dict(phase='triple_stage_resources',triple_stage=True,matrix_loads=False,proof_n=p,pipeline_stages=3 if p==16 else 2,registers=168,local_bytes=0,active_blocks=1) for p in (8,16)]
  rows.append(dict(phase='triple_stage_correctness',triple_stage=True,matrix_loads=False,passed=True,fixtures=6,full_matrix_and_transcript=True,non_debug_transcript_checked=True,other_kernels_executed=False));return rows
 def text(self,rows):return '\n'.join(json.dumps(r) for r in rows)+'\nERROR SUMMARY: 0 errors\nLEAK SUMMARY: 0 bytes leaked in 0 allocations\n'
 def test_async_schedule_all_short_tails(self):
  for depth in (2,3):
   for total in range(1,70):schedule(total,depth)
 def test_correctness_resources_and_depths(self):validate_memcheck(self.text(self.rows()),0,'triple-check')
 def test_refuse_incomplete_or_wrong_depth_results(self):
  for change in ('missing','depth','spills','registers'):
   rows=self.rows()
   if change=='missing':rows.pop(0)
   if change=='depth':rows[1]['pipeline_stages']=2
   if change=='spills':rows[0]['local_bytes']=4
   if change=='registers':rows[0]['registers']=169
   with self.assertRaises(ValueError):validate_memcheck(self.text(rows),0,'triple-check')
 def test_comparison_bounds(self):
  self.assertEqual(validation_budget(1,.25,1,20,'triple-compare',False),5)
  for d,w,r,t,s in [(2,.25,1,20,False),(1,0,1,20,False),(1,.25,1,14,False),(1,.25,1,20,True)]:
   with self.assertRaises(ValueError):validation_budget(d,w,r,t,'triple-compare',s)
if __name__=='__main__':unittest.main()
