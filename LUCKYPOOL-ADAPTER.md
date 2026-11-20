# Revision0.5.0 — captured LuckyPool job adapter and GPU jackpot filter

## Actual captured job

pool/captured-notify.json contains only the public notify from the supplied PUBLIC-JOB.json;
wallet, worker, authorization and miner process metadata are omitted. It is an ARCHIVED job
from a CLOSED diagnostic session, not a live job that can be submitted now.

Decoded by the official Rust header parser and independently by Python:
- certificate3 -> Salted seed derivation, independent of block-header version;
- exactly76 header bytes, block version0x20000000, timestamp1795126315, block nbits0x1743e183;
- notify target is a big-endian integer in hex; jackpot digest is interpreted little-endian.
- target is NOT recomputed from diff1500000 or substituted with header block nbits.

The captured notify contains no K/rank/matrix/pattern selection. Profiles are EXPLICIT local
choices. pool/client-reference.json records131072x131072/K4096/rank256/proof16x16 from the
inspected independent client; its claim of a mandated profile is NOT treated as confirmed pool policy.
pool/lab-small.json chooses64x64 with the same K/rank/pattern ONLY for bounded CPU diagnostics.
These profiles never alter the user's miner or GPU settings. No live large profile is silently shrunk.

## Implemented and checked

1. tools/luckypool_adapter.py: strict offline notify/header parsing, current-context fingerprint,
   stale-job invalidation, explicit profile and exact share-target scaling. No socket code.
2. Bound follows official penalized_target_bound:
   target * proof_rows * proof_columns * (K/rank) *128, rejecting U256 overflow.
   For K4096/rank256/proof16x16 factor=524288. Rust and Python produce identical exact bounds.
   This is the current OFFICIAL miner/verifier policy, not a confirmed observation of LuckyPool's
   server implementation. The inspected third-party miner_capi.py instead uses unpenalized h*w*K
   (1048576 for that profile). That discrepancy is retained explicitly; its defaults/formula are
   not silently adopted as authoritative pool rules. Backend consumes an explicit already scaled bound.
3. proof-oracle pool module calls unmodified official verifier/parser/noise/hash functions.
   On the captured header, one bounded small diagnostic candidate was constructed and its
   STRUCTURE/job/Merkle/seed validated with an explicitly EASY verifier target override.
   This is deliberately NOT reported as meeting the actual pool target: it FAILS the exact
   captured share target. The submission formatter correctly refuses it. No proof was sent.
4. A separate SYNTHETIC easy-target fixture passed official verification and formatting into
   newline JSON mining.submit with dictionary wallet/worker/job_id/plain_proof(base64 bincode).
   Proof bytes round-trip unchanged. Fake wallet strings were used only in offline tests.
   Altered proof bytes, stale job, foreign header and unmet actual target were rejected.
   The format is sourced from an inspected client, not a pool acceptance test.
5. New include/jackpot_hash.hpp computes keyed BLAKE3 for EXACTLY64 transcript bytes and
   compares eight LE hash/target words.195 official Pearl BLAKE3 vectors passed CPU comparison,
   including real-job/fixture keys, random inputs, target equality, just-below, max and zero.
6. src/filter.cu implements the GPU filtering stage: one context per batch, bounded hit-index
   queue, total-hit count even with capacity0/1, optional test-only per-item contexts/debug hashes.
   Producer GEMM and consumer filter must use the SAME CUDA stream. No mining loop calls this yet.
   SM86/89 CUDA13.0.88 compilation:40 registers, no stack/spills, no shared memory/barriers.
   GPU execution and performance of this NEW stage are NOT yet tested.

Evidence: pool/CPU-RESULT.json, CAPTURED-JOB-PLAN.json, REAL-HEADER-CANDIDATE.json, hash-vectors.bin.
Existing stage64 matrix kernel source remains unchanged. No network/GPU access happened here.
The formatter trusts only the caller's locally produced verifier report; JSON booleans are not
cryptographic certificates and it is not an API for accepting untrusted validation reports.

## Primary implementation references

