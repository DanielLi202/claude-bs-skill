from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "harness" / "evolve-loop" / "bin" / "migrate-inplace.sh"
CONFIG = ROOT / "harness" / "evolve-loop" / "bin" / "bs-evolve-config.py"
ADOPT = ROOT / "harness" / "evolve-loop" / "bin" / "adopt-cycle.py"
CLOSURE = ROOT / "harness" / "evolve-loop" / "bin" / "closure.py"


def run(cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    run(["git", "init"], cwd=path)
    run(["git", "config", "user.email", "test@example.com"], cwd=path)
    run(["git", "config", "user.name", "Test User"], cwd=path)


def tree_manifest(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            out[rel + "/"] = "dir"
        elif path.is_symlink():
            out[rel] = "symlink:" + os.readlink(path)
        elif path.is_file():
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def ls_prompts_bsevolve(repo: Path) -> str:
    return run(["bash", "-lc", "ls -laR .prompts .bs-evolve 2>&1 || true"], cwd=repo).stdout


def make_skill_with_deleted_reviews(base: Path) -> Path:
    skill = base / "skill"
    init_repo(skill)
    review = skill / "harness" / "evolve-loop" / "reviews" / "opensymphony" / "cycle-007"
    review.mkdir(parents=True)
    (review / "closure.yaml").write_text(
        "cycle: cycle-007\nr1: done\nr2: done\nskill_release: v1.0.0\nremediation: done\nclosed: true\n",
        encoding="utf-8",
    )
    (review / "r1.md").write_text("historical r1\n", encoding="utf-8")
    run(["git", "add", "harness/evolve-loop/reviews"], cwd=skill)
    run(["git", "commit", "-m", "archive old reviews"], cwd=skill)
    shutil.rmtree(skill / "harness" / "evolve-loop" / "reviews" / "opensymphony")
    (skill / "harness" / "evolve-loop" / "reviews" / ".gitkeep").write_text("", encoding="utf-8")
    run(["git", "add", "-A", "harness/evolve-loop/reviews"], cwd=skill)
    run(["git", "commit", "-m", "remove live reviews"], cwd=skill)
    return skill


def make_target(base: Path, *, running_lock: bool = False) -> Path:
    target = base / "target"
    init_repo(target)
    loop = target / ".prompts" / "loop"
    loop.mkdir(parents=True)
    (loop / "inflight").mkdir()
    if running_lock:
        (loop / "RUNNING.lock").write_text("busy\n", encoding="utf-8")
    (loop / "state.json").write_text(
        json.dumps(
            {
                "loop": "bs-evolve-loop",
                "target_repo": str(target),
                "mode": "auto",
                "iteration": 20,
                "max_iterations": 20,
                "anchor": {"legacy_path": str(loop / "iter-020")},
                "history": [str(loop / "iter-019"), ".prompts/loop/iter-020"],
                "stop_reason": "backlog_exhausted",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    for n in (7, 8, 9):
        c = target / ".prompts" / "dogfood" / f"cycle-{n:03d}"
        c.mkdir(parents=True)
        (c / "cycle.yaml").write_text("type: code\nrisk_level: low\n", encoding="utf-8")
        (c / "outcome.md").write_text(f"outcome {n}\n", encoding="utf-8")
        (c / "grade_round_1.md").write_text("grade_summary:\n  p0_count: 0\n", encoding="utf-8")
    boot = target / ".bootstrap"
    boot.mkdir()
    (boot / "contract.sha256").write_text("0" * 64 + "\n", encoding="utf-8")
    run(["git", "add", ".prompts", ".bootstrap"], cwd=target)
    run(["git", "commit", "-m", "seed stopped legacy loop"], cwd=target)
    return target


class BsEvolveInplaceMigrationTests(unittest.TestCase):
    def test_dry_run_prints_plan_and_has_zero_target_side_effects(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            skill = make_skill_with_deleted_reviews(base)
            target = make_target(base)
            before_status = run(["git", "status", "--short"], cwd=target).stdout
            before_ls = ls_prompts_bsevolve(target)
            before_tree = tree_manifest(target)
            proc = run([
                sys.executable,
                str(SCRIPT),
                "--target",
                str(target),
                "--skill",
                str(skill),
                "--slug",
                "demo",
                "--backup-dir",
                str(base / "backups"),
                "--dry-run",
            ])
            self.assertIn("MIGRATE_INPLACE_PLAN", proc.stdout)
            self.assertIn("detected_migrated_through_cycle=009", proc.stdout)
            self.assertIn("DRY_RUN_OK zero target writes performed", proc.stdout)
            self.assertEqual(before_status, run(["git", "status", "--short"], cwd=target).stdout)
            self.assertEqual(before_ls, ls_prompts_bsevolve(target))
            self.assertEqual(before_tree, tree_manifest(target))
            self.assertFalse((base / "backups").exists())

    def test_real_migration_builds_config_commits_archived_reviews_and_tombstones_legacy_loop(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            skill = make_skill_with_deleted_reviews(base)
            target = make_target(base)
            proc = run([
                sys.executable,
                str(SCRIPT),
                "--target",
                str(target),
                "--skill",
                str(skill),
                "--slug",
                "demo",
                "--backup-dir",
                str(base / "backups"),
            ])
            self.assertIn("MIGRATE_OK", proc.stdout)
            self.assertIn("reviews_copied_from_skill_history=2", proc.stdout)
            self.assertEqual(run(["git", "status", "--short"], cwd=skill).stdout, "")

            cfg = yaml.safe_load((target / ".bs-evolve" / "config.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["migrated_through_cycle"], 9)
            self.assertNotIn("042", (target / ".bs-evolve" / "config.yaml").read_text(encoding="utf-8"))
            env = run([sys.executable, str(CONFIG), "--config", str(target / ".bs-evolve" / "config.yaml"), "--emit-env"]).stdout
            self.assertIn("export BS_LOOP_PROJECT_SLUG=demo", env)
            self.assertIn("export BS_LOOP_ADOPT_MIN_CYCLE=10", env)
            self.assertIn(str((target / ".prompts" / "dogfood").resolve()), env)

            tracked_reviews = run(["git", "ls-files", ".bs-evolve/reviews"], cwd=target).stdout.splitlines()
            self.assertIn(".bs-evolve/reviews/cycle-007/closure.yaml", tracked_reviews)
            self.assertIn(".bs-evolve/reviews/cycle-007/r1.md", tracked_reviews)
            self.assertIn("bs-evolve: migrate reviews for demo", run(["git", "log", "-1", "--pretty=%s"], cwd=target).stdout)

            for ignored in [".bs-evolve/state.json", ".bs-evolve/RUNNING.lock", ".bs-evolve/config.yaml", ".bs-evolve/corpus", ".bs-evolve/fleet.yaml"]:
                self.assertEqual(run(["git", "check-ignore", "-q", ignored], cwd=target, check=False).returncode, 0, ignored)
            self.assertNotEqual(run(["git", "check-ignore", "-q", ".bs-evolve/reviews/cycle-007/closure.yaml"], cwd=target, check=False).returncode, 0)

            self.assertTrue((target / ".prompts" / "loop" / "STOP").exists())
            self.assertTrue((target / ".prompts" / "loop").is_dir())
            self.assertEqual(run(["git", "check-ignore", "-q", ".prompts/loop/STOP"], cwd=target, check=False).returncode, 0)
            self.assertNotIn(".prompts/loop/STOP", run(["git", "status", "--short"], cwd=target).stdout)
            state = json.loads((target / ".bs-evolve" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["stop_reason"], "backlog_exhausted")
            self.assertIn(".bs-evolve", state["history"][1])
            self.assertGreaterEqual(len(list((target / ".prompts" / "dogfood").glob("cycle-*/cycle.yaml"))), 1)
            newest = run([sys.executable, str(CLOSURE), "--reviews-root", str(target / ".bs-evolve" / "reviews"), "newest-open"], check=False)
            self.assertEqual(newest.returncode, 10, newest.stdout + newest.stderr)
            adopt = run([
                sys.executable,
                str(ADOPT),
                "--corpus-root",
                str(target / ".prompts" / "dogfood"),
                "--reviews-root",
                str(target / ".bs-evolve" / "reviews"),
                "--min-cycle",
                "10",
            ], check=False)
            self.assertEqual(adopt.returncode, 10, adopt.stdout + adopt.stderr)

    def test_static_precondition_failure_is_nonzero_and_zero_write(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            skill = make_skill_with_deleted_reviews(base)
            target = make_target(base, running_lock=True)
            before_status = run(["git", "status", "--short"], cwd=target).stdout
            before_tree = tree_manifest(target)
            proc = run([
                sys.executable,
                str(SCRIPT),
                "--target",
                str(target),
                "--skill",
                str(skill),
                "--slug",
                "demo",
                "--backup-dir",
                str(base / "backups"),
            ], check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("RUNNING.lock exists", proc.stderr)
            self.assertEqual(before_status, run(["git", "status", "--short"], cwd=target).stdout)
            self.assertEqual(before_tree, tree_manifest(target))
            self.assertFalse((target / ".bs-evolve").exists())
            self.assertFalse((base / "backups").exists())



    def test_quiet_preconditions_rejects_codex_worker_cwd_inside_target(self):
        import importlib.machinery
        import importlib.util

        loader = importlib.machinery.SourceFileLoader("migrate_inplace", str(SCRIPT))
        spec = importlib.util.spec_from_loader("migrate_inplace", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            target = make_target(base)
            subdir = target / "nested"
            subdir.mkdir()

            def fake_run(cmd, *, cwd=None, check=True):
                if len(cmd) >= 5 and cmd[0] == "git" and cmd[1] == "-C" and Path(cmd[2]).resolve() == target.resolve() and "diff" in cmd:
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                if cmd[:3] == ["ps", "-axo", "pid=,pgid=,command="]:
                    return subprocess.CompletedProcess(cmd, 0, "123 123 codex exec --skip-git-repo-check\n", "")
                raise AssertionError(f"unexpected command {cmd}")

            with mock.patch.object(module, "run", side_effect=fake_run), mock.patch.object(module, "process_cwd", return_value=str(subdir)):
                ok, reasons = module.quiet_preconditions(target)

            self.assertFalse(ok)
            self.assertTrue(any("live codex process" in reason for reason in reasons), reasons)

    def test_precondition_rejects_prestaged_target_changes_without_writing(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            skill = make_skill_with_deleted_reviews(base)
            target = make_target(base)
            (target / "unrelated.txt").write_text("pre-staged unrelated\n", encoding="utf-8")
            run(["git", "add", "unrelated.txt"], cwd=target)
            before_status = run(["git", "status", "--short"], cwd=target).stdout
            before_tree = tree_manifest(target)
            proc = run([
                sys.executable,
                str(SCRIPT),
                "--target",
                str(target),
                "--skill",
                str(skill),
                "--slug",
                "demo",
                "--backup-dir",
                str(base / "backups"),
            ], check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("pre-staged changes", proc.stderr)
            self.assertEqual(before_status, run(["git", "status", "--short"], cwd=target).stdout)
            self.assertEqual(before_tree, tree_manifest(target))
            self.assertFalse((target / ".bs-evolve").exists())

    def test_rollback_restores_target_file_tree_and_removes_bsevolve_residue(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            skill = make_skill_with_deleted_reviews(base)
            target = make_target(base)
            before_tree = tree_manifest(target)
            proc = run([
                sys.executable,
                str(SCRIPT),
                "--target",
                str(target),
                "--skill",
                str(skill),
                "--slug",
                "demo",
                "--backup-dir",
                str(base / "backups"),
            ])
            backup_line = next(line for line in proc.stdout.splitlines() if line.startswith("BACKUP="))
            backup = Path(backup_line.split("=", 1)[1])
            self.assertTrue((target / ".bs-evolve").exists())
            rb = run([sys.executable, str(SCRIPT), "--rollback", str(backup)])
            self.assertIn("ROLLBACK_OK", rb.stdout)
            self.assertEqual(before_tree, tree_manifest(target))
            self.assertFalse((target / ".bs-evolve").exists())
            self.assertEqual(run(["git", "status", "--short"], cwd=target).stdout, "")


if __name__ == "__main__":
    unittest.main()
