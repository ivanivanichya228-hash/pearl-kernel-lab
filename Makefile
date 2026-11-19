CUDA_HOME ?= /usr/local/cuda
NVCC ?= $(CUDA_HOME)/bin/nvcc
CXX ?= g++
CUDA_ARCH_FLAGS ?= -gencode arch=compute_86,code=sm_86 -gencode arch=compute_89,code=sm_89 -gencode arch=compute_86,code=compute_86
NVFLAGS = -std=c++17 -O3 -lineinfo -Iinclude -L$(CUDA_HOME)/lib $(CUDA_ARCH_FLAGS) -Xptxas=-v
.PHONY: all cpu-check fixtures clean
all: build/pearl-bench
build:
	mkdir -p build
build/pearl-bench: src/kernel.cu src/bench.cu include/kernel.cuh include/contract.hpp include/fixture.hpp | build
	$(NVCC) $(NVFLAGS) src/kernel.cu src/bench.cu -Xcompiler=-pthread -ldl -o $@
build/test-contract: tests/test_contract.cpp include/contract.hpp | build
	$(CXX) -std=c++17 -O3 -Wall -Wextra -Werror -Iinclude $< -o $@
build/check-fixtures: tests/check_fixtures.cpp include/fixture.hpp include/contract.hpp | build
	$(CXX) -std=c++17 -O3 -Wall -Wextra -Werror -Iinclude $< -o $@
fixtures:
	python3 tools/make_fixtures.py
cpu-check: build/test-contract build/check-fixtures
	./build/test-contract
	./build/check-fixtures
	python3 tests/test_compact.py
	python3 tests/test_stage64.py
clean:
	rm -rf build
