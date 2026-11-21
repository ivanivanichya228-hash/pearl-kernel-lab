# Computational kernel: collective matrix loads, scalar384 control

Goal: a Pearl miner faster than SRBMiner at the existing310W limit. That goal is NOT yet
achieved or established by this revision. CPU tests/compiler resources are not GPU speed.
Previous384 live result:29.677104515M fresh groups/s, one pool-accepted proof, no measured
advantage over SRBMiner. The later pinned-transfer candidate was rejected:0.978531813x,
about2.15% slower than scalar384. Keep --transfer-overlap OFF throughout this experiment.

Progress: steps1/2 already implemented, current work is step3 (compute kernel), step4 is
local build/verification, step5 remains one bounded on-rig validation. Raw RNG/root/Merkle
preparation still uses CPU; do not describe the full preparation pipeline as GPU-resident.

## Actual code change

Explicit --matrix-loads selects a new384-thread192x256/stage64 kernel. Four ldmatrix.x4
loads supply the four A fragments and eight ldmatrix.x2 loads supply/reuse the eight B
fragments per warp/K32. They replace scalar shared-memory word loads; BT is already
transposed in storage, so no .trans modifier is used. The .b16 load is bit-preserving
packing: MMA remains signed INT8 m16n8k32, not FP16 computation. Sources and lane layout:
https://docs.nvidia.com/cuda/parallel-thread-execution/index.html#warp-level-matrix-instructions-ldmatrix

All intermediate rank checkpoints, cumulative INT32 sums, rolling transcripts, target,
noise, proof format, pool protocol and verification remain unchanged. Geometry/shared
buffer layout are identical to scalar384. Flag defaults OFF. It is rejected with256,
CPU mock, or transfer overlap; no silent fallback or automatic selection.

Compiled with CUDA13.0.88 for SM86/89: ALL eight debug/nondebug/proof8/16 new instantiations
use168 registers,0 stack bytes,0 spill stores/loads. Shared bytes are83968(proof16) and
96256(proof8). At-home CUDA12.0 must independently pass the resource check BEFORE pause;
a different compiler may allocate differently. No hardware speedup is predicted.

Offline: independent documented ldmatrix lane model checks every fragment byte for all
12warps,4A/8B fragments, both K32 substeps, reconstructs operands and verifies signed MMA.
Existing192x256 model checks full matrix/transcripts, boundaries, ranks and rolling slots.
71 Python tests and CPU contract/fixture/validation checks pass. Actual CPU-reference CLI
loopback checks all eight official proofs; it does not execute this new GPU kernel.
See miner/LDMATRIX-CPU-RESULT.json for machine-readable limits/evidence.

## Single local Codex task: Mint RTX4090 only

Use a NEW pinned checkout of this revision; verify CHECKSUMS.sha256. Follow the existing
root-owned controller, never an improvised sudo script. Existing authorization: total
original mining pause <=600s, one attempt, no installs, production deployment, tuning,
reconnects or retries. Only room-room@192.168.1.98, never3060/Hive. Preserve PL310W,
core lock2600/current2610, offset+300, mem405, both fans55%, wallet/pool/protected files.
Resolve CURRENT original PID/start ticks; do not hardcode historical PID4158372.

1. BEFORE PAUSE: build native with existing nvcc; inspect all new384 matrix-load functions
   in ptxas/cuobjdump: registers<=168,0 stack/spill/local bytes; check help has --matrix-loads,
   matrix-check and matrix-compare. Prepare unchanged pinned oracle using tools/prepare_miner.py
   and CPU work-cpu helper. Prepare three NEW local-only boundary cases with
   tests/prepare_compact_check.py (1030 CPU hits,10 official sampled proofs). Reuse known
   sanitizer2025.3.1 bundle, no downloads/installation. Verify idle-test plan/timings, private
   tmpfs >=12GiB, exact GPU UUID, fresh current GPU0/API baseline. Preserve prior evidence.
2. Arm independent watchdog590s BEFORE SIGSTOP; experiment cgroup RuntimeMax555s and
   KillMode=control-group; children UID1000. Root operation lock, original pidfd/start ticks,
   all threads T, GPU idle/no other compute. Everything below shares this ONE pause/deadline.
