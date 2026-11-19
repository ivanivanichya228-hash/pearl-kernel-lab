"""CPU model: compact warp ownership, edges, and lane-resident rolling slots.
This checks indexing/contract, not CUDA execution or performance.
"""
import numpy as np
rng = np.random.default_rng(20261119)
for pn in (8, 16):
    m, n, k, rank = 80, 144, 2176, 128
    a = rng.integers(-128, 128, (m, k), dtype=np.int16).astype(np.int32)
    bt = rng.integers(-128, 128, (n, k), dtype=np.int16).astype(np.int32)
    c = np.zeros((128, 256), dtype=np.int32)
    expected = np.zeros((m // 16, n // pn, 16), dtype=np.uint32)
    # Each warp owns 32x64 cells; each lane <16 owns one rolling slot.
    history = np.zeros((2, 2, 4, 2, 8 // (pn // 8), 16), dtype=np.uint32)
    owners = np.zeros((m, n), dtype=np.int32)
    for cp in range(k // rank):
        lo, hi = cp * rank, (cp + 1) * rank
        c[:m, :n] += a[:, lo:hi] @ bt[:, lo:hi].T
        slot = cp % 16
        x = c[:m, :n].reshape(m // 16, 16, n // pn, pn).astype(np.uint32)
        x = np.bitwise_xor.reduce(np.bitwise_xor.reduce(x, axis=3), axis=1)
        old = expected[:, :, slot]
        expected[:, :, slot] = ((old << 13) | (old >> 19)) ^ x
        for by in range(2):
            for bx in range(2):
                for warp in range(4):
                    wr, wc = warp // 2 * 32, warp % 2 * 64
                    for im in range(2):
                        for proof in range(8 // (pn // 8)):
                            value = 0
                            for lane in range(32):
                                for z in range(pn // 8):
                                    for q in range(4):
                                        row = by * 64 + wr + im * 16 + lane // 4 + (8 if q >= 2 else 0)
                                        col = bx * 128 + wc + (proof * (pn // 8) + z) * 8 + lane % 4 * 2 + (q & 1)
                                        value ^= int(c[row, col]) & 0xffffffff
                                        if cp == 0 and row < m and col < n:
                                            owners[row, col] += 1
                            h = int(history[by, bx, warp, im, proof, slot])
                            history[by, bx, warp, im, proof, slot] = (((h << 13) | (h >> 19)) ^ value) & 0xffffffff
    actual = np.zeros_like(expected)
    writers = np.zeros_like(expected)
    for by in range(2):
        for bx in range(2):
            for warp in range(4):
                for im in range(2):
                    for proof in range(8 // (pn // 8)):
                        row = (by * 64 + warp // 2 * 32) // 16 + im
                        col = (bx * 128 + warp % 2 * 64) // pn + proof
                        if row < m // 16 and col < n // pn:
                            actual[row, col] = history[by, bx, warp, im, proof]
                            writers[row, col] += 1
    assert np.all(owners == 1) and np.all(writers == 1)
    assert np.array_equal(actual, expected), pn
print('compact CPU model passed: proof 8/16, signed inputs, edge tiles, 17 checkpoints, unique writers')
