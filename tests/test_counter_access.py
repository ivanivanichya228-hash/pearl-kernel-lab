import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from counter_access import PERFMON,CAP_FIELDS,inspect_access
class CounterAccess(unittest.TestCase):
 def fixture(self):return '\n'.join(f'{k}:\t{PERFMON:016x}' for k in CAP_FIELDS)+'\nNoNewPrivs:\t1\n'
 def aux(self,secure=0):return struct.pack('=QQQQ',23,secure,0,0)
 def test_exact_transient_scope(self):self.assertTrue(inspect_access(self.fixture(),self.aux(),1000,595)['ambient_perfmon_scope_valid'])
 def test_root_wrong_user_old_or_unknown_driver(self):
  for uid,version in [(0,595),(1001,595),(1000,564),(1000,None)]:self.assertFalse(inspect_access(self.fixture(),self.aux(),uid,version)['ambient_perfmon_scope_valid'])
 def test_secure_exec_or_no_new_privileges_missing(self):
  self.assertFalse(inspect_access(self.fixture(),self.aux(1),1000,595)['ambient_perfmon_scope_valid'])
  self.assertFalse(inspect_access(self.fixture().replace('NoNewPrivs:\t1','NoNewPrivs:\t0'),self.aux(),1000,595)['ambient_perfmon_scope_valid'])
 def test_extra_missing_or_dropped_capabilities(self):
  for field in CAP_FIELDS:
   for caps in (0,PERFMON|(1<<21)):
    text=self.fixture().replace(f'{field}:\t{PERFMON:016x}',f'{field}:\t{caps:016x}')
    self.assertFalse(inspect_access(text,self.aux(),1000,595)['ambient_perfmon_scope_valid'])
 def test_auxv_must_have_secure_record_and_terminator(self):
  for aux in (struct.pack('=QQ',0,0),struct.pack('=QQ',23,0),b''):
   self.assertFalse(inspect_access(self.fixture(),aux,1000,595)['ambient_perfmon_scope_valid'])
  with self.assertRaises(ValueError):inspect_access(self.fixture(),b'x',1000,595)
if __name__=='__main__':unittest.main()
