"""Bounded scalar384 diagnostics; no pool, miner controls, installs or GPU setters."""
import argparse,asyncio,csv,hashlib,io,json,math,os,platform,re,shutil,subprocess,sys
from decimal import Decimal
from pathlib import Path
# -I ignores cwd/user-site/PYTHONPATH; the counter scope uses a root-owned trusted copy.
sys.path.insert(0,str(Path(__file__).resolve().parent))
from pearl_miner import child,gpu_guard
from counter_access import current_access
ROOT=Path(__file__).resolve().parents[1]
SECTIONS=('SpeedOfLight','Occupancy','SchedulerStats','WarpStateStats','MemoryWorkloadAnalysis')

def counter_command(ncu,engine,pid,ticks,report):
 return [str(ncu),'--clock-control','none','--cache-control','none','--replay-mode','kernel',
  '--kernel-name-base','demangled','--kernel-name','regex:.*(pearl_int8|compact_filter_kernel).*',
  '--launch-skip','6','--launch-count','2',*[x for s in SECTIONS for x in ('--section',s)],
  '--page','raw','--csv','--export',str(report),str(engine),'--run-gpu','--mode','kernel-counters',
  '--candidate','384','--stage-k','64','--allow-concurrent-miner','--paused-pid',str(pid),'--paused-start-ticks',str(ticks)]

def timing_summary(text):
 records=[]
 for line in text.splitlines():
  try:r=json.loads(line)
  except ValueError:continue
  if isinstance(r,dict):records.append(r)
 rows=[r for r in records if r.get('phase')=='diagnostic_sample']
 summaries=[r for r in records if r.get('phase')=='diagnostic_summary']
 if len(rows)!=32 or [r.get('iteration') for r in rows]!=list(range(32)) or len(summaries)!=1:raise ValueError('Incomplete diagnostic sequence')
 for r in rows:
  if not all(type(r.get(k)) in (int,float) and math.isfinite(r[k]) and r[k]>0 for k in ('gemm_ms','filter_ms')):raise ValueError('Invalid event timing')
 s=summaries[0]
 if any(s.get(k) is not v for k,v in {'matrix_loads':False,'resident_input_only':True,'includes_CPU_prepare':False,'includes_H2D':False,'event_instrumented':True,'pool_connected':False,'hashrate_measured':False}.items()) or s.get('kernel_threads')!=384 or s.get('samples')!=32 or s.get('shares_sent')!=0:raise ValueError('Wrong diagnostic scope')
 g=sum(r['gemm_ms'] for r in rows);h=sum(r['filter_ms'] for r in rows)
 for key,total in (('gemm_total_ms',g),('filter_total_ms',h)):
  if not math.isclose(s.get(key,float('nan')),total,rel_tol=2e-5,abs_tol=.002):raise ValueError('Timing sum mismatch')
 return {'GPU_executed':True,'scope':'resident repeated scalar384 slab, event-instrumented, not full mining',
  'gemm_fraction':g/(g+h),'filter_fraction':h/(g+h),'gemm_mean_ms':g/32,'filter_mean_ms':h/32,
  'shares_sent':0,'real_hashrate_measured':False,'hardware_counters_collected':False,
  'cause_of_kernel_stalls_established':False,'summary':s,'samples':rows}

def counter_summary(text):
 if '==ERROR==' in text or 'ERR_NVGPUCTRPERM' in text:raise ValueError('Profiler reported an error')
 completed=[]
 for line in text.splitlines():
  try:r=json.loads(line)
  except ValueError:continue
  if isinstance(r,dict) and r.get('phase')=='counter_targets_completed':completed.append(r)
 if len(completed)!=1:raise ValueError('Native counter targets did not complete')
 r=completed[0]
 if r.get('kernel_threads')!=384 or r.get('matrix_loads') is not False or r.get('warm_matching_launches')!=6 or r.get('profile_matching_launches')!=2 or r.get('timings_valid') is not False or r.get('pool_connected') is not False or r.get('shares_sent')!=0:raise ValueError('Wrong counter target scope')
 header=None;metrics={}
 for row in csv.reader(io.StringIO(text)):
  if all(k in row for k in ('Kernel Name','Metric Name','Metric Value')):header=row;continue
  if header and len(row)==len(header) and ('ID' not in header or row[header.index('ID')].isdigit()):
   data=dict(zip(header,row));name=data['Kernel Name'];metrics.setdefault(name,{})[data['Metric Name']]=data['Metric Value']
 if len(metrics)!=2 or not any('pearl_int8' in n for n in metrics) or not any('compact_filter_kernel' in n for n in metrics):raise ValueError('Expected exactly GEMM and filter counter targets')
 for values in metrics.values():
  for name in ('gpu__time_duration.sum','sm__throughput.avg.pct_of_peak_sustained_elapsed'):
   try:value=float(values[name].replace(',',''))
   except (KeyError,ValueError):raise ValueError('Missing actual hardware metric: '+name) from None
   if not math.isfinite(value) or value<0:raise ValueError('Invalid hardware metric: '+name)
 return {'kernel_names':sorted(metrics),'metrics':metrics,'native_completion':r}

