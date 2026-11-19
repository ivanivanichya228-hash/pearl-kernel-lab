#pragma once
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace pearl_lab {
struct Shape {
  int m, n, k, rank, proof_n;
  void validate() const {
    if ((proof_n != 8 && proof_n != 16) || m <= 0 || n <= 0 || k < 32 || k > 65536 ||
        m > 32768 || n > 32768 || m % 16 || n % proof_n ||
        rank < 32 || rank > 1024 ||
        (rank & (rank - 1)) || k % rank || rank % 32)
      throw std::invalid_argument("unsupported kernel shape");
  }
  std::size_t groups() const { return std::size_t(m / 16) * (n / proof_n); }
};
inline uint32_t rotate13(uint32_t v) { return (v << 13) | (v >> 19); }
struct Reference {
  std::vector<int32_t> matrix;
  std::vector<uint32_t> transcript;
};
// A is M x K row-major; BT is N x K row-major. Noise must already be applied.
// This is the arithmetic/transcript subproblem, NOT a complete Pearl verifier.
inline Reference reference(const int8_t* a, const int8_t* bt, const Shape& p) {
  p.validate();
  Reference r{std::vector<int32_t>(std::size_t(p.m) * p.n),
              std::vector<uint32_t>(p.groups() * 16, 0)};
  for (int i = 0; i < p.m; ++i) {
    for (int j = 0; j < p.n; ++j) {
      int64_t c = 0;
      const std::size_t group = std::size_t(i / 16) * (p.n / p.proof_n) + j / p.proof_n;
      for (int q = 0; q < p.k; q += p.rank) {
        for (int t = q; t < q + p.rank; ++t)
          c += int64_t(a[std::size_t(i) * p.k + t]) * bt[std::size_t(j) * p.k + t];
        // Accumulate the XOR contribution of this element into its slot.
        // Rotation is linear over XOR, so each element can contribute separately.
        const int cp = q / p.rank;
        const int later = ((p.k / p.rank - 1 - cp) / 16);
        uint32_t v = uint32_t(c);
        for (int l = 0; l < later; ++l) v = rotate13(v);
        r.transcript[group * 16 + (cp & 15)] ^= v;
      }
      if (c < INT32_MIN || c > INT32_MAX)
        throw std::overflow_error("signed INT32 accumulator overflow");
      r.matrix[std::size_t(i) * p.n + j] = int32_t(c);
    }
  }
  return r;
}
}  // namespace pearl_lab
