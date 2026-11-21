# 0.13.0 — computational kernel192x256 /384 threads

This changes the actual GEMM/MMA kernel geometry, not just its scheduler or reports. GPU speed
has NOT been measured here. The prior e84c917 result was28.569652M fresh groups/s and one real
accepted proof; it did not improve the prior throughput. This candidate remains explicitly
selected, with the proven256-thread kernel still the DEFAULT/control. No production deployment.

## New kernel

| Property | Control | Candidate |
|---|---:|---:|
| CTA tile MxN |128x320|192x256|
| Threads / warps |256 /8|384 /12|
| Warp grid |4x2|3x4|
| MMA fragments per warp |2x20|4x8|
| Accumulator registers/thread |160|128|
| Compiler registers, proof16 |224|166|
| Compiler registers, proof8 |224|167|
| Shared bytes, proof16 |81920|83968|
| Shared bytes, proof8 |92160|96256|
| CTAs for8192x8192 |1664|1376|

For a full8192x8192,K4096 slab the nominal valid matrix input requests decrease from3019898880
bytes to2516582400 bytes:16.6667%. This is an exact tile/request calculation, NOT measured DRAM
traffic or a hashrate prediction. Cache behavior, occupancy/latency and device/compiler effects
can still make this candidate slower. More warps per block does not guarantee higher throughput.

The64-wide double buffer, cp.async32/64 checkpoints, signed INT8 MMA, cumulative INT32 sums,
16-slot rolling transcript, keyed filter/targets, GPU noise, root preparation and proof verifier
semantics remain. The new3x4 warp grid owns4x8 MMA fragments/warp. Shared history dimensions,
prefetch ownership, global/debug output and launch/resource geometry all follow192x256.

Selected only with native --candidate 384, or live --kernel-threads 384. Default256 remains.
Every mining_batch reports kernel_threads; performance.json records requested_kernel_threads.
No automatic fallback/switch, fee, profile, pool, wallet, driver, clock, fan or power change.

## Verification completed here, no rig pause

- CUDA13.0.88 compiled SM86/89, debug/nondebug, proof8/16:166/167 registers, zero stack bytes,
  spill stores and spill loads in ALL eight new instantiations. Report in miner/KERNEL384-CPU-RESULT.json.
- Independent NumPy staged-load/full-matrix/transcript model: partial192/256 tile boundaries,
  rank32/128/256, proof8/16, partial64-wide K stage and17-checkpoint rolling-slot reuse. New3x4
  warp-fragment/proof ownership covers every cell/proof exactly once; shared load banks distinct.
-59 Python tests pass. Actual CLI/persistent CPU-reference/official-proof loopback still passes
  and retains all eight verified proof artifacts. This CPU integration does NOT execute384.
- Rust bridge/binary, root/RNG preparation, GPU noise and compact-hit filter unchanged. Native
  new geometry and its new selection path still require the targeted actual GPU checks below.

## Fast reject gate before a long pause

New kernel384-compare compares resident GEMM kernels256/stage64 versus384/stage64 in the SAME
binary, on8192x8192,K4096,rank256,proof16. Four legs A/B/B/A, exactly1s each and.25s warmup each:
5s nominal measured/warmup budget plus allocation/initialization/cleanup. It does not run a pool.
The old generic benchmark compared against stage32; DO NOT use that mode for this decision.

Summary candidate_faster_for_live=true requires mean control/candidate median time ratio>1.02
AND BOTH B legs faster than BOTH A legs. Otherwise restore immediately without420s live work.
This is a short on-card rejection test, not proof of stable throughput/earnings. No retries.

## ONE local Codex task, Mint RTX4090 only

Existing authorization: original mining pause<=600s total. PL310W, exact core/memory/offset,
both fans, pool/wallet/profile unchanged. No3060/Hive. Keep root-owned pidfd/start ticks,
operation lock, all-thread-T/idle/unique compute, watchdog/cgroup and current-GPU recovery checks.
No system installs and no production deployment. Report the current step out of five.

1. BEFORE PAUSE, new pinned checkout/checksums and native build with existing nvcc. Inspect local
   ptxas/cuobjdump for384 proof8/16: registers<=168, no spills/local stack; do not pause if this fails.
   Prepare unchanged pinned oracle with tools/prepare_miner.py. Build CPU helperwork-cpu. Prepare
   the three compact boundary cases using tests/prepare_compact_check.py into a NEW directory;
   same1030 CPU hits/10 official sampled proofs as before. These are local synthetic inputs,
   never submitted. No Rust/NumPy/toolkit installation and no old noise/full-size root/compact
   filter test replay: those sources are unchanged. Save existing private receipts/proofs.