def probe_ncu(explicit=None):
 paths=[Path(explicit)] if explicit else [Path(p) for p in [shutil.which('ncu')] if p]
 if not explicit:
  for pattern in ('/opt/nvidia/nsight-compute/*/ncu','/opt/nvidia/nsight-compute/*/target/linux-desktop-glibc_2_11_3-x64/ncu','/usr/local/cuda*/nsight-compute*/ncu','/usr/local/cuda*/NsightCompute*/ncu'):
   import glob
   paths.extend(Path(p) for p in glob.glob(pattern))
 params=Path('/proc/driver/nvidia/params');restricted=None
 if params.is_file():
  match=re.search(r'^RmProfilingAdminOnly:\s*([01])\s*$',params.read_text(),re.M)
  if match:restricted=bool(int(match.group(1)))
 facts={'GPU_executed':False,'ncu':None,'known_admin_only_counters':restricted,'installation_performed':False,'permission_changes':False,'counter_access':current_access()}
 for path in dict.fromkeys(paths):
  if not path.is_file() or not os.access(path,os.X_OK):continue
  version=subprocess.run([str(path),'--version'],capture_output=True,text=True,timeout=5)
  help_result=subprocess.run([str(path),'--help'],capture_output=True,text=True,timeout=5)
  sections=subprocess.run([str(path),'--list-sections'],capture_output=True,text=True,timeout=5)
  text=help_result.stdout+help_result.stderr;section_text=sections.stdout+sections.stderr
  if any(r.returncode for r in (version,help_result,sections)):continue
  if not all(flag in text for flag in ('clock-control','cache-control','launch-skip','launch-count','kernel-name-base')):continue
  if not all(s in section_text for s in SECTIONS):continue
  facts.update(ncu=str(path.resolve()),ncu_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),version=version.stdout.strip(),sections=list(SECTIONS))
  break
 return facts

async def run(args):
 if args.out.exists():raise ValueError('NEW private output directory required')
 args.out.mkdir(parents=True,mode=0o700)
 if args.preflight:
  result=probe_ncu(args.ncu);(args.out/'preflight.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return
 if not args.run_gpu or not args.gpu or not args.paused_pid or not args.paused_start_ticks or args.expected_power_limit_w!=Decimal(310):raise ValueError('Explicit selected4090/310W/paused identity required')
 if platform.freedesktop_os_release().get('ID')!='linuxmint':raise ValueError('Mint4090 only')
 engine=args.engine.resolve()
 if args.kind=='counters':
  if not args.ncu:raise ValueError('Use the preflight-verified profiler path')
  facts=probe_ncu(args.ncu)
  if not facts['ncu']:raise ValueError('Profiler preflight failed; no GPU work')
  if os.geteuid()!=1000:raise ValueError('Counter collection must remain UID1000, not root')
  if facts['known_admin_only_counters'] is not False and not facts['counter_access']['ambient_perfmon_scope_valid']:raise ValueError('Admin-only/unknown counter policy requires a verified transient PERFMON-only scope')
  argv=counter_command(facts['ncu'],engine,args.paused_pid,args.paused_start_ticks,args.out/'hardware')
 else:
  argv=[engine,'--run-gpu','--mode','kernel-diagnose','--candidate','384','--stage-k','64','--allow-concurrent-miner','--paused-pid',args.paused_pid,'--paused-start-ticks',args.paused_start_ticks]
 guard=gpu_guard(args.gpu,args.expected_power_limit_w,args.paused_pid,args.paused_start_ticks);guard()
 os.environ['CUDA_DEVICE_ORDER']='PCI_BUS_ID';os.environ['CUDA_VISIBLE_DEVICES']=args.gpu
 log=args.out/'raw.log';await child(argv,30 if args.kind=='counters' else 15,guard,log);guard();text=log.read_text()
 if args.kind=='timing':result=timing_summary(text)
 else:
  report=args.out/'hardware.ncu-rep'
  if not report.is_file() or not report.stat().st_size:raise ValueError('Counter report absent/empty; retain full raw log')
  detail=counter_summary(text)
  result={'GPU_executed':True,'hardware_counters_collected':True,**detail,'shares_sent':0,'real_hashrate_measured':False,'instrumented_timings_are_not_benchmark_results':True,'profiler':facts}
 (args.out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

def cli():
 p=argparse.ArgumentParser();p.add_argument('--preflight',action='store_true');p.add_argument('--run-gpu',action='store_true');p.add_argument('--kind',choices=['timing','counters'],default='timing');p.add_argument('--ncu',type=Path);p.add_argument('--engine',type=Path,default=ROOT/'build/pearl-bench');p.add_argument('--out',type=Path,required=True);p.add_argument('--gpu');p.add_argument('--expected-power-limit-w',type=Decimal);p.add_argument('--paused-pid',type=int);p.add_argument('--paused-start-ticks',type=int);args=p.parse_args();asyncio.run(run(args))
if __name__=='__main__':cli()
