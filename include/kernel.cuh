#pragma once
#include <cuda_runtime.h>
#include <cstdint>
#include "contract.hpp"
#include "compact_hits.hpp"
#include "jackpot_hash.hpp"

namespace pearl_lab {
constexpr int tile_m = 128, tile_n = 384, tile_k = 32;
constexpr int shared_stride = 48; // 12 words/row: avoids packed-load bank aliasing.
constexpr int stage_bytes = (tile_m + tile_n) * shared_stride;
constexpr int shared_bytes(int pn) {
  return 2 * stage_bytes + (tile_m / 16) * (tile_n / pn) * 16 * sizeof(uint32_t);
}
constexpr int stage64_shared_bytes(int pn) {
  return 2 * (128 + 320) * 80 + (128 / 16) * (320 / pn) * 16 * sizeof(uint32_t);
}
constexpr int stage384_shared_bytes(int pn) {
  return 2 * (192 + 256) * 80 + (192 / 16) * (256 / pn) * 16 * sizeof(uint32_t);
}
// threads384/stage64: 192x256, 3x4 warps, four-by-eight MMA fragments/warp.
// threads=128 selects compact 64x128 with lane-resident transcript.
// threads=256/512 preserve the original 128x384 shared-history baselines.
cudaError_t launch(const int8_t* a, const int8_t* bt, uint32_t* transcript,
                   int32_t* debug_matrix, Shape p, int threads, cudaStream_t stream, int stage_k = 32, bool matrix_loads = false, bool two_cta = false, bool triple_stage = false);
cudaError_t resource_info(int threads, int proof_n, bool debug,
                         cudaFuncAttributes* attr, int* active_blocks, int stage_k = 32, bool matrix_loads = false, bool two_cta = false, bool triple_stage = false);
// Experimental standalone fused triple384 + exact keyed target check.
cudaError_t launch_fused(const int8_t*,const int8_t*,Shape,KeyTarget,CompactHit*,uint32_t*,uint32_t,HitGeometry,cudaStream_t);
cudaError_t fused_resource_info(int,cudaFuncAttributes*,int*);
cudaError_t launch_singlepass(const int8_t*,const int8_t*,Shape,KeyTarget,CompactHit*,uint32_t*,uint32_t,HitGeometry,cudaStream_t);
cudaError_t singlepass_resource_info(int,cudaFuncAttributes*,int*);
cudaError_t launch_fixed_shape(const int8_t*,const int8_t*,Shape,KeyTarget,CompactHit*,uint32_t*,uint32_t,HitGeometry,cudaStream_t);
cudaError_t fixed_shape_resource_info(int,cudaFuncAttributes*,int*);
}  // namespace pearl_lab
