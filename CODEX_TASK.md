CURRENT: [TWO-CTA-KERNEL.md](TWO-CTA-KERNEL.md), revision0.19.0. NEW128x128/256 computational kernel,107 registers,45056/49152 dynamic shared bytes,zero spills. Goal>=2resident CTAs; GPU speed not measured. One bounded correctness/short comparison then conditional live test. Earlier tasks below are historical.

CURRENT TASK: [ROOT-HARDWARE-PROFILE.md](ROOT-HARDWARE-PROFILE.md), revision0.18.0. One fixed root profiler entry; root-owned frozen code, pinned binaries/GPU, transient SYS_ADMIN-only unit. Preflight BEFORE pause. No new kernel or long test. Earlier tasks below are historical.

CURRENT TASK: [HARDWARE-COUNTERS.md](HARDWARE-COUNTERS.md), revision0.17.0. One transient PERFMON-only profile, UID1000. Inert capability/exec probe BEFORE any mining pause. No new kernel, no timing replay, no permanent privileges. Earlier tasks below are historical.

CURRENT: [COMPUTE-DIAGNOSIS.md](COMPUTE-DIAGNOSIS.md). Diagnostic revision0.16.0, unchanged scalar384 compute/filter. Previous ldmatrix was rejected; no faster-than-SRB result. Only one short phase/counter measurement, no long mining test. Earlier tasks below are historical.

> CURRENT TASK: [LDMATRIX.md](LDMATRIX.md), revision0.15.0. All tasks below are historical. One bounded Mint4090 test only, scalar384 vs collective384, no transfer overlap. No SRBMiner advantage established.

> Revision0.5.0: [LUCKYPOOL-ADAPTER.md](LUCKYPOOL-ADAPTER.md): real-job offline adapter and new GPU hash filter. CPU tests passed; new GPU stage not tested. Older tasks are historical.

> Revision0.4.0: [PROOF-COMPATIBILITY-4090.md](PROOF-COMPATIBILITY-4090.md). Official plain-proof CPU bridge passed; new GPU fixture comparison pending. Previous tasks are historical.

> Revision0.3.3: follow [ISOLATED-SANITIZER-4090.md](ISOLATED-SANITIZER-4090.md). Use pinned standalone sanitizer; old installed-tool tasks are historical.

> Revision 0.3.2: fix installed sanitizer discovery first, following [REPAIR-SANITIZER-4090.md](REPAIR-SANITIZER-4090.md). No mining pause/GPU workload for this repair.

> Revision 0.3.1: follow [VALIDATE-STAGE64-4090.md](VALIDATE-STAGE64-4090.md). It supersedes previous test tasks; kernel unchanged, stronger validation only.

> Revision 0.3.0: [STAGE64-4090.md](STAGE64-4090.md) supersedes previous experiment instructions. New candidate is 256 threads / stage-k 64; rebuild required. No measured speedup yet.

> Revision 0.2.0: follow [NEXT-4090.md](NEXT-4090.md). It supersedes the old comparison and binary instructions below. Preserve the validated local recovery and paused-process guards.

# Первый тест: только RTX 4090 на Linux Mint

Клонируй этот репозиторий в отдельный каталог, вне mining-panel и установленного SRBMiner. Прочитай README.md и STATUS.json. Цель — проверить новое математическое CUDA-ядро и сравнить наши версии на 256/512 потоков. Не объявляй matrix_TOPS хешрейтом Pearl и не устанавливай экспериментальное ядро в рабочий майнер.

## Где выполнять

CUDA-тесты ТОЛЬКО на Mint-риге с RTX 4090 из существующего SSH-профиля панели. Сам профиль и ключи не менять. Перед запуском проверь hostname, Linux Mint, модель и UUID GPU. На сервере панели разрешены подготовка, сборка и CPU-проверки. Локальную RTX 3060 и Hive OS не использовать для CUDA-нагрузки.

## Power limit и настройки

1. Прочитай фактический PL выбранной 4090 через nvidia-smi/NVML и сверь с сохранённым профилем панели. При расхождении сообщи его; не исправляй автоматически. Не подставляй значения из переписки или лимит другой карты.
2. Все проверки и сравнения выполнять при ЭТОМ неизменном PL. Не менять лимит, частоты, напряжение, вентиляторы, драйвер, GPU-профиль, пул, кошелёк или постоянную конфигурацию майнера.
3. GPU-стенд запускать через `tools/test_4090_mint.py` с явно переданным `--expected-power-limit-w`, равным подтверждённому текущему значению. Скрипт проверяет модель и PL до старта, во время исполнения и после; при изменении лимита останавливает только свой тестовый процесс. Эта проверка не устанавливает PL.
4. Отдельно фиксировать фактические средние/пиковые ватты и частоты. Не считать прежний PL доказательством прежнего потребления.

