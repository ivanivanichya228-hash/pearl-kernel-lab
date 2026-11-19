import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('guard_validation',Path(__file__).resolve().parents[1]/'tools/test_4090_mint.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class BudgetTests(unittest.TestCase):
    def test_allowed_repeated_measurement(self):
        self.assertEqual(g.validation_budget(3,2,2,55,'bench',False),40)
    def test_refuse_excess_or_missing_recovery_margin(self):
        for duration,warmup,rounds,timeout in ((3,2,2,45),(10,5,3,60),(3,2,0,55),(3,float('nan'),2,55),(3,2,2,300)):
            with self.assertRaises(ValueError):g.validation_budget(duration,warmup,rounds,timeout,'bench',False)
    def test_sanitizer_never_benchmarks(self):
        with self.assertRaises(ValueError):g.validation_budget(3,2,2,55,'bench',True)
        self.assertEqual(g.validation_budget(2,0,1,50,'check',True),0)
