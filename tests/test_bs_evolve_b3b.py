from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEDUP = ROOT / "harness" / "evolve-loop" / "bin" / "skill-release-dedup.py"
CLOSURE = ROOT / "harness" / "evolve-loop" / "bin" / "closure.py"
COMMAND = ROOT / "commands" / "bs-evolve.md"


def run(cmd, check=True):
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def init_closure(base: Path) -> Path:
    d = base / "reviews" / "cycle-001"
    run([sys.executable, str(CLOSURE), "--dir", str(d), "init", "--cycle", "cycle-001"])
    run([sys.executable, str(CLOSURE), "--dir", str(d), "set", "r1", "done"])
    run([sys.executable, str(CLOSURE), "--dir", str(d), "set", "r2", "done"])
    return d / "closure.yaml"


class BsEvolveB3bTests(unittest.TestCase):
    def test_partial_coverage_only_implements_uncovered_item_and_records_covered(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            closure = init_closure(base)
            items = base / "items.yaml"
            items.write_text(yaml.safe_dump([{"id": "R2-A"}, {"id": "R2-B"}]), encoding="utf-8")
            covered = base / "covered.txt"
            covered.write_text("R2-A\n", encoding="utf-8")
            proc = run([sys.executable, str(DEDUP), "plan", "--closure", str(closure), "--items", str(items), "--covered-upstream", str(covered), "--write"])
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["implement"], ["R2-B"])
            c = yaml.safe_load(closure.read_text(encoding="utf-8"))
            self.assertEqual(c["covered_upstream"], ["R2-A"])
            self.assertIsNone(c["skill_release"], "partial coverage must not write no-op sentinel while work remains")

    def test_self_recovery_skips_items_already_done_before_kill(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            closure = init_closure(base)
            items = base / "items.yaml"
            items.write_text(yaml.safe_dump([{"id": "R2-A"}, {"id": "R2-B"}]), encoding="utf-8")
            run([sys.executable, str(DEDUP), "mark-done", "--closure", str(closure), "--item-id", "R2-A", "--commit", "abc123"])
            proc = run([sys.executable, str(DEDUP), "plan", "--closure", str(closure), "--items", str(items), "--write"])
            payload = json.loads(proc.stdout)
            statuses = {row["id"]: row["status"] for row in payload["items"]}
            self.assertEqual(statuses["R2-A"], "already_done")
            self.assertEqual(payload["implement"], ["R2-B"])
            c = yaml.safe_load(closure.read_text(encoding="utf-8"))
            self.assertEqual(c["skill_release_items_done"]["R2-A"]["commit"], "abc123")

    def assert_noop_advances(self, items_payload, covered_payload, expected_reason: str):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            closure = init_closure(base)
            items = base / "items.yaml"
            items.write_text(yaml.safe_dump(items_payload), encoding="utf-8")
            cmd = [sys.executable, str(DEDUP), "plan", "--closure", str(closure), "--items", str(items), "--write"]
            if covered_payload is not None:
                covered = base / "covered.yaml"
                covered.write_text(yaml.safe_dump(covered_payload), encoding="utf-8")
                cmd.extend(["--covered-upstream", str(covered)])
            proc = run(cmd)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["implement"], [])
            c = yaml.safe_load(closure.read_text(encoding="utf-8"))
            self.assertEqual(c["skill_release"]["status"], "no_release")
            self.assertEqual(c["skill_release"]["reason"], expected_reason)
            nxt = run([sys.executable, str(CLOSURE), "--dir", str(closure.parent), "next"])
            self.assertEqual(nxt.stdout.strip(), "remediation")

    def test_noop_all_covered_writes_non_empty_sentinel(self):
        self.assert_noop_advances([{"id": "R2-A"}], ["R2-A"], "all_covered_upstream")

    def test_noop_needs_human_writes_non_empty_sentinel(self):
        self.assert_noop_advances([{"id": "R2-A", "needs_human": True}], None, "all_needs_human_or_done")

    def test_noop_no_deterministic_items_writes_non_empty_sentinel(self):
        self.assert_noop_advances([], None, "no_deterministic_items")

    def test_command_documents_b3b_lock_dedup_and_noop_sentinel(self):
        text = COMMAND.read_text(encoding="utf-8")
        self.assertIn("skill-release-dedup.py", text)
        self.assertIn("covered_upstream", text)
        self.assertIn("skill_release_items_done", text)
        self.assertIn("status: no_release", text)
        self.assertIn("closure.py next", text)


if __name__ == "__main__":
    unittest.main()
