#pragma once
#include <cstdint>
#include <limits>
namespace pearl_lab {
struct CompactHit { uint32_t index;uint32_t transcript[16]; };
static_assert(sizeof(CompactHit)==68,"compact hit ABI");
struct HitGeometry {uint32_t row0,col0,local_n,full_n,proof_n;};
#ifdef __CUDACC__
#define PEARL_HD __host__ __device__
#else
#define PEARL_HD
#endif
PEARL_HD inline uint64_t compact_global_index(uint32_t i,HitGeometry g){
 return (uint64_t(g.row0/16)+i/(g.local_n/g.proof_n))*(g.full_n/g.proof_n)+g.col0/g.proof_n+i%(g.local_n/g.proof_n);
}
#undef PEARL_HD
inline bool valid_hit_geometry(uint32_t groups,HitGeometry g){
 if((g.proof_n!=8&&g.proof_n!=16)||!g.local_n||!g.full_n||g.row0%16||g.col0%g.proof_n||g.local_n%g.proof_n||g.full_n%g.proof_n||uint64_t(g.col0)+g.local_n>g.full_n)return false;
 return !groups||compact_global_index(groups-1,g)<=std::numeric_limits<uint32_t>::max();
}
}
