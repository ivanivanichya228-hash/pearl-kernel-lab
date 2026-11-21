"""One bounded offline A/B/B/A of SAME full raw inputs, all at kernel384; no pool connection."""
import argparse,asyncio,json,os,time,platform
from decimal import Decimal
from pathlib import Path
from queued_engine import QueuedEngine
from pearl_miner import gpu_guard
def live_decision(legs,gpu_executed):
 controls=[x['timed_pair_wall_seconds'] for x in legs if x['mode']=='control'];candidates=[x['timed_pair_wall_seconds'] for x in legs if x['mode']=='overlap'];ratio=sum(controls)/sum(candidates)
 demonstrated=all(x['timed_H2D_compute_stream_intersection_ms']>=max(1,.1*x['timed_H2D_phase_ms']) for x in legs if x['mode']=='overlap')
 return ratio,bool(gpu_executed and ratio>1.02 and max(candidates)<min(controls) and demonstrated)
async def main(args):
 inputs=json.loads(args.inputs.read_text());assert inputs['local_benchmark_only'] is True;inputs=inputs['inputs'];assert len(inputs)==2 and inputs[0]['batch_id']!=inputs[1]['batch_id']
 for item in inputs:
  p=item['profile'];shape=tuple(p[k] for k in ('m','n','k','rank'))
  if not args.mock_cpu and (shape!=(131072,131072,4096,256) or len(p['column_pattern'])!=16):raise ValueError('GPU comparison requires exact full profile')
  if args.mock_cpu and p['m']*p['n']*p['k']>1<<26:raise ValueError('CPU mock comparison must be small')
  path=Path(item['raw_manifest']);assert path.stat().st_size==188 and path.read_bytes()[:8]==b'PRLRAWN1';assert json.loads((path.parent/'work.json').read_text())['batch_id']==item['batch_id']
 if args.out.exists():raise ValueError('NEW output directory required')
 args.out.mkdir(parents=True,mode=0o700);expected={};legs=[];guard=None
 if not args.mock_cpu:
  if not args.run_gpu:raise ValueError('Explicit --run-gpu required')
  if platform.freedesktop_os_release().get('ID')!='linuxmint':raise ValueError('GPU comparison restricted to Linux Mint')
  available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
  if available<16*1024**3:raise ValueError('Need at least16GiB available RAM before pinned comparison')
  guard=gpu_guard(args.gpu,args.expected_power_limit_w,args.paused_pid,args.paused_start_ticks);guard();os.environ['CUDA_DEVICE_ORDER']='PCI_BUS_ID';os.environ['CUDA_VISIBLE_DEVICES']=args.gpu
 for index,mode in enumerate(('control','overlap','overlap','control')):
  folder=args.out/str(index);folder.mkdir(mode=0o700)
  argv=[args.engine,'--queued-serve' if mode=='overlap' else '--serve'] if args.mock_cpu else [args.engine,'--run-gpu','--mode','overlap-worker' if mode=='overlap' else 'worker','--candidate','384','--allow-concurrent-miner','--paused-pid',str(args.paused_pid),'--paused-start-ticks',str(args.paused_start_ticks)]
  engine=QueuedEngine(argv,guard,folder,timeout=30,expected_protocol=2 if mode=='overlap' else 1)
  try:
   await engine.start()
   for phase in ('warm','timed'):
    started=time.monotonic();tickets=[await engine.submit(Path(item['raw_manifest']),folder/f'{phase}-{i}.json') for i,item in enumerate(inputs)];await asyncio.gather(*(engine.wait(t) for t in tickets));wall=time.monotonic()-started
    for i,item in enumerate(inputs):
     got=json.loads((folder/f'{phase}-{i}.json').read_text());assert got['GPU_executed'] is (not args.mock_cpu);assert got['batch_id']==item['batch_id'];got['hits'].sort(key=lambda h:h['index'])
     if i in expected:assert got==expected[i],'transfer changed actual hit/transcript data'
     else:expected[i]=got
    if phase=='timed':timed=wall
  finally:await engine.close()
  assert engine.proc.returncode==0 and not engine.shutdown_forced,'comparison worker did not close cleanly'
  records=[json.loads(line) for line in (folder/'persistent-engine.events.jsonl').read_text().splitlines()];stages={r['seq']:r for r in records if r.get('phase')=='transfer_stage'};overlap_ms=0;copy_ms=0
  if mode=='overlap' and not args.mock_cpu:
   assert len(stages)==4 and all(r['pinned'] is True for r in stages.values())
   previous,current=stages[3],stages[4];copy_ms=current['copy_end_ms']-current['copy_begin_ms'];overlap_ms=max(0,min(previous['compute_end_ms'],current['copy_end_ms'])-max(previous['compute_begin_ms'],current['copy_begin_ms']))
   assert current['slot']!=previous['slot'];assert all(r.get('kernel_threads')==384 for r in records if r.get('phase')=='mining_batch')
  legs.append({'leg':index,'mode':mode,'timed_pair_wall_seconds':timed,'timed_H2D_compute_stream_intersection_ms':overlap_ms,'timed_H2D_phase_ms':copy_ms,'worker':engine.describe()})
 ratio,go=live_decision(legs,not args.mock_cpu)
 result={'scope':'fixed LOCAL raw inputs, two warm and two timed packets per fresh leg, no pool or hashrate claim','GPU_executed':not args.mock_cpu,'legs':legs,'speed_ratio':ratio,'candidate_faster_for_live':go,'all_actual_hits_and_transcripts_identical':True,'pool_shares_sent':0};(args.out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
def cli():
 p=argparse.ArgumentParser();p.add_argument('--engine',type=Path,required=True);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--run-gpu',action='store_true');p.add_argument('--mock-cpu',action='store_true');p.add_argument('--gpu');p.add_argument('--expected-power-limit-w',type=Decimal);p.add_argument('--paused-pid',type=int);p.add_argument('--paused-start-ticks',type=int);args=p.parse_args();args.engine=args.engine.resolve();asyncio.run(main(args))
if __name__=='__main__':cli()
