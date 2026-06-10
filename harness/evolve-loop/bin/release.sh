#!/usr/bin/env bash
# bs-evolve-loop release plumbing — Stage 4 (deterministic half), v2.
#
# v2 model: codex implements r2 items as PER-ITEM COMMITS on bs-skill main (fine-
# grained revert), the LAST commit being the version bump + manifest relock. This
# script then GATES and performs tag+push+pin-sync. A dirty tree is also accepted
# (v1 compat): it is committed as one release commit before tagging.
#
# Gates (all must pass before anything is pushed):
#   G1 version strings == --version everywhere they are pinned
#   G2 full unittest suite green (python3 -m unittest discover -s tests)
#   G3 runtime manifest relocked (verify-manifest.sh)
#   G4 backtest evidence: report exists, must_fire: true, and EVERY misfire
#      candidate is adjudicated + fresh-context verified (no 'agree: false').
#      Skippable ONLY with --no-backtest "<reason>" (e.g. release touches no
#      grade_lint rules), and the reason is echoed into the tag message.
#
# Usage: release.sh --skill P --target P --version vX.Y.Z [--summary "text"]
#                   [--backtest-report PATH --adj-verify PATH | --no-backtest "reason"]
#                   [--anchor SHA] [--dry]
# Exit:  0 released | 2 gate failed (nothing pushed; per-item commits left intact —
#        caller decides revert) | 3 tag/push skill failed | 4 target sync/push failed | 5 usage
set -euo pipefail

SKILL=""; TARGET=""; VERSION=""; SUMMARY="bs-evolve-loop auto release"
BTREPORT=""; ADJVERIFY=""; NOBACKTEST=""; ANCHOR=""; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --skill) SKILL="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --summary) SUMMARY="$2"; shift 2 ;;
    --backtest-report) BTREPORT="$2"; shift 2 ;;
    --adj-verify) ADJVERIFY="$2"; shift 2 ;;
    --no-backtest) NOBACKTEST="$2"; shift 2 ;;
    --anchor) ANCHOR="$2"; shift 2 ;;
    --dry) DRY=1; shift ;;
    *) echo "bad arg $1" >&2; exit 5 ;;
  esac
done
[ -n "$SKILL" ] && [ -n "$TARGET" ] && [ -n "$VERSION" ] || { echo "need --skill --target --version" >&2; exit 5; }
HARNESS="$(cd "$(dirname "$0")/.." && pwd)"
NUM="${VERSION#v}"
say() { echo "[release] $*"; }

cd "$SKILL"

# ---- commit model detection ----
DIRTY=0
git diff --quiet && git diff --cached --quiet || DIRTY=1
if [ "$DIRTY" -eq 0 ]; then
  if [ -n "$ANCHOR" ] && [ "$(git rev-parse HEAD)" = "$(git rev-parse "$ANCHOR")" ]; then
    say "tree clean and HEAD == anchor: nothing to release"; exit 2
  fi
  say "per-item commit model (tree clean; will tag HEAD)"
else
  say "dirty-tree model (will create one release commit)"
fi

# ---- G1 version strings ----
say "G1: version strings == $NUM"
grep -q "version: \"$NUM\"" skill.yaml || { say "G1 FAIL: skill.yaml version != $NUM"; exit 2; }
grep -q "$VERSION" contract.md        || { say "G1 FAIL: contract.md missing $VERSION"; exit 2; }

# ---- G2 unittest ----
say "G2: unittest suite"
python3 -m unittest discover -s tests -p 'test_*.py' >/dev/null 2>&1 || { say "G2 FAIL: unittest red"; exit 2; }

# ---- G3 manifest relock ----
say "G3: manifest relock"
bash "$HARNESS/bin/verify-manifest.sh" "$SKILL" >/dev/null || { say "G3 FAIL: manifest not relocked"; exit 2; }

# ---- G4 backtest evidence ----
if [ -n "$NOBACKTEST" ]; then
  say "G4: backtest SKIPPED — reason: $NOBACKTEST"
else
  say "G4: backtest evidence"
  [ -f "$BTREPORT" ] || { say "G4 FAIL: --backtest-report missing (or pass --no-backtest with a reason)"; exit 2; }
  G4=$(python3 - "$BTREPORT" "${ADJVERIFY:-}" <<'PY'
import sys, yaml, pathlib
rep = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text())
if not rep.get("must_fire"):
    print("must_fire false"); sys.exit(1)
mis = rep.get("misfire_candidates") or []
if mis:
    av = sys.argv[2]
    if not av or not pathlib.Path(av).exists():
        print(f"{len(mis)} misfire candidate(s) but no --adj-verify evidence"); sys.exit(1)
    text = pathlib.Path(av).read_text()
    if "agree: false" in text:
        print("fresh-context verifier DISAGREES with an adjudication"); sys.exit(1)
    if "adj_verify" not in text:
        print("adj-verify file lacks the adj_verify verdict block"); sys.exit(1)
print("ok"); sys.exit(0)
PY
) || { say "G4 FAIL: $G4"; exit 2; }
  say "G4 ok: must_fire + adjudications verified"
fi

if [ "$DRY" -eq 1 ]; then say "DRY: all gates pass; would tag/push $VERSION + sync pin"; exit 0; fi

# ---- commit (dirty model only) + tag ----
if [ "$DIRTY" -eq 1 ]; then
  git add -A
  git commit -m "release $VERSION: $SUMMARY" >/dev/null || { say "commit failed"; exit 2; }
fi
git tag -a "$VERSION" -m "$SUMMARY${NOBACKTEST:+ [no-backtest: $NOBACKTEST]}" || { say "tag exists"; exit 3; }

# ---- push skill, then sync + push target pin ----
git push origin main       || { say "push skill main FAILED"; exit 3; }
git push origin "$VERSION" || { say "push tag FAILED"; exit 3; }
cd "$TARGET"
python3 scripts/sync-bs-binding.py --commit || { say "pin sync exit $? (0 ok|2 range|3 verify|4 env)"; exit 4; }
git push origin main || { say "push target main FAILED"; exit 4; }

# ---- health: three-way contract sha ----
inst_sha="$(shasum -a 256 "$SKILL/contract.md" | awk '{print $1}')"
pin_sha="$(tr -d '[:space:]' < "$TARGET/.bootstrap/contract.sha256")"
[ "$inst_sha" = "$pin_sha" ] || { say "post-release sha skew"; exit 4; }
say "released $VERSION; pin synced; health OK"
exit 0
