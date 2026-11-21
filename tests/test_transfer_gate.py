import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from compare_transfer import live_decision

def legs(a,b,overlap_ms=50):return [{'mode':mode,'timed_pair_wall_seconds':seconds,'timed_H2D_phase_ms':100,'timed_H2D_compute_stream_intersection_ms':overlap_ms} for mode,seconds in [('control',a),('overlap',b),('overlap',b),('control',a)]]
class TransferGate(unittest.TestCase):
 def test_real_gain_and_material_overlap_required(self):self.assertTrue(live_decision(legs(4,3),True)[1])
 def test_slow_or_tiny_overlap_rejected(self):
  self.assertFalse(live_decision(legs(4,4.1),True)[1]);self.assertFalse(live_decision(legs(4,3,0.01),True)[1]);self.assertFalse(live_decision(legs(4,3,9),True)[1])
 def test_cpu_mock_never_authorizes_live(self):self.assertFalse(live_decision(legs(4,1),False)[1])
