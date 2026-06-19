from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "harness" / "evolve-loop" / "bin" / "release-plan.py"
READ_REF = ROOT / "harness" / "evolve-loop" / "bin" / "skill-read-ref.py"
RELEASE = ROOT / "harness" / "evolve-loop" / "bin" / "release.sh"
COMMAND = ROOT / "commands" / "bs-evolve.md"


def run(cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    run(["git", "init"], cwd=path)
    run(["git", "config", "user.email", "test@example.com"], cwd=path)
    run(["git", "config", "user.name", "Test User"], cwd=path)


class BsEvolveB2B3Tests(unittest.TestCase):
    def test_release_plan_uses_max_release_tag_and_candidate_patch_plus_one(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "skill"
            init_repo(repo)
            (repo / "skill.yaml").write_text('name: bs\nversion: "1.2.0"\n', encoding="utf-8")
            run(["git", "add", "skill.yaml"], cwd=repo)
            run(["git", "commit", "-m", "init"], cwd=repo)
            run(["git", "tag", "v1.4.9"], cwd=repo)
            (repo / "skill.yaml").write_text('name: bs\nversion: "1.4.10"\n', encoding="utf-8")
            run(["git", "commit", "-am", "bump"], cwd=repo)
            run(["git", "tag", "v1.4.10"], cwd=repo)
            run(["git", "tag", "not-a-release"], cwd=repo)
            out = repo / "plan.yaml"
            proc = run([sys.executable, str(PLAN), "--skill", str(repo), "--out", str(out), "--json"])
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["baseline_ref"], "v1.4.10")
            self.assertEqual(payload["candidate_version"], "v1.4.11")
            written = yaml.safe_load(out.read_text(encoding="utf-8"))
            self.assertEqual(written["baseline_ref"], "v1.4.10")
            self.assertRegex(written["baseline_sha"], r"^[0-9a-f]{40}$")

    def test_skill_read_ref_reads_bound_history_not_current_worktree(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "skill"
            init_repo(repo)
            (repo / "commands").mkdir()
            (repo / "commands" / "bs-evolve.md").write_text("rule-set-v1\n", encoding="utf-8")
            run(["git", "add", "commands/bs-evolve.md"], cwd=repo)
            run(["git", "commit", "-m", "v1"], cwd=repo)
            old = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
            (repo / "commands" / "bs-evolve.md").write_text("rule-set-v2\n", encoding="utf-8")
            run(["git", "commit", "-am", "v2"], cwd=repo)
            proc = run([sys.executable, str(READ_REF), "--skill", str(repo), "--ref", old, "--path", "commands/bs-evolve.md"])
            self.assertEqual(proc.stdout, "rule-set-v1\n")
            head = run([sys.executable, str(READ_REF), "--skill", str(repo), "--ref", "HEAD", "--path", "commands/bs-evolve.md"])
            self.assertEqual(head.stdout, "rule-set-v2\n")

    def test_release_script_is_skill_only_and_uses_explicit_candidate_push(self):
        text = RELEASE.read_text(encoding="utf-8")
        self.assertIn("--plan-file", text)
        self.assertIn('git push origin "HEAD:refs/heads/main"', text)
        self.assertIn('git merge --ff-only "$VERSION"', text)
        self.assertNotIn("sync-bs-binding.py", text)
        self.assertNotIn("cd \"$TARGET\"", text)
        self.assertNotIn(".bootstrap/contract.sha256", text)

    def test_release_g1_anchors_top_level_skill_version_not_contract_version(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "skill"
            init_repo(repo)
            (repo / "skill.yaml").write_text('name: bs\nversion: "1.0.0"\ncontract_version: "1.0.0"\n', encoding="utf-8")
            (repo / "contract.md").write_text("# Contract\n\nrelease v1.0.0\n", encoding="utf-8")
            run(["git", "add", "skill.yaml", "contract.md"], cwd=repo)
            run(["git", "commit", "-m", "base"], cwd=repo)
            anchor = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
            (repo / "skill.yaml").write_text('name: bs\nversion: "1.0.0"\ncontract_version: "1.0.1"\n', encoding="utf-8")
            (repo / "contract.md").write_text("# Contract\n\nrelease v1.0.1\n", encoding="utf-8")
            run(["git", "commit", "-am", "contract-version-only"], cwd=repo)
            proc = run(
                [
                    "bash",
                    str(RELEASE),
                    "--skill",
                    str(repo),
                    "--version",
                    "v1.0.1",
                    "--anchor",
                    anchor,
                    "--no-backtest",
                    "contract prose only",
                    "--dry",
                ],
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("skill.yaml top-level version mismatch", proc.stdout + proc.stderr)

    def test_command_documents_b2_b3_protocols(self):
        text = COMMAND.read_text(encoding="utf-8")
        self.assertIn("release-plan.py", text)
        self.assertIn("baseline_ref", text)
        self.assertIn("candidate_version", text)
        self.assertIn("stale-anchor evidence", text)
        self.assertIn("skill-read-ref.py", text)
        self.assertIn("binding source", text)
        self.assertIn("Target pin-sync is deferred", text)


if __name__ == "__main__":
    unittest.main()
