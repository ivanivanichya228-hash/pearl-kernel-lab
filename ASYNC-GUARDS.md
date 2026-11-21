# 0.2.1: проверки состояния без блокировки клиента

## Основание
В fused-live293batch ожидание GPU у клиента357.328730с, native wall320.321830с.
Разность37.006900с включает всю внешнюю обработку, НЕ только guard.
Успешные native prepare256.248667с; raw file writes141.648829с.
Интервалы CPU/GPU перекрываются, их нельзя складывать как последовательные задержки.

Синхронные nvidia-smi проверки находились внутри asyncio-потока перед каждой
JSON-строкой worker и во время ожидания CPU-процесса. Пока они выполнялись,
пул/подготовка/worker не могли обслуживаться тем же циклом.

## Изменение
AsyncGuardChecks выполняет ПРЕЖНЮЮ gpu_guard в одном фоновом потоке под общим lock.
Результаты не кешируются. Перед каждым GPU-запросом есть новая проверка.
При ожидании worker/CPU дольше0.2с проверка повторяется. Получение готовой JSON-строки
больше не запускает лишний blocking subprocess. Ошибка закрывает сеанс.
При отмене ограниченная активная проверка дожидается завершения, включая повторную
отмену; проверки не остаются вне жизненного цикла эксперимента. Прежний timeout
nvidia-smi3с, все процессы/потоки остаются в той же cgroup.
Исходная gpu_guard не изменена; AST до отключения среды совпал с прежней версией.
В performance.json добавлены guard_checks.calls/failed/execution_seconds/
queue_seconds/cancelled_and_drained. Эти времена не равны обещанному live-приросту.

Ядро, ELF engine, oracle и профиль прежние0.2.0. Никаких новых occupancy/two-CTA,
transfer-overlap, изменений CUDA или повторов старых microbenchmarks.
Root-контроллер, receipt, watchdog, восстановление не меняются.

## Проверка в среде разработки
До отключения среды прошли120 CPU-тестов: неблокирующий цикл, сериализация без кеша,
cancel/drain, запрет запроса при ошибке и завершение worker при ошибке проверки.
CPU-loopback проверил8уникальных proof официальным verifier:
6mock accepted/2намеренныхmock rejected. Это НЕ acceptance реального пула.
Пакет был собран и проверен на распаковку/конфиг/изменённый guard-модуль; ELF/oracle
побайтно совпали с0.2.0. GPU не запускался, прирост/310Вт не подтверждены.

Готовый архив: `dist/pearl-test-0.2.1-linux-x86_64.tar.gz`.
SHA256 `eaddaf639c7afb1a6cd89c48bff01a88342079db6068228adb19af827fb6828a`, размер3230596байт.
Исходники заново проверены:120 CPU-тестов прошли; repack_async.py успешно выполнен,
загрузка пакета и побайтное совпадение ELF/oracle с0.2.0 подтверждены без GPU.

## Задание домашнему Codex
На Mint4090 room-room@192.168.1.98 получи ЭТОТ коммит в отдельный checkout.
Скачай готовый архив из dist ЭТОГО ЖЕ коммита, проверь SHA256 и безопасные пути,
распакуй в НОВЫЙ каталог. Ничего не компилируй, зависимости/драйверы не устанавливай.
До паузы выполни ./pearl-test version и ./pearl-test verify.
Нужна версия0.2.1-fused-async. При несовпадении хешей/версии тест не начинать.
Скрипт release/repack_async.py оставлен для воспроизводимой упаковки разработчиком;
при наличии готового архива выполнять его на риге не нужно.

Импортируй прошлый приватный конфиг, сохрани host/port/wallet/worker,config0600;
полный профиль тот же, секреты не выводи. Подготовь новый одноразовый экземпляр
ПРЕЖНЕГО короткого контроллера с новыми путями/хешами. Не переписывай его
pidfd/start ticks/operation lock/stop/resume/recovery. Root-код только в закрытой
root-копии. Sudoers/права драйвера/постоянные службы не менять.

Один контрольный live-сеанс180с для оценки клиентского планирования:

    /NEW_PACKAGE/pearl-test run --config /NEW_PACKAGE/config.json
    --session /run/pearl-test-sessions/ID/session.json
    --state /NEW_PRIVATE/pilot-run --ram-dir /VALIDATED_PRIVATE_TMPFS --duration 180

Только внутри проверенного контроллера: watchdog590с ДО SIGSTOP, cgroup555с,
KillMode=control-group, общий предел паузы600с. Receipt после all-threadsT/idle/
unique-compute. UUID GPU-14cc341d-41f4-a977-1a1d-12785f4079da.
UID/GID1000, capabilities0, NoNewPrivileges=yes. PL310/core2610/memory405/
offset+300/fan55% и все настройки сохранять. Другие риги/пул/кошелёк/API/автозапуск
не менять. При ошибке закончить и восстановить без автоповтора.

Сохрани guard_checks, fresh/stale groups/s, native и client_GPU wait timings,
native/credited batch counts, мощность/температуру и sent/accepted/rejected/unknown.
Нужны fused_stage=true,global_transcript_materialized=false,target_modified=false,
один persistent worker,guard_checks.failed=0. Ноль шар за180с не считать acceptance
или доказательством неисправности. Если шары есть, сохранить proof/receipt и
независимо проверить исходный target.

Собрать всю cgroup ДО SIGCONT, строго подтвердить тот же SRBMiner, свежий хешрейт/
задания/шару, уникальность и неизменность настроек. Watchdog снимать после recovery.
Один отчёт и полный архив журналов без приватных конфигов/ключей.
45.971805млн fresh groups/s прежнего запуска — только ориентир разных сеансов,
не matched A/B и не SRBMinerTH/s.
