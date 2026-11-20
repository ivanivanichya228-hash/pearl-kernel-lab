# Pearl miner alpha 0.7.0 — runnable network/GPU loop

This is an experimental runnable miner, not an SRBMiner-speed replacement claim.
No real LuckyPool share has yet been sent or accepted by this build. Do not interpret local
mock-pool acceptance or the earlier synthetic GPU proofs as real mining revenue.

## What is implemented

`tools/pearl_miner.py` opens a newline-JSON plain TCP session, authorizes with private local
wallet/worker, receives current V3 jobs, builds fresh work, invokes the GPU engine, reconstructs
and officially verifies each hit, and sends mining.submit only when explicitly enabled.
The pool's exact explicit target is preserved. Counts sent/accepted/rejected/unknown are separate.
An accepted count requires the matching request ID, result=true, error=null from that connection.

New jobs, same-ID target changes, disconnects and unsupported difficulty updates invalidate work.
The reader continues while preparation/GPU/proof work run; cancellation kills and reaps its process
session before temporary work is deleted. A last freshness check precedes every submit write.
Unique request IDs and proof SHA deduplication prevent blind repeats. Unknown outcomes are never
retried automatically. CLI makes only one connection and stops on the first explicit rejection.
No raw server error, credentials, argv or pool authorization payload is logged.

`work-prepare` uses OS-randomized raw INT7 matrices for EVERY pass. It builds full official keyed
Merkle commitments and salted noise in chunks. It does not precompute CPU GEMM, invent hits or
load golden transcripts. `work-finalize` reconstructs proofs for reported indices and checks their
transcripts and exact target using the pinned unmodified official Pearl verifier. Target scaling
remains the official rank-penalized rule; LuckyPool's current policy is not independently confirmed.

`mine-batch` computes stage64 slabs and filters on the SAME stream. It processes full explicitly
selected M/N, including131072, without shrinking committed dimensions or raising the tested
kernel's32768 bound. Slabs are<=8192, global indices include both offsets, and every group is covered
once. Host/GPU work is bounded, all hits per slab fit the queue, and excess total proof queue size
fails without partial output. The unchanged src/kernel.cu and src/filter.cu implement arithmetic/hash.
The NEW scheduler/file path is compiled but has not run on the rig yet.

Prepared Rust bridge (Linux x86_64, glibc>=2.34) is SHA/source-pinned in miner/oracle-lock.json.
It needs only libc/libgcc, not a Rust installation or system changes. Existing nvcc builds GPU code.
The chosen full profile is the inspected client's131072x131072,K4096,rank256,16x16; the pool did
NOT advertise/confirm these fields. First live response must establish compatibility; never claim
otherwise or silently change to32x32. This profile is not a performance recommendation.

## Validation completed here

- CUDA13.0.88 compilation SM86/89; native math/hash source SHA unchanged.
- Real loopback TCP integration: two newly randomized batches, eight different bincode proofs.
  Local server independently checked EVERY received proof using the official verifier and exact
  local target. Six explicit accepts and two deliberate rejections were accounted correctly.
- These were mock responses, independent C++ CPU arithmetic, zero GPU and ZERO external traffic.
  See miner/LOOPBACK-RESULT.json. Real-pool accepted remains false.
- Tests cover target-change cancellation, disconnect invalidation, non-plain auth refusal,
  unknown outcomes, subprocess cancellation/reaping, private credential permissions, slab mapping,
  and the existing contracts. Old GPU/ABBA tests are not required again.

## Prepare while original mining continues

    python3 tools/prepare_miner.py
    make
    make build/work-cpu build/test-work-index
    build/test-work-index
    python3 -m unittest discover -s tests -p test_miner_loop.py
    python3 tools/prepare_live_check.py --out build/new-worker-check
    build/work-cpu build/new-worker-check/work/work.bin build/new-worker-check/cpu-hits.json

Prepared bridge source hashes must match. Local modifications to safety code in Python/C++ do
not require replacing the Rust bridge. Test --help/bridge command BEFORE any pause.
No old CPU-true probes, CUDA reinstall, Rust install, six-fixture replay or old benchmarks.

## Codex task — ONE bounded Mint4090 experiment

