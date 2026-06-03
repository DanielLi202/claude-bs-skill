#!/usr/bin/env python3
"""Codex app-server driver for bs v1.3.8.

Runs one frozen outcome capsule through `codex app-server --listen stdio://`
using `/goal @<outcome.md>`. Captures JSON-RPC requests, raw server output,
stderr, and driver metadata. Launch/handshake transient failures retry; fatal
protocol/auth/capability errors fail fast. No `codex exec` fallback exists.

Transport completion is not work completion: explicit or inferred completion must
pass post-turn semantic validation before exit 0. Silence is telemetry by
default, not a kill condition.
"""
from __future__ import annotations

import argparse, hashlib, json, os, subprocess, sys, threading, time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

class LaunchTransient(Exception): pass
class LaunchFatal(Exception): pass
HARD_REFUSAL_MARKERS=["Blocked: true","required tools are unavailable","goal-backed execution cannot start"]
SOFT_REFUSAL_MARKERS=["I can't proceed","I cannot proceed","unable to proceed"]
WRITE_ACTIONS={"write","edit"}
DRIVER_EVIDENCE_FILES={"raw_vendor_output.jsonl","rpc_requests.jsonl","vendor_stderr.txt","driver_events.jsonl"}
@dataclass
class Snapshot: files: dict[str,str]
@dataclass
class TurnObservation:
    cwd: Path; evidence_dir: Path; final_answer_text: str|None=None; final_answer_seen: bool=False
    command_actions: dict[str,int]=field(default_factory=lambda:{"read":0,"search":0,"write":0,"edit":0})
    final_answer_deltas: dict[str,str]=field(default_factory=dict)
    turn_start_snapshot: Snapshot|None=None; turn_end_snapshot: Snapshot|None=None
    evidence_start_snapshot: Snapshot|None=None; evidence_end_snapshot: Snapshot|None=None
    workspace_delta_files: list[str]=field(default_factory=list); evidence_delta_files: list[str]=field(default_factory=list)
    @property
    def write_action_count(self)->int: return sum(self.command_actions.get(k,0) for k in WRITE_ACTIONS)
    def start(self)->None:
        self.turn_start_snapshot=snapshot_tree(self.cwd,self.evidence_dir); self.evidence_start_snapshot=snapshot_evidence_tree(self.evidence_dir)
    def finish(self)->None:
        self.turn_end_snapshot=snapshot_tree(self.cwd,self.evidence_dir); self.evidence_end_snapshot=snapshot_evidence_tree(self.evidence_dir)
        start=self.turn_start_snapshot.files if self.turn_start_snapshot else {}; end=self.turn_end_snapshot.files if self.turn_end_snapshot else {}
        self.workspace_delta_files=sorted(p for p,d in end.items() if start.get(p)!=d)+[f"{p} (removed)" for p in sorted(p for p in start if p not in end)]
        evs=self.evidence_start_snapshot.files if self.evidence_start_snapshot else {}; eve=self.evidence_end_snapshot.files if self.evidence_end_snapshot else {}
        self.evidence_delta_files=sorted(p for p,d in eve.items() if evs.get(p)!=d)+[f"{p} (removed)" for p in sorted(p for p in evs if p not in eve)]

def _is_relative_to(path:Path,parent:Path)->bool:
    try: path.resolve().relative_to(parent.resolve()); return True
    except ValueError: return False

def _fingerprint(path:Path)->str:
    st=path.stat(); h=hashlib.sha256(); h.update(str(st.st_size).encode()); h.update(str(st.st_mtime_ns).encode()); return h.hexdigest()

def snapshot_tree(cwd:Path,evidence_dir:Path)->Snapshot:
    files={}; er=evidence_dir.resolve()
    for path in cwd.rglob('*'):
        if not path.is_file(): continue
        parts=path.relative_to(cwd).parts
        if '.git' in parts or '__pycache__' in parts or _is_relative_to(path,er): continue
        try: files[path.relative_to(cwd).as_posix()]=_fingerprint(path)
        except OSError: pass
    return Snapshot(files)

