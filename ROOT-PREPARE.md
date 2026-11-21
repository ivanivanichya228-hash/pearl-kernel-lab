# 0.11.0 — step 3: remove full-tree preparation and parallelize raw RNG

This revision changes ONLY the CPU preparation/official bridge. CUDA source, GEMM, noise,
filter, worker IPC, scheduler, raw header, profile, target and submit protocol are unchanged.
Raw random matrices and commitment roots are still CPU work; this does not claim GPU Merkle.

## Implemented

Previously each packet constructed both full official MerkleTree objects. Preparation then
used only their roots; both trees and all retained data were discarded without making proofs.
Each tree also received a pad_to_chunk_boundary clone, even for already aligned input.

The new preparation calls the OFFICIAL Blake3Hasher::hash on borrowed aligned data, in parallel
for A/BT. Nonaligned inputs keep official zero padding. Hashing already uses the official SIMD/
Rayon implementation. No new hash implementation or consensus rule is introduced. Full official
Merkle trees remain unchanged in finalize, reference_noise and the independent new root audit.

Raw generation fills independent 4MiB chunks using fresh OS-seeded StdRng CSPRNGs on Rayon.
Seeds are never fixed, reused or derived only from jobs. The canonical signed INT7 distribution
is unchanged. Allocation and thread usage remain bounded by the existing matrix limits and
Rayon pool. No custom thread-count override is imposed in the live client.

At full M=N131072,K4096, preparation avoids making/retaining full tree data and intermediate
layers for 1GiB raw arrays. Raw output is still 1GiB, backed by the existing tmpfs pipeline.
This is not zero-copy GPU generation. Candidate hits still reconstruct and independently verify
complete official proofs before any live submit. No partial verifier or unchecked roots.

## Evidence here

- Rust: four tests, including full official Merkle root equality for aligned/nonaligned lengths,
  odd/even leaf counts and two keys; parallel RNG range/freshness and official noise equality.
- Four raw cases: 835584 official noise bytes matched, 26 verified proofs. Independent root audit
  checks all 188 manifest bytes against full official trees. It rejects changed A seed, B seed,
  target and raw matrix content. Actual CLI/persistent CPU-reference/loopback verifies eight proofs;
  six mock acceptances/two intentional rejections are NOT live pool results.
- 54 Python tests pass. No GPU execution, card setting change or home-miner pause here.
- Full-profile CPU benchmark: one warmup for each version, then measured A/B/B/A, four Rayon
  threads, same host and tmpfs. Mean before 2.146829s, after 0.526319s: 4.078947x faster PREPARATION.
  Each timed run has 1GiB raw arrays; outside timing, its manifest is independently checked against
  full official Merkle trees. Individual runs and excluded warmups are preserved in
  miner/ROOT-PREPARE-CPU-BENCHMARK.json. These are not Mint4090 or miner hashrate measurements.

The prior Mint4090 GPU-noise report belongs to adb5fe2: 18.359213M fresh groups/s, 118 requests,
zero sent/accepted shares; full GPU noise correctness and official proofs passed. Current build
has not yet run on that rig. Production SRBMiner remains the mining process.

## Current five-step progress

1. Persistent GPU — previously verified on Mint4090.
2. RAM/overlap — previously verified on Mint4090.
3. Preparation — GPU noise verified earlier; CPU RNG/root-only optimization now implemented,
   independently checked and locally timed. Raw RNG/Merkle roots are NOT moved to GPU.
4. New bridge/build and CPU integration — passed here.
5. New end-to-end Mint4090 measurement — pending the SINGLE task below.

## ONE task for local Codex

Do not ask for authorization already given: up to 600 seconds total mining pause, Mint4090 only,
PL310W and exact existing clock/memory/offset/fans/profile/pool/wallet preserved. No3060/Hive work.
Use a NEW pinned checkout and the existing verified recovery/controller; no system installations.

### While SRBMiner continues, no GPU workloads

1. Verify checksums. Compare EVERY src/, include/ and Makefile byte to adb5fe2: all must be identical.
   Reuse/copy the exact known successful native engine after verifying its SHA256
   b3ba3a154fc9c374baa87a1e77b82f6534f25936a14da1d7dcbea6ad7a9f001a.
   Do not repeat CUDA compilation/Sanitizer/noise-check/ABBA/minimal CUDA probes: CUDA is unchanged.
   If the known engine is missing or differs, report that before pausing; no silent substitution.
