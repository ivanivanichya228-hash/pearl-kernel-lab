# Pearl Test Miner0.4.0-singlepass-transcript

Готовый тестовый клиент для одной Mint RTX4090. Изменено CUDA-ядро, а не guards
или подготовка CPU. Преимущество над SRBMiner и новый GPU-прирост пока не измерены.
Комиссия разработчика0%, комиссия пула своя.

Оптимизация при k==16*rank: каждый из16слотов transcript пишется один раз,
поэтому удалены начальное обнуление, чтение/rotation старого значения.
Остальные формы используют прежний fused kernel. MMA, cp.async, размеры tile,
семантика commitments/noise/target/proof не менялись. Полный профильk4096/rank256
попадает в новый путь. CPU-производитель и оригинальный pinned checker из0.3.0.
Старое fused-ядро включено в тот же ELF как контроль.

После импорта приватного конфига и до паузы:

    ./pearl-test version
    ./pearl-test verify
    ./pearl-test configure --import-config /EXISTING_PRIVATE/config.json

Новый каталог, никаких перезаписей. Все host/port/wallet/worker сохраняются,
config0600. Нужны Linuxx86_64,Python>=3.10,glibc>=2.38,driver>=580;
Rust/Toolkit/NumPy на риге не требуются. GPU UUID
GPU-14cc341d-41f4-a977-1a1d-12785f4079da,PL310,прочие настройки прежние.
Программа не меняет напряжения, частоты, PL, вентиляторы или службы.

Запуск только прежним проверенным внешним root-контроллером; клиент UID/GID1000,
capabilities0,NoNewPrivileges=yes. Нужны действительный root-receipt в правильной
cgroup, независимый watchdog до SIGSTOP, all-threadsT/idle/unique-compute.

    ./pearl-test run --config /NEW_PACKAGE/config.json \
      --session /run/pearl-test-sessions/ID/session.json \
      --state /NEW_PRIVATE/pilot-run --ram-dir /PRIVATE_TMPFS --duration 420

Внутри команды сначала автоматически выполняются10GPU fixtures и одно короткое
A/B/B/A: именно original-fused384 против singlepass-fused384 на одном8192профиле,
без сравнения со старым separate-filter. Точные transcripts, смешанный target,
queue capacity0/1/all, proof8/16, partial tiles и fallback обязательны.
Затем проверяются исходные4времени: отношение>1.03 и обе B быстрее обеих A.
Только после успеха gate начинается420с полного майнинга. Иначе выход/восстановление
без длинного сеанса. Gate timeout45с; вся пауза<=600с, существующий контроллер
cgroup555с/watchdog590с. После gate повторно проверяется запас времени сессии.

Gate и live-клиент находятся в одной cgroup; отмена дожидается child/reap.
Контроллер завершает всю cgroup ДОSIGCONT и строго проверяет возврат того же SRB,
свежие задания/хешрейт/принятую шару. Watchdog снимается только после recovery.
Постоянные привилегии, sudoers, другие риги и settings не менять.

Сохраняются singlepass-gate.log/json, live events/performance/native timings,
proof/receipt. Скорость — свежие группы/с за полный wall; в SRBTH/s не переводится.
Три шара прежнего0.3.0 не являются доказательством скорости0.4.0. Не внедрять
в production без live-результата. Полное задание — SINGLEPASS-KERNEL.md в GitHub.
