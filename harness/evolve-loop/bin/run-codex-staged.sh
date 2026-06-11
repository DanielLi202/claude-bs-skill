#!/usr/bin/env bash
# bs-evolve-loop staged codex runner — fail-closed wall-clock budget + inflight record.
#
# Born from the cycle-019 incident: a remediation codex hung 12h+ and the loop never
# woke (a held turn freezes all ScheduleWakeup firings). Supervision therefore cannot
# live only in wakeups — every codex invocation must be bounded AT THE CALL BOUNDARY,
# so the call ALWAYS returns within budget and a hang becomes an ordinary stage failure.
#
# Usage:
#   run-codex-staged.sh --stage TAG --budget SECONDS --prompt FILE --log FILE \
#                       [--cwd DIR] [-- extra codex args...]
# Runs: codex exec --skip-git-repo-check -C CWD -c model_reasoning_effort="xhigh" \
#         <extra args> - < PROMPT > LOG 2>&1   in its OWN PROCESS GROUP, and:
#   * writes $BS_LOOP_STATE_DIR/inflight/<TAG>.json {pgid,started_at,budget,log} so a
#     takeover probe can detect/reap a dead or overdue stage;
#   * at budget: SIGTERM the whole group, +60s grace then SIGKILL; always reaps;
#   * removes the inflight record on every exit path.
# Exit: codex's exit code | 124 budget exceeded | 2 usage/env
set -uo pipefail

STAGE=""; BUDGET=""; PROMPT=""; LOG=""; CWD="."
EXTRA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --stage) STAGE="$2"; shift 2 ;;
    --budget) BUDGET="$2"; shift 2 ;;
    --prompt) PROMPT="$2"; shift 2 ;;
    --log) LOG="$2"; shift 2 ;;
    --cwd) CWD="$2"; shift 2 ;;
    --) shift; EXTRA=("$@"); break ;;
    *) echo "run-codex-staged: bad arg $1" >&2; exit 2 ;;
  esac
done
[ -n "$STAGE" ] && [ -n "$BUDGET" ] && [ -n "$PROMPT" ] && [ -n "$LOG" ] || { echo "need --stage --budget --prompt --log" >&2; exit 2; }
[ -n "${BS_LOOP_STATE_DIR:-}" ] || { echo "BS_LOOP_STATE_DIR required" >&2; exit 2; }
[ -f "$PROMPT" ] || { echo "prompt file missing: $PROMPT" >&2; exit 2; }
INFLIGHT_DIR="$BS_LOOP_STATE_DIR/inflight"; mkdir -p "$INFLIGHT_DIR"
INFLIGHT="$INFLIGHT_DIR/$STAGE.json"
TIMED_OUT_MARK="$INFLIGHT_DIR/$STAGE.timeout"

set -m   # job control: the background job below becomes its own process-group leader
codex exec --skip-git-repo-check -C "$CWD" -c model_reasoning_effort="xhigh" \
  "${EXTRA[@]}" - < "$PROMPT" > "$LOG" 2>&1 &
PID=$!; PGID=$PID
printf '{"stage":"%s","pgid":%d,"started_at":"%s","budget_sec":%s,"log":"%s"}\n' \
  "$STAGE" "$PGID" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$BUDGET" "$LOG" > "$INFLIGHT"

rm -f "$TIMED_OUT_MARK"
(
  sleep "$BUDGET"
  touch "$TIMED_OUT_MARK"
  kill -TERM -- -"$PGID" 2>/dev/null
  sleep 60
  kill -KILL -- -"$PGID" 2>/dev/null
) &
WATCHDOG=$!

wait "$PID"; RC=$?
# stop the watchdog (and its sleeps) without signalling ourselves
kill "$WATCHDOG" 2>/dev/null; pkill -P "$WATCHDOG" 2>/dev/null; wait "$WATCHDOG" 2>/dev/null
# belt-and-braces: reap any survivors in the group
kill -KILL -- -"$PGID" 2>/dev/null
rm -f "$INFLIGHT"
if [ -f "$TIMED_OUT_MARK" ]; then
  rm -f "$TIMED_OUT_MARK"
  echo "run-codex-staged: stage=$STAGE EXCEEDED budget ${BUDGET}s — group reaped" >&2
  exit 124
fi
exit "$RC"
