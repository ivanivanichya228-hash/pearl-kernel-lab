"""Independent staged-load CPU model, not a CUDA correctness/performance claim."""
import numpy as np
rng = np.random.default_rng(45)
for pn, rank, k in ((8, 32, 544), (16, 32, 544), (8, 128, 2176), (16, 128, 2176), (8,256,4352), (16,256,4352)):
    m, n = 208, 272
    a = rng.integers(-128, 128, (m, k), dtype=np.int16).astype(np.int32)
    b = rng.integers(-128, 128, (n, k), dtype=np.int16).astype(np.int32)
    expected_c = np.zeros((m, n), dtype=np.int32)
    expected_h = np.zeros((m // 16, n // pn, 16), dtype=np.uint32)
    for cp in range(k // rank):
        off = cp * rank
        expected_c += a[:, off:off+rank] @ b[:, off:off+rank].T
        x = expected_c.reshape(m//16,16,n//pn,pn).astype(np.uint32)
        x = np.bitwise_xor.reduce(np.bitwise_xor.reduce(x,axis=3),axis=1)
        h = expected_h[:,:,cp%16]
        expected_h[:,:,cp%16] = ((h << 13) | (h >> 19)) ^ x
    actual_c = np.zeros_like(expected_c)
    actual_h = np.zeros_like(expected_h)
    for row0 in range(0, m, 192):
        for col0 in range(0, n, 256):
            c = np.zeros((192,256),dtype=np.int32)
            history = np.zeros((12,256//pn,16),dtype=np.uint32)
            buffers = [None, None]
            def load(kk):
                stage = np.zeros((448,80),dtype=np.int32)
                # Exactly the 16-byte vector ownership/validity used by cp.async.
                writers = np.zeros((448,64),dtype=np.uint8)
                for tid in range(384):
                    for v in range(tid,448*4,384):
                        row,half = v//4,(v%4)*16
                        src,global_row = (a,row0+row) if row<192 else (b,col0+row-192)
                        if global_row<len(src) and kk+half<k:
                            stage[row,half:half+16] = src[global_row,kk+half:kk+half+16]
                        writers[row,half:half+16] += 1
                assert np.all(writers==1)
                return stage
            buffers[0] = load(0)
            for kk in range(0,k,64):
                which = (kk//64)%2
                if kk+64<k: buffers[1-which] = load(kk+64)
                stage = buffers[which]
                for sub in (0,32):
                    if kk+sub>=k: break
                    c += stage[:192,sub:sub+32] @ stage[192:,sub:sub+32].T
                    if (kk+sub+32)%rank==0:
                        slot = ((kk+sub+32)//rank-1)%16
                        x = c.reshape(12,16,256//pn,pn).astype(np.uint32)
                        x = np.bitwise_xor.reduce(np.bitwise_xor.reduce(x,axis=3),axis=1)
                        h = history[:,:,slot]
                        history[:,:,slot] = ((h<<13)|(h>>19)) ^ x
            rows,cols = min(192,m-row0),min(256,n-col0)
            actual_c[row0:row0+rows,col0:col0+cols] = c[:rows,:cols]
            actual_h[row0//16:(row0+rows)//16,col0//pn:(col0+cols)//pn] = history[:rows//16,:cols//pn]
    assert np.array_equal(actual_c,expected_c)
    assert np.array_equal(actual_h,expected_h)
# Independent m16n8k32 register ownership for the new 3x4 warp grid.
for pn in (8,16):
    cells=set(); proofs=set()
    for warp in range(12):
        wr,wc=warp//4*64,warp%4*64
        for im in range(4):
            for j in range(8):
                for lane in range(32):
                    for q in range(4):
                        pos=(wr+im*16+lane//4+(8 if q>=2 else 0),wc+j*8+lane%4*2+(q&1))
                        assert pos not in cells; cells.add(pos)
            for j in range(8//(pn//8)):
                pos=(wr//16+im,wc//pn+j)
                assert pos not in proofs; proofs.add(pos)
    assert len(cells)==192*256 and len(proofs)==12*(256//pn)
for sub in (0,32):
    banks=[(((lane//4)*80+(lane%4)*4+sub)//4)%32 for lane in range(32)]
    assert len(set(banks))==32
# Exact input-request arithmetic for an8192 slab; excludes cache/DRAM effects.
old_blocks=((8192+127)//128)*((8192+319)//320)
new_blocks=((8192+191)//192)*((8192+255)//256)
old_loads=((8192+127)//128+(8192+319)//320)*8192*4096
new_loads=((8192+191)//192+(8192+255)//256)*8192*4096
assert old_blocks==1664 and new_blocks==1376 and new_loads*6==old_loads*5
print('wide384 CPU model passed: full matrix/transcript, edge tiles, rank32/128/256, proof8/16, partial K/rolling slots, 3x4 warp ownership and conflict-free load banks')
