#pragma once
#include <cuda_runtime.h>
#include <cstdint>
#include "contract.hpp"

namespace pearl_lab {
constexpr int tile_m = 128, tile_n = 384, tile_k = 32;
constexpr int shared_stride = 48; // 12 words/row: avoids packed-load bank aliasing.
constexpr int stage_bytes = (tile_m + tile_n) * shared_stride;
constexpr int shared_bytes(int pn) {
  return 2 * stage_bytes + (tile_m / 16) * (tile_n / pn) * 16 * sizeof(uint32_t);
}
cudaError_t launch(const int8_t* a, const int8_t* bt, uint32_t* transcript,
                   int32_t* debug_matrix, Shape p, int threads, cudaStream_t stream);
cudaError_t resource_info(int threads, int proof_n, bool debug,
                         cudaFuncAttributes* attr, int* active_blocks);
}  // namespace pearl_lab
