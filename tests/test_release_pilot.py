import contextlib,importlib.util,io,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_pilot',ROOT/'release/pearl_test.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
spec=importlib.util.spec_from_file_location('issue_release_session',ROOT/'release/issue_session.py');issuer=importlib.util.module_from_spec(spec);spec.loader.exec_module(issuer)
class ReleasePilot(unittest.TestCase):
 def config(self):return r.clean_config(dict(host='pearl-eu2.luckypool.io',port=3360,wallet='TEST_ONLY_NOT_A_WALLET',worker='test'),Path('/profile.json'))
 def session(self):return dict(schema='pearl-test-session-v1',original_pid=123,original_start_ticks=456,gpu_uuid=r.GPU,power_limit_w=310,pause_started_monotonic=100,deadline_monotonic=655,cgroup_path='/system.slice/pearl-pilot.service',watchdog_unit='pearl-pilot-watchdog.timer')
 def test_fixed_gpu_profile_and_pool_preserved(self):
  c=self.config();self.assertEqual(c['power_limit_w'],310);self.assertEqual(c['gpu_uuid'],r.GPU);self.assertEqual(c['wallet'],'TEST_ONLY_NOT_A_WALLET');self.assertEqual(c['port'],3360)
 def test_reject_bad_configuration(self):
  for data in [dict(host='https://pool/',port=1,wallet='x',worker='x'),dict(host='pool',port=True,wallet='x',worker='x'),dict(host='pool',port=65536,wallet='x',worker='x'),dict(host='pool',port=3360,wallet='',worker='x'),dict(host='pool',port=3360,wallet='x\ny',worker='x')]:
   with self.assertRaises(ValueError):r.clean_config(data,Path('/profile'))
 def test_private_config_no_overwrite_or_symlink_follow(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'config.json';r.save_private(p,self.config());self.assertEqual(p.stat().st_mode&0o777,0o600);self.assertEqual(r.read_private(p)['port'],3360)
   with self.assertRaises(FileExistsError):r.save_private(p,{})
   link=Path(tmp)/'link';link.symlink_to(p)
   with self.assertRaises(ValueError):r.read_private(link)
   p.chmod(0o644)
   with self.assertRaises(ValueError):r.read_private(p)
 def test_controller_session_valid(self):self.assertEqual(r.validate_session(self.session(),self.config(),110,420,'/system.slice/pearl-pilot.service',True),(123,456))
 def test_reject_wrong_cgroup_watchdog_gpu_and_expiry(self):
  for change in ('cgroup','watchdog','gpu','late','extension','nan'):
   s=self.session();now=110;cg=s['cgroup_path'];active=True
   if change=='cgroup':cg='/user.slice/unrelated.service'
   if change=='watchdog':active=False
   if change=='gpu':s['gpu_uuid']='GPU-other'
   if change=='late':now=640
   if change=='extension':s['deadline_monotonic']=701
   if change=='nan':s['deadline_monotonic']=float('nan')
   with self.assertRaises(ValueError,msg=change):r.validate_session(s,self.config(),now,420,cg,active)
 def test_runner_must_be_unprivileged(self):
  text='\n'.join(k+': 0' for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb'))+'\nNoNewPrivs: 1'
  r.runner_security(text,1000)
  with self.assertRaises(ValueError):r.runner_security(text,0)
  with self.assertRaises(ValueError):r.runner_security(text.replace('CapEff: 0','CapEff: 200000'),1000)
 def test_issuer_requires_root_before_any_file_write(self):
  with patch.object(issuer.os,'geteuid',return_value=1000):
   with self.assertRaises(PermissionError):issuer.issue_session(original_pid=123,original_start_ticks=456,gpu_uuid=r.GPU,power_limit_w=310,pause_started_monotonic=100,deadline_monotonic=655,cgroup_path='/system.slice/pearl-pilot.service',watchdog_unit='pearl-watch.timer')
 def test_status_does_not_invent_srb_hashrate(self):
  text=r.format_status('status',dict(accepted=1,rejected=0,performance={'fresh_finished_candidates_per_second':40_705_831}))
  self.assertIn('40.71',text);self.assertNotIn('TH/s',text);self.assertIn('Принято: 1',text)
if __name__=='__main__':unittest.main()
