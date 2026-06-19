from __future__ import annotations

import hashlib
import os
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
