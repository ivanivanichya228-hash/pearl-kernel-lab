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
  for(int threads:{128,256,512}){
    cudaFuncAttributes a{};int blocks=0;check(resource_info(threads,pn,false,&a,&blocks));
    std::cout<<"{\"phase\":\"resources\",\"threads\":"<<threads<<",\"proof_n\":"<<pn
      <<",\"registers\":"<<a.numRegs<<",\"local_bytes_per_thread\":"<<a.localSizeBytes
      <<",\"shared_bytes_per_block\":"<<shared_bytes(pn)<<",\"active_blocks_per_SM\":"<<blocks<<"}\n";
  }
}
void verify(const std::string&root) {
  for(int i=0;i<6;++i){
    auto f=read_fixture(root+"/case-"+std::to_string(i)+".bin");
    Buffer<int8_t>a(f.a.size()),b(f.bt.size());Buffer<uint32_t>out(f.golden.transcript.size());
    Buffer<int32_t>matrix(f.golden.matrix.size());a.put(f.a);b.put(f.bt);
    for(int threads:{128,256,512}){
      check(launch(a.p,b.p,out.p,matrix.p,f.p,threads,nullptr));check(cudaDeviceSynchronize());
      if(out.get()!=f.golden.transcript||matrix.get()!=f.golden.matrix)
        throw std::runtime_error("GPU correctness mismatch fixture="+std::to_string(i)+" threads="+std::to_string(threads));
    }
  }
  std::cout<<"{\"phase\":\"correctness\",\"passed\":true,\"fixtures\":6,\"variants_per_fixture\":3,\"full_matrix_and_transcript\":true}\n";
}
double median(std::vector<double>x){std::sort(x.begin(),x.end());return x.size()%2?x[x.size()/2]:(x[x.size()/2-1]+x[x.size()/2])*0.5;}
double measure(const int8_t*a,const int8_t*b,uint32_t*out,Shape p,int threads,double duration,const char*pci) {
  cudaStream_t stream;check(cudaStreamCreateWithFlags(&stream,cudaStreamNonBlocking));
  cudaEvent_t begin,end;check(cudaEventCreate(&begin));check(cudaEventCreate(&end));
  for(int i=0;i<3;++i)check(launch(a,b,out,nullptr,p,threads,stream));
  check(cudaStreamSynchronize(stream));
  constexpr int batch=16;
  check(cudaStreamBeginCapture(stream,cudaStreamCaptureModeGlobal));
  for(int i=0;i<batch;++i)check(launch(a,b,out,nullptr,p,threads,stream));
  cudaGraph_t graph;check(cudaStreamEndCapture(stream,&graph));
  cudaGraphExec_t exec;check(cudaGraphInstantiate(&exec,graph,nullptr,nullptr,0));
  Power power(pci);power.start();std::vector<double>times;
  auto start=std::chrono::steady_clock::now();
  do {
    check(cudaEventRecord(begin,stream));check(cudaGraphLaunch(exec,stream));check(cudaEventRecord(end,stream));
    check(cudaEventSynchronize(end));float ms=0;check(cudaEventElapsedTime(&ms,begin,end));times.push_back(ms/batch);
  } while(std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()<duration);
  auto telemetry=power.json();double ms=median(times);
  std::cout<<"{\"phase\":\"benchmark\",\"threads\":"<<threads<<",\"median_ms\":"<<ms
    <<",\"batches\":"<<times.size()<<",\"graph_batch\":"<<batch
    <<",\"matrix_TOPS\":"<<(2.0*p.m*p.n*p.k/(ms*1e9))<<",\"telemetry\":"<<telemetry<<"}\n"<<std::flush;
  cudaGraphExecDestroy(exec);cudaGraphDestroy(graph);cudaEventDestroy(begin);cudaEventDestroy(end);cudaStreamDestroy(stream);
  return ms;
}
} // namespace
int main(int argc,char**argv){
  try {
    bool allow=false,concurrent=false;int device=0,candidate=128;std::string mode="check",fixtures="tests/fixtures";
    Shape shape{2048,6144,4096,128,16};double duration=2;
    for(int i=1;i<argc;++i){
      std::string s=argv[i];
      if(s=="--help"){
        std::cout<<"pearl-bench --run-gpu [--mode check|bench|info] [--device N]\n"
          <<"  [--fixtures DIR] [--m M --n N --k K --rank R --proof-n 8|16]\n"
          <<"  [--duration 1..10] [--candidate 128|512] [--allow-concurrent-miner]\n"
          <<"No GPU work without --run-gpu. No miner, clock, fan or power changes.\n"
          <<"Bench runs correctness first, then an A/B/B/A sequence. Matrix TOPS is NOT Pearl hashrate.\n";return 0;
      }
      if(s=="--run-gpu"){allow=true;continue;}
      if(s=="--allow-concurrent-miner"){concurrent=true;continue;}
      if(i+1==argc)throw std::runtime_error("missing argument for "+s);
      std::string v=argv[++i];
      if(s=="--mode")mode=v;else if(s=="--device")device=std::stoi(v);
      else if(s=="--candidate")candidate=std::stoi(v);
      else if(s=="--fixtures")fixtures=v;else if(s=="--duration")duration=std::stod(v);
      else if(s=="--m")shape.m=std::stoi(v);else if(s=="--n")shape.n=std::stoi(v);
      else if(s=="--k")shape.k=std::stoi(v);else if(s=="--rank")shape.rank=std::stoi(v);
      else if(s=="--proof-n")shape.proof_n=std::stoi(v);else throw std::runtime_error("unknown option: "+s);
    }
    if(!allow)throw std::runtime_error("GPU execution requires explicit --run-gpu");
    if((mode!="check"&&mode!="bench"&&mode!="info")||(candidate!=128&&candidate!=512)||device<0||device>31||!std::isfinite(duration)||duration<1||duration>10)
      throw std::runtime_error("invalid options");
    bool miner=miner_present();
    if(miner&&!concurrent)throw std::runtime_error("SRBMiner process found; no GPU work performed. Use a separate idle test GPU. Explicit --allow-concurrent-miner is required to override this guard; concurrent timings are not a speedup measurement.");
    shape.validate();check(cudaSetDevice(device));cudaDeviceProp prop{};check(cudaGetDeviceProperties(&prop,device));
    if(prop.major!=8||(prop.minor!=6&&prop.minor!=9))throw std::runtime_error("This experimental build targets SM86/SM89 only");
    char pci[32];check(cudaDeviceGetPCIBusId(pci,sizeof(pci),device));
    std::cout<<"{\"phase\":\"device\",\"name\":"<<quoted(prop.name)<<",\"pci\":"<<quoted(pci)
      <<",\"SMs\":"<<prop.multiProcessorCount<<",\"concurrent_miner_detected\":"<<(miner?"true":"false")<<"}\n";
    resources(shape.proof_n);if(mode=="info")return 0;
    verify(fixtures);if(mode=="check")return 0;
    const uint64_t bytes=uint64_t(shape.m+shape.n)*shape.k+uint64_t(shape.groups())*16*4*2;
    std::size_t free=0,total=0;check(cudaMemGetInfo(&free,&total));
    if(bytes+256*1024*1024>free)throw std::runtime_error("insufficient free GPU memory for benchmark");
    std::mt19937 rng(20261119);std::vector<int8_t>a(std::size_t(shape.m)*shape.k),b(std::size_t(shape.n)*shape.k);
    for(auto&x:a)x=int8_t(int(rng()%129)-64);for(auto&x:b)x=int8_t(int(rng()%129)-64);
    Buffer<int8_t>da(a.size()),db(b.size());Buffer<uint32_t>oa(shape.groups()*16),ob(shape.groups()*16);
    da.put(a);db.put(b);check(launch(da.p,db.p,oa.p,nullptr,shape,256,nullptr));check(launch(da.p,db.p,ob.p,nullptr,shape,candidate,nullptr));
    check(cudaDeviceSynchronize());if(oa.get()!=ob.get())throw std::runtime_error("benchmark-shape variant mismatch");
    std::cout<<"{\"phase\":\"benchmark_shape\",\"m\":"<<shape.m<<",\"n\":"<<shape.n<<",\"k\":"<<shape.k
      <<",\"rank\":"<<shape.rank<<",\"proof_n\":"<<shape.proof_n<<"}\n";
    double a1=measure(da.p,db.p,oa.p,shape,256,duration,pci);
    double b1=measure(da.p,db.p,ob.p,shape,candidate,duration,pci);
    double b2=measure(da.p,db.p,ob.p,shape,candidate,duration,pci);
    double a2=measure(da.p,db.p,oa.p,shape,256,duration,pci);
    std::cout<<"{\"phase\":\"summary\",\"arithmetic_correctness_passed\":true,\"candidate_over_256_speed_ratio\":"
      <<std::sqrt(a1*a2/(b1*b2))<<",\"candidate_threads\":"<<candidate<<",\"baseline\":\"our_256_thread_kernel_not_SRBMiner\",\"Pearl_hashrate_measured\":false}\n";
    return 0;
  }catch(const std::exception&e){std::cerr<<"ERROR: "<<e.what()<<"\n";return 1;}
}
