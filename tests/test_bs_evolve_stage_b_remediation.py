from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "harness" / "evolve-loop" / "bin" / "release.sh"


def run(cmd, cwd=None, check=False, env=None):
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True, env=env)


def init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    run(["git", "init"], cwd=repo, check=True)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)


def write_minimal_skill(repo: Path, version: str) -> None:
    (repo / "runtime").mkdir(parents=True, exist_ok=True)
    (repo / "tests" / "grade_lint_fixtures" / "anon-clean").mkdir(parents=True, exist_ok=True)
    (repo / "tests" / "test_smoke.py").write_text("import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n", encoding="utf-8")
    (repo / "runtime" / "grade_lint.py").write_text(
        "import argparse, pathlib\n"
        "p=argparse.ArgumentParser(); p.add_argument('--task-type'); p.add_argument('--risk-level'); p.add_argument('--grade-file'); p.add_argument('--outcome-file'); p.add_argument('--evidence-file'); a=p.parse_args(); pathlib.Path(a.evidence_file).write_text('{\\\"grade_lint\\\": {\\\"errors\\\": []}}')\n",
        encoding="utf-8",
    )
    (repo / "tests" / "grade_lint_fixtures" / "anon-clean" / "metadata.yaml").write_text("task_type: code\nrisk_level: low\nexpect: must_not_fire\n", encoding="utf-8")
    (repo / "tests" / "grade_lint_fixtures" / "anon-clean" / "grade.md").write_text("clean\n", encoding="utf-8")
    digest = hashlib.sha256((repo / "runtime" / "grade_lint.py").read_bytes()).hexdigest()
    (repo / "contract.md").write_text(f"# Contract {version}\n\nmentions {version}\n\n## Runtime manifest (locked)\n\n| file | sha256 |\n|---|---|\n| runtime/grade_lint.py | {digest} |\n", encoding="utf-8")
    (repo / "skill.yaml").write_text(f'name: bs\nversion: "{version.removeprefix("v")}"\ncontract_version: "{version.removeprefix("v")}"\n', encoding="utf-8")


def make_release_fixture(base: Path) -> tuple[Path, Path, str]:
    bare = base / "origin.git"
    run(["git", "init", "--bare", str(bare)], check=True)
    skill = base / "skill"
    init_repo(skill)
    write_minimal_skill(skill, "v1.0.0")
    run(["git", "add", "."], cwd=skill, check=True)
    run(["git", "commit", "-m", "v1.0.0"], cwd=skill, check=True)
    run(["git", "tag", "v1.0.0"], cwd=skill, check=True)
    run(["git", "remote", "add", "origin", str(bare)], cwd=skill, check=True)
    run(["git", "push", "origin", "HEAD:refs/heads/main", "v1.0.0"], cwd=skill, check=True)
    anchor = run(["git", "rev-parse", "HEAD"], cwd=skill, check=True).stdout.strip()
    write_minimal_skill(skill, "v1.0.1")
    run(["git", "add", "."], cwd=skill, check=True)
    run(["git", "commit", "-m", "v1.0.1"], cwd=skill, check=True)
    return skill, bare, anchor



def make_harness_copy(base: Path, *, release_mutator=None, gates_mutator=None) -> Path:
    root = base / "harness" / "evolve-loop" / "bin"
    root.mkdir(parents=True)
    for name in ["release.sh", "verify-manifest.sh", "grade-fixture-walker.py", "release-gates.py"]:
        src = ROOT / "harness" / "evolve-loop" / "bin" / name
        text = src.read_text(encoding="utf-8")
        if name == "release.sh" and release_mutator:
            text = release_mutator(text)
        if name == "release-gates.py" and gates_mutator:
            text = gates_mutator(text)
        dst = root / name
        dst.write_text(text, encoding="utf-8")
        dst.chmod(0o755)
    return root / "release.sh"


def update_runtime_manifest(skill: Path) -> None:
    digest = hashlib.sha256((skill / "runtime" / "grade_lint.py").read_bytes()).hexdigest()
    contract = skill / "contract.md"
    text = contract.read_text(encoding="utf-8")
    text = re.sub(r"\| runtime/grade_lint\.py \| [0-9a-f]{64} \|", f"| runtime/grade_lint.py | {digest} |", text)
    contract.write_text(text, encoding="utf-8")


def add_rule_change(skill: Path) -> None:
    lint = skill / "runtime" / "grade_lint.py"
    lint.write_text(
        lint.read_text(encoding="utf-8") + "\n# rule change touches grade_lint surface\n",
        encoding="utf-8",
    )
    update_runtime_manifest(skill)
    run(["git", "add", "runtime/grade_lint.py", "contract.md"], cwd=skill, check=True)
    run(["git", "commit", "-m", "rule change"], cwd=skill, check=True)


