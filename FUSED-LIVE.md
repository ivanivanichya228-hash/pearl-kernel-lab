# Полный майнер0.2.0-fused: один реальный тест Mint4090

## Готовый пакет

`dist/pearl-test-0.2.0-linux-x86_64.tar.gz`

SHA256 `36c522d335e3330987d48b394ce616b85544e350bb02b99b90fc043bd2fe952a`.
Размер3229739байт. Скачивать из того же коммита, что этот документ.
Бинарники уже включены. На риге ничего не компилировать/устанавливать.

## Изменение

Ранее только отдельный fused-compare использовал новое ядро. Теперь --fused-stage
проходит через Python-клиент, persistent worker и MiningExecutor. Для КАЖДОГО
slab вызывается launch_fused с исходным KeyTarget и полным HitGeometry. Очередь
общая для всего batch, переполнение закрывает работу без частичного результата.
Глобальный transcript не выделяется и не материализуется. Нового ядра/геометрии
в этой интеграции нет; SM89 instruction text PN8/PN16 побайтно идентичен бинарнику
711db03, который прошёл тест на риге. Это проверено без GPU через cuobjdump.

Подготовка свежих случайных данных, commitments/noise, прежний Rust oracle,
построение доказательств и submission не заменены. Полный профиль/реальный target
сохраняются. Нет комиссии разработчика. Протокол — прежний plainJSONLuckyPool.
Rejected/unknown завершают тест, автопереподключения и повторного запуска нет.

115 CPU-тестов и make cpu-check прошли. Loopback CPU integration проверил8уникальных
доказательств официальным verifier:6mock accepted/2преднамеренныхmock rejected.
Это НЕ шары реального пула. Пакет проверен на загрузку/целостность без GPU.
Настоящий live-тест0.2.0-fused здесь ещё не выполнен; победа над SRBMiner не заявлена.

## Задание домашнему Codex

На Mint4090 room-room@192.168.1.98 скачай архив из dist ЭТОГО коммита, проверь
SHA256 и безопасные пути, распакуй в НОВЫЙ каталог. Прочитай README_RU.md и
integration/CONTROLLER.md. Выполни version/verify до остановки майнинга.
Версия должна быть0.2.0-fused, kernel=fused-triple384. Старые установки не заменяй.

Импортируй предыдущий приватный конфиг через configure --import-config.
Сохрани host/port/wallet/worker побайтно; конфиг0600, секреты не выводи.
Комплектный полный profile сравни со старым, target не ослабляй.

Переиспользуй проверенный КОРОТКИЙ контроллер420с/600с. Для нового одноразового
сеанса подготовь новый защищённый экземпляр с путями/хешами нового пакета;
не переписывай identity/pidfd/start ticks/operation lock/stop/resume/recovery.
Issuer скопируй в защищённый root-каталог, пользовательский код от root не запускай.
Sudoers/права драйвера/постоянные службы не меняй. Если нужен root-пароль,
подготовь одну конкретную команду установки адаптера для ввода локально.

Проведи ОДИН live-сеанс420с. Общая пауза<=600с, watchdog590с вооружён доSIGSTOP,
экспериментальная cgroup555с, KillMode=control-group, TimeoutStop2с. Receipt только
после all-threadsT, idle и unique-compute. UID/GID1000, capabilities0,
NoNewPrivileges=yes. UUID GPU-14cc341d-41f4-a977-1a1d-12785f4079da, ожидаемый PL310.
Частоты/offset/memory405/оба вентилятора55%, пул/кошелёк/API/автозапуск не меняй.
3060/Hive не затрагивай. Новый30мин сеанс автоматически не запускай.

Команда GPU-клиента ВНУТРИ прежнего контроллера:

```text
/NEW_PACKAGE/pearl-test run --config /NEW_PACKAGE/config.json
--session /run/pearl-test-sessions/ID/session.json
--state /NEW_PRIVATE/pilot-run --ram-dir /VALIDATED_PRIVATE_TMPFS --duration 420
```

Это первый тест полного ПОТОКА с fused, а не повтор microbenchmark. Старые
occupancy/two-CTA/matrix-loads/transfer-overlap/профилировщик/Sanitizer не запускать.
При ошибке остановить этот сеанс и восстановить SRBMiner без автоповтора.

Проверь в native mining_batch: fused_stage=true, global_transcript_materialized=false,
kernel_threads384/triple_stage=true, GPU_noise_applied=true, target_modified=false.
Все завершённые native batches должны совпасть с credited; свежие/stale отделены,
частичная работа не зачисляется. Если признаки не совпали — тест не засчитывать.
При найденных шарах сохрани proof.bin/report.json/receipt; каждое proof независимо
проверь закреплённым oracle pool-verify по ИСХОДНЫМ job/profile, без раскрытия wallet.
Ноль шар за420с обозначь прямо, не объявляй ни acceptance, ни доказанную поломку.

В завершение собери всю экспериментальную cgroup доSIGCONT; строго подтверди тот
же SRBMiner, свежий GPU0/API хешрейт, новые задания/принятую шару, уникальность,
рост uptime и неизменность настроек/защищённых файлов. Watchdog снимать только
после подтверждения. Контроллер обязан сохранить восстановление независимо от SSH.

## Отчёт

Фактическая длительность, fresh groups/s, sent/accepted/rejected/unknown/stale,
число native/credited batches, H2D/noise/fused-compute/prepare/proofs timings,
телеметрия мощности/температуры с указанием окна, результат восстановления и пауза.
Приложи полный архив журналов/доказательств без конфигов, ключей и кошельков.
Сравнение с прежними41.483920млн fresh groups/s — ориентир разных live-сеансов,
не причинное A/B; не переводить группы/с в SRBMinerTH/s и не обещать310Вт.