Official pinned Pearl proof and target rules:
https://github.com/pearl-research-labs/pearl/tree/38dd764ab0aec528e81fc467665c6762ef6739e9/zk-pow/src

Inspected independent client protocol/profile reference (not imported or executed):
https://github.com/Muskwak/Open-Pearl-Miner/blob/ac3d992d7eb6ca1bb344d5d3ee125eecb182248d/python/pool_common.py

No dev-fee scheduler, addresses or code from that client are included in the adapter.

## Reproduce offline, no rig needed

  python3 tools/luckypool_adapter.py --job pool/captured-notify.json --profile pool/client-reference.json --out build/job-plan.json
  python3 -m unittest discover -s tests -p test_pool_adapter.py
  make build/test-jackpot-hash
  build/test-jackpot-hash pool/hash-vectors.bin

Optional official Rust bridge (same prepared upstream checkout and installed Cargo as previous stage):
  cargo build --locked --release --manifest-path proof-oracle/Cargo.toml
  proof-oracle/target/release/pearl-protocol-oracle pool-candidate pool/captured-notify.json pool/lab-small.json build/real-header-candidate
  python3 tests/run_pool_integration.py --oracle <absolute-oracle-binary> --fixtures <unpacked-official-fixtures>

## Single bounded Codex GPU task — filter check only

Only Mint4090, existing actualPL and profile unchanged. Preserve keys/private files, fan/OC/
miner/control service, pool/wallet, drivers, system CUDA, panel/VPN. Never test3060/Hive.

1. NEW worktree. Read last successful proof-stage local guards/controller/recovery; preserve all
   uncommitted safety code. Before pause confirm current sustained miner speed around its normal
   pre-test baseline (~333TH/s in latest report), accepted shares and no errors. No settings changes.
2. Run the small Python adapter tests and g++ hash-vector test above while mining continues.
   No Rust installation/build on the rig. Ready195-vector file is hash-checked by CHECKSUMS.
3. Merge existing pausedPID/start-ticks/all-thread-T, operation lock, UUID/currentPL, cgroup/session
   cleanup, independent watchdog and full-speed restoration into this revision. Keep new mode and
   hash-filter output validation. Reuse known good standalone Sanitizer2025.3.1 via pinned hashes;
   no downloads/CPU-true/minimal-CUDA probes or revalidation of unchanged proof fixtures.
4. Build new bench/filter with the existing nvcc. --help before pause must list filter-check and
   --hash-vectors. Matrix src/kernel.cu hash stays91e9721506867dda5872267c465b0ee2c33596f96b54d788641e5d163816c352.
5. ONE new snapshot/lock/watchdog70s controlled pause, guard timeout30s/cgroup40s/hard total<=90s.
   Run the NEW mode under successful sanitizer:
     --run-gpu --mode filter-check --hash-vectors <worktree>/pool/hash-vectors.bin
   with existing --sanitizer/actual UUID/currentPL/pausedPID/start-ticks controls.
   Filter-check verifies per-item official hashes/indices, the production uniform-context entry,
   count/capacity1 sentinel, capacity0 and empty input. No benchmark or original six-fixture rerun.
6. Success requires hash_filter_correctness passed=true, official_vectors195,
   uniform_context_passed=true, capacity_edges_passed=true, tool exit0, memcheck errors0 and leak0.
   Do not require the old 'phase:correctness' record for this new mode; require its actual new record.
   Do not fabricate/bypass gates. On error save full output, restore original mining and stop.
7. In EVERY path kill/check empty test cgroup before SIGCONT, then strict identity/settings/
   fresh work-or-share and sustained full-speed recovery. Disarm watchdog only after return.
   Deliver full sanitizer/check output and recovery, actual pause and PL. No tuning or extra retries.
8. DO NOT CONNECT to the pool, submit a share, run a live search or deploy into SRBMiner in this task.
   The archived capture belongs to a closed session. The remaining production work is the live
   job loop plus matrix/noise/commitment preparation and proof construction around GPU hits.
   This revision is not a complete miner and claims no new hashrate/energy gain.
