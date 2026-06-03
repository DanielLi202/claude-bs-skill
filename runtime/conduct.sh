#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: conduct.sh --cycle-dir ABS --outcome-file PATH --evidence-dir PATH [--fix-round N] [--model M] [--effort E]
EOF
}

CYCLE_DIR=""
OUTCOME_FILE=""
EVIDENCE_DIR=""
FIX_ROUND=""
MODEL=""
EFFORT="low"
EXPECTED_EFFECT_KIND="workspace_delta"
EXPECTED_EFFECT_REQUIRED="true"
WALL_CLOCK_LIMIT_SEC=""
ON_WALL_CLOCK_LIMIT="mark_stale"
IDLE_KILL_SEC=""
SILENT_SOFT_LIMIT_SEC=""
STALE_NOTICE_SEC=""
PROGRESS_REPORT_SEC=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cycle-dir) CYCLE_DIR="${2:-}"; shift 2 ;;
    --outcome-file) OUTCOME_FILE="${2:-}"; shift 2 ;;
    --evidence-dir) EVIDENCE_DIR="${2:-}"; shift 2 ;;
    --fix-round) FIX_ROUND="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --effort) EFFORT="${2:-}"; shift 2 ;;
    --expected-effect-kind) EXPECTED_EFFECT_KIND="${2:-}"; shift 2 ;;
    --expected-effect-required) EXPECTED_EFFECT_REQUIRED="${2:-}"; shift 2 ;;
    --wall-clock-limit-sec) WALL_CLOCK_LIMIT_SEC="${2:-}"; shift 2 ;;
    --on-wall-clock-limit) ON_WALL_CLOCK_LIMIT="${2:-}"; shift 2 ;;
    --idle-kill-sec|--idle-timeout-sec) IDLE_KILL_SEC="${2:-}"; shift 2 ;;
    --silent-soft-limit-sec) SILENT_SOFT_LIMIT_SEC="${2:-}"; shift 2 ;;
    --stale-notice-sec) STALE_NOTICE_SEC="${2:-}"; shift 2 ;;
    --progress-report-sec) PROGRESS_REPORT_SEC="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 64 ;;
  esac
done

[[ -n "$CYCLE_DIR" && -n "$OUTCOME_FILE" && -n "$EVIDENCE_DIR" ]] || { usage; exit 64; }

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
  MARKER_RE="<!--[[:space:]]*bs-fix-round:[[:space:]]*${FIX_ROUND};[[:space:]]*archive=outcome[.]v${PREV_ROUND}[.]md;[[:space:]]*grade=grade_round_${PREV_ROUND}[.]md;"
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

ARGS=("$DRIVER" --cwd "$(git rev-parse --show-toplevel)" --outcome-file "$OUTCOME_FILE" --evidence-dir "$ROUND_EVIDENCE_DIR" --effort "$EFFORT" --expected-effect-kind "$EXPECTED_EFFECT_KIND" --expected-effect-required "$EXPECTED_EFFECT_REQUIRED" --on-wall-clock-limit "$ON_WALL_CLOCK_LIMIT")
[[ -z "$MODEL" ]] || ARGS+=(--model "$MODEL")
[[ -z "$WALL_CLOCK_LIMIT_SEC" ]] || ARGS+=(--wall-clock-limit-sec "$WALL_CLOCK_LIMIT_SEC")
[[ -z "$IDLE_KILL_SEC" ]] || ARGS+=(--idle-timeout-sec "$IDLE_KILL_SEC")
[[ -z "$SILENT_SOFT_LIMIT_SEC" ]] || ARGS+=(--silent-soft-limit-sec "$SILENT_SOFT_LIMIT_SEC")
[[ -z "$STALE_NOTICE_SEC" ]] || ARGS+=(--stale-notice-sec "$STALE_NOTICE_SEC")
[[ -z "$PROGRESS_REPORT_SEC" ]] || ARGS+=(--progress-report-sec "$PROGRESS_REPORT_SEC")

set +e
env -u CODEX_BIN -u BS_TEST_FAKE_CODEX python3 "${ARGS[@]}"
rc=$?
set -e
case "$rc" in
  0) result="completed" ;;
  2) result="turn_failed" ;;
  3) result="launch_exhausted" ;;
  4) result="launch_fatal" ;;
  6) result="semantic_failed" ;;
  *) result="failed" ;;
esac
printf '{"conduct_result":"%s","exit":%s,"round":%s}\n' "$result" "$rc" "$ROUND"
exit "$rc"
