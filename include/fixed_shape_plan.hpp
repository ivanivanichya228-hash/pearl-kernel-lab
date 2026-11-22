#pragma once
#include "contract.hpp"
#include "compact_hits.hpp"
namespace pearl_lab {
// Called only after Shape/HitGeometry validation. Zero means exact old fallback.
inline int fixed_shape_interior_rows(Shape p,HitGeometry g){
 if(p.k!=4096||p.rank!=256||p.proof_n!=16||p.n%256||p.m<192)return 0;
 const int rows=p.m/192*192;
 if(uint64_t(g.row0)+uint32_t(rows)>std::numeric_limits<uint32_t>::max())return 0;
 return rows;
}
}
