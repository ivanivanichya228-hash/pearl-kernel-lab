#pragma once
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <exception>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <optional>
#include <poll.h>
#include <stdexcept>
#include <string>
#include <thread>
#include <unistd.h>
namespace pearl_lab {
struct WorkerRequest{uint64_t seq=0;std::string input,output;bool quit=false;};
inline WorkerRequest parse_overlap_request(const std::string&line,uint64_t&previous){
 if(line=="QUIT")return WorkerRequest{0,"","",true};
 if(line.size()>8192)throw std::runtime_error("overlap request too large");
 auto a=line.find('\t'),b=a==std::string::npos?a:line.find('\t',a+1);
 if(a==std::string::npos||b==std::string::npos||line.find('\t',b+1)!=std::string::npos)throw std::runtime_error("overlap request framing");
 auto id=line.substr(0,a),input=line.substr(a+1,b-a-1),output=line.substr(b+1);
 if(id.empty()||id.find_first_not_of("0123456789")!=std::string::npos||input.empty()||output.empty()||input[0]!='/'||output[0]!='/')throw std::runtime_error("overlap request fields");
 for(unsigned char c:input+output)if(c<32||c==127)throw std::runtime_error("overlap path control character");
 auto seq=std::stoull(id);if(seq!=previous+1)throw std::runtime_error("overlap sequence mismatch");previous=seq;return WorkerRequest{seq,input,output,false};
}
// Reader owns no CUDA state. Polling makes shutdown/join bounded even on an open idle pipe.
class RequestInbox{
 std::mutex mutex_;std::condition_variable cv_;std::deque<WorkerRequest>queue_;bool stop_=false,eof_=false;std::exception_ptr failure_;std::thread reader_;
 void read_loop(){try{std::string pending;uint64_t previous=0;char buf[4096];
  while(true){ {std::lock_guard<std::mutex>g(mutex_);if(stop_)return;}pollfd fd{STDIN_FILENO,POLLIN,0};int ready=poll(&fd,1,50);if(ready<0){if(errno==EINTR)continue;throw std::runtime_error("overlap stdin poll");}if(!ready)continue;
   auto n=read(STDIN_FILENO,buf,sizeof buf);if(n<0){if(errno==EINTR)continue;throw std::runtime_error("overlap stdin read");}if(!n){std::lock_guard<std::mutex>g(mutex_);if(!pending.empty())throw std::runtime_error("partial overlap request at EOF");eof_=true;cv_.notify_all();return;}
   pending.append(buf,std::size_t(n));std::size_t pos;
   while((pos=pending.find('\n'))!=std::string::npos){auto request=parse_overlap_request(pending.substr(0,pos),previous);pending.erase(0,pos+1);std::unique_lock<std::mutex>lock(mutex_);cv_.wait(lock,[&]{return stop_||queue_.size()<1;});if(stop_)return;bool quit=request.quit;queue_.push_back(std::move(request));cv_.notify_all();lock.unlock();if(quit)return;}
   if(pending.size()>8192)throw std::runtime_error("overlap request too large");
  }
 }catch(...){std::lock_guard<std::mutex>g(mutex_);failure_=std::current_exception();cv_.notify_all();}}
 public:
 RequestInbox():reader_([this]{read_loop();}){}
 ~RequestInbox(){ {std::lock_guard<std::mutex>g(mutex_);stop_=true;cv_.notify_all();}if(reader_.joinable())reader_.join();}
 std::optional<WorkerRequest>take(bool wait){std::unique_lock<std::mutex>lock(mutex_);if(wait)cv_.wait(lock,[&]{return !queue_.empty()||eof_||failure_;});if(failure_)std::rethrow_exception(failure_);if(queue_.empty()){if(eof_)return WorkerRequest{0,"","",true};return std::nullopt;}auto r=std::move(queue_.front());queue_.pop_front();cv_.notify_all();return r;}
};
}