## Подготовка без паузы майнинга

- Проверь CHECKSUMS.sha256, выполни `make cpu-check` и `python3 tests/test_guard.py`. При наличии NumPy также `python3 tests/test_layout.py`.
- Попробуй `bin/pearl-bench-linux-x86_64 --help` без GPU-флагов. Если готовый executable несовместим, собери из исходников через tools/build.py; при отсутствии nvcc допускается его изолированная загрузка через `--download-toolchain`. Не устанавливай и не обновляй драйверы. Все зависимости и сборку подготовь ДО паузы майнинга.
- Если доступ или установка зависимостей заблокированы политикой среды, не обходи ограничение. Сохрани конкретную причину.

## Обязательное восстановление майнинга

Подготовь восстановление ДО остановки. Определи существующую управляемую службу/механизм запуска именно этого майнера и запомни, был ли он активен. Сохрани идентичность запуска и профиль приватно, без вывода кошельков, токенов и полной командной строки. Убедись, что существующий запуск доступен для возврата и остановка майнера не выключает контроллер разгона/вентиляторов и не сбрасывает PL. Не используй копию /proc/PID/exe и не создавай новую команду запуска из предположений.

Предусмотри независимый от тестового процесса одноразовый watchdog возврата через доступный штатный механизм, а также возврат в `finally`/обработчике завершения. Watchdog должен восстановить исходную службу, только если она изначально работала; повторный старт должен быть идемпотентным и не создавать второй экземпляр. Не менять постоянное enable/disable службы. Если надёжный возврат подготовить нельзя, рабочий майнер не останавливай.

Для чистого замера допускается короткая контролируемая пауза ТОЛЬКО майнера этой Mint-4090. Не останавливай службу OC/AutoFan. Целевое окно паузы — не более 90 секунд, включая восстановление; при проблемах приоритет у возврата майнинга, а не у продолжения измерений. Сначала проверь, что фактический PL после освобождения GPU остался прежним. Если нет — тест не запускай и верни исходный запуск.

Не измеряй скорость одновременно со SRBMiner. Не используй `--allow-concurrent-miner` для сравнения производительности. Если на этом же ПК работает посторонняя GPU-нагрузка, не останавливай её произвольно и не выдавай замер за чистый.

## GPU-проверка

После подготовки watchdog и освобождения GPU запусти guarded `--mode bench --duration 1` с явным UUID и ожидаемым PL. Этот режим сначала проверяет все шесть fixtures для 256/512 потоков, сравнивает каждый элемент матрицы и все слова transcript, затем сверяет две версии на benchmark-матрице и выполняет A/B/B/A. При любой ошибке correctness/CUDA/PL/тайм-ауте прекрати тест и переходи к восстановлению.

Пример структуры команды, с ФАКТИЧЕСКИ прочитанными значениями вместо заполнителей:

```bash
python3 tools/test_4090_mint.py --run-gpu --mode bench --gpu GPU-UUID --expected-power-limit-w CURRENT_WATTS --duration 1 --timeout-sec 60
```

Сохрани stdout/stderr в `GPU-RESULT-4090-MINT.jsonl`. Если тест требует исправления, исправляй только изолированную лабораторию; перед повтором верни рабочий майнинг и не продлевай паузу серией неограниченных попыток.

## Возврат и отчёт

При успехе, ошибке и тайм-ауте обязательно восстанови ТОТ ЖЕ прежний майнер через существующий механизм, если он работал до теста. Не меняй его версию, параметры, окружение, пул или кошелёк. Проверь активность, отсутствие дубликатов, прежний PL и свежий положительный хешрейт в доступном API/журнале. Дальнейшее появление принятой шары — дополнительное подтверждение; не называй его проверенным, если не наблюдал. Watchdog убирай только после подтверждения восстановления. Если восстановление не подтверждено, прямо укажи это первым пунктом отчёта.

Сохрани `TEST-RESULT-4090-MINT.md`: идентичность карты без секретов; PL до/во время/после; correctness; median_ms и matrix_TOPS; соотношение 512/256; фактические ватты/температуры/частоты; длительность паузы; подтверждение возврата майнинга. Baseline — наша 256-поточная версия, а не SRBMiner. До полного proof/pool pipeline не обещать прирост дохода или хешрейта Pearl.
