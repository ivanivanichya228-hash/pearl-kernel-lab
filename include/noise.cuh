#pragma once
#include "noise.hpp"
#include <cuda_runtime.h>
#include <string>
namespace pearl_lab {
// Apply raw+official sparse noise IN PLACE. scratch uniform/perm are reused on the same stream.
cudaError_t launch_apply_noise(int8_t* data,int rows,int k,int rank,NoiseKey key,int8_t*uniform,uint32_t*perm,uint32_t*error,cudaStream_t stream);
void check_gpu_noise(const std::string&raw_path,const std::string&official_noised_path);
}
