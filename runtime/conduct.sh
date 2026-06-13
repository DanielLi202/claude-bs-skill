#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: conduct.sh --cycle-dir ABS --outcome-file PATH --evidence-dir PATH [--worktree PATH] [--fix-round N] [--model M] [--effort E] [--mcp-policy clean|allowlist|full] [--mcp-allow a,b,c] [--terminal-candidate-idle-sec N] [--on-terminal-candidate observe|terminate] [--progress-suspect-age-sec N] [--on-progress-suspect observe|annotate|needs_human] [--goal-completion-nudge]

Long Conduct turns can outlive the caller's session; run this detached so an
external SIGTERM of the launching turn does not abandon a near-complete turn,
e.g.:  setsid conduct.sh ... &   or   tmux new -d 'conduct.sh ...'
EOF
}

CYCLE_DIR=""
OUTCOME_FILE=""
EVIDENCE_DIR=""
WORKTREE_CWD=""
FIX_ROUND=""
MODEL=""
EFFORT="low"
EXPECTED_EFFECT_KIND="workspace_delta"
EXPECTED_EFFECT_REQUIRED="true"
WALL_CLOCK_LIMIT_SEC=""
ON_WALL_CLOCK_LIMIT="mark_stale"
FIRST_WORK_ITEM_STALE_SEC=""
FIRST_WORK_ITEM_TERMINATE_SEC=""
ON_NO_WORK_ITEMS="mark_stale"
IDLE_KILL_SEC=""
SILENT_SOFT_LIMIT_SEC=""
STALE_NOTICE_SEC=""
PROGRESS_REPORT_SEC=""
TERMINAL_CANDIDATE_IDLE_SEC=""
ON_TERMINAL_CANDIDATE=""
PROGRESS_SUSPECT_AGE_SEC=""
ON_PROGRESS_SUSPECT=""
GOAL_COMPLETION_NUDGE=""
MCP_POLICY="clean"
MCP_ALLOW=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cycle-dir) CYCLE_DIR="${2:-}"; shift 2 ;;
    --outcome-file) OUTCOME_FILE="${2:-}"; shift 2 ;;
    --evidence-dir) EVIDENCE_DIR="${2:-}"; shift 2 ;;
    --worktree) WORKTREE_CWD="${2:-}"; shift 2 ;;
    --fix-round) FIX_ROUND="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --effort) EFFORT="${2:-}"; shift 2 ;;
    --expected-effect-kind) EXPECTED_EFFECT_KIND="${2:-}"; shift 2 ;;
    --expected-effect-required) EXPECTED_EFFECT_REQUIRED="${2:-}"; shift 2 ;;
    --wall-clock-limit-sec) WALL_CLOCK_LIMIT_SEC="${2:-}"; shift 2 ;;
    --on-wall-clock-limit) ON_WALL_CLOCK_LIMIT="${2:-}"; shift 2 ;;
    --first-work-item-stale-sec) FIRST_WORK_ITEM_STALE_SEC="${2:-}"; shift 2 ;;
    --first-work-item-terminate-sec) FIRST_WORK_ITEM_TERMINATE_SEC="${2:-}"; shift 2 ;;
    --on-no-work-items) ON_NO_WORK_ITEMS="${2:-}"; shift 2 ;;
    --idle-kill-sec|--idle-timeout-sec) IDLE_KILL_SEC="${2:-}"; shift 2 ;;
    --silent-soft-limit-sec) SILENT_SOFT_LIMIT_SEC="${2:-}"; shift 2 ;;
    --stale-notice-sec) STALE_NOTICE_SEC="${2:-}"; shift 2 ;;
    --progress-report-sec) PROGRESS_REPORT_SEC="${2:-}"; shift 2 ;;
    --terminal-candidate-idle-sec) TERMINAL_CANDIDATE_IDLE_SEC="${2:-}"; shift 2 ;;
    --on-terminal-candidate) ON_TERMINAL_CANDIDATE="${2:-}"; shift 2 ;;
    --progress-suspect-age-sec) PROGRESS_SUSPECT_AGE_SEC="${2:-}"; shift 2 ;;
    --on-progress-suspect) ON_PROGRESS_SUSPECT="${2:-}"; shift 2 ;;
    --goal-completion-nudge) GOAL_COMPLETION_NUDGE="1"; shift 1 ;;
    --mcp-policy) MCP_POLICY="${2:-}"; shift 2 ;;
    --mcp-allow|--mcp-allowlist) MCP_ALLOW="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 64 ;;
  esac
