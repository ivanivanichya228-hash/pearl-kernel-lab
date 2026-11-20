#pragma once
#include "jackpot_hash.hpp"
#include <array>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>
namespace pearl_lab {
struct HashVector {KeyTarget context;uint32_t transcript[16];uint32_t expected[8];uint32_t qualifies;};
inline std::vector<HashVector> read_hash_vectors(const std::string& path){
 std::ifstream f(path,std::ios::binary);std::array<char,8>magic{};uint32_t count=0;
 f.read(magic.data(),8);f.read(reinterpret_cast<char*>(&count),4);
 if(std::string(magic.data(),8)!="PRLHSH01"||count==0||count>4096)throw std::runtime_error("invalid hash vectors header");
 std::vector<HashVector> result(count);
 for(auto&v:result){
  f.read(reinterpret_cast<char*>(v.context.key),32);f.read(reinterpret_cast<char*>(v.transcript),64);
  f.read(reinterpret_cast<char*>(v.expected),32);f.read(reinterpret_cast<char*>(v.context.target),32);
  f.read(reinterpret_cast<char*>(&v.qualifies),4);if(v.qualifies>1)throw std::runtime_error("invalid qualifies flag");
 }
 if(!f||f.peek()!=std::char_traits<char>::eof())throw std::runtime_error("invalid hash vectors size");
 return result;
}
}
