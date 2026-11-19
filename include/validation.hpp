#pragma once
#include <array>
#include <cmath>
#include <stdexcept>
namespace pearl_lab {
constexpr std::array<int,4> abba_order{0,1,1,0};
struct ValidationPlan {
  double duration = 2, warmup = 0;
  int rounds = 1;
  double scheduled_seconds() const { return 4 * rounds * (duration + warmup); }
  void validate() const {
    if (!std::isfinite(duration) || !std::isfinite(warmup) ||
        duration < 1 || duration > 10 || warmup < 0 || warmup > 5 ||
        rounds < 1 || rounds > 3 || scheduled_seconds() > 45)
      throw std::invalid_argument("invalid validation plan or scheduled work exceeds 45s");
  }
};
}
