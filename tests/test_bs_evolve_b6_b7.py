from __future__ import annotations

import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import unittest
import yaml
import hashlib

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "harness" / "evolve-loop" / "bin" / "pin-sync.py"
FLEET_UPDATE = ROOT / "harness" / "evolve-loop" / "bin" / "fleet-update.py"
FLEET_STOP = ROOT / "harness" / "evolve-loop" / "bin" / "fleet-stop.py"
JITTER = ROOT / "harness" / "evolve-loop" / "bin" / "retry-jitter.py"
LOCK = ROOT / "harness" / "evolve-loop" / "bin" / "evolve-lock.py"
RELEASE = ROOT / "harness" / "evolve-loop" / "bin" / "release.sh"
COMMAND = ROOT / "commands" / "bs-evolve.md"


def run(cmd, cwd=None, check=False):
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    run(["git", "init"], cwd=repo, check=True)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)


def write_min_bootstrap(target: Path, skill: Path, digest: str) -> None:
    (target / ".bootstrap").mkdir(exist_ok=True)
    (target / ".bootstrap" / "backlog.yaml").write_text("tasks: []\n", encoding="utf-8")
    (target / ".bootstrap" / "ledger.yaml").write_text("cycles: []\n", encoding="utf-8")
    (target / ".bootstrap" / "contract.sha256").write_text(digest + "\n", encoding="utf-8")
    (target / ".bootstrap.yaml").write_text(yaml.safe_dump({
        "schema_version": 1,
        "contract": {
            "source_url": "file://skill",
            "source_tag": "v0.0.0",
            "source_commit": "0" * 40,
            "source_sha256": digest,
            "sha256_path": ".bootstrap/contract.sha256",
            "compatible_range": ">=0.0.0",
        },
        "backlog": ".bootstrap/backlog.yaml",
        "ledger": ".bootstrap/ledger.yaml",
        "cycle_dir_root": ".bootstrap/cycles",
        "red_lines": [],
        "verify_command": "true",
    }, sort_keys=False), encoding="utf-8")
    (target / ".bootstrap" / "cycles").mkdir(exist_ok=True)


