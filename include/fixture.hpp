#pragma once
#include "contract.hpp"
#include <array>
#include <fstream>
#include <string>

namespace pearl_lab {
struct Fixture {
  Shape p;
  std::vector<int8_t> a, bt;
  Reference golden;
};
inline Fixture read_fixture(const std::string& path) {
  std::ifstream f(path,std::ios::binary);
  if (!f) throw std::runtime_error("fixture not found: "+path);
  std::array<char,8> magic{}; f.read(magic.data(),8);
  if (std::string(magic.data(),8)!="PRLFX001") throw std::runtime_error("fixture magic");
  std::array<uint32_t,5> dims{};
  f.read(reinterpret_cast<char*>(dims.data()),20);
  Fixture x; x.p={int(dims[0]),int(dims[1]),int(dims[2]),int(dims[3]),int(dims[4])};
  x.p.validate();
  if (uint64_t(x.p.m)*x.p.n*x.p.k>uint64_t(1)<<30)
    throw std::runtime_error("fixture work limit");
  x.a.resize(std::size_t(x.p.m)*x.p.k); x.bt.resize(std::size_t(x.p.n)*x.p.k);
  x.golden.matrix.resize(std::size_t(x.p.m)*x.p.n);
  x.golden.transcript.resize(x.p.groups()*16);
  f.read(reinterpret_cast<char*>(x.a.data()),x.a.size());
  f.read(reinterpret_cast<char*>(x.bt.data()),x.bt.size());
  f.read(reinterpret_cast<char*>(x.golden.matrix.data()),x.golden.matrix.size()*4);
  f.read(reinterpret_cast<char*>(x.golden.transcript.data()),x.golden.transcript.size()*4);
  if (!f || f.peek()!=std::char_traits<char>::eof()) throw std::runtime_error("fixture size");
  return x;
}
}