def snapshot_evidence_tree(evidence_dir:Path)->Snapshot:
    files={}
    if not evidence_dir.exists(): return Snapshot(files)
    for path in evidence_dir.rglob('*'):
        if not path.is_file(): continue
        try: rel=path.relative_to(evidence_dir).as_posix()
        except ValueError: rel=str(path)
        if rel in DRIVER_EVIDENCE_FILES: continue
        try: files[rel]=_fingerprint(path)
        except OSError: pass
    return Snapshot(files)

def detect_inferred_completion_signal(obj:dict)->str|None:
    method=obj.get('method'); params=obj.get('params') or {}
    if method=='item/completed':
        item=params.get('item') or {}; phase=item.get('phase') or params.get('phase'); typ=item.get('type') or params.get('type'); role=item.get('role') or params.get('role')
        if phase=='final_answer' or (typ in {'message','assistant_message','agentMessage'} and role in {'assistant',None} and phase=='final_answer'): return 'item_completed_final_answer'
    if method=='thread/status/changed':
        status=params.get('status') or (params.get('thread') or {}).get('status')
        if isinstance(status,dict): status=status.get('type')
        if status in {'idle','completed'}: return f'thread_status_{status}'
    return None

def emit_meta(meta:TextIO,**obj:object)->None:
    obj.setdefault('ts',time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())); meta.write(json.dumps(obj,ensure_ascii=False,sort_keys=True)+'\n'); meta.flush()

def _content_text(value:object)->str:
    if isinstance(value,str): return value
    if isinstance(value,list): return ''.join((i.get('text') or i.get('content') or '') for i in value if isinstance(i,dict) and isinstance(i.get('text') or i.get('content') or '',str))
    return ''

def observe_event(obj:dict,obs:TurnObservation)->None:
    method=obj.get('method'); params=obj.get('params') or {}; item=params.get('item') or {}; item=item if isinstance(item,dict) else {}
    if method=='item/agentMessage/delta':
        iid=str(params.get('itemId') or ''); delta=params.get('delta')
        if iid and isinstance(delta,str):
            obs.final_answer_deltas[iid]=obs.final_answer_deltas.get(iid,'')+delta
        return
    actions=item.get('commandActions')
    if isinstance(actions,list):
        for a in actions:
            if isinstance(a,dict) and a.get('type') in obs.command_actions: obs.command_actions[a['type']]+=1
    phase=item.get('phase') or params.get('phase'); typ=item.get('type') or params.get('type')
    text=item.get('text') or _content_text(item.get('content'))
    if method in {'item/completed','item/started'} and phase=='final_answer' and typ in {'agentMessage','message','assistant_message'}:
        iid=str(item.get('id') or ''); text=text or obs.final_answer_deltas.get(iid,'')
        if isinstance(text,str): obs.final_answer_text=text; obs.final_answer_seen=True

def send(proc:subprocess.Popen,rpc:TextIO,i:int,method:str,params:dict)->None:
    req={'jsonrpc':'2.0','id':i,'method':method,'params':params}; line=json.dumps(req,ensure_ascii=False); rpc.write(line+'\n'); rpc.flush(); assert proc.stdin is not None
    try: proc.stdin.write(line+'\n'); proc.stdin.flush()
    except (BrokenPipeError,OSError) as exc: raise LaunchTransient(f'app-server stdin unavailable during {method}: {exc}') from exc

def classify_rpc_error(resp:dict)->LaunchFatal:
    err=resp.get('error'); msg=(err.get('message') if isinstance(err,dict) else str(err)) or json.dumps(err,ensure_ascii=False,sort_keys=True); return LaunchFatal(msg)


class LineQueue:
    def __init__(self):
        self.items=deque(); self.cv=threading.Condition()
    def put(self,item):
        with self.cv:
            self.items.append(item); self.cv.notify()
    def get(self,timeout:float):
        deadline=time.monotonic()+timeout
        with self.cv:
            while not self.items:
                remaining=deadline-time.monotonic()
                if remaining<=0: raise TimeoutError
                self.cv.wait(remaining)
            return self.items.popleft()

