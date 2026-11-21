# 0.14.0 — pinned host memory and two-slot input transfer

Implemented and locally checked, NOT GPU-executed here. The measured 44ee1d9 baseline is
29.677105M fresh groups/s at kernel384. This revision changes transport/lifetime, not GEMM,
noise, filter, target/profile, root generation or the pinned official Rust verifier.

## Data path

- Explicit --transfer-overlap, requires --pipeline --gpu-noise. Default remains OFF. Use the
  already-validated --kernel-threads 384 for this comparison; no new kernel search.
- Native overlap-worker protocol2 has exactly two reusable host/device slots. cudaHostAlloc
  provides pinned host memory, confirmed with cudaPointerGetAttributes. Each slot stores raw
  A+BT contiguously; CPU memcpy into pinned RAM, then ONE asynchronous H2D transfer per packet.
  A small pinned result region avoids pageable D2H staging from synchronizing the next transfer.
- Copy and compute have distinct nonblocking streams. An event connects input-copy completion
  to its compute. A background reader owns stdin ONLY; all CUDA calls stay on the main native
  thread. While current kernels run, the main thread stages the queued next packet into the
  OTHER slot. No slot or pinned source is reused before its previous compute/copy completes.
- Both full-profile slots allocate before first compute. Same geometry reuses allocation;
  growth can synchronize CUDA and is allowed in correctness fixtures, not presented as overlap.
  At the live profile, two raw pinned buffers total2GiB plus small result regions; device input
  storage2GiB. Available RAM>=16GiB plus the profile-based tmpfs/heap/pinned bound is required.
  No pageable/disk fallback or memlock/driver/system-setting workaround.
- Python submits at most two tickets, one stdout owner, strict sequence/PID acknowledgement,
  deadline also for unawaited prefetches, no process restart. Workspace ownership persists through
  stale queued completion. Global stop reaps the native process before temporary data cleanup.
- Protocol1 legacy worker and the previous unpinned path remain available as control. New
  transfer_stage records contain GPU-epoch copy/compute intervals, CPU copy time, slot/generation
  and byte count. H2D_phase now measures actual copy interval in overlap mode; the separate
  input_ready_wait field measures the compute stream waiting for input. Native run-wall excludes
  initial staging done before run; ONLY full-wall client/paired measurements evaluate improvement.

## Accounting

Pipeline timings in overlap mode measure submission-to-native-done, including queue wait; they
can overlap and must not be added as sequential stage time. Throughput credits only fully consumed,
validated/classified packets. On a hard window boundary an extra queued packet may have completed
without consumer validation. completed_unconsumed_sequences explicitly lists it; native logs retain
its output and it gets NO fresh-rate credit. Unfinished transfers/compute get no credit either.
Candidate proof/receipt retention and strict fresh-job checks remain. Stale work is never submitted.

A stream-interval intersection is not a hardware DMA-busy/PCIe-bandwidth measurement. The short
comparison requires both speed improvement AND material intersection before authorizing a long run.

## Local evidence

CUDA13.0.88 SM86/89 build succeeded.68 Python checks pass, including two-inflight bounds,
unawaited deadlines, bad ACK/no restart, global cancellation and stale-prefetch workspace lifetime.
Native reader parser/sequence/absolute paths passed; reader joins even with stdin pipe left open.
Actual CLI + queued native CPU-reference + official proofs/loopback retained eight verified proofs
and cleaned RAM. A completed extra CPU packet at the artificial two-batch cutoff was explicitly
reported as unconsumed, not credited. Four local transfer correctness inputs produce1034 CPU hits
and14 official sampled proofs, including new-small-after-large slot reuse. The A/B/B/A driver was
exercised in CPU mock mode and NEVER authorizes live from a CPU result. No GPU speedup is claimed.

## ONE task for local Codex — same Mint4090, PL310W

Existing authorization: original-miner pause<=600s total, no tuning or production deployment.
Keep exact clocks/memory/offset/both fans/pool/wallet/profile. No3060/Hive work. Reuse verified
root pidfd/start ticks, lock/all-thread-T/idle/unique compute, watchdog/cgroup and current-GPU
recovery controls. Do not replace protocol2 with an old protocol1-only local wrapper.

1. BEFORE pause: NEW pinned checkout/checksums; build changed native transport with EXISTING
   nvcc, unchanged oracle via tools/prepare_miner.py; no installs. Build work-cpu/test-request-inbox.
   Prepare NEW small correctness cases while SRBMiner runs:

       python3 tests/prepare_overlap_checks.py --oracle build/pearl-protocol-oracle --out <new-small-check-dir>

   Require4cases,1034 CPU hits,14 official proofs. This reuses boundary geometry as input to the
   NEW transfer mechanism; no historical kernel/noise/filter/ABBA replay. No NumPy/Rust install.
2. Still BEFORE pause, on the validated private tmpfs parent recorded in root plan, prepare TWO
   full-profile LOCAL benchmark inputs (2GiB raw total), not a pool session:

       python3 tests/prepare_transfer_inputs.py --oracle build/pearl-protocol-oracle --out <private-tmpfs-bench-dir>

   Do NOT pass --small for GPU benchmark. Check >=16GiB MemAvailable AFTER preparation, sufficient
   tmpfs and VM headroom, private evidence, working standalone Sanitizer2025.3.1. Snapshot fresh
   normal ~333TH/s and exact original identity/settings. Current GPU0/API recovery parser only.
