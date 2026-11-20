#pragma once
#include "contract.hpp"
#include "jackpot_hash.hpp"
#include <algorithm>
#include <fstream>
#include <string>
namespace pearl_lab {
struct PipelineFixture {
 Shape shape;KeyTarget context{};std::string fingerprint,batch_id;
 std::vector<int8_t>a,bt;std::vector<int32_t>matrix;std::vector<uint32_t>transcripts,hits;
};
inline PipelineFixture read_pipeline_fixture(const std::string& path){
 std::ifstream f(path,std::ios::binary);if(!f)throw std::runtime_error("open pipeline fixture");
 auto bytes=[&](void* p,std::size_t n){if(!f.read(static_cast<char*>(p),n))throw std::runtime_error("truncated pipeline fixture");};
 auto u32=[&](){unsigned char b[4];bytes(b,4);return uint32_t(b[0])|(uint32_t(b[1])<<8)|(uint32_t(b[2])<<16)|(uint32_t(b[3])<<24);};
 auto hex32=[&](){unsigned char b[32];bytes(b,32);const char* h="0123456789abcdef";std::string s;for(auto x:b){s+=h[x>>4];s+=h[x&15];}return s;};
 char magic[8];bytes(magic,8);if(std::string(magic,8)!="PRLPIPE1")throw std::runtime_error("pipeline magic");
 PipelineFixture p;p.shape={int(u32()),int(u32()),int(u32()),int(u32()),int(u32())};p.shape.validate();const auto&s=p.shape;
 if(s.m>128||s.n>128||s.k>8192||uint64_t(s.m)*s.n*s.k>(1<<26))throw std::runtime_error("not a bounded pipeline fixture");
 p.fingerprint=hex32();p.batch_id=hex32();for(auto&v:p.context.key)v=u32();for(auto&v:p.context.target)v=u32();
 p.a.resize(std::size_t(s.m)*s.k);p.bt.resize(std::size_t(s.n)*s.k);bytes(p.a.data(),p.a.size());bytes(p.bt.data(),p.bt.size());
 p.matrix.resize(std::size_t(s.m)*s.n);for(auto&v:p.matrix){auto u=u32();v=(u<=INT32_MAX)?int32_t(u):int32_t(int64_t(u)-(int64_t(1)<<32));}
 p.transcripts.resize(s.groups()*16);for(auto&v:p.transcripts)v=u32();const auto n=u32();if(n>s.groups())throw std::runtime_error("too many fixture hits");
 for(uint32_t i=0;i<n;++i){auto x=u32();if(x>=s.groups()||(!p.hits.empty()&&x<=p.hits.back()))throw std::runtime_error("invalid fixture hit set");p.hits.push_back(x);}
 if(f.peek()!=std::char_traits<char>::eof())throw std::runtime_error("trailing pipeline data");
 return p;
}
inline std::vector<uint32_t> pipeline_hits(const std::vector<uint32_t>& t,const KeyTarget& c){
 if(t.size()%16)throw std::runtime_error("transcript size");
 std::vector<uint32_t>hits;
 for(std::size_t i=0;i<t.size()/16;++i){uint32_t h[8];jackpot_hash64(t.data()+i*16,c.key,h);if(hash_meets_target(h,c.target))hits.push_back(uint32_t(i));}return hits;
}
void check_batch_pipeline(const std::string& fixture,const std::string& export_path);
}