done

[[ -n "$CYCLE_DIR" && -n "$OUTCOME_FILE" && -n "$EVIDENCE_DIR" ]] || { usage; exit 64; }
case "$MCP_POLICY" in clean|allowlist|full) ;; *) echo "invalid --mcp-policy: $MCP_POLICY" >&2; exit 64 ;; esac
case "$ON_NO_WORK_ITEMS" in mark_stale|terminate) ;; *) echo "invalid --on-no-work-items: $ON_NO_WORK_ITEMS" >&2; exit 64 ;; esac
case "$ON_TERMINAL_CANDIDATE" in ""|observe|terminate) ;; *) echo "invalid --on-terminal-candidate: $ON_TERMINAL_CANDIDATE" >&2; exit 64 ;; esac
case "$ON_PROGRESS_SUSPECT" in ""|observe|annotate|needs_human) ;; *) echo "invalid --on-progress-suspect: $ON_PROGRESS_SUSPECT" >&2; exit 64 ;; esac
if [[ -n "$WORKTREE_CWD" ]]; then
  [[ -d "$WORKTREE_CWD" ]] || { echo "invalid --worktree: not a directory: $WORKTREE_CWD" >&2; exit 64; }
  DRIVER_CWD="$(git -C "$WORKTREE_CWD" rev-parse --show-toplevel 2>/dev/null)" || { echo "invalid --worktree: not a git worktree: $WORKTREE_CWD" >&2; exit 64; }
else
  DRIVER_CWD="$(git rev-parse --show-toplevel)"
fi

ROUND="0"
if [[ -n "$FIX_ROUND" ]]; then
  if ! [[ "$FIX_ROUND" =~ ^[1-9][0-9]*$ ]]; then
    echo '{"conduct_result":"reshape_missing","exit":5,"reason":"invalid_fix_round"}'
    exit 5
  fi
  ROUND="$FIX_ROUND"
  PREV_ROUND=$((FIX_ROUND - 1))
  ARCHIVE_NAME="outcome.v${PREV_ROUND}.md"
  GRADE_NAME="grade_round_${PREV_ROUND}.md"
  ARCHIVE="$CYCLE_DIR/$ARCHIVE_NAME"
  GRADE="$CYCLE_DIR/$GRADE_NAME"
  MARKER_RE="<!--[[:space:]]*bs-fix-round:[[:space:]]*${FIX_ROUND};[[:space:]]*archive=outcome[.]v${PREV_ROUND}[.]md;[[:space:]]*grade=grade_round_${PREV_ROUND}[.]md;[[:space:]]*failed=\[[^]]*\][[:space:]]*-->"
  if [[ ! -f "$ARCHIVE" || ! -f "$GRADE" ]] || ! grep -Eq "$MARKER_RE" "$OUTCOME_FILE"; then
    echo '{"conduct_result":"reshape_missing","exit":5}'
    exit 5
  fi
fi

ROUND_EVIDENCE_DIR="$EVIDENCE_DIR/conduct_round_${ROUND}"
command -v codex >/dev/null 2>&1 || { echo '{"conduct_result":"launch_fatal","exit":4,"reason":"codex binary missing"}'; exit 4; }
codex login status >/dev/null 2>&1 || { echo '{"conduct_result":"launch_fatal","exit":4,"reason":"codex login required"}'; exit 4; }

