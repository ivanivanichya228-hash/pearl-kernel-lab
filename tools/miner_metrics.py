"""Wall-time mining-work accounting. No pool-hashrate or SRBMiner-unit equivalence assumed."""
import time
class Performance:
 def __init__(self,profile,clock=time.monotonic):
  self.profile=profile;self.clock=clock;self.started=clock();self.stages={};self.work={};self.identities=set()
 def stage(self,name,seconds,outcome):
  if name not in ('prepare','GPU','proofs') or seconds<0:raise ValueError('Invalid stage measurement')
  totals=self.stages.setdefault(name,{'seconds':0.0,'completed':0,'cancelled':0,'failed':0});totals['seconds']+=seconds;totals[outcome]+=1
 def gpu_complete(self,batch,identity,groups):
  expected=(self.profile.m//len(self.profile.rows))*(self.profile.n//len(self.profile.columns))
  if groups!=expected or batch in self.work or identity in self.identities:raise ValueError('Wrong or duplicate measured work')
  if len(self.work)>=65536:raise ValueError('Measurement ledger bound exceeded')
  self.identities.add(identity);self.work[batch]={'groups':groups,'outcome':'pending'}
 def classify(self,batch,outcome):
  if outcome not in ('fresh','stale'):raise ValueError('Invalid work classification')
  if batch in self.work:self.work[batch]['outcome']=outcome
 def snapshot(self):
  elapsed=max(0.0,self.clock()-self.started);p=self.profile
  groups=sum(w['groups'] for w in self.work.values());fresh=sum(w['groups'] for w in self.work.values() if w['outcome']=='fresh');stale=sum(w['groups'] for w in self.work.values() if w['outcome']=='stale');pending=groups-fresh-stale
  operations_per_group=2*len(p.rows)*len(p.columns)*p.k
  result={'wall_seconds':elapsed,'completed_GPU_or_CPU_batches':len(self.work),'completed_candidate_groups':groups,'fresh_finished_candidate_groups':fresh,'stale_completed_candidate_groups':stale,'unclassified_completed_candidate_groups':pending,'partial_or_cancelled_GPU_work_credited':False,'stages':{k:dict(v) for k,v in self.stages.items()},'arithmetic_operation_convention':'2 operations per dense multiply-add; not assumed equal to pool or SRBMiner TH/s','stage_times_may_overlap':True,'pool_hashrate_measured':False,'SRBMiner_speedup_measured':False}
  if elapsed:
   result.update(completed_candidates_per_second=groups/elapsed,fresh_finished_candidates_per_second=fresh/elapsed,completed_dense_arithmetic_TOP_s=groups*operations_per_group/elapsed/1e12,fresh_finished_dense_arithmetic_TOP_s=fresh*operations_per_group/elapsed/1e12,official_target_weight_units_per_second=fresh*p.factor()/elapsed)
  return result
