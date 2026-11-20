#pragma once
#include "jackpot_hash.hpp"
#include <vector>
#include <stdexcept>
#ifdef __CUDACC__
#define PRL_NOISE_HD __host__ __device__ __forceinline__
#else
#define PRL_NOISE_HD inline
#endif
namespace pearl_lab {
struct NoiseKey{uint32_t key[8];bool is_a;};
// Official get_random_hash: index+1 at prepend DWORD, zero padding, then padded A/B_tensor.
PRL_NOISE_HD void noise_hash(uint32_t index,int prepend,const NoiseKey& c,uint32_t out[8]){
 uint32_t message[16]={};message[prepend]=index+1;message[8]=c.is_a?0x65745f41u:0x65745f42u;message[9]=0x726f736eu;jackpot_hash64(message,c.key,out);
}
PRL_NOISE_HD uint32_t noise_second_index(uint32_t u,uint32_t rank){return (u&(rank-1))^(1u+uint32_t((uint64_t(rank-1)*u)>>32));}
// Independent HOST check of the GPU algorithm; compared against unmodified official Rust arrays.
inline std::vector<int8_t> noise_reference(const int8_t*raw,int rows,int k,int rank,const NoiseKey&c){
 std::vector<int8_t>uniform(std::size_t(rows)*rank);std::vector<uint32_t>perm(k*2);
 for(std::size_t block=0;block<uniform.size()/32;++block){uint32_t h[8];noise_hash(uint32_t(block),0,c,h);for(int j=0;j<32;++j)uniform[block*32+j]=int8_t(int((h[j/4]>>(8*(j%4)))&63)-32);}
 for(int block=0;block<k/8;++block){uint32_t h[8];noise_hash(uint32_t(block),1,c,h);for(int j=0;j<8;++j){perm[(block*8+j)*2]=h[j]&(rank-1);perm[(block*8+j)*2+1]=noise_second_index(h[j],rank);}}
 std::vector<int8_t>out(std::size_t(rows)*k);
 for(int row=0;row<rows;++row)for(int col=0;col<k;++col){int x=raw[std::size_t(row)*k+col];if(x < -64 || x > 63)throw std::runtime_error("invalid raw INT7");int value=x+uniform[std::size_t(row)*rank+perm[col*2]]-uniform[std::size_t(row)*rank+perm[col*2+1]];if(value < -127 || value > 127)throw std::runtime_error("noisy INT8 overflow");out[std::size_t(row)*k+col]=int8_t(value);}
 return out;
}
}
#undef PRL_NOISE_HD
