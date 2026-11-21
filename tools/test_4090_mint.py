#!/usr/bin/env python3
"""Read-only board/PL guard around the compiled harness. Never sets GPU state."""
import argparse,csv,io,json,math,os,platform,shutil,signal,subprocess,sys,tempfile,time
from decimal import Decimal,InvalidOperation
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def parse_board(text):
    rows=list(csv.reader(io.StringIO(text.strip()),skipinitialspace=True))
    if len(rows)!=1 or len(rows[0])!=3:raise ValueError('Expected exactly one GPU')
    uuid,name,watts=(v.strip() for v in rows[0])
    try:limit=Decimal(watts)
    except InvalidOperation as e:raise ValueError('Unreadable power limit') from e
    if not uuid.startswith('GPU-') or 'RTX 4090' not in name:
        raise ValueError('Only the selected RTX 4090 is permitted')
    if not limit.is_finite() or not 0<limit<=2000:raise ValueError('Invalid power limit')
    return uuid,name,limit

def query(smi,selector):
    r=subprocess.run([smi,'--query-gpu=uuid,name,power.limit','--format=csv,noheader,nounits',
                      '--id='+selector],capture_output=True,text=True,check=True,timeout=5)
    return parse_board(r.stdout)

def validation_budget(duration,warmup,rounds,timeout,mode,sanitizer):
    if (not all(math.isfinite(x) for x in (duration,warmup,timeout)) or
        not 1<=duration<=10 or not 0<=warmup<=5 or not 1<=rounds<=3 or
        not 10<=timeout<=60):
        raise ValueError('Invalid validation duration/rounds/timeout')
    scheduled=4*rounds*(duration+warmup)
    if mode=='bench' and (scheduled>45 or timeout<scheduled+10):
        raise ValueError('Benchmark exceeds pause budget or lacks 10s check margin')
    if sanitizer and mode not in ('check','filter-check','pipeline-check','mine-batch','noise-check','compact-check'):
        raise ValueError('Compute Sanitizer is restricted to correctness mode')
    return scheduled if mode=='bench' else 0

