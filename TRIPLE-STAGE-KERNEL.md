# Same192x256 reuse, deeper shared-memory prefetch

Goal: higher real Pearl throughput than SRBMiner at existing310W. Not established. Latest
128x128/two-CTA candidate was rejected:4.24336ms control vs6.760385ms candidate,0.627680x.
It is NOT the development control. Control remains proven scalar384/192x256/stage64.

## This change

The candidate is a SEPARATE kernel, include/triple_stage.cuh. The original pearl_int8
kernel body, original padded prefetch and geometry are unchanged. Candidate keeps192x256,
384threads,3x4warp grid,128accumulators/thread,64-wide stages and exact32-wide checkpoint
semantics. No extra matrix input fetches and no smaller tile. Pool/filter/targets/noise/
proof formats unchanged. Explicit flag --triple-stage, defaultOFF, no automatic selection.

For the ACTUAL proof16 mining format: three shared stages instead of two; preload stage0/1,
then issue stage+2 before computing current. cp.async.wait_group1 leaves a future stage
pending; tail drains with wait_group0. CTA barrier protects readers before buffer reuse.
This attempts to hide memory latency identified as a plausible issue by the root profile;
it is not proof that global/shared latency is the only throughput limiter.

To fit three stages,64-byte rows replace80-byte padded rows. Sixteen-byte blocks are stored
at column XOR (((row>>1)&3)*16), and scalar32-bit reads invert the same mapping. This is a
bijection/aligned layout; the warp bank mapping is conflict-free by the offline address model.
Proof16 shared:3*448*64+12288=98304 dynamic bytes, expected+1024driver=99328 of102400. CUDA
max-shared carveout requested only for the new function; it is a hint, not GPU tuning.
Proof8 compatibility uses TWO swizzled stages because three+its larger history would not fit;
its dynamic shared81920bytes and pipeline_stages2 are explicit. Never call that path triple-
buffered. Actual live proof16 must report pipeline_stages3. No occupancy increase is claimed.

CUDA13.0.88 SM86/89 build: proof16 debug/nondebug168registers,proof8 nondebug166/debug167;
all8new functions0stack/0spill stores/loads. No hard register cap. Actual nvcc12/driver
resource and correctness gates must pass before timings/live work. Shared swizzle/modulo/
extra prefetch address arithmetic can cost instructions; a deeper pipeline can still lose.
No speedup percentage predicted. Primary async completion semantics:
https://docs.nvidia.com/cuda/archive/12.0.1/parallel-thread-execution/index.html

98 CPU tests pass. Independent physical-layout full-matrix/transcript model covers partial
192/256tiles,K tails,rank32/128/256,proof8/16,rolling slots,bijective aligned stores and warp
bank mapping. Separate async schedule model covers all1..69stage counts/depth2/3 for read-
before-ready/overwrite-before-barrier/tail drain. CPU CLI+official-proof loopback passes;
this is NOT GPU correctness or performance. miner/TRIPLE-STAGE-CPU-RESULT.json records limits.
Historical root profiler Python-import pin is refreshed for the reviewed client module; that
fixed old-engine profiler is not used here. No profiler/sanitizer installation or new privilege.

## ONE local Codex task

Current step3: compute pipeline changed; step4: local checks done; step5: one bounded rig test.
Only room-room@192.168.1.98 / Mint4090. PL310,core lock2600/current2610,offset+300,mem405,both
fans55,wallet/pool/profile/API/autostart/driver unchanged. No3060/Hive. One existing-authorized
pause<=600s,one attempt,no installs/tuning/retries/deployment. GPU children normalUID1000,
empty capabilities/NoNewPrivileges=yes. No root GPU profiling and no old diagnostic replay.

1. BEFORE PAUSE:new pinned checkout/checksums,native build existing nvcc12 sm89. Inspect
   pearl_triple proof8/16/debug/nondebug:registers<=168,stack/spill/local0. Verify --triple-stage,
   triple-check,triple-compare in help. On build/resource failure:no pause. Prepare unchanged
   oracle with tools/prepare_miner.py and CPU work-cpu; NEW prepare_compact_check.py cases:
   1030CPU hits,10official sampled proofs. Use known standalone Sanitizer2025.3.1,no installs.
2. Fresh current original identity/baseline/protected files/settings;private tmpfs>=12GiB,
   no disk fallback. Reuse root-owned pidfd/start-ticks controller,operation lock,all-thread-T,
   GPU idle/no-other-compute,selectedUUID. Watchdog590s armed BEFORE SIGSTOP; whole experiment
   cgroup RuntimeMax555s,KillModecontrol-group;one common pause/deadline. Never hardcodePID.
