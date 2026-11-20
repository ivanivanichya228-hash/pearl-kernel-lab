#pragma once
#include <cstdint>
#ifdef __CUDACC__
#define PRL_HD __host__ __device__ __forceinline__
#else
#define PRL_HD inline
#endif
namespace pearl_lab {
struct KeyTarget { uint32_t key[8]; uint32_t target[8]; };
PRL_HD uint32_t rr(uint32_t x,int n){return (x>>n)|(x<<(32-n));}
PRL_HD void mix(uint32_t* v,int a,int b,int c,int d,uint32_t x,uint32_t y){
 v[a]+=v[b]+x;v[d]=rr(v[d]^v[a],16);v[c]+=v[d];v[b]=rr(v[b]^v[c],12);
 v[a]+=v[b]+y;v[d]=rr(v[d]^v[a],8);v[c]+=v[d];v[b]=rr(v[b]^v[c],7);
}
// BLAKE3 keyed hash of EXACTLY one 64-byte jackpot message; not a generic Merkle hasher.
PRL_HD void jackpot_hash64(const uint32_t* words,const uint32_t* key,uint32_t* out){
 uint32_t v[16],m[16];
 #ifdef __CUDACC__
 #pragma unroll
 #endif
 for(int i=0;i<8;++i)v[i]=key[i];
 v[8]=0x6a09e667;v[9]=0xbb67ae85;v[10]=0x3c6ef372;v[11]=0xa54ff53a;
 v[12]=0;v[13]=0;v[14]=64;v[15]=1|2|8|16; // CHUNK_START|CHUNK_END|ROOT|KEYED_HASH
 #ifdef __CUDACC__
 #pragma unroll
 #endif
 for(int i=0;i<16;++i)m[i]=words[i];
 #ifdef __CUDACC__
 #pragma unroll
 #endif
 for(int r=0;r<7;++r){
  mix(v,0,4,8,12,m[0],m[1]);mix(v,1,5,9,13,m[2],m[3]);mix(v,2,6,10,14,m[4],m[5]);mix(v,3,7,11,15,m[6],m[7]);
  mix(v,0,5,10,15,m[8],m[9]);mix(v,1,6,11,12,m[10],m[11]);mix(v,2,7,8,13,m[12],m[13]);mix(v,3,4,9,14,m[14],m[15]);
  if(r!=6){
   const uint32_t p[16]={m[2],m[6],m[3],m[10],m[7],m[0],m[4],m[13],m[1],m[11],m[12],m[5],m[9],m[14],m[15],m[8]};
   #ifdef __CUDACC__
   #pragma unroll
   #endif
   for(int i=0;i<16;++i)m[i]=p[i];
  }
 }
 #ifdef __CUDACC__
 #pragma unroll
 #endif
 for(int i=0;i<8;++i)out[i]=v[i]^v[i+8];
}
// Words are little-endian; compare most significant word first, including equality.
PRL_HD bool hash_meets_target(const uint32_t* hash,const uint32_t* target){
 for(int i=7;i>=0;--i){if(hash[i]<target[i])return true;if(hash[i]>target[i])return false;}return true;
}
}
#undef PRL_HD