3. Changed kernel correctness ONLY, common60s budget for this step:

       python3 tools/test_4090_mint.py --run-gpu --mode matrix-check --sanitizer
         --gpu <UUID> --expected-power-limit-w 310 --timeout-sec 15
         --paused-pid <PID> --paused-start-ticks <TICKS> --allow-concurrent-miner

   Require kernel384_correctness matrix_loads=true,fixtures6,full matrix/nondebug true,
   other_kernels_executed=false; resources<=168/local0/activeblocks>=1; exit0/errors0/leaks0.
   Then ONE sanitizer-wrapped worker, same controller and pause:

       <verified-sanitizer> --injection-path <verified-path> --tool memcheck
         --error-exitcode 86 --leak-check full <new-bench> --run-gpu --mode worker
         --candidate 384 --stage-k 64 --matrix-loads --allow-concurrent-miner
         --paused-pid <PID> --paused-start-ticks <TICKS>

   Feed seq1/2/3 TAB raw_manifest TAB NEW GPU_hits paths from cases.json, then QUIT.
   Require same process, done1/2/3, generations1/2/3, groups4/513/513; all mining_batch
   kernel_threads384,matrix_loads=true,pinned_transfer_overlap=false. Exit0/errors0/leaks0.
   tests/verify_compact_outputs.py must compare all1030 GPU hits/transcripts against CPU
   and officially verify10 sampled GPU proofs, including row/column slab edges511/512.
   No old noise/filter/root/full-size sanitizer replay. Any failure: restore, stop, report.
4. SAME pause, one short matched scalar384(A) versus ldmatrix384(B) A/B/B/A:

       python3 tools/test_4090_mint.py --run-gpu --mode matrix-compare
         --duration 1 --warmup .25 --rounds 1 --timeout-sec 20
         --gpu <UUID> --expected-power-limit-w 310
         --paused-pid <PID> --paused-start-ticks <TICKS> --allow-concurrent-miner

   Exactly four legs, all384/stage64, matrix_loads false/true/true/false, resident same
   8192x8192,K4096,rank256,proof16. Post-compare full transcript equality required.
   matrix_comparison candidate_faster_for_live=true requires speed_ratio>1.02 and BOTH B
   legs faster than BOTH A legs. On false/mismatch/error: restore NOW, no420s window.
   Do not use generic bench, old256 comparison or rejected transfer-overlap benchmark.
5. ONLY if all gates pass and >=440s remain before cgroup deadline, one full420s live:

       python3 tools/pearl_miner.py --pipeline --gpu-noise --kernel-threads 384 --matrix-loads
         --config <existing-private-config> --oracle <unchanged-pinned-oracle>
         --engine <new-engine> --allow-live --enable-submit --extended-test
         --measure-stability --duration 420 --stop-after-accepted 0
         --gpu <UUID> --expected-power-limit-w 310
         --paused-pid <PID> --paused-start-ticks <TICKS>
         --evidence <new-private-evidence> --workdir <new-private-control-directory>
         --ram-dir <validated-private-tmpfs-parent>

   NO --transfer-overlap. Original full profile/target/wallet/pool, natural Rayon40, fresh
   diagnostic worker. Abort rejection/unknown/error/settings drift; no target relaxation,
   fallback, retries, deadline extension or production installation. Retain actual proof
   bytes/reports/pool receipts, fresh/stale ledger, all phase timings and read-only telemetry.
   Require matrix_loads_requested=true, transfer_overlap_requested=false, every native batch
   matrix_loads=true,kernel_threads384,pinned_transfer_overlap=false. Compare against prior
   29.677104515M fresh groups/s with job/stale/compiler differences explicitly acknowledged.
6. EVERY exit: kill/reap ENTIRE experiment cgroup, prove empty BEFORE SIGCONT; cleanup only
   validated tmpfs after consumers die. Resume exact original identity; confirm unique
   SRBMiner, unchanged protected settings/files, fresh CURRENT GPU0/API ~333TH/s, new work /
   share evidence and sustained samples. Six-hour average is not recovery evidence. Disarm
   watchdog only after strict confirmation. Leave transient units inactive.
7. Return REPORT-LDMATRIX-4090.md, full compiler/sanitizer logs,1030-hit/10-proof validation,
   all four matched legs/decision, live performance/proofs/telemetry only if actually run,
   pause length and recovery proof. A rejected short gate is a result; do not chase a share.
   Keep live counters null if live was skipped. Do not equate groups/s or matrix TOPS with
   SRBMiner TH/s or claim faster-than-SRB from one accepted share. End-to-end accepted work
   at equal settings is the ultimate criterion; this gate only rejects weak kernels early.