def add_near_miss_fixture(skill: Path) -> None:
    fx = skill / "tests" / "grade_lint_fixtures" / "near-miss"
    fx.mkdir(parents=True)
    (fx / "metadata.yaml").write_text("task_type: code\nrisk_level: low\nexpect: must_not_fire\n", encoding="utf-8")
    (fx / "grade.md").write_text("anonymous clean near miss\n", encoding="utf-8")
    run(["git", "add", "tests/grade_lint_fixtures/near-miss"], cwd=skill, check=True)
    run(["git", "commit", "-m", "near miss fixture"], cwd=skill, check=True)


def write_backtest_report(path: Path, *, misfire: bool = False) -> None:
    mis = "\nmisfire_candidates:\n  - id: c1\n" if misfire else "\nmisfire_candidates: []\n"
    path.write_text("must_fire: true" + mis, encoding="utf-8")


def make_mutated_harness(base: Path) -> Path:
    root = base / "mut_harness" / "evolve-loop" / "bin"
    root.mkdir(parents=True)
    for name in ["release.sh", "verify-manifest.sh", "grade-fixture-walker.py", "release-gates.py"]:
        src = ROOT / "harness" / "evolve-loop" / "bin" / name
        text = src.read_text(encoding="utf-8")
        if name == "release.sh":
            text = text.replace('$(peel_commit "$VERSION")', '$(git rev-parse "$VERSION")')
        dst = root / name
        dst.write_text(text, encoding="utf-8")
        dst.chmod(0o755)
    return root / "release.sh"


