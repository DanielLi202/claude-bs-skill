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

if out=$(git --version 2>&1); then add_check git pass true "$out"; else add_check git fail true "$out"; fi
if codex_path=$(command -v codex 2>/dev/null); then add_check codex_binary pass true "$codex_path"; else add_check codex_binary fail true "codex not found"; fi
if out=$(codex --version 2>&1); then
  if version_ge "$out" "$MIN_CODEX_VERSION"; then add_check codex_version pass true "$out"; else add_check codex_version fail true "$out < $MIN_CODEX_VERSION"; fi
else add_check codex_version fail true "$out"; fi
if out=$(codex login status 2>&1); then add_check codex_auth pass true "$out"; else add_check codex_auth fail true "$out"; fi
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

printf 'overall: %s\n' "$OVERALL"
printf 'checked_at: "%s"\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'checks:\n'
cat "$CHECKS_FILE"
rm -f "$CHECKS_FILE"
[[ "$OVERALL" == "pass" ]]
