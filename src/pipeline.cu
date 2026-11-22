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
#include "request_inbox.hpp"
#include "transfer_pool.cuh"
#include <thread>
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
 Reusable<int8_t>a,b,uniform;Reusable<uint32_t>transcripts,count,permutation;Reusable<CompactHit>packed;Stream stream;uint64_t generation=0;int threads;bool matrix_loads;bool two_cta;bool triple_stage;bool fused_stage;bool singlepass;
 public:
 explicit MiningExecutor(int kernel_threads=256,bool loads=false,bool compact=false,bool triple=false,bool fused=false,bool single=false):threads(kernel_threads),matrix_loads(loads),two_cta(compact),triple_stage(triple),fused_stage(fused),singlepass(single){if(single&&!fused)throw std::runtime_error("singlepass requires fused");if(fused&&(!triple||kernel_threads!=384||loads||compact))throw std::runtime_error("fused needs triple384 exclusively");if((threads!=256&&threads!=384)||(loads&&threads!=384)||(compact&&(threads!=256||loads))||(triple&&(threads!=384||loads||compact)))throw std::runtime_error("kernel threads/matrix loads");}
 uint64_t run(const std::string&path,const std::string&output,TransferSlot*input=nullptr,cudaEvent_t epoch=nullptr,const std::function<void(cudaEvent_t)>&overlap={}){
  const auto started=std::chrono::steady_clock::now();
  if(output.empty()||std::filesystem::exists(output))throw std::runtime_error("new hits output path required");
  std::unique_ptr<MappedMiningWork>mapped;if(!input)mapped=std::make_unique<MappedMiningWork>(path);
  const MiningWorkInfo&info=input?input->info:mapped->info;const auto a_bytes=input?input->a_bytes:mapped->a_bytes,b_bytes=input?input->b_bytes:mapped->b_bytes;MappingFence fence{stream.s};const auto&p=info.shape;constexpr int slab=8192;constexpr uint32_t capacity=transfer_result_capacity;
  const std::size_t maxgroups=fused_stage?0:std::size_t(std::min(slab,p.m)/16)*(std::min(slab,p.n)/p.proof_n);
  const std::size_t uniform_bytes=info.raw_input?std::size_t(std::max(p.m,p.n))*p.rank:0;
  if(uniform_bytes>uniform.capacity||(info.raw_input&&std::size_t(p.k*2)>permutation.capacity)||(!input&&(a_bytes>a.capacity||b_bytes>b.capacity))||maxgroups*16>transcripts.capacity||!count.p||packed.capacity<capacity){
   checked(cudaStreamSynchronize(stream.s));a.clear();b.clear();transcripts.clear();count.clear();uniform.clear();permutation.clear();packed.clear();
   std::size_t free=0,totalmem=0;checked(cudaMemGetInfo(&free,&totalmem));
   if(a_bytes+b_bytes+maxgroups*64+capacity*sizeof(CompactHit)+uniform_bytes+std::size_t(p.k)*8+256ull*1024*1024>free)throw std::runtime_error("insufficient VRAM for explicit profile");
   if(!input){a.allocate(a_bytes);b.allocate(b_bytes);}if(maxgroups)transcripts.allocate(maxgroups*16);count.allocate(1);packed.allocate(capacity);if(info.raw_input){uniform.allocate(uniform_bytes);permutation.allocate(p.k*2);}++generation;
  }
  int8_t*device_a=input?input->device:a.p;int8_t*device_b=input?input->device+a_bytes:b.p;
  EventMarks marks;checked(cudaEventRecord(marks.e[0],stream.s));
  if(input){if(input->path!=path||input->computing)throw std::runtime_error("staged input identity/reuse");input->computing=true;checked(cudaStreamWaitEvent(stream.s,input->end,0));}
  else{checked(cudaMemcpyAsync(device_a,mapped->a,a_bytes,cudaMemcpyHostToDevice,stream.s));checked(cudaMemcpyAsync(device_b,mapped->bt,b_bytes,cudaMemcpyHostToDevice,stream.s));}checked(cudaEventRecord(marks.e[1],stream.s));
  if(info.raw_input){
   checked(cudaMemsetAsync(count.p,0,4,stream.s));
   NoiseKey ka{},kb{};std::copy(info.context.key,info.context.key+8,ka.key);std::copy(info.b_noise_key,info.b_noise_key+8,kb.key);ka.is_a=true;kb.is_a=false;
   checked(launch_apply_noise(device_a,p.m,p.k,p.rank,ka,uniform.p,permutation.p,count.p,stream.s));checked(launch_apply_noise(device_b,p.n,p.k,p.rank,kb,uniform.p,permutation.p,count.p,stream.s));
   checked(cudaEventRecord(marks.e[2],stream.s));checked(cudaStreamSynchronize(stream.s));uint32_t error=0;checked(cudaMemcpy(&error,count.p,4,cudaMemcpyDeviceToHost));if(error)throw std::runtime_error("GPU raw/noisy range error");
  }else checked(cudaEventRecord(marks.e[2],stream.s));
  // One bounded append queue for the ENTIRE batch. A filter copies winning words
  // on this same stream BEFORE the next GEMM overwrites the shared transcript slab.
  checked(cudaMemsetAsync(count.p,0,4,stream.s));uint32_t slabs=0;
  for(int r=0;r<p.m;r+=slab){for(int c=0;c<p.n;c+=slab){
   Shape local{std::min(slab,p.m-r),std::min(slab,p.n-c),p.k,p.rank,p.proof_n};
   HitGeometry geometry{uint32_t(r),uint32_t(c),uint32_t(local.n),uint32_t(p.n),uint32_t(p.proof_n)};
   if(fused_stage)checked((singlepass?launch_singlepass:launch_fused)(device_a+std::size_t(r)*p.k,device_b+std::size_t(c)*p.k,local,info.context,packed.p,count.p,capacity,geometry,stream.s));
   else{
    checked(launch(device_a+std::size_t(r)*p.k,device_b+std::size_t(c)*p.k,transcripts.p,nullptr,local,threads,stream.s,64,matrix_loads,two_cta,triple_stage));
    checked(launch_compact_filter(transcripts.p,uint32_t(local.groups()),info.context,packed.p,count.p,capacity,geometry,stream.s));
   }++slabs;
  }}
  checked(cudaEventRecord(marks.e[3],stream.s));if(overlap)overlap(marks.e[3]);uint32_t found=0;uint32_t*host_count=input?input->result_count():&found;
  checked(cudaMemcpyAsync(host_count,count.p,4,cudaMemcpyDeviceToHost,stream.s));checked(cudaStreamSynchronize(stream.s));if(input)found=*host_count;
  if(found>capacity)throw std::runtime_error("compact hit queue overflow; no partial output");
  std::vector<CompactHit>collected(found);if(found)checked(cudaMemcpyAsync(input?input->result_hits():collected.data(),packed.p,found*sizeof(CompactHit),cudaMemcpyDeviceToHost,stream.s));
  checked(cudaEventRecord(marks.e[4],stream.s));checked(cudaStreamSynchronize(stream.s));if(input&&found)std::copy_n(input->result_hits(),found,collected.begin());
  std::sort(collected.begin(),collected.end(),[](const CompactHit&a,const CompactHit&b){return a.index<b.index;});
  std::vector<MiningHit>hits;hits.reserve(found);for(const auto&item:collected){if(item.index>=p.groups()||(!hits.empty()&&hits.back().index==item.index))throw std::runtime_error("compact global index/duplicate");MiningHit h{};h.index=item.index;std::copy(item.transcript,item.transcript+16,h.transcript);hits.push_back(h);}
  write_mining_hits(info,hits,output,true);
  if(input){float begin_ms=0,end_ms=0,compute_begin=0,compute_end=0;checked(cudaEventElapsedTime(&begin_ms,epoch,input->begin));checked(cudaEventElapsedTime(&end_ms,epoch,input->end));checked(cudaEventElapsedTime(&compute_begin,epoch,marks.e[2]));checked(cudaEventElapsedTime(&compute_end,epoch,marks.e[3]));
   std::cout<<"{\"phase\":\"transfer_stage\",\"seq\":"<<input->seq<<",\"pinned\":true,\"slot\":"<<(input->seq%2)<<",\"slot_generation\":"<<input->generation<<",\"raw_bytes\":"<<a_bytes+b_bytes<<",\"CPU_copy_ms\":"<<input->CPU_copy_ms<<",\"copy_begin_ms\":"<<begin_ms<<",\"copy_end_ms\":"<<end_ms<<",\"compute_begin_ms\":"<<compute_begin<<",\"compute_end_ms\":"<<compute_end<<"}\n";input->computing=false;
  }
  float transfer_ms=marks.elapsed(0,1);if(input)checked(cudaEventElapsedTime(&transfer_ms,input->begin,input->end));
  const auto wall_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count();
  std::cout<<"{\"phase\":\"mining_batch\",\"groups\":"<<p.groups()<<",\"kernel_threads\":"<<threads<<",\"triple_stage\":"<<(triple_stage?"true":"false")<<",\"fused_stage\":"<<(fused_stage?"true":"false")<<",\"singlepass_transcript_requested\":"<<(singlepass?"true":"false")<<",\"singlepass_transcript_applied\":"<<((singlepass&&p.k==16*p.rank)?"true":"false")<<",\"global_transcript_materialized\":"<<(fused_stage?"false":"true")<<",\"pipeline_stages\":"<<((triple_stage&&p.proof_n==16)?3:2)<<",\"two_cta\":"<<(two_cta?"true":"false")<<",\"matrix_loads\":"<<(matrix_loads?"true":"false")<<",\"pinned_transfer_overlap\":"<<(input?"true":"false")<<",\"hits\":"<<hits.size()<<",\"compact_hit_collection\":true,\"slabs\":"<<slabs<<",\"result_count_readbacks\":1,\"GPU_noise_applied\":"<<(info.raw_input?"true":"false")<<",\"GPU_noise_milliseconds\":"<<marks.elapsed(1,2)<<",\"H2D_phase_milliseconds\":"<<transfer_ms<<",\"input_ready_wait_milliseconds\":"<<(input?marks.elapsed(0,1):0)<<",\"compute_filter_phase_milliseconds\":"<<marks.elapsed(2,3)<<",\"result_copy_phase_milliseconds\":"<<marks.elapsed(3,4)<<",\"native_batch_wall_milliseconds\":"<<wall_ms<<",\"target_modified\":false}\n";return generation;
 }
};
}
void overlap_worker(const std::function<void()>&guard,int kernel_threads){
 TransferPool pool;MiningExecutor engine(kernel_threads);RequestInbox inbox;std::optional<WorkerRequest>next;int next_slot=0;uint64_t completed=0;
 std::cout<<"{\"phase\":\"worker_ready\",\"protocol\":2,\"backend\":\"GPU\",\"transfer_slots\":2,\"pid\":"<<getpid()<<"}\n"<<std::flush;
 while(true){WorkerRequest request;int slot;
  if(next){request=std::move(*next);next.reset();slot=next_slot;}
  else{request=*inbox.take(true);if(request.quit)return;guard();slot=int(request.seq%2);pool.prepare(slot,request.seq,request.input);std::cout<<"{\"phase\":\"transfer_queued\",\"seq\":"<<request.seq<<",\"prefetch\":false}\n"<<std::flush;}
  if(request.quit)return;guard();
  auto generation=engine.run(request.input,request.output,&pool.slots[slot],pool.epoch,[&](cudaEvent_t done){
   while(true){auto status=cudaEventQuery(done);if(status==cudaSuccess)break;if(status!=cudaErrorNotReady)checked(status);else{auto last=cudaGetLastError();if(last!=cudaSuccess&&last!=cudaErrorNotReady)checked(last);}
    if(!next){auto pending=inbox.take(false);if(pending){next=std::move(*pending);if(!next->quit){guard();next_slot=1-slot;pool.prepare(next_slot,next->seq,next->input);std::cout<<"{\"phase\":\"transfer_queued\",\"seq\":"<<next->seq<<",\"prefetch\":true}\n"<<std::flush;}}}
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
   }
  });guard();++completed;
  std::cout<<"{\"phase\":\"worker_done\",\"seq\":"<<request.seq<<",\"requests_completed\":"<<completed<<",\"resource_generation\":"<<generation<<",\"pid\":"<<getpid()<<"}\n"<<std::flush;
 }
}
void mine_batch(const std::string&path,const std::string&output,int kernel_threads,bool matrix_loads,bool two_cta,bool triple_stage,bool fused_stage,bool singlepass){MiningExecutor engine(kernel_threads,matrix_loads,two_cta,triple_stage,fused_stage,singlepass);engine.run(path,output);}
void mining_worker(const std::function<void()>&guard,int kernel_threads,bool matrix_loads,bool two_cta,bool triple_stage,bool fused_stage,bool singlepass){MiningExecutor engine(kernel_threads,matrix_loads,two_cta,triple_stage,fused_stage,singlepass);serve_mining_worker([&](const std::string&i,const std::string&o){guard();auto result=engine.run(i,o);guard();return result;},"GPU");}
}