def ensure_reader(proc:subprocess.Popen):
    if hasattr(proc, '_bs_line_queue'):
        return proc._bs_line_queue
    q=LineQueue()
    proc._bs_line_queue = q
    proc._bs_pending = []
    def pump(name: str, stream):
        try:
            for line in iter(stream.readline, ''):
                q.put((name, line))
        finally:
            q.put((name, None))
    assert proc.stdout is not None and proc.stderr is not None
    threading.Thread(target=pump, args=('stdout', proc.stdout), daemon=True).start()
    threading.Thread(target=pump, args=('stderr', proc.stderr), daemon=True).start()
    return q

def read_response(proc:subprocess.Popen,raw:TextIO,err:TextIO,target:int,timeout:int)->dict:
    start=time.monotonic(); q=ensure_reader(proc)
    while time.monotonic()-start<timeout:
        if proc.poll() is not None: raise LaunchTransient(f'app-server exited before response id={target} (exit={proc.returncode})')
        try: source,line=q.get(timeout=min(0.5,max(0.01,timeout-(time.monotonic()-start))))
        except TimeoutError: continue
        if not line: continue
        if source=='stdout':
            raw.write(line); raw.flush()
            try: obj=json.loads(line)
            except json.JSONDecodeError: continue
            if obj.get('id')==target:
                if 'error' in obj: raise classify_rpc_error(obj)
                return obj
            proc._bs_pending.append(('stdout_buffered',line))
        else: err.write(line); err.flush()
    raise LaunchTransient(f'timed out waiting for response id={target}')

def kill_proc(proc:subprocess.Popen|None)->None:
    if proc is None: return
    try: proc.kill(); proc.wait(timeout=2)
    except Exception: pass

def _matches_marker(text:str,markers:list[str])->str|None:
    low=text.lower()
    for m in markers:
        if m.lower() in low: return m
    return None

def post_turn_validate(args:argparse.Namespace,obs:TurnObservation,meta:TextIO,completion_event:str,**fields:object)->int:
    obs.finish(); final=obs.final_answer_text or ''; hard=_matches_marker(final,HARD_REFUSAL_MARKERS); soft=_matches_marker(final,SOFT_REFUSAL_MARKERS)
    workspace=bool(obs.workspace_delta_files); evidence=bool(obs.evidence_delta_files); any_delta=workspace or evidence; present=True
    if args.expected_effect_required and args.expected_effect_kind!='none': present={'workspace_delta':workspace,'evidence_delta':evidence,'any_delta':any_delta}[args.expected_effect_kind]
    reason=None
    if hard: reason='semantic_blocked_final_answer' if 'blocked' in hard.lower() else 'semantic_refusal_final_answer'
    elif soft and not present: reason='semantic_refusal_final_answer'
    elif not present: reason='semantic_required_effect_missing'
    payload=dict(expected_effect_kind=args.expected_effect_kind, expected_effect_required=args.expected_effect_required, workspace_delta_files=obs.workspace_delta_files, evidence_delta_files=obs.evidence_delta_files, write_actions=obs.write_action_count, completion_event=completion_event, **fields)
    if reason:
        emit_meta(meta,event='turn_semantic_failed',reason_code=reason,marker=hard or soft,final_answer_seen=obs.final_answer_seen,**payload); return 6
    emit_meta(meta,event=completion_event,semantic_validated=True,**payload); return 0

