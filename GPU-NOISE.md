# Revision 0.10.0 — step 3: GPU noise

Current work replaces CPU noise generation with CUDA kernels. Raw random matrices and keyed
Merkle trees remain CPU work. This is a PARTIAL implementation of step 3, not completion of
all GPU preparation and not a measured speedup.

| Step | Evidence |
|---|---|
|1 Persistent GPU process|Previous e3c4af5 Mint4090 report: 82 requests, one PID, allocation generation 1.|
|2 RAM and overlap|Previous report: 10.895839M fresh groups/s over 480.412s; zero submitted shares. Comparison to earlier own run is descriptive, not an SRBMiner speedup.|
|3 GPU preparation|Noise implemented and compiled; raw matrices/Merkle still CPU. New GPU execution pending.|
|4 Local verification|54 Python checks; official whole-array noise comparison: 835584 bytes, four cases, 26 verified proofs. Actual CLI + CPU-reference worker + loopback: eight verified proofs. Mock responses are not real pool shares.|
|5 New Mint4090 run|Not executed here. Use the ONE combined task below.|

## Changes

`--pipeline --gpu-noise` selects raw preparation and GPU noise. The raw header is 188 bytes,
with separate original raw A/BT arrays. At the full 131072x4096 profile this avoids producing,
writing and retaining a second 1GiB CPU-noised payload. This is a byte-count calculation, not a
throughput prediction. The GPU receives raw bytes, generates keyed uniform noise/permutations,
adds them in place, range-checks, then runs the unchanged stage64 GEMM and hash filter.

One stream orders both matrices and reused scratch. Persistent buffers retain their capacities.
Per-batch metadata reports GPU_noise_applied and CUDA-event GPU_noise_milliseconds; overall
performance.json remains full wall time, includes preparation/stale work and does not convert
our dense TOP/s to SRBMiner TH/s. No CPU fallback when GPU noise was requested.

The prepared Rust bridge is rebuilt and source/checksum pinned. New commands work-prepare-raw
and work-reference-noise use the pinned official root/seed/noise/proof implementation. The latter
is small-input validation only; it produces all reference bytes independently of the CUDA code.
No fee, pool, wallet, power, fan, clock, driver, service or production-miner change is included.

## Reproduce without GPU, while mining continues

    python3 tools/prepare_miner.py
    make build/work-cpu build/test-noise-reference
    python3 tests/run_gpu_noise_cpu.py --oracle build/pearl-protocol-oracle --out build/noise-cases
    python3 tests/run_miner_integration.py --pipeline --gpu-noise --oracle build/pearl-protocol-oracle --engine build/work-cpu

Use a NEW fixture output directory. cases.json contains absolute paths for this checkout.
Synthetic easy targets are ONLY these local fixtures and must never enter a live pool session.

## ONE task for local Codex — Mint RTX4090 only

Do this within the existing authorization of at most 600 seconds total mining pause. No extra
approval loop. Do not pause mining until build, CPU checks and all recovery controls are ready.
Do not run historical tasks, ABBA, old six fixtures or installations. No 3060/Hive operations.

1. New pinned checkout; verify CHECKSUMS.sha256. Build with EXISTING nvcc; install the included
   source-pinned bridge using tools/prepare_miner.py, without installing Rust/CUDA/drivers.
   Run the above CPU checks while SRBMiner continues. Keep private config/wallet out of logs.
   Prepare a SECOND independent raw input with the same case-2 profile (rank256,K4096,32x32,
   proof16) using work-prepare-raw. Save CPU hits with build/work-cpu and verify with work-finalize.
   Check it has a different batch ID, four hits and the same geometry as case 2.
2. Reuse the verified root-owned pidfd/start-ticks recovery controller, operation lock,
   all-thread-T/idle/no-other-compute guards, independent watchdog and cgroup containment.
   Record original identity, protected files, PL310W, core/memory/offset and both fans. Preserve
   exact settings; no tuning commands. Snapshot fresh normal ~333TH/s baseline. Known private
   tmpfs parent recorded in root recovery plan; sufficient RAM (>=12GiB) and tmpfs, no disk fallback.
3. Arm watchdog at590s before SIGSTOP. Entire experiment cgroup deadline555s, all experiment
   processes UID1000. Pause only the original pidfd identity; verify all threads T and idle GPU.
   Isolate its live UUID. Total pause including checks, cleanup and resume MUST stay <=600s.
4. Changed-path checks first, with a combined <=60s deadline and no retry:
   For each of the FOUR cases, run tools/test_4090_mint.py --run-gpu --mode noise-check
   --work-input <raw_manifest> --noise-reference <official_reference> --sanitizer
   --expected-power-limit-w 310 --gpu <UUID> --paused-pid <PID>
   --paused-start-ticks <TICKS> --allow-concurrent-miner --timeout-sec 12.
   Use the already verified standalone Sanitizer2025.3.1 bundle. Require exit0, memcheck0,
   no leaks, noise_correctness passed and ALL array bytes matched. Missing tools is a failure,
   not permission to install, bypass or start repeated probes.
5. Still in that same deadline/pause, use ONE native --mode worker under the known sanitizer
   with --run-gpu --allow-concurrent-miner --paused-pid/--paused-start-ticks. Feed case2 raw
   and the second independent same-shape raw input, then QUIT (protocol documented in
   PIPELINE-REBUILD.md step5). Require one native PID, done sequences1/2, allocation generation1
   for both, exit0/memcheck0/leaks0. Compare ALL actual hit indices/transcripts to their CPU
   files, require raw_noise_input=true/noise_backend=GPU, and officially work-finalize BOTH.
6. If all pass and budget remains, same pause/cgroup: ONE live window420s:

       python3 tools/pearl_miner.py --pipeline --gpu-noise --config <private-config>
         --oracle <new-verified-oracle> --engine <new-verified-bench>
         --allow-live --enable-submit --extended-test --measure-stability --duration 420
         --stop-after-accepted 0 --gpu <UUID> --expected-power-limit-w 310
         --paused-pid <PID> --paused-start-ticks <TICKS>
         --evidence <new-private-evidence> --workdir <new-private-control-dir>
         --ram-dir <root-plan-private-tmpfs-parent>

   Original pool/wallet/full profile remain. No synthetic target, retry, reconnect or extending
   the time to chase a share. Abort on rejection/unknown/error/drift. Sample board power, clocks,
   fans, temperature read-only. Save full native batch output including noise milliseconds.
7. On EVERY outcome kill/reap the ENTIRE experiment cgroup and prove empty BEFORE SIGCONT.
   Remove only validated disposable tmpfs after consumers die. Confirm same original PID/start
   ticks/exe/argv/env/cwd/protected settings, no duplicates, fresh hash and jobs or accepted share,
   sustained baseline throughput. Session counters may reset on pool reconnect: document that
   separately; never substitute an old share for current work. Disarm watchdog after recovery.
8. Return REPORT-GPU-NOISE-4090.md, unabridged sanitizer/worker logs, performance.json, telemetry,
   CPU/GPU hit/proof checks and restoration evidence. Compare fresh full-wall groups/s to prior
   10.895839M/s only with identical full profile and explicitly label differing time/network/jobs.
   Report stage overlap, stale/cancelled work, one-PID generations, GPU noise time and accepted/
   rejected/unknown counts. A slower result is valid evidence. Zero shares is not proof of
   invalid computation; one share is not proof of superior speed. No production deployment.

This task is prepared for the local rig Codex; it has NOT been run by this environment.
