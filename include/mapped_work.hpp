#pragma once
#include "mining_work.hpp"
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
namespace pearl_lab {
// Read-only mapping; the producer and consumer exchange ownership before this opens.
// No second gigabyte-sized host vector or disk read buffer is allocated.
class MappedBytes{
 int fd_=-1;void*data_=MAP_FAILED;std::size_t size_=0;
 public:
 explicit MappedBytes(const std::string&path){
  fd_=open(path.c_str(),O_RDONLY|O_CLOEXEC|O_NOFOLLOW);if(fd_<0)throw std::runtime_error("open mapped work");
  struct stat st{};
  if(fstat(fd_,&st)||!S_ISREG(st.st_mode)||st.st_size<156||uint64_t(st.st_size)>(1ull<<31)+156){close(fd_);fd_=-1;throw std::runtime_error("mapped work file bounds");}
  size_=std::size_t(st.st_size);data_=mmap(nullptr,size_,PROT_READ,MAP_SHARED,fd_,0);
  if(data_==MAP_FAILED){close(fd_);fd_=-1;throw std::runtime_error("map work");}
 }
 ~MappedBytes(){if(data_!=MAP_FAILED)munmap(data_,size_);if(fd_>=0)close(fd_);}
 MappedBytes(const MappedBytes&)=delete;MappedBytes&operator=(const MappedBytes&)=delete;
 const char*data()const{return static_cast<const char*>(data_);}std::size_t size()const{return size_;}
};
class MappedMiningWork{
 MappedBytes bytes_;
 public:
 MiningWorkInfo info;const int8_t*a=nullptr;const int8_t*bt=nullptr;std::size_t a_bytes=0,b_bytes=0;
 explicit MappedMiningWork(const std::string&path):bytes_(path){
  std::istringstream header(std::string(bytes_.data(),156),std::ios::binary);info=read_mining_header(header);a_bytes=std::size_t(info.shape.m)*info.shape.k;b_bytes=std::size_t(info.shape.n)*info.shape.k;
  if(bytes_.size()!=156+a_bytes+b_bytes)throw std::runtime_error("mapped work length mismatch");
  a=reinterpret_cast<const int8_t*>(bytes_.data()+156);bt=a+a_bytes;
 }
};
}
