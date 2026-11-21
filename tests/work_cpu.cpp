// Slow independent CPU backend only for loopback integration. Not a GPU hashrate claim.
#include "mapped_work.hpp"
#include "noise.hpp"
#include "worker_protocol.hpp"
#include <algorithm>
#include <iostream>
void execute(const std::string&input,const std::string&output){
 const pearl_lab::MappedMiningWork mapped(input);const auto&w=mapped.info;
 if(uint64_t(w.shape.m)*w.shape.n*w.shape.k>(1<<29))throw std::runtime_error("CPU work limited to integration shapes");
 std::vector<int8_t>an,bn;const int8_t*a=mapped.a,*b=mapped.bt;
 if(w.raw_input){pearl_lab::NoiseKey ka{},kb{};std::copy(w.context.key,w.context.key+8,ka.key);std::copy(w.b_noise_key,w.b_noise_key+8,kb.key);ka.is_a=true;kb.is_a=false;an=pearl_lab::noise_reference(a,w.shape.m,w.shape.k,w.shape.rank,ka);bn=pearl_lab::noise_reference(b,w.shape.n,w.shape.k,w.shape.rank,kb);a=an.data();b=bn.data();}
 auto r=pearl_lab::reference(a,b,w.shape);std::vector<pearl_lab::MiningHit>hits;
 for(std::size_t i=0;i<w.shape.groups();++i){uint32_t h[8];pearl_lab::jackpot_hash64(r.transcript.data()+i*16,w.context.key,h);if(pearl_lab::hash_meets_target(h,w.context.target)){pearl_lab::MiningHit v{};v.index=uint32_t(i);std::copy_n(r.transcript.data()+i*16,16,v.transcript);hits.push_back(v);}}
 pearl_lab::write_mining_hits(w,hits,output,false);
}
int main(int argc,char**argv){try{
 if(argc==2&&std::string(argv[1])=="--serve")return pearl_lab::serve_mining_worker([](const std::string&i,const std::string&o){execute(i,o);return 0;},"CPU-reference");
 if(argc!=3)throw std::runtime_error("work input/output required");
 execute(argv[1],argv[2]);
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
