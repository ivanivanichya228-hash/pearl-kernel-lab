#include "mapped_work.hpp"
#include <iostream>
#include <algorithm>
int main(int argc,char**argv){try{
 if(argc!=2)throw std::runtime_error("work path required");
 const auto copied=pearl_lab::read_mining_work(argv[1]);const pearl_lab::MappedMiningWork mapped(argv[1]);
 if(copied.batch_id!=mapped.info.batch_id||copied.fingerprint!=mapped.info.fingerprint||copied.a.size()!=mapped.a_bytes||copied.bt.size()!=mapped.b_bytes||!std::equal(copied.a.begin(),copied.a.end(),mapped.a)||!std::equal(copied.bt.begin(),copied.bt.end(),mapped.bt))throw std::runtime_error("mapped/copied payload differs");
 std::cout<<"Mapped header and both signed input arrays match copied reader exactly\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
