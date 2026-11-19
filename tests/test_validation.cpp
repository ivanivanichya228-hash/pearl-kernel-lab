#include "validation.hpp"
#include <cassert>
#include <limits>
using namespace pearl_lab;
int main() {
  ValidationPlan p{3,2,2};p.validate();assert(p.scheduled_seconds()==40);
  assert((abba_order == std::array<int,4>{0,1,1,0}));
  int rejected=0;
  for(auto bad : {ValidationPlan{10,5,3},ValidationPlan{3,2,0},
                 ValidationPlan{3,-1,2},ValidationPlan{0,2,2},
                 ValidationPlan{std::numeric_limits<double>::quiet_NaN(),0,1},
                 ValidationPlan{3,std::numeric_limits<double>::infinity(),2}}) {
    try {bad.validate();} catch(const std::invalid_argument&) {++rejected;}
  }
  assert(rejected==6);
}
