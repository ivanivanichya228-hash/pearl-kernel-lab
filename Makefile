CUDA_HOME ?= /usr/local/cuda
NVCC ?= $(CUDA_HOME)/bin/nvcc
CXX ?= g++
CUDA_ARCH_FLAGS ?= -gencode arch=compute_86,code=sm_86 -gencode arch=compute_89,code=sm_89 -gencode arch=compute_86,code=compute_86
NVFLAGS = -std=c++17 -O3 -lineinfo -Iinclude -L$(CUDA_HOME)/lib $(CUDA_ARCH_FLAGS) -Xptxas=-v
.PHONY: all cpu-check fixtures clean
all: build/pearl-bench
build:
	mkdir -p build
build/pearl-bench: src/kernel.cu src/bench.cu src/filter.cu src/pipeline.cu src/noise.cu include/request_inbox.hpp include/transfer_pool.cuh include/compact_hits.hpp include/noise.cuh include/noise.hpp include/filter.cuh include/pipeline_fixture.hpp include/mining_work.hpp include/mapped_work.hpp include/worker_protocol.hpp include/paused_guard.hpp include/jackpot_hash.hpp include/hash_vectors.hpp include/kernel.cuh include/triple_stage.cuh include/occupancy_stage.cuh include/contract.hpp include/fixture.hpp include/validation.hpp | build
	$(NVCC) $(NVFLAGS) src/kernel.cu src/bench.cu src/filter.cu src/pipeline.cu src/noise.cu -Xcompiler=-pthread -ldl -o $@
build/test-contract: tests/test_contract.cpp include/contract.hpp | build
	$(CXX) -std=c++17 -O3 -Wall -Wextra -Werror -Iinclude $< -o $@
build/check-fixtures: tests/check_fixtures.cpp include/fixture.hpp include/contract.hpp | build
	$(CXX) -std=c++17 -O3 -Wall -Wextra -Werror -Iinclude $< -o $@
fixtures:
	python3 tools/make_fixtures.py
build/test-validation: tests/test_validation.cpp include/validation.hpp | build
	$(CXX) -std=c++17 -O2 -Wall -Wextra -Werror -Iinclude $< -o $@
cpu-check: build/test-contract build/check-fixtures build/test-validation
	./build/test-validation
	./build/test-contract
	./build/check-fixtures
	python3 tests/test_compact.py
	python3 tests/test_stage64.py
clean:
	rm -rf build

build/protocol-cpu: tests/protocol_cpu.cpp include/fixture.hpp include/contract.hpp | build
	$(CXX) -std=c++17 -O3 -Wall -Wextra -Werror -Iinclude $< -o $@

build/test-jackpot-hash: tests/test_jackpot_hash.cpp include/jackpot_hash.hpp include/hash_vectors.hpp | build
	$(CXX) -std=c++17 -O3 -Wall -Wextra -Werror -Iinclude $< -o $@

build/check-pipeline: tests/check_pipeline.cpp include/pipeline_fixture.hpp include/contract.hpp include/jackpot_hash.hpp | build
	$(CXX) -std=c++17 -O3 -Wall -Wextra -Werror -Iinclude $< -o $@

build/work-cpu: tests/work_cpu.cpp include/request_inbox.hpp include/noise.hpp include/mapped_work.hpp include/worker_protocol.hpp include/mining_work.hpp include/contract.hpp include/jackpot_hash.hpp | build
	$(CXX) -std=c++17 -O3 -Wall -Wextra -Werror -Iinclude $< -pthread -o $@

build/test-work-index: tests/test_work_index.cpp include/mining_work.hpp include/contract.hpp | build
	$(CXX) -std=c++17 -O3 -Wall -Wextra -Werror -Iinclude $< -o $@

build/test-paused-guard: tests/test_paused_guard.cpp include/paused_guard.hpp | build
	$(CXX) -std=c++17 -O2 -Wall -Wextra -Werror -Iinclude $< -o $@

build/test-mapped-work: tests/test_mapped_work.cpp include/mapped_work.hpp include/mining_work.hpp | build
	$(CXX) -std=c++17 -O3 -Wall -Wextra -Werror -Iinclude $< -o $@

build/test-noise-reference: tests/test_noise_reference.cpp include/noise.hpp include/mapped_work.hpp include/mining_work.hpp | build
	$(CXX) -std=c++17 -O3 -Wall -Wextra -Werror -Iinclude $< -o $@

build/test-compact-hits: tests/test_compact_hits.cpp include/compact_hits.hpp include/mining_work.hpp include/hash_vectors.hpp include/jackpot_hash.hpp | build
	$(CXX) -std=c++17 -O3 -Wall -Wextra -Werror -Iinclude $< -o $@

build/test-request-inbox: tests/test_request_inbox.cpp include/request_inbox.hpp | build
	$(CXX) -std=c++17 -O3 -Wall -Wextra -Werror -Iinclude $< -pthread -o $@
