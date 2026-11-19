#include "fixture.hpp"
#include <fstream>
#include <iostream>
int main(int argc,char**argv) {
 try {
  if(argc!=3)throw std::runtime_error("usage: protocol-cpu FIXTURE_DIR OUTPUT.jsonl");
  std::ofstream output(argv[2]);if(!output)throw std::runtime_error("cannot create transcript output");
  for(int i=0;i<6;++i) {
   auto f=pearl_lab::read_fixture(std::string(argv[1])+"/case-"+std::to_string(i)+".bin");
   auto result=pearl_lab::reference(f.a.data(),f.bt.data(),f.p);
   if(result.matrix!=f.golden.matrix||result.transcript!=f.golden.transcript)
    throw std::runtime_error("official proof fixture mismatch case "+std::to_string(i));
   output<<"{\"case\":"<<i<<",\"transcript\":[";
   for(std::size_t j=0;j<result.transcript.size();++j){if(j)output<<',';output<<result.transcript[j];}
   output<<"]}\n";
  }
  if(!output)throw std::runtime_error("transcript write failed");
  std::cout<<"6 official proof fixtures matched independent C++ matrix/transcript\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
}
