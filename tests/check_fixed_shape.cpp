#include "fixture.hpp"
#include "fixed_shape_plan.hpp"
#include <iostream>
#include <set>
using namespace pearl_lab;
int main(){
 for(int i=10;i<12;++i){
  auto f=read_fixture("tests/fixtures/case-"+std::to_string(i)+".bin");
  auto r=reference(f.a.data(),f.bt.data(),f.p);
  if(r.matrix!=f.golden.matrix||r.transcript!=f.golden.transcript)throw std::runtime_error("fixed-shape independent golden differs");
 }
 for(int m:{16,192,208,384,8192})for(int n:{256,272,512,8192}){
  Shape p{m,n,4096,256,16};p.validate();HitGeometry g{32,32,uint32_t(n),uint32_t(n+64),16};
  const int split=fixed_shape_interior_rows(p,g);std::set<uint64_t>indices;
  auto add=[&](int offset,int rows){HitGeometry local=g;local.row0+=uint32_t(offset);
   for(int r=0;r<rows/16;++r)for(int c=0;c<n/16;++c)
    if(!indices.insert(compact_global_index(uint32_t(r*(n/16)+c),local)).second)throw std::runtime_error("duplicate split hit index");};
  if(split){if(split%192||split>m||n%256)throw std::runtime_error("unchecked interior alignment");add(0,split);if(split<m)add(split,m-split);}
  else add(0,m);
  std::set<uint64_t>expected;for(uint32_t i=0;i<p.groups();++i)expected.insert(compact_global_index(i,g));
  if(indices!=expected)throw std::runtime_error("interior/tail group coverage");
 }
 Shape p{208,256,4096,256,16};HitGeometry g{0xfffffff0u,0,256,256,16};
 if(fixed_shape_interior_rows(p,g))throw std::runtime_error("tail row offset overflow not refused");
 for(auto q:{Shape{208,256,2048,256,16},Shape{208,256,4096,128,16},Shape{208,256,4096,256,8}})
  if(fixed_shape_interior_rows(q,{0,0,256,256,uint32_t(q.proof_n)}))throw std::runtime_error("wrong-profile specialization");
 std::cout<<"2 independent dense prefix goldens; 20 split/offset/edge coverage cases; profile/overflow fallbacks passed (CPU only)\n";
}
