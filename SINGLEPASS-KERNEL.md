# Single-pass transcript: CUDA kernel0.4.0

Готовый пакет: `dist/pearl-test-0.4.0-linux-x86_64.tar.gz`,6280587байт.
SHA256 `06b6e25e608a8fca12282bc2d011d99d1e49d823f5e0ec43019382ee8506a3af`.
Engine SHA256 `0d0a0342ed43214e4134930ffbfefca60fd0a851e3e932af74a91ef5dee8eef0`.

## Что изменено

При k=16*rank каждый из16слотов transcript записывается ровно один раз.
В формуле h=rotl13(h)^x предыдущее h равно нулю; результат равен x.
Новый template SinglePass удаляет начальное shared-обнуление, чтение и вращение
прежнего h. Все16слотов записаны до общего barrier/транспонирования.
При других формах вызывается исходный fused kernel. Полный production профиль
k4096/rank256 исполняется прежними8192slabs и попадает в новый путь.
MMA/prefix/checkpoints/XOR/noise/hash/target/proof,384потока,tile192x256 и стадии
сохранены. CPU producer/checker и guards/recovery прежние.

SM89 статические SASS-инструкции одного kernel function:

| Инструкция | Оригинал | SinglePass |
|---|---:|---:|
| LDS |135|103|
| STS |66|37|
| SHF |334|302|
| IMMA |64|64|
| REDUX |32|32|

Это **не runtime counters и не процент ускорения**. В обоих вариантах proof16
использует168регистров,proof8 —167; SM86/89,stack/spills=0. CUDA13.0.88 build
прошёл.135Python-тестов и4новых NumPy fixtures против независимого C++ prefix/
rotation reference прошли. Всего для GPU gate10fixtures:proof8/16,rank32/128/256,
ровно16checkpoints,edge tiles и fallback. GPU-прирост/преимущество над SRB не измерены.

Перестановка A/B fragments не поставляется: PTX был короче, но SASS уже устранял
повторные чтения. Новый вариант содержит именно single-pass transcript.
0.3.0 дал45.002427M fresh groups/s,3accepted,99.445Вт без доказанного ускорения.
Не повторять mapped-input/guards/twoCTA/occupancy/transfer-overlap эксперименты.

## Автоматический короткий gate

Штатный `pearl-test run` САМ запускает10GPU correctness fixtures, затем одно
A/B/B/A по1с с прогревом0.25с на одинаковом8192²K4096/rank256/proof16.
A — original-fused384, B — singlepass-fused384. Старый separate-filter не контроль.
Точные transcripts, mixedtarget,capacity0/1/all,proof8/16 и fallback обязательны.
Клиент заново считает ratio из4времён: нужно >1.03 и max(B)<min(A).
Если correctness/скорость/guards не прошли, длинного live НЕ БУДЕТ.
Timeout gate45с. При успехе проверяется оставшееся время root-receipt,
после чего начинается один420с-сеанс полного майнинга. Всё в прежней cgroup,
с signal cancellation/child reap/watchdog. Второго stop/resume механизма нет.

## Задание домашнему Codex

Получи ЭТОТ коммит ivanivanichya228-hash/pearl-kernel-lab в новый checkout.
На Mint4090 room-room@192.168.1.98 скачай готовый0.4.0архив из dist этого коммита,
проверь SHA/безопасные пути и распакуй в новый каталог. До паузы version/verify;
без Rust/CUDA/NumPy установок и пересборок на риге. Share/fixtures должен иметь0..9.
Импортируй существующий приватный config с прежними host/port/wallet/worker,
config0600. Не выводи секреты.

Используй одноразовый экземпляр СУЩЕСТВУЮЩЕГО проверенного короткого контроллера:
поменяй paths/hashes на новый пакет. Сохрани pidfd/start ticks/operation lock,
stop/resume/recovery, закрытый root-owned код, issuer после all-threadsT/idle/
unique-compute. Watchdog590с ДО SIGSTOP, cgroup555с,KillMode=control-group,
общая пауза<=600с. Клиент UID/GID1000,capabilities0,NoNewPrivileges=yes.
UUID GPU-14cc341d-41f4-a977-1a1d-12785f4079da, PL310,lockcore2600/фактоколо2610,
offset+300,memory405,обаfan55%; pool/wallet/API/autostart/settings прежние.
3060/Hive/драйверы/постоянные службы/sudoers не менять.

ОДИН запуск, gate уже встроен — отдельно его НЕ запускать:

```text
/NEW_PACKAGE/pearl-test run --config /NEW_PACKAGE/config.json
--session /run/pearl-test-sessions/ID/session.json
--state /NEW_PRIVATE/pilot-run --ram-dir /VALIDATED_PRIVATE_TMPFS --duration 420
```

При отказе gate — штатное восстановление без длинного live и без повторов.
При успехе — один420с-сеанс. Не добавлять старые проверки, CPU-ABBA,Sanitizer,ncu.
В конце ВСЮ cgroup завершить ДО SIGCONT; строго подтвердить тот же SRBMiner
PID/start ticks,свежий хешрейт/задания/принятую шару,уникальность и прежний
GPU/защищённые файлы. Watchdog снять после recovery. Новый майнер не оставлять
в production. При ошибке никаких автоматических повторов.

Отчёт: singlepass-gate.log/json,4legtimes/ratio,контрольoriginalfused,10fixtures;
если live был — native singlepass_transcript_requested/applied=true, fresh/stale
группы/с за полныйwall,prepare/H2D/noise/compute/clientwait,средняя/пиковая мощность/
PL,sent/accepted/rejected/unknown,proof/receipt,независимый pool-verify по исходному
job/target. Группы не переводить автоматически в SRBTH/s. При отказе gate честно
указать,что live-прирост не измерялся. Прежние45.97Mgroups/s — исторический ориентир,
не matchedABBA. Три accepted старой0.3.0 не доказывают скорость новой0.4.0.

## Воспроизведение отдельно от майнинга

make singlepass-cpu-check — независимые CPU algebra/writer/gate/fixture checks.
make CUDA_HOME=/EXISTING_PINNED_CUDA13 — build без GPU/root/driver changes.
miner/SINGLEPASS-CPU-BUILD.json хранит наблюдавшиеся ресурсы/статические counts.
В готовом архиве все бинарники/profile/fixtures/licenses; восстанавливать build
окружение на майнинговом риге не требуется.