3. ONE combined pause: watchdog590s armed BEFORE exact pidfd SIGSTOP; whole experiment cgroup
   RuntimeMax555s/KillModecontrol-group, all childrenUID1000, selected UUID. Prove every original
   threadT/GPU idle/no other compute. Hard original pause<=600s including cleanup/recovery.
4. NEW transfer correctness, one native process under known sanitizer, <=20s including verifier:

       <sanitizer> --injection-path <verified-path> --tool memcheck --error-exitcode 86
         --leak-check full <new-bench> --run-gpu --mode overlap-worker --candidate 384
         --allow-concurrent-miner --paused-pid <original-PID> --paused-start-ticks <ticks>

   Pipe seq1/2/3/4 TAB raw_manifest TAB NEW GPU_hits from cases.json, then QUIT. Require protocol2,
   transfer_slots2, same PID, done1/2/3/4, exit0/errors0/leaks0. All mining_batch kernel384,
   pinned_transfer_overlap=true. transfer_stage seq1/2/3/4 pinned=true, slots1/0/1/0, correct raw
   bytes, no per-packet allocation growth for same-size reuse. Seq4 reuses the larger seq2 slot
   for a NEW smaller packet: same slot allocation generation, new batch ID/results. Computational
   resource generation can grow differently from protocol1; do not hard-code old1/2/3 epochs.
   Verify ALL actual1034 GPU hits/transcripts and14 official proofs:

       python3 tests/verify_compact_outputs.py --oracle build/pearl-protocol-oracle
         --cases <small-check-dir>/cases.json --out <new-GPU-proof-evidence>

   No CPU substitution. Preserve complete outputs and proofs. ANY failure => STOP/restore/report,
   no retry, driver install, probe or alternate memory fallback.
5. SAME pause/cgroup, ONE matched short transport comparison, external whole-command timeout45s:

       python3 tools/compare_transfer.py --run-gpu --engine <new-bench>
         --inputs <private-tmpfs-bench-dir>/inputs.json --out <new-private-comparison-evidence>
         --gpu <UUID> --expected-power-limit-w 310
         --paused-pid <original-PID> --paused-start-ticks <ticks>

   Four intentional A/B/B/A legs, each a fresh process; two warm + two timed packets per leg.
   SAME two fixed LOCAL inputs, SAME kernel384 in both modes. Control protocol1, overlap protocol2.
   Replays are offline benchmarks ONLY, not fresh/live work; no pool and no submit/receipt claim.
   Require actual hit/transcript equality on every repeat, clean exit0/reaped for all four workers.
   Summary candidate_faster_for_live must be true: >2% paired gain, BOTH B legs faster than BOTH
   A legs, and timed copy/preceding-compute stream intersection >=1ms AND >=10% of that copy phase
   in BOTH B legs. If false or timeout/failure => restore immediately; SKIP420s live. No rerun.
6. Only if all pass and >=440s remain before the cgroup deadline: remove ONLY validated disposable
   benchmark inputs after comparison workers are dead; recheck RAM, then SAME pause, ONE live420s:

       python3 tools/pearl_miner.py --pipeline --gpu-noise --kernel-threads 384 --transfer-overlap
         --config <existing-private-config> --oracle <unchanged-verified-oracle> --engine <new-bench>
         --allow-live --enable-submit --extended-test --measure-stability --duration 420
         --stop-after-accepted 0 --gpu <UUID> --expected-power-limit-w 310
         --paused-pid <original-PID> --paused-start-ticks <ticks>
         --evidence <new-private-evidence> --workdir <new-private-control-dir>
         --ram-dir <validated-private-tmpfs-live-parent>

   Original full profile/target/pool/wallet and natural Rayon40 unchanged, fresh diagnostic worker.
   No retries/reconnects/deadline extension/fallback. Abort on rejection/unknown/error/drift. Verify
   transfer_overlap_requested=true, protocol2, maximum pending<=2, kernel384 and pinned flag on
   native batches. Preserve CUDA-epoch transfer/compute records and quantify their intersections;
   flags alone are not proof of overlap. Report boundary completed-unconsumed requests separately
   with zero rate credit; retain raw events and actual candidate proofs/receipts. Sample settings/
   power/temp/utilization read-only. No synthetic benchmark input is eligible for live submission.
7. EVERY exit: terminate/reap ENTIRE cgroup, prove empty BEFORE SIGCONT. Only then clean validated
   tmpfs. Confirm SAME original identity/config/settings, unique SRBMiner and sustained current
   GPU0/API ~333TH/s with fresh jobs/share. Disarm watchdog after recovery; units/timer inactive.
8. Return REPORT-TRANSFER-OVERLAP-4090.md, full sanitizer/proof checks, four paired legs/decision,
   actual overlap intervals and live performance/telemetry/proofs if run, plus strict recovery.
   Full-window fresh rate comparison against29.677105M/s must distinguish changed jobs/stale/
   boundary exclusions. No conversion to SRBMiner TH/s or claims based on one share. If rejected,
   the short result and restoration are the result; do not spend seven more minutes on it.

No home GPU test, actual pinned bandwidth or hash-rate improvement for0.14.0 is claimed here.
