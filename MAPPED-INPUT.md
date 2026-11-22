# 0.3.0: данные сразу в shared tmpfs

Готовый пакет `dist/pearl-test-0.3.0-linux-x86_64.tar.gz`,3857629байт.
SHA256 `932949e5f48bb79b9aaa398ef85b40eadf31c1df0a8c5f50292a22630fe8e810`.

Изменена подготовка входов, а не CUDA-ядро: новый `pearl-data-producer`
создаёт два MAP_SHARED-файла и заполняет их свежей случайностью на месте.
Удалены промежуточные Vec общим объёмом1ГиБ и копирование1ГиБ через fs::write.
GPU по-прежнему читает raw-a/raw-bt и188-байтный PRLRAWN1-манифест.
OS-seeded CSPRNG по4МиБ, распределение INT7[-64,63], commitments и target прежние.
Метафайл готовности записывается последним. Незавершённая подготовка не отправляется
GPU; pipeline дожидается завершения отменённого child перед удалением каталога.

Исходный pinned oracle НЕ заменён: он по-прежнему строит/проверяет доказательства,
корни и share target. Новый producer вызывается только для `work-prepare-mapped`.
CUDA engine, profile и recovery API побайтно прежние; guards0.2.3 сохранены.
Нет гарантированного роста до310Вт или доказанной победы над SRBMiner.

## Измеренный результат

Один хост разработки, четыре Rayon-потока, полный профиль
m=n=131072,k4096,rank256, proof16x16. Сначала отдельный прогрев каждого пути,
затем A/B/B/A. Каждый измеренный результат независимо проверен исходным oracle
через полные official Merkle trees; все188байт заголовка совпали.

| CPU-подготовка | Среднее wall,с |
|---|---:|
| Исходная |0.487374347|
| Direct-mapped |0.354845223|

Сокращение времени27.1925%, отношение скоростей подготовки1.37348x.
Это CPU-замер, **не прирост хешрейта**: CPU и GPU работают с перекрытием.
Карта не запускалась; pool acceptance этой сборки ещё не проверен.
Сырые данные: `miner/MAPPED-PREP-BENCH.json`.

Пять Rust-тестов прошли. Четыре формы rank128/256,k2048/4096,proof8/16
проверены независимой C++-арифметикой и исходным verifier:26proofs.
Полный PythonCLI+loopback:8уникальных proofs,6mockaccepted и2намеренных
mockrejected; это не шары настоящего пула.128Python-тестов прошли.
Результаты: `miner/MAPPED-CPU-CHECK.json`, `miner/MAPPED-LOOPBACK-RESULT.json`.

## Задание домашнему Codex

Работай с ЭТИМ коммитом `ivanivanichya228-hash/pearl-kernel-lab` в новом checkout.
На Mint4090 room-room@192.168.1.98 получи готовый0.3.0архив выше из dist,
проверь SHA, безопасные пути, распакуй в НОВЫЙ каталог. Не пересобирай и не
устанавливай Toolkit/Rust на риг. До паузы выполни version/verify;
версия0.3.0-mapped-input, producer mapped-raw-v1. Engine/oracle должны быть
побайтно идентичны0.2.0, producerSHA
`44b9ae789102c09d1483e40127eb8456c21b41ce3e3a80eaf9dfb86e7462e160`.

Импортируй существующий приватный config: те же host/port/wallet/worker,
новый config0600; секреты не выводи. Другие риги не трогай.
Никаких CPU-ABBA/профайлеров/повторных старых экспериментов на работающем риге.

Используй существующий проверенный root-контроллер и recovery. Подготовь новый
одноразовый экземпляр с новыми путями/хешами; логику pidfd/start ticks/operation
lock/stop/resume не меняй. Root-код остаётся в закрытом root-каталоге.
Не ослабляй sudoers/права и не меняй постоянные службы/API/автозапуск.

**Один420-секундный live-сеанс**, без повторов и без остановки на первой шаре:

```text
/NEW_PACKAGE/pearl-test run --config /NEW_PACKAGE/config.json
--session /run/pearl-test-sessions/ID/session.json
--state /NEW_PRIVATE/pilot-run --ram-dir /VALIDATED_PRIVATE_TMPFS --duration 420
```

Только через прежний
контроллер: watchdog590с ДОSIGSTOP, cgroup555с, KillMode=control-group,
общая пауза<=600с. Receipt после all-threadsT/idle/unique-compute.
UID/GID1000,capabilities0,NoNewPrivileges=yes; UUID
GPU-14cc341d-41f4-a977-1a1d-12785f4079da. PL310, lockcore2600/факт около2610,
offset+300, memory405, обаfan55%; профиль/кошелёк/пул не менять.

Не включать two-CTA/occupancy/transfer-overlap/Sanitizer/ncu. Kernel остаётся
fused-triple384. При ошибке закончить без автоповторов. Всю cgroup собрать
ДОSIGCONT. Строго подтвердить возврат того же PID/start ticks SRBMiner,
свежий хешрейт, новые задания и принятую шару, уникальность и прежние настройки.
Watchdog снять после строгого recovery. Не оставлять новый майнер в production.

Отчёт: версия/SHA, fresh candidate groups/s за весь сеанс, completed/stalegroups,
число batch, native/clientwait/H2D/noise/compute, все prepare_timing,
мощность средняя/пик/PL, sent/accepted/rejected/unknown, proof/receipt.
Подтвердить producer mode по фактическому argv и metadata; оригинальный oracle
использован на finalize/verify. Ноль найденных шар не объявлять неисправностью;
mockaccepted не принимать за realaccepted. Предыдущие45.971805Mgroups/s — только
исторический ориентир, сравнение разных сеансов не matchedABBA. В TH/s SRB
группы автоматически не переводить. Полный отчёт/архив без приватных конфигов.

## Воспроизведение CPU-проверки на отдельной машине

Оригинальный oracle из0.2.0: SHA
`2b009ef7afb1a2fce1be5f93da2a10e3f80019d4cab89edbf2eb3f0a354049bb`.

```sh
c++ -O2 -std=c++17 -Iinclude tests/work_cpu.cpp -o build/work-cpu
python3 tests/check_mapped_producer.py --oracle /ORIGINAL_ORACLE --producer /NEW_PRODUCER --engine build/work-cpu --out /NEW_RESULT.json
python3 tests/benchmark_mapped_prepare.py --oracle /ORIGINAL_ORACLE --producer /NEW_PRODUCER --out /NEW_BENCH.json --threads 4
```

Бенчмарк занимает CPU/память,
не предназначен для параллельного запуска рядом с прибыльным майнингом.

Сборка исходников требует pinned upstream38dd764 и Cargo.lock из проекта.
После подготовки `.proof-cache/upstream` на ЭТОМ commit обычный путь:
`cargo build --locked --release --manifest-path proof-oracle/Cargo.toml`.
Полученный bridge скопировать под именем pearl-data-producer; **не подменять**
им оригинальный checker. Clean-Cargo сборка в этом ходе не выполнялась: готовый
producer собран rustc1.90.0 из уже существующих rlibs без загрузок/установок.
Прямой путь: tools/build_mapped_producer.py --rustc /RUSTC --cached-deps /DEPS
--out /NEW_PRODUCER; exact rlib names/hashes в miner/MAPPED-PRODUCER-BUILD.json.
Путь с --test даёт Rust unit binary. История guard-пакетов сохранена отдельно.
