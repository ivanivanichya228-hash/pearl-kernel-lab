"""Check shared-stage reuse, transposition and partial-tile hit indexing."""
import unittest
from collections import Counter


class FusedLayout(unittest.TestCase):
 def test_transpose_preserves_every_word_without_overlapping_live_history(self):
  for pn in (8,16):
   proofs=12*(256//pn)
   history=list(range(proofs*16))
   target=[None]*(16*(proofs+1))
   for z,value in enumerate(history):target[(z&15)*(proofs+1)+z//16]=value
   for proof in range(proofs):
    self.assertEqual([target[j*(proofs+1)+proof] for j in range(16)],history[proof*16:(proof+1)*16])
   stage_bytes=(2 if pn==8 else 3)*448*64
   self.assertLessEqual(len(target)*4,stage_bytes)

 def test_hash_read_banks_are_unique_for_every_warp(self):
  for proofs in (192,384):
   for j in range(16):
    for first in range(0,proofs,32):
     self.assertEqual(len({(j*(proofs+1)+p)%32 for p in range(first,min(first+32,proofs))}),32)
   for first in range(0,proofs*16,32):
    banks=Counter(((z&15)*(proofs+1)+z//16)%32 for z in range(first,first+32))
    self.assertLessEqual(max(banks.values()),2)

 def test_partial_tiles_and_slab_offsets_have_no_missing_or_duplicate_groups(self):
  for pn in (8,16):
   for m,n in ((16,32),(144,272),(384,512),(400,528)):
    got=[]
    for row0 in range(0,m,192):
     for col0 in range(0,n,256):
      for proof in range(12*(256//pn)):
       row=row0//16+proof//(256//pn);col=col0//pn+proof%(256//pn)
       if row<m//16 and col<n//pn:
        got.append((2+row)*((n+64)//pn)+32//pn+col)
    expected=[(2+r)*((n+64)//pn)+32//pn+c for r in range(m//16) for c in range(n//pn)]
    self.assertEqual(sorted(got),expected)

if __name__=='__main__':unittest.main()
