#!/usr/bin/env python3
"""Ready bounded Mint4090 pilot; the existing external controller owns SRBMiner recovery."""
import argparse,asyncio,csv,hashlib,io,json,math,os,platform,re,signal,stat,subprocess,sys,time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent
# Installed as package/pearl-test; imported from release/ in source tests.
if ROOT.name=='release':ROOT=ROOT.parent
VERSION='0.4.0-singlepass-transcript'
GPU='GPU-14cc341d-41f4-a977-1a1d-12785f4079da'

def verify_bundle(root=ROOT):
 manifest=json.loads((root/'manifest.json').read_text())
 if manifest.get('version')!=VERSION or manifest.get('kernel')!='fused-triple384':raise ValueError('Неизвестная сборка')
 for name,digest in manifest['files'].items():
  rel=Path(name)
  if rel.is_absolute() or '..' in rel.parts:raise ValueError('Некорректный путь манифеста')
  path=root/rel
  if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Изменён или отсутствует файл: '+name)
 return manifest

def loader_check(root=ROOT):
 engine=subprocess.run([str(root/'bin/pearl-engine'),'--help'],capture_output=True,text=True,check=True,timeout=5)
 if '--triple-stage' not in engine.stdout or '--fused-stage' not in engine.stdout or '--singlepass-transcript' not in engine.stdout:raise ValueError('Вычислительный бинарник не поддерживает triple384')
 oracle=subprocess.run([str(root/'bin/pearl-protocol-oracle')],capture_output=True,text=True,timeout=5)
 if oracle.returncode!=1 or 'usage:' not in oracle.stderr.lower():raise ValueError('Проверяющий бинарник не загрузился')

 producer=subprocess.run([str(root/'bin/pearl-data-producer'),'data-producer-info'],capture_output=True,text=True,check=True,timeout=5)
 if json.loads(producer.stdout)!={'producer':'mapped-raw-v1','GPU_executed':False}:raise ValueError('Неверный производитель данных')

def clean_config(data,profile):
 host=data.get('host');port=data.get('port')
 if not isinstance(host,str) or not 1<=len(host)<=253 or not re.fullmatch(r'[A-Za-z0-9.:-]+',host):raise ValueError('Укажи имя пула без https:// и без порта')
 if type(port) is not int or not 1<=port<=65535:raise ValueError('Порт должен быть числом от1 до65535')
 for name in ('wallet','worker'):
  value=data.get(name)
  if not isinstance(value,str) or not value or len(value)>256 or any(ord(c)<33 or ord(c)>126 for c in value):raise ValueError('Некорректное поле '+name)
 return dict(host=host,port=port,wallet=data['wallet'],worker=data['worker'],profile=str(profile.resolve()),gpu_uuid=GPU,power_limit_w=310)

def read_private(path):
 info=path.lstat()
 if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('Конфиг должен принадлежать пользователю и иметь права0600')
 return json.loads(path.read_text())

def save_private(path,data):
 path=path.absolute();path.parent.mkdir(parents=True,exist_ok=True)
 fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'w') as out:json.dump(data,out,indent=2);out.write('\n')

