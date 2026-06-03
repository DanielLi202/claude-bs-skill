#!/usr/bin/env python3
"""Deterministic lint for bs Grade artifacts."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None
BLOCKING={"P0","P1"}
SURFACES={"process","background_process","runtime_files","identity_sentinel","network_probe","auth_or_secret","file_modes","concurrency_or_locking","destructive_operation","external_subprocess"}
class LintError(ValueError): pass
def blocks(path:Path)->list[dict[str,Any]]:
    if yaml is None: raise LintError("PyYAML is required")
    if not path.exists(): raise LintError(f"file missing: {path}")
    out=[]; lines=path.read_text(encoding='utf-8').splitlines(); i=0
    while i<len(lines):
        if lines[i].strip() in {'```yaml','```yml'}:
            j=i+1
            while j<len(lines) and lines[j].strip()!='```': j+=1
            if j>=len(lines): raise LintError(f"unterminated yaml fence in {path}")
            data=yaml.safe_load('\n'.join(lines[i+1:j]) or 'null')
            if isinstance(data,dict): out.append(data)
            i=j
        i+=1
    return out
def first(bs,key):
    return next((b[key] for b in bs if key in b), None)
def nni(v): return isinstance(v,int) and not isinstance(v,bool) and v>=0
def is_gate(t,r): return t=='code' and r in {'medium','high'}
def strs(v): return [v] if isinstance(v,str) else (v if isinstance(v,list) and all(isinstance(x,str) for x in v) else [])
def sev(row):
    if not isinstance(row,dict): return None
    v=row.get('severity') or row.get('severity_if_fail')
    return v if v in {'P0','P1','P2'} else None
def has_ref(row):
    return any(isinstance(row.get(k),str) and row.get(k).strip() for k in ('evidence_ref','acceptance_id','acceptance_ref','tracked_waiver_ref','maintainer_waiver_ref','user_waiver_ref'))
def validate_required(summary, acceptance, errors):
    if not isinstance(summary,dict): errors.append('missing or malformed grade_summary block')
    else:
        for k in ('p0_count','p1_count','p2_count'):
            if not nni(summary.get(k)): errors.append(f'grade_summary.{k} must be a non-negative integer')
    if not isinstance(acceptance,list): errors.append('missing or malformed acceptance_status block'); return
    for i,row in enumerate(acceptance):
        if not isinstance(row,dict): errors.append(f'acceptance_status[{i}] must be an object'); continue
        if not isinstance(row.get('id'),str) or not row.get('id'): errors.append(f'acceptance_status[{i}].id is required')
        if row.get('status') not in {'pass','fail'}: errors.append(f'acceptance_status[{i}].status must be pass|fail')
        if row.get('status')=='fail' and row.get('severity') not in {'P0','P1','P2'}: errors.append(f'acceptance_status[{i}].severity is required for fail')
def validate_outcome(bs,errors):
    rs=first(bs,'risk_surface'); adv=first(bs,'adversarial_acceptance')
    if not isinstance(rs,dict): errors.append('medium/high code outcome missing parseable risk_surface block'); return
    surfaces=rs.get('surfaces')
    if not isinstance(surfaces,dict): errors.append('risk_surface.surfaces must be a mapping'); return
    present=set()
    for name,detail in surfaces.items():
        if name not in SURFACES: continue
        if detail is True or (isinstance(detail,dict) and detail.get('present') is True): present.add(name)
        if isinstance(detail,dict) and detail.get('not_applicable') is True and not detail.get('reason'): errors.append(f'risk_surface.surfaces.{name} not_applicable requires reason')
    if present and (not isinstance(adv,list) or not adv): errors.append('medium/high code outcome with present risk surfaces requires adversarial_acceptance entries'); return
    covered=set()
    if isinstance(adv,list):
        for i,row in enumerate(adv):
            if not isinstance(row,dict): errors.append(f'adversarial_acceptance[{i}] must be an object'); continue
            if not isinstance(row.get('id'),str) or not row.get('id'): errors.append(f'adversarial_acceptance[{i}].id is required')
            if row.get('severity') not in {'P0','P1','P2'}: errors.append(f'adversarial_acceptance[{i}].severity must be P0|P1|P2')
            covered.update(set(strs(row.get('surface') or row.get('surfaces'))) & present)
            if not isinstance(row.get('verification_hint'),str) or not row.get('verification_hint').strip(): errors.append(f'adversarial_acceptance[{i}].verification_hint is required')
    missing=sorted(present-covered)
    if missing: errors.append('present risk surfaces without adversarial_acceptance coverage: '+','.join(missing))

def adversarial_acceptance_ids(outcome_file: Path) -> set[str]:
    ids: set[str] = set()
    adv = first(blocks(outcome_file), 'adversarial_acceptance')
    if isinstance(adv, list):
        for row in adv:
            if isinstance(row, dict) and isinstance(row.get('id'), str) and row.get('id'):
                ids.add(row['id'])
    return ids

def validate_adv(summary,bs,errors,required_acceptance_ids=None):
    checks=first(bs,'adversarial_checks'); inv=first(bs,'trust_surface_inventory'); deferred=first(bs,'deferred_claims')
    if not isinstance(checks,list): errors.append('medium/high code grade missing parseable adversarial_checks block'); checks=[]
    if not isinstance(inv,dict): errors.append('medium/high code grade missing parseable trust_surface_inventory block'); inv={}
    if not isinstance(deferred,list): errors.append('medium/high code grade missing parseable deferred_claims block'); deferred=[]
    calc={'P0':0,'P1':0}
    covered_acceptance_ids=set()
    for i,row in enumerate(checks):
        if not isinstance(row,dict): errors.append(f'adversarial_checks[{i}] must be an object'); continue
        st=row.get('status'); sv=row.get('severity_if_fail')
        for k in ('id','acceptance_id','acceptance_ref'):
            if isinstance(row.get(k), str) and row.get(k): covered_acceptance_ids.add(row.get(k))
        if not isinstance(row.get('id'),str) or not row.get('id'): errors.append(f'adversarial_checks[{i}].id is required')
        if st not in {'pass','fail','unverified','not_applicable'}: errors.append(f'adversarial_checks[{i}].status must be pass|fail|unverified|not_applicable'); continue
        if sv not in {'P0','P1','P2'}: errors.append(f'adversarial_checks[{i}].severity_if_fail must be P0|P1|P2'); continue
        if st in {'fail','unverified'} and sv in BLOCKING: calc[sv]+=1; errors.append(f"adversarial_checks[{i}] {row.get('id')} is blocking: {st}/{sv}")
        if st!='not_applicable' and not isinstance(row.get('evidence_ref'),str): errors.append(f'adversarial_checks[{i}].evidence_ref is required unless not_applicable')
    missing_acceptance=sorted((required_acceptance_ids or set())-covered_acceptance_ids)
    if missing_acceptance: errors.append('adversarial_checks missing shaped adversarial_acceptance IDs: '+','.join(missing_acceptance))
    for k in ('adversarial_p0_count','adversarial_p1_count'):
        if not nni(summary.get(k)): errors.append(f'grade_summary.{k} must be a non-negative integer for medium/high code')
    if nni(summary.get('adversarial_p0_count')) and summary.get('adversarial_p0_count')!=calc['P0']: errors.append(f"grade_summary.adversarial_p0_count={summary.get('adversarial_p0_count')} disagrees with calculated {calc['P0']}")
    if nni(summary.get('adversarial_p1_count')) and summary.get('adversarial_p1_count')!=calc['P1']: errors.append(f"grade_summary.adversarial_p1_count={summary.get('adversarial_p1_count')} disagrees with calculated {calc['P1']}")
    if nni(summary.get('p0_count')) and summary.get('p0_count')<calc['P0']: errors.append('grade_summary.p0_count undercounts blocking adversarial P0 findings')
    if nni(summary.get('p1_count')) and summary.get('p1_count')<calc['P1']: errors.append('grade_summary.p1_count undercounts blocking adversarial P1 findings')
    uv=inv.get('unverified_items') if isinstance(inv,dict) else None
    if uv is None: errors.append('trust_surface_inventory.unverified_items is required')
    elif not isinstance(uv,list): errors.append('trust_surface_inventory.unverified_items must be a list')
    else:
        for i,item in enumerate(uv):
            if sev(item) in BLOCKING: errors.append(f'trust_surface_inventory.unverified_items[{i}] is blocking: {sev(item)}')
    for i,row in enumerate(deferred):
        if not isinstance(row,dict): errors.append(f'deferred_claims[{i}] must be an object'); continue
        if row.get('current_scope_implementable') is True and not has_ref(row): errors.append(f'deferred_claims[{i}] current-scope item lacks evidence_ref or acceptance/waiver ref')
        if row.get('current_scope_implementable') is True and row.get('waiver') is True and sev(row) in BLOCKING and not any(isinstance(row.get(k),str) and row.get(k).strip() for k in ('tracked_waiver_ref','maintainer_waiver_ref','user_waiver_ref')): errors.append(f'deferred_claims[{i}] blocking current-scope waiver lacks tracked maintainer/user waiver ref')
def lint(task_type,risk_level,grade_file,outcome_file):
    errors=[]; gbs=blocks(grade_file); summary=first(gbs,'grade_summary'); acceptance=first(gbs,'acceptance_status')
    validate_required(summary,acceptance,errors); gated=is_gate(task_type,risk_level)
    if gated:
        validate_outcome(blocks(outcome_file),errors)
        required_ids=adversarial_acceptance_ids(outcome_file)
        validate_adv(summary,gbs,errors,required_ids) if isinstance(summary,dict) else errors.append('cannot validate adversarial grade without grade_summary')
    return {'grade_lint':{'status':'fail' if errors else 'pass','task_type':task_type,'risk_level':risk_level,'medium_high_code_gate':gated,'grade_file':str(grade_file),'outcome_file':str(outcome_file),'errors':errors}}
def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument('--task-type',required=True,choices=['code','docs','infra','refactor','spec']); ap.add_argument('--risk-level',required=True,choices=['low','medium','high']); ap.add_argument('--grade-file',required=True); ap.add_argument('--outcome-file',required=True); ap.add_argument('--evidence-file')
    a=ap.parse_args(argv)
    try: result=lint(a.task_type,a.risk_level,Path(a.grade_file).resolve(),Path(a.outcome_file).resolve())
    except LintError as e: result={'grade_lint':{'status':'fail','task_type':a.task_type,'risk_level':a.risk_level,'grade_file':str(Path(a.grade_file).resolve()),'outcome_file':str(Path(a.outcome_file).resolve()),'errors':[str(e)]}}
    payload=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if a.evidence_file:
        out=Path(a.evidence_file).resolve(); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(payload,encoding='utf-8')
    print(payload,end=''); return 0 if result['grade_lint']['status']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
