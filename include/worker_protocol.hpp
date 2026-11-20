#pragma once
#include <iostream>
#include <stdexcept>
#include <string>
#include <unistd.h>
namespace pearl_lab {
// Sequential request: positive seq<TAB>absolute input<TAB>absolute output<LF>.
// Paths with control characters are rejected by both sides. No credentials are carried.
template<class Execute>int serve_mining_worker(Execute execute,const char*backend){
 std::cout<<"{\"phase\":\"worker_ready\",\"protocol\":1,\"backend\":\""<<backend<<"\",\"pid\":"<<getpid()<<"}\n"<<std::flush;
 std::string line;uint64_t previous=0;
 while(std::getline(std::cin,line)){
  if(line=="QUIT")return 0;
  if(line.size()>8192)throw std::runtime_error("worker request too large");
  auto first=line.find('\t'),second=first==std::string::npos?first:line.find('\t',first+1);
  if(first==std::string::npos||second==std::string::npos||line.find('\t',second+1)!=std::string::npos)throw std::runtime_error("worker request framing");
  auto id=line.substr(0,first),input=line.substr(first+1,second-first-1),output=line.substr(second+1);
  if(id.empty()||id.find_first_not_of("0123456789")!=std::string::npos||input.empty()||output.empty()||input[0]!='/'||output[0]!='/')throw std::runtime_error("worker request fields");
  for(unsigned char c:input+output)if(c<32||c==127)throw std::runtime_error("worker path control character");
  uint64_t seq=std::stoull(id);if(seq!=previous+1)throw std::runtime_error("worker sequence mismatch");previous=seq;
  auto generation=execute(input,output);
  std::cout<<"{\"phase\":\"worker_done\",\"seq\":"<<seq<<",\"requests_completed\":"<<seq<<",\"resource_generation\":"<<generation<<",\"pid\":"<<getpid()<<"}\n"<<std::flush;
 }
 return 0;
}
}
