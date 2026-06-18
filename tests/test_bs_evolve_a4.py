from __future__ import annotations

import os
import shutil
import subprocess
import uuid
import sys
import tempfile
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "harness" / "evolve-loop" / "bin" / "bs-evolve-init.py"


def run(cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def make_repo(base: Path, name: str = "target") -> Path:
    repo = base / name
    repo.mkdir()
    run(["git", "init"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    dog = repo / ".prompts" / "dogfood" / "cycle-001"
    dog.mkdir(parents=True)
    (dog / "grade_round_1.md").write_text("spec_compliance_matrix:\n- id: a1\n  status: PASS\n  evidence_ref: ProjectZephyr package manager registry check passed under /Users/example/ProjectZephyr with TASK-123 and decision-abc redacted\n", encoding="utf-8")
    run(["git", "add", ".prompts/dogfood/cycle-001/grade_round_1.md"], cwd=repo)
    run(["git", "commit", "-m", "seed corpus"], cwd=repo)
    return repo


class BsEvolveA4InitTests(unittest.TestCase):
    def test_init_creates_config_gitignore_state_fixture_and_ignored_fleet(self):
        with tempfile.TemporaryDirectory() as td:
            repo = make_repo(Path(td), "ProjectZephyr")
            before = set((ROOT / "tests" / "grade_lint_fixtures").glob("anon-*"))
            slug = "demo-" + uuid.uuid4().hex[:8]
            proc = run([sys.executable, str(INIT), str(repo), "--slug", slug, "--mode", "auto"])
            self.assertIn('"cycles": 1', proc.stdout)
            cfg = yaml.safe_load((repo / ".bs-evolve" / "config.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["state_dir"], ".")
            self.assertEqual(cfg["reviews_root"], "./reviews")
            self.assertEqual(cfg["corpus_dir"], "./corpus")
            self.assertEqual(cfg["mode"], "auto")
            self.assertTrue((repo / ".bs-evolve" / "state.json").exists())
            self.assertEqual(run(["git", "check-ignore", "-q", ".bs-evolve/config.yaml"], cwd=repo, check=False).returncode, 0)
            self.assertEqual(run(["git", "check-ignore", "-q", ".bs-evolve/state.json"], cwd=repo, check=False).returncode, 0)
            self.assertNotEqual(run(["git", "check-ignore", "-q", ".bs-evolve/reviews/cycle-001/closure.yaml"], cwd=repo, check=False).returncode, 0)
            after = set((ROOT / "tests" / "grade_lint_fixtures").glob("anon-*"))
            new = list(after - before)
            self.assertEqual(len(new), 1)
            meta = yaml.safe_load((new[0] / "metadata.yaml").read_text(encoding="utf-8"))
            text = (new[0] / "grade.md").read_text(encoding="utf-8")
            self.assertEqual(meta["task_type"], "code")
            self.assertEqual(meta["risk_level"], "low")
            self.assertNotRegex(text, r"ProjectZephyr|/Users/|[A-Z]+-\d{3}|decision[-_ ]")
            self.assertEqual(run(["git", "check-ignore", "-q", ".bs-evolve/fleet.yaml"], cwd=ROOT, check=False).returncode, 0)
            shutil.rmtree(new[0])

    def test_init_fails_without_corpus(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "empty"
            repo.mkdir()
            run(["git", "init"], cwd=repo)
            proc = run([sys.executable, str(INIT), str(repo), "--slug", "empty"], check=False)
            self.assertEqual(proc.returncode, 3)
            self.assertIn("corpus_dir glob found no code cycles", proc.stderr)


if __name__ == "__main__":
    unittest.main()
