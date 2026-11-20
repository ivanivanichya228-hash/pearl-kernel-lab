#include "noise.cuh"
#include "mapped_work.hpp"
#include <algorithm>
#include <iostream>
namespace pearl_lab {
namespace {
__global__ void uniform_kernel(int8_t*out,uint32_t blocks,NoiseKey key){uint32_t i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=blocks)return;uint32_t h[8];noise_hash(i,0,key,h);
 #pragma unroll
 for(int j=0;j<32;++j)out[std::size_t(i)*32+j]=int8_t(int((h[j/4]>>(8*(j%4)))&63)-32);
}
__global__ void permutation_kernel(uint32_t*out,int blocks,int rank,NoiseKey key){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=blocks)return;uint32_t h[8];noise_hash(uint32_t(i),1,key,h);
 #pragma unroll
 for(int j=0;j<8;++j){out[(i*8+j)*2]=h[j]&(rank-1);out[(i*8+j)*2+1]=noise_second_index(h[j],rank);}
}
__global__ void add_kernel(int8_t*data,std::size_t packs,int k,int rank,const int8_t*uniform,const uint32_t*perm,uint32_t*error){
 std::size_t pack=std::size_t(blockIdx.x)*blockDim.x+threadIdx.x;if(pack>=packs)return;const std::size_t offset=pack*4,row=offset/k;const int col=int(offset%k);uint32_t input=reinterpret_cast<const uint32_t*>(data)[pack],output=0;
 #pragma unroll
 for(int j=0;j<4;++j){int raw=int(int8_t((input>>(8*j))&255));int value=raw+uniform[row*rank+perm[(col+j)*2]]-uniform[row*rank+perm[(col+j)*2+1]];
  if(raw < -64 || raw > 63 || value < -127 || value > 127)atomicOr(error,1u);output|=uint32_t(uint8_t(value))<<(8*j);
 }reinterpret_cast<uint32_t*>(data)[pack]=output;
}
void checked(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
template<class T>struct Device{T*p=nullptr;explicit Device(std::size_t n){checked(cudaMalloc(&p,n*sizeof(T)));}~Device(){if(p)cudaFree(p);}};
}
cudaError_t launch_apply_noise(int8_t*data,int rows,int k,int rank,NoiseKey key,int8_t*uniform,uint32_t*perm,uint32_t*error,cudaStream_t stream){
 if(!data||!uniform||!perm||!error||rows<=0||rows>131072||k<1024||k>8192||k%64||rank<128||rank>1024||(rank&(rank-1))||k%rank)return cudaErrorInvalidValue;
 uint32_t blocks=uint32_t(std::size_t(rows)*rank/32);uniform_kernel<<<(blocks+127)/128,128,0,stream>>>(uniform,blocks,key);auto e=cudaGetLastError();if(e!=cudaSuccess)return e;
 permutation_kernel<<<(k/8+127)/128,128,0,stream>>>(perm,k/8,rank,key);e=cudaGetLastError();if(e!=cudaSuccess)return e;
 std::size_t packs=std::size_t(rows)*k/4;add_kernel<<<unsigned((packs+255)/256),256,0,stream>>>(data,packs,k,rank,uniform,perm,error);return cudaGetLastError();
}
void check_gpu_noise(const std::string&raw_path,const std::string&ref_path){
 const MappedMiningWork raw(raw_path),ref(ref_path);auto&p=raw.info.shape;
 if(!raw.info.raw_input||ref.info.raw_input||p.m>256||p.n>256||p.k>8192||p.m!=ref.info.shape.m||p.n!=ref.info.shape.n||p.k!=ref.info.shape.k||p.rank!=ref.info.shape.rank||p.proof_n!=ref.info.shape.proof_n||raw.a_bytes!=ref.a_bytes||raw.b_bytes!=ref.b_bytes||raw.info.batch_id!=ref.info.batch_id||raw.info.fingerprint!=ref.info.fingerprint)throw std::runtime_error("noise check reference/context bounds");
 Device<int8_t>a(raw.a_bytes),b(raw.b_bytes),uniform(std::size_t(std::max(p.m,p.n))*p.rank);Device<uint32_t>perm(p.k*2),error(1);
 checked(cudaMemcpy(a.p,raw.a,raw.a_bytes,cudaMemcpyHostToDevice));checked(cudaMemcpy(b.p,raw.bt,raw.b_bytes,cudaMemcpyHostToDevice));checked(cudaMemset(error.p,0,4));
 NoiseKey ka{},kb{};std::copy(raw.info.context.key,raw.info.context.key+8,ka.key);std::copy(raw.info.b_noise_key,raw.info.b_noise_key+8,kb.key);ka.is_a=true;kb.is_a=false;
 checked(launch_apply_noise(a.p,p.m,p.k,p.rank,ka,uniform.p,perm.p,error.p,nullptr));checked(launch_apply_noise(b.p,p.n,p.k,p.rank,kb,uniform.p,perm.p,error.p,nullptr));checked(cudaDeviceSynchronize());uint32_t flag=0;checked(cudaMemcpy(&flag,error.p,4,cudaMemcpyDeviceToHost));if(flag)throw std::runtime_error("GPU noise range failure");
 std::vector<int8_t>av(raw.a_bytes),bv(raw.b_bytes);checked(cudaMemcpy(av.data(),a.p,av.size(),cudaMemcpyDeviceToHost));checked(cudaMemcpy(bv.data(),b.p,bv.size(),cudaMemcpyDeviceToHost));
 if(!std::equal(av.begin(),av.end(),ref.a)||!std::equal(bv.begin(),bv.end(),ref.bt))throw std::runtime_error("GPU noise differs from unmodified official reference");
 std::cout<<"{\"phase\":\"noise_correctness\",\"passed\":true,\"all_A_B_bytes_checked\":true,\"matrix_bytes\":"<<av.size()+bv.size()<<",\"rank\":"<<p.rank<<"}\n";
}
}
