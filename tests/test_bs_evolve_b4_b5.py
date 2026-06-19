from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WALKER = ROOT / "harness" / "evolve-loop" / "bin" / "grade-fixture-walker.py"
GATES = ROOT / "harness" / "evolve-loop" / "bin" / "release-gates.py"
RELEASE = ROOT / "harness" / "evolve-loop" / "bin" / "release.sh"
COMMAND = ROOT / "commands" / "bs-evolve.md"


def run(cmd, cwd=None, check=False):
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def write_yaml(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    run(["git", "init"], cwd=repo, check=True)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)


class BsEvolveB4B5Tests(unittest.TestCase):
    def test_fixture_walker_passes_current_committed_anonymous_fixtures(self):
        proc = run([sys.executable, str(WALKER), "--skill", str(ROOT)])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("fixture walker OK", proc.stdout)

    def test_fixture_walker_fail_closed_on_empty_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "empty"
            root.mkdir()
            proc = run([sys.executable, str(WALKER), "--skill", str(ROOT), "--fixtures-root", str(root)])
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("fixture root is empty", proc.stderr)

    def test_g4_blocks_false_positive_missing_adjudication_missing_fresh_verify_and_allows_clean(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            report = base / "report.yaml"
            write_yaml(report, {"must_fire": True, "baseline_ref": "v1.0.0", "misfire_candidates": [{"id": "m1"}, {"id": "m2"}]})
            adj = base / "adj.yaml"
            write_yaml(adj, {"adjudications": [{"id": "m1", "verdict": "false_positive", "fresh_verify": {"status": "pass"}}]})
            proc = run([sys.executable, str(GATES), "g4", "--report", str(report), "--adj-verify", str(adj)])
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("false_positive", proc.stdout)
            self.assertIn("missing adjudication for m2", proc.stdout)

            write_yaml(adj, {"adjudications": [
                {"id": "m1", "verdict": "true_positive", "fresh_verify": {"status": "pass"}},
                {"id": "m2", "verdict": "true_positive"},
            ]})
            proc = run([sys.executable, str(GATES), "g4", "--report", str(report), "--adj-verify", str(adj)])
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("missing fresh-verify pass for m2", proc.stdout)

            write_yaml(adj, {"adjudications": [
                {"id": "m1", "verdict": "true_positive", "fresh_verify": {"status": "pass"}},
                {"id": "m2", "verdict": "true_positive", "fresh_verify": {"status": "pass"}},
            ]})
            proc = run([sys.executable, str(GATES), "g4", "--report", str(report), "--adj-verify", str(adj)])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_no_backtest_allows_contract_only_but_rejects_rule_surface(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "skill"
            init_repo(repo)
            (repo / "contract.md").write_text("v1\n", encoding="utf-8")
            (repo / "runtime").mkdir()
            (repo / "runtime" / "grade_lint.py").write_text("print('old')\n", encoding="utf-8")
            run(["git", "add", "."], cwd=repo, check=True)
            run(["git", "commit", "-m", "base"], cwd=repo, check=True)
            anchor = run(["git", "rev-parse", "HEAD"], cwd=repo, check=True).stdout.strip()
            (repo / "contract.md").write_text("v2\n", encoding="utf-8")
            run(["git", "commit", "-am", "contract"], cwd=repo, check=True)
            ok = run([sys.executable, str(GATES), "no-backtest", "--skill", str(repo), "--anchor", anchor, "--reason", "contract prose only"])
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            (repo / "runtime" / "grade_lint.py").write_text("print('new')\n", encoding="utf-8")
            run(["git", "commit", "-am", "rule"], cwd=repo, check=True)
            bad = run([sys.executable, str(GATES), "no-backtest", "--skill", str(repo), "--anchor", anchor, "--reason", "skip"])
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("rejected", bad.stdout)

    def test_no_backtest_and_near_miss_reject_dirty_staged_and_untracked_rule_surfaces(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "skill"
            init_repo(repo)
            (repo / "runtime").mkdir()
            (repo / "tests" / "grade_lint_fixtures").mkdir(parents=True)
            (repo / "runtime" / "grade_lint.py").write_text("old\n", encoding="utf-8")
            run(["git", "add", "."], cwd=repo, check=True)
            run(["git", "commit", "-m", "base"], cwd=repo, check=True)
            anchor = run(["git", "rev-parse", "HEAD"], cwd=repo, check=True).stdout.strip()

            (repo / "runtime" / "grade_lint.py").write_text("dirty\n", encoding="utf-8")
            dirty_nb = run([sys.executable, str(GATES), "no-backtest", "--skill", str(repo), "--anchor", anchor, "--reason", "skip"])
            dirty_nm = run([sys.executable, str(GATES), "near-miss", "--skill", str(repo), "--anchor", anchor])
            self.assertNotEqual(dirty_nb.returncode, 0)
            self.assertNotEqual(dirty_nm.returncode, 0)

            run(["git", "add", "runtime/grade_lint.py"], cwd=repo, check=True)
            staged_nb = run([sys.executable, str(GATES), "no-backtest", "--skill", str(repo), "--anchor", anchor, "--reason", "skip"])
            staged_nm = run([sys.executable, str(GATES), "near-miss", "--skill", str(repo), "--anchor", anchor])
            self.assertNotEqual(staged_nb.returncode, 0)
            self.assertNotEqual(staged_nm.returncode, 0)

            # Restore the rule, then prove untracked fixture metadata is visible to the surface classifier.
            run(["git", "restore", "--staged", "runtime/grade_lint.py"], cwd=repo, check=True)
            run(["git", "restore", "runtime/grade_lint.py"], cwd=repo, check=True)
            untracked = repo / "tests" / "grade_lint_fixtures" / "anon-new" / "metadata.yaml"
            untracked.parent.mkdir(parents=True)
            untracked.write_text("expect: must_not_fire\n", encoding="utf-8")
            untracked_nb = run([sys.executable, str(GATES), "no-backtest", "--skill", str(repo), "--anchor", anchor, "--reason", "skip"])
            self.assertNotEqual(untracked_nb.returncode, 0)

    def test_near_miss_required_for_grade_lint_rule_change(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "skill"
            init_repo(repo)
            (repo / "runtime").mkdir()
            (repo / "tests" / "grade_lint_fixtures" / "anon-x").mkdir(parents=True)
            (repo / "runtime" / "grade_lint.py").write_text("old\n", encoding="utf-8")
            run(["git", "add", "."], cwd=repo, check=True)
            run(["git", "commit", "-m", "base"], cwd=repo, check=True)
            anchor = run(["git", "rev-parse", "HEAD"], cwd=repo, check=True).stdout.strip()
            (repo / "runtime" / "grade_lint.py").write_text("new\n", encoding="utf-8")
            run(["git", "commit", "-am", "rule"], cwd=repo, check=True)
            bad = run([sys.executable, str(GATES), "near-miss", "--skill", str(repo), "--anchor", anchor])
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("near-miss fixture missing", bad.stdout)
            meta = repo / "tests" / "grade_lint_fixtures" / "anon-x" / "metadata.yaml"
            meta.write_text("expect: must_not_fire\n", encoding="utf-8")
            run(["git", "add", str(meta.relative_to(repo))], cwd=repo, check=True)
            run(["git", "commit", "-m", "fixture"], cwd=repo, check=True)
            ok = run([sys.executable, str(GATES), "near-miss", "--skill", str(repo), "--anchor", anchor])
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)

    def test_release_script_and_command_wire_b4_b5_gates(self):
        release = RELEASE.read_text(encoding="utf-8")
        self.assertIn("grade-fixture-walker.py", release)
        self.assertIn("release-gates.py", release)
        self.assertIn("no-backtest", release)
        self.assertIn("near-miss", release)
        command = COMMAND.read_text(encoding="utf-8")
        self.assertIn("grade-fixture-walker.py", command)
        self.assertIn("false-positive blocks release", command)
        self.assertIn("near-miss fixture", command)


if __name__ == "__main__":
    unittest.main()
