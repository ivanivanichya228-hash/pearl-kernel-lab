# One transient PERFMON-only hardware profile, unchanged scalar384

Current goal: real hashing faster than SRBMiner at the same310W. No speedup established.
Last event diagnosis: GEMM4.0765275ms, compact filter0.137777ms;96.73073%/3.26927% of those
TWO RESIDENT phases only. Do not replay that diagnosis or equate it with full mining time.
Hardware stalls/issue/memory limits remain unmeasured because prior instructions prohibited
profiling privileges. This task addresses that blocker without modifying driver permissions.

## Implemented change

New tools/counter_access.py verifies a specific transient Linux scope: UID1000; exactly
CAP_PERFMON(bit38) in inheritable/permitted/effective/bounding/ambient sets; NoNewPrivs1;
AT_SECURE0 with a complete auxv; NVIDIA driver major>=565. Unknown driver or extra/missing
capabilities fail. This is read-only/no GPU work, NOT a privilege-granting or sudo helper.

New tools/counter_scope_probe.py checks that scope, an exec-child inheriting the same scope,
root-owned/non-writable code/interpreter/executables/path components, no setuid/setgid/file
capabilities, fixed executable SHA256s and profiler --version. It rejects injected Python/
loader environment. Run it inside the exact candidate transient security context BEFORE
stopping mining. Successful probe is not proof that GPU profiling will work.

The existing diagnose_compute.py now permits admin-restricted counter collection only when
that scope is actually verified; UID0 counter collection is rejected. The unrestricted
UID1000 path is unchanged. Use Python -I and a root-owned trusted source copy for this scope.
All GPU compute/filter/noise/proof/worker sources and compiled engine stay unchanged from
f1e31c0. Source compilation is unnecessary if the exact previously built binary is retained.
Only the profiling unit and its diagnostic descendants inherit PERFMON. Original SRBMiner,
panel, SSH session and permanent services receive no new capabilities.

Official primary references:
https://developer.nvidia.com/ERR_NVGPUCTRPERM
NVIDIA documents CAP_PERFMON support from R565 and the secure-execution caveat. The reported
rig driver595.99.02 meets the documented version condition; actual collection remains unproven.
https://docs.nvidia.com/nsight-compute/NsightComputeCli/index.html
Use --clock-control none/--cache-control none; one matched GEMM and one compact filter only.

85 CPU tests passed including exact/extra/dropped capabilities, wrong UID/driver, secure-exec,
malformed auxv, missing scope and environment/path refusal. No elevated scope or GPU profiling
executed here. The fixed installed ncu2022.4.1 may still encounter driver/tool incompatibility;
that is not assumed away by a successful privilege probe. No automatic fallback/retry/upgrade.

## ONE local Codex task

Only Mint4090 room-room@192.168.1.98. PL310W, core lock2600/current2610, offset+300, memory405,
both fans fixed55%; original pool/wallet/profile/API/autostart/driver unchanged. No3060/Hive.
One pause<=90s, one hardware collection<=30s; no long live run or optimization in this task.
Current work is step3 hardware diagnosis; step4 CPU checks done; step5 one bounded measurement.

1. BEFORE PAUSE while SRBMiner continues: obtain this pinned revision, verify checksums and
   unchanged src/kernel.cu/filter.cu/noise.cu/pipeline.cu/proof sources against f1e31c0. Preserve
   prior artifacts. Locate the previously compiled sm89 engine, SHA256:
   3e935b1171b3e925db9aeadd901564eaa3d4500bcb19a29dd2aa50df40e5f7c1
   Existing ncu /usr/lib/nsight-compute/ncu, SHA256:
   f2a737629d325c771b9564113088fc144ad182cf9ebc8847dc0b6d565dcb6274
   Resolve real paths and verify owner/modes/hashes. If missing/different, report BEFORE pause;
   do not install anything or use a different binary without reviewing the discrepancy.
