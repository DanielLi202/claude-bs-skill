#!/usr/bin/env bash
set -uo pipefail

MIN_CODEX_VERSION="0.133.0"
VERIFY_COMMAND=""
SKIP_COUNCIL=0
SKIP_VERIFY_PREFLIGHT=0
REQUIRE_COUNCIL=0
COUNCIL_QUORUM_MIN=2

while [[ $# -gt 0 ]]; do
  case "$1" in
    --min-codex-version) MIN_CODEX_VERSION="${2:-}"; shift 2 ;;
    --verify-command) VERIFY_COMMAND="${2:-}"; shift 2 ;;
    --skip-council) SKIP_COUNCIL=1; shift ;;
    --require-council) REQUIRE_COUNCIL=1; shift ;;
    --council-quorum-min) COUNCIL_QUORUM_MIN="${2:-}"; shift 2 ;;
    --skip-verify-preflight) SKIP_VERIFY_PREFLIGHT=1; shift ;;
    -h|--help)
      echo "usage: preflight.sh [--min-codex-version X] [--verify-command CMD] [--skip-council] [--require-council] [--council-quorum-min N] [--skip-verify-preflight]"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 64 ;;
  esac
done

CHECKS_FILE="$(mktemp)"
OVERALL="pass"
COUNCIL_ALIVE=0
RECOVERY_REASON=""

escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
add_check() {
  local name="$1" status="$2" required="$3" detail="$4"
  [[ "$status" == "fail" && "$required" == "true" ]] && OVERALL="fail"
  {
    printf '  - name: %s\n' "$name"
    printf '    status: %s\n' "$status"
    printf '    required: %s\n' "$required"
    printf '    detail: "%s"\n' "$(escape "$detail")"
  } >> "$CHECKS_FILE"
}

emit_report() {
  printf 'overall: %s\n' "$OVERALL"
  printf 'checked_at: "%s"\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'checks:\n'
  cat "$CHECKS_FILE"
  rm -f "$CHECKS_FILE"
  if [[ -n "$RECOVERY_REASON" ]]; then
    printf '%s\n' "$RECOVERY_REASON"
  fi
  [[ "$OVERALL" == "pass" ]]
}

close_gap_probe() {
  python3 - <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except Exception as exc:
    print(f"close_gap_probe_error=PyYAML_unavailable: {exc}")
    sys.exit(1)


ROOT = Path.cwd()
STEP_TARGETS = {"step_7", "step_10"}


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuntimeError(f"missing {path}")
    except Exception as exc:
        raise RuntimeError(f"invalid yaml {path}: {exc}")
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} root must be mapping")
    return data


def task_id_from_cycle(cycle_dir: Path) -> str | None:
    path = cycle_dir / "cycle.yaml"
    if not path.exists():
        return None
    try:
        data = load_yaml(path)
    except RuntimeError:
        return None
    snapshot = data.get("task_snapshot")
    task = data.get("task")
    for value in (
        data.get("task_id"),
        snapshot.get("id") if isinstance(snapshot, dict) else None,
        task.get("id") if isinstance(task, dict) else None,
    ):
        if isinstance(value, str) and value:
            return value
    return None


def cycle_number(cycle_dir: Path) -> int:
    match = re.fullmatch(r"cycle-(\d+)", cycle_dir.name)
    return int(match.group(1)) if match else -1


def latest_cycle_for_task(cycle_root: Path, task_id: str) -> Path | None:
    if not cycle_root.exists():
        return None
    matches = []
    for cycle_dir in cycle_root.iterdir():
        if not cycle_dir.is_dir() or cycle_number(cycle_dir) < 0:
            continue
        if task_id_from_cycle(cycle_dir) == task_id:
            matches.append(cycle_dir)
    if not matches:
        return None
    return max(matches, key=cycle_number)


def gate_decision(cycle_dir: Path) -> str | None:
    path = cycle_dir / "auto_merge_gate.yaml"
    if not path.exists():
        return None
    data = load_yaml(path)
    gate = data.get("auto_merge_gate", data)
    if not isinstance(gate, dict):
        return None
    decision = gate.get("decision")
    return str(decision) if decision is not None else None


