// Original experimental implementation, not derived from SRBMiner disassembly.
#include "kernel.cuh"

namespace pearl_lab {
namespace {
__device__ __forceinline__ uint32_t word(const int8_t* p) {
  return *reinterpret_cast<const uint32_t*>(p);
}
// Each address supplies an aligned 16-byte row of an 8x8 b16 matrix.
// No transpose: BT is already stored with contiguous K bytes per column.
__device__ __forceinline__ void matrix_a(const int8_t* p, uint32_t (&v)[4]) {
  const uint32_t address = uint32_t(__cvta_generic_to_shared(p));
  asm volatile("ldmatrix.sync.aligned.m8n8.x4.shared.b16 {%0,%1,%2,%3}, [%4];"
      : "=r"(v[0]), "=r"(v[1]), "=r"(v[2]), "=r"(v[3]) : "r"(address) : "memory");
}
__device__ __forceinline__ void matrix_b(const int8_t* p, uint32_t (&v)[2]) {
  const uint32_t address = uint32_t(__cvta_generic_to_shared(p));
  asm volatile("ldmatrix.sync.aligned.m8n8.x2.shared.b16 {%0,%1}, [%2];"
      : "=r"(v[0]), "=r"(v[1]) : "r"(address) : "memory");
}
__device__ __forceinline__ void copy16(int8_t* dst, const int8_t* src, bool valid) {
  const uint32_t address = uint32_t(__cvta_generic_to_shared(dst));
  const int bytes = valid ? 16 : 0;
  asm volatile("cp.async.cg.shared.global [%0], [%1], 16, %2;"
               :: "r"(address), "l"(src), "r"(bytes) : "memory");
}
__device__ __forceinline__ void mma(int32_t* c, uint32_t a0, uint32_t a1,
                                    uint32_t a2, uint32_t a3,
                                    uint32_t b0, uint32_t b1) {
  asm volatile(
      "mma.sync.aligned.m16n8k32.row.col.s32.s8.s8.s32 "
      "{%0,%1,%2,%3}, {%4,%5,%6,%7}, {%8,%9}, {%0,%1,%2,%3};"
      : "+r"(c[0]), "+r"(c[1]), "+r"(c[2]), "+r"(c[3])
      : "r"(a0), "r"(a1), "r"(a2), "r"(a3), "r"(b0), "r"(b1));
}
__device__ __forceinline__ uint32_t xor_warp(uint32_t x) {
  uint32_t v;
  asm volatile("redux.sync.xor.b32 %0, %1, 0xffffffff;" : "=r"(v) : "r"(x));
  return v;
}
template<int Threads, int TM, int TN, int StageK>
__device__ __forceinline__ void prefetch(int8_t* stage, const int8_t* a,
                                        const int8_t* bt, Shape p,
                                        int row0, int col0, int kk) {
  constexpr int stride = StageK + 16;
  for (int v = threadIdx.x; v < (TM + TN) * (StageK / 16); v += Threads) {
    const int row = v / (StageK / 16), half = (v % (StageK / 16)) * 16;
    const bool is_a = row < TM;
    const int global_row = is_a ? row0 + row : col0 + row - TM;
    const bool valid = global_row < (is_a ? p.m : p.n) && kk + half < p.k;
    const int8_t* base = is_a ? a : bt;
    const int8_t* src = valid ? base + std::size_t(global_row) * p.k + kk + half : base;
    copy16(stage + row * stride + half, src, valid);
  }
  asm volatile("cp.async.commit_group;" ::: "memory");
}

template<int Threads, int ProofN, bool Debug, int StageK, bool MatrixLoads = false>
__global__ __launch_bounds__(Threads, 1)
void pearl_int8(const int8_t* __restrict__ a, const int8_t* __restrict__ bt,
                uint32_t* __restrict__ out, int32_t* __restrict__ matrix, Shape p) {
  constexpr int tile_m = Threads == 384 ? 192 : (Threads == 128 ? 64 : pearl_lab::tile_m);
  constexpr int tile_n = Threads == 384 ? 256 : (StageK == 64 ? 320 : (Threads == 128 ? 128 : pearl_lab::tile_n));
  constexpr int shared_stride = StageK + 16;
  constexpr int stage_bytes = (tile_m + tile_n) * shared_stride;
  constexpr int warps_m = Threads == 384 ? 3 : (Threads == 128 ? 2 : 4), warps_n = Threads / 32 / warps_m;
  constexpr int mi_count = tile_m / warps_m / 16;
  constexpr int ni_count = tile_n / warps_n / 8;
  constexpr int combine = ProofN / 8;
  constexpr int proofs = (tile_m / 16) * (tile_n / ProofN);
  extern __shared__ __align__(16) unsigned char memory[];
  auto* stage = reinterpret_cast<int8_t*>(memory);
  // In the compact variant, lane 0..15 each own one transcript slot.
  uint32_t lane_history[mi_count][ni_count / combine] = {};
  auto* history = reinterpret_cast<uint32_t*>(memory + 2 * stage_bytes);
  if constexpr (Threads != 128)
    for (int t = threadIdx.x; t < proofs * 16; t += Threads) history[t] = 0;
  const int warp = threadIdx.x >> 5, lane = threadIdx.x & 31;
  const int wm = warp / warps_n, wn = warp % warps_n;
  const int row0 = blockIdx.y * tile_m, col0 = blockIdx.x * tile_n;
  const int warp_row = wm * mi_count * 16, warp_col = wn * ni_count * 8;
  const int group = lane >> 2, t = lane & 3;
  const int rank_shift = __ffs(p.rank) - 1;
  int32_t c[mi_count][ni_count][4] = {};
  prefetch<Threads, tile_m, tile_n, StageK>(stage, a, bt, p, row0, col0, 0);
  asm volatile("cp.async.wait_group 0;" ::: "memory");
  __syncthreads();
  for (int kk = 0; kk < p.k; kk += StageK) {
    const int which = (kk / StageK) & 1;
    const bool next = kk + StageK < p.k;
    if (next) prefetch<Threads, tile_m, tile_n, StageK>(stage + (1 - which) * stage_bytes,
                               a, bt, p, row0, col0, kk + StageK);
    #pragma unroll
    for (int sub = 0; sub < StageK; sub += tile_k) {
    if (kk + sub >= p.k) break;
    const int8_t* sa = stage + which * stage_bytes + sub;
    const int8_t* sb = sa + tile_m * shared_stride;
    if constexpr (MatrixLoads) {
      // Reuse each of eight B fragments across all four A fragments.
      uint32_t bfrag[ni_count][2];
      #pragma unroll
      for (int in = 0; in < ni_count; ++in)
        matrix_b(sb + (warp_col + in * 8 + (lane & 7)) * shared_stride
                    + ((lane >> 3) & 1) * 16, bfrag[in]);
      #pragma unroll
      for (int im = 0; im < mi_count; ++im) {
        uint32_t afrag[4];
        matrix_a(sa + (warp_row + im * 16 + (lane & 15)) * shared_stride
                    + (lane >> 4) * 16, afrag);
        #pragma unroll
        for (int in = 0; in < ni_count; ++in)
          mma(c[im][in], afrag[0], afrag[1], afrag[2], afrag[3], bfrag[in][0], bfrag[in][1]);
      }
    } else {
    #pragma unroll
    for (int im = 0; im < mi_count; ++im) {
      const int ar = warp_row + im * 16 + group;
      const uint32_t a0 = word(sa + ar * shared_stride + t * 4);
      const uint32_t a1 = word(sa + (ar + 8) * shared_stride + t * 4);
      const uint32_t a2 = word(sa + ar * shared_stride + t * 4 + 16);
      const uint32_t a3 = word(sa + (ar + 8) * shared_stride + t * 4 + 16);
      #pragma unroll
      for (int in = 0; in < ni_count; ++in) {
        const int br = warp_col + in * 8 + group;
        mma(c[im][in], a0, a1, a2, a3,
            word(sb + br * shared_stride + t * 4),
            word(sb + br * shared_stride + t * 4 + 16));
      }
    }
    }
    if (((kk + sub + tile_k) & (p.rank - 1)) == 0) {
      const int slot = (((kk + sub + tile_k) >> rank_shift) - 1) & 15;
      #pragma unroll
      for (int im = 0; im < mi_count; ++im) {
        #pragma unroll
        for (int pn = 0; pn < ni_count / combine; ++pn) {
          uint32_t x = 0;
          #pragma unroll
          for (int z = 0; z < combine; ++z) {
            #pragma unroll
            for (int q = 0; q < 4; ++q) x ^= uint32_t(c[im][pn * combine + z][q]);
          }
          x = xor_warp(x);
          if (lane == slot) {
            const int proof = (warp_row / 16 + im) * (tile_n / ProofN)
                            + warp_col / ProofN + pn;
            uint32_t& h = Threads == 128 ? lane_history[im][pn] : history[proof * 16 + slot];
            h = (h << 13 | h >> 19) ^ x;
          }
        }
      }
    }
    } // checkpoint handled after each 32-wide MMA, even when rank=32
    if (next) asm volatile("cp.async.wait_group 0;" ::: "memory");
    // Protect current readers before the next iteration overwrites this buffer.
    __syncthreads();
  }
  if constexpr (Threads == 128) {
    if (lane < 16) {
      #pragma unroll
      for (int im = 0; im < mi_count; ++im) {
        #pragma unroll
        for (int pn = 0; pn < ni_count / combine; ++pn) {
          const int row = (row0 + warp_row) / 16 + im;
          const int col = (col0 + warp_col) / ProofN + pn;
          if (row < p.m / 16 && col < p.n / ProofN)
            out[(std::size_t(row) * (p.n / ProofN) + col) * 16 + lane] = lane_history[im][pn];
        }
      }
    }
  } else for (int z = threadIdx.x; z < proofs * 16; z += Threads) {
    const int proof = z / 16, slot = z & 15;
    const int row = row0 / 16 + proof / (tile_n / ProofN);
    const int col = col0 / ProofN + proof % (tile_n / ProofN);
    if (row < p.m / 16 && col < p.n / ProofN)
      out[(std::size_t(row) * (p.n / ProofN) + col) * 16 + slot] = history[z];
  }
  if constexpr (Debug) {
    #pragma unroll
    for (int im = 0; im < mi_count; ++im) {
      #pragma unroll
      for (int in = 0; in < ni_count; ++in) {
        #pragma unroll
        for (int q = 0; q < 4; ++q) {
          const int row = row0 + warp_row + im * 16 + group + (q >= 2 ? 8 : 0);
          const int col = col0 + warp_col + in * 8 + t * 2 + (q & 1);
          if (row < p.m && col < p.n) matrix[std::size_t(row) * p.n + col] = c[im][in][q];
        }
      }
    }
  }
}
template<int T, int PN, bool Debug, int StageK = 32, bool MatrixLoads = false>
cudaError_t run(const int8_t* a, const int8_t* bt, uint32_t* out,
                 int32_t* matrix, Shape p, cudaStream_t stream) {
  constexpr int tile_m = T == 384 ? 192 : (T == 128 ? 64 : pearl_lab::tile_m);
  constexpr int tile_n = T == 384 ? 256 : (StageK == 64 ? 320 : (T == 128 ? 128 : pearl_lab::tile_n));
  constexpr int bytes = T == 384 ? stage384_shared_bytes(PN) : (StageK == 64 ? stage64_shared_bytes(PN) : (T == 128 ? 2 * (tile_m + tile_n) * shared_stride : shared_bytes(PN)));
  // The standalone harness owns the context for its entire lifetime (no reset).
  static thread_local int configured_device = -1;
  int device = -1;
  cudaError_t e = cudaGetDevice(&device);
  if (e != cudaSuccess) return e;
  if (configured_device != device) {
    e = cudaFuncSetAttribute(pearl_int8<T, PN, Debug, StageK, MatrixLoads>,
                             cudaFuncAttributeMaxDynamicSharedMemorySize, bytes);
    if (e != cudaSuccess) return e;
    configured_device = device;
  }
  pearl_int8<T, PN, Debug, StageK, MatrixLoads><<<dim3((p.n + tile_n - 1) / tile_n,
                                 (p.m + tile_m - 1) / tile_m), T, bytes, stream>>>
      (a, bt, out, matrix, p);
  return cudaGetLastError();
}
template<int T, int PN, bool Debug, int StageK = 32, bool MatrixLoads = false>
cudaError_t info(cudaFuncAttributes* attr, int* blocks) {
  constexpr int bytes = T == 384 ? stage384_shared_bytes(PN) : (StageK == 64 ? stage64_shared_bytes(PN) : (T == 128 ? 2 * (64 + 128) * shared_stride : shared_bytes(PN)));
  auto e = cudaFuncGetAttributes(attr, pearl_int8<T, PN, Debug, StageK, MatrixLoads>);
  if (e != cudaSuccess) return e;
  e = cudaFuncSetAttribute(pearl_int8<T, PN, Debug, StageK, MatrixLoads>,
                           cudaFuncAttributeMaxDynamicSharedMemorySize, bytes);
  if (e != cudaSuccess) return e;
  return cudaOccupancyMaxActiveBlocksPerMultiprocessor(blocks,
      pearl_int8<T, PN, Debug, StageK, MatrixLoads>, T, bytes);
}
} // namespace
cudaError_t launch(const int8_t* a, const int8_t* bt, uint32_t* out,
                   int32_t* matrix, Shape p, int threads, cudaStream_t stream, int stage_k, bool matrix_loads) {
  try { p.validate(); } catch (...) { return cudaErrorInvalidValue; }
  if (!a || !bt || !out || (threads != 128 && threads != 256 && threads != 384 && threads != 512)) return cudaErrorInvalidValue;
  if(matrix_loads){
    if(threads!=384||stage_k!=64)return cudaErrorInvalidValue;
    if(p.proof_n==8){if(matrix)return run<384,8,true,64,true>(a,bt,out,matrix,p,stream);return run<384,8,false,64,true>(a,bt,out,matrix,p,stream);}
    if(matrix)return run<384,16,true,64,true>(a,bt,out,matrix,p,stream);return run<384,16,false,64,true>(a,bt,out,matrix,p,stream);
  }
  if(stage_k==64&&threads==384){
    if(p.proof_n==8){if(matrix)return run<384,8,true,64>(a,bt,out,matrix,p,stream);return run<384,8,false,64>(a,bt,out,matrix,p,stream);}
    if(matrix)return run<384,16,true,64>(a,bt,out,matrix,p,stream);return run<384,16,false,64>(a,bt,out,matrix,p,stream);
  }
  if (stage_k == 64 && threads == 256) {
    if (p.proof_n == 8) {
      if (matrix) return run<256,8,true,64>(a,bt,out,matrix,p,stream);
      return run<256,8,false,64>(a,bt,out,matrix,p,stream);
    }
    if (matrix) return run<256,16,true,64>(a,bt,out,matrix,p,stream);
    return run<256,16,false,64>(a,bt,out,matrix,p,stream);
  }
  if (stage_k != 32) return cudaErrorInvalidValue;
  #define RUN(T,PN) if (threads == T && p.proof_n == PN) { \
    if (matrix) return run<T,PN,true>(a,bt,out,matrix,p,stream); \
    return run<T,PN,false>(a,bt,out,matrix,p,stream); }
  RUN(128,8) RUN(128,16) RUN(256,8) RUN(256,16) RUN(512,8) RUN(512,16)
  #undef RUN
  return cudaErrorInvalidValue;
}
cudaError_t resource_info(int threads, int pn, bool debug,
                         cudaFuncAttributes* attr, int* blocks, int stage_k, bool matrix_loads) {
  if (!attr || !blocks) return cudaErrorInvalidValue;
  if(matrix_loads){
    if(threads!=384||stage_k!=64)return cudaErrorInvalidValue;
    if(pn==8){if(debug)return info<384,8,true,64,true>(attr,blocks);return info<384,8,false,64,true>(attr,blocks);}
    if(pn!=16)return cudaErrorInvalidValue;
    if(debug)return info<384,16,true,64,true>(attr,blocks);return info<384,16,false,64,true>(attr,blocks);
  }
  if(stage_k==64&&threads==384){
    if(pn==8){if(debug)return info<384,8,true,64>(attr,blocks);return info<384,8,false,64>(attr,blocks);}
    if(pn!=16)return cudaErrorInvalidValue;
    if(debug)return info<384,16,true,64>(attr,blocks);return info<384,16,false,64>(attr,blocks);
  }
  if (stage_k == 64 && threads == 256) {
    if (pn == 8) {
      if (debug) return info<256,8,true,64>(attr,blocks);
      return info<256,8,false,64>(attr,blocks);
    }
    if (pn != 16) return cudaErrorInvalidValue;
    if (debug) return info<256,16,true,64>(attr,blocks);
    return info<256,16,false,64>(attr,blocks);
  }
  if (stage_k != 32) return cudaErrorInvalidValue;
  #define INFO(T,PN) if (threads == T && pn == PN) { \
    if (debug) return info<T,PN,true>(attr,blocks); \
    return info<T,PN,false>(attr,blocks); }
  INFO(128,8) INFO(128,16) INFO(256,8) INFO(256,16) INFO(512,8) INFO(512,16)
  #undef INFO
  return cudaErrorInvalidValue;
}
} // namespace pearl_lab
