#include "mining_work.hpp"
#include <iostream>
#include <set>
int main(){for(int pn:{8,16}){for(int m:{16,48,64,96}){for(int n:{16,48,64,96}){
 std::set<uint32_t>seen;
 for(int r=0;r<m;r+=32){for(int c=0;c<n;c+=32){int lm=std::min(32,m-r),ln=std::min(32,n-c);for(int i=0;i<(lm/16)*(ln/pn);++i){auto x=pearl_lab::global_group_index(i,r,c,ln,n,pn);if(x>=unsigned((m/16)*(n/pn))||!seen.insert(x).second)return 1;}}}
 if(seen.size()!=std::size_t((m/16)*(n/pn)))return 2;
}}}std::cout<<"Slab indices cover every full-matrix group exactly once, proof8/16 and partial slabs\n";}