class BsEvolveB6B7Tests(unittest.TestCase):
    def test_pin_sync_commits_target_pin_and_leaves_tree_clean(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            skill = base / "skill"
            target = base / "target"
            skill.mkdir(); (skill / "contract.md").write_text("contract v2\n", encoding="utf-8")
            init_repo(target)
            write_min_bootstrap(target, skill, "0" * 64)
            run(["git", "add", "."], cwd=target, check=True)
            run(["git", "commit", "-m", "base"], cwd=target, check=True)
            proc = run([sys.executable, str(PIN), "--target", str(target), "--skill", str(skill), "--commit"])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("refresh bs contract pin", run(["git", "log", "-1", "--pretty=%s"], cwd=target, check=True).stdout)
            self.assertEqual(run(["git", "status", "--porcelain"], cwd=target, check=True).stdout, "")
            expected = hashlib.sha256((skill / "contract.md").read_bytes()).hexdigest()
            boot = yaml.safe_load((target / ".bootstrap.yaml").read_text(encoding="utf-8"))
            self.assertEqual(boot["contract"]["source_sha256"], expected)
            self.assertEqual((target / ".bootstrap" / "contract.sha256").read_text().strip(), expected)
            validate = run([sys.executable, "-c", "import pathlib,yaml; from lib import binding; repo=pathlib.Path(r'" + str(target) + "'); binding.validate(repo, yaml.safe_load((repo/'.bootstrap.yaml').read_text()), pathlib.Path(r'" + str(skill / "contract.md") + "'))"], cwd=ROOT)
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)

    def test_pin_sync_fails_closed_on_dirty_target_before_refresh(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            skill = base / "skill"
            target = base / "target"
            skill.mkdir(); (skill / "contract.md").write_text("contract v2\n", encoding="utf-8")
            init_repo(target)
            write_min_bootstrap(target, skill, "0" * 64)
            run(["git", "add", "."], cwd=target, check=True)
            run(["git", "commit", "-m", "base"], cwd=target, check=True)
            (target / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            proc = run([sys.executable, str(PIN), "--target", str(target), "--skill", str(skill), "--commit"])
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("target tree dirty", proc.stderr)

    def test_fleet_update_under_skill_lock_preserves_projects_and_init_uses_lock(self):
        init_text = (ROOT / "harness" / "evolve-loop" / "bin" / "bs-evolve-init.py").read_text(encoding="utf-8")
        self.assertIn("evolve-lock.py", init_text)
        self.assertIn("fleet-update.py", init_text)
        self.assertIn("SKILL.lock", init_text)
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            fleet = base / "skill" / ".bs-evolve" / "fleet.yaml"
            lock = base / "skill" / ".bs-evolve" / "SKILL.lock"

            for slug in ["a", "b"]:
                acq = run([sys.executable, str(LOCK), "acquire", "--lock-file", str(lock), "--owner", slug], check=True)
                token = __import__("json").loads(acq.stdout)["token"]
                try:
                    proc = run([sys.executable, str(FLEET_UPDATE), "--fleet", str(fleet), "--slug", slug, "--target", f"/tmp/{slug}", "--config", f"/tmp/{slug}/.bs-evolve/config.yaml"])
                    self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                finally:
                    run([sys.executable, str(LOCK), "release", "--lock-file", str(lock), "--token", token])

            data = yaml.safe_load(fleet.read_text(encoding="utf-8"))
            self.assertEqual(sorted(data["projects"]), ["a", "b"])

    def test_init_fails_before_skill_writes_when_skill_lock_is_held(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            skill = ROOT
            target = base / "target"
            init_repo(target)
            dog = target / ".prompts" / "dogfood" / "cycle-001"
            dog.mkdir(parents=True)
            (dog / "grade_round_1.md").write_text("enough anonymizable generic evidence text " * 4, encoding="utf-8")
            run(["git", "add", "."], cwd=target, check=True)
            run(["git", "commit", "-m", "seed corpus"], cwd=target, check=True)
            lock = skill / ".bs-evolve" / "SKILL.lock"
            acq = run([sys.executable, str(skill / "harness" / "evolve-loop" / "bin" / "evolve-lock.py"), "acquire", "--lock-file", str(lock), "--owner", "other"], check=True)
            try:
                before = set((skill / "tests" / "grade_lint_fixtures").glob("anon-*"))
                proc = run([sys.executable, str(skill / "harness" / "evolve-loop" / "bin" / "bs-evolve-init.py"), str(target), "--slug", "locked-demo"])
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("SKILL.lock held", proc.stderr + proc.stdout)
                after = set((skill / "tests" / "grade_lint_fixtures").glob("anon-*"))
                self.assertEqual(before, after)
            finally:
                token = __import__("json").loads(acq.stdout)["token"]
                run([sys.executable, str(skill / "harness" / "evolve-loop" / "bin" / "evolve-lock.py"), "release", "--lock-file", str(lock), "--token", token])

    def test_fleet_stop_writes_stop_tombstones(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            c1 = base / "p1" / ".bs-evolve" / "config.yaml"; c1.parent.mkdir(parents=True); c1.write_text("", encoding="utf-8")
            c2 = base / "p2" / ".bs-evolve" / "config.yaml"; c2.parent.mkdir(parents=True); c2.write_text("", encoding="utf-8")
            fleet = base / "fleet.yaml"
            fleet.write_text(yaml.safe_dump({"projects": {"p1": {"config": str(c1)}, "p2": {"config": str(c2)}}}), encoding="utf-8")
            proc = run([sys.executable, str(FLEET_STOP), "--fleet", str(fleet), "--slug", "p2"])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertFalse((c1.parent / "STOP").exists())
            self.assertTrue((c2.parent / "STOP").exists())

    def test_retry_jitter_is_deterministic_and_project_specific(self):
        a1 = int(run([sys.executable, str(JITTER), "--slug", "alpha", "--base", "1800", "--spread", "420"], check=True).stdout)
        a2 = int(run([sys.executable, str(JITTER), "--slug", "alpha", "--base", "1800", "--spread", "420"], check=True).stdout)
        b = int(run([sys.executable, str(JITTER), "--slug", "beta", "--base", "1800", "--spread", "420"], check=True).stdout)
        self.assertEqual(a1, a2)
        self.assertNotEqual(a1, b)
        self.assertTrue(1800 <= a1 < 2220)

    def test_release_script_has_no_target_reach_in_and_command_documents_b6_b7(self):
        release = RELEASE.read_text(encoding="utf-8")
        self.assertNotIn("sync-bs-binding.py", release)
        self.assertNotIn("git push origin main || { say \"push target", release)
        text = COMMAND.read_text(encoding="utf-8")
        self.assertIn("pin-sync.py", text)
        self.assertIn("fleet-update.py", text)
        self.assertIn("fleet-stop.py", text)
        self.assertIn("retry-jitter.py", text)


if __name__ == "__main__":
    unittest.main()
