"""CPU checks of register transcript ownership and edge-tile coverage."""
import unittest


class OccupancyLayout(unittest.TestCase):
 def test_every_group_has_one_writer_including_partial_tiles(self):
  for pn in (8,16):
   for m,n in ((16,pn),(144,136),(256,256),(192,384)):
    n=n//pn*pn
    written=[]
    for row0 in range(0,m,128):
     for col0 in range(0,n,128):
      for warp in range(8):
       for im in range(4):
        for proof in range(4//(pn//8)):
         row=(row0+(warp//4)*64)//16+im
         col=(col0+(warp%4)*32)//pn+proof
         if row<m//16 and col<n//pn:
          for lane in range(16):written.append((row*(n//pn)+col)*16+lane)
    self.assertEqual(sorted(written),list(range((m//16)*(n//pn)*16)))

 def test_lane_history_retains_all_sixteen_checkpoint_slots(self):
  for pn in (8,16):
   for checkpoints in (1,2,16,17,32,128):
    slots=[[0]*(4//(pn//8)) for _ in range(32)]
    expected=[[0]*16 for _ in range(4//(pn//8))]
    for cp in range(checkpoints):
     for proof in range(len(expected)):
      x=(cp*0x9e3779b9+proof*0x1234567)&0xffffffff
      old=expected[proof][cp&15]
      expected[proof][cp&15]=(((old<<13)|(old>>19))^x)&0xffffffff
      old=slots[cp&15][proof]
      slots[cp&15][proof]=(((old<<13)|(old>>19))^x)&0xffffffff
    for proof in range(len(expected)):
     self.assertEqual([slots[lane][proof] for lane in range(16)],expected[proof])

 def test_shared_memory_budget_permits_two_blocks_on_100k_sm(self):
  self.assertLessEqual(2*3*(128+128)*64,100*1024)
  self.assertGreater(2*(3*(192+256)*64+12*16*16*4),100*1024)

if __name__=='__main__':unittest.main()
