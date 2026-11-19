# Standalone sanitizer 2025.3.1: prepare once and continue validation

## Supplied component and measured preparation

Official NVIDIA CUDA13.0.2 redistribution metadata names cuda_sanitizer_api13.0.85.
The archive actually contains the FULL Compute Sanitizer2025.3.1.0 (build36400806),
not just API headers. Size11,399,964 bytes; SHA256:
8eeba425f66fdd17e78d0dff49baa8b3e4599fc0579984eab7ad9c486a95ebf2

URLs and digest are pinned in tools/prepare_sanitizer.py. It downloads/extracts solely into
this checkout's ignored .sanitizer-cache, preserves the official directory/symlink structure,
compares all extracted files back with the verified archive, checks helper executability,
--version/--help and shared dependencies. It does not install packages or modify PATH,
/usr, ldconfig, drivers, CUDA runtime/toolkit, systemd, GPU settings or mining.
Preparation/version/help/dependency audit succeeded in the author's Linux build environment.

IMPORTANT: one CPU /usr/bin/true attempt here produced 'process didn’t terminate successfully'
and 'Target application terminated before first instrumented API call', despite CLI exit0.
This is NOT recorded as a successful launcher check. Cause in this build environment is unknown;
no conclusion about the user's Mint follows. No GPU validation was run here.
The CPU-true test is not used as a GPU permission/success gate, and must not be repeated on rig.

The prior supplied reports show the old tool's CUDA probe failed too. New package/version is a
specific replacement experiment, not a proven fix of that launch failure. No speedup is promised.

## Guard integration

With --sanitizer, tools/test_4090_mint.py now resolves ONLY the already prepared standalone
bundle and passes its native injection directory explicitly. There is no system-tool fallback,
network download or old CPU-smoke gate inside a mining pause. Child-only LD_LIBRARY_PATH
prepends the new directory and excludes inherited compute-sanitizer directory entries.
The kernel and benchmark mathematics remain unchanged.

Sanitizer stdout/stderr are preserved and emitted after the process. Even exit0 is rejected
if an Error line occurs, no clean ERROR SUMMARY exists, or debug/non-debug correctness did
not complete. All detected error-summary counts must be zero. Existing external gates still
require full output inspection, leak summary and miner recovery. Timeout prints partial output
and kills test descendants; test-cgroup cleanup and independent watchdog remain compulsory.

## One task for Codex on panel host

Continue to the actual result without asking again after each successful phase. User has
already authorized controlled test pauses and automatic restoration. Only Mint RTX4090;
no3060/Hive tests. Actual current PL/profile must agree; keep all GPU/miner/pool/wallet/
autostart/driver/panel/VPN settings. Retain all original evidence and private snapshots.

1. Use NEW worktree for this revision. Read the last FULL-FAILURE-JOURNAL and known recovery
   safeguards. Preserve local validated controller/cgroup/pidfd/start-ticks/all-thread-T checks.
   Do not replace them with old upstream weaker code. Reuse successful preparation/tests where
   source is unchanged; no full repeated project exploration, builds or CPU suites without reason.
2. On the Mint4090 as its normal user, run:
       python3 tools/prepare_sanitizer.py
   Record JSON and exact executable/tool version/archive digest. Native layout, helpers and all
   libraries stay together. No sudo installer or driver/toolkit upgrade. This phase needs no pause.
   Run only new CPU regressions relevant to merged guard changes (test_isolated_sanitizer.py,
   test_memcheck_evidence.py and guard/budget tests). They do not initialize CUDA.
3. Reuse already built cuda-minimal and the validated9ab7ca5 benchmark executable by their saved
   SHA256, if unchanged. Rebuild only if a genuine source/ABI change requires it. The matmul kernel
   hash must remain91e9721506867dda5872267c465b0ee2c33596f96b54d788641e5d163816c352.
4. Adapt local run_validation_stage.py and its verified cache to the prepared new executable,
   injection path and child library path; verify archive/extracted hashes before the pause.
   Do not invoke the old /usr/bin/compute-sanitizer or old preflight CPU-true requirement.
   Keep full stdout/stderr, stage-gates, process-group PLUS cgroup cleanup and strict recovery.
5. ONE controlled minimal CUDA probe under the NEW tool, timeout25s, test-cgroup RuntimeMax30s,
   watchdog70s armed before SIGSTOP, hard total pause<=90s. Same UUID/currentPL, fresh snapshot,
   existing operation lock. Instrument ONLY this test process, never attach to mining.
   Require explicit CUDA-probe passed output and clean sanitizer summary/exit. Inspect error text,
   not just exit0. Kill entire test cgroup before SIGCONT. Confirm fresh positive hashrate AND
   (new job OR accepted share), same identity/settings/no duplicate before watchdog disarm.
6. If minimal probe and strict restoration pass, continue WITHOUT another permission request:
   NEW snapshot/watchdog/lock for memcheck of all 6 fixtures, all 4 variants, debug fullC/transcript
   plus non-debug transcript. Use existing binary and explicit new tool paths. Timeout50s and
   cgroup58s, watchdog70s, total pause<=90s. Require completion, zero error summaries, leak result
   inspection and zero errors/no leaks. No benchmark gate before actual memcheck success AND return.
7. If memcheck and restoration pass, continue uninstrumented: two A/B/B/A, duration3s/warmup2s,
   40s scheduled work plus setup/checks, guard55s/cgroup58s/watchdog70s/total<=90s. Baseline stage32
   and candidate stage64, both256 threads, shape2048x6144x4096/rank128/proof16. Preserve live PL.
   Restore and strictly confirm same original miner in every path. No deployment into SRBMiner.
8. If any stage fails, stop subsequent GPU stages, restore mining and keep gates false.
   Do not repeat the same failed GPU probe or vary flags blindly. If new launcher still fails,
   while mining continues collect CPU-only startup diagnostics if strace is already installed:
   trace only the standalone tool targeting /usr/bin/true with CUDA_VISIBLE_DEVICES=-1 and
   require-cuda-init=no, child-only new LD path, bounded15s, process/file syscalls, no environment
   values or miner tracing. Also read the test unit's security restrictions. Label this diagnostic,
   not a CUDA test; tracing may change behavior. Do not install tools or alter system restrictions.
   This additional diagnostic should expose missing exec/load/permission details without a new pause.
9. Final report: source/binary/tool identities, all completed stages, exact failure if any,
   pause durations, return evidence, actualPL, memcheck summary, eight timing phases/two ratios,
   or explicit 'not run'. No substitution of old+9.63% into unexecuted tests. No conversion of
   matrix TOPS to SRBMiner TH/s, profit or energy gains. Preserve private argv/env/config on rig.
