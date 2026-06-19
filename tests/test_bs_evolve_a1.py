from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "commands" / "bs-evolve.md"
HELPER = ROOT / "harness" / "evolve-loop" / "bin" / "bs-evolve-config.py"
LOOP_STATE = ROOT / "harness" / "evolve-loop" / "bin" / "loop-state.py"


class BsEvolveA1ContractTests(unittest.TestCase):
    def test_command_exists_loads_config_and_exports_environment(self):
        text = COMMAND.read_text(encoding="utf-8")
        self.assertIn("/loop /bs-evolve [--once]", text)
        self.assertIn("Advanced `--config` override", text)
        self.assertIn("/bs-evolve-init", text)
        self.assertIn("bs-evolve-config.py", text)
        self.assertIn("BOOTSTRAP_SKILL_REPO", text)
        self.assertNotIn('eval "$(python3 "$BS_LOOP_SKILL_REPO/harness/evolve-loop/bin/bs-evolve-config.py', text)
        for key in [
            "BS_LOOP_SKILL_REPO",
            "BS_LOOP_TARGET_REPO",
            "BS_LOOP_PROJECT_SLUG",
            "BS_LOOP_STATE_DIR",
            "BS_LOOP_REVIEWS_ROOT",
            "BS_LOOP_CORPUS_DIR",
            "BS_LOOP_HARNESS",
            "BS_LOOP_WAKE_PROMPT",
            "BS_LOOP_MODE",
            "BS_LOOP_MAX_ITERATIONS",
        ]:
            self.assertIn(key, text)

    def test_command_body_has_no_opensymphony_hardcoding(self):
        text = COMMAND.read_text(encoding="utf-8")
        forbidden = [
            "/Users/lidongyuan/workspace/utils/OpenSymphony-V3",
            "reviews/opensymphony",
            ".prompts/dogfood",
            ".prompts/loop",
            "cycle-018",
        ]
        for token in forbidden:
            self.assertNotIn(token, text)

    def test_migration_fixes_are_explicit(self):
        text = COMMAND.read_text(encoding="utf-8")
        release_idx = text.index('loop-guard.sh" release')
        wake_idx = text.index('ScheduleWakeup(delaySeconds: 90')
        self.assertLess(release_idx, wake_idx, "Stage 7 must release before terminal wake")
        self.assertIn('git -C "$BS_LOOP_TARGET_REPO" add', text)
        self.assertIn('/private/tmp/bs-evolve-remediate/${BS_LOOP_PROJECT_SLUG}-<cycle>-${repo_hash}', text)
        self.assertIn('Every turn starts by resolving the installed skill root', text)

    def test_background_supervision_skeleton_is_retained(self):
        text = COMMAND.read_text(encoding="utf-8")
        self.assertIn('run-codex-staged.sh', text)
        self.assertIn('inflight/<stage>.json', text)
        self.assertIn('lock-held retry probe', text)
        self.assertIn('ScheduleWakeup(delaySeconds: 2700, reason: "stage check-in"', text)
        self.assertIn('Use 900 seconds for short review/backtest/canary stages', text)
        self.assertIn('--once` never arms these', text)

    def test_config_helper_emits_expected_exports(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            config_dir = base / "target" / ".bs-evolve"
            config_dir.mkdir(parents=True)
            config = config_dir / "config.yaml"
            config.write_text(
                "\n".join([
                    "schema_version: 1",
                    "project_slug: demo",
                    "target_repo: ..",
                    "state_dir: .",
                    "reviews_root: ./reviews",
                    "corpus_dir: ./corpus",
                    "mode: auto",
                    "max_iterations: 9",
                ]),
                encoding="utf-8",
            )
            out = subprocess.check_output([sys.executable, str(HELPER), "--config", str(config), "--emit-env"], text=True)
            self.assertIn("export BS_LOOP_PROJECT_SLUG=demo", out)
            self.assertIn("export BS_LOOP_MODE=auto", out)
            self.assertIn("export BS_LOOP_MAX_ITERATIONS=9", out)
            self.assertIn(str((base / "target").resolve()), out)

    def test_once_state_step_preserves_auto_mode_without_fake_wake_assertion(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            state_dir = base / "target" / ".bs-evolve"
            state_dir.mkdir(parents=True)
            subprocess.run([
                sys.executable,
                str(LOOP_STATE),
                "--state-dir",
                str(state_dir),
                "init",
                "--target",
                str(base / "target"),
                "--skill",
                str(ROOT),
                "--mode",
                "auto",
                "--max",
                "5",
            ], check=True, text=True, capture_output=True)
            before = subprocess.check_output([sys.executable, str(LOOP_STATE), "--state-dir", str(state_dir), "get", "mode"], text=True).strip()
            advanced = subprocess.check_output([sys.executable, str(LOOP_STATE), "--state-dir", str(state_dir), "begin-iteration"], text=True).strip()
            after = subprocess.check_output([sys.executable, str(LOOP_STATE), "--state-dir", str(state_dir), "get", "mode"], text=True).strip()
            self.assertEqual(before, "auto")
            self.assertEqual(advanced, "1")
            self.assertEqual(after, "auto")

    def test_once_wake_arm_claim_is_live_only_not_simulated(self):
        text = COMMAND.read_text(encoding="utf-8")
        self.assertIn("wake-arm half is prompt-level/live-only", text)
        self.assertNotIn("--once-smoke", text)
        self.assertNotIn("scheduled_wakeup", text)


if __name__ == "__main__":
    unittest.main()
