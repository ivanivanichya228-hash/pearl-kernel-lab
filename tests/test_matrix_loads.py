"""CPU model of documented ldmatrix register distribution, not a GPU test."""
import json
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from test_4090_mint import validate_memcheck, validation_budget


def ldmatrix(stage, addresses, count):
    # Matrix j is supplied by lanes 8*j..8*j+7. Four receiving lanes
    # hold adjacent 32-bit fragments of each sixteen-byte source row.
    result = np.empty((32, count, 4), dtype=np.uint8)
    for matrix in range(count):
        for lane in range(32):
            row, column = addresses[matrix * 8 + lane // 4]
            result[lane, matrix] = stage[row, column + (lane % 4) * 4:
                                                    column + (lane % 4) * 4 + 4]
    return result


class MatrixLoads(unittest.TestCase):
    def test_all_fragment_bytes_match_scalar_and_mma(self):
        rng = np.random.default_rng(91043)
        stage = rng.integers(0, 256, (448, 80), dtype=np.uint8)
        for sub in (0, 32):
            for warp in range(12):
                wr, wc = warp // 4 * 64, 192 + warp % 4 * 64
                for im in range(4):
                    ar = wr + im * 16
                    addresses = [(ar + (lane & 15), sub + (lane >> 4) * 16)
                                 for lane in range(32)]
                    self.assertTrue(all(column % 16 == 0 for _, column in addresses))
                    af = ldmatrix(stage, addresses, 4)
                    for lane in range(32):
                        r, c = ar + lane // 4, sub + lane % 4 * 4
                        expected = np.stack([stage[r,c:c+4], stage[r+8,c:c+4],
                                             stage[r,c+16:c+20], stage[r+8,c+16:c+20]])
                        np.testing.assert_array_equal(af[lane], expected)
                    for j in range(8):
                        br = wc + j * 8
                        bf = ldmatrix(stage, [(br + (lane & 7),
                                              sub + ((lane >> 3) & 1) * 16)
                                             for lane in range(32)], 2)
                        # Reconstruct the complete operands exclusively from
                        # loaded lane registers, then check signed INT8 MMA.
                        a = np.empty((16, 32), dtype=np.uint8)
                        b = np.empty((8, 32), dtype=np.uint8)
                        for lane in range(32):
                            r, c = lane // 4, lane % 4 * 4
                            a[r,c:c+4], a[r+8,c:c+4] = af[lane,0], af[lane,1]
                            a[r,c+16:c+20], a[r+8,c+16:c+20] = af[lane,2], af[lane,3]
                            b[r,c:c+4], b[r,c+16:c+20] = bf[lane,0], bf[lane,1]
                        np.testing.assert_array_equal(a, stage[ar:ar+16,sub:sub+32])
                        np.testing.assert_array_equal(b, stage[br:br+8,sub:sub+32])
                        actual = a.view(np.int8).astype(np.int32) @ b.view(np.int8).astype(np.int32).T
                        expected = stage[ar:ar+16,sub:sub+32].view(np.int8).astype(np.int32) @ stage[br:br+8,sub:sub+32].view(np.int8).astype(np.int32).T
                        np.testing.assert_array_equal(actual, expected)

    def test_short_compare_budget(self):
        self.assertEqual(validation_budget(1, .25, 1, 20, 'matrix-compare', False), 5)
        for params in ((2,.25,1,20,False), (1,0,1,20,False),
                       (1,.25,1,14,False), (1,.25,1,20,True)):
            d,w,r,t,s = params
            with self.assertRaises(ValueError):
                validation_budget(d,w,r,t,'matrix-compare',s)

    def test_memcheck_rejects_scalar_result_and_missing_leaks(self):
        result = dict(phase='kernel384_correctness', passed=True, fixtures=6,
                      full_matrix_and_transcript=True, non_debug_transcript_checked=True,
                      other_kernels_executed=False, matrix_loads=True)
        summary = '\nERROR SUMMARY: 0 errors\nLEAK SUMMARY: 0 bytes leaked in 0 allocations\n'
        validate_memcheck(json.dumps(result)+summary, 0, 'matrix-check')
        result['matrix_loads'] = False
        with self.assertRaises(ValueError):
            validate_memcheck(json.dumps(result)+summary, 0, 'matrix-check')
        result['matrix_loads'] = True
        with self.assertRaises(ValueError):
            validate_memcheck(json.dumps(result)+'\nERROR SUMMARY: 0 errors', 0, 'matrix-check')


if __name__ == '__main__':
    unittest.main()
