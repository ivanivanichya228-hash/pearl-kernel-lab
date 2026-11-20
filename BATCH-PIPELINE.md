# Bounded offline batch pipeline — 0.6.0

VALIDATION COMPLETED 2026-11-20: Mint4090 passed the single pipeline-check (195 vectors,
4 groups, hits[1,3], memcheck0/leaks0). Actual GPU export SHA256
7dd113eadb481bebb723d1ebc4a10f7dd68d4fbb42d8ff10880dc70dae2b9a93
was independently finalized with the pinned official Pearl oracle: both proofs pass structure
and exact SYNTHETIC target; all four transcripts match. Both submit frames round-trip offline.
See pool/GPU-PIPELINE-RESULT.json. The rig report records7.912157s pause and333.379TH/s restored
at unchanged310W PL. No real share was sent. The task below is historical: DO NOT rerun it.

This revision connects already prepared noisy matrices to stage64 GEMM, keyed BLAKE3 filtering,
hit indices and official plain-proof reconstruction. It is not a live mining loop.
The captured header is archived. The diagnostic target/job ID are SYNTHETIC and must never
be submitted to a pool. No network client or mining.submit transmission is implemented here.

## Completed here

- Official pinned Pearl code prepares raw matrices, keyed Merkle commitments, salted V3 noise,
  four transcripts and exact target decisions for explicit M=N32,K4096,rank256,proof16x16.
- A middle synthetic target produces exactly two hits and two misses. It exercises both paths.
- Independent C++ computes the whole matrix, every transcript and keyed target decisions;
  all match the official Rust oracle. The reproducible SHA-pinned archive contains six files.
- CPU-simulated hit input is converted to two actual bincode PlainProof values. Both pass the
  unmodified official structural verifier AND the explicit synthetic target check. Both
  round-trip through the offline newline-JSON submit formatter with a fake wallet.
- Eight negative inputs are rejected: stale job, wrong batch, missing/false/duplicate/out-of-range
  hits, changed transcript and missing transcript. Finalization rechecks ALL four transcripts
  and derives the complete hit set independently, rather than trusting the producer's booleans.
- CUDA producer and consumer are queued on one nonblocking stream with no intervening host sync.
  Debug path checks full C; non-debug path exports actual device transcripts and indices.
  Queue holds every candidate. No matrix/filter kernel source changes from the previous revision.
- New CUDA pipeline compiled for SM86/89 with CUDA13.0.88. No GPU execution happened here.
  The GPU test must establish this new path; older stage64 results are not a substitute.

Evidence: pool/PIPELINE-CPU-RESULT.json, pool/pipeline-lock.json.
The old +9.64% measurement compared our own two arithmetic kernels, not SRBMiner or this pipeline.

## Offline reproduction (developer machine, not required on rig)

    python3 tools/pipeline_fixture.py --unpack build/pipeline-lab
    make build/check-pipeline
    build/check-pipeline build/pipeline-lab/batch.fixture
    python3 tests/run_pipeline_integration.py --oracle <built-official-oracle> --batch build/pipeline-lab

Build oracle with the same pinned official upstream/Cargo.lock and Rust1.90 as earlier stages.
The rig does NOT need Rust, a new CUDA installation or new drivers. Fixture preparation uses
bounded diagnostic dimensions explicitly; no claim is made that a pool accepts that profile.

After receiving actual GPU export, finalize HERE with trusted official oracle:

    proof-oracle/target/release/pearl-protocol-oracle batch-finalize build/pipeline-lab GPU-PIPELINE-4090.json build/gpu-pipeline-proofs

Its two proofs must pass the official verifier plus exact synthetic-target check. The export's
GPU_executed field is a producer claim, not attestation; preserve original rig/sanitizer evidence.
No recursive ZK certificate or real-pool acceptance is claimed.

## Codex task: ONE bounded Mint4090 GPU check

Implement this task in a NEW worktree of this exact revision. Preserve all local controller,
watchdog and restoration fixes from the last successful proof run. Do not overwrite them by
resetting an old checkout. Do not install Rust, CUDA, drivers or anything system-wide.

1. While mining continues, verify CHECKSUMS.sha256; unpack the archive into a NEW build directory.
   Run build/check-pipeline and the small pipeline-guard tests. Build the new bench with existing
   nvcc; --help must list pipeline-check, --pipeline-fixture and --export-pipeline BEFORE pause.
   Reuse the known successful standalone Sanitizer2025.3.1 bundle after hash verification.
   Do not repeat sanitizer installation, CPU-true/minimal probes, old six-proof tests or ABBA.
2. Only room-room@192.168.1.98 (Mint RTX4090). Read LIVE UUID, PL and profile; retain all values.
   Never change PL, core/memory/offset, fan mode/speed, pool/wallet, service desired state,
   drivers, panel, VPN or other rigs. Confirm sustained original mining baseline and fresh work.
3. Reuse existing pool.operation.lock, independent root-owned watchdog70s, pidfd PID/start-ticks
   identity, all-threads-T and idle checks. Keep GPU controller/fans active. Never stop the miner
   via normal service control. No GPU work while SRBMiner runs; SIGSTOP only under the guard.
4. ONE controlled pause. Existing safe outer controller invokes tools/test_4090_mint.py with:

       --run-gpu --mode pipeline-check --sanitizer
       --gpu <live-UUID> --expected-power-limit-w <live-PL>
       --pipeline-fixture <unpacked>/batch.fixture
       --export-pipeline <new-absolute-path>/GPU-PIPELINE-4090.json
       --hash-vectors <worktree>/pool/hash-vectors.bin
       --timeout-sec 50 --allow-concurrent-miner

   --allow-concurrent-miner only bypasses process-name presence for the independently STOPPED
   miner; it is not permission to run concurrently. Preserve local extra paused-PID/start-ticks
   checks when integrating the new mode. Do not run this bare command outside safe controller.
   Outer transient test cgroup must include the wrapper's new session and every descendant.
   Cgroup deadline58s, watchdog70s, hard total pause<=90s. On failure save full output and restore;
   do not retry or launch further GPU work. Build/unpack/proof reconstruction run outside pause.
5. One mode includes the195 hash-filter vectors and then debug/full-C plus non-debug connected
   producer→filter path. Require BOTH records: hash_filter_correctness passed with195 vectors,
   uniform_context_passed and capacity_edges_passed; pipeline_correctness passed with groups4,
   hits2, debug_matrix_checked, non_debug_transcript_checked and ordered_stream all true.
   Require sanitizer exit0, errors0, leaks0 and complete GPU export. Do not bypass any gate.
6. EVERY exit: kill and prove ENTIRE test cgroup empty before SIGCONT. Confirm same original PID,
   unchanged profile/PL/fans, no duplicate miner, fresh positive hashrate plus job or accepted share,
   and sustained return to pre-test throughput (~333TH/s previously; use fresh baseline).
   Disarm watchdog only after full restoration. Report actual pause and complete recovery.
7. Return GPU-PIPELINE-4090.json and full sanitizer/guard/restoration output. No Rust build on rig.
   NO pool connection, live search, share transmission, main-miner replacement or deployment.

## Remaining production work

The small verified pipeline must still become a scalable scheduler with matrix/noise/commitment
costs included, correct live job/target replacement and stale cancellation, pool profile agreement,
proof queue and real accepted shares. Current kernel dimension bound is32768; inspected client
profile131072 is not supported by this bounded lab path and is not silently substituted.
Production hash rate and profit improvement remain unmeasured.
