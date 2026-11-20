#include "filter.cuh"
#include "hash_vectors.hpp"
#include <algorithm>
#include <iostream>
#include <limits>
#include <vector>
namespace pearl_lab {
namespace {
template<bool PerItem>
__global__ void filter_kernel(const uint32_t* words,uint32_t groups,KeyTarget common,const KeyTarget* contexts,
 uint32_t* indices,uint32_t* found,uint32_t capacity,uint32_t* debug){
 const uint32_t i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=groups)return;
 const KeyTarget& c=PerItem?contexts[i]:common;uint32_t hash[8];jackpot_hash64(words+std::size_t(i)*16,c.key,hash);
 if(debug){
  #pragma unroll
  for(int j=0;j<8;++j)debug[std::size_t(i)*8+j]=hash[j];
 }
 if(hash_meets_target(hash,c.target)){uint32_t slot=atomicAdd(found,1u);if(slot<capacity)indices[slot]=i;}
}
void checked(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
template<class T>struct Device {T* p=nullptr;explicit Device(std::size_t n){checked(cudaMalloc(&p,n*sizeof(T)));}~Device(){if(p)cudaFree(p);}Device(const Device&)=delete;Device&operator=(const Device&)=delete;};
}
cudaError_t launch_jackpot_filter(const uint32_t* words,std::size_t groups,KeyTarget context,
 uint32_t* indices,uint32_t* found,uint32_t capacity,cudaStream_t stream){
 if(!found||groups>std::numeric_limits<uint32_t>::max()||(!words&&groups)||(!indices&&capacity))return cudaErrorInvalidValue;
 auto e=cudaMemsetAsync(found,0,sizeof(uint32_t),stream);if(e!=cudaSuccess||groups==0)return e;
 filter_kernel<false><<<unsigned((groups+127)/128),128,0,stream>>>(words,uint32_t(groups),context,nullptr,indices,found,capacity,nullptr);
 return cudaGetLastError();
}
void check_jackpot_filter(const std::string& path){
 auto vectors=read_hash_vectors(path);const auto n=vectors.size();std::vector<uint32_t>words(n*16),expected,hashes(n*8),found(n+1,0xdeadbeefu);
 std::vector<KeyTarget>contexts(n);
 for(std::size_t i=0;i<n;++i){std::copy(vectors[i].transcript,vectors[i].transcript+16,words.begin()+i*16);contexts[i]=vectors[i].context;if(vectors[i].qualifies)expected.push_back(uint32_t(i));}
 Device<uint32_t>dwords(words.size()),dindices(n+1),dcount(1),dhash(n*8);Device<KeyTarget>dcontexts(n);
 checked(cudaMemcpy(dwords.p,words.data(),words.size()*4,cudaMemcpyHostToDevice));checked(cudaMemcpy(dcontexts.p,contexts.data(),n*sizeof(KeyTarget),cudaMemcpyHostToDevice));checked(cudaMemset(dcount.p,0,4));
 filter_kernel<true><<<unsigned((n+127)/128),128>>>(dwords.p,uint32_t(n),KeyTarget{},dcontexts.p,dindices.p,dcount.p,uint32_t(n),dhash.p);
 checked(cudaGetLastError());checked(cudaDeviceSynchronize());uint32_t count=0;checked(cudaMemcpy(&count,dcount.p,4,cudaMemcpyDeviceToHost));
 if(count!=expected.size())throw std::runtime_error("per-item found count mismatch");
 checked(cudaMemcpy(found.data(),dindices.p,count*4,cudaMemcpyDeviceToHost));std::sort(found.begin(),found.begin()+count);
 if(!std::equal(expected.begin(),expected.end(),found.begin()))throw std::runtime_error("per-item found indices mismatch");
 checked(cudaMemcpy(hashes.data(),dhash.p,n*8*4,cudaMemcpyDeviceToHost));
 for(std::size_t i=0;i<n;++i)if(!std::equal(vectors[i].expected,vectors[i].expected+8,hashes.begin()+i*8))throw std::runtime_error("GPU digest differs from official vector");
 // The production entry uses a SINGLE shared job key/target, unlike the per-item test above.
 KeyTarget common=contexts[0];expected.clear();
 for(std::size_t i=0;i<n;++i){uint32_t h[8];jackpot_hash64(words.data()+i*16,common.key,h);if(hash_meets_target(h,common.target))expected.push_back(uint32_t(i));}
 checked(launch_jackpot_filter(dwords.p,n,common,dindices.p,dcount.p,uint32_t(n),nullptr));checked(cudaDeviceSynchronize());checked(cudaMemcpy(&count,dcount.p,4,cudaMemcpyDeviceToHost));
 if(count!=expected.size())throw std::runtime_error("uniform-context count mismatch");
 checked(cudaMemcpy(found.data(),dindices.p,count*4,cudaMemcpyDeviceToHost));std::sort(found.begin(),found.begin()+count);
 if(!std::equal(expected.begin(),expected.end(),found.begin()))throw std::runtime_error("uniform-context indices mismatch");
 // Capacity1, zero capacity and empty input: total count and sentinel must remain correct.
 for(auto&x:common.target)x=0xffffffffu;
 std::fill(found.begin(),found.end(),0xdeadbeefu);checked(cudaMemcpy(dindices.p,found.data(),found.size()*4,cudaMemcpyHostToDevice));
 checked(launch_jackpot_filter(dwords.p,n,common,dindices.p,dcount.p,1,nullptr));checked(cudaDeviceSynchronize());checked(cudaMemcpy(&count,dcount.p,4,cudaMemcpyDeviceToHost));checked(cudaMemcpy(found.data(),dindices.p,8,cudaMemcpyDeviceToHost));
 if(count!=n||found[0]>=n||found[1]!=0xdeadbeefu)throw std::runtime_error("capacity1 count/sentinel mismatch");
 checked(launch_jackpot_filter(dwords.p,n,common,nullptr,dcount.p,0,nullptr));checked(cudaDeviceSynchronize());checked(cudaMemcpy(&count,dcount.p,4,cudaMemcpyDeviceToHost));if(count!=n)throw std::runtime_error("capacity0 count mismatch");
 checked(launch_jackpot_filter(nullptr,0,common,nullptr,dcount.p,0,nullptr));checked(cudaDeviceSynchronize());checked(cudaMemcpy(&count,dcount.p,4,cudaMemcpyDeviceToHost));if(count!=0)throw std::runtime_error("empty input mismatch");
 std::cout<<"{\"phase\":\"hash_filter_correctness\",\"passed\":true,\"official_vectors\":"<<n<<",\"uniform_context_passed\":true,\"capacity_edges_passed\":true}\n";
}
}
