# One fixed root profiler run; original miner/settings unchanged

Goal remains faster real Pearl mining than SRBMiner at310W; no speedup established. Prior
PERFMON scope/inheritance passed but the actual ncu2022.4 collection failed ERR_NVGPUCTRPERM.
This task changes ONLY profiling access to a one-off UID0 unit. It does not change the
kernel, driver permission setting, original miner capabilities or any persistent service.

Official access guidance: https://developer.nvidia.com/ERR_NVGPUCTRPERM
NVIDIA documents root/CAP_SYS_ADMIN as a supported way to obtain counter access. This is a
separate authorized approach after the prior temporary CAP_PERFMON-only attempt failed;
success/driver-tool compatibility is NOT guaranteed. No automatic retries or tool upgrades.
CLI reference: https://docs.nvidia.com/nsight-compute/NsightComputeCli/index.html

## New entry and checks

Use tools/root_counter_profile.py, NOT diagnose_compute.py --kind counters as UID0 (the old
entry intentionally rejects UID0). New entry has only preflight/collect actions, a NEW output
directory and original stopped PID/start ticks. There is NO arbitrary executable, GPU, power,
command, duration or profiler-arguments interface. It fixes:

- GPU-14cc341d-41f4-a977-1a1d-12785f4079da (the Mint4090), PL310.
- The existing ncu binary SHA f2a737629d325c771b9564113088fc144ad182cf9ebc8847dc0b6d565dcb6274.
- The existing engine SHA 3e935b1171b3e925db9aeadd901564eaa3d4500bcb19a29dd2aa50df40e5f7c1.
- SHA256s of the complete project Python import closure, checked BEFORE those imports.
- Root-owned/non-group/other-writable code/interpreter/binary/path components, ordinary files
  without setuid/setgid/file capabilities, isolated Python -I and sanitized loader/Python env.
- UID0/GID0, exactly CAP_SYS_ADMIN in all five sets, NoNewPrivs1, AT_SECURE0. Other scopes fail.
- Output only in a NEW direct root-owned0700 child of /var/lib/pearl-root-counter-profile.
- One fixed counter_command, 30s child timeout, original paused identity and310W guarded during
  execution. Full raw output retained on failure; actual metrics/completion/report required.

All native/algorithm/miner/proof files unchanged from696a8eb/f1e31c0; reuse the exact trusted
engine, no build required.91 CPU tests passed: privilege scope refusals, import closure pinning,
restricted CLI/output and existing counter-output validation. No root profiling executed here.

## One local Codex task

Only room-room@192.168.1.98 / Mint4090. Keep PL310W, core lock2600/current2610, offset+300,
mem405, both fans55, wallet/pool/config/API/driver/autostart unchanged. No3060/Hive. Existing
mining-pause authorization covers one attempt<=90s; profile command<=30s, no live mining test.
The profiling unit's root access is explicitly part of this task; keep every other service's
privileges unchanged. No global driver permissions, sudoers, setcap, groups or permanent units.

1. BEFORE PAUSE: new pinned checkout/checksums. Inspect root_counter_profile.py and verify
   native/kernel/filter/noise/proof files match696a8eb. Preserve prior evidence. Existing
   ncu and engine must match fixed hashes above. No installs/downloads/rebuilds. Resolve
   actual paths; the prior read-only /opt/pearl-counter-lab copy can supply the exact engine.
2. Prepare a NEW root-owned frozen tree (e.g. /opt/pearl-root-counter-lab/<unique-id>) containing
   root_counter_profile.py, its five pinned tools dependencies and build/pearl-bench. All
   parents root-owned/non-group/other-writable, files0444/0555/directories0555. Verify each
   copied SHA against this revision; the dependency hash dict is literal and must not be
   changed. Create /var/lib/pearl-root-counter-profile as a real root-owned0700 directory.
   Controller/snapshots remain in their existing private root location. No file capabilities.