class StageBRemediationF1(unittest.TestCase):
    def test_release_annotated_tag_peels_commit_and_mutation_fails(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            skill, bare, anchor = make_release_fixture(base / "good")
            proc = run(["bash", str(RELEASE), "--skill", str(skill), "--version", "v1.0.1", "--anchor", anchor, "--no-backtest", "contract prose only"])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            origin_main = run(["git", f"--git-dir={bare}", "rev-parse", "refs/heads/main"], check=True).stdout.strip()
            tag_commit = run(["git", "rev-parse", "v1.0.1^{commit}"], cwd=skill, check=True).stdout.strip()
            local_head = run(["git", "rev-parse", "HEAD"], cwd=skill, check=True).stdout.strip()
            self.assertEqual(origin_main, tag_commit)
            self.assertEqual(local_head, tag_commit)

            bad_release = make_mutated_harness(base / "mut")
            bad_skill, _bad_bare, bad_anchor = make_release_fixture(base / "bad")
            bad = run(["bash", str(bad_release), "--skill", str(bad_skill), "--version", "v1.0.1", "--anchor", bad_anchor, "--no-backtest", "contract prose only"])
            self.assertNotEqual(bad.returncode, 0, bad.stdout + bad.stderr)
            self.assertIn("local canonical != tag", bad.stdout + bad.stderr)


class StageBRemediationF3F5(unittest.TestCase):
    def test_no_anchor_rules_release_requires_near_miss_fixture_and_mutation_bypasses(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            skill, _bare, _anchor = make_release_fixture(base / "missing")
            add_rule_change(skill)
            report = base / "backtest.yaml"
            write_backtest_report(report)

            missing = run(["bash", str(RELEASE), "--skill", str(skill), "--version", "v1.0.1", "--backtest-report", str(report), "--dry"])
            self.assertNotEqual(missing.returncode, 0, missing.stdout + missing.stderr)
            self.assertIn("G4 FAIL: near-miss fixture missing", missing.stdout + missing.stderr)

            add_near_miss_fixture(skill)
            with_fixture = run(["bash", str(RELEASE), "--skill", str(skill), "--version", "v1.0.1", "--backtest-report", str(report), "--dry"])
            self.assertEqual(with_fixture.returncode, 0, with_fixture.stdout + with_fixture.stderr)
            self.assertIn("DRY: all gates pass", with_fixture.stdout + with_fixture.stderr)

            def skip_no_anchor_near_miss(text: str) -> str:
                old = '  nm_args=(near-miss --skill "$SKILL")\n  [ -n "$ANCHOR" ] && nm_args+=(--anchor "$ANCHOR")\n  python3 "$HARNESS/bin/release-gates.py" "${nm_args[@]}" >/dev/null || { say "G4 FAIL: near-miss fixture missing"; exit 2; }\n'
                new = '  if [ -n "$ANCHOR" ]; then\n    python3 "$HARNESS/bin/release-gates.py" near-miss --skill "$SKILL" --anchor "$ANCHOR" >/dev/null || { say "G4 FAIL: near-miss fixture missing"; exit 2; }\n  fi\n'
                self.assertIn(old, text)
                return text.replace(old, new)

            mutant_release = make_harness_copy(base / "mutant", release_mutator=skip_no_anchor_near_miss)
            mutant_skill, _mut_bare, _mut_anchor = make_release_fixture(base / "mutant-skill")
            add_rule_change(mutant_skill)
            mutant_report = base / "mutant-backtest.yaml"
            write_backtest_report(mutant_report)
            mutant = run(["bash", str(mutant_release), "--skill", str(mutant_skill), "--version", "v1.0.1", "--backtest-report", str(mutant_report), "--dry"])
            self.assertEqual(mutant.returncode, 0, mutant.stdout + mutant.stderr)



class StageBRemediationF5(unittest.TestCase):
    def test_g1_uses_top_level_skill_version_behavior_and_mutation_bypasses(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            skill, _bare, anchor = make_release_fixture(base / "g1")
            (skill / "skill.yaml").write_text('name: bs\nversion: "1.0.0"\ncontract_version: "1.0.1"\n', encoding="utf-8")
            run(["git", "add", "skill.yaml"], cwd=skill, check=True)
            run(["git", "commit", "-m", "contract-version-only mismatch"], cwd=skill, check=True)
            proc = run(["bash", str(RELEASE), "--skill", str(skill), "--version", "v1.0.1", "--anchor", anchor, "--no-backtest", "contract prose only", "--dry"])
            self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("skill.yaml top-level version mismatch", proc.stdout + proc.stderr)

            def disable_g1_version_check(text: str) -> str:
                old = "if str(skill.get('version')) != num:\n    print('skill.yaml top-level version mismatch')\n    sys.exit(1)"
                self.assertIn(old, text)
                return text.replace(old, "if False and str(skill.get('version')) != num:\n    print('skill.yaml top-level version mismatch')\n    sys.exit(1)")

            mutant_release = make_harness_copy(base / "g1-mutant", release_mutator=disable_g1_version_check)
            mutant = run(["bash", str(mutant_release), "--skill", str(skill), "--version", "v1.0.1", "--anchor", anchor, "--no-backtest", "contract prose only", "--dry"])
            self.assertEqual(mutant.returncode, 0, mutant.stdout + mutant.stderr)

    def test_g4_misfires_without_adjudication_file_are_rejected_by_release(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            skill, _bare, anchor = make_release_fixture(base / "g4")
            report = base / "misfire-report.yaml"
            write_backtest_report(report, misfire=True)
            proc = run(["bash", str(RELEASE), "--skill", str(skill), "--version", "v1.0.1", "--anchor", anchor, "--backtest-report", str(report), "--dry"])
            self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("G4 FAIL: structured adjudication gate failed", proc.stdout + proc.stderr)


class StageBRemediationF2(unittest.TestCase):
    REAL_CORPUS_TESTS = [
        "tests.test_grade_lint.GradeLintTests.test_cycle028_real_corpus_fires_containment_unavailable_and_trusted_binary_facets",
        "tests.test_grade_lint.GradeLintTests.test_cycle026_real_corpus_does_not_fire_containment_unavailable_or_trusted_binary_facets",
        "tests.test_grade_lint.GradeLintTests.test_cycle020_real_corpus_grade_rounds_do_not_fire_containment_unavailable_or_trusted_binary_facets",
        "tests.test_grade_lint.GradeLintTests.test_cycle029_real_corpus_fires_scanned_pid_kill_selector_facet",
        "tests.test_grade_lint.GradeLintTests.test_cycle028_real_corpus_does_not_fire_scanned_pid_kill_selector_facet",
    ]

    def test_missing_opensymphony_real_corpus_skips_instead_of_failing_or_fake_passing(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing-dogfood-root"
            env = os.environ.copy()
            env["BS_EVOLVE_REAL_CORPUS_ROOT"] = str(missing)
            proc = run([sys.executable, "-m", "unittest", *self.REAL_CORPUS_TESTS], cwd=ROOT, env=env)
            output = proc.stdout + proc.stderr
            self.assertEqual(proc.returncode, 0, output)
            self.assertIn("OK (skipped=6)", output)
            self.assertNotIn("FAILED", output)


if __name__ == "__main__":
    unittest.main()
