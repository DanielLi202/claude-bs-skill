from __future__ import annotations

import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "harness" / "evolve-loop" / "bin" / "bs-evolve-config.py"


def run(cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def parse_exports(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in text.splitlines():
        parts = shlex.split(line)
        if not parts or parts[0] != "export" or len(parts) != 2 or "=" not in parts[1]:
            continue
        key, value = parts[1].split("=", 1)
        env[key] = value
    return env


class BsEvolveZeroConfigDiscoveryTests(unittest.TestCase):
    def init_git(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        run(["git", "init"], cwd=path)
        run(["git", "config", "user.email", "test@example.com"], cwd=path)
        run(["git", "config", "user.name", "Test User"], cwd=path)

    def write_config(self, target: Path, slug: str = "demo") -> Path:
        config_dir = target / ".bs-evolve"
        config_dir.mkdir(parents=True, exist_ok=True)
        config = config_dir / "config.yaml"
        config.write_text("\n".join([
            "schema_version: 1",
            f"project_slug: {slug}",
            "target_repo: ..",
            "state_dir: .",
            "reviews_root: ./reviews",
            "corpus_dir: ./corpus",
            "mode: auto",
            "max_iterations: 7",
        ]), encoding="utf-8")
        return config

    def test_initialized_root_zero_arg_matches_explicit_config_and_breaks_when_config_removed(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "target"
            self.init_git(target)
            config = self.write_config(target)

            discovered = run([sys.executable, str(CONFIG), "--emit-env"], cwd=target).stdout
            explicit = run([sys.executable, str(CONFIG), "--config", str(config), "--emit-env"], cwd=ROOT).stdout
            self.assertEqual(parse_exports(discovered), parse_exports(explicit))

            moved = config.with_suffix(".moved")
            config.rename(moved)
            failed = run([sys.executable, str(CONFIG), "--emit-env"], cwd=target, check=False)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("/bs-evolve-init", failed.stderr)
            self.assertNotIn("export BS_LOOP_", failed.stdout)

    def test_subdirectory_zero_arg_discovers_git_root_config(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "target"
            self.init_git(target)
            config = self.write_config(target)
            subdir = target / "nested" / "child"
            subdir.mkdir(parents=True)

            env = parse_exports(run([sys.executable, str(CONFIG), "--emit-env"], cwd=subdir).stdout)
            self.assertEqual(env["BS_LOOP_TARGET_REPO"], str(target.resolve()))
            self.assertEqual(env["BS_LOOP_STATE_DIR"], str((target / ".bs-evolve").resolve()))
            self.assertIn(f"/bs-evolve --config {config.resolve()}", env["BS_LOOP_WAKE_PROMPT"])

    def test_uninitialized_git_repo_fails_closed_without_emit_env(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "uninitialized"
            self.init_git(target)
            proc = run([sys.executable, str(CONFIG), "--emit-env"], cwd=target, check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("未初始化", proc.stderr)
            self.assertIn("/bs-evolve-init", proc.stderr)
            self.assertNotIn("export BS_LOOP_", proc.stdout)
            self.assertNotIn(str((target / ".bs-evolve" / "reviews").resolve()), proc.stdout + proc.stderr)

    def test_non_git_directory_fails_without_traceback(self):
        with tempfile.TemporaryDirectory() as td:
            proc = run([sys.executable, str(CONFIG), "--emit-env"], cwd=Path(td), check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("not inside a git repository", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr + proc.stdout)
            self.assertNotIn("export BS_LOOP_", proc.stdout)

    def test_explicit_config_override_still_works_outside_target_repo(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "target"
            other = Path(td) / "other"
            self.init_git(target)
            other.mkdir()
            config = self.write_config(target, slug="override-demo")

            env = parse_exports(run([sys.executable, str(CONFIG), "--config", str(config), "--emit-env"], cwd=other).stdout)
            self.assertEqual(env["BS_LOOP_PROJECT_SLUG"], "override-demo")
            self.assertEqual(env["BS_LOOP_TARGET_REPO"], str(target.resolve()))

    def test_zero_arg_wake_prompt_contains_resolved_absolute_config_path(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "target"
            self.init_git(target)
            config = self.write_config(target)
            env = parse_exports(run([sys.executable, str(CONFIG), "--emit-env"], cwd=target).stdout)
            wake = env["BS_LOOP_WAKE_PROMPT"]
            self.assertIn(f"--config {config.resolve()}", wake)
            self.assertNotIn("--config .bs-evolve/config.yaml", wake)


if __name__ == "__main__":
    unittest.main()
