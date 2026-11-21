#pragma once
// Included only inside kernel.cu's private namespace, after copy16/mma/xor_warp.
__device__ __forceinline__ uint32_t occupancy_word(const int8_t* base,int row,int column){
  return word(base+row*64+(column^(((row>>1)&3)*16)));
}
__device__ __forceinline__ void occupancy_prefetch(int8_t* dst,const int8_t*a,const int8_t*bt,Shape p,int row0,int col0,int kk){
  for(int v=threadIdx.x;v<256*4;v+=256){
    const int row=v/4,half=(v%4)*16;
    const bool is_a=row<128;const int global_row=is_a?row0+row:col0+row-128;
    const bool valid=global_row<(is_a?p.m:p.n)&&kk+half<p.k;
    const int8_t*base=is_a?a:bt;
    const int8_t*src=valid?base+std::size_t(global_row)*p.k+kk+half:base;
    copy16(dst+row*64+(half^(((row>>1)&3)*16)),src,valid);
  }
  asm volatile("cp.async.commit_group;" ::: "memory");
}
template<int ProofN, bool Debug>
__global__ __launch_bounds__(256, 2)
void pearl_occupancy(const int8_t* __restrict__ a, const int8_t* __restrict__ bt,
                uint32_t* __restrict__ out, int32_t* __restrict__ matrix, Shape p) {
  constexpr int Threads=256, StageK=64, tile_m=128, tile_n=128;
  constexpr int stages=3;
  constexpr int shared_stride=64,stage_bytes=(tile_m+tile_n)*shared_stride;
  constexpr int warps_m=2,warps_n=4;
  constexpr int mi_count = tile_m / warps_m / 16;
  constexpr int ni_count = tile_n / warps_n / 8;
  constexpr int combine = ProofN / 8;
  constexpr int proofs = (tile_m / 16) * (tile_n / ProofN);
  extern __shared__ __align__(16) unsigned char memory[];
  auto* stage = reinterpret_cast<int8_t*>(memory);
  // In the compact variant, lane 0..15 each own one transcript slot.
  uint32_t lane_history[mi_count][ni_count / combine] = {};
  auto* history = reinterpret_cast<uint32_t*>(memory + stages * stage_bytes);
  if constexpr (false)
    for (int t = threadIdx.x; t < proofs * 16; t += Threads) history[t] = 0;
  const int warp = threadIdx.x >> 5, lane = threadIdx.x & 31;
  const int wm = warp / warps_n, wn = warp % warps_n;
  const int row0 = blockIdx.y * tile_m, col0 = blockIdx.x * tile_n;
  const int warp_row = wm * mi_count * 16, warp_col = wn * ni_count * 8;
  const int group = lane >> 2, t = lane & 3;
  const int rank_shift = __ffs(p.rank) - 1;
  int32_t c[mi_count][ni_count][4] = {};
  occupancy_prefetch(stage,a,bt,p,row0,col0,0);
  if constexpr(stages==3){
    if(p.k>64){occupancy_prefetch(stage+stage_bytes,a,bt,p,row0,col0,64);asm volatile("cp.async.wait_group 1;" ::: "memory");}
    else asm volatile("cp.async.wait_group 0;" ::: "memory");
  }else asm volatile("cp.async.wait_group 0;" ::: "memory");
  __syncthreads();
  for(int kk=0;kk<p.k;kk+=64){
    const int which=(kk/64)%stages;
    if(kk+(stages-1)*64<p.k)
      occupancy_prefetch(stage+((which+stages-1)%stages)*stage_bytes,a,bt,p,row0,col0,kk+(stages-1)*64);
    #pragma unroll
    for (int sub = 0; sub < StageK; sub += tile_k) {
    if (kk + sub >= p.k) break;
    const int8_t* sa=stage+which*stage_bytes;
    const int8_t* sb=sa+tile_m*shared_stride;
    #pragma unroll
    for (int im = 0; im < mi_count; ++im) {
      const int ar = warp_row + im * 16 + group;
      const uint32_t a0 = occupancy_word(sa,ar,sub+t*4);
      const uint32_t a1 = occupancy_word(sa,ar+8,sub+t*4);
      const uint32_t a2 = occupancy_word(sa,ar,sub+t*4+16);
      const uint32_t a3 = occupancy_word(sa,ar+8,sub+t*4+16);
      #pragma unroll
      for (int in = 0; in < ni_count; ++in) {
        const int br = warp_col + in * 8 + group;
        mma(c[im][in], a0, a1, a2, a3,
            occupancy_word(sb,br,sub+t*4),
            occupancy_word(sb,br,sub+t*4+16));
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
            uint32_t& h = true ? lane_history[im][pn] : history[proof * 16 + slot];
            h = (h << 13 | h >> 19) ^ x;
          }
        }
      }
    }
    } // checkpoint handled after each 32-wide MMA, even when rank=32
    if constexpr(stages==3){
      if(kk+128<p.k)asm volatile("cp.async.wait_group 1;" ::: "memory");
      else asm volatile("cp.async.wait_group 0;" ::: "memory");
    }else asm volatile("cp.async.wait_group 0;" ::: "memory");
    // Protect current readers before the next iteration overwrites this buffer.
    __syncthreads();
  }
  if constexpr (true) {
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


// Keep all transcript slots in their owner lane; no shared history allocation.
constexpr int occupancy_shared_bytes=3*256*64;
template<int PN,bool Debug>cudaError_t occupancy_run(const int8_t*a,const int8_t*bt,uint32_t*out,int32_t*matrix,Shape p,cudaStream_t stream){
 static thread_local int configured=-1;int device=-1;auto e=cudaGetDevice(&device);if(e!=cudaSuccess)return e;
 if(configured!=device){
  e=cudaFuncSetAttribute(pearl_occupancy<PN,Debug>,cudaFuncAttributeMaxDynamicSharedMemorySize,occupancy_shared_bytes);if(e!=cudaSuccess)return e;
  e=cudaFuncSetAttribute(pearl_occupancy<PN,Debug>,cudaFuncAttributePreferredSharedMemoryCarveout,100);if(e!=cudaSuccess)return e;configured=device;
 }
 pearl_occupancy<PN,Debug><<<dim3((p.n+127)/128,(p.m+127)/128),256,occupancy_shared_bytes,stream>>>(a,bt,out,matrix,p);
 return cudaGetLastError();
}
template<int PN,bool Debug>cudaError_t occupancy_info(cudaFuncAttributes*attr,int*blocks){
 auto e=cudaFuncGetAttributes(attr,pearl_occupancy<PN,Debug>);if(e!=cudaSuccess)return e;
 e=cudaFuncSetAttribute(pearl_occupancy<PN,Debug>,cudaFuncAttributeMaxDynamicSharedMemorySize,occupancy_shared_bytes);if(e!=cudaSuccess)return e;
 e=cudaFuncSetAttribute(pearl_occupancy<PN,Debug>,cudaFuncAttributePreferredSharedMemoryCarveout,100);if(e!=cudaSuccess)return e;
 return cudaOccupancyMaxActiveBlocksPerMultiprocessor(blocks,pearl_occupancy<PN,Debug>,256,occupancy_shared_bytes);
}