3. NEW kernel correctness only,common60s changed-path budget:

       python3 tools/test_4090_mint.py --run-gpu --mode triple-check --sanitizer
         --gpu <UUID> --expected-power-limit-w 310 --timeout-sec 15
         --paused-pid <PID> --paused-start-ticks <TICKS> --allow-concurrent-miner

   Require triple_stage_correctness passed,fixtures6,full matrix/nondebug true,triple_stage
   true,matrix_loadsfalse,other_kernels_executedfalse. Both triple_stage_resources entries:
   proof16stages3,proof8stages2,registers<=168,local0,activeblocks>=1. Exit0/errors0/leaks0.
   Then ONE known-Sanitizer-wrapped protocol1 worker in same cgroup/pause:

       <sanitizer> --injection-path <verified-path> --tool memcheck --error-exitcode 86
         --leak-check full <new-bench> --run-gpu --mode worker --candidate 384
         --stage-k 64 --triple-stage --allow-concurrent-miner
         --paused-pid <PID> --paused-start-ticks <TICKS>

   Feed seq1/2/3 TAB raw_manifest TAB NEW_GPU_hits from NEW cases.json,then QUIT. Require
   same PID,done1/2/3,generations1/2/3,groups4/513/513,all batches threads384/triple_stage=true/
   two_cta=false/matrix_loads=false/pinned_transfer_overlap=false;pipeline_stages3/2/3 for
   casesproof16/8/16. Verify ALL1030actual GPU hits/transcripts against CPU and10official
   sampled GPU proofs (existing verify_compact_outputs.py),including0/511/512 both boundaries.
   Exit0/errors0/leaks0. Any mismatch/error/budget failure:restore/stop/report,no retry.
4. SAME pause:one short matched scalar384(A) vs new384-triple(B):

       python3 tools/test_4090_mint.py --run-gpu --mode triple-compare
         --duration 1 --warmup .25 --rounds 1 --timeout-sec 20
         --gpu <UUID> --expected-power-limit-w 310
         --paused-pid <PID> --paused-start-ticks <TICKS> --allow-concurrent-miner

   A/B/B/A all384/stage64,triple_stagefalse/true/true/false;resident same8192x8192,K4096,
   rank256,proof16;post-compare full transcripts equal. triple_stage_comparison
   candidate_faster_for_live=true requires speedratio>1.02 and BOTH B faster than BOTH A.
   Otherwise restore immediately,skip420s. No generic/old-two-CTA/matrix/transfer benchmark,
   repeat legs,extra hardware profile or clock adjustment.
5. ONLY if all gates pass and >=440s remain before555s cgroup deadline,ONE live420s:

       python3 tools/pearl_miner.py --pipeline --gpu-noise --kernel-threads 384 --triple-stage
         --config <existing-private-config> --oracle <unchanged-pinned-oracle>
         --engine <new-engine> --allow-live --enable-submit --extended-test
         --measure-stability --duration 420 --stop-after-accepted 0
         --gpu <UUID> --expected-power-limit-w 310
         --paused-pid <PID> --paused-start-ticks <TICKS>
         --evidence <NEW-private-evidence> --workdir <NEW-private-control-dir>
         --ram-dir <validated-private-tmpfs-parent>

   NO --two-cta/--matrix-loads/--transfer-overlap. Original full proof16profile,target,wallet,
   pool, natural Rayon40; fresh diagnostic worker. Every batch384/triple_stage=true/pipeline_stages3;
   requested flagtrue. Abort on rejection/unknown/error/drift. Preserve actual candidate proofs/
   reports/pool receipts,fresh/stale ledger,allphases and read-only telemetry. No target
   relaxation, reconnect, retry, fallback,deadline extension or production installation.
   Compare full rate with previous29.677104515M fresh groups/s,not rejectedtwo-CTA. Different
   jobs/stale behavior must be disclosed. No automatic conversion to SRBMinerTH/s or claim
   of stable speed from one acceptedshare. Real end-to-end work remains the goal.
6. Every exit:kill/reap ENTIRE experiment cgroup,prove empty BEFORE SIGCONT,cleanup only
   validated tmpfs after consumers die; resume SAME original identity, unique SRBMiner, exact settings/
   protectedfiles/capabilities,fresh CURRENT GPU0/API~333TH/s andnewwork/share, sustained samples.
   No 6hr average. Disarm watchdog after strict recovery; transient units inactive, no residual processes.
7. Return REPORT-TRIPLE-STAGE-4090.md, full build/resource and changed-kernel Sanitizer logs,
   1030-hit/10-proof checks, all four short legs/decision,live performance/proofs only if actually run,
   exact pause/recovery. No live counters when skipped:use null.No second experiment or deployment.
