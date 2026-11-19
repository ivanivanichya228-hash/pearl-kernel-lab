# Revision 0.3.1: confirm stage64 and run memory checks

The kernel source is UNCHANGED from c75957c. Its initial short result was +9.628% against
our stage32 kernel on the specified matrix. That result was user-supplied; it is not a comparison
with SRBMiner, measured Pearl hashrate, energy efficiency or full proof compatibility.
This revision strengthens validation only. No further GPU tests have been run by its author.

## New harness behavior

- Correctness poisons output buffers before each launch. For all 6 fixtures and 4 variants,
  checks full debug C/transcript AND non-debug transcript independently (48 kernel launches).
- --rounds 1..3 repeats A/B/B/A. --warmup 0..5 runs the same variant's graph before each leg.
- JSON identifies round/leg/stage, emits per-round ratios and their geometric mean/min/max.
  Ranges across a few rounds describe repeatability, not a confidence interval.
- Transcript outputs must still match after the timed workload.
- CPU/GPU-CLI plan validation: 4*rounds*(warmup+duration)<=45 seconds of scheduled work.
  Initialization, fixture checks, graph setup, reads and synchronization are extra.
- Python guard caps timeout at 60 seconds; benchmark requires at least 10 seconds of margin
  beyond scheduled work. Existing independent external watchdog remains mandatory.
- --sanitizer uses an EXISTING compute-sanitizer, memcheck, error-exitcode86, leak-check full.
  It is restricted to --mode check. Absence fails before test launch; no silent skip/install.
- Guard starts a separate test process session and terminates its process group in finally.
  This also handles sanitizer child processes; external watchdog still kills the entire test cgroup.
- New C++ plan tests and Python budget tests passed; prior CPU correctness models are retained.

## Task for Codex on panel host

Only Mint RTX4090. Never test local3060/Hive. Preserve current PL, OC/fans, pool/wallet,
miner configuration, driver, panel, VPN and auth. Build only in a NEW worktree. Keep previous
worktrees/evidence/private snapshots and uncommitted safety fixes intact.

### Preparation before either pause

1. Read latest stage64 report including the prematurely disarmed watchdog finding. Use the
   FIXED local controlled4090.py, whose final verified criterion requires fresh hashrate AND
   (new pool job OR accepted share). Identity/single miner/settings/uptime consistency also
   required. Do not reuse the previously executed weaker verifier or any old snapshot.
2. Carefully port existing paused PID/start-ticks/all-thread-T guards into new bench/Python
   guard; retain new rounds/warmup/budget/session cleanup. Never bypass miner detection with
   --allow-concurrent-miner. The upstream guard alone does not pause or restore mining.
3. Build with the rig's existing nvcc. Confirm --help --rounds/--warmup, exact source/binary
   hashes and unchanged kernel hash. Run make cpu-check, test_layout.py, both Python guard
   suites and paused identity tests. No driver/package installation and no GPU work pre-pause.
4. Locate existing compute-sanitizer and inspect version/help (no GPU work). Check the actual
   installed tool accepts --error-exitcode 86 and --leak-check full. See official documentation:
   https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/
   If tool missing/incompatible, report this as BLOCKED; do not call memory validation passed
   and do not proceed to longer timing automatically. No installing or repeated blind attempts.
5. Re-read actual UUID/PL and cross-check panel profile. Use the existing operation lock, NEW
   one-shot root-owned snapshot and independent watchdog BEFORE EACH pause. Verify watchdog
   without pausing mining first. Existing pidfd SIGSTOP/SIGCONT method preserves fan controller.
   Before CUDA: all target miner threads T, utilization<=1% for2s, no other compute work.
   Tests and helpers must survive SSH/CLI disappearance without leaving mining stopped.

### Run 1: memcheck only

Guard options, with existing paused-identity options appended:
--run-gpu --mode check --sanitizer --expected-power-limit-w <ACTUAL_PL> --timeout-sec 50

No timing under sanitizer. Capture unmodified stdout/stderr, tool version and return code.
Require check completion, both debug/non-debug golden results, exit0 AND sanitizer summary
ERROR SUMMARY: 0 errors. Inspect leakage summary; incomplete/timeout/no summary is NOT pass.
Use watchdog70s and hard total pause<=90s. Kill whole test cgroup/process groups BEFORE
SIGCONT in normal and emergency paths. Verify full restoration with stronger criteria before
watchdog disarm. If error/timeout/recovery failure, stop and report; no longer benchmark.

### Run 2: longer uninstrumented comparison, only after clean Run1 and restoration

New snapshot/watchdog/lock for this second independent pause. No sanitizer attached.
Guard options, with same paused identity validation:
--run-gpu --mode bench --rounds 2 --duration 3 --warmup 2
--expected-power-limit-w <ACTUAL_PL> --timeout-sec 55

Expected plan is 40 seconds: 8 legs * (2s warmup +3s measurements), PLUS checks/setup/reads.
Watchdog70s, hard total pause<=90s. If infrastructure cannot maintain those bounds, don't start.
Baseline256/stage32 vs candidate256/stage64, M2048 N6144 K4096 rank128 proof16.
Keep read-only PL checks and telemetry throughout. No configuration setters. Restore and fully
verify same miner after test in all cases. Disarm watchdog only after strict verified=true.
Do not add more runs or change GPU settings if noise/drift/timeout occurs; save the evidence.

### Deliver

Report each pause duration/recovery, actual PL, compiler, kernel/binary identity, sanitizer
full summary, all 8 timing phases, both round ratios, combined ratio/range, NVML clocks/W/temp
and before/after unchanged files/settings. Keep private argv/env/config on rig only.
Do not interpret these NVML windows as conclusive equal-power/energy evidence; PL is a ceiling.
Do not extrapolate matrix TOPS into SRBMiner TH/s, profits or production stability.
No modifications/injection into SRBMiner and no automatic deployment. The next gate after this
is compatibility with the full Pearl proof/noise/commitment pipeline, not a promised miner upgrade.
