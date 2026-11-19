#!/usr/bin/env python3
"""Independent NumPy oracle. CPU only. Writes bounded arithmetic fixtures."""
from pathlib import Path
import hashlib, json, struct
import numpy as np

root = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
root.mkdir(exist_ok=True)
rng = np.random.default_rng(20261119)
cases = [(16,16,32,32,8,"zero"), (16,16,2176,128,16,"negative_spike"),
         (32,48,4096,128,8,"random"), (160,400,512,128,16,"random"),
         (32,48,2048,256,16,"random"), (16,16,65536,1024,16,"extreme")]
manifest = []
for number,(m,n,k,rank,pn,kind) in enumerate(cases):
    a = rng.integers(-64,65,(m,k),dtype=np.int8)
    b = rng.integers(-64,65,(n,k),dtype=np.int8)
    if kind == "zero": a.fill(0)
    if kind == "negative_spike":
        a.fill(0); b.fill(0); a[0,:] = -1; b[0,:] = 1
    if kind == "extreme": a.fill(-128); b.fill(-128)
    c = np.zeros((m,n),dtype=np.int64)
    history = np.zeros((m//16,n//pn,16),dtype=np.uint32)
    for cp,q in enumerate(range(0,k,rank)):
        c += a[:,q:q+rank].astype(np.int64) @ b[:,q:q+rank].astype(np.int64).T
        tiles = (c & 0xffffffff).astype(np.uint32).reshape(m//16,16,n//pn,pn)
        x = np.bitwise_xor.reduce(np.bitwise_xor.reduce(tiles,axis=3),axis=1)
        slot = cp % 16
        old = history[:,:,slot]
        history[:,:,slot] = ((old << np.uint32(13)) | (old >> np.uint32(19))) ^ x
    assert np.all(c >= -(2**31)) and np.all(c < 2**31)
    file = root / f"case-{number}.bin"
    file.write_bytes(b"PRLFX001" + struct.pack("<5I",m,n,k,rank,pn) +
                     a.tobytes() + b.tobytes() + c.astype("<i4").tobytes() +
                     history.astype("<u4").tobytes())
    manifest.append(dict(file=file.name,shape=[m,n,k,rank,pn],kind=kind,
                         sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
(root/"manifest.json").write_text(json.dumps(manifest,indent=2))
print(f"Generated {len(cases)} CPU golden fixtures")
