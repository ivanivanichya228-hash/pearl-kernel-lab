#include "pipeline_fixture.hpp"
#include <iostream>
int main(int argc,char**argv){try{
 if(argc!=2)throw std::runtime_error("fixture path required");
 const auto f=pearl_lab::read_pipeline_fixture(argv[1]);const auto r=pearl_lab::reference(f.a.data(),f.bt.data(),f.shape);
 if(r.matrix!=f.matrix||r.transcript!=f.transcripts||pearl_lab::pipeline_hits(r.transcript,f.context)!=f.hits)throw std::runtime_error("independent C++ pipeline mismatch");
 std::cout<<"Independent C++ matrix, all transcripts and exact-target hit set match official Rust oracle\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