2. Snapshot fresh ~333TH/s baseline/current identity/settings. Known sanitizer2025.3.1 already
   verified offline, private tmpfs parent in root plan, >=12GiB free RAM, no disk fallback.
   Before SIGSTOP arm watchdog590s; whole experiment cgroup RuntimeMax555s, KillModecontrol-group,
   all childrenUID1000, selected live UUID. Stop exact original pidfd, prove every threadT and idle.
3. NEW kernel correctness only, within the common60s changed-path budget:

       python3 tools/test_4090_mint.py --run-gpu --mode kernel384-check --sanitizer
         --gpu <UUID> --expected-power-limit-w 310 --timeout-sec 15
         --paused-pid <original-PID> --paused-start-ticks <ticks>
         --allow-concurrent-miner

   This runs ONLY384 on the six known goldens, debug/full matrix and nondebug transcript, not
   historical kernels. Require kernel384_correctness passed/fixtures6/full matrix/nondebug,
   other_kernels_executed=false, local bytes0/registers<=168/active blocks>=1, exit0/errors0/leaks0.
   Then ONE worker under same known sanitizer, same pause/cgroup, explicit --candidate 384:

       <sanitizer> --injection-path <verified-path> --tool memcheck --error-exitcode 86
         --leak-check full <new-bench> --run-gpu --mode worker --candidate 384
         --allow-concurrent-miner --paused-pid <original-PID> --paused-start-ticks <ticks>

   Write seq1/2/3 TAB raw_manifest TAB NEW GPU_hits from cases.json, then QUIT. Require same PID,
   done1/2/3, intentional geometry generations1/2/3, groups4/513/513, kernel_threads384 on all
   batches, exit0/errors0/leaks0. Run tests/verify_compact_outputs.py to compare ALL1030 actual
   GPU hits/transcripts and officially verify ten sampled GPU proofs, including0/511/512 around
   both slab boundaries. Preserve outputs. This executes the new kernel through the real worker.
   Any error/mismatch/budget failure: STOP/restore/report without retry or comparison/live load.
4. SAME pause, one SHORT matched comparison, no sanitizer and no historical benchmark:

       python3 tools/test_4090_mint.py --run-gpu --mode kernel384-compare
         --duration 1 --warmup .25 --rounds 1 --timeout-sec 20
         --gpu <UUID> --expected-power-limit-w 310
         --paused-pid <original-PID> --paused-start-ticks <ticks>
         --allow-concurrent-miner

   Require four benchmark records order256/384/384/256, both stage_k64, same resident inputs,
   and summary candidate_faster_for_live=true. If false, STOP and restore immediately; report
   the measured ratio and skip live420. No repeated legs, second attempt or settings tuning.
5. ONLY IF faster, all correctness gates passed and >=440s remain before cgroup deadline:
   SAME pause/cgroup, one full live420s window with explicit new kernel:

       python3 tools/pearl_miner.py --pipeline --gpu-noise --kernel-threads 384
         --config <existing-private-config> --oracle <unchanged-source-pinned-oracle>
         --engine <new-verified-engine> --allow-live --enable-submit
         --extended-test --measure-stability --duration 420 --stop-after-accepted 0
         --gpu <UUID> --expected-power-limit-w 310
         --paused-pid <original-PID> --paused-start-ticks <ticks>
         --evidence <new-private-evidence> --workdir <new-private-control-dir>
         --ram-dir <validated-private-tmpfs-parent>

   Original full profile/target/pool/wallet, natural Rayon40 unchanged, fresh diagnostic worker.
   No synthetic live target, retries/reconnects, deadline extension or automatic kernel fallback.
   Require requested_kernel_threads384 and every native batch kernel_threads384; capture all
   phase timings, fresh/stale groups, counters and read-only settings/power/utilization telemetry.
   Abort on rejection/unknown/error/drift. Retain actual candidate proofs/reports and receipts.
6. EVERY exit: terminate/reap ENTIRE experiment cgroup, prove empty BEFORE SIGCONT. Clean only
   validated tmpfs after consumers die. Resume SAME original identity, confirm unique miner,
   unchanged protected files/settings and fresh current GPU0/API ~333TH/s plus work/share and
   sustained samples. Do not use6hr average. Disarm watchdog after recovery; final units inactive.
7. Return REPORT-KERNEL384-4090.md, complete new-kernel sanitizer logs, actual GPU hit/proof checks,
   all four short comparison legs/decision, and live performance/phase/proof/telemetry if run.
   If rejected, the short comparison and successful restoration ARE the result: do not chase
   shares or spend420s on an unpromising candidate. If live ran, compare against28.569652M/s with
   matched profile/target/thread pool and explicit differing jobs/stale; no SRBMiner TH/s claim.

The native CLI uses separated flags/values, e.g. --candidate 384 and --error-exitcode 86. Compact
spelling above in prose is shorthand only. No new real GPU test/hasrate result is claimed here.
