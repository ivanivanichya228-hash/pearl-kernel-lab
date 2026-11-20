#include "mapped_work.hpp"
#include "noise.hpp"
#include <algorithm>
#include <iostream>
int main(int argc,char**argv){try{
 if(argc!=3)throw std::runtime_error("raw and official noised paths required");
 const pearl_lab::MappedMiningWork raw(argv[1]),ref(argv[2]);const auto&p=raw.info.shape;
 if(!raw.info.raw_input||ref.info.raw_input||p.m>256||p.n>256||p.k>8192||raw.a_bytes!=ref.a_bytes||raw.b_bytes!=ref.b_bytes||raw.info.fingerprint!=ref.info.fingerprint||raw.info.batch_id!=ref.info.batch_id)throw std::runtime_error("noise reference context");
 pearl_lab::NoiseKey ka{},kb{};std::copy(raw.info.context.key,raw.info.context.key+8,ka.key);std::copy(raw.info.b_noise_key,raw.info.b_noise_key+8,kb.key);ka.is_a=true;kb.is_a=false;
 auto a=pearl_lab::noise_reference(raw.a,p.m,p.k,p.rank,ka),b=pearl_lab::noise_reference(raw.bt,p.n,p.k,p.rank,kb);
 if(!std::equal(a.begin(),a.end(),ref.a)||!std::equal(b.begin(),b.end(),ref.bt))throw std::runtime_error("independent C++ noise differs from official Rust arrays");
 std::cout<<"All "<<a.size()+b.size()<<" A/B bytes match unmodified official Rust noise\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
