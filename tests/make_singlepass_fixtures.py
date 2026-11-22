"""Independent NumPy prefix oracle; original six fixtures are never overwritten."""
import hashlib,json,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def build():
 rng=np.random.default_rng(620611);records=[]
 for case,(m,n,rank,pn) in enumerate([(32,48,256,16),(32,48,128,8),(208,272,32,16),(208,272,32,8)],6):
  k=16*rank;a=rng.integers(-127,128,(m,k),dtype=np.int16).astype(np.int8);b=rng.integers(-127,128,(n,k),dtype=np.int16).astype(np.int8)
  total=np.zeros((m,n),dtype=np.int64);hist=np.zeros((m//16,n//pn,16),dtype=np.uint32)
  for cp in range(16):
   off=cp*rank;total+=a[:,off:off+rank].astype(np.int64)@b[:,off:off+rank].astype(np.int64).T
   tiles=total.astype(np.uint32).reshape(m//16,16,n//pn,pn);x=np.bitwise_xor.reduce(np.bitwise_xor.reduce(tiles,axis=3),axis=1)
   old=hist[:,:,cp];hist[:,:,cp]=((old<<np.uint32(13))|(old>>np.uint32(19)))^x
  assert np.all(total>=-(2**31))and np.all(total<2**31)
  data=b'PRLFX001'+struct.pack('<5I',m,n,k,rank,pn)+a.tobytes()+b.tobytes()+total.astype('<i4').tobytes()+hist.astype('<u4').tobytes()
  path=ROOT/f'tests/fixtures/case-{case}.bin'
  if path.exists() and path.read_bytes()!=data:raise ValueError('Refusing to replace different fixture')
  path.write_bytes(data);records.append({'file':path.name,'shape':[m,n,k,rank,pn],'sha256':hashlib.sha256(data).hexdigest(),'checkpoint_count':16,'independent_oracle':'NumPy cumulative int64 GEMM + original rotating XOR recurrence'})
 (ROOT/'tests/fixtures/singlepass-manifest.json').write_text(json.dumps(records,indent=2)+'\n')
if __name__=='__main__':build()