RUNTIME_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DRIVER="$RUNTIME_DIR/codex_driver.py"
[[ -z "$FIX_ROUND" ]] || DRIVER="$RUNTIME_DIR/codex_fix_driver.py"
PRE_HEAD=""
if [[ -n "$FIX_ROUND" ]]; then
  PRE_HEAD="$(git -C "$DRIVER_CWD" rev-parse HEAD 2>/dev/null || true)"
fi
REAL_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
TEMP_HOMES=()
cleanup_temp_homes() {
  local d
  for d in "${TEMP_HOMES[@]:-}"; do
    if [[ -n "$d" && -d "$d" ]]; then
      rm -rf -- "$d" || true
    fi
  done
  return 0
}
trap cleanup_temp_homes EXIT

build_clean_home() {
  local policy="$1"
  local allow="$2"
  local home
  home="$(mktemp -d "${TMPDIR:-/tmp}/bs-codex-home.XXXXXX")"
  TEMP_HOMES+=("$home")
  [[ -f "$REAL_CODEX_HOME/auth.json" ]] && cp "$REAL_CODEX_HOME/auth.json" "$home/auth.json"
  python3 - "$REAL_CODEX_HOME/config.toml" "$home/config.toml" "$policy" "$allow" <<'PY'
import re, sys
src, dst, policy, allow = sys.argv[1:5]
allowed = {x for x in allow.split(',') if x}
try:
    text = open(src, encoding='utf-8').read()
except OSError:
    text = ''
blocks = []
if policy == 'allowlist' and text:
    matches = list(re.finditer(r'^\[mcp_servers\.([^\]]+)\]\s*$', text, flags=re.M))
    for i, m in enumerate(matches):
        name = m.group(1).strip('"')
        if name not in allowed:
            continue
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append(text[start:end].strip())
with open(dst, 'w', encoding='utf-8') as f:
    f.write('# generated by bs conduct clean MCP policy\n')
    if blocks:
        f.write('\n\n'.join(blocks) + '\n')
PY
  printf '%s\n' "$home"
}

real_mcp_servers() {
  python3 - "$REAL_CODEX_HOME/config.toml" <<'PY'
import re, sys
try:
    text = open(sys.argv[1], encoding='utf-8').read()
except OSError:
    text = ''
names = []
for m in re.finditer(r'^\[mcp_servers\.([^\]]+)\]\s*$', text, flags=re.M):
    names.append(m.group(1).strip('"'))
print(','.join(sorted(set(names))))
PY
}

suppressed_mcp_servers() {
  local policy="$1"
  local real_csv="$2"
  local allow_csv="$3"
  python3 - "$policy" "$real_csv" "$allow_csv" <<'PY'
import sys
policy, real_csv, allow_csv = sys.argv[1:4]
real = {x for x in real_csv.split(',') if x}
allow = {x for x in allow_csv.split(',') if x}
if policy == 'full':
    suppressed = set()
elif policy == 'allowlist':
    suppressed = real - allow
else:
    suppressed = real
print(','.join(sorted(suppressed)))
PY
}

