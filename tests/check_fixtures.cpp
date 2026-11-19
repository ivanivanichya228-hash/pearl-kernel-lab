#include "fixture.hpp"
#include <iostream>
int main(int argc,char**argv) {
  try {
    const std::string root=argc>1?argv[1]:"tests/fixtures";
    for (int i=0;i<6;++i) {
      auto f=pearl_lab::read_fixture(root+"/case-"+std::to_string(i)+".bin");
      auto r=pearl_lab::reference(f.a.data(),f.bt.data(),f.p);
      if (r.matrix!=f.golden.matrix || r.transcript!=f.golden.transcript)
        throw std::runtime_error("CPU oracle mismatch case "+std::to_string(i));
    }
    std::cout<<"6 independent NumPy/C++ fixtures matched\n";
  } catch (const std::exception&e) {std::cerr<<e.what()<<"\n";return 1;}
}
