#!/usr/bin/env bash
# bs-evolve-loop release plumbing — Stage 4 skill-only transaction.
#
# Model A: while holding SKILL.lock, Stage 4 computes release-plan (fresh max
# release tag + candidate) before backtest, implements in a private worktree,
# gates, then atomically pushes candidate HEAD to origin/main and pushes the tag.
# Target pin-sync is deliberately NOT done here; each target heals itself at Step 0.
#
# Usage: release.sh --skill P --version vX.Y.Z [--summary "text"]
#                   [--plan-file PATH]
#                   [--backtest-report PATH --adj-verify PATH | --no-backtest "reason"]
#                   [--anchor SHA] [--dry]
# Back-compat: --target is accepted but ignored.
# Exit: 0 released/dry-ok | 2 gate failed | 3 tag/push failed | 5 usage
set -euo pipefail

SKILL=""; TARGET=""; VERSION=""; SUMMARY="bs-evolve-loop auto release"
BTREPORT=""; ADJVERIFY=""; NOBACKTEST=""; ANCHOR=""; PLAN=""; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --skill) SKILL="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;; # accepted for old callers; never used
    --version) VERSION="$2"; shift 2 ;;
    --summary) SUMMARY="$2"; shift 2 ;;
    --plan-file) PLAN="$2"; shift 2 ;;
    --backtest-report) BTREPORT="$2"; shift 2 ;;
    --adj-verify) ADJVERIFY="$2"; shift 2 ;;
    --no-backtest) NOBACKTEST="$2"; shift 2 ;;
    --anchor) ANCHOR="$2"; shift 2 ;;
    --dry) DRY=1; shift ;;
    *) echo "bad arg $1" >&2; exit 5 ;;
  esac
done
[ -n "$SKILL" ] && [ -n "$VERSION" ] || { echo "need --skill --version" >&2; exit 5; }
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

# ---- optional B2 release plan consistency ----
if [ -n "$PLAN" ]; then
  say "B2: release plan consistency"
  [ -f "$PLAN" ] || { say "B2 FAIL: --plan-file missing"; exit 2; }
  python3 - "$PLAN" "$VERSION" <<'PY'
import pathlib, sys, yaml
plan = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text()) or {}
if plan.get("candidate_version") != sys.argv[2]:
    print(f"candidate mismatch: plan={plan.get('candidate_version')} arg={sys.argv[2]}")
    sys.exit(1)
if not plan.get("baseline_ref") or not plan.get("baseline_sha"):
    print("plan missing baseline_ref/baseline_sha")
    sys.exit(1)
PY
fi

# ---- G1 version strings (anchored; do not accept contract_version alone) ----
say "G1: version strings == $NUM"
python3 - "$NUM" <<'PY'
import pathlib, re, sys, yaml
num = sys.argv[1]
skill = yaml.safe_load(pathlib.Path('skill.yaml').read_text()) or {}
if str(skill.get('version')) != num:
    print('skill.yaml top-level version mismatch')
    sys.exit(1)
text = pathlib.Path('contract.md').read_text()
if f"v{num}" not in text:
    print('contract.md missing release version')
    sys.exit(1)
PY

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
  G4=$(python3 - "$BTREPORT" "${ADJVERIFY:-}" "${PLAN:-}" <<'PY'
import sys, yaml, pathlib
rep = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text()) or {}
if not rep.get("must_fire"):
    print("must_fire false"); sys.exit(1)
plan_file = sys.argv[3]
if plan_file:
    plan = yaml.safe_load(pathlib.Path(plan_file).read_text()) or {}
    if rep.get("baseline_ref") != plan.get("baseline_ref"):
        print(f"baseline_ref mismatch: report={rep.get('baseline_ref')} plan={plan.get('baseline_ref')}"); sys.exit(1)
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

if [ "$DRY" -eq 1 ]; then say "DRY: all gates pass; would tag/push $VERSION on skill only"; exit 0; fi

# ---- commit (dirty model only) + tag ----
if [ "$DIRTY" -eq 1 ]; then
  git add -A
  git commit -m "release $VERSION: $SUMMARY" >/dev/null || { say "commit failed"; exit 2; }
fi
git tag -a "$VERSION" -m "$SUMMARY${NOBACKTEST:+ [no-backtest: $NOBACKTEST]}" || { say "tag exists"; exit 3; }

# ---- atomic skill push; no target reach-in ----
git push origin "HEAD:refs/heads/main" || { say "push skill main FAILED"; exit 3; }
git push origin "$VERSION" || { say "push tag FAILED"; exit 3; }
git fetch origin main --tags >/dev/null 2>&1 || true
git merge --ff-only "$VERSION" >/dev/null || { say "local canonical not fast-forwardable to $VERSION"; exit 3; }
[ "$(git rev-parse HEAD)" = "$(git rev-parse "$VERSION")" ] || { say "local canonical != tag"; exit 3; }
say "released $VERSION on skill; target pin-sync deferred to target Step 0"
exit 0
