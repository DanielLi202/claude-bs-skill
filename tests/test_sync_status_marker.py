from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / "runtime" / "sync_status_marker.py"


def task(tid, status, blocked_by=None, closed_in=None, title=None):
    blocked = "[" + ", ".join(blocked_by or []) + "]"
    title_str = title or (tid + " task")
    closed_in_val = '"' + closed_in + '"' if closed_in else "null"
    closed_at_val = '"2026-01-01T00:00:00Z"' if closed_in else "null"
    lines = [
        "  - id: " + tid,
        '    title: "' + title_str + '"',
        "    type: docs",
        "    risk_level: low",
        "    status: " + status,
        "    blocked_by: " + blocked,
        '    spec_refs: ["docs/x.md"]',
        "    closed_in: " + closed_in_val,
        "    closed_at: " + closed_at_val,
        "    escalation_reason: null",
        "    parked_reason: null",
    ]
    return "\n".join(lines)


def write_repo(td, tasks_yaml, agents_text, status_marker_block):
    root = Path(td)
    (root / ".bootstrap").mkdir(parents=True, exist_ok=True)
    (root / ".bootstrap" / "backlog.yaml").write_text("schema_version: 1\ntasks:\n" + tasks_yaml + "\n", encoding="utf-8")
    (root / "AGENTS.md").write_text(agents_text, encoding="utf-8")
    binding = "schema_version: 1\nbacklog: .bootstrap/backlog.yaml\n" + status_marker_block
    (root / ".bootstrap.yaml").write_text(binding, encoding="utf-8")
    return root


def run(root):
    proc = subprocess.run(
        [sys.executable, str(HELPER), "--binding-file", str(root / ".bootstrap.yaml"), "--repo-root", str(root)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    out = json.loads(proc.stdout)["status_marker"] if proc.stdout.strip() else {}
    return proc.returncode, out


SM = (
    "status_marker:\n"
    "  file: AGENTS.md\n"
    '  next_task_marker: "§1-next-bs-task"\n'
)

SM_GUARD = (
    "status_marker:\n"
    "  file: AGENTS.md\n"
    '  next_task_marker: "§1-next-bs-task"\n'
    "  stale_id_guard:\n"
    "    enabled: true\n"
    '    start: "<!-- status:start -->"\n'
    '    end: "<!-- status:end -->"\n'
)


class SyncStatusMarkerTests(unittest.TestCase):
    def test_marker_advances_to_next_pending_unblocked(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = task("B-001", "completed", closed_in="cycle-001") + "\n" + task("B-002", "pending", blocked_by=["B-001"])
            root = write_repo(td, tasks, "next: <!-- §1-next-bs-task: B-001 -->\n", SM)
            rc, out = run(root)
            self.assertEqual(rc, 0)
            self.assertEqual(out["next"], "B-002")
            self.assertTrue(out["changed"])
            self.assertIn("<!-- §1-next-bs-task: B-002 -->", (root / "AGENTS.md").read_text())

    def test_in_progress_task_wins(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = task("B-001", "completed", closed_in="cycle-001") + "\n" + task("B-002", "in_progress", blocked_by=["B-001"]) + "\n" + task("B-003", "pending", blocked_by=["B-001"])
            root = write_repo(td, tasks, "x <!-- §1-next-bs-task: B-001 --> y\n", SM)
            rc, out = run(root)
            self.assertEqual(rc, 0)
            self.assertEqual(out["next"], "B-002")  # in_progress wins over pending B-003

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = task("B-001", "completed", closed_in="cycle-001") + "\n" + task("B-002", "pending", blocked_by=["B-001"])
            root = write_repo(td, tasks, "<!-- §1-next-bs-task: B-002 -->\n", SM)
            rc, out = run(root)
            self.assertEqual(rc, 0)
            self.assertFalse(out["changed"])  # already correct -> no change

    def test_noop_when_unconfigured(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = task("B-001", "pending")
            root = write_repo(td, tasks, "<!-- §1-next-bs-task: B-001 -->\n", "")  # no status_marker block
            before = (root / "AGENTS.md").read_text()
            rc, out = run(root)
            self.assertEqual(rc, 0)
            self.assertFalse(out.get("configured", False))
            self.assertEqual((root / "AGENTS.md").read_text(), before)

    def test_next_task_line_rendered(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = task("B-001", "completed", closed_in="cycle-001") + "\n" + task("B-002", "pending", blocked_by=["B-001"], title="CLI thin client")
            sm = SM + (
                "  next_task_line:\n"
                '    start: "<!-- nt:start -->"\n'
                '    end: "<!-- nt:end -->"\n'
                '    template: "{id} — {title}"\n'
            )
            agents = "下一个：<!-- nt:start -->OLD<!-- nt:end --> <!-- §1-next-bs-task: B-001 -->\n"
            root = write_repo(td, tasks, agents, sm)
            rc, out = run(root)
            self.assertEqual(rc, 0)
            self.assertEqual(out["line_rewrites"], 1)
            self.assertIn("<!-- nt:start -->B-002 — CLI thin client<!-- nt:end -->", (root / "AGENTS.md").read_text())

    def test_stale_id_guard_blocks_old_dynamic_prose(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = task("B-001", "completed", closed_in="cycle-001") + "\n" + task("B-002", "pending", blocked_by=["B-001"])
            agents = "<!-- status:start -->\ncurrent: B-001\n<!-- §1-next-bs-task: B-001 -->\n<!-- status:end -->\n"
            root = write_repo(td, tasks, agents, SM_GUARD)
            rc, out = run(root)
            self.assertEqual(rc, 5)
            self.assertIn("B-001", out["error"])
            self.assertIn("<!-- §1-next-bs-task: B-001 -->", (root / "AGENTS.md").read_text())

    def test_stale_id_guard_passes_when_managed_line_rewrites_all_dynamic_text(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = task("B-001", "completed", closed_in="cycle-001") + "\n" + task("B-002", "pending", blocked_by=["B-001"], title="next")
            sm = SM_GUARD + (
                "  next_task_line:\n"
                '    start: "<!-- next:start -->"\n'
                '    end: "<!-- next:end -->"\n'
                '    template: "current: {id}"\n'
            )
            agents = "<!-- status:start -->\n<!-- next:start -->current: B-001<!-- next:end -->\n<!-- §1-next-bs-task: B-001 -->\n<!-- status:end -->\n"
            root = write_repo(td, tasks, agents, sm)
            rc, out = run(root)
            self.assertEqual(rc, 0, out)
            self.assertIn("current: B-002", (root / "AGENTS.md").read_text())

    def test_error_when_marker_absent(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = task("B-001", "pending")
            root = write_repo(td, tasks, "no marker here\n", SM)
            rc, out = run(root)
            self.assertEqual(rc, 3)
            self.assertEqual(out["status"], "error")

    def test_post_sync_command_runs(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = task("B-001", "completed", closed_in="cycle-001") + "\n" + task("B-002", "pending", blocked_by=["B-001"])
            sm = SM + '  post_sync_command: "touch post_sync_ran.flag"\n'
            root = write_repo(td, tasks, "<!-- §1-next-bs-task: B-001 -->\n", sm)
            rc, out = run(root)
            self.assertEqual(rc, 0)
            self.assertEqual(out["post_sync_exit"], 0)
            self.assertTrue((root / "post_sync_ran.flag").exists())


if __name__ == "__main__":
    unittest.main()
