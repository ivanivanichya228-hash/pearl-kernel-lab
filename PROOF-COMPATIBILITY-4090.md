# Revision 0.4.0: real plain-proof compatibility bridge

## Completed here, CPU only

Unmodified official source: https://github.com/pearl-research-labs/pearl/tree/38dd764ab0aec528e81fc467665c6762ef6739e9
The current upstream HEAD checked during preparation matches that pinned commit.
The optional Rust oracle links its zk-pow and pearl-blake3 crates directly, with Cargo.lock.
No copied verifier substitute is called an official verifier.

Six deterministic synthetic mining solutions were generated with upstream try_mine_one and
accepted by upstream verify_plain_proof. The cases cover Legacy(V2) and Salted(V3) seed rules,
proof16x8/16x16, contiguous and strided original indices, K4096/rank128, full matrices64x64.
The raw committed strips are gathered in verifier order BEFORE addition of their indexed noise.
Prepared signed inputs stay in [-127,127]: original signal[-64,64] plus noise[-63,63].
This bound follows the upstream uniform[-32,31] and sparse difference noise construction.
There is no +128 cast/wrap correction and no change to consensus arithmetic.

For each actual plain proof the official parser/noise/helper computed the transcript and keyed
jackpot hash. An independent existing C++ reference recomputed full C and all transcript words.
All six agreed; their exported transcripts were rechecked against reconstructed upstream proofs.
All19 fixture/proof/header/manifest files reproduced byte-identically from the seeded generator.

36 actual verifier rejection checks: altered root, leaf, sibling, job header, dimension wrap and
too-hard target for each proof. 12 additional local hash checks change transcript/key bits.
A corrupted external C++ transcript was also rejected by the official-proof bridge.
Results: protocol/CPU-RESULT.json. Ready fixture archive is SHA-pinned and contains synthetic data only.

IMPORTANT SCOPE: this verifies the official PLAIN mining solution path, NOT a recursively generated
STARK/Plonky2 certificate. Active pool job/certificate parameters have not been obtained/confirmed.
These are not network shares submitted to a pool. GPU compatibility with THESE proof fixtures is
still pending; no GPU work was run here. The measured +9.64% remains vs OUR prior arithmetic kernel.

## Components

- proof-oracle/: Rust bridge calling upstream directly, no CUDA, no miner/pool access.
- tools/proof_oracle.py: optional reproducible upstream fetch/build/generate/verify using installed
  Cargo (tested rustc1.90.0). Normal Mint4090 test does NOT need Rust or build the verifier.
- protocol/proof-fixtures-v1.tar.gz and fixture-lock.json:6 binary arithmetic fixtures,6 actual
  serialized plain proofs,6 header files and manifest. SHA256 checked before extraction.
- tools/proof_fixtures.py --compare: compares to pinned oracle outputs; it DOES NOT execute Rust verifier.
- tests/protocol_cpu.cpp: independent C++ check and JSONL export.
- bench --export-transcripts FILE: exports actual non-debug stage64 GPU output for each fixture.
  Each file is incomplete if interrupted; checker refuses missing/duplicate/different cases.
- guard accepts --fixtures and --export-transcripts; old defaults still use old arithmetic fixtures.

Reproduce CPU stage (optional, separate CPU host):
  python3 tools/proof_oracle.py --generate build/regenerated-proof-fixtures
  make build/protocol-cpu
  build/protocol-cpu build/regenerated-proof-fixtures build/cpu-transcripts.jsonl
  python3 tools/proof_oracle.py --verify build/cpu-transcripts.jsonl --fixtures build/regenerated-proof-fixtures

## One Codex task on panel host

1. Before any new pause, READ current Mint4090 miner state/logs. Last supplied post-benchmark
   API was130.14TH/s, so a return to the pre-test ~333TH/s was NOT yet shown. Confirm normal
   sustained fresh mining output and accepted shares without changing/restarting anything.
   The panel API may average a pause; use fresh log timestamps to distinguish it. If full speed
   remains absent, stop new GPU tests and report current readings; preserve the working process.
2. NEW worktree for this revision, only Mint4090. Preserve tested local pidfd identity/all-thread-T,
   cgroup/session cleanup, live UUID/currentPL, operation lock, independent watchdog and stronger
   return criteria. Never use concurrent override. No GPU, fan, driver, miner/pool/wallet/settings
   change or work on3060/Hive. No performance rerun; only this compatibility check.
3. While mining continues:
   python3 tools/proof_fixtures.py --unpack build/proof-fixtures
   make build/protocol-cpu
   build/protocol-cpu build/proof-fixtures build/proof-cpu-transcripts.jsonl
   python3 tools/proof_fixtures.py --compare build/proof-cpu-transcripts.jsonl
   These are small CPU checks; no Rust installation or oracle compilation on the rig.
4. Reuse the already successful standalone sanitizer2025.3.1 by its pinned archive/file hashes.
   Do not download/install/debug the system2022 sanitizer or repeat prior CPU-true/minimal CUDA
   probes. Rebuild only bench with existing nvcc to add actual transcript export; kernel file hash
   stays91e9721506867dda5872267c465b0ee2c33596f96b54d788641e5d163816c352.
   Verify --help includes --export-transcripts before pause. Merge local safety changes carefully.
5. One guarded check under successful standalone sanitizer, NEW snapshot/lock/watchdog70s,
   guard50s/test-cgroup58s/hard total pause<=90s. Guard/bench options:
   --mode check --fixtures <worktree>/build/proof-fixtures
   --export-transcripts <worktree>/build/proof-gpu-transcripts.jsonl
   plus existing --run-gpu/actualUUID/actualPL/pausedPID/start-ticks and --sanitizer where applicable.
   Require all6 fixtures x4 variants (fullC/debug transcript AND non-debug transcript), memcheck0,
   leak0 and test exit0. Export is from actual stage64 non-debug output, not the golden array.
6. Kill test cgroup BEFORE SIGCONT in every path. Require fresh hashrate AND (job OR share),
   same original miner identity/settings/no duplicates, then read-only confirmation of return to
   pre-pause throughput; don't call positive-but-slow API a full-speed recovery. Keep independent
   watchdog until mining return conditions are met. Do not fabricate or bypass gate results.
7. After recovery, without CUDA:
   python3 tools/proof_fixtures.py --compare build/proof-gpu-transcripts.jsonl
   Save/export this small JSONL along with full check/sanitizer output and recovery report.
   I can feed it into the already built official Rust verifier here; no Rust installation needed there.
8. If active public job parameters already exist in readable API/log/cache, record only non-secret
   certificate rule, MMA type, K/rank, row/column patterns, dimensions and difficulty format.
   Do not start a new miner, connect with credentials, capture wallet/auth traffic or change log/pool
   configuration to obtain them. If unavailable, explicitly mark active-job compatibility unknown.
9. Stop on any mismatch/error and restore original mining. No extra pauses, tuning, benchmarks,
   network-share submission or deployment into SRBMiner. Deliver actual transcript file, outputs,
   pause duration, recovery including throughput, and public-job fields if already available.
