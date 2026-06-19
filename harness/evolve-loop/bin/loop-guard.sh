#!/usr/bin/env bash
# bs-evolve-loop guard — STOP check plus tokened atomic RUNNING.lock wrapper.
#
# Usage: loop-guard.sh <acquire|heartbeat|release|status|check-stop> [STATE_DIR] [TOKEN]
#   STATE_DIR defaults to $BS_LOOP_STATE_DIR.
#   acquire prints JSON containing owner_token; heartbeat/release require TOKEN or
#   $BS_LOOP_LOCK_TOKEN and compare it to the persisted owner token.
# Exit: 0 ok | 10 STOP file present | 11 lock held | 12 token mismatch | 1 usage/error
set -euo pipefail

cmd="${1:-}"
STATE_DIR="${2:-${BS_LOOP_STATE_DIR:-}}"
TOKEN="${3:-${BS_LOOP_LOCK_TOKEN:-}}"
[ -n "$STATE_DIR" ] || { echo "loop-guard: STATE_DIR required (arg2 or \$BS_LOOP_STATE_DIR)" >&2; exit 1; }
mkdir -p "$STATE_DIR"
STOP="$STATE_DIR/STOP"
LOCK="$STATE_DIR/RUNNING.lock"
INFLIGHT="$STATE_DIR/inflight"
HELPER="$(cd "$(dirname "$0")" && pwd)/evolve-lock.py"

case "$cmd" in
  check-stop)
    [ -e "$STOP" ] && { echo "stop_file"; exit 10; }
    exit 0 ;;
  acquire)
    [ -e "$STOP" ] && { echo "stop_file"; exit 10; }
    exec python3 "$HELPER" acquire --lock-file "$LOCK" --inflight-dir "$INFLIGHT" --owner "project:$STATE_DIR" ;;
  heartbeat)
    [ -n "$TOKEN" ] || { echo "loop-guard: token required for heartbeat" >&2; exit 1; }
    exec python3 "$HELPER" heartbeat --lock-file "$LOCK" --token "$TOKEN" ;;
  release)
    [ -n "$TOKEN" ] || { echo "loop-guard: token required for release" >&2; exit 1; }
    exec python3 "$HELPER" release --lock-file "$LOCK" --token "$TOKEN" ;;
  status)
    exec python3 "$HELPER" status --lock-file "$LOCK" ;;
  *)
    echo "usage: loop-guard.sh <acquire|heartbeat|release|status|check-stop> [STATE_DIR] [TOKEN]" >&2; exit 1 ;;
esac
