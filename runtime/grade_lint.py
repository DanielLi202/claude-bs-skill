#!/usr/bin/env python3
"""Deterministic lint for bs Grade artifacts."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any
try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None
BLOCKING={"P0","P1"}
SURFACES={"process","background_process","runtime_files","identity_sentinel","network_probe","auth_or_secret","file_modes","concurrency_or_locking","destructive_operation","external_subprocess","string_boundary","input_validation_or_schema"}
OPTIONAL_CURRENT_HINT_PATTERNS=(
    (re.compile(r"\boptional\b", re.I), "optional"),
    (re.compile(r"\bdefer(?:red|ral|s|ring)?\b", re.I), "deferred"),
    (re.compile(r"\bfuture\b", re.I), "future"),
    (re.compile(r"\bnot[-\s]?reachable\b", re.I), "not-reachable"),
    (re.compile(r"\bunreachable\b", re.I), "unreachable"),
    (re.compile(r"\bnot\s+required\b", re.I), "not required"),
    (re.compile(r"\bcan\s+skip\b", re.I), "can skip"),
    (re.compile(r"\bif\s+possible\b", re.I), "if possible"),
    (re.compile(r"\blater\b", re.I), "later"),
    (re.compile(r"\bfollow[-\s]?up\b", re.I), "follow-up"),
)
CONCURRENCY_TERMS=re.compile(r"\bconcurrent(?:ly|cy)?\b|lost\s+update|same[-\s]?revision|\bone\s+2xx\b|\b409\b|if[-\s]?match", re.I)
CONCURRENCY_EVIDENCE={"concurrency_test","atomicity_proof"}
BOUNDARY_TERMS=re.compile(r"<=\s*\d+\s*chars?\b|\b\d+\s*chars?\b|\blength\s+(?:cap|limit|boundary)\b|\bchar[-_\s]?boundary\b|\bstring[-_\s]?boundary\b|\btruncate(?:d|s|ion)?\b|\buser\s+text\b|\bmalformed\s+(?:input|json)\b|\bnon[-_\s]?ascii\b|\bboundary\s+(?:probe|test|risk|case)\b", re.I)
BOUNDARY_SURFACES={"string_boundary","input_validation_or_schema"}
BOUNDARY_EVIDENCE={"non_ascii_boundary_test","malformed_input_test","length_boundary_test","json_boundary_test","schema_validation_test"}
PANIC_TERMS=re.compile(r"\bno[-\s]?panic\b|\bpanic(?:s|ked|king)?\b|\bunwrap\b|\bexpect\b", re.I)
PANIC_EVIDENCE={"panic_audit","implicit_panic_audit"}
PATH_ROOT_TERMS=re.compile(r"\bpath[-_\s]?traversal\b|\btravers(?:e|al|ing)\b.*\boutside\b|\boutside\b.*\b(?:root|roots|director(?:y|ies)|filesystem|file\s+tree)\b|\bescape\b.*\b(?:root|roots|director(?:y|ies)|filesystem|file\s+tree)\b|\broot[-_\s]?contain(?:ed|ment)?\b", re.I)
PATH_ACCESS_TERMS=re.compile(r"\b(?:read|open|file|filesystem|path|dir|directory|directories|root|roots|skill[-_ ]?id|id)\b", re.I)
STRING_TRAVERSAL_TERMS=re.compile(r"\.\.|slash|backslash|absolute\s+path|%2f|%5c|encoded\s+(?:slash|path)|path[-_\s]?traversal", re.I)
SYMLINK_CONTAINMENT_TERMS=re.compile(r"symlink|canonical(?:ize|ise|ization|isation)?|realpath|starts?_with|starts[-\s]?with|root[-_\s]?contain(?:ed|ment)?|within\s+(?:the\s+)?(?:root|directory)|no[-_\s]?follow|lstat|symlink_metadata|link_metadata", re.I)
REQUEST_TARGET_TERMS=re.compile(r"request[-_\s]?target|request\s+line|raw\s+http|http/1\.1|path\s+segment|percent[-_\s]?encod|url[-_\s]?encod|crlf|control\s+char|request\s+delimiter", re.I)
REQUEST_TARGET_FACET_TERMS=re.compile(r"delimiter|\?|#|\bspaces?\b|control|crlf|\\r|\\n|percent[-_\s]?encod|url[-_\s]?encod", re.I)
SECRET_AUDIT_SCOPE_TERMS=re.compile(r"\b(?:auth|secret|token|credential|password|oauth|bearer|api[-_\s]?key|vendor[-_\s]?stderr|stderr|logs?|logging|traces?|tracing|events?|evidence|debug|display|errors?|serialization)\b", re.I)
SECRET_TOKEN_SHAPE_PATTERNS={
    "bare_token_or_key": re.compile(r"\b(?:bare[-_\s]*(?:whitespace[-_\s]*)?(?:token|key|form|shape)|key[-_\s]?value|token[-_\s]?equals|api[-_\s]?key[-_\s]?equals)\b|\b(?:token|api[-_\s]?key)\s*=", re.I),
    "json_or_quoted_token": re.compile(r"\b(?:json(?:[-_\s]*or[-_\s]*quoted)?|quoted)[-_\s]*(?:token|api[-_\s]?key|form|shape)\b|[\"'](?:api[-_]?key|token)[\"']\s*:", re.I),
    "authorization_bearer": re.compile(r"\bauthorization\s*:\s*bearer\b|\bauthorization[-_\s]*bearer\b|\bhttp[-_\s]*header\b[^.;,\n]*\bbearer\b|\bbearer[-_\s]*header\b", re.I),
}
SECRET_BARE_SK_PATTERN=re.compile(r"(?<![\"':/A-Za-z0-9_-])sk-[A-Za-z0-9][A-Za-z0-9._-]*(?![A-Za-z0-9_-])", re.I)
class LintError(ValueError): pass

def split_top_level(text, sep=','):
    parts=[]; cur=[]; depth=0; quote=''
    for ch in text:
        if quote:
            cur.append(ch)
            if ch==quote: quote=''
            continue
        if ch in ('"', "'"):
            quote=ch; cur.append(ch); continue
        if ch in '[{(': depth+=1
        elif ch in ']})' and depth>0: depth-=1
        if ch==sep and depth==0:
            parts.append(''.join(cur).strip()); cur=[]
        else:
            cur.append(ch)
    if cur or text.strip(): parts.append(''.join(cur).strip())
    return parts

def parse_scalar(value):
    value=value.strip()
    if value in ('', 'null', 'Null', 'NULL', '~'): return None
    if value in ('true','True','TRUE'): return True
    if value in ('false','False','FALSE'): return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith('{') and value.endswith('}'):
        out={}
        inner=value[1:-1].strip()
        if not inner: return out
        for part in split_top_level(inner):
            if ':' not in part: raise LintError(f'malformed inline mapping item: {part}')
            k,v=part.split(':',1); out[k.strip()]=parse_scalar(v)
        return out
    if value.startswith('[') and value.endswith(']'):
        inner=value[1:-1].strip()
        return [] if not inner else [parse_scalar(part) for part in split_top_level(inner)]
    if re.fullmatch(r'-?\d+', value):
        return int(value)
    return value


def is_block_scalar(value):
    return value in {'>', '>-', '>+', '|', '|-', '|+'}

def parse_block_scalar(lines, start, parent_indent, marker):
    collected=[]; i=start
    while i<len(lines):
        if not lines[i].strip():
            collected.append(''); i+=1; continue
        cur_indent=indent_of(lines[i])
        if cur_indent<=parent_indent: break
        collected.append(lines[i].strip())
        i+=1
    if marker.startswith('>'):
        return ' '.join(part for part in collected if part), i
    return '\n'.join(collected), i

def indent_of(line):
    return len(line)-len(line.lstrip(' '))

def next_content(lines, start):
    i=start
    while i<len(lines) and not lines[i].strip(): i+=1
    return i

def parse_key_value(content):
    if ':' not in content: raise LintError(f'malformed yaml line: {content}')
    key,value=content.split(':',1)
    return key.strip(), value.strip()

def parse_mapping(lines, start, indent):
    out={}; i=start
    while i<len(lines):
        if not lines[i].strip(): i+=1; continue
        cur_indent=indent_of(lines[i])
        if cur_indent<indent: break
        if cur_indent>indent: break
        content=lines[i].strip()
        if content.startswith('- '): break
        key,value=parse_key_value(content)
        if value:
            if is_block_scalar(value):
                out[key], i = parse_block_scalar(lines, i+1, cur_indent, value)
            else:
                out[key]=parse_scalar(value); i+=1
            continue
        j=next_content(lines,i+1)
        if j>=len(lines) or indent_of(lines[j])<=cur_indent:
            out[key]=None; i=i+1; continue
        if lines[j].strip().startswith('- '):
            out[key],i=parse_list(lines,j,indent_of(lines[j]))
        else:
            out[key],i=parse_mapping(lines,j,indent_of(lines[j]))
    return out,i

def parse_list(lines, start, indent):
    out=[]; i=start
    while i<len(lines):
        if not lines[i].strip(): i+=1; continue
        cur_indent=indent_of(lines[i])
        if cur_indent<indent: break
        if cur_indent!=indent or not lines[i].strip().startswith('- '): break
        item=lines[i].strip()[2:].strip()
        if not item:
            parsed,i=parse_mapping(lines,next_content(lines,i+1),indent+2)
            out.append(parsed); continue
        if item.startswith('{') and item.endswith('}'):
            out.append(parse_scalar(item)); i+=1; continue
        if ':' in item:
            key,value=parse_key_value(item)
            if value and is_block_scalar(value):
                parsed_value, next_i = parse_block_scalar(lines, i+1, cur_indent, value)
                out.append({key: parsed_value})
                i = next_i
                continue
            row={key: parse_scalar(value) if value else None}
            j=next_content(lines,i+1)
            if j<len(lines) and indent_of(lines[j])>cur_indent and not lines[j].strip().startswith('- '):
                extra,i=parse_mapping(lines,j,indent_of(lines[j]))
                row.update(extra)
            else:
                i+=1
            out.append(row); continue
        out.append(parse_scalar(item)); i+=1
    return out,i

def parse_yaml_fence(fence_lines):
    if yaml is not None:
        text = '\n'.join(fence_lines)
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            # Backward compatibility: older Grade artifacts sometimes used
            # unquoted prose scalars containing ": ". Prefer PyYAML for valid
            # YAML, but fall back to the legacy permissive parser for those
            # artifacts instead of failing before lint semantics can run.
            pass
    lines=[line.rstrip() for line in fence_lines]
    start=next_content(lines,0)
    if start>=len(lines): return None
    if lines[start].strip().startswith('- '):
        data,_=parse_list(lines,start,indent_of(lines[start]))
        return data
    data,_=parse_mapping(lines,start,indent_of(lines[start]))
    return data

def parse_front_matter(lines):
    if not lines or lines[0].strip()!='---':
        return None, 0
    j=1
    while j<len(lines) and lines[j].strip()!='---':
        j+=1
    if j>=len(lines):
        return None, 0
    data=parse_yaml_fence(lines[1:j])
    return data, j+1

def blocks(path:Path, *, include_front_matter=False)->list[dict[str,Any]]:
    if not path.exists(): raise LintError(f"file missing: {path}")
    out=[]; lines=path.read_text(encoding='utf-8').splitlines(); i=0
    if include_front_matter:
        data,next_i=parse_front_matter(lines)
        if isinstance(data,dict):
            out.append(data)
            i=next_i
    while i<len(lines):
        if lines[i].strip() in {'```yaml','```yml'}:
            j=i+1
            while j<len(lines) and lines[j].strip()!='```': j+=1
            if j>=len(lines): raise LintError(f"unterminated yaml fence in {path}")
            data=parse_yaml_fence(lines[i+1:j])
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
def has_tracked_waiver_or_scope_basis(row):
    return any(isinstance(row.get(k),str) and row.get(k).strip() for k in ('tracked_waiver_ref','maintainer_waiver_ref','user_waiver_ref','scope_basis_ref'))
def text_values(value):
    if isinstance(value,str):
        return [value]
    if isinstance(value,dict):
        out=[]
        for k,v in value.items():
            if isinstance(k,str): out.append(k)
            out.extend(text_values(v))
        return out
    if isinstance(value,list):
        out=[]
        for item in value: out.extend(text_values(item))
        return out
    return []
def text_blob(*values):
    return ' '.join(text_values(list(values)))
def row_surfaces(row):
    if not isinstance(row,dict): return set()
    return set(strs(row.get('surface'))+strs(row.get('surfaces')))
def evidence_kind(row):
    return row.get('evidence_kind') if isinstance(row.get('evidence_kind'),str) else ''
def references_any_id(row, ids):
    blob=text_blob(row)
    return any(re.search(rf"(?<![A-Za-z0-9_-]){re.escape(item)}(?![A-Za-z0-9_-])", blob) for item in ids)
def method_is_mere_grep(row):
    for k in ('method','evidence_method','audit_method'):
        v=row.get(k)
        if isinstance(v,str) and re.search(r"^(grep|regex|search)$|\b(mere|only|just)\s+grep\b|\bgrep\s+only\b", v.strip(), re.I):
            return True
    for k in ('evidence_ref','evidence_summary','evidence_note','summary','note'):
        v=row.get(k)
        if isinstance(v,str) and re.search(r"grep\s+(?:-[A-Za-z]*R|-[A-Za-z]+)|\bgrep\b.*\b(?:no hits|found no hits|only|mere)\b|\b(?:no hits|found no hits)\b.*\bgrep\b", v, re.I):
            return True
    return False
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
def adversarial_acceptance_metadata(bs):
    meta={}
    adv=first(bs,'adversarial_acceptance')
    if isinstance(adv,list):
        for row in adv:
            if isinstance(row,dict) and isinstance(row.get('id'),str) and row.get('id'):
                meta[row['id']]={'severity':row.get('severity'),'surfaces':row_surfaces(row),'text':text_blob(row),'row':row}
    return meta
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
            row_id=row.get('id')
            row_sev=row.get('severity')
            hint=row.get('verification_hint')
            if not isinstance(row_id,str) or not row_id: errors.append(f'adversarial_acceptance[{i}].id is required')
            if row_sev not in {'P0','P1','P2'}: errors.append(f'adversarial_acceptance[{i}].severity must be P0|P1|P2')
            surfaces_for_row=row_surfaces(row)
            covered.update(surfaces_for_row & present)
            if not isinstance(hint,str) or not hint.strip(): errors.append(f'adversarial_acceptance[{i}].verification_hint is required')
            elif row_sev in BLOCKING:
                for pattern,label in OPTIONAL_CURRENT_HINT_PATTERNS:
                    if pattern.search(hint):
                        errors.append(f'adversarial_acceptance[{i}] {row_id} P0/P1 verification_hint makes current validation optional via {label} wording')
                        break
            row_text=text_blob(row)
            if BOUNDARY_TERMS.search(row_text) and not (surfaces_for_row & BOUNDARY_SURFACES):
                errors.append(f'adversarial_acceptance[{i}] {row_id} boundary/input risk must use string_boundary or input_validation_or_schema surface')
    missing=sorted(present-covered)
    if missing: errors.append('present risk surfaces without adversarial_acceptance coverage: '+','.join(missing))

def adversarial_acceptance_ids(outcome_file: Path) -> set[str]:
    return set(adversarial_acceptance_metadata(blocks(outcome_file)))

def outcome_acceptance_metadata(bs):
    meta={}
    acc=first(bs,'acceptance')
    if isinstance(acc,list):
        for row in acc:
            if isinstance(row,dict) and isinstance(row.get('id'),str) and row.get('id'):
                meta[row['id']]={'severity':row.get('severity'),'text':text_blob(row),'row':row}
    return meta

def acceptance_status_metadata(acceptance):
    meta={}
    if isinstance(acceptance,list):
        for row in acceptance:
            if isinstance(row,dict) and isinstance(row.get('id'),str) and row.get('id'):
                meta[row['id']]={'severity':row.get('severity'),'text':text_blob(row),'row':row}
    return meta

def row_acceptance_ref(row):
    if not isinstance(row,dict): return ''
    for k in ('acceptance_id','acceptance_ref','id'):
        v=row.get(k)
        if isinstance(v,str) and v.strip(): return v.strip()
    return ''

def list_of_strs(value):
    return isinstance(value,list) and all(isinstance(x,str) and x.strip() for x in value)

def outcome_dependency_terms(required_acceptance):
    blob=text_blob([v.get('text','') for v in required_acceptance.values()])
    return bool(re.search(r"\b(dependenc(?:y|ies)|crate|package|cargo|npm|pip|go\.mod|version|lock(?:ed)?|Cargo\.toml|Cargo\.lock|forbidden\s+dependency|no\s+new\s+dependency)\b", blob, re.I))

def has_path_root_obligation(meta):
    text=meta.get('text','') if isinstance(meta,dict) else ''
    return bool(PATH_ROOT_TERMS.search(text) and PATH_ACCESS_TERMS.search(text))

def has_request_target_obligation(meta):
    text=meta.get('text','') if isinstance(meta,dict) else ''
    return bool(REQUEST_TARGET_TERMS.search(text))

def negative_rows_for_acceptance(neg, acceptance_id):
    return [row for row in neg if isinstance(row,dict) and row_acceptance_ref(row)==acceptance_id]

def row_evidence_text(rows):
    evidence_fields=('scenario','evidence_ref','evidence_refs','evidence_kind','method','evidence_method','audit_method','evidence_summary','summary','note','details','rationale')
    values=[]
    for row in rows:
        if isinstance(row,dict):
            values.extend(row.get(field) for field in evidence_fields if field in row)
    return text_blob(values)

def outcome_has_auth_secret_surface(outcome_blocks):
    rs=first(outcome_blocks or [],'risk_surface')
    surfaces=rs.get('surfaces') if isinstance(rs,dict) else None
    if isinstance(surfaces,dict):
        detail=surfaces.get('auth_or_secret')
        if detail is True or (isinstance(detail,dict) and detail.get('present') is True):
            return True
    adv=first(outcome_blocks or [],'adversarial_acceptance')
    return isinstance(adv,list) and any(isinstance(row,dict) and 'auth_or_secret' in row_surfaces(row) for row in adv)

def secret_audit_scope_text(secret):
    return text_blob(
        secret.get('checked_surfaces'),
        secret.get('evidence_ref'),
        secret.get('evidence_refs'),
        secret.get('evidence_summary'),
        secret.get('summary'),
        secret.get('note'),
        secret.get('details'),
    )

def secret_audit_requires_multi_shape(secret, outcome_blocks):
    return outcome_has_auth_secret_surface(outcome_blocks) or bool(SECRET_AUDIT_SCOPE_TERMS.search(secret_audit_scope_text(secret)))

def has_bare_sk_token(text):
    for match in SECRET_BARE_SK_PATTERN.finditer(text):
        context=text[max(0,match.start()-40):match.end()+40]
        if not re.search(r"\b(?:authorization|bearer)\b", context, re.I):
            return True
    return False

def secret_probe_has_shape(name, text):
    pattern=SECRET_TOKEN_SHAPE_PATTERNS[name]
    if pattern.search(text):
        return True
    return name=='bare_token_or_key' and has_bare_sk_token(text)

def validate_cleartext_secret_probe_shape(secret, outcome_blocks, errors):
    probe=secret.get('cleartext_secret_probe')
    if isinstance(probe,str):
        if probe not in {'pass','not_applicable'}:
            errors.append('secret_leakage_audit.cleartext_secret_probe must be pass|not_applicable or a structured shape list when status pass')
            return
    elif isinstance(probe,dict):
        probe_status=probe.get('status') or probe.get('result')
        if probe_status is not None and probe_status not in {'pass','not_applicable'}:
            errors.append('secret_leakage_audit.cleartext_secret_probe.status must be pass|not_applicable when status pass')
            return
    elif not isinstance(probe,list):
        errors.append('secret_leakage_audit.cleartext_secret_probe must be pass|not_applicable or a structured shape list when status pass')
        return
    if not secret_audit_requires_multi_shape(secret, outcome_blocks):
        return
    probe_text=text_blob(secret)
    missing=[name for name in SECRET_TOKEN_SHAPE_PATTERNS if not secret_probe_has_shape(name, probe_text)]
    if missing:
        errors.append('secret_leakage_audit.cleartext_secret_probe missing required token shapes for in-scope auth/secret/log/evidence surfaces: '+','.join(missing))

def validate_property_obligations(required_acceptance, neg, errors):
    """Catch property escapes where a Grade covers an example but not the invariant."""
    calc={'P0':0,'P1':0}
    for acceptance_id, meta in sorted(required_acceptance.items()):
        severity=meta.get('severity')
        if severity not in BLOCKING:
            continue
        rows=negative_rows_for_acceptance(neg, acceptance_id)
        if not rows:
            continue
        text=row_evidence_text(rows)
        missing=[]
        if has_path_root_obligation(meta):
            if not STRING_TRAVERSAL_TERMS.search(text):
                missing.append('string_traversal')
            if not SYMLINK_CONTAINMENT_TERMS.search(text):
                missing.append('symlink_or_canonical_containment')
        if has_request_target_obligation(meta) and not REQUEST_TARGET_FACET_TERMS.search(text):
            missing.append('request_target_delimiter_or_control_chars')
        if missing:
            calc[severity]+=1
            errors.append(f"property_obligation[{acceptance_id}] missing required negative coverage facets: {','.join(missing)}")
    return calc

def validate_code_baseline(summary, bs, errors, required_acceptance, acceptance_status, outcome_blocks=None):
    """All code tasks need replayable spec/security/negative-test evidence."""
    required_acceptance = required_acceptance or acceptance_status_metadata(acceptance_status)
    required_ids=set(required_acceptance)
    blocking_ids={k for k,v in required_acceptance.items() if v.get('severity') in BLOCKING}
    calc={'P0':0,'P1':0}

    spec=first(bs,'spec_compliance_matrix')
    if not isinstance(spec,list) or not spec:
        errors.append('code grade missing parseable spec_compliance_matrix block'); spec=[]
    covered=set()
    for i,row in enumerate(spec):
        if not isinstance(row,dict): errors.append(f'spec_compliance_matrix[{i}] must be an object'); continue
        rid=row_acceptance_ref(row); st=row.get('status'); sv=row.get('severity_if_fail') or required_acceptance.get(rid,{}).get('severity')
        if not rid: errors.append(f'spec_compliance_matrix[{i}].acceptance_id is required')
        else: covered.add(rid)
        if st not in {'pass','fail','unverified','not_applicable'}: errors.append(f'spec_compliance_matrix[{i}].status must be pass|fail|unverified|not_applicable'); continue
        if sv not in {'P0','P1','P2'}: errors.append(f'spec_compliance_matrix[{i}].severity_if_fail must be P0|P1|P2'); continue
        if st in {'fail','unverified'} and sv in BLOCKING:
            calc[sv]+=1; errors.append(f"spec_compliance_matrix[{i}] {rid} is blocking: {st}/{sv}")
        if st!='not_applicable':
            if not isinstance(row.get('evidence_ref'),str) or not row.get('evidence_ref').strip(): errors.append(f'spec_compliance_matrix[{i}].evidence_ref is required unless not_applicable')
            if not (list_of_strs(row.get('spec_refs')) or isinstance(row.get('spec_ref'),str)): errors.append(f'spec_compliance_matrix[{i}] requires spec_ref or spec_refs')
        elif not (isinstance(row.get('rationale'),str) and row.get('rationale').strip()):
            errors.append(f'spec_compliance_matrix[{i}].rationale is required when not_applicable')
    missing=sorted(required_ids-covered)
    if missing: errors.append('spec_compliance_matrix missing outcome acceptance IDs: '+','.join(missing))

    neg=first(bs,'negative_regression_tests')
    if not isinstance(neg,list) or not neg:
        errors.append('code grade missing parseable negative_regression_tests block'); neg=[]
    neg_covered=set()
    for i,row in enumerate(neg):
        if not isinstance(row,dict): errors.append(f'negative_regression_tests[{i}] must be an object'); continue
        rid=row_acceptance_ref(row); st=row.get('status'); sv=row.get('severity_if_fail') or required_acceptance.get(rid,{}).get('severity')
        if not rid: errors.append(f'negative_regression_tests[{i}].acceptance_id is required')
        else: neg_covered.add(rid)
        if st not in {'pass','fail','unverified','not_applicable'}: errors.append(f'negative_regression_tests[{i}].status must be pass|fail|unverified|not_applicable'); continue
        if sv not in {'P0','P1','P2'}: errors.append(f'negative_regression_tests[{i}].severity_if_fail must be P0|P1|P2'); continue
        if st in {'fail','unverified'} and sv in BLOCKING:
            calc[sv]+=1; errors.append(f"negative_regression_tests[{i}] {rid} is blocking: {st}/{sv}")
        if st=='pass':
            if not isinstance(row.get('evidence_ref'),str) or not row.get('evidence_ref').strip(): errors.append(f'negative_regression_tests[{i}].evidence_ref is required when pass')
            if not isinstance(row.get('scenario'),str) or not row.get('scenario').strip(): errors.append(f'negative_regression_tests[{i}].scenario is required when pass')
        if st=='not_applicable' and rid in blocking_ids and not any(isinstance(row.get(k),str) and row.get(k).strip() for k in ('scope_basis_ref','tracked_waiver_ref','maintainer_waiver_ref','user_waiver_ref')):
            errors.append(f'negative_regression_tests[{i}] {rid} P0/P1 not_applicable requires scope_basis_ref or tracked waiver')
    missing_neg=sorted(blocking_ids-neg_covered)
    if missing_neg: errors.append('negative_regression_tests missing P0/P1 outcome acceptance IDs: '+','.join(missing_neg))
    prop_calc=validate_property_obligations(required_acceptance, neg, errors)
    calc['P0']+=prop_calc['P0']; calc['P1']+=prop_calc['P1']

    secret=first(bs,'secret_leakage_audit')
    if not isinstance(secret,dict):
        errors.append('code grade missing parseable secret_leakage_audit block')
    else:
        st=secret.get('status')
        if st not in {'pass','fail','unverified','not_applicable'}:
            errors.append('secret_leakage_audit.status must be pass|fail|unverified|not_applicable')
        elif st in {'fail','unverified'}:
            calc['P1']+=1; errors.append(f'secret_leakage_audit is blocking: {st}/P1')
        elif st=='pass':
            if not isinstance(secret.get('evidence_ref'),str) or not secret.get('evidence_ref').strip(): errors.append('secret_leakage_audit.evidence_ref is required when pass')
            if not list_of_strs(secret.get('checked_surfaces')): errors.append('secret_leakage_audit.checked_surfaces must be a non-empty list when pass')
            validate_cleartext_secret_probe_shape(secret, outcome_blocks, errors)
        elif st=='not_applicable' and not any(isinstance(secret.get(k),str) and secret.get(k).strip() for k in ('rationale','scope_basis_ref')):
            errors.append('secret_leakage_audit not_applicable requires rationale or scope_basis_ref')

    dep=first(bs,'dependency_spec_review')
    dep_required=outcome_dependency_terms(required_acceptance)
    if not isinstance(dep,list) or not dep:
        errors.append('code grade missing parseable dependency_spec_review block'); dep=[]
    dep_has_applicable=False
    for i,row in enumerate(dep):
        if not isinstance(row,dict): errors.append(f'dependency_spec_review[{i}] must be an object'); continue
        st=row.get('status'); sv=row.get('severity_if_fail') or 'P1'
        if st not in {'pass','fail','unverified','not_applicable'}: errors.append(f'dependency_spec_review[{i}].status must be pass|fail|unverified|not_applicable'); continue
        if sv not in {'P0','P1','P2'}: errors.append(f'dependency_spec_review[{i}].severity_if_fail must be P0|P1|P2'); continue
        if st!='not_applicable':
            dep_has_applicable=True
            if not isinstance(row.get('evidence_ref'),str) or not row.get('evidence_ref').strip(): errors.append(f'dependency_spec_review[{i}].evidence_ref is required unless not_applicable')
            if not (isinstance(row.get('spec_ref'),str) and row.get('spec_ref').strip()): errors.append(f'dependency_spec_review[{i}].spec_ref is required unless not_applicable')
        elif not (isinstance(row.get('rationale'),str) and row.get('rationale').strip()):
            errors.append(f'dependency_spec_review[{i}].rationale is required when not_applicable')
        if st in {'fail','unverified'} and sv in BLOCKING:
            calc[sv]+=1; errors.append(f"dependency_spec_review[{i}] is blocking: {st}/{sv}")
    if dep_required and not dep_has_applicable:
        errors.append('dependency_spec_review must include at least one applicable row because outcome acceptance references dependencies/versions/packages')

    if isinstance(summary,dict):
        if nni(summary.get('p0_count')) and summary.get('p0_count')<calc['P0']: errors.append('grade_summary.p0_count undercounts blocking code-baseline P0 findings')
        if nni(summary.get('p1_count')) and summary.get('p1_count')<calc['P1']: errors.append('grade_summary.p1_count undercounts blocking code-baseline P1 findings')

def validate_adv(summary,bs,errors,required_acceptance=None):
    required_acceptance=required_acceptance or {}
    checks=first(bs,'adversarial_checks'); inv=first(bs,'trust_surface_inventory'); deferred=first(bs,'deferred_claims')
    if not isinstance(checks,list): errors.append('medium/high code grade missing parseable adversarial_checks block'); checks=[]
    if not isinstance(inv,dict): errors.append('medium/high code grade missing parseable trust_surface_inventory block'); inv={}
    if not isinstance(deferred,list): errors.append('medium/high code grade missing parseable deferred_claims block'); deferred=[]
    calc={'P0':0,'P1':0}
    covered_acceptance_ids=set()
    for i,row in enumerate(checks):
        if not isinstance(row,dict): errors.append(f'adversarial_checks[{i}] must be an object'); continue
        st=row.get('status'); sv=row.get('severity_if_fail')
        row_refs=[]
        for k in ('acceptance_id','acceptance_ref','adversarial_id','adversarial_ref'):
            if isinstance(row.get(k), str) and row.get(k): row_refs.append(row.get(k)); covered_acceptance_ids.add(row.get(k))
        if not isinstance(row.get('id'),str) or not row.get('id'): errors.append(f'adversarial_checks[{i}].id is required')
        if st not in {'pass','fail','unverified','not_applicable'}: errors.append(f'adversarial_checks[{i}].status must be pass|fail|unverified|not_applicable'); continue
        if sv not in {'P0','P1','P2'}: errors.append(f'adversarial_checks[{i}].severity_if_fail must be P0|P1|P2'); continue
        if st in {'fail','unverified'} and sv in BLOCKING: calc[sv]+=1; errors.append(f"adversarial_checks[{i}] {row.get('id')} is blocking: {st}/{sv}")
        if st!='not_applicable' and not isinstance(row.get('evidence_ref'),str): errors.append(f'adversarial_checks[{i}].evidence_ref is required unless not_applicable')
        referenced=[required_acceptance[x] for x in row_refs if x in required_acceptance]
        combined_text=text_blob(row, referenced)
        combined_surfaces=set(row_surfaces(row))
        for ref in referenced: combined_surfaces |= set(ref.get('surfaces') or set())
        if st!='not_applicable' and 'concurrency_or_locking' in combined_surfaces and CONCURRENCY_TERMS.search(combined_text) and evidence_kind(row) not in CONCURRENCY_EVIDENCE:
            errors.append(f'adversarial_checks[{i}] {row.get("id")} concurrency_or_locking check requires evidence_kind concurrency_test|atomicity_proof')
        if st!='not_applicable' and ((combined_surfaces & BOUNDARY_SURFACES) or BOUNDARY_TERMS.search(combined_text)) and evidence_kind(row) not in BOUNDARY_EVIDENCE:
            errors.append(f'adversarial_checks[{i}] {row.get("id")} boundary/input check requires evidence_kind non_ascii_boundary_test|malformed_input_test|length_boundary_test|json_boundary_test|schema_validation_test')
        if st!='not_applicable' and PANIC_TERMS.search(combined_text):
            if evidence_kind(row) not in PANIC_EVIDENCE:
                errors.append(f'adversarial_checks[{i}] {row.get("id")} panic/no-panic audit requires evidence_kind panic_audit|implicit_panic_audit')
            if method_is_mere_grep(row):
                errors.append(f'adversarial_checks[{i}] {row.get("id")} panic/no-panic audit cannot be mere grep')
    missing_acceptance=sorted(set(required_acceptance)-covered_acceptance_ids)
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
    blocking_ids={k for k,v in required_acceptance.items() if v.get('severity') in BLOCKING}
    for i,row in enumerate(deferred):
        if not isinstance(row,dict): errors.append(f'deferred_claims[{i}] must be an object'); continue
        if row.get('current_scope_implementable') is True and not has_ref(row): errors.append(f'deferred_claims[{i}] current-scope item lacks evidence_ref or acceptance/waiver ref')
        if row.get('current_scope_implementable') is True and row.get('waiver') is True and sev(row) in BLOCKING and not any(isinstance(row.get(k),str) and row.get(k).strip() for k in ('tracked_waiver_ref','maintainer_waiver_ref','user_waiver_ref')): errors.append(f'deferred_claims[{i}] blocking current-scope waiver lacks tracked maintainer/user waiver ref')
        if blocking_ids and references_any_id(row, blocking_ids) and not has_tracked_waiver_or_scope_basis(row):
            errors.append(f'deferred_claims[{i}] defers current P0/P1 adversarial acceptance without tracked waiver or scope_basis_ref')
def lint(task_type,risk_level,grade_file,outcome_file):
    errors=[]; gbs=blocks(grade_file); summary=first(gbs,'grade_summary'); acceptance=first(gbs,'acceptance_status')
    validate_required(summary,acceptance,errors); gated=is_gate(task_type,risk_level); code_gate=(task_type=='code')
    obs=blocks(outcome_file, include_front_matter=True) if code_gate or gated else []
    if code_gate:
        validate_code_baseline(summary,gbs,errors,outcome_acceptance_metadata(obs),acceptance,obs)
    if gated:
        validate_outcome(obs,errors)
        required=adversarial_acceptance_metadata(obs)
        validate_adv(summary,gbs,errors,required) if isinstance(summary,dict) else errors.append('cannot validate adversarial grade without grade_summary')
    return {'grade_lint':{'status':'fail' if errors else 'pass','task_type':task_type,'risk_level':risk_level,'code_baseline_gate':code_gate,'medium_high_code_gate':gated,'grade_file':str(grade_file),'outcome_file':str(outcome_file),'errors':errors}}
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
