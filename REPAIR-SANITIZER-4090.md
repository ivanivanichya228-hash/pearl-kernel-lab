# Fix injection discovery without a mining pause

The supplied run stopped before memcheck: installed /usr/bin/compute-sanitizer 2022.4.1
could not locate libsanitizer-collection.so (exit13). This does NOT prove the file is absent.
Ubuntu's package commonly stores it in /usr/lib/nvidia-cuda-toolkit/compute-sanitizer/.
Official --injection-path selects that directory without moving executables or adding /usr/bin symlinks.
Sources:
https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/
https://packages.ubuntu.com/jammy/amd64/nvidia-cuda-toolkit/filelist

This revision adds tools/sanitizer_preflight.py. It inspects the installed executable, package
inventory, candidate injection directories, both collection/public libraries, x86-64 ELF format,
root ownership/non-writable paths and ldd dependencies. It requires matching package ownership
when dpkg can identify the executable. No broad filesystem scan or mixing toolkit versions.
It then smoke-tests ONLY /usr/bin/true with CUDA_VISIBLE_DEVICES=-1 and require-cuda-init=no.
This checks CPU process injection startup; it is NOT a CUDA memory correctness test.
The PL guard uses the audited path explicitly for future memcheck. Kernel source is unchanged.

## Task for Codex connected to Mint4090

Perform this repair while mining continues. No SIGSTOP/SIGCONT, GPU test, benchmark,
CUDA workload, clocks/fans/PL changes, driver installation, toolkit upgrade or miner restart.
No work on3060/Hive. Keep all prior working copies/evidence and private files.

1. Read supplied error report and current protected gate (passed=false); keep the gate false.
   Fetch this revision in a new worktree. Read source before use. Run CPU tests:
   python3 -m unittest discover -s tests -p 'test_sanitizer_preflight.py'
   python3 -m unittest discover -s tests -p 'test*guard.py'
2. On4090 run python3 tools/sanitizer_preflight.py --audit-only. This does not launch sanitizer.
   Inspect executable realpath, dpkg package/version/file inventory, library realpaths/permissions,
   and dependency findings. Do not print private miner arguments/environment or secrets.
3. If matching complete directory found, run python3 tools/sanitizer_preflight.py once.
   This executes only CPU /usr/bin/true, with no CUDA workload. It passes the documented
   --injection-path explicitly. Save raw output and command/tool/library identities.
4. If missing/damaged files are established, repair ONLY those Compute Sanitizer component
   files from the verified official package of the SAME installed version. Obtain package
   metadata/hash through configured official apt sources, download/extract without running
   a full toolkit installer. Restore original component paths/ownership if needed. Do not
   install/upgrade CUDA toolkit or drivers or create library links in /usr/bin. No third-party
   .so files or cross-version mixing. If exact verified package unavailable, report the precise
   blocker instead of making substitutions. Retry CPU-only audit/smoke after actual repair.
5. Port this module and explicit injection-path invocation into the previously validated local
   guard, preserving paused identity, cgroup cleanup, current PL checks, watchdog and strict
   recovery criteria. Preserve the new rounds/warmup/session cleanup behavior as well.
   Do not overwrite safeguards. Record diff and source hashes. No CUDA test yet.
6. Confirm miner still running with fresh status and original settings; a pause is not needed.
   Report exact executable/library/version, resolved dependencies, CPU smoke return/output,
   repair performed and unchanged miner. Leave memcheck gate CLOSED: GPU validation still pending.

Only after this repair report should we resume the separately prepared guarded memcheck and,
if successful, longer A/B/B/A. CPU startup success alone must never authorize benchmark gate.
