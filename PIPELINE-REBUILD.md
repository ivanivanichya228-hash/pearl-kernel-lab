# Five-step progress — 0.9.0

| Step | Current result |
|---|---|
|1. Persistent GPU process/context/buffers|Implemented and CUDA-compiled. CPU IPC verifies one PID over multiple requests. Actual GPU/VRAM reuse remains untested.|
|2. RAM transport + overlapped preparation|Implemented. Two-workspace bound, real tmpfs, mapped input and producer/consumer overlap verified locally.|
|3. GPU matrix/noise/Merkle preparation|NOT implemented. Official CPU preparation remains.|
|4. Assemble and verify new build|CUDA SM86/89 build, native CPU checks, lifecycle tests and official-proof loopback integration passed here.|
|5. One end-to-end Mint4090 test|NOT run for this revision. No GPU, pool connection or miner pause performed here.|

This is a substantial execution-path revision, NOT a measured speedup or production replacement.
The previous first accepted share and subsequent slow run belong to the earlier sequential version.
No new live share or hashrate result is claimed for0.9.0.

## Step1 implementation

- Native --mode worker retains one CUDA context/stream and one MiningExecutor for the entire run.
  A/B device arrays, transcripts, indices and count buffers grow only when capacity is insufficient.
  Same-profile requests reuse the allocations. resource_generation reports the allocation epoch.
- Input headers/arrays are mapped read-only instead of copying the full payload into host vectors.
  A stream fence keeps the mapping alive until queued transfers/compute finish, including errors.
- Sequence-numbered request/acknowledgement protocol enforces one outstanding GPU request. PID
  stays the same, there is no automatic process restart after errors. Idle close uses QUIT for a
  clean destructor path; cancelled active compute terminates/reaps the whole engine process group.
- Native pre-CUDA and per-request checks reject a running original SRBMiner, wrong start-ticks,
  a resumed thread or an additional SRBMiner. Python/outer watchdog/cgroup protections still apply.
  --allow-concurrent-miner only bypasses name presence for the independently stopped identity.

The unrelated90s idle-read timeout is also removed: pool silence alone no longer aborts a
bounded session. EOF/network errors,15s authorization/submit deadlines, total run deadline and
watchdog remain. This does NOT establish why the previous382.99s run stopped without its log.

## Step2 implementation

- --pipeline explicitly enables the new path. --ram-dir defaults to /dev/shm and MUST resolve to
  tmpfs. Free tmpfs capacity and available system RAM are checked for two full workspaces.
  There is NO automatic fallback to the old SSD/HDD work directory if RAM is insufficient.
- Large raw/noisy arrays are RAM-backed. Logical files remain as the bridge/mmap interface;
  this is not a claim that all file handles or metadata writes have disappeared. Small persistent
  evidence/proofs stay in the private evidence directory. No fsync of disposable work is used.
- One producer prepares the next input while the consumer computes the current one. Queue size1
  plus a two-slot semaphore bounds both active and ahead-of-time preparation to TWO workspaces.
- New pool jobs cancel/reap obsolete CPU preparation. Already running GPU requests are allowed
  to finish; their stale results are discarded without submit or effective-rate credit. A job
  update does NOT destroy the CUDA context. The next current preparation proceeds independently.
- Global stop/failure kills or cleanly stops/reaps the GPU worker BEFORE its mapped workspace is
  released. CPU children are reaped, queued work removed, and the private RAM root removed.
- Proof generation/official verification is still CPU work after a hit. It has NOT been moved
  outside the critical path in this revision. Stage times may overlap and cannot be summed into
  wall-time percentages as if stages were sequential. Wall-based candidate rates remain valid.

The arithmetic src/kernel.cu and jackpot src/filter.cu are unchanged, as are the prepared official
Rust bridge, target rules, profile and proof format. The native scheduler/lifetime path CHANGED,
so old GPU acceptance does not validate this new worker automatically.

## Checks completed here, no rig needed

-52 Python tests, including overlap proven by events, two-slot ownership bound, failure/cancel
 cleanup, stale jobs without restart, malformed acknowledgement and process reaping.
- Actual CLI + ONE persistent native CPU-reference process + tmpfs + official Rust bridge + local
 loopback server: two full small batches, eight distinct proof messages, all independently checked
 by the official verifier. Deliberate mock acceptance/rejection accounting remains correct.
- CPU worker PID reused, no forced shutdown on normal completion, exit0, all RAM work removed.
- Native mapped input equals the copied reader byte-for-byte; new native paused identity guard
 tested on disposable local mock processes (stopped/running/wrong ticks/duplicate). No real miner.
- CUDA13.0.88 builds SM86/89. No GPU execution or performance measurement was possible here.

Evidence: miner/PIPELINE-LOOPBACK-RESULT.json. Mock responses are not real pool acceptance.
No system Rust/driver/toolkit installation, fee scheduler, wallet change or card testing occurred.

## Reproduce local CPU integration

    python3 tools/prepare_miner.py
    make build/work-cpu build/test-paused-guard build/test-mapped-work
    build/test-paused-guard
    python3 -m unittest discover -s tests -p 'test_*.py'
    python3 tests/run_miner_integration.py --pipeline --oracle build/pearl-protocol-oracle --engine build/work-cpu

