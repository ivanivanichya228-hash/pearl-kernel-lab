CURRENT RELEASE: **0.5.0-fixed-shape** — [FIXED-SHAPE.md](FIXED-SHAPE.md). New fixed-K4096/rank256 interior CUDA kernel with explicit safe edge fallback. Same-ELF0.4.0 control; automatic12-fixture/ABBA gate before conditional420s live test.139CPU tests pass; GPU gain unmeasured. Only this task is active; older tasks below are historical.

CURRENT RELEASE: **0.4.0-singlepass-transcript** — [SINGLEPASS-KERNEL.md](SINGLEPASS-KERNEL.md). Actual CUDA transcript specialization for16checkpoints. Original fused control in the same ELF; automatic short correctness/speed gate before a conditional420s live run. No new GPU speedup measured. Only this task is active; all tasks below are historical.

CURRENT RELEASE: **0.3.0-mapped-input** — [MAPPED-INPUT.md](MAPPED-INPUT.md). Ready archive in dist; fresh raw operands generated directly in shared tmpfs. CPU preparation0.487374→0.354845s (−27.19%,4threads), original verifier preserved. GPU throughput/real-pool acceptance of this release untested. Only this task is active; all tasks below are historical and must not be rerun.

CURRENT: [TRIPLE-STAGE-KERNEL.md](TRIPLE-STAGE-KERNEL.md), revision0.20.0. Separate192x256/384 kernel,three swizzled64-wide stages for proof16;original scalar384 control unchanged.0spills,98CPU tests passed.GPU speed untested.One bounded correctness/shortgate then conditional live test.Earlier tasks historical.

CURRENT: [TWO-CTA-KERNEL.md](TWO-CTA-KERNEL.md), revision0.19.0. NEW128x128/256 computational kernel,107 registers,45056/49152 dynamic shared bytes,zero spills. Goal>=2resident CTAs; GPU speed not measured. One bounded correctness/short comparison then conditional live test. Earlier tasks below are historical.

CURRENT TASK: [ROOT-HARDWARE-PROFILE.md](ROOT-HARDWARE-PROFILE.md), revision0.18.0. One fixed root profiler entry; root-owned frozen code, pinned binaries/GPU, transient SYS_ADMIN-only unit. Preflight BEFORE pause. No new kernel or long test. Earlier tasks below are historical.

CURRENT TASK: [HARDWARE-COUNTERS.md](HARDWARE-COUNTERS.md), revision0.17.0. One transient PERFMON-only profile, UID1000. Inert capability/exec probe BEFORE any mining pause. No new kernel, no timing replay, no permanent privileges. Earlier tasks below are historical.

CURRENT: [COMPUTE-DIAGNOSIS.md](COMPUTE-DIAGNOSIS.md). Diagnostic revision0.16.0, unchanged scalar384 compute/filter. Previous ldmatrix was rejected; no faster-than-SRB result. Only one short phase/counter measurement, no long mining test. Earlier tasks below are historical.

Current revision **0.15.0**: [LDMATRIX.md](LDMATRIX.md). New collective matrix-load384 kernel, scalar384 control;168 registers, zero spills,71 CPU tests passed. New GPU validation pending. Previous pinned-transfer path was rejected on the rig (0.97853x); keep it OFF. No demonstrated advantage over SRBMiner. Use ONLY the current bounded task.

Historical revision notes follow.

Current revision **0.14.0**: [TRANSFER-OVERLAP.md](TRANSFER-OVERLAP.md). Explicit pinned two-slot transfer path, unchanged kernel384, bounded queued lifecycle. CUDA build and68 CPU checks pass; GPU execution pending. One short matched transport comparison gates any long live test. Default OFF.

Current revision **0.13.0**: [KERNEL384.md](KERNEL384.md). Actual192x256/384-thread GEMM candidate;166/167 registers, zero spills in SM86/89 build. CPU model passed. GPU performance untested. Default remains256; one short matched rejection comparison before any long live window.

Current revision **0.12.0**: [COMPACT-TRANSFER.md](COMPACT-TRANSFER.md). One compact GPU hit queue instead of per-slab host readbacks; native phase timings and persistent candidate evidence. CUDA compiled and CPU checks passed; new GPU path untested here. Use only this single current task.

Current revision **0.11.0**: [ROOT-PREPARE.md](ROOT-PREPARE.md). CPU root-only preparation and parallel fresh RNG; local full-profile preparation benchmark 4.08x, independent official roots/proofs passed. New rig throughput not measured. CUDA unchanged; do not repeat old GPU gates.