Use a NEW checkout of this revision; preserve all successful local paused-PID/start-ticks,
controller/cgroup/watchdog protections. Do not run the network loop from a root process.
Do not replace SRBMiner or change desired service states, pool/wallet, PL, OC, fans, driver,
panel, VPN,3060 or Hive. Read actual profile/UUID/PL; previous PL was310W, never set it here.

1. Finish all build/unpack/CPU steps above while mining continues. Verify CHECKSUMS and source
   pins first, preserve the original checksums before integrating local guards. Check available
   RAM/temporary disk for full work (allow8GiB), VRAM and glibc compatibility. Record actual
   original miner throughput, PID/start-ticks, unique process and protected profile identities.
2. Create owner-only private JSON from miner/config.example.json, owned by the unprivileged runner.
   Read the current wallet from the existing private configuration without logging it. Use a NEW
   diagnostic worker name; existing SRBMiner worker and launch files remain untouched. Use the
   actual pool endpoint. Default inspected full profile is miner/luckypool-profile.json.
3. Reuse independent root-owned outer controller and existing operation lock. Arm watchdog70s
   before pidfd SIGSTOP; all original threads must beT, GPU idle and no other compute work.
   Controller/fans remain active. Test subprocesses, including their sessions, belong to ONE
   transient cgroup with deadline58s. Hard total pause<=90s. No retry after any failure.
4. First run the NEW small work path once under the already successful standalone Sanitizer2025.3.1,
   via integrated tools/test_4090_mint.py mode mine-batch (timeout15s), --work-input
   build/new-worker-check/work/work.bin and a NEW --work-output absolute path. Supply actualPL,
   UUID and existing paused-identity controls. Preserve Python/C++ local guards. Require exit0,
   memcheck0/leaks0 and phase mining_batch groups4,hits4,target_modified=false.
5. Compare GPU hit indices/transcripts to build/new-worker-check/cpu-hits.json ignoring only
   GPU_executed. Run the prepared official bridge work-finalize on this GPU output, outside GPU
   sanitizer, and require four exact-target/structural successes. It is a LOCAL never-submit job.
   If failed or less than35s remain before the cgroup deadline, restore immediately; do not proceed.
6. With sufficient remaining budget, SAME pause, ONE actual live connection (no mock/replay):

       python3 tools/pearl_miner.py --config <private-0600-config>
         --oracle <worktree>/build/pearl-protocol-oracle --engine <worktree>/build/pearl-bench
         --allow-live --enable-submit --gpu <UUID> --expected-power-limit-w <live-PL>
         --paused-pid <original-PID> --paused-start-ticks <start-ticks>
         --duration 30 --workdir <new-private-0700-work-directory>
         --evidence <new-private-0700-log-directory>

   Preparation/GPU/verifier stdout and stderr are retained in the private evidence directory.
   No authorization request or raw pool error is printed.
   The script never stops/resumes miners itself: ONLY run it inside the known safe outer controller.
   Full prepare/GPU/proof stages count toward the30s budget. Do not add reconnects or extend the
   pause to chase a share. Current archived target implies about12.3 billion proof groups per
   expected share (about183 full batches); a30s run is NOT guaranteed to find a share. Record zero
   honestly. No smaller dimensions, altered target, fake proof, copied old proof or claimed win.
7. On EVERY exit prove the entire test cgroup empty BEFORE SIGCONT. Strictly confirm the same
   original PID/exe/argv/env/profile/PL/fans, fresh positive hashrate plus job OR accepted share,
   no duplicate miner and sustained return to live pre-test throughput. Then remove watchdog.
8. Return full new-worker sanitizer output, GPU hits/proof check, real network counters and actual
   duration, categorized rejection if present, and complete recovery. Do not export credentials.
   Distinguish accepted0 from no attempt, timeout, unknown and explicit rejected. No performance
   or profit claim without a sufficiently long, separately agreed full-cycle measurement.

## Limits

The CLI is bounded to1..50 seconds for alpha validation, not installed as an unattended miner.
Preparation/commitment/noise, file transfers, verifier cost and slab scheduling have NOT been
benchmarked together on4090. Live throughput and pool acceptance are unknown. The kernel's
previous +9.64% is only versus our earlier kernel. SRBMiner remains the working production miner.
