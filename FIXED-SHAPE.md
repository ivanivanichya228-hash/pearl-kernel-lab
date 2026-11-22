# 0.5.0: фиксированная форма CUDA compute, безопасный отдельный край

Архив `dist/pearl-test-0.5.0-linux-x86_64.tar.gz`,8932124байт.
SHA256 `a351d48b87085e08a858d50f8a59345eb3accef7b2aff26722296bdd0b6cfd56`.
Engine SHA256 `3ed386576fcc0dafad0dd12ab70d84a5a93f8db272d82b6fc111cc19b71bb8e3`.

## Конкретная переработка

Новое CUDA-ядро pearl_fixed знает K4096/rank256/proof16 во время компиляции.
Внутри полностью заполненных192x256плиток все cp.async16-байтные загрузки
заведомо валидны. Убраны runtime-проверки каждой загрузки и вычисление шага
через runtime K. Это изменение пути загрузки/GEMM внутри CUDA, не guards/CPU.
MMA/prefix/checkpoint/XOR/hash/target/proof сохраняются.

Host-план использует это ядро только при точном профиле,K4096/rank256/proof16,
ширине кратной256 и наличии хотя бы192строк. Полные192-строчные блоки запускаются
отдельно; хвост — прежним singlepass0.4.0 с правильным смещением указателя A и
HitGeometry.row0. Иные формы,включая proof8,полностью идут по прежнему пути.
Переполнение row0 при разделении исключается fallback,не wraparound.

В8192slab:8064строки нового ядра+128старого. При полном131072профиле каждыйbatch:
67,108,864группы=66,060,288новых+1,048,576fallback; ничего не пропущено/добавлено.
Новый native-log явно пишет fixed_shape_requested/interior_groups/fallback_groups.
Это98.4375%групп на новом пути, **не процент ускорения**.

SM89 статические инструкции одного kernel function:

| Инструкции |0.4.0 singlepass|0.5.0 fixed |
|---|---:|---:|
| IMAD |416|322|
| ISETP |108|67|
| BRA |48|43|
| STS |37|21|
| LDS |103|103|
| IMMA |64|64|

Статические counts не runtime counters и не замер скорости. Полный CUDA13.0.88
build SM86/SM89 прошёл:168регистров,stack/spills0.139Python-тестов прошли.
Два новых dense NumPy prefix-эталона совпали с независимым C++ reference.
Проверены20комбинаций interior/tail/offset coverage,ошибочный профиль и rowoverflow.
ДляGPU gate12готовыхfixtures:старые10+полнаяплитка192x256 и край208x512.
Новое ядро на GPU ещё НЕ запускалось. Победа над SRBMiner не заявляется.

0.4.0 дал только1.01818x и был правильно отклонён; длинного live не было.
Повторять его/понижать3%/выдавать эту прибавку за результат0.5.0 нельзя.

## Автоматический отбор

Встроен в один штатный pearl-test run. Сначала GPU correctness12fixtures,
включая новую interior-ветку/край,proof8/16,fallback,mixedtarget,queuecapacity0/1/all.
Затем один короткий A/B/B/A(1с/.25сwarmup),одинаковый8192²K4096/rank256/proof16.
A — singlepass-fused0.4.0, B — fixed-shape0.5.0,оба в одном ELF.
Оригинальный fused0.3.0 и separate-filter НЕ используются как контроль.

Клиент заново считаетratioиз4времён,требует >1.03 и max(B)<min(A).
Без подтверждённого correctness/выигрыша длинный live автоматически не начинается.
Порог не менялся. Gate timeout45с. При успехе проверяется остаток root-receipt и
идёт один420ссеанс полного майнинга. Guards/session/cgroup/watchdog/recovery прежние.

## Задание домашнему Codex

Получи ЭТОТ коммит ivanivanichya228-hash/pearl-kernel-lab в новый checkout.
Mint4090 room-room@192.168.1.98:скачай готовый0.5.0архив из dist этого коммита,
проверь SHA/безопасные пути,распакуй в НОВЫЙ каталог. До паузы version/verify,
share/fixtures0..11. Не пересобирай/не устанавливай CUDA/Rust/NumPy на риг.
Импортируй прежний privateconfig с сохранением host/port/wallet/worker,config0600;
секреты не выводи.3060/Hive не трогай.

Используй существующий проверенный короткий контроллер;одноразовый экземпляр
с новыми paths/hashes,без изменения pidfd/startticks/operationlock/stop/resume/
recovery. Root-код закрытый/root-owned,без изменений sudoers/драйверов/API/
автозапуска/постоянных служб. Watchdog590с ДОSIGSTOP,cgroup555с,
KillMode=control-group,пауза<=600с,issuer послеall-thread-T/idle/uniquecompute.
Клиент UID/GID1000,capabilities0,NoNewPrivileges=yes. UUID
GPU-14cc341d-41f4-a977-1a1d-12785f4079da; PL310,lockcore2600/фактоколо2610,
offset+300,memory405,обаfan55%,pool/wallet и прочие настройки прежние.

ОДИН запуск:короткий gate уже внутри,отдельно его не запускать:

```text
/NEW_PACKAGE/pearl-test run --config /NEW_PACKAGE/config.json --session /run/pearl-test-sessions/ID/session.json --state /NEW_PRIVATE/pilot-run --ram-dir /VALIDATED_PRIVATE_TMPFS --duration 420
```

Если gate отказал — штатное восстановление без длинного live и без повторов.
Если прошёл — один420сlive-сеанс. Не добавлять старые тесты0.4/CPU-ABBA/occupancy/
twoCTA/transfer-overlap/Sanitizer/ncu/профилировщики.

В конце всюcgroup завершить ДОSIGCONT;строго подтвердить тот жеSRBMiner PID/
startticks,уникальность,свежий хешрейт/новые задания/принятую шару,прежниеGPU/
защищённыефайлы. Watchdog снять после строгогоrecovery;вproduction новыйклиент
не оставлять.При ошибке не повторять автоматически.

Отчёт: fixed-shape-gate.log/json,12fixtures,4legtimes,ratio и контрольименно0.4.0.
Еслиlive был — всеnative fixed_shape_requested=true,interior_groups66060288/
fallback1048576 накаждыйполныйbatch,fresh/stale groups/s за весьwall,
prepare/H2D/noise/compute/clientwait,средняя/пиковаямощность/PL,sent/accepted/
rejected/unknown,proof/receipt,независимыйpool-verify по исходномуjob/target.
При отказеgate прямо указать,чтоlive-прирост не измерялся. ВSRBTH/s группы
не переводить. Microbenchmark сам по себе не доказывает превосходство надSRB.

## Воспроизводимость отдельно от майнинга

make fixed-shape-cpu-check — новыеgoldens/независимыйC++/coverage/gate tests.
make CUDA_HOME=/EXISTING_PINNED_CUDA13 — полныйbuild безGPU/root/driverchanges.
Два больших новыхgoldenфайла воспроизводимыизseed и не дублируются отдельно вgit;
они уже включены вготовыйархив. Хеши — tests/fixtures/fixed-shape-manifest.json.
Сборка/CPUрезультаты — miner/FIXED-SHAPE-CPU-BUILD.json. Исходныйoracle иproducer
побайтно0.4.0,комиссияразработчика0%,доказанногоGPU-прироста пока нет.