Earlier revision notes follow.

Current revision **0.10.0**: [GPU-NOISE.md](GPU-NOISE.md). Step3: CUDA noise implemented; full-array official CPU checks passed, real GPU validation pending. Raw matrices and Merkle remain CPU. No new hashrate claim.

The entries below describe historical revisions; use only the current task above.

Current implementation: [PIPELINE-REBUILD.md](PIPELINE-REBUILD.md). Steps1–2 implemented/local-tested: persistent worker, reusable buffers, mapped RAM work and overlapped CPU preparation. New GPU path untested; no measured speedup.

Next measurement: [RATE-STABILITY.md](RATE-STABILITY.md) — candidates/s and full-cycle costs, one bounded540s Mint4090 window. First real share accepted; no SRBMiner speedup claim.

Latest: forced disk sync removed for disposable work; [ACCEPTANCE-TEST.md](ACCEPTANCE-TEST.md) prepares one bounded test up to first accepted share. Extended pause requires user approval; no automatic GPU run.

Current fix: [PREPARE-FIX.md](PREPARE-FIX.md). CPU preparation optimized and batch logs preserved. No accepted real share; do not rerun the old30s GPU task.

Current runnable alpha: [LIVE-MINER.md](LIVE-MINER.md). Network/job/GPU/proof/submit loop implemented; local integration passed. New GPU scheduler and real-pool acceptance remain untested. No SRBMiner speedup claim.

Current stage: [BATCH-PIPELINE.md](BATCH-PIPELINE.md) — offline batch → GPU hit indices → official plain proof. GPU pipeline passed on Mint4090; both actual GPU-derived proofs passed the official verifier and synthetic target. See pool/GPU-PIPELINE-RESULT.json. No live share sent.

> Revision0.5.0: [LUCKYPOOL-ADAPTER.md](LUCKYPOOL-ADAPTER.md): real-job offline adapter and new GPU hash filter. CPU tests passed; new GPU stage not tested. Older tasks are historical.

> Revision0.4.0: [PROOF-COMPATIBILITY-4090.md](PROOF-COMPATIBILITY-4090.md). Official plain-proof CPU bridge passed; new GPU fixture comparison pending. Previous tasks are historical.

> Revision0.3.3: follow [ISOLATED-SANITIZER-4090.md](ISOLATED-SANITIZER-4090.md). Use pinned standalone sanitizer; old installed-tool tasks are historical.

> Revision 0.3.2: fix installed sanitizer discovery first, following [REPAIR-SANITIZER-4090.md](REPAIR-SANITIZER-4090.md). No mining pause/GPU workload for this repair.

> Revision 0.3.1: follow [VALIDATE-STAGE64-4090.md](VALIDATE-STAGE64-4090.md). It supersedes previous test tasks; kernel unchanged, stronger validation only.

> Revision 0.3.0: [STAGE64-4090.md](STAGE64-4090.md) supersedes previous experiment instructions. New candidate is 256 threads / stage-k 64; rebuild required. No measured speedup yet.

# Compact revision 0.2.0

New 128-thread 64x128 candidate with register-resident transcripts. GPU validation pending.
Build from source; bundled `bin/` executable is legacy and must not be used for this revision.
Read [NEXT-4090.md](NEXT-4090.md) before any GPU work. Existing mining must be restored using the verified local watchdog procedure.

# Pearl INT8 kernel experiment 0.1.1

Написано новое CUDA-ядро и собран отдельный стенд для первой проверки на RTX 3060 / RTX 4090. Рабочие майнеры и панель не изменялись.

**Это математическое ядро для тестов. Оно ещё не является самостоятельным майнером или заменой SRBMiner.** Реальный выигрыш хешрейта и сохранение фактических ватт не измерены. Успешная компиляция и CPU-проверки не означают, что CUDA-вычисление уже проверено на карте.

## Полученные результаты сборки

CUDA compiler 13.0.88, обе архитектуры SM86 и SM89:

| Вариант | Proof tile | Регистры/поток | Stack | Spills | Динамическая shared/блок |
|---|---|---:|---:|---:|---:|
| 512 потоков | 16×16 | **126** | **0** | **0** | **61 440 байт (60 КиБ)** |
| 512 потоков | 16×8 | 128 | 0 | 0 | 73 728 байт (72 КиБ) |
| 256 потоков, контрольная реализация | 16×16 | 238 | 0 | 0 | 61 440 байт |
| 256 потоков, контрольная реализация | 16×8 | 238 | 0 | 0 | 73 728 байт |

