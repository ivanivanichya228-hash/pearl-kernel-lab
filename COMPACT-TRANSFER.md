# 0.12.0 — step 3: compact GPU results, fewer host round trips

Current new implementation, not a measured rig speedup. Previous 84d5b58 report: 28.882358M
fresh groups/s, 187 requests, one stale candidate, no sent/accepted real share. Current change
has not executed on a real GPU here. Production SRBMiner is untouched.

## Concrete change

The full profile has 16x16=256 slabs. Previously each slab did a stream synchronization and
host count read; hits needed another index copy and separate 64-byte transcript copies.

Now a same-stream filter APPENDS global index plus 16 transcript words into one persistent
GPU queue. It copies winning words BEFORE a later GEMM overwrites the transcript slab. Queue
capacity4096, same total hit bound as before. Count includes all overflow: overflow aborts the
whole batch without partial output; it never silently truncates. The queue resets once per
batch, not once per slab. Host reads ONE final count and, when nonempty, ONE compact payload.
The existing separate noise range-check synchronization remains intact. Mathematical GEMM,
noise, keyed digest, target comparison, roots, profile and proof verification are unchanged.
Filter storage and executor ordering DID change and require the targeted GPU gate below.

Event markers now separate H2D, noise, compute/filter and result-copy phases. These are stream
phase intervals and may include host-induced idle gaps, not pure hardware busy time or PCIe
bandwidth measurements. native_batch_wall includes mapping/allocation/write overhead; Python
full-wall metrics also include guards/IPC/CPU/network/stale work. Do not sum overlapping stages.

Raw native records are saved in persistent-engine.events.jsonl. Validated hits.json and ALL
successfully verified candidate proofs/reports are saved outside disposable work before submit
freshness decisions. A stale verified candidate is not lost on workspace cleanup. This does
not make stale work valid for submission and does not claim an accepted real share.

## Local evidence

- CUDA13.0.88 compile SM86/89 succeeds. GPU execution/speedup pending.
- Native compact mapping matches the independent prior slab mapping for proof8/16, partial
  slabs and global overflow bounds. A mixed common target has100hits/95misses among195 vectors.
-56 Python tests pass, including strict new-path evidence and missing/nonzero leak rejection.
- Actual CLI + persistent CPU reference + official bridge + loopback: eight proofs independently
  checked and retained after work cleanup, including the two deliberate mock rejections.
  Mock responses are not real pool acceptance. Worker records survive cleanup too.
- Three new CPU-reference inputs: normal32x32/K4096/rank256/proof16; row-boundary8208x8/K2048/
  rank128/proof8; column-boundary16x8208/K2048/rank128/proof16. All1030 hit transcripts computed;
  ten normal/edge proofs officially verified. CPU validation cap raised from2^26 to2^29 scalar
  multiply terms to permit these bounded boundary cases; this affects only tests/work_cpu.cpp,
  not production profile/runtime authorization. Bridge/bundled Rust executable unchanged.

## Five-step progress

1. Persistent process and2. RAM overlap previously verified on Mint4090.
3. Compact result transfer implemented; actual GPU validation/performance still pending.
4. Build, index model and CPU integration passed here.
5. ONE targeted changed-path check followed by420s live window is prepared below, not run here.

## ONE local Codex task — Mint4090, original settings

Use the existing authorization: total original-miner pause <=600s. Only Mint4090, PL310W,
core/memory/offset/both fans/profile/pool/wallet unchanged. No3060/Hive operation. No deployments.
Do not replay historical tests or issue repeated approval requests. Preserve the proven root
pidfd/start-ticks/controller, lock, all-thread-T/idle/unique-compute, watchdog/cgroup controls.

### Prepare while SRBMiner continues

1. NEW pinned checkout, checksums. Rebuild changed native code with EXISTING nvcc. No CUDA/Rust/
   driver/tool installs. Prepare unchanged pinned oracle with python3 tools/prepare_miner.py.
   Build CPU helpers and prepare the NEW boundary cases ONCE:

       make build/work-cpu build/test-compact-hits
       build/test-compact-hits
       python3 tests/prepare_compact_check.py --oracle build/pearl-protocol-oracle --out build/compact-cases
       python3 tests/run_miner_integration.py --pipeline --gpu-noise --oracle build/pearl-protocol-oracle --engine build/work-cpu

   cases.json has absolute raw input, CPU-hit and NEW GPU-output paths. CPU cases are synthetic
   LOCAL ONLY; never submit them. Require1030 CPU hits and10 official sampled proofs. Need not
   repeat the old full-size root audit, four noise cases, old six fixtures or ABBA.
