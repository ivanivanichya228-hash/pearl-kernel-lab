# Adapter for the EXISTING home recovery controller

Do not introduce a second stop/resume mechanism. Reuse the tested root-owned pidfd/start-ticks
controller and its watchdog/cgroup-empty-before-SIGCONT/strict-recovery checks from the
successful triple-stage test. Do not execute user-writable scripts as root.

Preparation (no mining pause): audit issue_session.py, copy it into the existing protected
root-owned controller tree, freeze/hash it, and import that trusted copy from the controller.
Create /run/pearl-test-sessions as root:0711, without changing an existing directory's rights.
If that path already exists, require a real root-owned non-group/other-writable traversable
directory. Session data contains only process identity/deadline/unit names, no wallet or key.

After watchdog590s is armed, the exact original pidfd is stopped, all threadsT and GPU idle
are confirmed, issue a receipt using the values ALREADY held in the root controller:

    session_path = issue_session(
        original_pid=original_pid,
        original_start_ticks=original_start_ticks,
        gpu_uuid='GPU-14cc341d-41f4-a977-1a1d-12785f4079da',
        power_limit_w=310,
        pause_started_monotonic=pause_started_monotonic,
        deadline_monotonic=experiment_deadline_monotonic,
        cgroup_path='/system.slice/'+experiment_unit+'.service',
        watchdog_unit=watchdog_timer_unit,
    )

The original pause bound remains600s. The original experiment-unit limit remains555s;
receipt deadline must not exceed the unit/operation deadline. Each pilot duration<=420s,
plus20s remaining margin. Do not fabricate identity or use stale PID4158372. The cgroup
must be known before starting its GPU client; the receipt may be issued with that known
unit name before systemd-run starts it. Watchdog must already be active.

In that SAME experiment cgroup use User/Group1000, NoNewPrivileges=yes, all capability sets
EMPTY, KillMode=control-group, bounded runtime, controlled environment and selected GPU.
The sole client command becomes:

    /ABSOLUTE/PACKAGE/pearl-test run --config /PRIVATE/config.json \
      --session /ROOT-ISSUED/session.json --state /NEW/PRIVATE/run-id \
      --ram-dir /VALIDATED/PRIVATE/tmpfs --duration 420

The launcher checks cgroup-v2 membership and active watchdog, fixed GPU/310W, controller
identity/deadline, unprivileged execution and all package hashes. It invokes the exact
triple384 persistent pipeline with original full profile and submit enabled. On Ctrl+C/
SIGTERM, client failure, expired session or disabled watchdog it closes/reaps its backend.
The OUTER controller must still kill/reap the ENTIRE experiment cgroup and prove empty
before resuming SRBMiner, including descendants that may have detached process groups.

Preserve existing root snapshots, protected-file/capability checks, unique compute guard,
private tmpfs validation/cleanup, current-GPU0/API sustained recovery and new-work/share
confirmation. The launcher does not own SRBMiner pidfd and never calls SIGSTOP/SIGCONT.
Delete/revoke only this issued session file after cleanup/recovery. Keep private logs/proofs.
Do not install an unrestricted sudo helper or replace the validated controller with this
receipt writer: issue_session.py deliberately has no service, process or GPU control API.

During the PACKAGE PREPARATION task do not issue a live receipt, pause mining or run this
GPU command. First install/configure/verify only; actual pilot uses separate authorization.