common_args() {
  ARGS=("$DRIVER" --cwd "$DRIVER_CWD" --outcome-file "$OUTCOME_FILE" --evidence-dir "$ROUND_EVIDENCE_DIR" --effort "$EFFORT" --expected-effect-kind "$EXPECTED_EFFECT_KIND" --expected-effect-required "$EXPECTED_EFFECT_REQUIRED" --on-wall-clock-limit "$ON_WALL_CLOCK_LIMIT" --mcp-policy "$1" --mcp-allowlist "$MCP_ALLOW" --binding-mcp-policy "$MCP_POLICY")
  [[ "$1" == "clean" || "$1" == "allowlist" ]] && ARGS+=(--clean-codex-home)
  [[ -z "$MODEL" ]] || ARGS+=(--model "$MODEL")
  [[ -z "$WALL_CLOCK_LIMIT_SEC" ]] || ARGS+=(--wall-clock-limit-sec "$WALL_CLOCK_LIMIT_SEC")
  [[ -z "$FIRST_WORK_ITEM_STALE_SEC" ]] || ARGS+=(--first-work-item-stale-sec "$FIRST_WORK_ITEM_STALE_SEC")
  [[ -z "$FIRST_WORK_ITEM_TERMINATE_SEC" ]] || ARGS+=(--first-work-item-terminate-sec "$FIRST_WORK_ITEM_TERMINATE_SEC")
  [[ -z "$ON_NO_WORK_ITEMS" ]] || ARGS+=(--on-no-work-items "$ON_NO_WORK_ITEMS")
  [[ -z "$IDLE_KILL_SEC" ]] || ARGS+=(--idle-timeout-sec "$IDLE_KILL_SEC")
  [[ -z "$SILENT_SOFT_LIMIT_SEC" ]] || ARGS+=(--silent-soft-limit-sec "$SILENT_SOFT_LIMIT_SEC")
  [[ -z "$STALE_NOTICE_SEC" ]] || ARGS+=(--stale-notice-sec "$STALE_NOTICE_SEC")
  [[ -z "$PROGRESS_REPORT_SEC" ]] || ARGS+=(--progress-report-sec "$PROGRESS_REPORT_SEC")
  [[ -z "$TERMINAL_CANDIDATE_IDLE_SEC" ]] || ARGS+=(--terminal-candidate-idle-sec "$TERMINAL_CANDIDATE_IDLE_SEC")
  [[ -z "$ON_TERMINAL_CANDIDATE" ]] || ARGS+=(--on-terminal-candidate "$ON_TERMINAL_CANDIDATE")
  [[ -z "$PROGRESS_SUSPECT_AGE_SEC" ]] || ARGS+=(--progress-suspect-age-sec "$PROGRESS_SUSPECT_AGE_SEC")
  [[ -z "$ON_PROGRESS_SUSPECT" ]] || ARGS+=(--on-progress-suspect "$ON_PROGRESS_SUSPECT")
  [[ -z "$GOAL_COMPLETION_NUDGE" ]] || ARGS+=(--goal-completion-nudge)
}

run_driver_once() {
  local policy="$1"
  local effective_home="$REAL_CODEX_HOME"
  local clean="false"
  local real_servers suppressed=""
  real_servers="$(real_mcp_servers)"
  if [[ "$policy" == "clean" || "$policy" == "allowlist" ]]; then
    effective_home="$(build_clean_home "$policy" "$MCP_ALLOW")"
    clean="true"
  fi
  suppressed="$(suppressed_mcp_servers "$policy" "$real_servers" "$MCP_ALLOW")"
  common_args "$policy"
  [[ -z "$suppressed" ]] || ARGS+=(--suppressed-mcp-servers "$suppressed")
  set +e
  if [[ "$clean" == "true" ]]; then
    CODEX_HOME="$effective_home" env -u CODEX_BIN -u BS_TEST_FAKE_CODEX python3 "${ARGS[@]}"
  else
    env -u CODEX_BIN -u BS_TEST_FAKE_CODEX python3 "${ARGS[@]}"
  fi
  local rc=$?
  set +e
  return "$rc"
}

collect_changed_files() {
  local wt="$1"
  local pre_head="$2"
  local out="$3"
  : > "$out"
  if [[ -n "$pre_head" ]]; then
    git -C "$wt" diff --name-only "$pre_head" >> "$out" 2>/dev/null || true
  fi
  git -C "$wt" diff --name-only >> "$out" 2>/dev/null || true
  git -C "$wt" diff --cached --name-only >> "$out" 2>/dev/null || true
  git -C "$wt" ls-files --others --exclude-standard >> "$out" 2>/dev/null || true
  sort -u "$out" -o "$out"
}

