# 0.2.2: сокращение дублирующихся полных проверок

Пакет `dist/pearl-test-0.2.2-linux-x86_64.tar.gz`, SHA256
`9076894724e707d0a07fd5ab5f371c72441d6849de1524b2c57f87e7b87043a3`,3230952байт.

## Почему предыдущая версия не принята как ускорение

В0.2.1 за180.246841с выполнено977полных guard-проверок, execution100.252453с,
queue12.612465с. Они перекрываются с другими этапами; это не100с чистого простоя.
Fresh44.305658млн/с против45.971805у0.2.0 в другом сеансе, гарантированного
ускорения не получено. Эта версия не повторяет тот же простой перенос в thread.

## Новая политика — явно ограниченная свежесть PL

Сама функция полной проверки НЕ изменена: UUID/model/PL, PID/start ticks,
все потокиT, отсутствие другого SRBMiner. Её CPU-часть выделена в identity_guard;
AST совпадает с соответствующей частью прежней полной проверки.

При КАЖДОМ обращении проверяются PID/start ticks/все потокиT/другие SRBMiner.
Перед КАЖДЫМ GPU-запросом check_guard(force=True) запускает НОВЫЙ полный опрос,
независимо от возраста предыдущего. Нельзя начать GPU-запрос по старому PL.
Ожидания CPU/GPU используют успешный полный опрос только в пределах0.5с от
начала проверки; за пределами окна запускается полный опрос. Параллельные
периодические обращения разделяют этот результат вместо очереди дубликатов.
Полные проверки последовательны. Исходный subprocess timeout3с сохранён:
0.5с — окно повторного использования, не гарантия ответа драйвера за0.5с.
Любая ошибка fast/full фиксируется и закрывает дальнейшие обращения без повторов.
Отмена дожидается активной проверки; все потоки и процессы в прежней cgroup.
Внешний независимый контроллер/настройки/receipt/watchdog не изменены.

В performance.guard_checks.cached_results теперь ЯВНО true для GPU: это
ограниченное окно, а не прежнее обещание отсутствия кеширования. Добавлены
full_observation_period_seconds=0.5, fresh_full_check_before_GPU_request=true,
forced_full_checks, fast_calls/fast_seconds, periodic_reuses. calls считает
полные проверки. Старый отчётный gate0.2.1 cached_results=false здесь неприменим.

126CPU-тестов прошли:8одновременных periodic=>1full; истёкшее окно=>новыйfull;
каждыйforced=>новыйfull; ошибка PL наforced отклоняется даже сразу после успешного
full; ошибка PID отклоняется сразу в пределах окна; ошибка не сбрасывается.
Прежние cancel/drain/kill/неблокирующий цикл также проверены.
CPU-loopback:8официально проверенных доказательств,6mockaccepted/2намеренных
mockrejected. Это НЕ реальные шары нового пакета. GPU не запускался.
Ядро/engine/oracle побайтно прежние0.2.0, без CUDA-компиляции или установки.
Новый процент прироста/310Вт/победа надSRB не заявляются.

## Задание домашнему Codex

Получи ЭТОТ коммит в отдельный checkout. На Mint4090 room-room@192.168.1.98 скачай
готовый архив из dist того же коммита, проверь SHA и безопасные пути, распакуй в
НОВЫЙ каталог. Version0.2.2-guard-budget, verify до паузы. Engine/oracle должны
совпасть поSHA с0.2.0. Ничего не устанавливай и не пересобирай на риге.
Импортируй прежний приватный config с host/port/wallet/worker без изменений,
config0600. Полный profile тот же. Не выводи секреты.

Подготовь новый одноразовый экземпляр ПРЕЖНЕГО короткого контроллера с новыми
путями/хешами. identity/pidfd/start ticks/operation lock/stop/resume/recovery
не переписывай; root-код только в защищённой root-копии. Не меняй sudoers/драйвер.

Если выполняешь проверку на риге, только ОДИН180-секундный сеанс через этот
контроллер, без повторов,30мин,профилировщика,occupancy/two-CTA/transfer-overlap:

```text
/NEW_PACKAGE/pearl-test run --config /NEW_PACKAGE/config.json
--session /run/pearl-test-sessions/ID/session.json
--state /NEW_PRIVATE/pilot-run --ram-dir /VALIDATED_PRIVATE_TMPFS --duration 180
```

Watchdog590с ДО SIGSTOP, cgroup555с, общий предел паузы600с. Receipt после
all-threadsT/idle/unique-compute. UUID GPU-14cc341d-41f4-a977-1a1d-12785f4079da;
UID/GID1000, capabilities0, NoNewPrivileges=yes. PL310/core2610/memory405/
offset+300/обаfan55% и все настройки сохранять. Другие риги/пул/кошелёк/API/
автозапуск/постоянные службы не менять. При ошибке завершить и восстановить.

Новый gate: failed=0, максимум1parallel, nonblocking=true, cached_results=true,
full_observation_period_seconds=0.5, fresh_full_check_before_GPU_request=true,
forced_full_checks>=числа завершённых native batch. Полный опрос перед каждым
request проверить также по исходнику dispatch и CPU-негативному тесту.
fused_stage=true, global_transcript_materialized=false, target_modified=false.
Не подменяй отчёт, если старый gate не подходит: явно используй эти новые критерии.

Отчёт: fresh/stalegroups/s, full/fastcalls и времена, periodic_reuses, clientGPU
wait/nativewall, мощность/температура, native/credited, sent/accepted/rejected/
unknown. Ноль шар за180с не означает acceptance или неисправность. Доступные
proof/receipt независимо проверяются по исходному job/target.

Собери всю cgroup ДОSIGCONT, строго подтверди тот же SRBMiner, свежие хешрейт/
задания/шару, уникальность и неизменные файлы/настройки. Watchdog снимать после
recovery. Сохрани полный отчёт/архив без приватных конфигов и ключей.
Сравнение с0.2.0/0.2.1 — ориентир разных live-сеансов, не matched A/B.
