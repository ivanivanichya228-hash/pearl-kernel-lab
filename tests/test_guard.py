"""CPU-only tests; no GPU/SMI command is executed."""
import importlib.util,unittest
from pathlib import Path
from decimal import Decimal
spec=importlib.util.spec_from_file_location('guard',Path(__file__).parents[1]/'tools/test_4090_mint.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
class Guard(unittest.TestCase):
    def test_4090(self):
        self.assertEqual(guard.parse_board('GPU-abcd, NVIDIA GeForce RTX 4090, 310.00')[2],Decimal(310))
    def test_other_gpu_rejected(self):
        with self.assertRaises(ValueError):guard.parse_board('GPU-abcd, NVIDIA GeForce RTX 3060, 100.00')
    def test_multiple_gpus_rejected(self):
        with self.assertRaises(ValueError):guard.parse_board('GPU-a, RTX 4090, 300\nGPU-b, RTX 4090, 310')
    def test_unknown_power_rejected(self):
        for value in ('NaN','Infinity','0','-1','2001','N/A'):
            with self.assertRaises(ValueError):guard.parse_board('GPU-a, RTX 4090, '+value)
if __name__=='__main__':unittest.main()
