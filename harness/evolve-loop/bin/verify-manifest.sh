#!/usr/bin/env bash
# Verify the contract.md "Runtime manifest (locked)" sha table == actual file hashes, including runtime/lib/command surfaces and evolve-loop bin helpers.
# A correct relock is a release gate: a botched bump => binding validation / `/bs doctor`
# would fail later, so we catch it here before push.
#
# Usage: verify-manifest.sh [SKILL_REPO]   (defaults to $BS_LOOP_SKILL_REPO)
# Exit:  0 all match | 1 mismatch (offenders printed) | 2 error
set -euo pipefail

SKILL="${1:-${BS_LOOP_SKILL_REPO:-}}"
[ -n "$SKILL" ] || { echo "SKILL_REPO required (arg1 or \$BS_LOOP_SKILL_REPO)" >&2; exit 2; }
cd "$SKILL"
[ -f contract.md ] || { echo "no contract.md in $SKILL" >&2; exit 2; }

fail=0; n=0
while IFS= read -r line; do
  path="$(printf '%s' "$line" | awk -F'|' '{gsub(/^[ \t]+|[ \t]+$/,"",$2); print $2}')"
  want="$(printf '%s' "$line" | awk -F'|' '{gsub(/^[ \t]+|[ \t]+$/,"",$3); print $3}')"
  case "$path" in runtime/*|lib/*|commands/*|harness/evolve-loop/bin/*) ;; *) continue ;; esac
  if [ ! -f "$path" ]; then echo "MISSING $path"; fail=1; continue; fi
  got="$(shasum -a 256 "$path" | awk '{print $1}')"
  n=$((n + 1))
  [ "$got" = "$want" ] || { echo "MISMATCH $path want=$want got=$got"; fail=1; }
done < <(grep -E '^\| (runtime/|lib/|commands/|harness/evolve-loop/bin/)' contract.md)

[ "$n" -gt 0 ] || { echo "no manifest rows parsed in contract.md" >&2; exit 2; }
if [ "$fail" -eq 0 ]; then echo "manifest OK ($n files)"; exit 0; fi
exit 1
