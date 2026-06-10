#!/usr/bin/env bash
# bs-evolve-loop release plumbing — Stage 4, AUTO mode only (deterministic half).
#
# Assumes codex has ALREADY (workspace-write) applied the r2 fix, bumped
# skill.yaml/contract/clientInfo versions, RELOCKED the manifest table, added a
# unittest, and left `unittest` green. This script GATES, then commits+tags+pushes
# bs-skill and refreshes+pushes the OpenSymphony binding pin. Push happens LAST so a
# pre-push failure is locally reversible.
#
# Usage: release.sh --skill P --target P --version vX.Y.Z [--summary "text"] [--dry]
# Exit:  0 released
#        2 pre-commit gate failed   (no commit — caller discards codex edits)
#        3 committed, not pushed     (caller: rollback.sh local)
#        4 push/sync partial failure (caller: rollback.sh --pushed)
#        5 usage
set -euo pipefail

SKILL=""; TARGET=""; VERSION=""; SUMMARY="bs-evolve-loop auto release"; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --skill) SKILL="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --summary) SUMMARY="$2"; shift 2 ;;
    --dry) DRY=1; shift ;;
    *) echo "bad arg $1" >&2; exit 5 ;;
  esac
done
[ -n "$SKILL" ] && [ -n "$TARGET" ] && [ -n "$VERSION" ] || { echo "need --skill --target --version" >&2; exit 5; }
HARNESS="$(cd "$(dirname "$0")/.." && pwd)"
NUM="${VERSION#v}"
say() { echo "[release] $*"; }

# ---- Phase A: pre-commit gates (no side effects) ----
cd "$SKILL"
if git diff --quiet && git diff --cached --quiet; then say "no changes in skill repo"; exit 2; fi
say "gate: version strings == $NUM"
grep -q "version: \"$NUM\"" skill.yaml      || { say "skill.yaml version != $NUM"; exit 2; }
grep -q "$VERSION" contract.md              || { say "contract.md missing $VERSION title/changelog"; exit 2; }
say "gate: unittest (python3 -m unittest discover -s tests)"
python3 -m unittest discover -s tests -p 'test_*.py' >/dev/null 2>&1 || { say "unittest FAILED"; exit 2; }
say "gate: manifest relock"
bash "$HARNESS/bin/verify-manifest.sh" "$SKILL" >/dev/null || { say "manifest NOT relocked"; exit 2; }

if [ "$DRY" -eq 1 ]; then say "DRY: gates pass; would commit/tag/push $VERSION then sync OpenSymphony pin"; exit 0; fi

# ---- Phase B: commit + tag (local, reversible) ----
git add -A
git commit -m "release $VERSION: $SUMMARY" >/dev/null || { say "commit failed"; exit 2; }
git tag "$VERSION" || { say "tag $VERSION already exists"; exit 3; }

# ---- Phase C: push skill, then sync + push target pin ----
git push origin main      || { say "push skill main FAILED (committed, not pushed)"; exit 3; }
git push origin "$VERSION" || { say "push tag FAILED"; exit 4; }
cd "$TARGET"
if python3 scripts/sync-bs-binding.py --commit; then
  :
else
  say "sync-bs-binding.py exit $? (0=ok 2=out-of-range 3=verify-fail 4=env)"; exit 4
fi
git push origin main || { say "push target main FAILED"; exit 4; }

# ---- Phase D: health (three-way contract sha must agree) ----
inst_sha="$(shasum -a 256 "$SKILL/contract.md" | awk '{print $1}')"
pin_sha="$(tr -d '[:space:]' < "$TARGET/.bootstrap/contract.sha256")"
[ "$inst_sha" = "$pin_sha" ] || { say "post-release sha skew inst=$inst_sha pin=$pin_sha"; exit 4; }
say "released $VERSION; OpenSymphony pin synced; health OK"
exit 0
