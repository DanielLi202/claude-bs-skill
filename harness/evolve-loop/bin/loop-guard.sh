#!/usr/bin/env bash
# bs-evolve-loop guard — enforces single-iteration SERIAL execution + the kill-switch.
#
# The orchestrator (a Claude agent, not a unix process) holds the lock across many
# tool calls, so liveness is a TIME LEASE, not a pid check: a lock older than
# BS_LOOP_LOCK_STALE_SEC (default 2h) is treated as abandoned.
#
# Usage: loop-guard.sh <acquire|release|check-stop> [STATE_DIR]
#   STATE_DIR defaults to $BS_LOOP_STATE_DIR.
# Exit:  0 ok | 10 STOP file present (END loop) | 11 lock held (another iteration live)
#        | 1 usage/error
set -euo pipefail

cmd="${1:-}"
STATE_DIR="${2:-${BS_LOOP_STATE_DIR:-}}"
[ -n "$STATE_DIR" ] || { echo "loop-guard: STATE_DIR required (arg2 or \$BS_LOOP_STATE_DIR)" >&2; exit 1; }
mkdir -p "$STATE_DIR"
STOP="$STATE_DIR/STOP"
LOCK="$STATE_DIR/RUNNING.lock"

# file mtime in epoch seconds, guaranteed integer (GNU stat first, then BSD, else 0)
mtime() {
  local m
  m="$(stat -c %Y "$1" 2>/dev/null)" || m="$(stat -f %m "$1" 2>/dev/null)" || m=0
  case "$m" in ''|*[!0-9]*) m=0 ;; esac
  printf '%s' "$m"
}

case "$cmd" in
  check-stop)
    [ -e "$STOP" ] && { echo "stop_file"; exit 10; }
    exit 0 ;;
  acquire)
    [ -e "$STOP" ] && { echo "stop_file"; exit 10; }
    if [ -e "$LOCK" ]; then
      lock_m="$(mtime "$LOCK")"; now="$(date +%s)"; age=$(( now - lock_m ))
      stale="${BS_LOOP_LOCK_STALE_SEC:-7200}"
      if [ "$age" -lt "$stale" ]; then
        info="$(head -1 "$LOCK" 2>/dev/null || true)"
        echo "locked age=${age}s (${info})"; exit 11
      fi
      echo "loop-guard: clearing stale lock age=${age}s" >&2
    fi
    printf 'pid=%s started=%s host=%s\n' "$$" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(hostname)" > "$LOCK"
    exit 0 ;;
  release)
    rm -f "$LOCK"
    exit 0 ;;
  *)
    echo "usage: loop-guard.sh <acquire|release|check-stop> [STATE_DIR]" >&2; exit 1 ;;
esac
