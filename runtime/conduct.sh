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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cycle-dir) CYCLE_DIR="${2:-}"; shift 2 ;;
    --outcome-file) OUTCOME_FILE="${2:-}"; shift 2 ;;
    --evidence-dir) EVIDENCE_DIR="${2:-}"; shift 2 ;;
    --fix-round) FIX_ROUND="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --effort) EFFORT="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 64 ;;
  esac
done

[[ -n "$CYCLE_DIR" && -n "$OUTCOME_FILE" && -n "$EVIDENCE_DIR" ]] || { usage; exit 64; }
command -v codex >/dev/null 2>&1 || { echo '{"conduct_result":"launch_fatal","exit":4,"reason":"codex binary missing"}'; exit 4; }
codex login status >/dev/null 2>&1 || { echo '{"conduct_result":"launch_fatal","exit":4,"reason":"codex login required"}'; exit 4; }

RUNTIME_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DRIVER="$RUNTIME_DIR/codex_driver.py"
[[ -z "$FIX_ROUND" ]] || DRIVER="$RUNTIME_DIR/codex_fix_driver.py"

ARGS=("$DRIVER" --cwd "$(git rev-parse --show-toplevel)" --outcome-file "$OUTCOME_FILE" --evidence-dir "$EVIDENCE_DIR" --effort "$EFFORT")
[[ -z "$MODEL" ]] || ARGS+=(--model "$MODEL")

set +e
env -u CODEX_BIN -u BS_TEST_FAKE_CODEX python3 "${ARGS[@]}"
rc=$?
set -e
case "$rc" in
  0) result="completed" ;;
  2) result="turn_failed" ;;
  3) result="launch_exhausted" ;;
  4) result="launch_fatal" ;;
  *) result="failed" ;;
esac
printf '{"conduct_result":"%s","exit":%s}\n' "$result" "$rc"
exit "$rc"
