"""No GPU or network: reject archive escape and post-extraction tampering."""
import importlib.util,hashlib,io,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('isolated',Path(__file__).resolve().parents[1]/'tools/prepare_sanitizer.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class BundleTests(unittest.TestCase):
 def test_escaping_symlink_refused(self):
  member=tarfile.TarInfo('bundle/bin/tool');member.type=tarfile.SYMTYPE;member.linkname='../../../outside'
  class Archive:
   def getmembers(self):return [member]
  with self.assertRaises(ValueError):m.checked_members(Archive())
 def test_bundle_tamper_refused(self):
  with tempfile.TemporaryDirectory() as d:
   cache=Path(d);archive=cache/'sanitizer.tar.xz'
   with tarfile.open(archive,'w:xz') as tf:
    for name in m.REQUIRED:
     data=b'official test payload';x=tarfile.TarInfo('bundle/compute-sanitizer/'+name);x.size=len(data);x.mode=0o755;tf.addfile(x,io.BytesIO(data))
   lock={**m.LOCK,'size':archive.stat().st_size,'sha256':m.digest(archive)}
   dest=cache/('bundle-'+lock['sha256'][:12]);dest.mkdir()
   with tarfile.open(archive) as tf:tf.extractall(dest,filter='data')
   with patch.object(m,'CACHE',cache),patch.object(m,'LOCK',lock):
    self.assertIn('compute-sanitizer',m.resolve_bundle()['executable'])
    (dest/'bundle/compute-sanitizer/libsanitizer-collection.so').write_text('changed')
    with self.assertRaisesRegex(ValueError,'changed/missing'):m.resolve_bundle()
 def test_wrong_archive_hash_refused(self):
  with tempfile.NamedTemporaryFile() as f:
   f.write(b'not the official archive');f.flush()
   with self.assertRaises(ValueError):m.validate_archive(Path(f.name))