Компилятор действительно уложил 512-поточную версию в целевой бюджет ≤128 регистров без выгрузок в local memory. Это подтверждённый результат компиляции, а не прогноз скорости. В найденных ранее SRBMiner srb_c0 было 255 регистров; сравнение этих ресурсов НЕ является сравнением хешрейта или всего пайплайна майнера.

При 512 потоках ресурсный потолок — 16 варпов/SM вместо 8 у 256-поточного варианта. Загрузка SM, скрытие задержек и скорость должны определяться испытанием. Стенд дополнительно запросит фактический occupancy у CUDA на целевой карте.

## Что реализовано

- Собственный код, не патч проприетарного SRBMiner.
- Матричный рабочий tile 128×384; K обрабатывается шагами 32.
- Точные native Tensor Core `mma.sync.aligned.m16n8k32...s32.s8.s8.s32`.
- Предзагрузка следующего K-tile через `cp.async`, два буфера.
- Shared stride 48 байт вместо 32: CPU-модель 32 packed-word обращений даёт 32 разных банка. Это проверка раскладки, не профиль исполнения.
- INT32-накопления сохраняются между checkpoint. Входы уже должны содержать нужные значения после внешней подготовки.
- После каждых `rank` значений K: XOR uint32 накопленной матрицы выбранного proof tile; `transcript[(checkpoint-1)%16] = rotl13(old) XOR xor_tile`.
- Аппаратный warp XOR `redux.sync.xor`.
- Полный C не записывается в performance-режиме. В correctness-режиме сохраняется и сравнивается каждый элемент C, а также весь transcript.
- Две версии, 256 и 512 потоков, выполняют одинаковую математическую работу и сравниваются на одинаковых данных.

## Граница совместимости

API принимает `A[M,K]` и `BT[N,K]` row-major, тип **signed int8**. Формула: `C[u,v] += A[u,k]*BT[v,k]`. K ≤65536; INT32 достаточен даже для граничного signed INT8 произведения при этом K. Поддержаны proof tiles 16×8 и 16×16. M кратно 16, N кратно ширине proof tile; выход за границы рабочего tile обрабатывается нулями. Rank — степень двойки 32…1024, K кратно rank. Малые unit-test размеры не объявляются допустимыми параметрами сети Pearl.

Ядро НЕ генерирует шум, не выполняет commitments/Merkle, keyed BLAKE3, поиск target, построение/проверку сертификата или соединение с пулом. Важная граница: если результат upstream-подготовки выходит за [-128,127], его НЕЛЬЗЯ просто привести к int8. Сначала нужен точный packing/correction путь и его проверка. Не доказано, что выбранный здесь packing подходит всем текущим заданиям сети или U8-пути SRBMiner. Также не доказана совместимость с активным proof version / FP8.

Математический ориентир — зафиксированный открытый `compute_jackpot`; ссылка и SHA-256 в `tests/provenance.json`. Подготовка входов из этого источника пока не перенесена. Совпадение нашего transcript с CPU-эталоном не заменяет официальную проверку полного доказательства.

## Что уже проверено без GPU

1. Сборка CUDA для SM86/SM89, линковка Linux-стенда.
2. Аналитические C++-проверки положительных и отрицательных сумм, повторного обновления transcript после 16 checkpoint и неправильных параметров.
3. Все элементы C и все 16 слов каждого transcript совпали в шести независимых NumPy/C++ fixtures: нули, отрицательный единичный результат, случайные данные, края рабочего tile, разные rank, K=65536 и входы -128.
4. CPU-модель документированной PTX-раскладки операндов и C; однократное покрытие каждого элемента рабочего tile для 256/512 потоков; модель shared banks.
5. Исполнение `--help` и отказ без явного флага GPU.

**CUDA correctness, compute-sanitizer и GPU timing ещё не запускались.** Следующая проверка — `--mode check` на выделенной тестовой карте. До её успеха никаких выводов о производительности не делать.

## Готовый Linux-стенд

В `bin/pearl-bench-linux-x86_64` лежит собранный executable (SM86/SM89 + compute_86 PTX). Для него нужен Linux x86-64, glibc не ниже 2.38 и драйвер, совместимый с CUDA 13. Toolkit на целевом ПК для исполнения этой сборки не требуется. Версия системы/драйвера целевого ПК здесь не проверялась. Если бинарник не подходит по ABI, собирайте из исходников локально.

