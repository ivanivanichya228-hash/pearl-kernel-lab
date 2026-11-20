# Proposed one-share acceptance test — explicit user approval required

Status: PREPARED, NOT EXECUTED. Do not start this test from the old CPU-only task.
It extends the previous short mining pauses. The user must approve this exact maximum before
Codex pauses SRBMiner. No real share has yet been accepted by our miner.

## Goal and bound

One Mint4090 experiment. Stop at the first live LuckyPool accepted reply, at the first rejection
or failure, or when the540-second client budget expires. Restore the original SRBMiner in every
case. Main-miner pause maximum600 seconds, INCLUDING controller/cleanup overhead. The extra
minute is reserved for safe stop/resume, not for chasing another candidate.

No guarantee of a share: current target and complete-work speed are unknown; the archived target
implied about183 full batches per expected share. A timeout or accepted0 is a failed acceptance
demonstration, not proof of protocol incompatibility and not success. Do not retry automatically.

## Changes already prepared

- Stop after the FIRST explicit accepted response, correlated to this connection/request ID.
- Duration above50s requires BOTH --extended-test and --stop-after-accepted1; maximum600s in code.
  This proposal uses540s. No unlimited/background deployment or service installation is enabled.
- First explicit rejection terminates the experiment. Unknown outcomes are not retransmitted.
- Final sent/accepted/rejected/unknown counters are emitted even when the worker fails/cancels.
- Accepted proof bytes, official report and matching reply ID/result/error are retained privately
  under evidence/accepted/. Receipt JSON is a local record, not a signed pool attestation.
- No math/GPU scheduler changes. Earlier worker sanitizer and official-proof tests remain valid.
- Temporary work file is closed after completed writes; forced crash-durable fsync is removed.
  It is not a permanent wallet/database. Cancelled/partial work is never handed to the GPU;
  the next process starts only after successful work-prepare exit.

## After user approval only: Codex task

1. NEW checkout and original checksum verification. Preserve all previously successful local
   paused-identity, pidfd, cgroup, lock, controller/watchdog and strict recovery protections.
   Prepare source-pinned oracle and existing native engine while SRBMiner is RUNNING. The math
   src/kernel.cu, src/filter.cu and src/pipeline.cu are unchanged; no old GPU/ABBA/sanitizer rerun.
   No Rust/driver/CUDA installation. No new CPU full-size benchmark is needed before this test.
2. Use the same actual pool/wallet privately and a NEW diagnostic worker. Private files0600,
   work/evidence directories0700, runnerUID1000. No credentials in argv/logs/report. Verify available
   RAM/temp disk and reserve8GiB. Preserve current live UUID/PL/OC/fans; do NOT apply any setters.
3. Adapt the known root-owned outer controller to exactly this approved bound BEFORE pause:
   independent watchdog590s; transient test cgroup deadline555s (includes all sessions/children);
   hard main-miner pause<=600s. Watchdog must kill the entire test cgroup, verify it empty, then
   resume the original identity. Main controller does the same on EVERY exit. No SIGCONT while
   our GPU process can still run. Verify watchdog active before pidfd SIGSTOP. Keep GPU/fan
   controller active; do not use normal miner service stop/start. Do not touch3060/Hive.
4. Record fresh normal mining baseline/profile and exact original identity. Acquire existing
   operation lock, stop only the original miner by pidfd, prove all threadsT/GPU idle/no other
   compute work, then run ONE live connection under the independent controller:

       python3 tools/pearl_miner.py --config <private-config>
         --oracle <worktree>/build/pearl-protocol-oracle --engine <worktree>/build/pearl-bench
         --allow-live --enable-submit --extended-test --duration 540 --stop-after-accepted 1
         --gpu <live-UUID> --expected-power-limit-w <live-PL>
         --paused-pid <original-PID> --paused-start-ticks <start-ticks>
         --workdir <new-private-directory> --evidence <new-private-evidence-directory>

   Actual current explicit notify target only. No replay, synthetic target, altered dimensions,
   fake proof, extra pool connection or deferred stale submit. No auto reconnect/retry. Retain
   per-batch events and timing logs; do not print raw pool credentials/errors.
5. After first accepted, failure, first rejected or deadline: kill/check empty ENTIRE cgroup,
   then SIGCONT original PID. Verify original exe/argv/env/profile/desired states/PL/fans,
   unique miner, fresh positive hashrate plus work OR accepted share, then sustained return to
   live pre-test throughput. Disable watchdog only after strict recovery. GPU/controller/miner
   services remain in their original states; no permanent replacement/deployment.
6. Return total actual pause, final counters, server response classification and actual pool target,
   accepted proof/report/receipt if any, stage events/timings and full restoration evidence.
   Distinguish timeout accepted0, explicit rejected, unknown, cancellation and an accepted share.
   Do not call any result a hashrate/efficiency improvement or readiness for unattended mining.
