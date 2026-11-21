#pragma once
// Included only inside kernel.cu's private namespace, after copy16/mma/xor_warp.
__device__ __forceinline__ uint32_t fused_word(const int8_t* base,int row,int column){
  return word(base+row*64+(column^(((row>>1)&3)*16)));
}
__device__ __forceinline__ void fused_prefetch(int8_t* dst,const int8_t*a,const int8_t*bt,Shape p,int row0,int col0,int kk){
  for(int v=threadIdx.x;v<448*4;v+=384){
    const int row=v/4,half=(v%4)*16;
    const bool is_a=row<192;const int global_row=is_a?row0+row:col0+row-192;
    const bool valid=global_row<(is_a?p.m:p.n)&&kk+half<p.k;
    const int8_t*base=is_a?a:bt;
    const int8_t*src=valid?base+std::size_t(global_row)*p.k+kk+half:base;
    copy16(dst+row*64+(half^(((row>>1)&3)*16)),src,valid);
  }
  asm volatile("cp.async.commit_group;" ::: "memory");
}
template<int ProofN>
__global__ __launch_bounds__(384, 1)
void pearl_fused(const int8_t* __restrict__ a, const int8_t* __restrict__ bt,
                KeyTarget context, CompactHit* hits, uint32_t* found, uint32_t capacity, HitGeometry geometry, Shape p) {
  constexpr int Threads=384, StageK=64, tile_m=192, tile_n=256;
  constexpr int stages=ProofN==16?3:2;
  constexpr int shared_stride=64,stage_bytes=(tile_m+tile_n)*shared_stride;
  constexpr int warps_m=3,warps_n=4;
  constexpr int mi_count = tile_m / warps_m / 16;
  constexpr int ni_count = tile_n / warps_n / 8;
  constexpr int combine = ProofN / 8;
  constexpr int proofs = (tile_m / 16) * (tile_n / ProofN);
  extern __shared__ __align__(16) unsigned char memory[];
  auto* stage = reinterpret_cast<int8_t*>(memory);
  // In the compact variant, lane 0..15 each own one transcript slot.
  uint32_t lane_history[mi_count][ni_count / combine] = {};
  auto* history = reinterpret_cast<uint32_t*>(memory + stages * stage_bytes);
  if constexpr (Threads != 128)
    for (int t = threadIdx.x; t < proofs * 16; t += Threads) history[t] = 0;
  const int warp = threadIdx.x >> 5, lane = threadIdx.x & 31;
  const int wm = warp / warps_n, wn = warp % warps_n;
  const int row0 = blockIdx.y * tile_m, col0 = blockIdx.x * tile_n;
  const int warp_row = wm * mi_count * 16, warp_col = wn * ni_count * 8;
  const int group = lane >> 2, t = lane & 3;
  const int rank_shift = __ffs(p.rank) - 1;
  int32_t c[mi_count][ni_count][4] = {};
  fused_prefetch(stage,a,bt,p,row0,col0,0);
  if constexpr(stages==3){
    if(p.k>64){fused_prefetch(stage+stage_bytes,a,bt,p,row0,col0,64);asm volatile("cp.async.wait_group 1;" ::: "memory");}
    else asm volatile("cp.async.wait_group 0;" ::: "memory");
  }else asm volatile("cp.async.wait_group 0;" ::: "memory");
  __syncthreads();
  for(int kk=0;kk<p.k;kk+=64){
    const int which=(kk/64)%stages;
    if(kk+(stages-1)*64<p.k)
      fused_prefetch(stage+((which+stages-1)%stages)*stage_bytes,a,bt,p,row0,col0,kk+(stages-1)*64);
    #pragma unroll
    for (int sub = 0; sub < StageK; sub += tile_k) {
    if (kk + sub >= p.k) break;
    const int8_t* sa=stage+which*stage_bytes;
    const int8_t* sb=sa+tile_m*shared_stride;
    #pragma unroll
    for (int im = 0; im < mi_count; ++im) {
      const int ar = warp_row + im * 16 + group;
      const uint32_t a0 = fused_word(sa,ar,sub+t*4);
      const uint32_t a1 = fused_word(sa,ar+8,sub+t*4);
      const uint32_t a2 = fused_word(sa,ar,sub+t*4+16);
      const uint32_t a3 = fused_word(sa,ar+8,sub+t*4+16);
      #pragma unroll
      for (int in = 0; in < ni_count; ++in) {
        const int br = warp_col + in * 8 + group;
        mma(c[im][in], a0, a1, a2, a3,
            fused_word(sb,br,sub+t*4),
            fused_word(sb,br,sub+t*4+16));
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
    if constexpr(stages==3){
      if(kk+128<p.k)asm volatile("cp.async.wait_group 1;" ::: "memory");
      else asm volatile("cp.async.wait_group 0;" ::: "memory");
    }else asm volatile("cp.async.wait_group 0;" ::: "memory");
    // Protect current readers before the next iteration overwrites this buffer.
    __syncthreads();
  }
  // Stage buffers are dead after K; reuse them to transpose history for
  // bank-friendly one-thread-per-proof keyed hashing. No extra shared allocation.
  __syncthreads();
  uint32_t* transposed=reinterpret_cast<uint32_t*>(memory);
  for(int z=threadIdx.x;z<proofs*16;z+=Threads)
    transposed[(z&15)*(proofs+1)+z/16]=history[z];
  __syncthreads();
  for(int proof=threadIdx.x;proof<proofs;proof+=Threads){
    const int row=row0/16+proof/(tile_n/ProofN);
    const int col=col0/ProofN+proof%(tile_n/ProofN);
    if(row<p.m/16&&col<p.n/ProofN){
      uint32_t words[16],hash[8];
      #pragma unroll
      for(int j=0;j<16;++j)words[j]=transposed[j*(proofs+1)+proof];
      jackpot_hash64(words,context.key,hash);
      if(hash_meets_target(hash,context.target)){
        const uint32_t slot=atomicAdd(found,1u);
        if(slot<capacity){
          hits[slot].index=uint32_t(compact_global_index(uint32_t(row*(p.n/ProofN)+col),geometry));
          #pragma unroll
          for(int j=0;j<16;++j)hits[slot].transcript[j]=words[j];
        }
      }
    }
  }
}
template<int PN>cudaError_t fused_run(const int8_t*a,const int8_t*bt,KeyTarget context,CompactHit*hits,uint32_t*found,uint32_t capacity,HitGeometry geometry,Shape p,cudaStream_t stream){
 static thread_local int configured=-1;int device=-1;auto e=cudaGetDevice(&device);if(e!=cudaSuccess)return e;
 if(configured!=device){
  e=cudaFuncSetAttribute(pearl_fused<PN>,cudaFuncAttributeMaxDynamicSharedMemorySize,triple_bytes<PN>());if(e!=cudaSuccess)return e;
  e=cudaFuncSetAttribute(pearl_fused<PN>,cudaFuncAttributePreferredSharedMemoryCarveout,100);if(e!=cudaSuccess)return e;configured=device;
 }
 pearl_fused<PN><<<dim3((p.n+255)/256,(p.m+191)/192),384,triple_bytes<PN>(),stream>>>(a,bt,context,hits,found,capacity,geometry,p);
 return cudaGetLastError();
}
template<int PN>cudaError_t fused_info(cudaFuncAttributes*attr,int*blocks){
 auto e=cudaFuncGetAttributes(attr,pearl_fused<PN>);if(e!=cudaSuccess)return e;
 e=cudaFuncSetAttribute(pearl_fused<PN>,cudaFuncAttributeMaxDynamicSharedMemorySize,triple_bytes<PN>());if(e!=cudaSuccess)return e;
 e=cudaFuncSetAttribute(pearl_fused<PN>,cudaFuncAttributePreferredSharedMemoryCarveout,100);if(e!=cudaSuccess)return e;
 return cudaOccupancyMaxActiveBlocksPerMultiprocessor(blocks,pearl_fused<PN>,384,triple_bytes<PN>());
}
