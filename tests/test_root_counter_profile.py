import contextlib,hashlib,io,struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from root_counter_profile import SYS_ADMIN,DEPENDENCIES,ROOT,root_scope,parser,trusted_path,new_output
class RootCounterProfile(unittest.TestCase):
 def status(self):return '\n'.join(f'{k}:\t{SYS_ADMIN:016x}' for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb'))+'\nNoNewPrivs:\t1'
 def aux(self,v=0):return struct.pack('=QQQQ',23,v,0,0)
 def test_exact_root_transient_scope(self):self.assertTrue(root_scope(self.status(),self.aux(),0,0)['valid'])
 def test_reject_user_root_group_and_extra_or_missing_caps(self):
  for uid,gid in ((1000,0),(0,1000)):
   self.assertFalse(root_scope(self.status(),self.aux(),uid,gid)['valid'])
  for field in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb'):
   for value in (0,SYS_ADMIN|1):
    text=self.status().replace(f'{field}:\t{SYS_ADMIN:016x}',f'{field}:\t{value:016x}')
    self.assertFalse(root_scope(text,self.aux(),0,0)['valid'])
 def test_secure_or_ambiguous_execution_refused(self):
  self.assertFalse(root_scope(self.status(),self.aux(1),0,0)['valid'])
  self.assertFalse(root_scope(self.status(),b'',0,0)['valid'])
  self.assertFalse(root_scope(self.status().replace('NoNewPrivs:\t1','NoNewPrivs:\t0'),self.aux(),0,0)['valid'])
  with self.assertRaises(ValueError):root_scope(self.status(),b'x',0,0)
 def test_import_closure_hashes_match_pinned_sources(self):
  for name,digest in DEPENDENCIES.items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest)
 def test_no_arbitrary_binary_gpu_or_command_options(self):
  for flag in ('--engine','--ncu','--gpu','--command','--duration'):
   with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):parser().parse_args(['collect','--out','/var/lib/pearl-root-counter-profile/new',flag,'arbitrary'])
 def test_untrusted_path_and_output_location_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'fake';p.write_text('inert');p.chmod(0o444)
   with self.assertRaises(ValueError):trusted_path(p)
   with self.assertRaises(ValueError):new_output(Path(tmp)/'output')
if __name__=='__main__':unittest.main()