3. Prepare the existing ROOT controller with the established pidfd/start-ticks, operation
   lock, all-thread-T, GPU idle/unique compute, exact protected identity/settings/capability
   snapshots, external watchdog and cgroup cleanup-before-resume. Modify ONLY the single
   transient profiler unit to:

       User=0, Group=0
       CapabilityBoundingSet=CAP_SYS_ADMIN
       AmbientCapabilities=CAP_SYS_ADMIN
       NoNewPrivileges=yes
       RuntimeMaxSec=60, KillMode=control-group, TimeoutStopSec=2, UMask=0077
       WorkingDirectory=<new-root-owned-frozen-tree>

   Execute ONLY /usr/bin/python3 -I <trusted-tools>/root_counter_profile.py directly.
   DO NOT execute the old UID1000/user-writable runner or repository as root. Clear
   LD_PRELOAD/LD_AUDIT/LD_LIBRARY_PATH/PYTHONPATH/PYTHONHOME/PYTHONSTARTUP/PYTHONINSPECT;
   use PATH=/usr/sbin:/usr/bin:/sbin:/bin, PYTHONDONTWRITEBYTECODE=1. Keep the original process,
   SSH and panel capabilities unchanged. The root SYS_ADMIN scope exists only for this unit
   and its fixed diagnostic descendants; the root controller separately retains recovery.
4. BEFORE PAUSE run in the exact root security context above:

       /usr/bin/python3 -I <trusted-tools>/root_counter_profile.py preflight
         --out /var/lib/pearl-root-counter-profile/<unique-preflight>

   Require passed=true, valid root_scope UID0/GID0/AT_SECURE0/NoNewPrivs1, all five capability
   masks0000000000200000, pinned hashes, expected engine help/ncu version. Capture unit
   properties including ambient/bounding sets and child status. This executes only --version
   and --help, not CUDA kernels. Probe unit/cgroup must end empty before collection setup.
   Any preparation failure: NO pause; retain exact failure, do not silently broaden privilege.
5. Snapshot fresh baseline ~333TH/s and CURRENT original PID/start ticks/settings/files/
   capabilities. Do not hardcode historical PID4158372. Arm independent watchdog75s BEFORE
   SIGSTOP; whole profile cgroup RuntimeMax60s, hard pause90s, command internal timeout30s.
   Stop exact original pidfd, confirm all threadsT and GPU idle/no other compute. SAME
   transient security context/frozen paths/environment, ONE root collection:

       /usr/bin/python3 -I <trusted-tools>/root_counter_profile.py collect
         --out /var/lib/pearl-root-counter-profile/<unique-collection>
         --paused-pid <CURRENT-PID> --paused-start-ticks <CURRENT-TICKS>

   No ordinary user runner between controller and root entry. Fixed scalar384/stage64,
   three warm pairs then ONE profile pair; ncu skip6/count2, fixed five sections, clock-control
   none/cache-control none. No timing/Sanitizer/ABBA/fixtures/full mining/candidate/noise replay.
   Require exit0, nonempty hardware.ncu-rep, actual GEMM+filter metric rows, native completion
   and verified result.json. Export full raw stdout/stderr/CSV/report. Error/timeout/missing
   counters: restore and stop; no second run or alternate flags/settings/tool installation.
6. EVERY exit: kill/reap the entire ROOT experiment cgroup and prove empty BEFORE SIGCONT;
   terminate any diagnostic descendants regardless of process group. Resume SAME original
   miner; prove unique process, exact argv/env/exe/cwd/protected files and capabilities,
   unchanged settings, fresh CURRENT GPU0/API ~333TH/s and new work/share evidence with
   sustained samples. Root profiler processes must not remain. Disarm watchdog only after
   strict recovery. All transient units inactive; no permanent privileges created.
7. Return REPORT-ROOT-HARDWARE-PROFILE-4090.md, root preflight/unit capabilities, complete
   raw profiler stdout/stderr/CSV/.ncu-rep or exact failure, fixed-command/prelaunch/result,
   pause/recovery proof and before/after original capabilities. Root outputs must be copied
   to user evidence via the trusted export path after collection, preserving originals.
   If successful, interpret named issue/warp/SM/tensor/memory/stall/occupancy metrics and rank
   ONE next kernel change. Replay timing is not a mining benchmark or SRBMiner-equivalent
   hashrate. No new optimization/test in this task. If failed, preserve unknown fields as null.
