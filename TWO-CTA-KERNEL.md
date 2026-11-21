#128x128 /256-thread resource-reduced Pearl kernel

This is a computational-kernel change based on the actual f561218 root hardware profile,
not another profiler experiment. That profile showed scalar384:166 registers,83968 dynamic
shared+1024 reserved bytes,one resident CTA maximum,25% theoretical/achieved warp occupancy,
0.12eligible warps/SMSP,7.18%issue-active and13.23%tensor activity. These measurements motivate
more independent resident CTAs; they do not prove a unique cause or predict a speedup.

## Implemented

| Property | Proven scalar384 control | Explicit --two-cta candidate |
|---|---:|---:|
| CTA tile MxN |192x256|128x128|
| Threads/warps |384/12|256/8|
| Warp grid |3x4|4x2|
| Accumulators/thread |128|64|
| CUDA13.0.88 compiler registers |166|107|
| Dynamic shared,proof16 |83968|45056|
| Dynamic shared,proof8 |96256|49152|
| Expected shared including reported1KiB reserve,proof16 |84992|46080|
| Expected shared including reported1KiB reserve,proof8 |97280|50176|

Both proof widths fit TWO CTAs within the reported102400 bytes/65536 registers on Ada.
This is resource arithmetic, not observed residency or a hashrate measurement. The actual
runtime cudaOccupancy query MUST report>=2 for BOTH proof widths before timing/live work.
The candidate requests maximum shared-memory carveout ONLY for its CUDA function, to avoid
an avoidable smaller L1/shared partition. This is a per-function hint, not a driver/power/
clock/fan setting; the driver can choose another ratio. The normal control has no new hint.
Primary reference: https://docs.nvidia.com/cuda/cuda-runtime-api/cuda_runtime_api/group__CUDART__EXECUTION.html

The64-wide double buffer, cp.async, signed INT8 MMA, cumulative INT32 accumulators, exact
rank checkpoints, rolling transcripts, targets/filter/noise/proof semantics remain. No hard
register cap: compiler allocation naturally drops to107; all SM86/89 proof8/16 debug/nondebug
new variants have0 stack/spill stores/loads. Memory safety and real speed are still untested
on the rig for this revision. Smaller tiles increase input requests and CTA count; better
latency hiding can still lose to worse reuse. Occupancy alone is not a speedup claim.

Native explicit --candidate 256 --two-cta (stage64). Live explicit --kernel-threads 256
--two-cta --pipeline --gpu-noise. Default remains OFF; old256 and scalar384 remain available.
Reject combinations with matrix loads, transfer overlap, wrong thread count, or CPU mock.
Every mining_batch reports two_cta; performance records two_cta_requested. Historical root
collector's Python import pin is updated for the reviewed miner module; its fixed OLD engine
is unchanged and it is NOT part of this task. No more hardware profiling in this revision.

CPU validation:94 tests pass; independent NumPy staged-load full-matrix/transcript model
checks128x128 boundaries, partial64-wide K, rank32/128/256, proof8/16,17-checkpoint rolling
slots,4x2 warp ownership and resource arithmetic. CPU contract/golden fixtures pass. Actual
CLI/CPU-reference/official-proof loopback retains all8verified proofs; this does not execute
the new GPU kernel. Build/resource evidence:miner/TWO-CTA-CPU-RESULT.json. No GPU speed measured.

## ONE local Codex task; current step3 kernel changed, step4 local checks done, step5 on rig

Only Mint4090 room-room@192.168.1.98, selected UUID. PL310W, core lock2600/current2610,offset+300,
mem405,both fans55,pool/wallet/profile/driver/API/autostart unchanged. No3060/Hive. Existing
one-test mining-pause authorization<=600s total; one attempt, no installs/tuning/retries,
production deployment or extra profiling. Children return to normal UID1000 with NO profiling
capabilities; root controller only handles existing pause/recovery, not GPU execution.

1. BEFORE PAUSE: new pinned checkout/checksums. Build sm89 with existing nvcc12.0; inspect NEW
   TwoCTA=true256/stage64/proof8/16 debug/nondebug symbols:registers<=128,stack/spill/local0.
   Check help two-cta-check/two-cta-compare/--two-cta. If compiler resource gate fails, no pause.
   Prepare unchanged pinned oracle via tools/prepare_miner.py and work-cpu. Prepare NEW
   tests/prepare_compact_check.py cases (1030CPU hits,10official sampled proofs) outside pool.
   Reuse the known good standalone Sanitizer2025.3.1; no installations or old profiler tasks.
2. Fresh baseline/current original PID/start ticks/settings/protected files; private tmpfs
   sufficient RAM (>=12GiB),no disk fallback. Reuse root-owned pidfd recovery controller,
   operation lock,all-thread-T/GPU idle/no-other-compute and exact identity checks. Watchdog590s
   armed BEFORE SIGSTOP,entire experiment cgroup RuntimeMax555s,KillModecontrol-group,children
   UID1000. One common pause/deadline for all following steps. No new privileges on GPU children.
