# Preparation and evidence fix — 0.7.1

No real-pool share is accepted. This release does NOT authorize another short pause or claim that
thirty seconds can demonstrate share acceptance. The reported live run connected/authorized but
completed zero batches; one was cancelled after a new job.

## Measured cause and correction

From the rig's preserved ANALYSIS.txt: first preparation took approximately19.953s including
process/guards; GPU was then entered for at most1.120s before cancellation. Second preparation
lasted approximately8.739s before the budget expired. GPU kernel duration and the rig's exact
preparation substep bottleneck are UNKNOWN. Logs were destructively opened wb on each batch.

On an independent NON-MINING CPU host, full explicit131072x131072,K4096,rank256 work was measured
with4 Rayon threads (no GPU, external network or changes to the rigs):

| Variant | Random matrices | Commitments | Noise + work writing | Total |
|---|---:|---:|---:|---:|
| Previous implementation + timing |6.622s|1.257s|4.796s|13.017s|
| Bulk random fill only |2.306s|1.101s|4.796s|8.423s|
| Bulk fill + parallel noise |2.359s|1.107s|1.134s|4.906s|

Single full-size run per variant, same host. OS-random matrices differ between runs. This is not
RTX4090 speed, mining hashrate, energy efficiency or an estimate for the Mint CPU.

- CSPRNG fills bulk bytes, masks7 bits and translates to canonical signed INT7[-64,63]. Fresh
  OS seed each pass, no reused fixed seed. This replaces expensive random_range per byte.
- Official permutation/uniform generators are reused. Permutations are cached per matrix;
  row preparation runs in the existing bounded Rayon pool. Global row indices and A/B seed order
  are retained. Rust tests compare every produced noise byte to unmodified official code across
  A/B, ranks128/256 and global rows crossing a1024 boundary. They pass.
- Full loopback CLI integration still sends eight NEW proofs; every proof is checked by the
  official verifier at the local explicit target. Mock responses are never real pool acceptance.
- src/kernel.cu, src/filter.cu, src/pipeline.cu, job binding, target rule and wire protocol UNCHANGED.
  No GPU/driver/toolkit rebuild or old GPU validation is required for this CPU/log patch.
- Timing is emitted after raw generation, commitments, raw file writes, noisy work writes and
  sync. A cancelled batch keeps its own logs, context fingerprint and append-only start/end
  events with wall+monotonic timestamps, outcome, exit code and elapsed duration.
- Each batch has its own evidence/batch-*/ directory. wb overwrite across batches is removed;
  log files use exclusive creation. Cancellation and the next batch are tested explicitly.

Evidence: miner/PREPARE-CPU-RESULT.json and miner/LOOPBACK-RESULT.json. Updated source-pinned
prepared Rust bridge is included; tools/prepare_miner.py verifies it. Never install system Rust.
Use a new checkout/build directory; this installer deliberately refuses a different old binary.

## Share acceptance timing is statistical

At the archived captured target and selected official rank-penalized rule, a full batch scans
67,108,864 proof groups and has about0.00546125 expected successful shares. That is approximately
183 full batches per expected share; SIX completed batches yield only about3.22% chance of at
least one. Actual future pool target, full-cycle runtime and dependency between hashes can differ.
The model assumes uniform independent hashes and is NOT a promise about duration or acceptance.
No false target, fake candidate, delayed stale proof or local verifier result may count as a real
share. Server acceptance also depends on the pool supporting the chosen profile/protocol.

Thus a short live run can establish connection and completed work, but cannot reliably force
an accepted share. Do not silently turn a previously bounded pause into a long mining outage.
No automatic retries, new pause, higher PL or unattended installation in this fix.

## Codex handoff: apply and measure CPU only, with SRBMiner RUNNING

1. New checkout, verify original CHECKSUMS; preserve existing rig-side controller/guards.
   No miner signals, CUDA commands, GPU work, driver/OC/fan/pool/wallet or service changes.
2. python3 tools/prepare_miner.py (new build directory, glibc>=2.34).
   Run the small Python tests / CPU loopback if required; do not rerun old GPU tests.
3. One CPU-only work-prepare using pool/captured-notify.json and miner/luckypool-profile.json,
   RAYON_NUM_THREADS=4, output to a NEW owner-only temporary directory. Use timeout45s and retain
   complete stdout/stderr. The header is archived; NEVER submit this work. No pool connection.
   Available disk8GiB and adequate RAM must be checked before starting. Do not substitute small
   dimensions or run parallel duplicates. A timeout is reported honestly, not retried.
4. Return stage durations and confirmation that the existing live miner was not stopped or
   reconfigured. Remove generated temporary raw/work data after collecting timings; retain logs.
5. Do NOT start another live/GPU experiment from this handoff. A meaningful acceptance run needs
   measured full-cycle throughput and an explicitly bounded duration consistent with the user's
   mining continuity requirement. The short previous task in LIVE-MINER.md is superseded here.
