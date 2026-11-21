#pragma once
#include "mapped_work.hpp"
#include "compact_hits.hpp"
#include <cuda_runtime.h>
#include <chrono>
#include <cstring>
namespace pearl_lab {
constexpr uint32_t transfer_result_capacity=4096;
inline void transfer_checked(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
struct TransferSlot{
 int8_t*host=nullptr;int8_t*device=nullptr;std::size_t capacity=0,a_bytes=0,b_bytes=0;cudaEvent_t begin=nullptr,end=nullptr;MiningWorkInfo info;uint64_t seq=0,generation=0;std::string path;bool computing=false;double CPU_copy_ms=0;
 TransferSlot(){transfer_checked(cudaEventCreate(&begin));try{transfer_checked(cudaEventCreate(&end));}catch(...){cudaEventDestroy(begin);begin=nullptr;throw;}}
 ~TransferSlot(){if(end)cudaEventSynchronize(end);if(device)cudaFree(device);if(host)cudaFreeHost(host);if(begin)cudaEventDestroy(begin);if(end)cudaEventDestroy(end);}
 uint32_t*result_count(){return reinterpret_cast<uint32_t*>(host+capacity);}
 CompactHit*result_hits(){return reinterpret_cast<CompactHit*>(host+capacity+sizeof(uint32_t));}
 void reserve(std::size_t bytes){if(computing)throw std::runtime_error("attempted transfer buffer reuse during compute");if(bytes<=capacity)return;transfer_checked(cudaEventSynchronize(end));if(device){transfer_checked(cudaFree(device));device=nullptr;}if(host){transfer_checked(cudaFreeHost(host));host=nullptr;}capacity=0;transfer_checked(cudaMalloc(&device,bytes));transfer_checked(cudaHostAlloc(&host,bytes+sizeof(uint32_t)+transfer_result_capacity*sizeof(CompactHit),cudaHostAllocDefault));cudaPointerAttributes attributes{};transfer_checked(cudaPointerGetAttributes(&attributes,host));if(attributes.type!=cudaMemoryTypeHost)throw std::runtime_error("CUDA host buffer is not pinned host memory");capacity=bytes;++generation;}
};
class TransferPool{
 public:
 TransferSlot slots[2];cudaStream_t stream=nullptr;cudaEvent_t epoch=nullptr;
 TransferPool(){int device=0;cudaDeviceProp properties{};transfer_checked(cudaGetDevice(&device));transfer_checked(cudaGetDeviceProperties(&properties,device));if(properties.asyncEngineCount<1)throw std::runtime_error("GPU has no asynchronous copy engine");transfer_checked(cudaStreamCreateWithFlags(&stream,cudaStreamNonBlocking));try{transfer_checked(cudaEventCreate(&epoch));transfer_checked(cudaEventRecord(epoch,stream));transfer_checked(cudaEventSynchronize(epoch));}catch(...){if(epoch)cudaEventDestroy(epoch);cudaStreamDestroy(stream);throw;}}
 ~TransferPool(){if(stream)cudaStreamSynchronize(stream);if(epoch)cudaEventDestroy(epoch);if(stream)cudaStreamDestroy(stream);}
 void prepare(int index,uint64_t seq,const std::string&path){auto&slot=slots[index];if(slot.computing)throw std::runtime_error("busy pinned slot");const MappedMiningWork w(path);if(!w.info.raw_input)throw std::runtime_error("overlap mode requires raw GPU-noise input");auto bytes=w.a_bytes+w.b_bytes;
  // Initial same-shape pair allocated BEFORE compute; no per-packet malloc in steady state.
  if(!slots[0].capacity&&!slots[1].capacity){std::size_t free=0,total=0;transfer_checked(cudaMemGetInfo(&free,&total));if(bytes*2+512ull*1024*1024>free)throw std::runtime_error("insufficient VRAM for two transfer slots");slots[0].reserve(bytes);slots[1].reserve(bytes);}
  slot.reserve(bytes);transfer_checked(cudaEventSynchronize(slot.end));const auto started=std::chrono::steady_clock::now();std::memcpy(slot.host,w.a,w.a_bytes);std::memcpy(slot.host+w.a_bytes,w.bt,w.b_bytes);slot.CPU_copy_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count();slot.info=w.info;slot.seq=seq;slot.path=path;slot.a_bytes=w.a_bytes;slot.b_bytes=w.b_bytes;
  transfer_checked(cudaEventRecord(slot.begin,stream));transfer_checked(cudaMemcpyAsync(slot.device,slot.host,bytes,cudaMemcpyHostToDevice,stream));transfer_checked(cudaEventRecord(slot.end,stream));
 }
};
}
