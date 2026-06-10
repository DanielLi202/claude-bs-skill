#!/usr/bin/env bash
# bs-evolve-loop rollback to the pre-release anchor (Stage 4 safety net).
#
# Two modes:
#   (default)  local rollback — release.sh failed BEFORE/at push: hard-reset skill to
#              the anchor sha, delete the bad local tag, restore target binding files.
#   --pushed   forward-safe rollback — the bad release reached origin: `git revert` the
#              release commit (NO history rewrite), drop the tag, re-sync + push target.
#
# Usage: rollback.sh --skill P --target P --anchor-sha SHA [--bad-tag vX.Y.Z] [--pushed]
# Exit:  0 ok | 1 needs manual intervention | 2 usage
set -euo pipefail

SKILL=""; TARGET=""; ANCHOR=""; BADTAG=""; PUSHED=0
while [ $# -gt 0 ]; do
  case "$1" in
    --skill) SKILL="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --anchor-sha) ANCHOR="$2"; shift 2 ;;
    --bad-tag) BADTAG="$2"; shift 2 ;;
    --pushed) PUSHED=1; shift ;;
    *) echo "bad arg $1" >&2; exit 2 ;;
  esac
done
[ -n "$SKILL" ] && [ -n "$TARGET" ] && [ -n "$ANCHOR" ] || { echo "need --skill --target --anchor-sha" >&2; exit 2; }
say() { echo "[rollback] $*"; }

cd "$SKILL"
if [ "$PUSHED" -eq 1 ]; then
  say "pushed rollback: revert release commit (no history rewrite)"
  git revert --no-edit HEAD || { say "revert failed — MANUAL intervention required"; exit 1; }
  [ -n "$BADTAG" ] && { git tag -d "$BADTAG" 2>/dev/null || true; }
  git push origin main || say "WARN: push revert failed — push manually"
  [ -n "$BADTAG" ] && { git push origin ":refs/tags/$BADTAG" 2>/dev/null || true; }
else
  say "local rollback: reset skill to anchor $ANCHOR"
  git reset --hard "$ANCHOR"
  [ -n "$BADTAG" ] && { git tag -d "$BADTAG" 2>/dev/null || true; }
fi

cd "$TARGET"
if [ "$PUSHED" -eq 1 ]; then
  python3 scripts/sync-bs-binding.py --commit || say "WARN: re-sync after revert non-zero"
  git push origin main || say "WARN: push target failed — push manually"
else
  git checkout -- .bootstrap.yaml .bootstrap/contract.sha256 docs/ops/bootstrap-workflow.md 2>/dev/null || true
fi
say "rollback done (pushed=$PUSHED). Verify: cd $TARGET && /bs doctor"
exit 0
