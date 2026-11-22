# 0.2.3: исправлены двойные синхронные identity-проверки

Готовый пакет: `dist/pearl-test-0.2.3-linux-x86_64.tar.gz`,3231185байт.
SHA256 `470f10834dc13b590e9e09e8d354c376aa1dc89d1dfb648c6f91151e4e0cde22`.

## Исправление конкретной ошибки0.2.2

Старый AsyncGuardChecks.check_async вызывал fast_check до lock и после lock.
Оба вызова выполнялись прямо в asyncio-потоке. Полный check дополнительно
содержал ту же identity-проверку. В live-журнале0.2.2 это2050fast-вызовов и
66.451773с синхронной работы за180.290684с; 348full заняли31.413503с.
Эти величины не дают гарантированный процент прироста после исправления.

Теперь внутри async-функции нет вызовов /proc или nvidia-smi. Под общим lock
вызывается asyncio.to_thread(scheduled_check,force). В worker выбирается РОВНО
одна ветка: полный guard (он уже включает identity), либо одна identity-проверка.
Решение о свежести делается в worker после ожидания очереди. Двойных identity нет.

Прежняя политика0.2.2 сохранена: каждая отправка GPU-request принудительно
запускает новый полный check; только periodic может использовать успешный PL
в пределах0.5с от начала полного опроса. PID/start ticks/все потокиT/другой SRB
проверяются при каждом обращении — один раз, в worker. Ошибка остаётся latched;
отмена дожидается активной проверки. Тайм-аут subprocess3с и внешний watchdog
прежние. Кеш явно отражается в cached_results=true; его окно не увеличено.

Тела gpu_guard/identity_guard, GPU-бинарник, oracle, target и профиль не изменены.
128CPU-тестов прошли. ДВА новых regression-теста на старом0.2.2 завершаются
ожидаемой ошибкой; на исправлении проходят:
1. Ровно одна identity-проверка на каждое обращение, включая full/forced.
2. Намеренно медленная cached identity не блокирует цикл и работает не в его thread.
Результаты: miner/GUARD-FIX-REGRESSION.json. CPU-loopback проверил8уникальных proof
официальным verifier,6mockaccepted/2намеренныхmockrejected, без внешнего пула/GPU.
Новый live-прирост/310Вт/победа надSRB ещё не измерены. В production не внедрено.

## Задание домашнему Codex

Получи ЭТОТ коммит в отдельный checkout. На Mint4090 room-room@192.168.1.98
скачай архив из dist этого же коммита, проверь SHA и безопасные пути, распакуй
в НОВЫЙ каталог. Version0.2.3-nonblocking-guards, verify до паузы; engine/oracle
побайтно прежние0.2.0. Ничего не пересобирай/не устанавливай на риге.

Импортируй прежний приватный config с сохранением host/port/wallet/worker,
config0600. Полный profile прежний. Секреты не выводи. Подготовь новый одноразовый
экземпляр существующего короткого контроллера с новыми путями/хешами. Не меняй
его pidfd/start ticks/operation lock/stop/resume/recovery. Root-код только в
закрытом root-каталоге; sudoers/права драйвера/постоянные службы не менять.

При live-проверке — ОДИН180-секундный сеанс, без повторов или других kernels:

```text
/NEW_PACKAGE/pearl-test run --config /NEW_PACKAGE/config.json
--session /run/pearl-test-sessions/ID/session.json
--state /NEW_PRIVATE/pilot-run --ram-dir /VALIDATED_PRIVATE_TMPFS --duration 180
```

Только внутри прежнего контроллера: watchdog590с ДОSIGSTOP, cgroup555с,
KillMode=control-group, общая пауза<=600с, receipt после all-threadsT/idle/
unique-compute. UUID GPU-14cc341d-41f4-a977-1a1d-12785f4079da;
UID/GID1000,capabilities0,NoNewPrivileges=yes. PL310/core2610/memory405/
offset+300/обаfan55%, пул/кошелёк/API/автозапуск и другие риги не менять.

В отчёте нужны guard_checks.fast_checks_nonblocking=true,
duplicated_identity_checks=false, failed=0, forced_full_checks>=native batches,
full_observation_period_seconds=0.5, максимум1параллельныйcheck. Подтверди кодом
dispatch и новыми CPU-тестами, а не только булевым полем отчёта. Сохрани full/fast
calls и времена, queue_seconds, fresh/stalegroups/s, native/clientwait, мощность,
native/credited, sent/accepted/rejected/unknown. Ноль шар в180с не считать ни
acceptance, ни доказательством неисправности; найденные proof/receipt независимо
проверяются по исходному job/target. Не запускать старые A/B/occupancy/two-CTA/
profiler/Sanitizer/transfer-overlap. Сравнения разных live-сеансов — ориентир,
не matched A/B; группы/с не переводить автоматически в SRBMinerTH/s.

При ошибке заверши без автоповтора. Всю cgroup собрать ДОSIGCONT. Строго подтвердить
тот же SRBMiner, свежие хешрейт/задания/шару, уникальность и прежние настройки/
файлы. Watchdog снимать после recovery. Полный отчёт и архив без приватных конфигов.
