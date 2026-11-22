# Pearl Test Miner0.5.0-fixed-shape

Готовый ограниченный клиент для Mint RTX4090. Изменён CUDA compute-путь:
K4096/rank256/proof16 известны компилятору; полные192x256плитки не проверяют
каждую16-байтную загрузку на границы. Шаг4096 — константа, не runtime multiply.
Край обрабатывает0.4.0, остальные формы полностью возвращаются к старому пути.
Для8192slab —8064строки нового ядра и128строк старого. Сохраняются все группы,
MMA/prefix/transcript/noise/hash/target/proofs. Скорость на GPU ещё не измерена;
победа над SRBMiner не заявлена. Комиссия разработчика0%, комиссия пула своя.

Внутри новые engine/Python-клиент, прежние producer/checker/profile,12готовых
fixtures. Нужны Linuxx86_64,Python>=3.10,glibc>=2.38,driver>=580;
Rust/CUDA/NumPy на риг не устанавливаются. GPU UUID
GPU-14cc341d-41f4-a977-1a1d-12785f4079da,PL310 и остальные настройки прежние.
Программа не меняет напряжения/частоты/PL/вентиляторы/службы.

До паузы, новый каталог, без перезаписей:

    ./pearl-test version
    ./pearl-test verify
    ./pearl-test configure --import-config /EXISTING_PRIVATE/config.json

Импорт сохраняет host/port/wallet/worker,новый config0600.
Запуск только существующим root-контроллером; клиент UID/GID1000,
capabilities0,NoNewPrivileges=yes,привязанный root-receipt,правильная cgroup,
watchdog доSIGSTOP,all-thread-T/idle/unique-compute.

    ./pearl-test run --config /NEW_PACKAGE/config.json \\
      --session /run/pearl-test-sessions/ID/session.json \\
      --state /NEW_PRIVATE/pilot-run --ram-dir /PRIVATE_TMPFS --duration 420

Автоматически внутри ОДНОЙ команды:12fixture GPU checks,затем один короткий
A/B/B/A(1с/.25сwarmup). A — singlepass-fused0.4.0, B — fixed-shape0.5.0.
Исходный fused0.3.0 не используется как контроль. Клиент сам требует точных
transcripts/mixedtarget/capacity0/1/all и ratio>1.03,max(B)<min(A).
При отсутствии выигрыша/ошибке длинный live не начинается. Тайм-аут gate45с.
При успехе проверяется остаток root-receipt и идёт один420сlive-сеанс.
Порог3% не понижен,1.818% старого0.4.0 не считается новым результатом.

Всё в прежней cgroup,signal cancellation/child reap/session monitor/guards
сохранены. Внешний контроллер cgroup555с/watchdog590с/пауза<=600с завершает
всю cgroup ДОSIGCONT и строго проверяет возврат того же SRBMiner,новые задания,
свежий хешрейт и принятую шару. Watchdog снять после строгого recovery.
Без повторов,других ригов,изменений sudoers/драйверов/постоянных служб.

Логи fixed-shape-gate.log/json; live native содержит fixed_shape_requested,
fixed_shape_interior_groups,fixed_shape_fallback_groups. Для полного профиля
67,108,864группы=66,060,288interior+1,048,576fallback в каждом batch.
Сохраняются performance/proof/receipt; группы/с не переводить в SRBMinerTH/s.
Не оставлять в production без измеренного результата. Задание — FIXED-SHAPE.md.