2. Prepare the already-authorized root-owned recovery controller and ONE separate transient
   profiling-unit scope. Use existing sudo mechanism. Freeze a minimal verified diagnostic
   tools dependency tree plus the exact engine in a separate root-owned read-only directory
   with root-owned, non-group/other-writable traversable parents. UID1000 must be able to read
   code/execute the engine; output is a NEW UID1000-owned0700 directory. Do not place trusted
   code beneath a writable home/tmp parent. Keep controller/private snapshots root0700/0600.
   No user-writable code, PYTHONPATH/PYTHONHOME, LD_PRELOAD or LD_AUDIT in the privileged scope.
   Use /usr/bin/python3 -I; module imports must resolve to that trusted copy or system stdlib.
   The root controller grants ONLY this transient profile service:

       User=1000, Group=1000
       CapabilityBoundingSet=CAP_PERFMON
       AmbientCapabilities=CAP_PERFMON
       NoNewPrivileges=yes
       KillMode=control-group, TimeoutStopSec=2, RuntimeMaxSec=60, UMask=0077

   Preserve existing pidfd/start-ticks, operation lock, all-thread-T, idle/no-other-compute,
   exact identity/files/settings, selected UUID, cgroup cleanup and recovery protections.
   No CAP_SYS_ADMIN, permanent setcap/sudoers/groups/module/device permission changes, root
   CUDA execution, driver reload/reboot or broadening another service's privileges.
3. BEFORE PAUSE run the INERT probe in that exact transient security configuration; no GPU:

       /usr/bin/python3 -I <trusted-tools>/counter_scope_probe.py
         --ncu <verified-root-owned-ncu> --engine <trusted-engine>
         --expected-ncu-sha256 f2a737629d325c771b9564113088fc144ad182cf9ebc8847dc0b6d565dcb6274
         --expected-engine-sha256 3e935b1171b3e925db9aeadd901564eaa3d4500bcb19a29dd2aa50df40e5f7c1

   Retain full JSON/exit status. Require passed=true, both runner/exec-child scopes valid,
   UID1000, all five capability fields exactly0000004000000000, NoNewPrivs1, AT_SECURE0,
   driver>=565 and executable hashes. Capture systemctl properties including BOTH ambient
   and bounding capabilities. Ensure probe unit/cgroup terminated/empty. Only then prepare
   identical properties/paths/env for the collection. If the probe fails: NO mining pause,
   retain evidence and report the exact failure. Do not work around it with UID0/SYS_ADMIN.
4. One short pause, same trusted controller: snapshot fresh ~333TH/s baseline/current PID,
   protected settings/files and ORIGINAL capabilities. Do not hardcode historical PID4158372.
   Arm independent watchdog75s BEFORE SIGSTOP; experiment cgroup RuntimeMax60s; total90s hard
   pause bound. Stop exact original pidfd, prove all threadsT and no other GPU compute.
5. SAME paused session and validated PERFMON-only unit, ONE command (30s internal timeout):

       /usr/bin/python3 -I <trusted-tools>/diagnose_compute.py --run-gpu --kind counters
         --ncu <verified-root-owned-ncu> --engine <trusted-engine>
         --out <NEW-private-counter-output> --gpu <exact-UUID>
         --expected-power-limit-w 310 --paused-pid <PID> --paused-start-ticks <TICKS>

   Do NOT run kind timing, sanitizer, ABBA, fixtures, new candidate or live pool. The native
   kernel-counters runs three warm pairs then ONE profile pair; ncu skip6/count2, scalar384/
   stage64, matrix_loads=false. Fixed SpeedOfLight/Occupancy/SchedulerStats/WarpStateStats/
   MemoryWorkloadAnalysis sections; clock-control none/cache-control none. No clock reset,
   boost/cache tuning, transfer overlap, synthetic submission or deadline extension.
   Require exit0, raw CSV with actual GEMM and compact-filter metrics, nonempty hardware.ncu-rep,
   counter_targets_completed record and verified output. ERR_NVGPUCTRPERM, missing metrics,
   incompatibility or timeout is FAILURE: retain complete output and restore, no second try.
6. EVERY exit: terminate/reap ENTIRE profile cgroup and prove empty BEFORE SIGCONT. Resume
   SAME original process; unique miner, exact protected files/settings/capabilities unchanged,
   fresh CURRENT GPU0/API ~333TH/s, new job/share evidence and sustained samples. Disarm
   watchdog only after strict recovery; all transient profiling units inactive and no
   diagnostic process retains PERFMON. Do not change any global capability/driver setting.
7. Return REPORT-HARDWARE-COUNTERS-4090.md, inert probe JSON, captured unit capabilities,
   complete profiler stdout/stderr/raw CSV and .ncu-rep, child status/exit, exact pause and
   recovery evidence. Interpret named metrics for: eligible/active warps and issue rate,
   SM/tensor throughput, DRAM/L2/shared traffic/throughput, dominant warp stalls and occupancy
   limits. Distinguish metric observations from causal hypotheses. Rank ONE next kernel
   change supported by data; do not implement or rerun it during this task. Instrumented
   replay timing is not a hashrate result and one profile is not proof of SRBMiner advantage.
