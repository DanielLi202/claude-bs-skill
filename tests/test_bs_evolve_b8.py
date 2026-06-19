from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROLLBACK = ROOT / "harness" / "evolve-loop" / "bin" / "rollback.sh"
COMMAND = ROOT / "commands" / "bs-evolve.md"


def run(cmd, cwd=None, check=False):
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    run(["git", "init"], cwd=repo, check=True)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)


class BsEvolveB8Tests(unittest.TestCase):
    def test_rollback_script_is_forward_safe_and_lock_held(self):
        text = ROLLBACK.read_text(encoding="utf-8")
        self.assertIn("SKILL.lock", text)
        self.assertIn("evolve-lock.py", text)
        self.assertIn("git revert --no-edit", text)
        self.assertIn("git push origin HEAD:refs/heads/main", text)
        self.assertNotIn("git reset --hard", text)
        self.assertNotIn("git tag -d", text)
        self.assertNotIn(":refs/tags", text)

    def test_rollback_rejects_legacy_reset_and_tag_delete_args(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "skill"
            init_repo(repo)
            (repo / "f").write_text("a\n", encoding="utf-8")
            run(["git", "add", "f"], cwd=repo, check=True)
            run(["git", "commit", "-m", "base"], cwd=repo, check=True)
            bad = run(["git", "rev-parse", "HEAD"], cwd=repo, check=True).stdout.strip()
            proc = run(["bash", str(ROLLBACK), "--skill", str(repo), "--bad-sha", bad, "--bad-tag", "v1.2.3", "--pushed"])
            self.assertEqual(proc.returncode, 2)
            self.assertIn("legacy reset/tag-delete args are refused", proc.stderr)

    def test_rollback_rejects_rev_expressions_branches_and_tags(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "skill"
            init_repo(repo)
            (repo / "f").write_text("a\n", encoding="utf-8")
            run(["git", "add", "f"], cwd=repo, check=True)
            run(["git", "commit", "-m", "base"], cwd=repo, check=True)
            run(["git", "tag", "vbad"], cwd=repo, check=True)
            for bad in ["HEAD~1", "HEAD", "main", "vbad", "A" * 40, "0" * 39]:
                proc = run(["bash", str(ROLLBACK), "--skill", str(repo), "--bad-sha", bad, "--dry"])
                self.assertEqual(proc.returncode, 2, bad + proc.stdout + proc.stderr)
                if bad != "0" * 39:
                    self.assertIn("explicit 40-character lowercase", proc.stdout + proc.stderr)

    def test_dry_run_preserves_head_and_tags(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "skill"
            init_repo(repo)
            (repo / "f").write_text("a\n", encoding="utf-8")
            run(["git", "add", "f"], cwd=repo, check=True)
            run(["git", "commit", "-m", "base"], cwd=repo, check=True)
            run(["git", "tag", "v1.0.0"], cwd=repo, check=True)
            before = run(["git", "rev-parse", "HEAD"], cwd=repo, check=True).stdout.strip()
            proc = run(["bash", str(ROLLBACK), "--skill", str(repo), "--bad-sha", before, "--dry"])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(run(["git", "rev-parse", "HEAD"], cwd=repo, check=True).stdout.strip(), before)
            self.assertEqual(run(["git", "tag", "--list", "v1.0.0"], cwd=repo, check=True).stdout.strip(), "v1.0.0")

    def test_command_documents_b8_forward_revert(self):
        text = COMMAND.read_text(encoding="utf-8")
        self.assertIn("rollback", text.lower())
        self.assertIn("never deletes a pushed tag", text)


if __name__ == "__main__":
    unittest.main()
