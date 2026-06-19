from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROLLBACK = ROOT / "harness" / "evolve-loop" / "bin" / "rollback.sh"
EVOLVE_LOCK = ROOT / "harness" / "evolve-loop" / "bin" / "evolve-lock.py"
COMMAND = ROOT / "commands" / "bs-evolve.md"


def run(cmd, cwd=None, check=False):
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    run(["git", "init"], cwd=repo, check=True)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)


def make_rollback_fixture(base: Path) -> tuple[Path, Path, str, str, str]:
    bare = base / "origin.git"
    run(["git", "init", "--bare", str(bare)], check=True)
    repo = base / "skill"
    init_repo(repo)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    run(["git", "add", "README.md"], cwd=repo, check=True)
    run(["git", "commit", "-m", "base"], cwd=repo, check=True)
    run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True)
    run(["git", "push", "origin", "HEAD:refs/heads/main"], cwd=repo, check=True)
    (repo / "bad.txt").write_text("bad release\n", encoding="utf-8")
    run(["git", "add", "bad.txt"], cwd=repo, check=True)
    run(["git", "commit", "-m", "bad release"], cwd=repo, check=True)
    bad = run(["git", "rev-parse", "HEAD"], cwd=repo, check=True).stdout.strip()
    run(["git", "tag", "v1.0.1"], cwd=repo, check=True)
    run(["git", "push", "origin", "HEAD:refs/heads/main", "v1.0.1"], cwd=repo, check=True)
    (repo / "sibling.txt").write_text("sibling release\n", encoding="utf-8")
    run(["git", "add", "sibling.txt"], cwd=repo, check=True)
    run(["git", "commit", "-m", "sibling release"], cwd=repo, check=True)
    later = run(["git", "rev-parse", "HEAD"], cwd=repo, check=True).stdout.strip()
    run(["git", "push", "origin", "HEAD:refs/heads/main"], cwd=repo, check=True)
    return repo, bare, bad, later, "v1.0.1"


class BsEvolveB8Tests(unittest.TestCase):
    def test_rollback_script_is_forward_safe_and_lock_held(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo, bare, bad, later, tag = make_rollback_fixture(base / "forward")
            proc = run(["bash", str(ROLLBACK), "--skill", str(repo), "--bad-sha", bad, "--summary", "behavior test"])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            run(["git", "fetch", "origin", "main", "--tags"], cwd=repo, check=True)
            origin_main = run(["git", "rev-parse", "origin/main"], cwd=repo, check=True).stdout.strip()
            self.assertEqual(run(["git", "merge-base", "--is-ancestor", later, "origin/main"], cwd=repo).returncode, 0)
            self.assertEqual(run(["git", f"--git-dir={bare}", "rev-parse", f"{tag}^{{commit}}"], check=True).stdout.strip(), bad)
            self.assertNotEqual(run(["git", f"--git-dir={bare}", "cat-file", "-e", f"{origin_main}:bad.txt"]).returncode, 0)

            locked_repo, _locked_bare, locked_bad, _locked_later, _locked_tag = make_rollback_fixture(base / "locked")
            lock = locked_repo / ".bs-evolve" / "SKILL.lock"
            acq = run([sys.executable, str(EVOLVE_LOCK), "acquire", "--lock-file", str(lock), "--owner", "test"], check=True)
            token = __import__("json").loads(acq.stdout)["token"]
            try:
                locked = run(["bash", str(ROLLBACK), "--skill", str(locked_repo), "--bad-sha", locked_bad, "--dry"])
                self.assertEqual(locked.returncode, 11, locked.stdout + locked.stderr)
                self.assertIn("SKILL.lock held", locked.stdout + locked.stderr)
            finally:
                run([sys.executable, str(EVOLVE_LOCK), "release", "--lock-file", str(lock), "--token", token], check=True)

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
