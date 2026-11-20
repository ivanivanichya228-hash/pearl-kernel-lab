# Full-cycle rate and bounded stability measurement — 0.8.0

First real LuckyPool acceptance is already confirmed by the uploaded report/receipt for26ee387:
sent1,accepted1,rejected0,unknown0. The miner was restored. That milestone is NOT a hashrate
measurement. No real GPU/pool experiment for THIS metrics revision has been executed here.

## Existing evidence, no new GPU work

See miner/ACCEPTANCE-ANALYSIS-4090.json. The reported three FULL batches processed201,326,592
candidate groups in27.082794091 client seconds: approximately7.43 million groups/second.
Under the explicit TWO-dense-operations-per-multiply-add convention, this is about15.59 TOP/s
across the whole client, not a measured SRBMiner-equivalent TH/s value. The operation conventions
must not be silently mixed. Accepted1 in3 batches was lucky and does not establish long-term speed.

From the rounded stage times: preparation consumed approximately55.5% of that client window,
GPU-stage approximately30.2%, proof generation/check8.6%, and remaining overhead approximately5.7%.
GPU-stage includes process startup, transfers, synchronization and guards; it is NOT CUDA-event
kernel-only time. No SRBMiner speedup or efficiency claim follows from these figures.

## New accounting

- Final and periodic status include full wall time, fully observed completed candidate groups,
  fresh-finished/stale/unclassified work, stage duration and completion/cancellation/failure counts.
- Completed candidates per second includes connection, preparation, proof, response and cleanup
  time in the wall denominator. No warmup/slow/no-hit batches are silently removed.
- Arithmetic TOP/s is labeled as theoretical useful dense work count with2 operations per MAC.
  Official-target-weight units/s is separate. Neither is labeled pool/SRBMiner TH/s.
- Partial or cancelled GPU work is NOT estimated or credited. Duplicate work IDs, changed context,
  wrong group sizes or malformed hits fail instead of inflating counters.
- Work finishing after its job becomes stale is accounted separately and excluded from fresh
  finished rate. All attempted stage times remain in the report and wall denominator.
- --measure-stability explicitly selects a fixed window; it is mutually exclusive with stopping
  after the first accepted share. Long duration still requires --extended-test and is<=600s.
- First rejected/unknown outcome or failure aborts the live run. No reconnect/auto retry.
- Proofs/receipts and counters remain available; performance.json is written also on cancellation.
- Private per-batch stage logs are preserved. No credentials or raw authorization are logged.

All GPU/Rust math, source-pinned prepared oracle, file formats, profile and target rules are
UNCHANGED from the first accepted run. No GPU rebuild, sanitizer replay, old fixtures or new
Rust/driver/toolkit installation is required. Python mock tests exercise rate accounting and
cancellation; mock acceptance is not a new real-pool success.

## Codex task: ONE fixed-window Mint4090 run

The user requested the next speed/stability step after accepted1. Keep the existing maximum
600-second mining pause. This is a measurement window, so DO NOT stop after accepted1.

1. New checkout and original SHA verification. Preserve known local Python/C++ paused identity,
   pidfd, cgroup, watchdog, operation lock and restoration fixes. Reuse the verified native engine
   and oracle from accepted26ee387 after checking relevant file hashes and source pins. The native
   engine SHA reported there was9ed74c2227840adab9ffadc0105d660797a49f013ca677c64a0465cf415a568c.
   Local safety patches must be retained and recorded separately from upstream checksums.
   Only the Python networking/metrics modules change. Do not repeat old GPU/ABBA/sanitizer tests.
2. While SRBMiner RUNS, verify the small metrics/lifecycle CPU tests and new mode --help. Prepare
   new owner-only work/evidence directories, current credentials privately and a NEW diagnostic
   worker. Confirm same profile and actualPL310W; never set a different value. Collect a fresh
   >=60s baseline of existing SRBMiner API plus read-only power/temperature/clock samples.
3. Only room-room@192.168.1.98 Mint4090. No3060/Hive, new autostart/deployment, driver/CUDA/Rust,
   pool/wallet changes, OC/fan setters, VPN/panel changes or service desired-state changes.
4. Use the same independent root-owned controller. Arm/verify watchdog590s BEFORE pidfd SIGSTOP.
   Original identity/start-ticks, all-thread-T, idle/no-other-compute, and fan/controller health
   checks remain mandatory. Entire test cgroup including all subprocess sessions has deadline555s.
   Client window540s; pause hard maximum600s INCLUDING cleanup/resume overhead. No retries.
5. Invoke UID1000 in that cgroup, with the existing additional local paused-identity arguments:

       python3 tools/pearl_miner.py --config <private-config>
         --oracle <verified-oracle> --engine <verified-native-engine>
         --allow-live --enable-submit --extended-test --measure-stability --duration 540
         --stop-after-accepted 0 --gpu <live-UUID> --expected-power-limit-w <live-PL>
         --paused-pid <original-PID> --paused-start-ticks <start-ticks>
         --workdir <new-private-directory> --evidence <new-private-evidence-directory>

   ONE real connection/current job/target. No fake or replay jobs, target/dimension changes or
   synthetic success. No endless search. Stop immediately if rejection, unknown, hardware error,
   PL/profile drift, exception or deadline occurs; do not extend time to improve the result.
6. Preserve original stdout/stderr and final performance.json, per-batch events and accepted
   proofs/reports/receipts. Collect READ-ONLY GPU power.draw, power.limit, temperature, SM/memory
   clocks and fan samples about once per second via the existing external sampler. Record sample
   counts/missing samples and actual average/peak watts. Same PL is not proof of same actual power.
7. EVERY exit: kill/verify empty ENTIRE test cgroup before SIGCONT original pidfd. Confirm same
   PID/exe/argv/env/cwd, protected config/profile/desired states/PL/fans, no duplicate miner, fresh
   positive hashrate plus new job OR accepted share, then sustained normal pre-test throughput.
   Disarm watchdog only after strict restoration. No production replacement or second attempt.
8. Return RATE-STABILITY-4090.json/MD, complete performance.json, lifecycle/counter events,
   telemetry summary, actual pause and full recovery evidence. Clearly separate full-window finish
   from early abort, accepted/rejected/unknown, fresh/stale and completed/partial work.
   Report candidates/s and labeled arithmetic TOP/s; DO NOT directly divide them into SRBMiner
   API333TH/s or infer pool speed from one/few shares. Show SRBMiner API separately as context.

## What this can establish

A full fixed window with completed work, current-job handling, no errors/profile drift and safe
restoration demonstrates bounded operation for that window. It does not establish unattended
reliability, statistically precise pool hashrate, profitability or superiority over SRBMiner.
Performance optimization should use the measured full-cycle bottlenecks, not only the old9.64%
standalone-kernel advantage over our own stage32 implementation.