Prepared oracle/source pins are unchanged; no Rust installation or new archive is needed.
The old sequential CLI remains available WITHOUT --pipeline as a control. No fallback is automatic.

## Step5 Codex handoff: ONE combined changed-path check + measurement

This environment cannot operate the home rig. The following is the concrete next task for its
local Codex, within the user's existing maximum600-second mining-pause authorization. It has
NOT been executed here. No new approval prompt or repeated old GPU benchmarks is required.

1. NEW checkout, original checksum verification and preservation of all working local pidfd,
   operation-lock, Python/C++ paused identity, watchdog/cgroup and recovery controls. Native
   scheduler changed, so build it with the EXISTING nvcc while SRBMiner RUNS; no system installs.
   --help must list worker and --paused-pid/--paused-start-ticks. Verify the unchanged source-pinned
   official oracle. Keep PL310W, OC/memory/fans/pool/wallet/profile/desired states unchanged.
2. Check tmpfs and RAM BEFORE pause: two full-profile workspaces need approximately4GiB tmpfs;
   reserve at least12GiB available RAM plus headroom. Use a NEW private tmpfs PARENT area and evidence
   directory. Record that parent path/owner/inode in the root-owned recovery plan BEFORE pause,
   and pass it via --ram-dir. The client creates its random RAM root inside that known parent.
   Watchdog cleanup
   may remove only that validated disposable parent AFTER every experiment process is dead. No disk fallback.
3. While mining continues, prepare TWO independent small inputs with tools/prepare_live_check.py
   into different directories on that private tmpfs. Run build/work-cpu for each to save CPU hit
   indices/transcripts and official work-finalize on them. This is local synthetic work, never
   a live submit. Confirm different batch IDs and four qualified hits each. No GPU operation yet.
4. Snapshot fresh normal baseline/current identity/settings. Use the known root-owned controller,
   original pidfd/all-thread-T/idle/no-other-compute checks and operation lock. Arm/verify the
   independent watchdog590s BEFORE SIGSTOP. Entire experiment cgroup deadline555s; hard original
   mining pause<=600s including all cleanup/resume overhead. Runner and all test childrenUID1000.
5. FIRST validate the NEW persistent native path once under known good standalone Sanitizer2025.3.1,
   within25s, in that cgroup. Feed stdin sequence1<TAB>absolute-input1<TAB>new-output1<LF>, then
   sequence2 with the other input, then QUIT<LF> to ONE native process:

       <sanitizer> --injection-path <verified-path> --tool memcheck --error-exitcode 86
         --leak-check full <new-bench> --run-gpu --mode worker --allow-concurrent-miner
         --paused-pid <original-PID> --paused-start-ticks <start-ticks>

   Isolate the selected live UUID with CUDA_VISIBLE_DEVICES and retain currentPL guards/sampler.
   Require exit0, memcheck0/leaks0, ready protocol1, done sequence1/2, SAME native PID, and
   resource_generation1 on BOTH requests. Sanitizer launcher PID may differ from native PID.
   Compare each actual GPU hit set/transcript with its CPU result, then officially work-finalize
   BOTH GPU outputs. No old six-fixture/filter/ABBA or minimal-CUDA probe replay.
6. If ANY new-path check fails or insufficient budget remains, STOP, restore and report; no retry.
   Otherwise, SAME pause/cgroup, start ONE real pool window480s (not until first share):

       python3 tools/pearl_miner.py --pipeline --config <private-config>
         --oracle <verified-oracle> --engine <new-verified-native-engine>
         --allow-live --enable-submit --extended-test --measure-stability --duration 480
         --stop-after-accepted 0 --gpu <live-UUID> --expected-power-limit-w <live-PL>
         --paused-pid <original-PID> --paused-start-ticks <start-ticks>
         --evidence <new-private-evidence> --workdir <new-private-control-directory>
         --ram-dir <root-plan-private-tmpfs-parent>

   Fresh diagnostic worker, original wallet/pool read privately. No credentials in argv/logs.
   First rejection/unknown/error/profile drift aborts. No reconnect/retry or longer search to chase
   a share. Keep the fixed time budget. Collect read-only power/temperature/clocks/fans telemetry.
7. EVERY exit: terminate and prove ENTIRE cgroup empty BEFORE SIGCONT. Clean private RAM only
   after consumers/producers are dead; never unlink a still-used workspace. Confirm original PID,
   argv/env/exe/cwd/protected profile/settings, unique miner, fresh hash plus work OR accepted share
   and sustained normal baseline throughput. Disarm watchdog only after strict recovery.
8. Return the new worker/sanitizer output, real hit comparisons/official proof checks, final counters,
   performance.json, resource_generation/PID history, RAM cleanup and full recovery. Report full-wall
   candidates/s and labeled arithmetic TOP/s. Do not equate TOP/s to SRBMiner API TH/s or infer
   speed from one share. Compare full-cycle candidate rate against prior7.885M/s only for matching
   explicit profile/target policy and clearly distinguish fresh/stale/partial work and overlapping
   stage times. Report a slower result honestly. No production deployment/autostart.

No actual speedup, real share or GPU-resource reuse for this revision is claimed before that
combined rig check completes. Step3 (GPU-side preparation) remains a separate future change.
