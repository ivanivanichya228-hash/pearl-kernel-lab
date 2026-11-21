import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from counter_scope_probe import trusted_file,probe
class ScopeProbe(unittest.TestCase):
 def test_refuses_a_writable_path_even_when_file_readonly(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'inert';p.write_text('not executable');p.chmod(0o444)
   with self.assertRaises(ValueError):trusted_file(p)
 def test_refuses_missing_ambient_scope_before_any_subprocess(self):
  with patch('counter_scope_probe.current_access',return_value={'ambient_perfmon_scope_valid':False}),patch('counter_scope_probe.subprocess.run') as run:
   with self.assertRaises(ValueError):probe(Path('/ncu'),Path('/engine'),'x','y')
   run.assert_not_called()
 def test_refuses_injected_environment_before_exec(self):
  with patch('counter_scope_probe.current_access',return_value={'ambient_perfmon_scope_valid':True}),patch.dict(os.environ,{'LD_PRELOAD':'untrusted'}),patch('counter_scope_probe.subprocess.run') as run:
   with self.assertRaises(ValueError):probe(Path('/ncu'),Path('/engine'),'x','y')
   run.assert_not_called()
if __name__=='__main__':unittest.main()
