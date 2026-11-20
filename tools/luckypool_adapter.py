#!/usr/bin/env python3
"""Offline LuckyPool plain-job adapter. No sockets, credentials lookup or transmission."""
import argparse,base64,hashlib,json,re,struct
from dataclasses import dataclass
from pathlib import Path
MAX256=(1<<256)-1

def integer(x,label,low,high):
 if type(x) is not int or not low<=x<=high:raise ValueError('Invalid '+label)
 return x

def hex_bytes(value,size,label):
 if not isinstance(value,str) or re.fullmatch(r'[0-9a-fA-F]{'+str(size*2)+'}',value) is None:raise ValueError('Invalid '+label)
 return bytes.fromhex(value)

@dataclass(frozen=True)
class Job:
 job_id:str
 header:bytes
 target:int
 cert_version:int
 height:int|None
 @classmethod
 def parse(cls,message):
  if 'notify_params' in message:p=message['notify_params']
  elif message.get('method')=='mining.notify':p=message['params']
  else:raise ValueError('Expected mining.notify or captured notify_params')
  if not isinstance(p,dict):raise ValueError('notify params must be an object')
  cert=integer(p.get('cert_version'),'cert_version',3,3)
  header=hex_bytes(p.get('header'),76,'header')
  target=int.from_bytes(hex_bytes(p.get('target'),32,'target'),'big')
  if target==0:raise ValueError('Zero target')
  jid=p.get('job_id')
  if not isinstance(jid,str) or not 1<=len(jid.encode())<=256 or any(ord(c)<32 for c in jid):raise ValueError('Invalid job_id')
  height=p.get('height')
  if height is not None:integer(height,'height',0,0xffffffff)
  return cls(jid,header,target,cert,height)
 def fingerprint(self):
  jid=self.job_id.encode()
  payload=b'pearl-pool-job-v1\0'+self.header+struct.pack('<I',self.cert_version)+self.target.to_bytes(32,'big')+struct.pack('<I',len(jid))+jid
  return hashlib.sha256(payload).hexdigest()
 def describe(self):
  version,=struct.unpack_from('<I',self.header,0);timestamp,nbits=struct.unpack_from('<II',self.header,68)
  return {'job_id':self.job_id,'height':self.height,'cert_version':self.cert_version,'seed_rule':'Salted_V3',
   'header_hex':self.header.hex(),'header_version':version,'previous_block':self.header[4:36][::-1].hex(),
   'merkle_root':self.header[36:68][::-1].hex(),'timestamp':timestamp,'block_nbits':f'{nbits:08x}',
   'share_base_target_hex':f'{self.target:064x}','job_fingerprint':self.fingerprint()}

@dataclass(frozen=True)
class Profile:
 m:int;n:int;k:int;rank:int;rows:tuple;columns:tuple
 @classmethod
 def parse(cls,p):
  if p.get('mma_type')!=0 or type(p.get('mma_type')) is not int:raise ValueError('Only INT7 MMA is supported')
  m=integer(p.get('m'),'m',1,1<<24);n=integer(p.get('n'),'n',1,1<<24)
  k=integer(p.get('k'),'k',1024,65536);rank=integer(p.get('rank'),'rank',128,1024)
  if rank&(rank-1) or k%64 or k%rank or not 16*rank<=k<=4*rank*rank:raise ValueError('Invalid K/rank relationship')
  patterns=[]
  for label,bound in [('row_pattern',m),('column_pattern',n)]:
   x=p.get(label)
   if not isinstance(x,list) or not x:raise ValueError('Missing '+label)
   for v in x:integer(v,label,0,bound-1)
   if x!=sorted(set(x)) or x[0]!=0:raise ValueError('Pattern must be sorted unique and start at zero')
   patterns.append(tuple(x))
  rows,columns=patterns
  # This adapter only selects shapes handled by the tested stage64 backend.
  if len(rows)!=16 or len(columns) not in (8,16):raise ValueError('Unsupported stage64 proof geometry')
  return cls(m,n,k,rank,rows,columns)
 def factor(self):return len(self.rows)*len(self.columns)*(self.k//self.rank)*128
 def bound(self,job):
  factor=self.factor()
  if job.target>MAX256//factor:raise ValueError('Scaled share target overflows U256')
  return job.target*factor
 def qualifies(self,job,digest):
  if len(digest)!=32:raise ValueError('Digest must be32 bytes')
  return int.from_bytes(digest,'little')<=self.bound(job)
 def describe(self,job):
  return {'m':self.m,'n':self.n,'k':self.k,'rank':self.rank,'mma_type':0,'row_pattern':list(self.rows),'column_pattern':list(self.columns),
   'target_policy':'official_rank_penalized','pool_target_policy_confirmed':False,'rank_penalized_factor':self.factor(),'share_bound_hex':f'{self.bound(job):064x}',
   'share_bound_GPU_little_endian_hex':self.bound(job).to_bytes(32,'little').hex(),'pool_policy_verified':False}

class JobBook:
 """A notify change invalidates previously bound candidates; owns no network connection."""
 def __init__(self):self.current=None
 def update(self,job):self.current=job
 def require_current(self,job):
  if self.current is None or job.fingerprint()!=self.current.fingerprint():raise ValueError('Stale job')

def submit_frame(job,profile,proof_bytes,report,wallet,worker,book):
 """Build bytes only after verifier report and exact-target gate. Never send."""
 book.require_current(job)
 if not proof_bytes or len(proof_bytes)>4*1024*1024:raise ValueError('Invalid proof size')
 if report.get('job_fingerprint')!=job.fingerprint() or report.get('proof_sha256')!=hashlib.sha256(proof_bytes).hexdigest():raise ValueError('Proof/context binding differs')
 if report.get('structural_verifier_passed') is not True:raise ValueError('Proof structure has not passed official verifier')
 for key,value in [('m',profile.m),('n',profile.n),('k',profile.k),('rank',profile.rank),('row_pattern',list(profile.rows)),('column_pattern',list(profile.columns))]:
  if report.get(key)!=value:raise ValueError('Verifier configuration differs: '+key)
 digest=hex_bytes(report.get('jackpot_hash'),32,'jackpot hash')
 if not profile.qualifies(job,digest) or report.get('share_target_passed') is not True:raise ValueError('Candidate does not meet exact share target')
 if not wallet or not worker or not isinstance(wallet,str) or not isinstance(worker,str):raise ValueError('Local wallet/worker required')
 params={'wallet':wallet,'worker':worker,'job_id':job.job_id,'plain_proof':base64.b64encode(proof_bytes).decode()}
 return (json.dumps({'id':99,'method':'mining.submit','params':params},separators=(',',':'))+'\n').encode()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True);p.add_argument('--profile',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
 job=Job.parse(json.loads(args.job.read_text()));profile=Profile.parse(json.loads(args.profile.read_text()))
 result={'job':job.describe(),'chosen_profile':profile.describe(job),'network_enabled':False,'submit_sent':False,'captured_job_not_live_authorization':True}
 args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2)+'\n')
 print('Offline job/target plan saved; no socket or GPU work')
if __name__=='__main__':main()