run_fix_round_alignment_gate() {
  local sidecar="$CYCLE_DIR/fix_round_${FIX_ROUND}_alignment.yaml"
  local changed_file="${1:-}"
  local own_changed_file="false"
  local alignment_file align_rc aligned
  if [[ -z "$FIX_ROUND" || ! -f "$sidecar" ]]; then
    return 0
  fi
  if [[ -z "$changed_file" ]]; then
    changed_file="$(mktemp "${TMPDIR:-/tmp}/bs-fix-round-changed.XXXXXX")"
    own_changed_file="true"
    collect_changed_files "$DRIVER_CWD" "$PRE_HEAD" "$changed_file"
  fi
  alignment_file="$(mktemp "${TMPDIR:-/tmp}/bs-fix-round-alignment.XXXXXX")"
  set +e
  python3 "$RUNTIME_DIR/reshape_fix_round.py" alignment --sidecar "$sidecar" --changed-files-file "$changed_file" > "$alignment_file"
  align_rc=$?
  set -e
  aligned="$(python3 - "$alignment_file" <<'PY' 2>/dev/null || true
import json, sys
try:
    obj = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(1)
print("true" if obj.get("aligned") else "false")
PY
)"
  if [[ "$aligned" == "false" ]]; then
    python3 - "$alignment_file" "$changed_file" <<'PY'
import json, sys
alignment_path, changed_path = sys.argv[1:3]
alignment = json.load(open(alignment_path, encoding="utf-8"))
with open(changed_path, encoding="utf-8") as f:
    changed = [line.rstrip("\n") for line in f if line.rstrip("\n")]
payload = {
    "conduct_result": "fix_round_misaligned",
    "exit": 9,
    "alignment_reason": alignment.get("reason", ""),
    "required_production_loci": alignment.get("required_production_loci", []),
    "changed_files": changed,
}
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
PY
    [[ "$own_changed_file" == "false" ]] || rm -f "$changed_file"
    rm -f "$alignment_file"
    exit 9
  fi
  [[ "$own_changed_file" == "false" ]] || rm -f "$changed_file"
  rm -f "$alignment_file"
  [[ "$align_rc" == "0" ]] && FIX_ROUND_ALIGNMENT_STATUS="aligned"
  return 0
}

run_fix_round_uptake_gate() {
  local changed_file="$1"
  if [[ -z "$FIX_ROUND" || ! -s "$changed_file" ]]; then
    return 0
  fi
  set +e
  python3 - "$OUTCOME_FILE" "$changed_file" "$DRIVER_CWD" "$EVIDENCE_DIR" <<'PY'
import json, re, sys
from pathlib import Path

outcome = Path(sys.argv[1])
changed_file = Path(sys.argv[2])
cwd = Path(sys.argv[3])
evidence_dir = Path(sys.argv[4]).resolve()
text = outcome.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)
plain = [line.rstrip("\n").rstrip("\r") for line in lines]
marker_re = re.compile(r"<!--\s*bs-fix-round:\s*(\d+);[^>]*-->")
corrections_re = re.compile(r"^\s*Corrections:\s*(.*)$", re.I)
list_item_re = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+\S")
marker_line = None
for idx, line in enumerate(plain, start=1):
    if marker_re.search(line):
        marker_line = idx
if marker_line is None:
    sys.exit(0)
start_line = None
for idx in range(marker_line - 1, 0, -1):
    match = corrections_re.match(plain[idx - 1])
    if not match:
        continue
    if match.group(1).strip().lower() == "none":
        sys.exit(0)
    start_line = idx
    break
if start_line is None:
    sys.exit(0)
if not any(list_item_re.match(plain[idx - 1]) for idx in range(start_line + 1, marker_line)):
    sys.exit(0)
block = "".join(lines[start_line - 1:marker_line])
skip = {
    "const","type","true","false","null","undefined","return","import","from","with",
    "inside","mirror","first","second","before","after","missing","add","line","rows",
}
probes = []
seen = set()

def add(raw):
    raw = str(raw).strip().strip("`'\"()[]{}<>,;:")
    if len(raw) < 4 or raw in skip:
        return
    if raw not in seen:
        seen.add(raw)
        probes.append(raw)

