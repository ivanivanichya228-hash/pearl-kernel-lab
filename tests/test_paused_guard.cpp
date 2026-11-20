#include "paused_guard.hpp"
#include <sys/prctl.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>
#include <iostream>
int spawn(){int p=fork();if(p<0)throw std::runtime_error("fork");if(!p){prctl(PR_SET_NAME,"SRBMiner-LAB",0,0,0);raise(SIGSTOP);for(;;)pause();}int status;waitpid(p,&status,WUNTRACED);return p;}
void end(int p){if(p>0){kill(p,SIGKILL);int status;waitpid(p,&status,0);}}
int main(){int p=0,q=0;try{p=spawn();auto root=std::filesystem::path("/proc")/std::to_string(p);auto ticks=std::stoull(pearl_lab::process_stat(root/"stat")[19]);pearl_lab::require_paused_miner(p,ticks);
 bool rejected=false;try{pearl_lab::require_paused_miner(p,ticks+1);}catch(...){rejected=true;}if(!rejected)throw std::runtime_error("wrong identity accepted");
 q=spawn();rejected=false;try{pearl_lab::require_paused_miner(p,ticks);}catch(...){rejected=true;}end(q);q=0;if(!rejected)throw std::runtime_error("duplicate miner accepted");
 kill(p,SIGCONT);for(int i=0;i<100&&pearl_lab::process_stat(root/"stat")[0]=="T";++i)usleep(1000);rejected=false;try{pearl_lab::require_paused_miner(p,ticks);}catch(...){rejected=true;}if(!rejected)throw std::runtime_error("running miner accepted");end(p);std::cout<<"Paused identity, wrong start ticks, duplicate and resumed process guards passed\n";
 }catch(const std::exception&e){end(q);end(p);std::cerr<<e.what()<<'\n';return 1;}}
