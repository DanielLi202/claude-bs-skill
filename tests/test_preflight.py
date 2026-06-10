from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

PREFLIGHT = Path(__file__).resolve().parents[1] / 'runtime' / 'preflight.sh'

FAKE_CODEX = r'''#!/usr/bin/env python3
import json, sys

if len(sys.argv) >= 2 and sys.argv[1] == "--version":
    print("codex 0.133.0")
    sys.exit(0)
if len(sys.argv) >= 3 and sys.argv[1] == "login" and sys.argv[2] == "status":
    sys.exit(0)
if len(sys.argv) < 2 or sys.argv[1] != "app-server":
    sys.exit(64)

thread_id = "preflight-thread"
goal = None

def emit(obj):
    print(json.dumps(obj), flush=True)

for line in sys.stdin:
    req = json.loads(line)
    method = req.get("method")
    if method == "initialize":
        emit({"jsonrpc":"2.0","id":req["id"],"result":{}})
    elif method == "thread/start":
        params = req.get("params", {})
        if params.get("ephemeral") is not False:
            emit({"jsonrpc":"2.0","id":req["id"],"error":{"code":-32600,"message":"ephemeral must be false"}})
        else:
            emit({"jsonrpc":"2.0","id":req["id"],"result":{"thread":{"id":thread_id}}})
    elif method == "thread/goal/set":
        goal = {
            "objective": req.get("params", {}).get("objective", ""),
            "status": req.get("params", {}).get("status", "active"),
        }
        emit({"jsonrpc":"2.0","id":req["id"],"result":{"goal":goal}})
    elif method == "thread/goal/get":
        emit({"jsonrpc":"2.0","id":req["id"],"result":{"goal":goal or {}}})
    elif method in ("thread/goal/clear", "thread/archive"):
        emit({"jsonrpc":"2.0","id":req["id"],"result":{}})
    else:
        emit({"jsonrpc":"2.0","id":req.get("id"),"result":{}})
'''


class PreflightCouncilTests(unittest.TestCase):
    def make_bin(self, root: Path, name: str, body: str):
        path = root / name
        path.write_text(body, encoding='utf-8')
        path.chmod(0o755)
        return path

    def run_preflight(self, extra_args=None, with_codex=True, repo_root=None):
        with tempfile.TemporaryDirectory() as td:
            bindir = Path(td)
            if with_codex:
                self.make_bin(bindir, 'codex', FAKE_CODEX)
            self.make_bin(bindir, 'gh', '''#!/usr/bin/env bash
if [[ "$1" == "auth" && "$2" == "status" ]]; then exit 0; fi
exit 0
''')
            env = os.environ.copy()
            env['PATH'] = f'{bindir}{os.pathsep}/bin{os.pathsep}/usr/bin'
            cmd = ['bash', str(PREFLIGHT), '--skip-verify-preflight']
            if extra_args:
                cmd.extend(extra_args)
            return subprocess.run(
                cmd,
                cwd=str(repo_root) if repo_root is not None else None,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )

    def write_close_gap_fixture(self, root: Path, completed_close: bool = False):
        (root / '.bootstrap').mkdir()
        cycle_dir = root / '.prompts' / 'dogfood' / 'cycle-018'
        cycle_dir.mkdir(parents=True)
        (root / '.bootstrap.yaml').write_text(
            'schema_version: 1\n'
            'backlog: .bootstrap/backlog.yaml\n'
            'cycle_dir_root: .prompts/dogfood\n',
            encoding='utf-8',
        )
        (root / '.bootstrap' / 'backlog.yaml').write_text(
            'schema_version: 1\n'
            'tasks:\n'
            '  - id: B-018\n'
            '    status: in_progress\n',
            encoding='utf-8',
        )
        (cycle_dir / 'cycle.yaml').write_text(
            'cycle: cycle-018\n'
            'task_id: B-018\n',
            encoding='utf-8',
        )
        (cycle_dir / 'auto_merge_gate.yaml').write_text(
            'auto_merge_gate:\n'
            '  decision: merge\n'
            '  pr: 25\n',
            encoding='utf-8',
        )
        events = [
            {'step': 'step_7', 'attempt': 0, 'event': 'started', 'recorded_at': '2026-06-09T11:34:27Z'},
        ]
        if completed_close:
            events.extend([
                {'step': 'step_7', 'attempt': 0, 'event': 'completed', 'outcome': 'PR #25 auto-merged to main (squash 5017538)', 'recorded_at': '2026-06-10T02:19:38Z'},
                {'step': 'step_10', 'attempt': 0, 'event': 'started', 'recorded_at': '2026-06-10T02:19:38Z'},
                {'step': 'step_10', 'attempt': 0, 'event': 'completed', 'outcome': 'atomic close committed e6f9699', 'recorded_at': '2026-06-10T02:26:29Z'},
            ])
        (cycle_dir / 'step_events.jsonl').write_text(
            ''.join(json.dumps(event, sort_keys=True) + '\n' for event in events),
            encoding='utf-8',
        )

    def test_default_council_unavailable_is_warning_not_failure(self):
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('overall: pass', proc.stdout)
        self.assertIn('name: codex_goal_rpc_probe', proc.stdout)
        self.assertIn('cleanup=clear+archive', proc.stdout)
        self.assertIn('name: council_quorum', proc.stdout)
        self.assertIn('status: warn', proc.stdout)
        self.assertIn('required: false', proc.stdout)
        self.assertIn('required_by=none', proc.stdout)

    def test_require_council_unmet_fails(self):
        proc = self.run_preflight(['--require-council'])
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('name: council_quorum', proc.stdout)
        self.assertIn('status: fail', proc.stdout)
        self.assertIn('required_by=explicit_policy', proc.stdout)

    def test_codex_auth_remains_hard_required_when_council_optional(self):
        proc = self.run_preflight(with_codex=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('codex_binary', proc.stdout)
        self.assertIn('required: true', proc.stdout)

    def test_skip_council_is_warning_only(self):
        proc = self.run_preflight(['--skip-council'])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('council checks skipped', proc.stdout)
        self.assertIn('required: false', proc.stdout)

    def test_close_gap_probe_blocks_merge_decided_open_step_7(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_close_gap_fixture(root)
            proc = self.run_preflight(repo_root=root)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('overall: fail', proc.stdout)
        self.assertIn('name: close_gap_probe', proc.stdout)
        self.assertIn('recovery_required=merged_pr_needs_step10_close cycle=018 task=B-018', proc.stdout)
        self.assertNotIn('name: codex_binary', proc.stdout)

    def test_close_gap_probe_allows_completed_step_10(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_close_gap_fixture(root, completed_close=True)
            proc = self.run_preflight(repo_root=root)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('name: close_gap_probe', proc.stdout)
        self.assertIn('latest cycle cycle-018 has step_10 completed', proc.stdout)
        self.assertNotIn('recovery_required=merged_pr_needs_step10_close', proc.stdout)


if __name__ == '__main__':
    unittest.main()