def wait_for_turn_completion(proc:subprocess.Popen,raw:TextIO,err:TextIO,meta:TextIO,obs:TurnObservation,args:argparse.Namespace)->int:
    start=time.monotonic(); last_stdout=start; last_heartbeat=start; last_report=start; inferred_at=None; inferred_reason=None; soft=False; stale=False; wall=False
    if obs.turn_start_snapshot is None: obs.start()
    q=ensure_reader(proc)
    wall_limit=args.wall_clock_limit_sec or (args.timeout_sec if args.timeout_sec>0 and args.on_wall_clock_limit in {'fail','terminate'} else 0)
    while True:
        now=time.monotonic(); silent=now-last_stdout; elapsed=now-start
        if proc.poll() is not None: emit_meta(meta,event='transport_failed',reason_code='transport_eof_before_completion',exit=proc.returncode); return 2
        if wall_limit>0 and elapsed>wall_limit:
            if not wall: emit_meta(meta,event='turn_wall_clock_limit',reason_code='wall_clock_policy_exceeded',limit_sec=wall_limit,policy=args.on_wall_clock_limit); wall=True
            if args.on_wall_clock_limit in {'fail','terminate'}: kill_proc(proc); return 2
        if args.idle_timeout_sec>0 and silent>args.idle_timeout_sec: emit_meta(meta,event='turn_idle_timeout',idle_timeout_sec=args.idle_timeout_sec); kill_proc(proc); return 2
        if args.silent_soft_limit_sec>0 and not soft and silent>args.silent_soft_limit_sec: emit_meta(meta,event='turn_silent_soft_limit',silent_for_sec=round(silent,3),soft_limit_sec=args.silent_soft_limit_sec); soft=True
        if args.stale_notice_sec>0 and not stale and silent>args.stale_notice_sec: emit_meta(meta,event='turn_progress_stale',stale_for_sec=round(silent,3),stale_notice_sec=args.stale_notice_sec); stale=True
        if args.progress_report_sec>0 and now-last_report>=args.progress_report_sec: emit_meta(meta,event='turn_monitor_snapshot',status='stale' if stale else 'running',elapsed_sec=round(elapsed,3),stale_for_sec=round(silent,3),process_alive=proc.poll() is None,last_progress_kind='stdout' if last_stdout>start else 'none'); emit_meta(meta,event='turn_long_running',elapsed_sec=round(elapsed,3)); last_report=now
        if args.heartbeat_sec>0 and now-last_heartbeat>=args.heartbeat_sec: emit_meta(meta,event='heartbeat',idle_sec=round(silent,3)); last_heartbeat=now
        if inferred_at is not None and now-inferred_at>=args.inferred_completion_sec: return post_turn_validate(args,obs,meta,'turn_completed_inferred',inferred_completion=True,reason=inferred_reason,armed_for_sec=args.inferred_completion_sec)
        pending=getattr(proc,'_bs_pending',[])
        if pending:
            source,line=pending.pop(0)
        else:
            try: source,line=q.get(timeout=0.25)
            except TimeoutError: continue
        if not line: continue
        if source in {'stdout','stdout_buffered'}:
            last_stdout=time.monotonic(); soft=False; stale=False
            if source=='stdout': raw.write(line); raw.flush()
            try: obj=json.loads(line)
            except json.JSONDecodeError: continue
            observe_event(obj,obs)
            if obj.get('method')=='turn/completed':
                status=(obj.get('params') or {}).get('turn',{}).get('status')
                if status=='completed': return post_turn_validate(args,obs,meta,'turn_completed_explicit',status=status)
                emit_meta(meta,event='turn_completed_explicit',status=status); return 2
            reason=detect_inferred_completion_signal(obj)
            if reason and inferred_at is None: inferred_at=time.monotonic(); inferred_reason=reason; emit_meta(meta,event='inferred_completion_armed',reason=reason,delay_sec=args.inferred_completion_sec)
        else: err.write(line); err.flush()

def build_goal_input(outcome_file:Path)->str: return f'/goal @{outcome_file}'
def resolve_codex_bin(args:argparse.Namespace)->str:
    if args.codex_bin: return args.codex_bin
    if os.environ.get('BS_TEST_FAKE_CODEX')=='1': return os.environ.get('CODEX_BIN','codex')
    return 'codex'