3. NEW kernel correctness only, shared60s changed-path budget:

       python3 tools/test_4090_mint.py --run-gpu --mode two-cta-check --sanitizer
         --gpu <UUID> --expected-power-limit-w 310 --timeout-sec 15
         --paused-pid <CURRENT-PID> --paused-start-ticks <TICKS> --allow-concurrent-miner

   Require two_cta_correctness passed,fixtures6,full matrix/nondebug true,two_cta=true,
   matrix_loads=false,other_kernels_executed=false. BOTH two_cta_resources proof8/16 must show
   registers<=128,local0,active_blocks>=2. Exit0/errors0/leaks0. This query is predicted capacity,
   not observed sustained residency. On failure restore immediately; no timing/live test.
   Then ONE known-Sanitizer-wrapped protocol1 worker in same cgroup/pause:

       <verified-sanitizer> --injection-path <verified-path> --tool memcheck
         --error-exitcode 86 --leak-check full <new-bench> --run-gpu --mode worker
         --candidate 256 --stage-k 64 --two-cta --allow-concurrent-miner
         --paused-pid <PID> --paused-start-ticks <TICKS>

   Feed seq1/2/3 TAB raw_manifest TAB NEW_GPU_hits from cases.json,then QUIT. Require samePID,
   done1/2/3,generations1/2/3,groups4/513/513,all native batches threads256/two_cta=true/
   matrix_loads=false/pinned_transfer_overlap=false,exit0/errors0/leaks0. Run existing
   tests/verify_compact_outputs.py: ALL1030actual GPU hits/transcripts equal CPU;10official
   sampled GPU proofs pass including0/511/512 across BOTH slab boundaries. Preserve outputs.
   No old noise/root/filter/full-size/Sanitizer replay. Any error:restore/stop/report,no retry.
4. SAME pause:one short matched scalar384(A) vs new128x128/256(B),same resident inputs:

       python3 tools/test_4090_mint.py --run-gpu --mode two-cta-compare
         --duration 1 --warmup .25 --rounds 1 --timeout-sec 20
         --gpu <UUID> --expected-power-limit-w 310
         --paused-pid <PID> --paused-start-ticks <TICKS> --allow-concurrent-miner

   Four legs A/B/B/A:threads384/256/256/384,two_cta false/true/true/false,stage64,matrix_loads
   false,8192x8192,K4096,rank256,proof16. Post-compare full transcripts equal. Summary
   two_cta_comparison candidate_faster_for_live=true requires ratio>1.02 and BOTH B faster
   than BOTH A. Otherwise restore NOW;skip long run. No generic bench/old256/matrix/transfer
   comparison or extra profiler. A failed candidate is a valid result,not reason to retry.
5. ONLY if all gates pass and>=440s remain before cgroup555s deadline,ONE live420s:

       python3 tools/pearl_miner.py --pipeline --gpu-noise --kernel-threads 256 --two-cta
         --config <existing-private-config> --oracle <unchanged-pinned-oracle>
         --engine <new-engine> --allow-live --enable-submit --extended-test
         --measure-stability --duration 420 --stop-after-accepted 0
         --gpu <UUID> --expected-power-limit-w 310
         --paused-pid <PID> --paused-start-ticks <TICKS>
         --evidence <NEW-private-evidence> --workdir <NEW-private-control-dir>
         --ram-dir <validated-private-tmpfs-parent>

   NO --matrix-loads or --transfer-overlap. Original full profile/target/wallet/pool and
   natural Rayon40;fresh diagnostic worker. Abort reject/unknown/error/settings drift.
   No relaxed target,reconnect,retry,fallback or deadline extension. Every native batch
   threads256/two_cta=true;requested flag true. Preserve fresh/stale ledger,all phase times,
   actual candidate proof bytes/reports/pool receipts and read-only telemetry. Compare full
   rate to the previous29.677104515M fresh groups/s,explicitly retaining job/stale differences.
   Groups/s/matrix TOPS are not automatically SRBMiner TH/s;one share is not stable throughput.
6. Every exit:terminate/reap ENTIRE experiment cgroup,prove empty BEFORE SIGCONT,cleanup
   only validated tmpfs after consumers die,resume SAME original process. Unique miner,
   unchanged protected files/settings/capabilities,fresh CURRENT GPU0/API~333TH/s and new
   work/share evidence,sustained samples. No6hr average. Disarm watchdog after strict recovery.
7. Return REPORT-TWO-CTA-4090.md,full native build/resource and changed-kernel Sanitizer logs,
   1030-hit/10-proof checks,all4short legs/decision,live performance/actual proofs only if run,
   exact pause/recovery. Live counters null when skipped. No production installation or
   second experiment. State measured end-to-end change honestly;do not substitute occupancy
   or successful correctness for an actual hashrate gain.
