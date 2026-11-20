#pragma once
#include "contract.hpp"
#include "jackpot_hash.hpp"
#include <fstream>
#include <sstream>
#include <string>
namespace pearl_lab {
struct MiningWork{Shape shape;KeyTarget context{};std::string fingerprint,batch_id;std::vector<int8_t>a,bt;};
inline MiningWork read_mining_work(const std::string& path){
 std::ifstream f(path,std::ios::binary);if(!f)throw std::runtime_error("open work");
 auto bytes=[&](void*p,std::size_t n){if(!f.read(static_cast<char*>(p),n))throw std::runtime_error("truncated work");};
 auto u32=[&](){unsigned char b[4];bytes(b,4);return uint32_t(b[0])|(uint32_t(b[1])<<8)|(uint32_t(b[2])<<16)|(uint32_t(b[3])<<24);};
 auto hex32=[&](){unsigned char b[32];bytes(b,32);std::string s;const char*h="0123456789abcdef";for(auto x:b){s+=h[x>>4];s+=h[x&15];}return s;};
 char magic[8];bytes(magic,8);if(std::string(magic,8)!="PRLWORK1")throw std::runtime_error("work magic");
 MiningWork w;w.shape={int(u32()),int(u32()),int(u32()),int(u32()),int(u32())};const auto&p=w.shape;
 if(p.m<=0||p.n<=0||p.m>131072||p.n>131072||p.k>8192||uint64_t(p.m+p.n)*p.k>(1ull<<31))throw std::runtime_error("work bounds");
 Shape local{16,p.proof_n,p.k,p.rank,p.proof_n};local.validate();if(p.m%16||p.n%p.proof_n)throw std::runtime_error("work geometry");
 w.fingerprint=hex32();w.batch_id=hex32();for(auto&x:w.context.key)x=u32();for(auto&x:w.context.target)x=u32();
 w.a.resize(std::size_t(p.m)*p.k);w.bt.resize(std::size_t(p.n)*p.k);bytes(w.a.data(),w.a.size());bytes(w.bt.data(),w.bt.size());
 if(f.peek()!=std::char_traits<char>::eof())throw std::runtime_error("trailing work bytes");
 return w;
}
struct MiningHit{uint32_t index;uint32_t transcript[16];};
inline uint32_t global_group_index(uint32_t local,int row0,int col0,int local_n,int full_n,int pn){
 return uint32_t((uint64_t(row0/16)+local/(local_n/pn))*(full_n/pn)+col0/pn+local%(local_n/pn));
}
inline void write_mining_hits(const MiningWork&w,const std::vector<MiningHit>&hits,const std::string&path,bool gpu){
 std::ofstream out(path,std::ios::binary);if(!out)throw std::runtime_error("open hits output");
 out<<"{\"job_fingerprint\":\""<<w.fingerprint<<"\",\"batch_id\":\""<<w.batch_id<<"\",\"GPU_executed\":"<<(gpu?"true":"false")<<",\"hits\":[";
 for(std::size_t i=0;i<hits.size();++i){if(i)out<<',';out<<"{\"index\":"<<hits[i].index<<",\"transcript\":[";for(int j=0;j<16;++j){if(j)out<<',';out<<hits[i].transcript[j];}out<<"]}";}out<<"]}\n";out.close();if(!out)throw std::runtime_error("write hits output");
}
void mine_batch(const std::string&path,const std::string&output);
}
