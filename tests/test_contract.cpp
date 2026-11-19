#include "contract.hpp"
#include <iostream>
#include <cassert>
#include <algorithm>
using namespace pearl_lab;
int main() {
  // A single nonzero output makes every checkpoint XOR analytically known.
  for (int sign : {1, -1}) {
    Shape p{16, 16, 2176, 128, 16};
    std::vector<int8_t> a(std::size_t(p.m)*p.k), b(std::size_t(p.n)*p.k);
    std::fill_n(a.begin(), p.k, int8_t(sign));
    std::fill_n(b.begin(), p.k, int8_t(1));
    auto r = reference(a.data(), b.data(), p);
    assert(r.matrix[0] == sign * 2176);
    for (int slot = 1; slot < 16; ++slot)
      assert(r.transcript[slot] == uint32_t(sign * (slot + 1) * 128));
    assert(r.transcript[0] == (rotate13(uint32_t(sign*128)) ^ uint32_t(sign*2176)));
  }
  // Rank changes checkpoints, not the final matrix. Transposed BT is explicit.
  Shape p{16, 24, 4096, 128, 8};
  std::vector<int8_t> a(std::size_t(p.m)*p.k), b(std::size_t(p.n)*p.k);
  for (std::size_t i=0;i<a.size();++i) a[i] = int8_t(int((i*13+9)%129)-64);
  for (std::size_t i=0;i<b.size();++i) b[i] = int8_t(int((i*7+5)%129)-64);
  auto first=reference(a.data(),b.data(),p); p.rank=256;
  auto second=reference(a.data(),b.data(),p);
  assert(first.matrix==second.matrix);
  assert(first.transcript!=second.transcript);
  bool rejected=false;
  try { Shape{16,16,32,32,0}.validate(); } catch (const std::invalid_argument&) {rejected=true;}
  assert(rejected);
  std::cout << "CPU contract checks passed\n";
}