def terminate_group(proc):
    # Popen owns a new session. Only terminate this experiment and its descendants.
    try:os.killpg(proc.pid,signal.SIGTERM)
    except ProcessLookupError:return
    try:proc.wait(timeout=2)
    except subprocess.TimeoutExpired:pass
    try:os.killpg(proc.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    proc.wait()

def validate_memcheck(output,returncode,mode="check"):
    if returncode!=0:raise ValueError('Compute Sanitizer exit '+str(returncode))
    import re
    if re.search(r'(?im)^.*\bError:',output):raise ValueError('Sanitizer emitted Error despite exit0')
    summaries=re.findall(r'ERROR SUMMARY:\s*(\d+) errors\b',output)
    if not summaries or any(int(n)!=0 for n in summaries):
        raise ValueError('No clean memcheck summary; GPU gate remains closed')
    if mode=='compact-check':
        leaks=re.findall(r'LEAK SUMMARY:\s*(\d+) bytes leaked in (\d+) allocations\b',output)
        if not leaks or any(int(a) or int(b) for a,b in leaks):
            raise ValueError('No clean leak summary for compact GPU path')
    correctness=False
    filter_passed=False
    for line in output.splitlines():
        try:record=json.loads(line)
        except (ValueError,TypeError):continue
        if isinstance(record,dict) and mode in ('filter-check','pipeline-check','mine-batch','noise-check','compact-check') and record.get('phase')=='hash_filter_correctness':
            filter_passed=(record.get('passed') is True and record.get('official_vectors')==195 and record.get('uniform_context_passed') is True and record.get('capacity_edges_passed') is True)
        if isinstance(record,dict) and mode=='mine-batch' and record.get('phase')=='mining_batch':
            correctness=(record.get('groups')==4 and record.get('hits')==4 and record.get('target_modified') is False)
        if isinstance(record,dict) and mode=='pipeline-check' and record.get('phase')=='pipeline_correctness':
            correctness=(record.get('passed') is True and record.get('groups')==4 and record.get('hits')==2 and record.get('debug_matrix_checked') is True and record.get('non_debug_transcript_checked') is True and record.get('ordered_stream') is True and record.get('network_used') is False)
        if isinstance(record,dict) and mode=='check' and record.get('phase')=='correctness':
            correctness=record.get('passed') is True and record.get('non_debug_transcript_checked') is True
        if isinstance(record,dict) and mode=='noise-check' and record.get('phase')=='noise_correctness':
            correctness=(record.get('passed') is True and record.get('all_A_B_bytes_checked') is True and record.get('matrix_bytes',0)>0 and record.get('rank') in (128,256))
        if isinstance(record,dict) and mode=='compact-check' and record.get('phase')=='compact_filter_correctness':
            correctness=(record.get('passed') is True and record.get('official_vectors')==195 and record.get('capacity_cases')==8 and record.get('append_and_transcript_retention') is True and record.get('exact_target_passed') is True and record.get('empty_preserves_count') is True)
    if mode=='filter-check':correctness=filter_passed
    if mode=='pipeline-check':correctness=correctness and filter_passed
    if not correctness:raise ValueError('No completed debug/non-debug correctness result')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-gpu',action='store_true')
    p.add_argument('--mode',choices=['check','bench','info','filter-check','pipeline-check','mine-batch','noise-check','compact-check'],default='check')
    p.add_argument('--gpu',default='0',help='physical nvidia-smi index or GPU UUID')
    p.add_argument('--expected-power-limit-w',type=Decimal,required=True)
    p.add_argument('--hash-vectors',type=Path,default=ROOT/'pool/hash-vectors.bin')
    p.add_argument('--fixtures',type=Path,default=ROOT/'tests/fixtures')
    p.add_argument('--work-input',type=Path)
    p.add_argument('--noise-reference',type=Path)
    p.add_argument('--paused-pid',type=int)
    p.add_argument('--paused-start-ticks',type=int)
    p.add_argument('--work-output',type=Path)
    p.add_argument('--pipeline-fixture',type=Path)
    p.add_argument('--export-pipeline',type=Path)
    p.add_argument('--export-transcripts',type=Path)
    p.add_argument('--duration',type=float,default=2)
    p.add_argument('--timeout-sec',type=float,default=60)
    p.add_argument('--rounds',type=int,default=1)
    p.add_argument('--warmup',type=float,default=0)
    p.add_argument('--sanitizer',action='store_true',help='existing compute-sanitizer memcheck; check mode only')
    p.add_argument('--allow-concurrent-miner',action='store_true')
    args=p.parse_args()
    if not args.run_gpu:raise ValueError('Explicit --run-gpu is required')
    if not args.expected_power_limit_w.is_finite() or not 0<args.expected_power_limit_w<=2000:
        raise ValueError('Invalid expected power limit')
    scheduled=validation_budget(args.duration,args.warmup,args.rounds,args.timeout_sec,args.mode,args.sanitizer)
    sanitizer=None
    if args.sanitizer:
        # Preparation/download occurs separately, while mining continues.
        # Never use the broken system tool or the CPU-true success gate here.
        sys.path.insert(0,str(ROOT/'tools'))
        from prepare_sanitizer import resolve_bundle,child_env
        sanitizer=resolve_bundle()
    os_release=platform.freedesktop_os_release()
    if platform.system()!='Linux' or os_release.get('ID')!='linuxmint':
        raise ValueError('GPU tests in this package are restricted to Linux Mint')
    smi=shutil.which('nvidia-smi')
    if not smi:raise ValueError('nvidia-smi is unavailable; no test started')
    uuid,name,limit=query(smi,args.gpu)
    if limit!=args.expected_power_limit_w:
        raise ValueError('Current PL differs from the expected PL; no test started')
    exe=ROOT/'build/pearl-bench'
    if not exe.is_file():raise ValueError('Build the harness first')
    help_result=subprocess.run([str(exe),'--help'],capture_output=True,text=True,check=True,timeout=5)
    if '--rounds 1..3' not in help_result.stdout:
        raise ValueError('Stale harness; rebuild the validation revision before any pause')
    if args.mode=='compact-check':
        if 'compact-check' not in help_result.stdout or not args.paused_pid or not args.paused_start_ticks:
            raise ValueError('compact-check needs rebuilt engine and original paused identity')
    if args.mode=='noise-check':
        if 'noise-check' not in help_result.stdout or not args.work_input or not args.noise_reference or not args.paused_pid or not args.paused_start_ticks:
            raise ValueError('noise-check needs reference files and original paused miner identity')
    if args.mode=='mine-batch':
        if 'mine-batch' not in help_result.stdout or not args.work_input or not args.work_output or args.work_output.exists():
            raise ValueError('mine-batch requires rebuilt bench, input and new output')
    if args.mode=='pipeline-check':
        if 'pipeline-check' not in help_result.stdout or not args.pipeline_fixture or not args.export_pipeline or args.export_pipeline.exists():
            raise ValueError('Pipeline requires rebuilt bench, fixture and a new export path')
    if args.mode=='filter-check' and 'filter-check' not in help_result.stdout:
        raise ValueError('Filter check requires rebuilt bench; no test started')
    if args.export_transcripts and '--export-transcripts' not in help_result.stdout:
        raise ValueError('Transcript export requires rebuilt bench; no test started')
    env=child_env(sanitizer) if sanitizer else os.environ.copy();env['CUDA_DEVICE_ORDER']='PCI_BUS_ID';env['CUDA_VISIBLE_DEVICES']=uuid
    command=[str(exe),'--run-gpu','--mode',args.mode,'--device','0',
             '--rounds',str(args.rounds),'--warmup',str(args.warmup),'--candidate','256','--stage-k','64','--duration',str(args.duration),'--fixtures',str(args.fixtures.resolve())]
    if args.mode=='compact-check':command+=['--hash-vectors',str(args.hash_vectors.resolve()),'--paused-pid',str(args.paused_pid),'--paused-start-ticks',str(args.paused_start_ticks)]
    if args.mode=='noise-check':command+=['--work-input',str(args.work_input.resolve()),'--noise-reference',str(args.noise_reference.resolve()),'--paused-pid',str(args.paused_pid),'--paused-start-ticks',str(args.paused_start_ticks)]
    if args.mode=='mine-batch':command+=['--work-input',str(args.work_input.resolve()),'--work-output',str(args.work_output.resolve())]
    if args.mode=='pipeline-check':command+=['--pipeline-fixture',str(args.pipeline_fixture.resolve()),'--export-pipeline',str(args.export_pipeline.resolve()),'--hash-vectors',str(args.hash_vectors.resolve())]
    if args.mode=='filter-check':command+=['--hash-vectors',str(args.hash_vectors.resolve())]
    if args.export_transcripts:command+=['--export-transcripts',str(args.export_transcripts.resolve())]
    if args.allow_concurrent_miner:command.append('--allow-concurrent-miner')
    if sanitizer:command=[sanitizer['executable'],'--injection-path',sanitizer['injection_path'],'--tool','memcheck','--error-exitcode','86','--leak-check','full']+command
    print(json.dumps({'phase':'guard','gpu_uuid':uuid,'model':name,'expected_PL_W':str(limit),
                      'scheduled_seconds_excluding_checks':scheduled,'sanitizer':bool(sanitizer),'sanitizer_executable':sanitizer['executable'] if sanitizer else None,'GPU_settings_changed':False}),flush=True)
    capture=tempfile.TemporaryFile(mode='w+t') if sanitizer else None
    emitted=False
    try:
        proc=subprocess.Popen(command,cwd=ROOT,env=env,start_new_session=True,
            stdout=capture,stderr=subprocess.STDOUT if sanitizer else None)
    except BaseException:
        if capture:capture.close()
        raise
    start=time.monotonic()
    try:
        while proc.poll() is None:
            current_uuid,_,current=query(smi,uuid)
            if current_uuid!=uuid or current!=limit:raise ValueError('GPU/PL changed; remaining test stopped')
            if time.monotonic()-start>args.timeout_sec:raise ValueError('Test timeout')
            time.sleep(0.2)
        final_uuid,_,final_limit=query(smi,uuid)
        if final_uuid!=uuid or final_limit!=limit:raise ValueError('Final PL differs')
        if capture:
            capture.seek(0);output=capture.read();print(output,end='',flush=True);emitted=True
            validate_memcheck(output,proc.returncode,args.mode)
        print(json.dumps({'phase':'guard_final','PL_W':str(final_limit),'unchanged':True,
                          'child_exit_code':proc.returncode}),flush=True)
        return proc.returncode
    finally:
        terminate_group(proc)
        if capture:
            if not emitted:
                capture.seek(0);print(capture.read(),end='',flush=True)
            capture.close()

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as e:
        print('ERROR: '+str(e),file=sys.stderr);sys.exit(1)
