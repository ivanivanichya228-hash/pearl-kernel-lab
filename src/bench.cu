#include "filter.cuh"
#include "noise.cuh"
#include "paused_guard.hpp"
#include "pipeline_fixture.hpp"
#include "mining_work.hpp"
#include "validation.hpp"
#include "kernel.cuh"
#include "fixture.hpp"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cctype>
#include <cmath>
#include <dlfcn.h>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <sstream>
#include <thread>

using namespace pearl_lab;
namespace {
void check(cudaError_t e) { if(e!=cudaSuccess) throw std::runtime_error(cudaGetErrorString(e)); }
template<class T> struct Buffer {
  T* p=nullptr; std::size_t n;
  explicit Buffer(std::size_t count):n(count){check(cudaMalloc(&p,n*sizeof(T)));}
  ~Buffer(){if(p)cudaFree(p);}
  Buffer(const Buffer&)=delete; Buffer&operator=(const Buffer&)=delete;
  void put(const std::vector<T>&v){if(v.size()!=n)throw std::runtime_error("buffer size");check(cudaMemcpy(p,v.data(),n*sizeof(T),cudaMemcpyHostToDevice));}
  std::vector<T> get(){std::vector<T>v(n);check(cudaMemcpy(v.data(),p,n*sizeof(T),cudaMemcpyDeviceToHost));return v;}
};
std::string quoted(const std::string&s){std::ostringstream o;o<<std::quoted(s);return o.str();}
bool miner_present() {
  std::error_code ec;
  for(const auto&d:std::filesystem::directory_iterator("/proc",ec)) {
    std::ifstream f(d.path()/"comm");std::string name;std::getline(f,name);
    std::transform(name.begin(),name.end(),name.begin(),[](unsigned char c){return std::tolower(c);});
    if(name.find("srbminer")!=std::string::npos)return true;
  }
  return false;
}
struct Power {
  void* lib=nullptr;void* handle=nullptr;bool initialized=false;
  using Init=int(*)();using GetHandle=int(*)(const char*,void**);
  using Read=int(*)(void*,unsigned*);using ReadKind=int(*)(void*,unsigned,unsigned*);
  Init shutdown=nullptr;Read power=nullptr,limit=nullptr;ReadKind temperature=nullptr,clock=nullptr;
  std::atomic<bool> stop{false};std::thread worker;
  std::vector<double> watts,clocks,temps;int errors=0;unsigned initial_limit=0;
  template<class F> F symbol(const char*n){return reinterpret_cast<F>(dlsym(lib,n));}
  explicit Power(const char*pci) {
    lib=dlopen("libnvidia-ml.so.1",RTLD_NOW|RTLD_LOCAL);if(!lib)return;
    auto init=symbol<Init>("nvmlInit_v2");shutdown=symbol<Init>("nvmlShutdown");
    auto get=symbol<GetHandle>("nvmlDeviceGetHandleByPciBusId_v2");
    if(!init||!shutdown||!get||init()!=0)return;initialized=true;
    if(get(pci,&handle)!=0){handle=nullptr;return;}
    power=symbol<Read>("nvmlDeviceGetPowerUsage");limit=symbol<Read>("nvmlDeviceGetPowerManagementLimit");
    temperature=symbol<ReadKind>("nvmlDeviceGetTemperature");clock=symbol<ReadKind>("nvmlDeviceGetClockInfo");
    if(limit)limit(handle,&initial_limit);
  }
  void start() {
    if(!handle||!power)return;
    worker=std::thread([this]{
      while(!stop.load()){
        unsigned x=0;
        if(power(handle,&x)==0)watts.push_back(x/1000.0);else++errors;
        if(clock&&clock(handle,1,&x)==0)clocks.push_back(x);
        if(temperature&&temperature(handle,0,&x)==0)temps.push_back(x);
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
      }
    });
  }
  void finish(){stop=true;if(worker.joinable())worker.join();}
  static double mean(const std::vector<double>&x){return std::accumulate(x.begin(),x.end(),0.0)/x.size();}
  std::string json(){
    finish();std::ostringstream o;o<<"{\"samples\":"<<watts.size()<<",\"read_errors\":"<<errors;
    if(!watts.empty())o<<",\"mean_W\":"<<mean(watts)<<",\"peak_W\":"<<*std::max_element(watts.begin(),watts.end());
    if(!clocks.empty())o<<",\"mean_sm_clock_MHz\":"<<mean(clocks);
    if(!temps.empty())o<<",\"peak_gpu_temp_C\":"<<*std::max_element(temps.begin(),temps.end());
    unsigned final_limit=0;
    if(limit&&handle&&initial_limit&&limit(handle,&final_limit)==0)
      o<<",\"power_limit_before_W\":"<<initial_limit/1000.0<<",\"power_limit_after_W\":"<<final_limit/1000.0;
    o<<"}";return o.str();
  }
  ~Power(){finish();if(initialized&&shutdown)shutdown();if(lib)dlclose(lib);}
};
void resources(int pn) {
  for(int variant:{128,256,512,64}){
    const int threads = variant == 64 ? 256 : variant;
    const int stage_k = variant == 64 ? 64 : 32;
    cudaFuncAttributes a{};int blocks=0;check(resource_info(threads,pn,false,&a,&blocks,stage_k));
    std::cout<<"{\"phase\":\"resources\",\"threads\":"<<threads<<",\"stage_k\":"<<stage_k<<",\"proof_n\":"<<pn
      <<",\"registers\":"<<a.numRegs<<",\"local_bytes_per_thread\":"<<a.localSizeBytes
      <<",\"shared_bytes_per_block\":"<<(stage_k == 64 ? stage64_shared_bytes(pn) : (threads == 128 ? 18432 : shared_bytes(pn)))<<",\"active_blocks_per_SM\":"<<blocks<<"}\n";
  }
}
void verify(const std::string&root, const std::string& export_path) {
  std::ofstream exported;
  if(!export_path.empty()) {
    exported.open(export_path);
    if(!exported)throw std::runtime_error("cannot open transcript export");
  }
  for(int i=0;i<6;++i){
    auto f=read_fixture(root+"/case-"+std::to_string(i)+".bin");
    Buffer<int8_t>a(f.a.size()),b(f.bt.size());Buffer<uint32_t>out(f.golden.transcript.size());
    Buffer<int32_t>matrix(f.golden.matrix.size());a.put(f.a);b.put(f.bt);
    for(int variant:{128,256,512,64}){
    const int threads = variant == 64 ? 256 : variant;
    const int stage_k = variant == 64 ? 64 : 32;
      out.put(std::vector<uint32_t>(f.golden.transcript.size(),0xa5a5a5a5u));
      matrix.put(std::vector<int32_t>(f.golden.matrix.size(),0x5a5a5a5a));
      check(launch(a.p,b.p,out.p,matrix.p,f.p,threads,nullptr,stage_k));check(cudaDeviceSynchronize());
      if(out.get()!=f.golden.transcript||matrix.get()!=f.golden.matrix)
        throw std::runtime_error("GPU correctness mismatch fixture="+std::to_string(i)+" threads="+std::to_string(threads));
      out.put(std::vector<uint32_t>(f.golden.transcript.size(),0xa5a5a5a5u));
      check(launch(a.p,b.p,out.p,nullptr,f.p,threads,nullptr,stage_k));
      check(cudaDeviceSynchronize());
      if(out.get()!=f.golden.transcript)
        throw std::runtime_error("non-debug transcript mismatch fixture="+std::to_string(i));
      if(exported.is_open() && variant==64) {
        auto values=out.get();exported<<"{\"case\":"<<i<<",\"transcript\":[";
        for(std::size_t j=0;j<values.size();++j){if(j)exported<<',';exported<<values[j];}
        exported<<"]}\n";
        if(!exported)throw std::runtime_error("transcript export failed");
      }
    }
  }
  std::cout<<"{\"phase\":\"correctness\",\"passed\":true,\"fixtures\":6,\"variants_per_fixture\":4,\"full_matrix_and_transcript\":true,\"non_debug_transcript_checked\":true}\n";
}
void verify384(const std::string&root,bool matrix_loads=false){
 for(int i=0;i<6;++i){auto f=read_fixture(root+"/case-"+std::to_string(i)+".bin");
  Buffer<int8_t>a(f.a.size()),b(f.bt.size());Buffer<uint32_t>out(f.golden.transcript.size());Buffer<int32_t>matrix(f.golden.matrix.size());a.put(f.a);b.put(f.bt);
  out.put(std::vector<uint32_t>(f.golden.transcript.size(),0xa5a5a5a5u));matrix.put(std::vector<int32_t>(f.golden.matrix.size(),0x5a5a5a5a));
  check(launch(a.p,b.p,out.p,matrix.p,f.p,384,nullptr,64,matrix_loads));check(cudaDeviceSynchronize());
  if(out.get()!=f.golden.transcript||matrix.get()!=f.golden.matrix)throw std::runtime_error("kernel384 matrix/transcript fixture="+std::to_string(i));
  out.put(std::vector<uint32_t>(f.golden.transcript.size(),0xa5a5a5a5u));check(launch(a.p,b.p,out.p,nullptr,f.p,384,nullptr,64,matrix_loads));check(cudaDeviceSynchronize());
  if(out.get()!=f.golden.transcript)throw std::runtime_error("kernel384 non-debug fixture="+std::to_string(i));
 }
 for(int pn:{8,16}){cudaFuncAttributes attr{};int blocks=0;check(resource_info(384,pn,false,&attr,&blocks,64,matrix_loads));if(attr.localSizeBytes||attr.numRegs>168||blocks<1)throw std::runtime_error("kernel384 resources/spills/occupancy");
  std::cout<<"{\"matrix_loads\":"<<(matrix_loads?"true":"false")<<",\"phase\":\"kernel384_resources\",\"proof_n\":"<<pn<<",\"registers\":"<<attr.numRegs<<",\"local_bytes\":"<<attr.localSizeBytes<<",\"active_blocks\":"<<blocks<<"}\n";
 }
 std::cout<<"{\"matrix_loads\":"<<(matrix_loads?"true":"false")<<",\"phase\":\"kernel384_correctness\",\"passed\":true,\"fixtures\":6,\"full_matrix_and_transcript\":true,\"non_debug_transcript_checked\":true,\"other_kernels_executed\":false}\n";
}
double median(std::vector<double>x){std::sort(x.begin(),x.end());return x.size()%2?x[x.size()/2]:(x[x.size()/2-1]+x[x.size()/2])*0.5;}
double measure(const int8_t*a,const int8_t*b,uint32_t*out,Shape p,int threads,double duration,const char*pci,int stage_k = 32, double warmup = 0, int round = 0, int leg = 0, bool matrix_loads = false) {
  cudaStream_t stream;check(cudaStreamCreateWithFlags(&stream,cudaStreamNonBlocking));
  cudaEvent_t begin,end;check(cudaEventCreate(&begin));check(cudaEventCreate(&end));
  for(int i=0;i<3;++i)check(launch(a,b,out,nullptr,p,threads,stream,stage_k,matrix_loads));
  check(cudaStreamSynchronize(stream));
  constexpr int batch=16;
  check(cudaStreamBeginCapture(stream,cudaStreamCaptureModeGlobal));
  for(int i=0;i<batch;++i)check(launch(a,b,out,nullptr,p,threads,stream,stage_k,matrix_loads));
  cudaGraph_t graph;check(cudaStreamEndCapture(stream,&graph));
  cudaGraphExec_t exec;check(cudaGraphInstantiate(&exec,graph,nullptr,nullptr,0));
  const auto warm_start=std::chrono::steady_clock::now();
  while(std::chrono::duration<double>(std::chrono::steady_clock::now()-warm_start).count()<warmup) {
    check(cudaGraphLaunch(exec,stream));check(cudaStreamSynchronize(stream));
  }
  Power power(pci);power.start();std::vector<double>times;
  auto start=std::chrono::steady_clock::now();
  do {
    check(cudaEventRecord(begin,stream));check(cudaGraphLaunch(exec,stream));check(cudaEventRecord(end,stream));
    check(cudaEventSynchronize(end));float ms=0;check(cudaEventElapsedTime(&ms,begin,end));times.push_back(ms/batch);
  } while(std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()<duration);
  auto telemetry=power.json();double ms=median(times);
  std::cout<<"{\"phase\":\"benchmark\",\"threads\":"<<threads<<",\"matrix_loads\":"<<(matrix_loads?"true":"false")<<",\"stage_k\":"<<stage_k<<",\"round\":"<<round<<",\"leg\":"<<leg<<",\"warmup_seconds\":"<<warmup<<",\"median_ms\":"<<ms
    <<",\"batches\":"<<times.size()<<",\"graph_batch\":"<<batch
    <<",\"matrix_TOPS\":"<<(2.0*p.m*p.n*p.k/(ms*1e9))<<",\"telemetry\":"<<telemetry<<"}\n"<<std::flush;
  cudaGraphExecDestroy(exec);cudaGraphDestroy(graph);cudaEventDestroy(begin);cudaEventDestroy(end);cudaStreamDestroy(stream);
  return ms;
}
} // namespace
int main(int argc,char**argv){
  try {
    bool allow=false,concurrent=false,matrix_loads=false;int paused_pid=0;uint64_t paused_ticks=0;int device=0,candidate=256,stage_k=64;std::string mode="check",fixtures="tests/fixtures",export_path,hash_vectors="pool/hash-vectors.bin",pipeline_fixture,pipeline_export,work_input,work_output,noise_reference_path;
    Shape shape{2048,6144,4096,128,16};ValidationPlan plan;
    for(int i=1;i<argc;++i){
      std::string s=argv[i];
      if(s=="--help"){
        std::cout<<"pearl-bench --run-gpu [--mode check|bench|info|filter-check|pipeline-check|mine-batch|worker|overlap-worker|noise-check|compact-check|kernel384-check|kernel384-compare|matrix-check|matrix-compare] [--device N]\n"
          <<"  [--fixtures DIR --export-transcripts FILE] [--hash-vectors FILE] [--pipeline-fixture FILE --export-pipeline FILE] [--work-input FILE --work-output FILE] [--noise-reference FILE] [--paused-pid PID --paused-start-ticks TICKS] [--m M --n N --k K --rank R --proof-n 8|16]\n"
          <<"  [--duration 1..10 --warmup 0..5 --rounds 1..3] [--candidate 128|256|384|512 --stage-k 32|64] [--allow-concurrent-miner] [--matrix-loads]\n"
          <<"No GPU work without --run-gpu. No miner, clock, fan or power changes.\n"
          <<"Bench runs correctness first, then an A/B/B/A sequence. Matrix TOPS is NOT Pearl hashrate.\n";return 0;
      }
      if(s=="--matrix-loads"){matrix_loads=true;continue;}
      if(s=="--run-gpu"){allow=true;continue;}
      if(s=="--allow-concurrent-miner"){concurrent=true;continue;}
      if(i+1==argc)throw std::runtime_error("missing argument for "+s);
      std::string v=argv[++i];
      if(s=="--paused-pid")paused_pid=std::stoi(v);else if(s=="--paused-start-ticks")paused_ticks=std::stoull(v);
      else if(s=="--mode")mode=v;else if(s=="--device")device=std::stoi(v);
      else if(s=="--stage-k")stage_k=std::stoi(v);
      else if(s=="--candidate")candidate=std::stoi(v);
      else if(s=="--noise-reference")noise_reference_path=v;
      else if(s=="--work-input")work_input=v;
      else if(s=="--work-output")work_output=v;
      else if(s=="--pipeline-fixture")pipeline_fixture=v;
      else if(s=="--export-pipeline")pipeline_export=v;
      else if(s=="--hash-vectors")hash_vectors=v;
      else if(s=="--export-transcripts")export_path=v;
      else if(s=="--fixtures")fixtures=v;else if(s=="--duration")plan.duration=std::stod(v);
      else if(s=="--warmup")plan.warmup=std::stod(v);
      else if(s=="--rounds")plan.rounds=std::stoi(v);
      else if(s=="--m")shape.m=std::stoi(v);else if(s=="--n")shape.n=std::stoi(v);
      else if(s=="--k")shape.k=std::stoi(v);else if(s=="--rank")shape.rank=std::stoi(v);
      else if(s=="--proof-n")shape.proof_n=std::stoi(v);else throw std::runtime_error("unknown option: "+s);
    }
    if(!allow)throw std::runtime_error("GPU execution requires explicit --run-gpu");
    if((mode!="check"&&mode!="bench"&&mode!="info"&&mode!="filter-check"&&mode!="pipeline-check"&&mode!="mine-batch"&&mode!="worker"&&mode!="overlap-worker"&&mode!="noise-check"&&mode!="compact-check"&&mode!="kernel384-check"&&mode!="kernel384-compare"&&mode!="matrix-check"&&mode!="matrix-compare")||(candidate!=128&&candidate!=256&&candidate!=384&&candidate!=512)||(stage_k!=32&&stage_k!=64)||(stage_k==64&&candidate!=256&&candidate!=384)||device<0||device>31)
      throw std::runtime_error("invalid options");
    if(matrix_loads&&(candidate!=384||stage_k!=64||(mode!="matrix-check"&&mode!="matrix-compare"&&mode!="worker"&&mode!="mine-batch")))throw std::runtime_error("matrix loads require384/stage64 and matrix mode/worker/mine-batch");
    if((mode=="matrix-check"||mode=="matrix-compare")&&(!matrix_loads||candidate!=384))throw std::runtime_error("matrix mode requires --matrix-loads --candidate 384");
    plan.validate();
    bool miner=miner_present();
    if(miner&&!concurrent)throw std::runtime_error("SRBMiner process found; no GPU work performed. Use a separate idle test GPU. Explicit --allow-concurrent-miner is required to override this guard; concurrent timings are not a speedup measurement.");
    if(mode=="worker"||mode=="overlap-worker"||mode=="noise-check"||mode=="compact-check"||mode=="kernel384-check"||mode=="kernel384-compare"||mode=="matrix-check"||mode=="matrix-compare"){if(paused_pid)require_paused_miner(paused_pid,paused_ticks);else if(miner)throw std::runtime_error("worker needs a paused original identity before CUDA initialization");}
    shape.validate();check(cudaSetDevice(device));cudaDeviceProp prop{};check(cudaGetDeviceProperties(&prop,device));
    if(prop.major!=8||(prop.minor!=6&&prop.minor!=9))throw std::runtime_error("This experimental build targets SM86/SM89 only");
    char pci[32];check(cudaDeviceGetPCIBusId(pci,sizeof(pci),device));
    std::cout<<"{\"phase\":\"device\",\"name\":"<<quoted(prop.name)<<",\"pci\":"<<quoted(pci)
      <<",\"SMs\":"<<prop.multiProcessorCount<<",\"concurrent_miner_detected\":"<<(miner?"true":"false")<<"}\n";
    if(mode=="matrix-check"){verify384(fixtures,true);return 0;}
    if(mode=="kernel384-check"){verify384(fixtures);return 0;}
    if(mode=="kernel384-compare"){
      if(shape.m!=8192||shape.n!=8192||shape.k!=4096||shape.rank!=256||shape.proof_n!=16||plan.rounds!=1||plan.duration!=1||plan.warmup!=0.25)throw std::runtime_error("kernel comparison requires exact bounded8192 profile, 1s legs/.25s warmup");
      std::mt19937 rng(71883);std::vector<int8_t>a(std::size_t(shape.m)*shape.k),b(std::size_t(shape.n)*shape.k);for(auto&x:a)x=int8_t(int(rng()%255)-127);for(auto&x:b)x=int8_t(int(rng()%255)-127);
      Buffer<int8_t>da(a.size()),db(b.size());Buffer<uint32_t>out(shape.groups()*16);da.put(a);db.put(b);double times[4]{};int order[4]={256,384,384,256};
      for(int leg=0;leg<4;++leg)times[leg]=measure(da.p,db.p,out.p,shape,order[leg],1,pci,64,.25,0,leg);
      const double ratio=(times[0]+times[3])/(times[1]+times[2]);const bool passed=ratio>1.02&&std::max(times[1],times[2])<std::min(times[0],times[3]);
      std::cout<<"{\"phase\":\"kernel384_comparison\",\"resident_input_only\":true,\"baseline_threads\":256,\"candidate_threads\":384,\"stage_k_both\":64,\"speed_ratio\":"<<ratio<<",\"candidate_faster_for_live\":"<<(passed?"true":"false")<<",\"live_hashrate_measured\":false}\n";return 0;
    }
    if(mode=="matrix-compare"){
      if(shape.m!=8192||shape.n!=8192||shape.k!=4096||shape.rank!=256||shape.proof_n!=16||plan.rounds!=1||plan.duration!=1||plan.warmup!=0.25)throw std::runtime_error("kernel comparison requires exact bounded8192 profile, 1s legs/.25s warmup");
      std::mt19937 rng(71883);std::vector<int8_t>a(std::size_t(shape.m)*shape.k),b(std::size_t(shape.n)*shape.k);for(auto&x:a)x=int8_t(int(rng()%255)-127);for(auto&x:b)x=int8_t(int(rng()%255)-127);
      Buffer<int8_t>da(a.size()),db(b.size());Buffer<uint32_t>out(shape.groups()*16);da.put(a);db.put(b);double times[4]{};int order[4]={0,1,1,0};
      for(int leg=0;leg<4;++leg)times[leg]=measure(da.p,db.p,out.p,shape,384,1,pci,64,.25,0,leg,order[leg]!=0);
      check(launch(da.p,db.p,out.p,nullptr,shape,384,nullptr,64,true));check(cudaDeviceSynchronize());
      Buffer<uint32_t>control(shape.groups()*16);check(launch(da.p,db.p,control.p,nullptr,shape,384,nullptr,64,false));check(cudaDeviceSynchronize());
      if(control.get()!=out.get())throw std::runtime_error("post-comparison transcript mismatch");
      const double ratio=(times[0]+times[3])/(times[1]+times[2]);const bool passed=ratio>1.02&&std::max(times[1],times[2])<std::min(times[0],times[3]);
      std::cout<<"{\"phase\":\"matrix_comparison\",\"resident_input_only\":true,\"baseline_threads\":384,\"candidate_threads\":384,\"stage_k_both\":64,\"baseline_matrix_loads\":false,\"candidate_matrix_loads\":true,\"post_compare_transcript_equal\":true,\"speed_ratio\":"<<ratio<<",\"candidate_faster_for_live\":"<<(passed?"true":"false")<<",\"live_hashrate_measured\":false}\n";return 0;
    }
    if(mode=="compact-check"){check_compact_filter(hash_vectors);return 0;}
    if(mode=="noise-check"){check_gpu_noise(work_input,noise_reference_path);return 0;}
    if(mode=="overlap-worker"){overlap_worker([&]{if(paused_pid)require_paused_miner(paused_pid,paused_ticks);else if(miner_present())throw std::runtime_error("SRBMiner appeared during overlap worker");},candidate);return 0;}
    if(mode=="worker"){if(miner&&(!paused_pid||!paused_ticks))throw std::runtime_error("persistent worker requires paused miner identity");
      mining_worker([&]{if(paused_pid)require_paused_miner(paused_pid,paused_ticks);else if(miner_present())throw std::runtime_error("SRBMiner appeared during worker lifetime");},candidate,matrix_loads);return 0;}
    if(mode=="mine-batch"){mine_batch(work_input,work_output,candidate,matrix_loads);return 0;}
    if(mode=="pipeline-check"){check_jackpot_filter(hash_vectors);check_batch_pipeline(pipeline_fixture,pipeline_export);return 0;}
    if(mode=="filter-check"){check_jackpot_filter(hash_vectors);return 0;}
    resources(shape.proof_n);if(mode=="info")return 0;
    verify(fixtures,export_path);if(mode=="check")return 0;
    const uint64_t bytes=uint64_t(shape.m+shape.n)*shape.k+uint64_t(shape.groups())*16*4*2;
    std::size_t free=0,total=0;check(cudaMemGetInfo(&free,&total));
    if(bytes+256*1024*1024>free)throw std::runtime_error("insufficient free GPU memory for benchmark");
    std::mt19937 rng(20261119);std::vector<int8_t>a(std::size_t(shape.m)*shape.k),b(std::size_t(shape.n)*shape.k);
    for(auto&x:a)x=int8_t(int(rng()%129)-64);for(auto&x:b)x=int8_t(int(rng()%129)-64);
    Buffer<int8_t>da(a.size()),db(b.size());Buffer<uint32_t>oa(shape.groups()*16),ob(shape.groups()*16);
    da.put(a);db.put(b);check(launch(da.p,db.p,oa.p,nullptr,shape,256,nullptr));check(launch(da.p,db.p,ob.p,nullptr,shape,candidate,nullptr,stage_k));
    check(cudaDeviceSynchronize());if(oa.get()!=ob.get())throw std::runtime_error("benchmark-shape variant mismatch");
    std::cout<<"{\"phase\":\"benchmark_shape\",\"m\":"<<shape.m<<",\"n\":"<<shape.n<<",\"k\":"<<shape.k
      <<",\"rank\":"<<shape.rank<<",\"proof_n\":"<<shape.proof_n<<"}\n";
    std::cout<<"{\"phase\":\"validation_plan\",\"rounds\":"<<plan.rounds
      <<",\"duration_seconds\":"<<plan.duration<<",\"warmup_seconds_per_leg\":"<<plan.warmup
      <<",\"scheduled_seconds_excluding_checks\":"<<plan.scheduled_seconds()<<"}\n";
    double log_sum=0,min_ratio=1e100,max_ratio=0;
    for(int round=0;round<plan.rounds;++round) {
      double times[4];
      for(int leg=0;leg<4;++leg) {
        const bool is_candidate=abba_order[leg]!=0;
        times[leg]=measure(da.p,db.p,is_candidate?ob.p:oa.p,shape,
          is_candidate?candidate:256,plan.duration,pci,is_candidate?stage_k:32,
          plan.warmup,round,leg);
      }
      const double ratio=std::sqrt(times[0]*times[3]/(times[1]*times[2]));
      log_sum+=std::log(ratio);min_ratio=std::min(min_ratio,ratio);max_ratio=std::max(max_ratio,ratio);
      std::cout<<"{\"phase\":\"round_summary\",\"round\":"<<round
        <<",\"candidate_over_256_speed_ratio\":"<<ratio<<"}\n";
    }
    check(cudaDeviceSynchronize());
    if(oa.get()!=ob.get())throw std::runtime_error("post-benchmark transcript mismatch");
    std::cout<<"{\"phase\":\"summary\",\"arithmetic_correctness_passed\":true,\"post_benchmark_transcript_equal\":true,\"candidate_over_256_speed_ratio\":"
      <<std::exp(log_sum/plan.rounds)<<",\"rounds\":"<<plan.rounds
      <<",\"min_round_ratio\":"<<min_ratio<<",\"max_round_ratio\":"<<max_ratio
      <<",\"candidate_threads\":"<<candidate<<",\"candidate_stage_k\":"<<stage_k
      <<",\"baseline\":\"our_256_thread_kernel_not_SRBMiner\",\"Pearl_hashrate_measured\":false}\n";
    return 0;
  }catch(const std::exception&e){std::cerr<<"ERROR: "<<e.what()<<"\n";return 1;}
}
