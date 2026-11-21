#include "filter.cuh"
#include "hash_vectors.hpp"
#include <algorithm>
#include <array>
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
__global__ void compact_filter_kernel(const uint32_t*words,uint32_t groups,KeyTarget context,
 CompactHit*hits,uint32_t*found,uint32_t capacity,HitGeometry geometry){
 uint32_t i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=groups)return;uint32_t hash[8];
 jackpot_hash64(words+std::size_t(i)*16,context.key,hash);
 if(hash_meets_target(hash,context.target)){
  uint32_t slot=atomicAdd(found,1u);
  if(slot<capacity){hits[slot].index=uint32_t(compact_global_index(i,geometry));
   #pragma unroll
   for(int j=0;j<16;++j)hits[slot].transcript[j]=words[std::size_t(i)*16+j];
  }
 }
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
cudaError_t launch_compact_filter(const uint32_t*words,uint32_t groups,KeyTarget context,
 CompactHit*hits,uint32_t*found,uint32_t capacity,HitGeometry geometry,cudaStream_t stream){
 if(!found||(!words&&groups)||(!hits&&capacity)||!valid_hit_geometry(groups,geometry))return cudaErrorInvalidValue;
 if(!groups)return cudaSuccess;
 compact_filter_kernel<<<unsigned((groups+127)/128),128,0,stream>>>(words,groups,context,hits,found,capacity,geometry);
 return cudaGetLastError();
}
void check_compact_filter(const std::string&path){
 const auto vectors=read_hash_vectors(path);const uint32_t n=uint32_t(vectors.size());if(n!=195)throw std::runtime_error("official vector count");
 std::vector<uint32_t>words(std::size_t(n)*16);for(uint32_t i=0;i<n;++i)std::copy(vectors[i].transcript,vectors[i].transcript+16,words.begin()+std::size_t(i)*16);
 Device<uint32_t>dw(words.size()),count(1);Device<CompactHit>dh(std::size_t(n)*2+1);const CompactHit sentinel={0xdeadbeefu,{0xcafef00du}};
 uint32_t cases=0;
 for(uint32_t pn:{8u,16u})for(uint32_t capacity:{0u,1u,n,n*2}){
  KeyTarget context=vectors[0].context;for(auto&x:context.target)x=0xffffffffu;
  checked(cudaMemcpy(dw.p,words.data(),words.size()*4,cudaMemcpyHostToDevice));checked(cudaMemset(count.p,0,4));
  checked(cudaMemcpy(dh.p+capacity,&sentinel,sizeof sentinel,cudaMemcpyHostToDevice));
  HitGeometry g1{16,0,pn*4,pn*16,pn},g2{4096,pn*8,pn*4,pn*16,pn};
  checked(launch_compact_filter(dw.p,n,context,capacity?dh.p:nullptr,count.p,capacity,g1,nullptr));
  // Overwrite slab between appends: compact transcripts must retain the FIRST bytes.
  checked(cudaMemset(dw.p,0,words.size()*4));
  checked(launch_compact_filter(dw.p,n,context,capacity?dh.p:nullptr,count.p,capacity,g2,nullptr));checked(cudaDeviceSynchronize());
  uint32_t found=0;checked(cudaMemcpy(&found,count.p,4,cudaMemcpyDeviceToHost));if(found!=n*2)throw std::runtime_error("compact append count/reset/overflow");
  CompactHit last{};checked(cudaMemcpy(&last,dh.p+capacity,sizeof last,cudaMemcpyDeviceToHost));if(last.index!=sentinel.index||last.transcript[0]!=sentinel.transcript[0])throw std::runtime_error("compact capacity sentinel overwritten");
  std::vector<CompactHit>got(capacity);if(capacity)checked(cudaMemcpy(got.data(),dh.p,capacity*sizeof(CompactHit),cudaMemcpyDeviceToHost));
  std::vector<uint32_t>seen;
  for(const auto&h:got){bool matched=false;for(uint32_t i=0;i<n;++i){if(h.index==compact_global_index(i,g1)){if(!std::equal(h.transcript,h.transcript+16,words.begin()+std::size_t(i)*16))throw std::runtime_error("compact transcript not retained");matched=true;break;}if(h.index==compact_global_index(i,g2)){for(auto x:h.transcript)if(x)throw std::runtime_error("second append transcript");matched=true;break;}}if(!matched)throw std::runtime_error("compact global index");seen.push_back(h.index);}
  std::sort(seen.begin(),seen.end());if(std::adjacent_find(seen.begin(),seen.end())!=seen.end())throw std::runtime_error("duplicate compact hit");
  if(capacity==n*2&&got.size()!=n*2)throw std::runtime_error("missing compact hit");++cases;
 }
 // Exact common target at a computed median: both hits and misses, local check only.
 auto context=vectors[0].context;HitGeometry g{32,16,64,128,16};std::vector<CompactHit>expected;
 std::vector<std::array<uint32_t,8>>digests(n);for(uint32_t i=0;i<n;++i)jackpot_hash64(words.data()+std::size_t(i)*16,context.key,digests[i].data());
 std::sort(digests.begin(),digests.end(),[](const auto&a,const auto&b){for(int j=7;j>=0;--j){if(a[j]!=b[j])return a[j]<b[j];}return false;});std::copy(digests[n/2].begin(),digests[n/2].end(),context.target);

 for(uint32_t i=0;i<n;++i){uint32_t h[8];jackpot_hash64(words.data()+std::size_t(i)*16,context.key,h);if(hash_meets_target(h,context.target)){CompactHit item{};item.index=uint32_t(compact_global_index(i,g));std::copy(words.begin()+std::size_t(i)*16,words.begin()+std::size_t(i+1)*16,item.transcript);expected.push_back(item);}}
 if(expected.empty()||expected.size()==n)throw std::runtime_error("mixed exact-target fixture must include both hits and misses");
 checked(cudaMemcpy(dw.p,words.data(),words.size()*4,cudaMemcpyHostToDevice));checked(cudaMemset(count.p,0,4));checked(launch_compact_filter(dw.p,n,context,dh.p,count.p,n,g,nullptr));checked(cudaDeviceSynchronize());uint32_t found=0;checked(cudaMemcpy(&found,count.p,4,cudaMemcpyDeviceToHost));if(found!=expected.size())throw std::runtime_error("compact exact target count");std::vector<CompactHit>got(found);if(found)checked(cudaMemcpy(got.data(),dh.p,found*sizeof(CompactHit),cudaMemcpyDeviceToHost));auto order=[](const CompactHit&a,const CompactHit&b){return a.index<b.index;};std::sort(got.begin(),got.end(),order);std::sort(expected.begin(),expected.end(),order);for(std::size_t i=0;i<got.size();++i)if(got[i].index!=expected[i].index||!std::equal(got[i].transcript,got[i].transcript+16,expected[i].transcript))throw std::runtime_error("compact exact target/transcript differs");
 checked(launch_compact_filter(nullptr,0,context,nullptr,count.p,0,g,nullptr));checked(cudaDeviceSynchronize());uint32_t after=0;checked(cudaMemcpy(&after,count.p,4,cudaMemcpyDeviceToHost));if(after!=found)throw std::runtime_error("empty append reset count");
 std::cout<<"{\"phase\":\"compact_filter_correctness\",\"passed\":true,\"official_vectors\":"<<n<<",\"capacity_cases\":"<<cases<<",\"append_and_transcript_retention\":true,\"exact_target_passed\":true,\"empty_preserves_count\":true}\n";
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
