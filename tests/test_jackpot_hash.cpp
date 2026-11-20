#include "hash_vectors.hpp"
#include <algorithm>
#include <iostream>
int main(int argc,char**argv){try{
 if(argc!=2)throw std::runtime_error("usage: test-jackpot-hash VECTORS");
 auto vectors=pearl_lab::read_hash_vectors(argv[1]);
 for(const auto&v:vectors){uint32_t hash[8];pearl_lab::jackpot_hash64(v.transcript,v.context.key,hash);
  if(!std::equal(hash,hash+8,v.expected)||pearl_lab::hash_meets_target(hash,v.context.target)!=bool(v.qualifies))throw std::runtime_error("official hash/target mismatch");
 }
 std::cout<<vectors.size()<<" official keyed hash/target CPU vectors passed\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
