#!/usr/bin/env bash
# bs-evolve-loop staged codex runner — LIVENESS-based supervision (maintainer ruling:
# duration never kills; only "no longer working" is an exception).
#
# Three liveness signals, sampled every --sample-sec; ANY advancing = alive:
#   1. log growth (codex exec streams thinking/tool events into --log)
#   2. process-group CPU-time delta (quiet codex whose child burns CPU, e.g. cargo)
#   3. workdir file activity (quiet edits/writes)
# ALL silent for --stall-sec  =>  evidence snapshot -> TERM -> +60s KILL of the whole
# group -> exit 125 (stalled). A hang becomes an ordinary stage failure.
#
# SUSPICION (fake-alive: busy-loops that look alive) is detected but NEVER kills —
# it is written into the inflight record for the orchestrator's check-in JUDGMENT:
#   * repetitive_output: a 5-sample window adds >=30 log lines but <5% never-seen-before
#   * workspace_stagnant (--expect-writes only): log grew across 3 windows while the
#     git workspace hash never changed
#
# Inflight record $BS_LOOP_STATE_DIR/inflight/<stage>.json is refreshed every sample
# (last_progress_at, suspect[]) so check-in wakes and takeover probes read REAL state.
#
# Usage:
#   run-codex-staged.sh --stage TAG --prompt FILE --log FILE [--cwd DIR]
#                       [--stall-sec 1200] [--sample-sec 60] [--expect-writes]
#                       [-- extra codex args...]
# Exit: codex's exit code | 125 stalled | 2 usage/env
set -uo pipefail

STAGE=""; PROMPT=""; LOG=""; CWD="."
STALL_SEC=1200; SAMPLE_SEC=60; EXPECT_WRITES=0
EXTRA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --stage) STAGE="$2"; shift 2 ;;
    --prompt) PROMPT="$2"; shift 2 ;;
    --log) LOG="$2"; shift 2 ;;
    --cwd) CWD="$2"; shift 2 ;;
    --stall-sec) STALL_SEC="$2"; shift 2 ;;
    --sample-sec) SAMPLE_SEC="$2"; shift 2 ;;
    --expect-writes) EXPECT_WRITES=1; shift ;;
    --) shift; EXTRA=("$@"); break ;;
    *) echo "run-codex-staged: bad arg $1" >&2; exit 2 ;;
  esac
done
[ -n "$STAGE" ] && [ -n "$PROMPT" ] && [ -n "$LOG" ] || { echo "need --stage --prompt --log" >&2; exit 2; }
[ -n "${BS_LOOP_STATE_DIR:-}" ] || { echo "BS_LOOP_STATE_DIR required" >&2; exit 2; }
[ -f "$PROMPT" ] || { echo "prompt file missing: $PROMPT" >&2; exit 2; }
INFLIGHT_DIR="$BS_LOOP_STATE_DIR/inflight"; mkdir -p "$INFLIGHT_DIR"
INFLIGHT="$INFLIGHT_DIR/$STAGE.json"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

log_size() { wc -c < "$LOG" 2>/dev/null | tr -d ' ' || echo 0; }
group_cpu() {  # summed CPU seconds of the process group
  ps -axo pgid=,time= 2>/dev/null | awk -v g="$1" '
    $1==g { n=split($2,p,":"); s=0; m=1
            for(i=n;i>=1;i--){ sub(/-/,":",p[i]); s+=p[i]*m; m*=60 }
            tot+=s }
    END { printf "%d", tot+0 }'
}
workdir_activity() {  # 1 if anything in CWD newer than the marker
  [ -e "$SCRATCH/fsmark" ] || { touch "$SCRATCH/fsmark"; echo 1; return; }
  if find "$CWD" -newer "$SCRATCH/fsmark" -not -path '*/.git/*' -print -quit 2>/dev/null | grep -q .; then
    touch "$SCRATCH/fsmark"; echo 1
  else echo 0; fi
}
ws_hash() { { git -C "$CWD" status --porcelain 2>/dev/null; git -C "$CWD" diff 2>/dev/null; } | shasum -a 256 | cut -c1-16; }
write_inflight() {  # $1 = suspect json array
  printf '{"stage":"%s","pgid":%d,"started_at":"%s","log":"%s","cwd":"%s","stall_sec":%s,"last_progress_at":"%s","suspect":%s}\n' \
    "$STAGE" "$PGID" "$STARTED" "$LOG" "$CWD" "$STALL_SEC" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" > "$INFLIGHT"
}

set -m   # job control: the codex job below leads its own process group
codex exec --skip-git-repo-check -C "$CWD" -c model_reasoning_effort="xhigh" \
  "${EXTRA[@]}" - < "$PROMPT" > "$LOG" 2>&1 &