def step_event_state(path: Path) -> tuple[set[str], bool, bool]:
    states: dict[tuple[str, int], str] = {}
    merged_evidence = False
    if not path.exists():
        raise RuntimeError(f"missing {path}")
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except Exception as exc:
            raise RuntimeError(f"invalid json {path}:{line_no}: {exc}")
        step = event.get("step")
        kind = event.get("event")
        try:
            attempt = int(event.get("attempt", 0))
        except Exception:
            attempt = 0
        if isinstance(step, str) and kind in {"started", "completed", "failed"}:
            states[(step, attempt)] = kind
        outcome = str(event.get("outcome", ""))
        if step == "step_7" and kind == "completed" and re.search(r"\b(auto-)?merged?\b|\bsquash\b|\bmerge commit\b", outcome, re.I):
            merged_evidence = True
    open_targets = {step for (step, _attempt), kind in states.items() if step in STEP_TARGETS and kind == "started"}
    step10_completed = any(step == "step_10" and kind == "completed" for (step, _attempt), kind in states.items())
    return open_targets, step10_completed and "step_10" not in open_targets, merged_evidence


def gate_has_merge_evidence(cycle_dir: Path) -> bool:
    path = cycle_dir / "auto_merge_gate.yaml"
    if not path.exists():
        return False
    data = load_yaml(path)
    gate = data.get("auto_merge_gate", data)
    if not isinstance(gate, dict):
        return False
    if gate.get("merged") is True:
        return True
    for key in ("merge_commit", "merge_commit_sha", "merge_sha", "squash_commit", "merged_at"):
        value = gate.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


try:
    binding = load_yaml(ROOT / ".bootstrap.yaml")
    backlog_rel = binding.get("backlog", ".bootstrap/backlog.yaml")
    cycle_root_rel = binding.get("cycle_dir_root")
    if not isinstance(backlog_rel, str) or not backlog_rel:
        raise RuntimeError(".bootstrap.yaml backlog must be a path")
    if not isinstance(cycle_root_rel, str) or not cycle_root_rel:
        raise RuntimeError(".bootstrap.yaml cycle_dir_root must be a path")
    backlog = load_yaml(ROOT / backlog_rel)
    tasks = backlog.get("tasks")
    if not isinstance(tasks, list):
        raise RuntimeError("backlog tasks must be a list")
    in_progress = [task for task in tasks if isinstance(task, dict) and task.get("status") == "in_progress"]
    if len(in_progress) != 1:
        print(f"ok: no unique in_progress task (count={len(in_progress)})")
        sys.exit(0)
    task_id = in_progress[0].get("id")
    if not isinstance(task_id, str) or not task_id:
        raise RuntimeError("in_progress task id missing")
    cycle_dir = latest_cycle_for_task(ROOT / cycle_root_rel, task_id)
    if cycle_dir is None:
        print(f"ok: no cycle dir for in_progress task {task_id}")
        sys.exit(0)
    if gate_decision(cycle_dir) != "merge":
        print(f"ok: latest cycle {cycle_dir.name} auto_merge_gate is not decision=merge")
        sys.exit(0)
    open_targets, step10_completed, event_merge_evidence = step_event_state(cycle_dir / "step_events.jsonl")
    if step10_completed:
        print(f"ok: latest cycle {cycle_dir.name} has step_10 completed")
        sys.exit(0)
    if open_targets or event_merge_evidence or gate_has_merge_evidence(cycle_dir):
        match = re.fullmatch(r"cycle-(\d+)", cycle_dir.name)
        cycle_id = match.group(1) if match else cycle_dir.name
        print(f"recovery_required=merged_pr_needs_step10_close cycle={cycle_id} task={task_id}")
        sys.exit(2)
    print(f"ok: latest cycle {cycle_dir.name} has decision=merge but no offline merged/open-step evidence")
    sys.exit(0)
except Exception as exc:
    print(f"close_gap_probe_error={exc}")
    sys.exit(1)
PY
}

