> Revision0.4.0: [PROOF-COMPATIBILITY-4090.md](PROOF-COMPATIBILITY-4090.md). Official plain-proof CPU bridge passed; new GPU fixture comparison pending. Previous tasks are historical.

> Revision0.3.3: follow [ISOLATED-SANITIZER-4090.md](ISOLATED-SANITIZER-4090.md). Use pinned standalone sanitizer; old installed-tool tasks are historical.

> Revision 0.3.2: fix installed sanitizer discovery first, following [REPAIR-SANITIZER-4090.md](REPAIR-SANITIZER-4090.md). No mining pause/GPU workload for this repair.

> Revision 0.3.1: follow [VALIDATE-STAGE64-4090.md](VALIDATE-STAGE64-4090.md). It supersedes previous test tasks; kernel unchanged, stronger validation only.

> Revision 0.3.0: [STAGE64-4090.md](STAGE64-4090.md) supersedes previous experiment instructions. New candidate is 256 threads / stage-k 64; rebuild required. No measured speedup yet.

> Revision 0.2.0: follow [NEXT-4090.md](NEXT-4090.md). It supersedes the old comparison and binary instructions below. Preserve the validated local recovery and paused-process guards.

# Задание для Codex

Выполни [CODEX_TASK.md](CODEX_TASK.md). Только Mint-риг с RTX 4090 и её подтверждённый текущий power limit. Прежде чем приостанавливать майнер, подготовь надёжное восстановление его прежнего запуска. В конце обязательно проверь возвращение хешрейта.
