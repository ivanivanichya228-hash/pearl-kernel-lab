# Pearl Test Miner0.2.3-nonblocking-guards

Полный тестовый клиент Pearl для Mint RTX4090, ядро fused-triple384 из711db03.
Оно прошло golden fixtures и resident compute+filter A/B/B/A:1.925695x относительно
нашего triple384+filter. Реальный майнинг ЭТОЙ сборкой ещё не проверен;
преимущество над SRBMiner не доказано. Комиссия разработчика0%, комиссия пула своя.

Внутри готовые bin/pearl-engine и bin/pearl-protocol-oracle, Python-клиент с одной
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
Подробное задание установки и одного теста — GUARD-FIX.md в GitHub.

Версия0.2.2: PID/start ticks/все потокиT/дубликаты проверяются при каждом обращении.
Полный UUID/PL опрашивается заново перед КАЖДЫМ GPU-запросом; периодические
ожидания используют результат полного опроса не старше0.5с от начала проверки.
Ошибки запоминаются и закрывают сеанс; отмена дожидается активного check.
Срок полного subprocess по-прежнему ограничен3с; внешний watchdog/контроллер прежние.
Новый live-прирост не измерен. Engine/oracle идентичны проверенной0.2.0.

Исправление0.2.3: оба вида проверок полностью выполняются в фоновом потоке.
Одно обращение вызывает либо полный опрос с identity, либо одну identity-проверку,
а не две identity плюс полный опрос. Проверки PID/PL и stop-on-failure сохранены.
Новый прирост скорости не измерен; GPU-бинарник/oracle/профиль не изменены.