Без обращения к GPU:

```bash
./bin/pearl-bench-linux-x86_64 --help
make cpu-check
```

`make cpu-check` требует g++ и make, но не CUDA; fixtures уже включены. NumPy нужен только для их регенерации и CPU-модели PTX.

## Сборка без установки драйверов

Если nvcc уже установлен:

```bash
python3 tools/build.py
```

Если nvcc нет, скрипт может скачать проверенные по SHA-256 официальные компоненты компилятора в пользовательский cache. Это около 74 МБ сжатых пакетов. Он не устанавливает драйвер, не требует sudo и не запускает GPU-тесты:

```bash
python3 tools/build.py --download-toolchain
```

Нужны Python 3.9+, g++ и make. Пакеты зафиксированы в `tools/toolchain-lock.json`. Сборка создаёт `build/pearl-bench`. Скрипт не меняет пользовательский PATH, системные службы и другие проекты.

## Первый GPU-тест: только Mint RTX 4090 и текущий PL

Полное задание для Codex — [CODEX_TASK.md](CODEX_TASK.md). Оно включает обязательную подготовку восстановления прежнего майнинга при успехе, ошибке и тайм-ауте. На RTX 3060 и Hive OS GPU-тесты не запускать.

В версии 0.1.1 добавлен отдельный Python-ограничитель `tools/test_4090_mint.py`. Он допускает только Linux Mint и RTX 4090, выбирает GPU через UUID, требует явно указать текущий PL и проверяет его до, во время и после дочернего процесса. При изменении/невозможности чтения PL оставшаяся тестовая работа прекращается. Скрипт НЕ устанавливает PL и НЕ восстанавливает майнер: восстановление обязан подготовить Codex по CODEX_TASK.md до паузы.

Передача GPU UUID в CUDA_VISIBLE_DEVICES ограничивает выбор устройства только для дочернего процесса и не меняет настройки карты. Совпадение PL сверяется с фактическим значением выбранной карты, без подстановки исторических 100/310 Вт. Если сохранённый профиль и фактический лимит расходятся, автоматически ничего не исправлять.

Пример структуры команды после подготовки восстановления и чтения реальных UUID/PL:

```bash
python3 tools/test_4090_mint.py --run-gpu --mode bench --gpu GPU-UUID --expected-power-limit-w CURRENT_WATTS --duration 1 --timeout-sec 60
```

GPU-режим `bench` сначала проверяет все шесть fixtures для обеих версий, затем сравнивает их выходы на benchmark-матрице и выполняет A/B/B/A. Время измеряется CUDA Events с графом из 16 запусков. Результат — JSON Lines: GPU/PCI, correctness, median_ms, matrix_TOPS и телеметрия NVML. Matrix_TOPS — не хешрейт Pearl; baseline — наша 256-поточная версия, не SRBMiner.

NVML при наличии показывает средние/пиковые ватты, SM clock, температуру и лимит до/после. Неизменный PL не доказывает неизменное потребление. По умолчанию дочерний стенд отказывается исполнять GPU-нагрузку при видимом SRBMiner. Не использовать конкурентный режим для сравнений скорости.

Готовый CUDA executable и CUDA-ядро сохранены из проверенной сборки 0.1.0, без изменения математического кода. Изменения 0.1.1 — внешний Python-ограничитель и задание на тест. Ограничитель проверен четырьмя CPU-тестами; на GPU он ещё не запускался. Пакет не выдаётся за подтверждённую работающую сборку майнера.

## Интерпретация

- Несовпадение C/transcript: ядро исправляется до дальнейшего benchmark.
- 512 быстрее 256: подтверждено улучшение только нашей матричной реализации при указанных данных/условиях.
- 512 медленнее: расчёт occupancy не обеспечил ускорения; старый майнер сохраняется.
- Положительный microbenchmark при большей мощности: задача прежних ватт ещё не выполнена.
- Для перехода к майнингу нужны точная подготовка входов, соответствующая версия протокола, hash/certificate и официальный verifier. Затем отдельное end-to-end сравнение с SRBMiner при одинаковом задании и фактической мощности. Одного matrix_TOPS недостаточно.

Файлы `STATUS.json`, `evidence/build.log`, `evidence/resources.json` фиксируют только фактически выполненные здесь проверки. Лицензия собственного кода — MIT; лицензия включённого NVIDIA runtime — в `third_party/`.