2. Run python3 tools/prepare_miner.py. New prepared oracle must match miner/oracle-lock.json,
   including source pins. No Rust/toolkit installs. Build ONLY the small CPU helpers:

       make build/work-cpu build/test-noise-reference
       python3 tests/run_gpu_noise_cpu.py --oracle build/pearl-protocol-oracle --out build/root-cases
       python3 tests/check_root_audit.py --oracle build/pearl-protocol-oracle --cases build/root-cases/cases.json
       python3 tests/run_miner_integration.py --pipeline --gpu-noise --oracle build/pearl-protocol-oracle --engine build/work-cpu

   Use new output paths if needed. These CPU fixtures are synthetic LOCAL ONLY, never submitted.
3. Once, prepare one FULL-profile packet on validated private tmpfs with new bridge:
   work-prepare-raw <public-notify> pool/client-reference.json <new-batch-dir>.
   Then work-audit-roots <that-batch-dir> <new-audit-file>. Require passed=true and 1073741824
   raw bytes. Save per-stage timings and new metadata: official-root-only, parallel-OS-seeded-CSPRNG,
   actual Rayon threads. Remove just this disposable input before the live test. This demonstrates
   full-size correctness on the host without a GPU pause. Do not install tuning tools or change
   global Rayon/thread environment. No need to repeat the cloud CPU benchmark to proceed.
4. Validate the root-owned controller's recovery parser BEFORE pause: it must read the CURRENT
   GPU0 hashrate, not the 6hr average. Preserve existing original-PID/start-ticks/config identity
   checks. Prepare a read-only current-row/API recovery audit first, keeping failed artifacts
   untouched. Require fresh hash/jobs or accepted shares and sustained normal ~333TH/s after resume.

### ONE real window, no repeated correctness gates

5. Snapshot exact original identity and settings, normal baseline and live UUID. Preserve known
   pidfd, all-threads-T, idle/no-other-compute and operation-lock checks. Arm independent root-owned
   watchdog590s BEFORE SIGSTOP; experiment cgroup RuntimeMax555s; hard mining pause<=600s including
   cleanup/recovery. All experiment children UID1000, live PL310W sampled without changes.
   Known disposable tmpfs parent recorded in the root plan, >=12GiB free RAM, no disk fallback.
6. Same single pause, real pool420s, fixed window (not chasing first share):

       python3 tools/pearl_miner.py --pipeline --gpu-noise --config <existing-private-config>
         --oracle <new-source-pinned-oracle> --engine <verified-unchanged-engine>
         --allow-live --enable-submit --extended-test --measure-stability --duration 420
         --stop-after-accepted 0 --gpu <live-UUID> --expected-power-limit-w 310
         --paused-pid <original-PID> --paused-start-ticks <original-ticks>
         --evidence <new-private-evidence> --workdir <new-private-control-dir>
         --ram-dir <validated-private-tmpfs-parent>

   Same pool/wallet/full profile, fresh diagnostic worker only. No synthetic target. No reconnect,
   retries, new flags or deadline extension. Abort on rejection/unknown/error/settings drift.
   Collect full stage/native logs, fresh/stale groups, PID/allocation generations, noise timings,
   counts and read-only board power/temperature/clocks/fans/utilization telemetry. Root-only prep
   metadata must be confirmed in private logs before cleanup. Do not copy credentials to reports.
7. Every exit: terminate/reap ENTIRE experiment cgroup, prove empty BEFORE SIGCONT, clean only
   validated tmpfs after consumers die. Resume exact original pidfd; confirm unique original miner,
   argv/env/exe/cwd/config/settings, sustained current ~333TH/s and fresh work. Do not mistake
   rolling averages for current hash. Disarm watchdog after recovery, verify timer/services inactive.
8. Return REPORT-ROOT-PREPARE-4090.md and performance.json, stage logs, telemetry and independent
   full-size root audit/recovery evidence. Compare full-wall fresh groups/s against previous
   18.359213M/s only with matched full profile/target; differing jobs/network/stale remain explicit.
   Include first rejection/proof failure detail if one occurs, without retries. Report all real
   sent/accepted/rejected/unknown counts. No SRBMiner-equivalent TH/s/profit claim or deployment.

No new rig test has been performed here. This instruction replaces GPU-NOISE.md for the NEXT run;
its previous checks already succeeded and are not to be repeated without a new observed problem.