2. Verify the already-working standalone Sanitizer2025.3.1 bundle offline; no minimal-CUDA probe,
   reinstall or version switching. Snapshot original exact identity/settings and fresh normal
   ~333TH/s baseline. Recovery must use CURRENT GPU0 hash, not6hr average. Check >=12GiB RAM and
   private tmpfs parent recorded in root plan, no disk fallback; bounded proof/log evidence private.

### One combined pause, no retries

3. Arm independent root watchdog590s BEFORE original pidfd SIGSTOP. RuntimeMax555s for ENTIRE
   experiment cgroup, all children UID1000, live UUID isolation. Prove all original threads T,
   GPU idle/no other compute. Keep actual PL310/clock/memory/offset/both fans read-only guarded.
4. Entire changed-path validation including verifier <=60s:
   FIRST one targeted compact-check, <=15s, known sanitizer, no old noise or math fixture replay:

       python3 tools/test_4090_mint.py --run-gpu --mode compact-check --sanitizer
         --gpu <UUID> --expected-power-limit-w 310 --timeout-sec 15
         --paused-pid <original-PID> --paused-start-ticks <start-ticks>
         --allow-concurrent-miner

   Require compact_filter_correctness passed,195 vectors,eight capacity cases, transcript retention,
   exact mixed target and empty-append checks; exit0/errors0/leaks0. This tests queue count
   accumulation, capacities0/1/195/390, overflow sentinels and both proof widths. No bypass.
5. In SAME validation budget/cgroup/pause, ONE native worker under that known Sanitizer:

       <sanitizer> --injection-path <verified-path> --tool memcheck --error-exitcode 86
         --leak-check full <new-bench> --run-gpu --mode worker --allow-concurrent-miner
         --paused-pid <original-PID> --paused-start-ticks <start-ticks>

   Feed seq1/2/3 + TAB absolute raw_manifest + TAB GPU_hits path from cases.json, then QUIT.
   Same native PID, done sequences1/2/3, generation1/2/3 (intentional geometry growth), exit0,
   errors0/leaks0, no restart. mining_batch groups4/513/513, slabs1/2/2, compact_hit_collection=true,
   result_count_readbacks=1 and GPU_noise_applied=true. Save complete output.
   Then, still within the validation budget:

       python3 tests/verify_compact_outputs.py --oracle build/pearl-protocol-oracle
         --cases build/compact-cases/cases.json --out build/compact-GPU-verified

   It compares ALL1030 actual GPU hits/transcripts and independently officially verifies ten GPU
   proofs, including global indices0/511/512 around BOTH slab boundaries. Do not replace actual
   output with CPU values. If ANY check fails or budget is insufficient, STOP/restore/report;
   no retry or follow-on live load.
6. If all pass, same pause: ONE fixed420s live measurement:

       python3 tools/pearl_miner.py --pipeline --gpu-noise --config <existing-private-config>
         --oracle <unchanged-verified-oracle> --engine <new-verified-bench>
         --allow-live --enable-submit --extended-test --measure-stability --duration 420
         --stop-after-accepted 0 --gpu <UUID> --expected-power-limit-w 310
         --paused-pid <original-PID> --paused-start-ticks <start-ticks>
         --evidence <new-private-evidence> --workdir <new-private-control-dir>
         --ram-dir <validated-tmpfs-parent>

   Original pool/wallet/full profile and current natural Rayon pool (previous40), no thread
   override, retries/reconnect/deadline extension. Stop on rejection/unknown/error/drift. Collect
   native events and phase timings, full-wall fresh/stale rates, power/utilization/temperature/
   clocks/fans samples. Verify compact flag/readbacks on all completed native packets. Retain
   every verified candidate binary/report, even stale: mark sent/accepted separately. No secrets.
7. EVERY exit: kill/reap ENTIRE experiment cgroup and prove empty BEFORE SIGCONT. Delete only
   validated disposable tmpfs after consumers die. Restore exact original identity/settings,
   unique original miner, fresh current GPU0/API ~333TH/s and work/accepted-share with sustained
   samples. Disarm watchdog only after recovery; confirm controller/GPU/watchdog units inactive.
8. Return REPORT-COMPACT-TRANSFER-4090.md, performance.json, complete compact-check/worker logs,
   GPU-vs-CPU/proof checks, native phase events, candidate proofs/reports, telemetry and recovery.
   Compare fresh full-wall groups/s against28.882358M/s with matched profile/target/thread pool;
   job/network/stale differences explicit, not controlled A/B or SRBMiner/earnings evidence.
   Identify whether H2D, compute/filter or host/IPC dominates. No new miner pause just to profile.

No home-rig GPU test for0.12.0 has happened here. No speedup or live-share acceptance is claimed.
