# Identify the real throughput limiter before another kernel rewrite

Goal remains a real Pearl miner faster than SRBMiner at the existing310W settings. NOT
achieved. This revision is diagnostic tooling, not a faster miner and not another candidate.
Latest on-rig ldmatrix result: scalar4.23936ms / candidate4.24204ms =0.999368x; rejected.
There was no long live test. SRBMiner recovered at about333TH/s after19.664236s pause.

The existing full-batch compute_filter_phase combines two different kernels. Kernel-only
A/B cannot distinguish matrix compute from the BLAKE3 candidate filter, nor explain stalls.
The two new native modes execute the UNCHANGED proven scalar384/stage64 GEMM and compact
filter. src/kernel.cu, src/filter.cu, noise, proof verifier, pipeline, client and all pool
settings are unchanged. No candidate optimization, fee or live pool code is added.

- kernel-diagnose: three warm GEMM/filter pairs, then32 event-instrumented resident pairs.
  Separate CUDA timestamps bracket GEMM and filter, with total CPU wall time retained.
  Input8192x8192,K4096,rank256,proof16; zero synthetic LOCAL target; no network/submission.
  This measures only the resident slab, not CPU preparation, H2D, full-batch rate or earnings.
- kernel-counters: same three warm pairs, then exactly ONE pair. It is intended solely for
  Nsight Compute. Matching launch skip6/count2 collects one GEMM and one compact filter.
  Profiling replay timings are explicitly invalid as speed/efficiency comparisons.
- tools/diagnose_compute.py --preflight: locate existing ncu, read version/help/sections and
  existing counter-permission setting. No CUDA kernels, pause, installation or driver changes.
- Hardware collection explicitly uses --clock-control none --cache-control none. Selected
  SpeedOfLight/Occupancy/SchedulerStats/WarpStateStats/MemoryWorkloadAnalysis sections expose
  issue/occupancy/memory/stall information. Never treat low power alone as an explanation.

Official primary references:
https://docs.nvidia.com/nsight-compute/NsightComputeCli/index.html
https://developer.nvidia.com/ERR_NVGPUCTRPERM

Build checked here with CUDA13.0.88, SM86/89.75 Python tests pass, including corrupted/partial
phase output rejection and profiler limits/clock-control checks. No GPU execution performed
here. The profiler preflight here reports ncu absent; this says nothing about the home rig.

## One local Codex task; current step3 diagnosis, step4 local checks, step5 bounded measurement

Only Mint4090 room-room@192.168.1.98. PL310, core lock2600/current2610, offset+300, mem405,
both fans55, wallet/pool/miner/config/driver/autostart unchanged. No3060/Hive. Use existing
root-owned pidfd/start-ticks recovery controller, operation lock, unique original process,
all-thread-T/idle checks, UID1000 children, independent watchdog, experiment cgroup and strict
current-GPU0/API recovery. Do not run GPU work in parallel with SRBMiner. No tuning/install,
permission edits, driver reload/reboot, new live window or production deployment.

1. While mining CONTINUES: new pinned checkout/checksums; native build with existing nvcc.
   Verify kernel/filter/noise/proof sources unchanged from c49bd82. Check new CLI help.
   Read existing phase/performance logs; preserve earlier proofs/receipts. Run once:

       python3 tools/diagnose_compute.py --preflight --out <NEW-private-preflight-dir>

   Record ncu availability/version and known_admin_only_counters. If absent/restricted,
   do not attempt counter collection or change permissions. This does not block the
   ordinary event timing. If supplied ncu requires any settings changes, skip counters.
   ncu/driver compatibility remains unproven until an actual collection succeeds.
2. One short pause, total target<=90s (within existing600s authorization). Arm independent
   watchdog BEFORE SIGSTOP, use existing hard cgroup protections/deadlines. Bound timed
   work15s plus optional counter work30s; allow recovery margin. If current controller
   cannot enforce the shorter bound, prepare it BEFORE pause. Root exact snapshot and
   selected UUID, original start ticks, fresh ~333TH/s baseline/settings. Children UID1000.
   Do not hardcode historical PID4158372.
3. Same pause/cgroup, ONE event timing, no sanitizer or old correctness/benchmark replay:

       python3 tools/diagnose_compute.py --run-gpu --kind timing
         --engine <new-bench> --out <NEW-private-event-dir> --gpu <UUID>
         --expected-power-limit-w 310 --paused-pid <PID> --paused-start-ticks <TICKS>

   Require32 actual samples plus summary, scalar384/stage64, finite matching timing sums,
   no pool/submissions. This executes about32 short slabs, not a420s mining experiment.
4. ONLY if preflight found a compatible existing ncu, counters are already permitted to
   the unchanged UID1000 execution context, timing passed and>=40s remain: ONE collection
   in the same pause/cgroup, maximum30s. No privilege/permission changes to obtain counters.

       python3 tools/diagnose_compute.py --run-gpu --kind counters --ncu <verified-ncu>
         --engine <new-bench> --out <NEW-private-counter-dir> --gpu <UUID>
         --expected-power-limit-w 310 --paused-pid <PID> --paused-start-ticks <TICKS>

   Fixed sections, one profiled GEMM+filter, skip6/count2, no frequency/cache-control changes.
   Preserve full raw CSV/log and .ncu-rep. Do not accept ERR_NVGPUCTRPERM, no report, missing
   kernels or timeout as successful profiling. On failure stop; no retries or live load.
5. Every exit: terminate/reap complete experiment cgroup and prove empty BEFORE SIGCONT;
   resume SAME original identity; unique SRBMiner, exact settings/protected files, fresh
   current GPU0/API about333TH/s and new work/share evidence. Disarm watchdog only after
   strict sustained recovery. No six-hour average. No second mining process.
6. Return REPORT-COMPUTE-DIAGNOSIS-4090.md, full native build log, event samples/result,
   ncu preflight, full counter CSV/.ncu-rep if collected, exact pause/recovery evidence.
   Explain measured GEMM/filter split separately from missing CPU/H2D/full-batch overhead.
   If counter data exists, identify actual issue/stall/throughput limits using named metrics;
   do not infer causes from timing alone. If absent, explicitly leave those causes unknown.
   Do not create another optimization, rerun a test or claim a hashrate increase in this task.

No artifact here establishes a speedup over SRBMiner. The output is the missing evidence
needed to choose an optimization that can improve end-to-end hashing rather than guessing.