PID=$!; PGID=$PID
STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
write_inflight '[]'

LAST_SIZE=$(log_size); LAST_CPU=$(group_cpu "$PGID"); QUIET=0
SUSPECT='[]'
WIN_N=0; WIN_OFFSET=0; SEEN="$SCRATCH/seen.lines"; : > "$SEEN"
WS_LAST=""; WS_SAME=0; WS_LOGGREW=0

while kill -0 "$PID" 2>/dev/null; do
  sleep "$SAMPLE_SEC" &
  SLEEPER=$!
  if ! wait "$SLEEPER" 2>/dev/null; then :; fi
  kill -0 "$PID" 2>/dev/null || break

  SIZE=$(log_size); CPU=$(group_cpu "$PGID"); FSACT=$(workdir_activity)
  PROGRESS=0
  [ "$SIZE" -gt "$LAST_SIZE" ] && PROGRESS=1
  [ "${CPU:-0}" -gt "${LAST_CPU:-0}" ] && PROGRESS=1
  [ "$FSACT" = "1" ] && PROGRESS=1

  if [ "$PROGRESS" = "1" ]; then
    QUIET=0
  else
    QUIET=$(( QUIET + SAMPLE_SEC ))
    if [ "$QUIET" -ge "$STALL_SEC" ]; then
      EV="$LOG.stall_evidence"; mkdir -p "$EV"
      { echo "stage=$STAGE pgid=$PGID quiet_sec=$QUIET stall_sec=$STALL_SEC at=$(date -u +%Y-%m-%dT%H:%M:%SZ)";
        echo "signals: log_size=$SIZE cpu=$CPU fs_activity=$FSACT"; } > "$EV/reason.txt"
      ps -axo pid=,pgid=,time=,command= | awk -v g="$PGID" '$2==g' > "$EV/process_group.txt" 2>/dev/null
      tail -c 20000 "$LOG" > "$EV/log_tail.txt" 2>/dev/null
      kill -TERM -- -"$PGID" 2>/dev/null
      for _ in $(seq 1 60); do kill -0 -- -"$PGID" 2>/dev/null || break; sleep 1; done
      kill -KILL -- -"$PGID" 2>/dev/null
      wait "$PID" 2>/dev/null
      rm -f "$INFLIGHT"
      echo "run-codex-staged: stage=$STAGE STALLED (all signals quiet ${QUIET}s) — group reaped; evidence: $EV" >&2
      exit 125
    fi
  fi

  # ---- suspicion (never kills) ----
  WIN_N=$(( WIN_N + 1 ))
  if [ $(( WIN_N % 5 )) -eq 0 ]; then
    # repetitive_output: new window lines vs everything seen before
    tail -c +"$(( WIN_OFFSET + 1 ))" "$LOG" 2>/dev/null > "$SCRATCH/win.raw"; WIN_OFFSET=$SIZE
    sort -u "$SCRATCH/win.raw" > "$SCRATCH/win.lines"
    TOTAL=$(wc -l < "$SCRATCH/win.raw" | tr -d ' ')
    NEW=$(comm -13 "$SEEN" "$SCRATCH/win.lines" | wc -l | tr -d ' ')
    sort -u -m "$SEEN" "$SCRATCH/win.lines" > "$SEEN.next" && mv "$SEEN.next" "$SEEN"
    S1=""
    if [ "${TOTAL:-0}" -ge 30 ] && [ $(( NEW * 100 )) -lt $(( TOTAL * 5 )) ]; then S1='"repetitive_output"'; fi
    # workspace_stagnant (write stages only)
    S2=""
    if [ "$EXPECT_WRITES" = "1" ] && git -C "$CWD" rev-parse --git-dir >/dev/null 2>&1; then
      H=$(ws_hash)
      if [ "$H" = "$WS_LAST" ]; then WS_SAME=$(( WS_SAME + 1 )); else WS_SAME=0; WS_LOGGREW=0; fi
      [ "$SIZE" -gt "$LAST_SIZE" ] && WS_LOGGREW=$(( WS_LOGGREW + 1 ))
      WS_LAST="$H"
      if [ "$WS_SAME" -ge 3 ] && [ "$WS_LOGGREW" -ge 3 ]; then S2='"workspace_stagnant"'; fi
    fi
    SUSPECT="[$(printf '%s,%s' "$S1" "$S2" | sed 's/^,//; s/,$//')]"
  fi
  write_inflight "$SUSPECT"
  LAST_SIZE=$SIZE; LAST_CPU=$CPU
done

wait "$PID"; RC=$?
kill -KILL -- -"$PGID" 2>/dev/null   # belt-and-braces: no survivors in the group
rm -f "$INFLIGHT"
exit "$RC"
