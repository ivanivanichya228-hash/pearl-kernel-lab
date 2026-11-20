#pragma once
#include "jackpot_hash.hpp"
#include <cuda_runtime.h>
#include <cstddef>
#include <string>
namespace pearl_lab {
// Input is groups*16 transcript words. Output indices are local proof-group indices.
// Same CUDA stream as the matrix kernel enforces producer/consumer ordering.
// found_total counts ALL hits; only min(total,capacity) indices are stored.
// If total>capacity, retain transcripts and rerun with more capacity; never silently drop hits.
cudaError_t launch_jackpot_filter(const uint32_t* transcripts,std::size_t groups,KeyTarget context,
 uint32_t* indices,uint32_t* found_total,uint32_t capacity,cudaStream_t stream);
void check_jackpot_filter(const std::string& vectors_path);
}
