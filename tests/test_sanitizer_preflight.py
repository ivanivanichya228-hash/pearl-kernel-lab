"""CPU-only regressions for missing/mismatched sanitizer bundles."""
import importlib.util,struct,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('preflight',Path(__file__).resolve().parents[1]/'tools/sanitizer_preflight.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class PreflightTests(unittest.TestCase):
    def test_wrong_architecture_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'lib.so';p.write_bytes(b'\x7fELF'+bytes((1,1))+bytes(14))
            with self.assertRaises(ValueError):m.check_elf(p)
    def bundle(self,root):
        folder=Path(root);header=bytearray(20);header[:6]=b'\x7fELF\x02\x01';header[18:20]=struct.pack('<H',62)
        for name in ('compute-sanitizer',*m.LIBRARIES):(folder/name).write_bytes(header)
        return folder
    def audit(self,folder,dependency_ok):
        def fake_run(args,**kwargs):
            if '--help' in args:out='injection-path require-cuda-init error-exitcode leak-check'
            elif '--version' in args:out='2022.4.1'
            else:out='libc.so.6 => /lib/libc.so.6' if dependency_ok else 'libmissing.so => not found'
            return subprocess.CompletedProcess(args,0,out,'')
        with patch.object(m.shutil,'which',side_effect=lambda x:str(folder/'compute-sanitizer') if x=='compute-sanitizer' else '/usr/bin/ldd'),patch.object(m,'trusted',side_effect=lambda p:Path(p).resolve(strict=True)),patch.object(m,'owner',return_value='nvidia-cuda-toolkit'),patch.object(m,'candidate_dirs',return_value=[folder]),patch.object(m,'run',side_effect=fake_run):
            return m.prepare()
    def test_complete_bundle_selected_and_missing_dependencies_refused(self):
        with tempfile.TemporaryDirectory() as root:
            folder=self.bundle(root)
            self.assertEqual(self.audit(folder,True)['injection_path'],str(folder))
            with self.assertRaisesRegex(ValueError,'Unresolved'):self.audit(folder,False)
    def test_missing_library_refused_before_probe(self):
        with tempfile.TemporaryDirectory() as root:
            folder=self.bundle(root);(folder/m.LIBRARIES[0]).unlink()
            with self.assertRaisesRegex(ValueError,'No complete'):self.audit(folder,True)
