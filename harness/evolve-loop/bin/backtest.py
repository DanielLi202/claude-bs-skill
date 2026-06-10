#!/usr/bin/env python3
"""bs-evolve-loop backtest — replay the NEW grade_lint against the historical
cycle corpus and attribute only DELTA failures to the new rules.

Methodology (the anti-over-fire gate for heuristic validators):
  For every code cycle in the corpus, run BOTH the baseline grade_lint (taken
  from a git ref, e.g. the last release tag) and the working-tree grade_lint on
  the cycle's FINAL grade round. delta = new_errors - baseline_errors.
    * --target-cycle (the cycle whose escapes motivated the new rules) MUST show
      a non-empty delta  -> must-fire proof (else exit 1: rules don't catch the
      known escape class).
    * delta on any OTHER cycle = potential misfire -> listed for in-loop
      adjudication (true_positive_historical | false_positive), evidence kept,
      then independently verified by a FRESH codex context before release.

Usage:
  backtest.py --skill-repo P --corpus-root P --baseline-ref v1.4.11 \
              --target-cycle cycle-018 --out <evidence-dir>
Exit: 0 report written + must-fire satisfied (misfires, if any, listed in report)
      1 must-fire NOT satisfied | 2 usage/env error
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile

import yaml

TYPE_RE = re.compile(r"^\s*(?:task_)?type:\s*\"?(\w+)", re.M)
RISK_RE = re.compile(r"^\s*(?:task_)?risk_level:\s*\"?(\w+)", re.M)


def run_lint(lint_path, task_type, risk, grade_file, outcome_file, evidence_file):
    p = subprocess.run(
        [sys.executable, str(lint_path), "--task-type", task_type, "--risk-level", risk,
         "--grade-file", str(grade_file), "--outcome-file", str(outcome_file),
         "--evidence-file", str(evidence_file)],
        capture_output=True, text=True)
    errors = []
    try:
        ev = json.loads(pathlib.Path(evidence_file).read_text())
        # evidence shape is {"grade_lint": {..., "errors": [...]}} (nested), with a
        # top-level fallback for older/other layouts
        errors = (ev.get("grade_lint") or ev).get("errors") or []
    except Exception:
        if p.returncode != 0:
            errors = [f"lint_crashed: {p.stderr.strip()[:300] or p.stdout.strip()[:300]}"]
    return p.returncode, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-repo", required=True)
    ap.add_argument("--corpus-root", required=True)
    ap.add_argument("--baseline-ref", required=True)
    ap.add_argument("--target-cycle", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    skill = pathlib.Path(a.skill_repo)
    corpus = pathlib.Path(a.corpus_root)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    show = subprocess.run(["git", "-C", str(skill), "show", f"{a.baseline_ref}:runtime/grade_lint.py"],
                          capture_output=True, text=True)
    if show.returncode != 0:
        print(f"cannot read baseline grade_lint at {a.baseline_ref}: {show.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    baseline_lint = pathlib.Path(tempfile.mkstemp(suffix="_baseline_grade_lint.py")[1])
    baseline_lint.write_text(show.stdout)
    new_lint = skill / "runtime" / "grade_lint.py"

    report = {"baseline_ref": a.baseline_ref, "target_cycle": a.target_cycle,
              "cycles": [], "must_fire": False, "misfire_candidates": []}

    for cdir in sorted(corpus.glob("cycle-*/")):
        cy = cdir / "cycle.yaml"
        outcome = cdir / "outcome.md"
        def round_no(p):
            m = re.search(r"(\d+)", p.stem)
            return int(m.group(1)) if m else -1
        grades = sorted(cdir.glob("grade_round_*.md"), key=round_no)
        if not (cy.exists() and outcome.exists() and grades):
            continue
        meta = cy.read_text()
        tm, rm = TYPE_RE.search(meta), RISK_RE.search(meta)
        if not tm or tm.group(1) != "code":
            continue  # grade_lint code rules apply to code cycles only
        risk = rm.group(1) if rm else "medium"
        final = grades[-1]
        name = cdir.name

        _, base_errors = run_lint(baseline_lint, "code", risk, final, outcome,
                                  out / f"{name}_baseline.json")
        _, new_errors = run_lint(new_lint, "code", risk, final, outcome,
                                 out / f"{name}_new.json")
        delta = [e for e in new_errors if e not in base_errors]
        row = {"cycle": name, "risk": risk, "grade": final.name,
               "baseline_error_count": len(base_errors), "new_error_count": len(new_errors),
               "delta_errors": delta}
        report["cycles"].append(row)
        if name == a.target_cycle and delta:
            report["must_fire"] = True
        if name != a.target_cycle and delta:
            report["misfire_candidates"].append(row)

    (out / "backtest_report.yaml").write_text(
        yaml.safe_dump(report, sort_keys=False, allow_unicode=True))
    baseline_lint.unlink(missing_ok=True)

    tested = [c["cycle"] for c in report["cycles"]]
    print(f"backtest: {len(tested)} code cycles tested {tested}")
    print(f"must_fire({a.target_cycle}): {report['must_fire']}")
    print(f"misfire_candidates: {len(report['misfire_candidates'])}")
    if not report["must_fire"]:
        print("FAIL: new rules do not fire on the target cycle's final grade — "
              "they would not have caught the known escape", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
