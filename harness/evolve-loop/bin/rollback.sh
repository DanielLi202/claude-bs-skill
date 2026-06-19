#!/usr/bin/env bash
# bs-evolve-loop forward-safe rollback.
#
# Rollback always runs under SKILL.lock, reverts an explicitly named bad sha, never
# resets shared main/HEAD, and never deletes pushed release tags.
# Usage: rollback.sh --skill P --bad-sha SHA [--summary text] [--dry]
set -euo pipefail

SKILL=""; BAD=""; SUMMARY="bs-evolve forward rollback"; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --skill) SKILL="$2"; shift 2 ;;
    --bad-sha) BAD="$2"; shift 2 ;;
    --summary) SUMMARY="$2"; shift 2 ;;
    --dry) DRY=1; shift ;;
    --target|--anchor-sha|--bad-tag|--pushed) echo "rollback: legacy reset/tag-delete args are refused" >&2; exit 2 ;;
    *) echo "bad arg $1" >&2; exit 2 ;;
  esac
done
[ -n "$SKILL" ] && [ -n "$BAD" ] || { echo "need --skill --bad-sha" >&2; exit 2; }
HARNESS="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="$SKILL/.bs-evolve/SKILL.lock"
say() { echo "[rollback] $*"; }

cd "$SKILL"
case "$BAD" in
  *[!0-9a-f]*|???????????????????????????????????????|?????????????????????????????????????????)
    say "bad sha must be an explicit 40-character lowercase commit sha"; exit 2 ;;
esac
[ "${#BAD}" -eq 40 ] || { say "bad sha must be an explicit 40-character lowercase commit sha"; exit 2; }
git rev-parse --verify "$BAD^{commit}" >/dev/null || { say "bad sha is not a commit"; exit 2; }

acq="$(python3 "$HARNESS/bin/evolve-lock.py" acquire --lock-file "$LOCK" --owner "rollback:$BAD")" || { say "SKILL.lock held"; exit 11; }
token="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["token"])' "$acq")"
trap 'python3 "$HARNESS/bin/evolve-lock.py" release --lock-file "$LOCK" --token "$token" >/dev/null 2>&1 || true' EXIT

if [ "$DRY" -eq 1 ]; then
  say "DRY: would revert $BAD; no reset, no tag deletion"
  exit 0
fi

git revert --no-edit "$BAD" || { say "revert failed; resolve manually under SKILL.lock discipline"; exit 1; }
git commit --amend -m "rollback: revert bad bs release $BAD" -m "$SUMMARY" >/dev/null
# Do not delete tags. Push only the forward revert.
git push origin HEAD:refs/heads/main || { say "push rollback failed"; exit 3; }
say "rollback pushed as forward revert of $BAD; pushed tags preserved"
