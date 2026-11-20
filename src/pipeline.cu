#include "pipeline_fixture.hpp"
#include "kernel.cuh"
#include "filter.cuh"
#include <filesystem>
#include <iostream>
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
class MiningExecutor{
 Reusable<int8_t>a,b;Reusable<uint32_t>transcripts,indices,count;Stream stream;uint64_t generation=0;
 public:
 uint64_t run(const std::string&path,const std::string&output){
  if(output.empty()||std::filesystem::exists(output))throw std::runtime_error("new hits output path required");
  const MappedMiningWork w(path);MappingFence fence{stream.s};const auto&p=w.info.shape;constexpr int slab=8192;
  const std::size_t maxgroups=std::size_t(std::min(slab,p.m)/16)*(std::min(slab,p.n)/p.proof_n);
  if(w.a_bytes>a.capacity||w.b_bytes>b.capacity||maxgroups*16>transcripts.capacity||maxgroups>indices.capacity||!count.p){
   checked(cudaStreamSynchronize(stream.s));a.clear();b.clear();transcripts.clear();indices.clear();count.clear();
   std::size_t free=0,totalmem=0;checked(cudaMemGetInfo(&free,&totalmem));
   if(w.a_bytes+w.b_bytes+maxgroups*68+256ull*1024*1024>free)throw std::runtime_error("insufficient VRAM for explicit profile");
   a.allocate(w.a_bytes);b.allocate(w.b_bytes);transcripts.allocate(maxgroups*16);indices.allocate(maxgroups);count.allocate(1);++generation;
  }
  checked(cudaMemcpyAsync(a.p,w.a,w.a_bytes,cudaMemcpyHostToDevice,stream.s));checked(cudaMemcpyAsync(b.p,w.bt,w.b_bytes,cudaMemcpyHostToDevice,stream.s));
  std::vector<MiningHit>hits;
  for(int r=0;r<p.m;r+=slab){for(int c=0;c<p.n;c+=slab){
   Shape local{std::min(slab,p.m-r),std::min(slab,p.n-c),p.k,p.rank,p.proof_n};
   checked(launch(a.p+std::size_t(r)*p.k,b.p+std::size_t(c)*p.k,transcripts.p,nullptr,local,256,stream.s,64));
   checked(launch_jackpot_filter(transcripts.p,local.groups(),w.info.context,indices.p,count.p,uint32_t(local.groups()),stream.s));checked(cudaStreamSynchronize(stream.s));
   uint32_t found=0;checked(cudaMemcpy(&found,count.p,4,cudaMemcpyDeviceToHost));if(found>local.groups()||hits.size()+found>4096)throw std::runtime_error("hit queue bound exceeded; no partial output");
   std::vector<uint32_t>ix(found);if(found)checked(cudaMemcpy(ix.data(),indices.p,found*4,cudaMemcpyDeviceToHost));std::sort(ix.begin(),ix.end());
   for(auto i:ix){if(i>=local.groups())throw std::runtime_error("invalid device hit index");MiningHit h{};h.index=global_group_index(i,r,c,local.n,p.n,p.proof_n);checked(cudaMemcpy(h.transcript,transcripts.p+std::size_t(i)*16,64,cudaMemcpyDeviceToHost));hits.push_back(h);}
  }}
  write_mining_hits(w.info,hits,output,true);
  std::cout<<"{\"phase\":\"mining_batch\",\"groups\":"<<p.groups()<<",\"hits\":"<<hits.size()<<",\"target_modified\":false}\n";return generation;
 }
};
}
void mine_batch(const std::string&path,const std::string&output){MiningExecutor engine;engine.run(path,output);}
void mining_worker(const std::function<void()>&guard){MiningExecutor engine;serve_mining_worker([&](const std::string&i,const std::string&o){guard();auto result=engine.run(i,o);guard();return result;},"GPU");}
}