def host_check(manifest):
 if platform.system()!='Linux' or platform.machine()!='x86_64' or platform.freedesktop_os_release().get('ID')!='linuxmint':raise ValueError('Тестовая сборка предназначена для Linux Mint x86_64')
 libc=platform.libc_ver()[1]
 if tuple(map(int,libc.split('.')[:2]))<tuple(manifest['glibc_min']):raise ValueError('Нужна glibc '+'.'.join(map(str,manifest['glibc_min'])))
 r=subprocess.run(['/usr/bin/nvidia-smi','--id='+GPU,'--query-gpu=uuid,name,power.limit,driver_version','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=5)
 rows=list(csv.reader(io.StringIO(r.stdout),skipinitialspace=True))
 if len(rows)!=1 or len(rows[0])!=4:raise ValueError('Не удалось определить выбранную видеокарту')
 uuid,name,pl,driver=[s.strip() for s in rows[0]]
 if uuid!=GPU or 'RTX 4090' not in name or Decimal(pl)!=Decimal(310):raise ValueError('Выбранная Mint4090 или её PL310 Вт не совпадает с настройками теста')
 if int(driver.split('.')[0])<manifest['driver_major_min']:raise ValueError('Драйвер слишком старый для комплектного CUDA-бинарника')
 return {'gpu':name,'uuid':uuid,'power_limit_w':str(pl),'driver':driver,'glibc':libc}

def runner_security(status,uid):
 fields=dict(line.split(':',1) for line in status.splitlines() if ':' in line)
 if uid!=1000 or fields.get('NoNewPrivs','').strip()!='1' or any(int(fields.get(k,'1').strip(),16)!=0 for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')):raise ValueError('Нужен обычный UID1000 без capabilities и с NoNewPrivileges')

def validate_session(data,config,now,duration,cgroup,active):
 if data.get('schema')!='pearl-test-session-v1':raise ValueError('Нет подтверждённой сессии контроллера')
 pid=data.get('original_pid');ticks=data.get('original_start_ticks')
 if type(pid) is not int or pid<=1 or type(ticks) is not int or ticks<=0:raise ValueError('Некорректная исходная идентичность майнера')
 if data.get('gpu_uuid')!=config['gpu_uuid'] or data.get('power_limit_w')!=310:raise ValueError('Контроллер выбрал другую карту или PL')
 begin=data.get('pause_started_monotonic');end=data.get('deadline_monotonic')
 if not all(type(x) in (int,float) and math.isfinite(x) for x in (begin,end)):raise ValueError('Нет срока безопасной сессии')
 if not 0<=now-begin or not 0<end-begin<=600 or now+duration+20>end:raise ValueError('Недостаточно времени для теста и восстановления')
 target=data.get('cgroup_path');watch=data.get('watchdog_unit')
 if not isinstance(target,str) or not target.startswith('/system.slice/pearl-') or not target.endswith('.service') or cgroup!=target:raise ValueError('Запуск должен принадлежать cgroup контроллера')
 if not isinstance(watch,str) or not re.fullmatch(r'pearl-[A-Za-z0-9_.@-]+\.timer',watch) or not active:raise ValueError('Watchdog восстановления не активен')
 return pid,ticks

def read_session(path,config,duration):
 path=path.absolute()
 for item in (path,*path.parents):
  info=item.lstat()
  if info.st_uid!=0 or stat.S_ISLNK(info.st_mode) or info.st_mode&0o022:raise ValueError('Сессию должен выдавать root-контроллер в защищённом каталоге')
 if not stat.S_ISREG(path.stat().st_mode):raise ValueError('Ожидался обычный файл сессии')
 data=json.loads(path.read_text());cgroups=Path('/proc/self/cgroup').read_text().splitlines();current=next((s.split(':',2)[2] for s in cgroups if s.startswith('0::')),'')
 watch=data.get('watchdog_unit','')
 if not isinstance(watch,str) or not re.fullmatch(r'pearl-[A-Za-z0-9_.@-]+\.timer',watch):raise ValueError('Некорректный watchdog')
 r=subprocess.run(['/usr/bin/systemctl','show',watch,'--property=ActiveState','--value'],capture_output=True,text=True,check=True,timeout=3)
 pid,ticks=validate_session(data,config,time.monotonic(),duration,current,r.stdout.strip()=='active')
 return data,pid,ticks

def format_status(event,row):
 if event=='new_job':return 'Получено новое задание'
 if event=='share_accepted':return 'Шара принята пулом'
 if event=='share_rejected':return 'Шара отклонена: тест останавливается'
 if event=='share_unknown':return 'Ответ на шару не подтверждён: тест останавливается'
 if event=='status':
  rate=row.get('performance',{}).get('fresh_finished_candidates_per_second',0)/1e6
  return f"Скорость: {rate:.2f} млн групп/с | Принято: {row.get('accepted',0)} | Отклонено: {row.get('rejected',0)} | Неизвестно: {row.get('unknown',0)}"
 if event=='final':return f"Тест завершён: {row.get('outcome','—')}. Принято {row.get('accepted',0)}, отклонено {row.get('rejected',0)}, неизвестно {row.get('unknown',0)}"
 if event=='failed':return 'Тест остановлен из-за ошибки; журнал сохранён'
 return None

def validate_singlepass_gate(text):
 rows=[]
 for line in text.splitlines():
  try:row=json.loads(line)
  except ValueError:continue
  if isinstance(row,dict):rows.append(row)
 checks=[r for r in rows if r.get('phase')=='fused_correctness']
 summary=[r for r in rows if r.get('phase')=='fused_comparison']
 legs=[r for r in rows if r.get('phase')=='fused_benchmark']
 if len(checks)!=1 or checks[0].get('singlepass_candidate') is not True or checks[0].get('fixtures')!=10 or checks[0].get('passed') is not True:raise ValueError('Singlepass correctness gate missing')
 if len(summary)!=1 or summary[0].get('baseline')!='original-fused-triple384' or summary[0].get('candidate')!='singlepass-fused-triple384':raise ValueError('Wrong comparison baseline')
 if len(legs)!=4 or [r.get('leg')for r in legs]!=[0,1,2,3] or [r.get('fused')for r in legs]!=[False,True,True,False]:raise ValueError('Incomplete A/B/B/A')
 values=[r.get('combined_compute_filter_ms')for r in legs]
 if any(type(x)not in(int,float) or not math.isfinite(x)or x<=0 for x in values):raise ValueError('Invalid timings')
 ratio=(values[0]+values[3])/(values[1]+values[2]);claimed=summary[0].get('speed_ratio')
 if type(claimed)not in(int,float)or not math.isfinite(claimed)or abs(claimed-ratio)>0.0001*ratio:raise ValueError('Comparison ratio mismatch')
 if ratio<=1.03 or max(values[1],values[2])>=min(values[0],values[3]):raise ValueError('New kernel did not pass speed gate; no live run')
 return {'passed':True,'ratio':ratio,'scope':'resident compute/filter; not full mining hashrate','legs_ms':values}

async def run_pilot(args,config):
 runner_security(Path('/proc/self/status').read_text(),os.geteuid())
 if not 1<=args.duration<=420:raise ValueError('Продолжительность теста:1–420 секунд')
 session,pid,ticks=read_session(args.session,config,args.duration+45)
 os.umask(0o077)
 sys.path.insert(0,str(ROOT/'lib'))
 import pearl_miner as miner
 destination=args.state.absolute();destination.mkdir(mode=0o700,parents=True,exist_ok=False)
 evidence=destination/'evidence';evidence.mkdir(mode=0o700)
 work=destination/'work';work.mkdir(mode=0o700)
 # Canonical config is private and uses the packaged profile, never an arbitrary one.
 runtime=destination/'runtime.json';save_private(runtime,config)
 def emit(event,**row):
  payload={'event':event,**row}
  with (destination/'events.jsonl').open('a') as log:log.write(json.dumps(payload)+'\n')
  line=format_status(event,row)
  if line:print(line,flush=True)
 miner.emit=emit
 options=SimpleNamespace(config=runtime,pipeline=True,gpu_noise=True,kernel_threads=384,triple_stage=True,fused_stage=True,singlepass_transcript=True,two_cta=False,matrix_loads=False,transfer_overlap=False,oracle=ROOT/'bin/pearl-protocol-oracle',producer=ROOT/'bin/pearl-data-producer',engine=ROOT/'bin/pearl-engine',mock_cpu=False,allow_live=True,enable_submit=True,gpu=GPU,expected_power_limit_w=Decimal(310),paused_pid=pid,paused_start_ticks=ticks,sanitizer=False,duration=args.duration,extended_test=True,measure_stability=True,stop_after_accepted=0,max_batches=0,ram_dir=args.ram_dir,workdir=work,evidence=evidence)
 async def monitor():
  while True:
   # Remaining duration is enforced by the miner; retain a20s recovery margin.
   read_session(args.session,config,0)
   await asyncio.sleep(2)
 async def gated_run():
  guard=miner.AsyncGuardChecks(miner.gpu_guard(GPU,Decimal(310),pid,ticks))
  await miner.check_guard(guard,force=True)
  command=[ROOT/'bin/pearl-engine','--run-gpu','--mode','fused-compare','--singlepass-transcript','--triple-stage','--candidate','384','--stage-k','64','--m','8192','--n','8192','--k','4096','--rank','256','--proof-n','16','--duration','1','--warmup','0.25','--rounds','1','--fixtures',ROOT/'share/fixtures','--paused-pid',str(pid),'--paused-start-ticks',str(ticks),'--allow-concurrent-miner']
  log=destination/'singlepass-gate.log'
  await miner.child(command,45,guard,log)
  result=validate_singlepass_gate(log.read_text());(destination/'singlepass-gate.json').write_text(json.dumps(result,indent=2)+'\n')
  read_session(args.session,config,args.duration)
  await miner.main_async(options)
 task=asyncio.create_task(gated_run());watch=asyncio.create_task(monitor())
 loop=asyncio.get_running_loop()
 for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,task.cancel)
 try:
  done,_=await asyncio.wait((task,watch),return_when=asyncio.FIRST_COMPLETED)
  if watch in done:
   await watch
  await task
 finally:
  for t in (task,watch):
   if not t.done():t.cancel()
  await asyncio.gather(task,watch,return_exceptions=True)
  for sig in (signal.SIGINT,signal.SIGTERM):loop.remove_signal_handler(sig)
  print('Процесс теста завершён; восстановление SRBMiner проверяет внешний контроллер.',flush=True)

def main():
 p=argparse.ArgumentParser(description='Pearl Test Miner / fused-triple384 / ограниченный тест Mint4090')
 sub=p.add_subparsers(dest='command',required=True)
 sub.add_parser('version')
 v=sub.add_parser('verify');v.add_argument('--offline',action='store_true')
 c=sub.add_parser('configure');c.add_argument('--import-config',type=Path);c.add_argument('--config',type=Path,default=ROOT/'config.json')
 r=sub.add_parser('run');r.add_argument('--config',type=Path,default=ROOT/'config.json');r.add_argument('--session',type=Path,required=True);r.add_argument('--state',type=Path,required=True);r.add_argument('--ram-dir',type=Path,required=True);r.add_argument('--duration',type=int,default=420)
 args=p.parse_args()
 if args.command=='version':print('Pearl Test Miner '+VERSION+' / fused-triple384 / developer fee0%');return
 manifest=verify_bundle()
 if args.command=='verify':
  loader_check()
  print('Целостность сборки: OK')
  if not args.offline:print(json.dumps(host_check(manifest),ensure_ascii=False))
  print('GPU-вычисления и соединение с пулом не запускались.');return
 if args.command=='configure':
  if args.import_config:data=read_private(args.import_config)
  else:
   host=input('Пул [pearl-eu2.luckypool.io]: ').strip() or 'pearl-eu2.luckypool.io'
   port=int(input('Порт [3360]: ').strip() or '3360')
   wallet=input('Кошелёк Pearl: ').strip();worker=input('Worker [pearl-test-4090]: ').strip() or 'pearl-test-4090'
   data=dict(host=host,port=port,wallet=wallet,worker=worker)
  config=clean_config(data,ROOT/'share/profile.json');save_private(args.config,config)
  print('Конфиг сохранён с правами0600. Кошелёк в журнал не выводится.');return
 host_check(manifest)
 raw=read_private(args.config)
 if raw.get('gpu_uuid')!=GPU or raw.get('power_limit_w')!=310:raise ValueError('Конфигурация рассчитана на выбранную Mint4090 и310 Вт')
 config=clean_config(raw,ROOT/'share/profile.json')
 try:asyncio.run(run_pilot(args,config))
 except asyncio.CancelledError:raise SystemExit(130)

if __name__=='__main__':
 try:main()
 except KeyboardInterrupt:raise SystemExit(130)
 except Exception as error:print('Ошибка: '+str(error),file=sys.stderr);raise SystemExit(1)
