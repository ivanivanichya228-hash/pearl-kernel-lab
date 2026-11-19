"""CPU model of documented PTX fragment ownership, not GPU execution."""
import numpy as np
rng=np.random.default_rng(77)
a=rng.integers(-128,128,(16,32),dtype=np.int16)
b=rng.integers(-128,128,(8,32),dtype=np.int16)
aa=np.empty_like(a);bb=np.empty_like(b)
seen_a=np.zeros_like(a);seen_b=np.zeros_like(b)
for lane in range(32):
    g,t=lane>>2,lane&3
    for i in range(16):
        row=g+(8 if i in list(range(4,8))+list(range(12,16)) else 0)
        col=t*4+(i&3)+(16 if i>=8 else 0)
        aa[row,col]=a[row,col];seen_a[row,col]+=1
    for i in range(8):
        kk=t*4+(i&3)+(16 if i>=4 else 0)
        bb[g,kk]=b[g,kk];seen_b[g,kk]+=1
assert np.all(seen_a==1) and np.all(seen_b==1)
c=aa.astype(np.int64)@bb.astype(np.int64).T
seen=np.zeros((16,8),dtype=np.int32);lane_x=[]
for lane in range(32):
    g,t=lane>>2,lane&3;x=0
    for q in range(4):
        row=g+(8 if q>=2 else 0);col=t*2+(q&1)
        seen[row,col]+=1;x^=int(c[row,col])&0xffffffff
    lane_x.append(x)
assert np.all(seen==1)
assert np.bitwise_xor.reduce(np.array(lane_x,dtype=np.uint32))==np.bitwise_xor.reduce((c&0xffffffff).astype(np.uint32).ravel())
for threads in (256,512):
    wm=4;wn=threads//32//wm;mi=2;ni=384//wn//8
    for pn in (8,16):
        cells=set();proofs=set()
        for warp in range(threads//32):
            wr,wc=warp//wn*32,warp%wn*ni*8
            for im in range(mi):
                for j in range(ni):
                    for lane in range(32):
                        for q in range(4):
                            p=(wr+im*16+(lane>>2)+(8 if q>=2 else 0),wc+j*8+(lane&3)*2+(q&1))
                            assert p not in cells;cells.add(p)
                for j in range(ni//(pn//8)):
                    p=(wr//16+im,wc//pn+j);assert p not in proofs;proofs.add(p)
        assert len(cells)==128*384 and len(proofs)==128//16*(384//pn)
# Shared packed-word banks: one 4-byte access per lane, row=lane>>2.
banks=[(((lane>>2)*48+(lane&3)*4)//4)%32 for lane in range(32)]
assert len(set(banks))==32
print('PTX fragment, CTA ownership and shared-bank CPU models passed')
