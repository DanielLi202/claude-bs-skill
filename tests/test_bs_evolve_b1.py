from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "harness" / "evolve-loop" / "bin" / "evolve-lock.py"
GUARD = ROOT / "harness" / "evolve-loop" / "bin" / "loop-guard.sh"
COMMAND = ROOT / "commands" / "bs-evolve.md"


def run(cmd, *, check=False):
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def payload(proc: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(proc.stdout)


class BsEvolveB1LockTests(unittest.TestCase):
    def test_generated_owner_tokens_are_cli_safe_hex(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "RUNNING.lock"
            proc = run(["python3", str(LOCK), "acquire", "--lock-file", str(lock)], check=True)
            tok = payload(proc)["token"]
            self.assertRegex(tok, r"^[0-9a-f]{48}$")
            self.assertFalse(tok.startswith("-"))

    def test_same_project_empty_lock_concurrency_starts_exactly_one_stage(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "target" / ".bs-evolve"
            state.mkdir(parents=True)

            def acquire(i: int):
                return run(["bash", str(GUARD), "acquire", str(state)])

            with ThreadPoolExecutor(max_workers=2) as ex:
                results = list(ex.map(acquire, [1, 2]))
            acquired = [p for p in results if p.returncode == 0]
            locked = [p for p in results if p.returncode == 11]
            self.assertEqual(len(acquired), 1, [p.stdout + p.stderr for p in results])
            self.assertEqual(len(locked), 1, [p.stdout + p.stderr for p in results])
            tok = payload(acquired[0])["token"]
            self.assertTrue((state / "RUNNING.lock").exists())
            self.assertEqual(payload(locked[0])["status"], "locked")
            self.assertEqual(run(["bash", str(GUARD), "release", str(state), "wrong-token"]).returncode, 12)
            self.assertTrue((state / "RUNNING.lock").exists(), "wrong token must not release another owner")
            self.assertEqual(run(["bash", str(GUARD), "release", str(state), tok]).returncode, 0)
            self.assertFalse((state / "RUNNING.lock").exists())

    def test_stale_running_lock_with_inflight_record_stays_locked(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "target" / ".bs-evolve"
            inflight = state / "inflight"
            inflight.mkdir(parents=True)
            first = run(["bash", str(GUARD), "acquire", str(state)], check=True)
            lock = state / "RUNNING.lock"
            (inflight / "r2.json").write_text(json.dumps({"stage": "r2", "pgid": 99999999}), encoding="utf-8")
            old = time.time() - 10
            os.utime(lock, (old, old))
            proc = run(["python3", str(LOCK), "acquire", "--lock-file", str(lock), "--inflight-dir", str(inflight), "--stale-sec", "1"])
            self.assertEqual(proc.returncode, 11, proc.stdout + proc.stderr)
            self.assertEqual(payload(proc)["reason"], "stale_with_inflight")
            self.assertEqual(json.loads(lock.read_text())["owner_token"], payload(first)["token"])

    def test_owner_heartbeat_renews_and_compare_release_protects_token(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "target" / ".bs-evolve"
            state.mkdir(parents=True)
            lock = state / "RUNNING.lock"
            first = run(["python3", str(LOCK), "acquire", "--lock-file", str(lock)], check=True)
            tok = payload(first)["token"]
            before = lock.stat().st_mtime
            time.sleep(0.02)
            hb = run(["python3", str(LOCK), "heartbeat", "--lock-file", str(lock), "--token", tok])
            self.assertEqual(hb.returncode, 0, hb.stdout + hb.stderr)
            self.assertGreaterEqual(lock.stat().st_mtime, before)
            self.assertEqual(run(["python3", str(LOCK), "heartbeat", "--lock-file", str(lock), "--token", "bad"]).returncode, 12)
            self.assertTrue(lock.exists())
            self.assertEqual(run(["python3", str(LOCK), "release", "--lock-file", str(lock), "--token", tok]).returncode, 0)
            self.assertFalse(lock.exists())

    def test_stale_takeover_makes_old_token_unable_to_touch_successor_lock(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "target" / ".bs-evolve"
            state.mkdir(parents=True)
            lock = state / "RUNNING.lock"
            first = run(["python3", str(LOCK), "acquire", "--lock-file", str(lock)], check=True)
            old_token = payload(first)["token"]
            old = time.time() - 10
            os.utime(lock, (old, old))
            second = run(["python3", str(LOCK), "acquire", "--lock-file", str(lock), "--stale-sec", "1"], check=True)
            new_token = payload(second)["token"]
            self.assertNotEqual(old_token, new_token)
            self.assertEqual(run(["python3", str(LOCK), "heartbeat", "--lock-file", str(lock), "--token", old_token]).returncode, 12)
            self.assertEqual(json.loads(lock.read_text())["owner_token"], new_token)
            self.assertEqual(run(["python3", str(LOCK), "release", "--lock-file", str(lock), "--token", old_token]).returncode, 12)
            self.assertTrue(lock.exists())
            self.assertEqual(json.loads(lock.read_text())["owner_token"], new_token)
            self.assertEqual(run(["python3", str(LOCK), "release", "--lock-file", str(lock), "--token", new_token]).returncode, 0)

    def test_lock_helper_serializes_revalidation_under_guard_flock(self):
        text = LOCK.read_text(encoding="utf-8")
        self.assertIn("fcntl.flock", text)
        self.assertIn("with lock_guard(path):", text)
        self.assertLess(text.index("def acquire"), text.index("def token_matches"))

    def test_skill_lock_uses_same_atomic_token_contract(self):
        with tempfile.TemporaryDirectory() as td:
            skill_state = Path(td) / "skill" / ".bs-evolve"
            skill_state.mkdir(parents=True)
            lock = skill_state / "SKILL.lock"

            def acquire(i: int):
                return run(["python3", str(LOCK), "acquire", "--lock-file", str(lock), "--owner", f"project-{i}"])

            with ThreadPoolExecutor(max_workers=2) as ex:
                results = list(ex.map(acquire, [1, 2]))
            self.assertEqual(len([p for p in results if p.returncode == 0]), 1, [p.stdout + p.stderr for p in results])
            self.assertEqual(len([p for p in results if p.returncode == 11]), 1, [p.stdout + p.stderr for p in results])

    def test_command_documents_tokened_running_and_skill_locks(self):
        text = COMMAND.read_text(encoding="utf-8")
        self.assertIn("prints JSON containing `token`", text)
        self.assertIn("loop-guard.sh heartbeat", text)
        self.assertIn("$BS_LOOP_SKILL_REPO/.bs-evolve/SKILL.lock", text)
        self.assertIn("compare-token semantics", text)
        self.assertIn('loop-guard.sh" release "$BS_LOOP_STATE_DIR" "$RUNNING_LOCK_TOKEN"', text)


if __name__ == "__main__":
    unittest.main()
