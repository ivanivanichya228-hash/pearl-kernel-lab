#include "compact_hits.hpp"
#include "hash_vectors.hpp"
#include <array>
#include <algorithm>
#include "mining_work.hpp"
#include <iostream>
#include <set>
int main(){
 for(unsigned pn:{8u,16u})for(int m:{16,48,96,8208})for(int n:{16,48,96,8240}){
  std::set<uint32_t>seen;
  for(int r=0;r<m;r+=8192)for(int c=0;c<n;c+=8192){int lm=std::min(8192,m-r),ln=std::min(8192,n-c);pearl_lab::HitGeometry g{unsigned(r),unsigned(c),unsigned(ln),unsigned(n),pn};unsigned groups=(lm/16)*(ln/pn);if(!pearl_lab::valid_hit_geometry(groups,g))return 1;
   for(unsigned i=0;i<groups;++i){auto x=pearl_lab::compact_global_index(i,g);if(x!=pearl_lab::global_group_index(i,r,c,ln,n,pn)||x>=unsigned((m/16)*(n/pn))||!seen.insert(uint32_t(x)).second)return 2;}
  }if(seen.size()!=std::size_t((m/16)*(n/pn)))return 3;
 }
 for(auto g:{pearl_lab::HitGeometry{0,0,0,16,16},{1,0,16,16,16},{0,0,16,16,1},{0,16,32,32,16}})if(pearl_lab::valid_hit_geometry(1,g))return 4;
 if(pearl_lab::valid_hit_geometry(0xffffffffu,{0xfffffff0u,0,16,0xfffffff0u,16}))return 5;
 auto vectors=pearl_lab::read_hash_vectors("pool/hash-vectors.bin");std::vector<std::array<uint32_t,8>>digests(vectors.size());for(std::size_t i=0;i<vectors.size();++i)pearl_lab::jackpot_hash64(vectors[i].transcript,vectors[0].context.key,digests[i].data());std::sort(digests.begin(),digests.end(),[](const auto&a,const auto&b){for(int i=7;i>=0;--i)if(a[i]!=b[i])return a[i]<b[i];return false;});auto ctx=vectors[0].context;std::copy(digests[digests.size()/2].begin(),digests[digests.size()/2].end(),ctx.target);std::size_t qualifies=0;for(const auto&row:vectors){uint32_t h[8];pearl_lab::jackpot_hash64(row.transcript,ctx.key,h);qualifies+=pearl_lab::hash_meets_target(h,ctx.target);}if(!qualifies||qualifies==vectors.size())return 6;std::cout<<"Mixed compact target includes "<<qualifies<<" hits and "<<vectors.size()-qualifies<<" misses\n";
 std::cout<<"Compact mapping matches independent slab indexing, complete coverage proof8/16, partial slabs and invalid/overflow bounds\n";
}