def launch_and_handshake(args:argparse.Namespace,raw:TextIO,rpc:TextIO,err:TextIO,meta:TextIO,obs:TurnObservation)->tuple[subprocess.Popen,str]:
    cwd=Path(args.cwd).resolve(); outcome_file=Path(args.outcome_file).resolve(); proc=None; codex_bin=resolve_codex_bin(args)
    try:
        proc=subprocess.Popen([codex_bin,'app-server','--listen','stdio://'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1,cwd=str(cwd))
        send(proc,rpc,1,'initialize',{'clientInfo':{'name':'bs-codex-driver','version':'0.5'},'capabilities':{'experimentalApi':True}}); read_response(proc,raw,err,1,args.handshake_timeout_sec)
        params={'cwd':str(cwd),'approvalPolicy':'never','sandbox':'workspace-write','ephemeral':True}
        if args.model: params['model']=args.model
        send(proc,rpc,2,'thread/start',params); thread=read_response(proc,raw,err,2,args.handshake_timeout_sec); tid=thread['result']['thread']['id']
        obs.start()
        send(proc,rpc,3,'turn/start',{'threadId':tid,'input':[{'type':'text','text':build_goal_input(outcome_file)}],'cwd':str(cwd),'approvalPolicy':'never','sandboxPolicy':{'type':'workspaceWrite','writableRoots':[str(cwd)],'networkAccess':False},'effort':args.effort}); read_response(proc,raw,err,3,args.handshake_timeout_sec)
        return proc,tid
    except LaunchFatal: kill_proc(proc); raise
    except LaunchTransient: kill_proc(proc); raise
    except OSError as exc: kill_proc(proc); raise LaunchTransient(f'spawn failed: {exc}') from exc
    except KeyError as exc: kill_proc(proc); raise LaunchFatal(f'missing expected app-server field: {exc}') from exc

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--cwd',required=True); ap.add_argument('--outcome-file',required=True); ap.add_argument('--evidence-dir',required=True); ap.add_argument('--model',default=None); ap.add_argument('--effort',default='low',choices=['none','minimal','low','medium','high','xhigh']); ap.add_argument('--timeout-sec',type=int,default=0,help='legacy wall-clock limit; ignored unless on-wall-clock-limit is fail/terminate'); ap.add_argument('--wall-clock-limit-sec',type=int,default=0); ap.add_argument('--on-wall-clock-limit',default='mark_stale',choices=['mark_stale','fail','terminate']); ap.add_argument('--idle-timeout-sec',type=int,default=0,help='deprecated hard idle kill; default disabled'); ap.add_argument('--silent-soft-limit-sec',type=int,default=120); ap.add_argument('--stale-notice-sec',type=int,default=1800); ap.add_argument('--progress-report-sec',type=int,default=900); ap.add_argument('--heartbeat-sec',type=int,default=30); ap.add_argument('--inferred-completion-sec',type=int,default=5); ap.add_argument('--handshake-timeout-sec',type=int,default=20); ap.add_argument('--launch-retries',type=int,default=2); ap.add_argument('--launch-backoff',default='1,2'); ap.add_argument('--expected-effect-kind',default='workspace_delta',choices=['workspace_delta','evidence_delta','any_delta','none']); ap.add_argument('--expected-effect-required',default='true',choices=['true','false']); ap.add_argument('--codex-bin',default=None)
    args=ap.parse_args(); args.expected_effect_required=args.expected_effect_required=='true'; cwd=Path(args.cwd).resolve(); outcome=Path(args.outcome_file).resolve()
    if not outcome.exists(): print(f'outcome file not found: {outcome}',file=sys.stderr); return 4
    evidence=Path(args.evidence_dir).resolve(); evidence.mkdir(parents=True,exist_ok=True); backoffs=[int(x) for x in args.launch_backoff.split(',') if x.strip()] or [1]
    with (evidence/'raw_vendor_output.jsonl').open('a',encoding='utf-8') as raw,(evidence/'rpc_requests.jsonl').open('a',encoding='utf-8') as rpc,(evidence/'vendor_stderr.txt').open('a',encoding='utf-8') as err,(evidence/'driver_events.jsonl').open('a',encoding='utf-8') as meta:
        proc=None; obs=TurnObservation(cwd,evidence)
        for attempt in range(args.launch_retries+1):
            emit_meta(meta,event='launch_attempt',attempt=attempt)
            try: proc,_=launch_and_handshake(args,raw,rpc,err,meta,obs); emit_meta(meta,event='launch_ok',attempt=attempt); break
            except LaunchFatal as exc: emit_meta(meta,event='launch_fatal',attempt=attempt,reason=str(exc),reason_code='launch_fatal'); return 4
            except LaunchTransient as exc:
                emit_meta(meta,event='launch_failed',attempt=attempt,reason=str(exc),reason_code='launch_transient')
                if attempt<args.launch_retries: time.sleep(backoffs[min(attempt,len(backoffs)-1)])
        else: emit_meta(meta,event='launch_exhausted',attempts=args.launch_retries+1); return 3
        try:
            assert proc is not None; return wait_for_turn_completion(proc,raw,err,meta,obs,args)
        finally: kill_proc(proc)
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc: print(f'codex_driver failed: {exc}',file=sys.stderr); raise SystemExit(1)
