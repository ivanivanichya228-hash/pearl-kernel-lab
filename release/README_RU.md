# Pearl Test Miner0.3.0-mapped-input

Полный тестовый клиент Pearl для Mint RTX4090, ядро fused-triple384 из711db03.
Оно прошло golden fixtures и resident compute+filter A/B/B/A:1.925695x относительно
нашего triple384+filter. Реальный майнинг ЭТОЙ сборкой ещё не проверен;
преимущество над SRBMiner не доказано. Комиссия разработчика0%, комиссия пула своя.

Внутри bin/pearl-engine, неизменённый bin/pearl-protocol-oracle и новый
bin/pearl-data-producer; Python-клиент с одной
командой pearl-test, полный profile, проверка хешей, issuer для прежнего контроллера.
Не нужны Toolkit/Rust/NumPy; LinuxMintx86_64, Python>=3.10,glibc>=2.38,driver>=580.
Точная карта GPU-14cc341d-41f4-a977-1a1d-12785f4079da, ожидается PL310.
Частоты, напряжение, PL, вентиляторы и службы программа не изменяет.

Распакуй в НОВЫЙ каталог, сохрани предыдущие установки. Команды подготовки:

    ./pearl-test version
    ./pearl-test verify
    ./pearl-test configure --import-config /абсолютный/путь/к/приватному/config.json

verify не запускает CUDA-вычисления и не соединяется с пулом. На другом Linux
допускается verify --offline. Импорт сохраняет host/port/wallet/worker; создаёт
новый config.json0600, не перезаписывает существующий. Профиль — комплектный полный.
Подтверждён протокол plainJSONLuckyPool; другие протоколы не заявлены.

Реальный запуск выполняет ТОЛЬКО прежний проверенный root-контроллер; GPU-клиент
работает UID/GID1000, все capabilities0, NoNewPrivileges=yes. Сначала независимый
watchdog, SIGSTOP исходного SRBMiner с pidfd/start ticks, все потокиT, простой GPU,
нет другого compute. Затем root-receipt, привязанный к cgroup/watchdog/дедлайну:

    ./pearl-test run --config /абсолютный/config.json \
      --session /run/pearl-test-sessions/ID/session.json \
      --state /НОВЫЙ/приватный/pilot-run --ram-dir /проверенный/private/tmpfs --duration 420

Без действительного root-receipt и правильной cgroup запуск блокируется.
Первый сеанс420с, вся пауза<=600с. Issuer/API восстановления не менялись.
Внешний контроллер завершает ВСЮ cgroup перед SIGCONT и строго подтверждает возврат
того же SRBMiner. Ctrl+C не заменяет подтверждение восстановления.

Новый native-путь: fused_stage=true, global_transcript_materialized=false,
triple_stage=true, kernel_threads384, GPU_noise_applied=true, target_modified=false.
Кошелёк и действительный target не подменяются. Строятся прежние Rust-доказательства,
пул получает настоящие шары. Reject/unknown завершают тест без автоповторов.

Показатели — свежие группы/с, accepted/rejected/unknown, native stage timings,
мощность из телеметрии внешнего контроллера; автоматически в SRBMinerTH/s не переводятся.
Ноль найденных шар за короткое окно сам по себе не доказывает неисправность.
Сохраняются privateevents.jsonl/performance.json/nativeevents и proof/receipt.
Подробное задание установки и одного теста — MAPPED-INPUT.md в GitHub.

Новый путь0.3.0: CPU генерирует случайные INT7-матрицы сразу в MAP_SHARED-файлах
приватного tmpfs. Нет промежуточных Vec на1ГиБ и последующего fs::write на1ГиБ.
GPU получает прежний PRLRAWN1-манифест188байт и те же форматы массивов.
Свежая OS-случайность, commitments, target и доказательства сохраняются.
Оригинальный pinned oracle продолжает независимо проверять/строить proof;
новый producer используется только для work-prepare-mapped. Engine не менялся.

CPU-подготовка полного1ГиБ на машине разработки:0.487374→0.354845с,−27.19% времени
(четыре потока, A/B/B/A после отдельных прогревов). Это НЕ прирост хешрейта;
подготовка перекрывается с вычислениями, результат на4090 пока не измерен.
Пять Rust-тестов,128Python-тестов,26 независимых official proofs и полный
CPU-loopback проверены. Mockaccepted не являются шарами настоящего пула.
Механизм watchdog/recovery и nonblocking guards из0.2.3 сохранены.