if [[ -f .bootstrap.yaml ]]; then
  if out=$(close_gap_probe 2>&1); then
    add_check close_gap_probe pass true "$out"
  else
    rc=$?
    add_check close_gap_probe fail true "$out"
    if [[ "$rc" == 2 ]] && grep -q '^recovery_required=merged_pr_needs_step10_close ' <<<"$out"; then
      RECOVERY_REASON="$(grep '^recovery_required=merged_pr_needs_step10_close ' <<<"$out" | tail -1)"
      emit_report
      exit $?
    fi
  fi
fi
version_ge() {
  python3 - "$1" "$2" <<'PY'
import re, sys

def parts(v):
    m=re.search(r'(\d+(?:\.\d+){1,3})', v)
    if not m: return None
    out=[int(x) for x in m.group(1).split('.')]
    while len(out)<3: out.append(0)
    return out
have, need = parts(sys.argv[1]), parts(sys.argv[2])
sys.exit(0 if have and need and have >= need else 1)
PY
}

goal_rpc_probe() {
  python3 - <<'PY'
import json, os, select, subprocess, sys, time
prefix = "BS_GOAL_V1 "
objective = prefix + json.dumps(
    {"run_id":"preflight","outcome_sha256":"0"*64,"outcome_path":"/preflight/outcome.md"},
    sort_keys=True,
    separators=(",",":"),
) + "\nPreflight goal RPC capability probe."

def send(proc, i, method, params):
    proc.stdin.write(json.dumps({"jsonrpc":"2.0","id":i,"method":method,"params":params})+"\n")
    proc.stdin.flush()
def read(proc, i, timeout=10):
    start=time.monotonic()
    while time.monotonic()-start<timeout:
        if proc.poll() is not None: raise RuntimeError(f"app-server exited before id={i}: {proc.returncode}")
        ready,_,_=select.select([proc.stdout, proc.stderr], [], [], 0.25)
        for stream in ready:
            line=stream.readline()
            if not line or stream is proc.stderr: continue
            obj=json.loads(line)
            if obj.get("id")==i:
                if "error" in obj: raise RuntimeError(str(obj["error"]))
                return obj.get("result") or {}
    raise RuntimeError(f"timeout waiting id={i}")
def goal_obj(result):
    return result.get("goal") or result.get("threadGoal") or result.get("data") or result

proc=None; thread_id=None
try:
    proc=subprocess.Popen(["codex","app-server","--listen","stdio://"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    send(proc,1,"initialize",{"clientInfo":{"name":"bs-preflight","version":"1.4.21"},"capabilities":{"experimentalApi":True}}); read(proc,1)
    send(proc,2,"thread/start",{"cwd":os.getcwd(),"approvalPolicy":"never","sandbox":"workspace-write","ephemeral":False}); thread_id=read(proc,2)["thread"]["id"]
    send(proc,3,"thread/goal/set",{"threadId":thread_id,"objective":objective,"status":"active","tokenBudget":None}); read(proc,3)
    send(proc,4,"thread/goal/get",{"threadId":thread_id}); got=goal_obj(read(proc,4))
    first=str(got.get("objective","")).splitlines()[0]
    if not first.startswith(prefix): raise RuntimeError("goal objective header missing after set/get")
    if json.loads(first[len(prefix):]).get("run_id")!="preflight": raise RuntimeError("goal objective header mismatch after set/get")
    raw=got.get("status"); status={"usageLimited":"usage_limited","budgetLimited":"budget_limited"}.get(raw, raw if raw in {"active","paused","blocked","complete"} else "unknown")
    if status not in {"active","complete"}: raise RuntimeError(f"unexpected normalized goal status {status}")
    print(f"thread_id={thread_id}; status={status}; cleanup=clear+archive")
except Exception as exc:
    print(str(exc), file=sys.stderr); sys.exit(1)
finally:
    if proc is not None and thread_id is not None and proc.poll() is None:
        for i,method in ((900001,"thread/goal/clear"),(900002,"thread/archive")):
            try: send(proc,i,method,{"threadId":thread_id}); read(proc,i,timeout=3)
            except Exception: pass
    if proc is not None:
        try: proc.kill()
        except Exception: pass
PY
}

if out=$(git --version 2>&1); then add_check git pass true "$out"; else add_check git fail true "$out"; fi
if codex_path=$(command -v codex 2>/dev/null); then add_check codex_binary pass true "$codex_path"; else add_check codex_binary fail true "codex not found"; fi
if out=$(codex --version 2>&1); then
  if version_ge "$out" "$MIN_CODEX_VERSION"; then add_check codex_version pass true "$out"; else add_check codex_version fail true "$out < $MIN_CODEX_VERSION"; fi
else add_check codex_version fail true "$out"; fi
if out=$(codex login status 2>&1); then add_check codex_auth pass true "$out"; else add_check codex_auth fail true "$out"; fi
if out=$(goal_rpc_probe 2>&1); then add_check codex_goal_rpc_probe pass true "$out"; else add_check codex_goal_rpc_probe fail true "$out"; fi
if gh_path=$(command -v gh 2>/dev/null); then add_check gh_binary pass true "$gh_path"; else add_check gh_binary fail true "gh not found"; fi
if out=$(gh auth status 2>&1); then add_check gh_auth pass true "gh auth status passed"; else add_check gh_auth fail true "$out"; fi

if ! [[ "$COUNCIL_QUORUM_MIN" =~ ^[0-9]+$ ]]; then
  add_check council_quorum fail true "invalid council quorum: $COUNCIL_QUORUM_MIN"
elif [[ "$SKIP_COUNCIL" == 1 ]]; then
  add_check council_quorum warn false "council checks skipped"
else
  COUNCIL_REQUIRED=false
  [[ "$REQUIRE_COUNCIL" == 1 ]] && COUNCIL_REQUIRED=true
  if grok_path=$(command -v grok 2>/dev/null); then
    add_check grok_binary pass false "$grok_path"
    if command -v timeout >/dev/null 2>&1 && timeout 35s grok models >/dev/null 2>&1; then add_check grok_auth pass false "grok models passed"; COUNCIL_ALIVE=$((COUNCIL_ALIVE+1)); else add_check grok_auth warn false "grok auth probe failed, timeout unavailable, or timed out"; fi
  else
    add_check grok_binary warn false "grok not found"
    add_check grok_auth warn false "grok unavailable"
  fi
  if agy_path=$(command -v agy 2>/dev/null); then
    if command -v timeout >/dev/null 2>&1 && timeout 35s agy --print "Reply exactly OK." --print-timeout 30s >/dev/null 2>&1; then add_check agy_auth pass false "agy print probe passed"; COUNCIL_ALIVE=$((COUNCIL_ALIVE+1)); else add_check agy_auth warn false "AGY_AUTH_DEAD/TIMEOUT"; fi
  else
    add_check agy_auth warn false "agy not found"
  fi
  if [[ "$COUNCIL_ALIVE" -ge "$COUNCIL_QUORUM_MIN" ]]; then
    add_check council_quorum pass "$COUNCIL_REQUIRED" "alive=$COUNCIL_ALIVE; need=$COUNCIL_QUORUM_MIN; required_by=$([[ "$COUNCIL_REQUIRED" == true ]] && echo explicit_policy || echo none)"
  elif [[ "$COUNCIL_REQUIRED" == true ]]; then
    add_check council_quorum fail true "alive=$COUNCIL_ALIVE; need=$COUNCIL_QUORUM_MIN; required_by=explicit_policy"
  else
    add_check council_quorum warn false "alive=$COUNCIL_ALIVE; need=$COUNCIL_QUORUM_MIN; required_by=none"
  fi
fi
if [[ "$SKIP_VERIFY_PREFLIGHT" == 1 ]]; then
  add_check verify_command_baseline warn false "baseline verify skipped"
elif [[ -n "$VERIFY_COMMAND" ]]; then
  if out=$(bash -c "$VERIFY_COMMAND" 2>&1); then add_check verify_command_baseline pass true "verify command passed"; else add_check verify_command_baseline fail true "$out"; fi
else
  add_check verify_command_baseline warn false "no verify command provided"
fi

emit_report
