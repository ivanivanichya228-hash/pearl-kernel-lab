"""Independent prefix GEMM goldens exercising both the unchecked interior and edge."""
import hashlib,json,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def main():
 rng=np.random.default_rng(2026112205);choices=np.array([-127,-65,-1,0,1,63,64,127],dtype=np.int8);records=[]
 for i,(m,n)in enumerate([(192,256),(208,512)],10):
  k,rank,pn=4096,256,16
  a=choices[rng.integers(0,len(choices),(m,k))];b=choices[rng.integers(0,len(choices),(n,k))]
  total=np.zeros((m,n),dtype=np.int64);history=np.zeros((m//16,n//pn,16),dtype=np.uint32)
  for cp in range(k//rank):
   off=cp*rank;total+=a[:,off:off+rank].astype(np.int64)@b[:,off:off+rank].astype(np.int64).T
   tile=total.astype(np.uint32).reshape(m//16,16,n//pn,pn);x=np.bitwise_xor.reduce(np.bitwise_xor.reduce(tile,axis=3),axis=1)
   old=history[:,:,cp&15];history[:,:,cp&15]=((old<<13)|(old>>19))^x
  assert np.all(total>=-(2**31))and np.all(total<2**31)
  data=b'PRLFX001'+struct.pack('<5I',m,n,k,rank,pn)+a.tobytes()+b.tobytes()+total.astype('<i4').tobytes()+history.astype('<u4').tobytes();path=ROOT/f'tests/fixtures/case-{i}.bin'
  if path.exists()and path.read_bytes()!=data:raise ValueError('Refusing fixture overwrite')
  path.write_bytes(data);records.append({'file':path.name,'shape':[m,n,k,rank,pn],'sha256':hashlib.sha256(data).hexdigest(),'independent_oracle':'NumPy int64 cumulative GEMM + original rotate/XOR; eight signed/extreme input values','interior_m':m//192*192,'edge_m':m%192})
 (ROOT/'tests/fixtures/fixed-shape-manifest.json').write_text(json.dumps(records,indent=2)+'\n')
if __name__=='__main__':main()
