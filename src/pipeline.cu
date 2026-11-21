#include "pipeline_fixture.hpp"
#include "kernel.cuh"
#include "filter.cuh"
#include <filesystem>
#include <iostream>
#include <chrono>
namespace pearl_lab {
namespace {
void checked(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
template<class T>struct Device{T*p=nullptr;explicit Device(std::size_t n){checked(cudaMalloc(&p,n*sizeof(T)));}~Device(){if(p)cudaFree(p);}Device(const Device&)=delete;};
struct Stream{cudaStream_t s=nullptr;Stream(){checked(cudaStreamCreateWithFlags(&s,cudaStreamNonBlocking));}~Stream(){cudaStreamDestroy(s);}};
}
void check_batch_pipeline(const std::string& path,const std::string& export_path){
 if(export_path.empty()||std::filesystem::exists(export_path))throw std::runtime_error("new pipeline export path required");
 const auto f=read_pipeline_fixture(path);const auto groups=f.shape.groups();
 Device<int8_t>a(f.a.size()),bt(f.bt.size());Device<int32_t>matrix(f.matrix.size());Device<uint32_t>t(groups*16),indices(groups),count(1);Stream stream;
 checked(cudaMemcpyAsync(a.p,f.a.data(),f.a.size(),cudaMemcpyHostToDevice,stream.s));checked(cudaMemcpyAsync(bt.p,f.bt.data(),f.bt.size(),cudaMemcpyHostToDevice,stream.s));
 // Debug output checks the full final matrix, including all boundary tiles.
 checked(launch(a.p,bt.p,t.p,matrix.p,f.shape,256,stream.s,64));checked(cudaStreamSynchronize(stream.s));
 std::vector<int32_t>c(f.matrix.size());std::vector<uint32_t>words(groups*16),hit(groups);uint32_t total=0;
 checked(cudaMemcpy(c.data(),matrix.p,c.size()*4,cudaMemcpyDeviceToHost));checked(cudaMemcpy(words.data(),t.p,words.size()*4,cudaMemcpyDeviceToHost));
 if(c!=f.matrix||words!=f.transcripts)throw std::runtime_error("debug matrix/transcript differs from official fixture");
 // Production path: no intervening synchronization between producer and consumer.
 checked(cudaMemsetAsync(t.p,0xa5,words.size()*4,stream.s));
 checked(launch(a.p,bt.p,t.p,nullptr,f.shape,256,stream.s,64));
 checked(launch_jackpot_filter(t.p,groups,f.context,indices.p,count.p,uint32_t(groups),stream.s));checked(cudaStreamSynchronize(stream.s));
 checked(cudaMemcpy(&total,count.p,4,cudaMemcpyDeviceToHost));if(total>groups)throw std::runtime_error("unexpected queue overflow");
 hit.resize(total);checked(cudaMemcpy(hit.data(),indices.p,total*4,cudaMemcpyDeviceToHost));checked(cudaMemcpy(words.data(),t.p,words.size()*4,cudaMemcpyDeviceToHost));std::sort(hit.begin(),hit.end());
 if(words!=f.transcripts||hit!=f.hits)throw std::runtime_error("production transcript/filter mismatch");
 // Export values copied from DEVICE, never substitute fixture reference values.
 std::ofstream out(export_path,std::ios::binary);if(!out)throw std::runtime_error("open pipeline export");
 out<<"{\"job_fingerprint\":\""<<f.fingerprint<<"\",\"batch_id\":\""<<f.batch_id<<"\",\"GPU_executed\":true,\"hit_indices\":[";
 for(std::size_t i=0;i<hit.size();++i){if(i)out<<',';out<<hit[i];}out<<"],\"transcripts\":[";
 for(std::size_t i=0;i<groups;++i){if(i)out<<',';out<<'[';for(int j=0;j<16;++j){if(j)out<<',';out<<words[i*16+j];}out<<']';}out<<"]}\n";out.close();if(!out)throw std::runtime_error("pipeline export write");
 std::cout<<"{\"phase\":\"pipeline_correctness\",\"passed\":true,\"groups\":"<<groups<<",\"hits\":"<<total<<",\"debug_matrix_checked\":true,\"non_debug_transcript_checked\":true,\"ordered_stream\":true,\"network_used\":false}\n";
}
}

#include "mining_work.hpp"
#include "noise.cuh"
#include "mapped_work.hpp"
#include "worker_protocol.hpp"
namespace pearl_lab {
namespace {
template<class T>struct Reusable{
 T*p=nullptr;std::size_t capacity=0;
 void clear(){if(p)checked(cudaFree(p));p=nullptr;capacity=0;}
 void allocate(std::size_t n){checked(cudaMalloc(&p,n*sizeof(T)));capacity=n;}
 ~Reusable(){if(p)cudaFree(p);}
};
struct MappingFence{cudaStream_t stream;~MappingFence(){cudaStreamSynchronize(stream);}};
struct EventMarks{
 cudaEvent_t e[5]{};
 EventMarks(){try{for(auto&x:e)checked(cudaEventCreate(&x));}catch(...){for(auto x:e)if(x)cudaEventDestroy(x);throw;}}
 ~EventMarks(){for(auto x:e)if(x)cudaEventDestroy(x);}
 float elapsed(int a,int b){float ms=0;checked(cudaEventElapsedTime(&ms,e[a],e[b]));return ms;}
};
class MiningExecutor{
 Reusable<int8_t>a,b,uniform;Reusable<uint32_t>transcripts,count,permutation;Reusable<CompactHit>packed;Stream stream;uint64_t generation=0;int threads;
 public:
 explicit MiningExecutor(int kernel_threads=256):threads(kernel_threads){if(threads!=256&&threads!=384)throw std::runtime_error("kernel threads");}
 uint64_t run(const std::string&path,const std::string&output){
  const auto started=std::chrono::steady_clock::now();
  if(output.empty()||std::filesystem::exists(output))throw std::runtime_error("new hits output path required");
  const MappedMiningWork w(path);MappingFence fence{stream.s};const auto&p=w.info.shape;constexpr int slab=8192;constexpr uint32_t capacity=4096;
  const std::size_t maxgroups=std::size_t(std::min(slab,p.m)/16)*(std::min(slab,p.n)/p.proof_n);
  const std::size_t uniform_bytes=w.info.raw_input?std::size_t(std::max(p.m,p.n))*p.rank:0;
  if(uniform_bytes>uniform.capacity||(w.info.raw_input&&std::size_t(p.k*2)>permutation.capacity)||w.a_bytes>a.capacity||w.b_bytes>b.capacity||maxgroups*16>transcripts.capacity||!count.p||packed.capacity<capacity){
   checked(cudaStreamSynchronize(stream.s));a.clear();b.clear();transcripts.clear();count.clear();uniform.clear();permutation.clear();packed.clear();
   std::size_t free=0,totalmem=0;checked(cudaMemGetInfo(&free,&totalmem));
   if(w.a_bytes+w.b_bytes+maxgroups*64+capacity*sizeof(CompactHit)+uniform_bytes+std::size_t(p.k)*8+256ull*1024*1024>free)throw std::runtime_error("insufficient VRAM for explicit profile");
   a.allocate(w.a_bytes);b.allocate(w.b_bytes);transcripts.allocate(maxgroups*16);count.allocate(1);packed.allocate(capacity);if(w.info.raw_input){uniform.allocate(uniform_bytes);permutation.allocate(p.k*2);}++generation;
  }
  EventMarks marks;checked(cudaEventRecord(marks.e[0],stream.s));
  checked(cudaMemcpyAsync(a.p,w.a,w.a_bytes,cudaMemcpyHostToDevice,stream.s));checked(cudaMemcpyAsync(b.p,w.bt,w.b_bytes,cudaMemcpyHostToDevice,stream.s));checked(cudaEventRecord(marks.e[1],stream.s));
  if(w.info.raw_input){
   checked(cudaMemsetAsync(count.p,0,4,stream.s));
   NoiseKey ka{},kb{};std::copy(w.info.context.key,w.info.context.key+8,ka.key);std::copy(w.info.b_noise_key,w.info.b_noise_key+8,kb.key);ka.is_a=true;kb.is_a=false;
   checked(launch_apply_noise(a.p,p.m,p.k,p.rank,ka,uniform.p,permutation.p,count.p,stream.s));checked(launch_apply_noise(b.p,p.n,p.k,p.rank,kb,uniform.p,permutation.p,count.p,stream.s));
   checked(cudaEventRecord(marks.e[2],stream.s));checked(cudaStreamSynchronize(stream.s));uint32_t error=0;checked(cudaMemcpy(&error,count.p,4,cudaMemcpyDeviceToHost));if(error)throw std::runtime_error("GPU raw/noisy range error");
  }else checked(cudaEventRecord(marks.e[2],stream.s));
  // One bounded append queue for the ENTIRE batch. A filter copies winning words
  // on this same stream BEFORE the next GEMM overwrites the shared transcript slab.
  checked(cudaMemsetAsync(count.p,0,4,stream.s));uint32_t slabs=0;
  for(int r=0;r<p.m;r+=slab){for(int c=0;c<p.n;c+=slab){
   Shape local{std::min(slab,p.m-r),std::min(slab,p.n-c),p.k,p.rank,p.proof_n};
   checked(launch(a.p+std::size_t(r)*p.k,b.p+std::size_t(c)*p.k,transcripts.p,nullptr,local,threads,stream.s,64));
   checked(launch_compact_filter(transcripts.p,uint32_t(local.groups()),w.info.context,packed.p,count.p,capacity,HitGeometry{uint32_t(r),uint32_t(c),uint32_t(local.n),uint32_t(p.n),uint32_t(p.proof_n)},stream.s));++slabs;
  }}
  checked(cudaEventRecord(marks.e[3],stream.s));uint32_t found=0;
  checked(cudaMemcpyAsync(&found,count.p,4,cudaMemcpyDeviceToHost,stream.s));checked(cudaStreamSynchronize(stream.s));
  if(found>capacity)throw std::runtime_error("compact hit queue overflow; no partial output");
  std::vector<CompactHit>collected(found);if(found)checked(cudaMemcpyAsync(collected.data(),packed.p,found*sizeof(CompactHit),cudaMemcpyDeviceToHost,stream.s));
  checked(cudaEventRecord(marks.e[4],stream.s));checked(cudaStreamSynchronize(stream.s));
  std::sort(collected.begin(),collected.end(),[](const CompactHit&a,const CompactHit&b){return a.index<b.index;});
  std::vector<MiningHit>hits;hits.reserve(found);for(const auto&item:collected){if(item.index>=p.groups()||(!hits.empty()&&hits.back().index==item.index))throw std::runtime_error("compact global index/duplicate");MiningHit h{};h.index=item.index;std::copy(item.transcript,item.transcript+16,h.transcript);hits.push_back(h);}
  write_mining_hits(w.info,hits,output,true);
  const auto wall_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count();
  std::cout<<"{\"phase\":\"mining_batch\",\"groups\":"<<p.groups()<<",\"kernel_threads\":"<<threads<<",\"hits\":"<<hits.size()<<",\"compact_hit_collection\":true,\"slabs\":"<<slabs<<",\"result_count_readbacks\":1,\"GPU_noise_applied\":"<<(w.info.raw_input?"true":"false")<<",\"GPU_noise_milliseconds\":"<<marks.elapsed(1,2)<<",\"H2D_phase_milliseconds\":"<<marks.elapsed(0,1)<<",\"compute_filter_phase_milliseconds\":"<<marks.elapsed(2,3)<<",\"result_copy_phase_milliseconds\":"<<marks.elapsed(3,4)<<",\"native_batch_wall_milliseconds\":"<<wall_ms<<",\"target_modified\":false}\n";return generation;
 }
};
}
void mine_batch(const std::string&path,const std::string&output,int kernel_threads){MiningExecutor engine(kernel_threads);engine.run(path,output);}
void mining_worker(const std::function<void()>&guard,int kernel_threads){MiningExecutor engine(kernel_threads);serve_mining_worker([&](const std::string&i,const std::string&o){guard();auto result=engine.run(i,o);guard();return result;},"GPU");}
}
