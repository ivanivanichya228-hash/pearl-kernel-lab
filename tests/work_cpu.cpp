// Slow independent CPU backend only for loopback integration. Not a GPU hashrate claim.
#include "mining_work.hpp"
#include <algorithm>
#include <iostream>
int main(int argc,char**argv){try{
 if(argc!=3)throw std::runtime_error("work input/output required");
 const auto w=pearl_lab::read_mining_work(argv[1]);
 if(uint64_t(w.shape.m)*w.shape.n*w.shape.k>(1<<26))throw std::runtime_error("CPU work limited to integration shapes");
 auto r=pearl_lab::reference(w.a.data(),w.bt.data(),w.shape);std::vector<pearl_lab::MiningHit>hits;
 for(std::size_t i=0;i<w.shape.groups();++i){uint32_t h[8];pearl_lab::jackpot_hash64(r.transcript.data()+i*16,w.context.key,h);if(pearl_lab::hash_meets_target(h,w.context.target)){pearl_lab::MiningHit v{};v.index=uint32_t(i);std::copy_n(r.transcript.data()+i*16,16,v.transcript);hits.push_back(v);}}
 pearl_lab::write_mining_hits(w,hits,argv[2],false);
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
