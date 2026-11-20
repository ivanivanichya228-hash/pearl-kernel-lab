#pragma once
#include <filesystem>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <stdexcept>
#include <vector>
namespace pearl_lab {
inline std::vector<std::string> process_stat(const std::filesystem::path&path){
 std::ifstream f(path);std::string line;std::getline(f,line);auto pos=line.rfind(')');if(pos==std::string::npos)throw std::runtime_error("paused identity stat unavailable");
 std::istringstream input(line.substr(pos+1));std::vector<std::string>fields;std::string s;while(input>>s)fields.push_back(s);if(fields.size()<20)throw std::runtime_error("short paused identity stat");return fields;
}
inline bool srb_process(const std::filesystem::path&dir){std::ifstream f(dir/"comm");std::string s;std::getline(f,s);std::transform(s.begin(),s.end(),s.begin(),[](unsigned char c){return std::tolower(c);});return s.find("srbminer")!=std::string::npos;}
inline void require_paused_miner(int pid,uint64_t ticks){
 auto root=std::filesystem::path("/proc")/std::to_string(pid);auto fields=process_stat(root/"stat");
 if(pid<=0||!ticks||fields[0]!="T"||std::stoull(fields[19])!=ticks||!srb_process(root))throw std::runtime_error("original miner is not the expected paused identity");
 for(const auto&thread:std::filesystem::directory_iterator(root/"task"))if(process_stat(thread.path()/"stat")[0]!="T")throw std::runtime_error("original miner thread is running");
 for(const auto&process:std::filesystem::directory_iterator("/proc"))if(process.path()!=root&&srb_process(process.path()))throw std::runtime_error("additional SRBMiner process found");
}
}
