#include "request_inbox.hpp"
#include <iostream>
int main(int argc,char**){try{
 if(argc>1){pearl_lab::RequestInbox inbox;return 0;}
 uint64_t seq=0;auto r=pearl_lab::parse_overlap_request("1\t/a\t/b",seq);if(r.seq!=1||r.input!="/a")return 1;
 for(auto line:{"1\t/a\t/b","2\ta\t/b","2\t/a\t/b\t/c","x\t/a\t/b"}){bool rejected=false;try{pearl_lab::parse_overlap_request(line,seq);}catch(...){rejected=true;}if(!rejected)return 2;}
 auto q=pearl_lab::parse_overlap_request("QUIT",seq);if(!q.quit)return 3;
 std::cout<<"Inbox framing, absolute paths, sequence and QUIT passed\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
