#include "fixture.hpp"
#include <iostream>
int main(){
 for(int i=6;i<10;++i){
  auto f=pearl_lab::read_fixture("tests/fixtures/case-"+std::to_string(i)+".bin");
  if(f.p.k!=16*f.p.rank)throw std::runtime_error("singlepass fixture gate");
  auto expected=pearl_lab::reference(f.a.data(),f.bt.data(),f.p);
  if(expected.matrix!=f.golden.matrix||expected.transcript!=f.golden.transcript)throw std::runtime_error("independent CPU fixture differs");
 }
 std::cout<<"4 singlepass fixtures match independent C++ prefix/rotation reference; no GPU executed\n";
}