for match in re.finditer(r"`([^`]+)`|\"((?:[^\"\\]|\\.)*)\"", block):
    backtick, quoted = match.groups()
    if backtick is not None:
        add(backtick)
        for token in re.findall(r"[A-Za-z0-9_.@/-]*[A-Za-z_][A-Za-z0-9_.@/-]*", backtick):
            add(token)
            if "/" in token:
                add(token.rsplit("/", 1)[-1])
    else:
        add(quoted)
        if "\\n" in quoted:
            add(quoted.replace("\\n", "\n"))
for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b", block):
    add(token)
for token in re.findall(r"\b[A-Za-z][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)+\b", block):
    add(token)
for token in re.findall(r"\b[A-Za-z0-9_.-]+\.(?:d\.ts|tsx|ts|jsx|js|rs|py|md)\b", block):
    add(token)
if not probes:
    sys.exit(0)
changed = [line.strip() for line in changed_file.read_text(encoding="utf-8").splitlines() if line.strip()]
content_parts = []
for rel in changed:
    path = (cwd / rel).resolve()
    try:
        path.relative_to(cwd.resolve())
    except ValueError:
        continue
    try:
        path.relative_to(evidence_dir)
        continue
    except ValueError:
        pass
    if not path.is_file():
        continue
    try:
        content_parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        pass
content = "\n".join(content_parts)
matched = [probe for probe in probes if probe in content]
if not matched:
    payload = {
        "conduct_result": "fix_round_zero_uptake",
        "exit": 10,
        "required_markers": probes,
        "matched_markers": [],
        "corrections_start_line": start_line,
        "changed_files": changed,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    sys.exit(10)
sys.exit(0)
PY
  local uptake_rc=$?
  set -e
  if [[ "$uptake_rc" == "10" ]]; then
    exit 10
  fi
  return "$uptake_rc"
}

FIX_ROUND_ALIGNMENT_STATUS=""

set +e
run_driver_once "$MCP_POLICY"
rc=$?
set -e
if [[ "$rc" == "7" && "$MCP_POLICY" != "clean" ]]; then
  if [[ -f "$ROUND_EVIDENCE_DIR/codex_env.json" ]]; then
    cp "$ROUND_EVIDENCE_DIR/codex_env.json" "$ROUND_EVIDENCE_DIR/codex_env.before_clean_retry.json" || true
  fi
  set +e
  run_driver_once "clean"
  rc=$?
  set -e
fi

case "$rc" in
  0) result="completed" ;;
  2) result="turn_failed" ;;
  3) result="launch_exhausted" ;;
  4) result="launch_fatal" ;;
  6) result="semantic_failed" ;;
  7) result="no_work_items" ;;
  8) result="interrupted_with_delta" ;;
  *) result="failed" ;;
esac
if [[ -n "$FIX_ROUND" && ( "$rc" == "0" || "$rc" == "6" || "$rc" == "8" ) ]]; then
  FIX_ROUND_CHANGED_FILE="$(mktemp "${TMPDIR:-/tmp}/bs-fix-round-changed.XXXXXX")"
  collect_changed_files "$DRIVER_CWD" "$PRE_HEAD" "$FIX_ROUND_CHANGED_FILE"
  if [[ -s "$FIX_ROUND_CHANGED_FILE" ]]; then
    run_fix_round_uptake_gate "$FIX_ROUND_CHANGED_FILE"
    run_fix_round_alignment_gate "$FIX_ROUND_CHANGED_FILE"
  fi
  rm -f "$FIX_ROUND_CHANGED_FILE"
fi
if [[ -n "$FIX_ROUND_ALIGNMENT_STATUS" ]]; then
  printf '{"conduct_result":"%s","exit":%s,"round":%s,"mcp_policy":"%s","fix_round_alignment":"%s"}\n' "$result" "$rc" "$ROUND" "$MCP_POLICY" "$FIX_ROUND_ALIGNMENT_STATUS"
else
  printf '{"conduct_result":"%s","exit":%s,"round":%s,"mcp_policy":"%s"}\n' "$result" "$rc" "$ROUND" "$MCP_POLICY"
fi
exit "$rc"
