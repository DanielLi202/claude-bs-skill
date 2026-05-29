from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

DRIVER = Path(__file__).resolve().parents[1] / 'runtime' / 'codex_driver.py'
spec = importlib.util.spec_from_file_location('codex_driver', DRIVER)
codex_driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codex_driver)


class CodexDriverUnitTests(unittest.TestCase):
    def test_final_answer_signal_arms_inferred_completion(self):
        obj = {'method': 'item/completed', 'params': {'item': {'phase': 'final_answer', 'type': 'message', 'role': 'assistant'}}}
        self.assertEqual(codex_driver.detect_inferred_completion_signal(obj), 'item_completed_final_answer')

    def test_idle_signal_arms_inferred_completion(self):
        obj = {'method': 'thread/status/changed', 'params': {'status': 'idle'}}
        self.assertEqual(codex_driver.detect_inferred_completion_signal(obj), 'thread_status_idle')

    def test_object_status_signal_extracts_type(self):
        obj = {'method': 'thread/status/changed', 'params': {'status': {'type': 'idle', 'activeFlags': []}}}
        self.assertEqual(codex_driver.detect_inferred_completion_signal(obj), 'thread_status_idle')

    def test_goal_input_uses_file_reference_without_wrapper(self):
        self.assertEqual(codex_driver.build_goal_input(Path('/tmp/outcome.md')), '/goal @/tmp/outcome.md')

    def test_driver_defaults_include_required_flags(self):
        source = DRIVER.read_text(encoding='utf-8')
        self.assertIn('default=30', source)
        self.assertIn('default=5', source)
        self.assertIn('default=120', source)
        self.assertIn('--outcome-file', source)
        self.assertIn('--launch-retries', source)
        self.assertIn('--codex-bin', source)
        self.assertIn('turn_completed_inferred', source)
        self.assertIn('heartbeat', source)

    def test_codex_bin_env_requires_test_gate(self):
        ns = type('Args', (), {'codex_bin': None})()
        with mock.patch.dict(os.environ, {'CODEX_BIN': '/tmp/fake'}, clear=True):
            self.assertEqual(codex_driver.resolve_codex_bin(ns), 'codex')
        with mock.patch.dict(os.environ, {'CODEX_BIN': '/tmp/fake', 'BS_TEST_FAKE_CODEX': '1'}, clear=True):
            self.assertEqual(codex_driver.resolve_codex_bin(ns), '/tmp/fake')


FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, sys, time
mode = os.environ.get('FAKE_CODEX_MODE', 'ok')
if len(sys.argv) < 2 or sys.argv[1] != 'app-server':
    sys.exit(64)
if mode == 'exit':
    sys.exit(99)
record = os.environ.get('FAKE_CODEX_RECORD')

def emit(obj):
    print(json.dumps(obj), flush=True)

for line in sys.stdin:
    req = json.loads(line)
    method = req.get('method')
    if mode == 'fatal' and method == 'initialize':
        emit({'jsonrpc':'2.0','id':req['id'],'error':{'code':-32602,'message':'validation error'}})
        continue
    if method == 'initialize':
        emit({'jsonrpc':'2.0','id':req['id'],'result':{}})
    elif method == 'thread/start':
        emit({'jsonrpc':'2.0','id':req['id'],'result':{'thread':{'id':'thread-1'}}})
    elif method == 'turn/start':
        if record:
            open(record, 'w').write(json.dumps(req.get('params', {}).get('input')))
        emit({'jsonrpc':'2.0','id':req['id'],'result':{'turn':{'id':'turn-1'}}})
        if mode == 'stderr_noise':
            while True:
                print('token refresh noise', file=sys.stderr, flush=True)
                time.sleep(0.05)
        else:
            time.sleep(0.1)
            emit({'jsonrpc':'2.0','method':'turn/completed','params':{'turn':{'status':'completed'}}})
    else:
        emit({'jsonrpc':'2.0','id':req.get('id'),'result':{}})
'''


class CodexDriverIntegrationTests(unittest.TestCase):
    def run_driver(self, mode: str, extra_args=None):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = root / 'fake_codex.py'
            fake.write_text(FAKE_CODEX, encoding='utf-8')
            fake.chmod(0o755)
            outcome = root / 'outcome.md'
            outcome.write_text('# Outcome\n', encoding='utf-8')
            evidence = root / 'evidence'
            record = root / 'record.json'
            env = os.environ.copy()
            env.update({'BS_TEST_FAKE_CODEX': '1', 'CODEX_BIN': str(fake), 'FAKE_CODEX_MODE': mode, 'FAKE_CODEX_RECORD': str(record)})
            cmd = [sys.executable, str(DRIVER), '--cwd', str(root), '--outcome-file', str(outcome), '--evidence-dir', str(evidence), '--launch-retries', '2', '--launch-backoff', '0', '--handshake-timeout-sec', '3', '--idle-timeout-sec', '1', '--timeout-sec', '5']
            if extra_args:
                cmd.extend(extra_args)
            proc = subprocess.run(cmd, cwd=str(root), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            events = []
            events_path = evidence / 'driver_events.jsonl'
            if events_path.exists():
                events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
            requests = (evidence / 'rpc_requests.jsonl').read_text() if (evidence / 'rpc_requests.jsonl').exists() else ''
            record_text = record.read_text() if record.exists() else ''
            return proc.returncode, events, requests, record_text, proc.stderr

    def test_transient_launch_exit_retries_then_exit_3_without_exec(self):
        rc, events, requests, _record, _stderr = self.run_driver('exit')
        self.assertEqual(rc, 3)
        self.assertEqual([e['event'] for e in events if e['event'] == 'launch_attempt'], ['launch_attempt'] * 3)
        self.assertEqual(events[-1]['event'], 'launch_exhausted')
        self.assertNotIn('exec', requests)

    def test_handshake_json_rpc_error_is_fatal_no_retry(self):
        rc, events, _requests, _record, _stderr = self.run_driver('fatal')
        self.assertEqual(rc, 4)
        self.assertEqual(len([e for e in events if e['event'] == 'launch_attempt']), 1)
        self.assertEqual(events[-1]['event'], 'launch_fatal')

    def test_success_sends_goal_outcome_file(self):
        rc, events, _requests, record, _stderr = self.run_driver('ok')
        self.assertEqual(rc, 0)
        self.assertIn('launch_ok', [e['event'] for e in events])
        self.assertIn('/goal @', record)
        self.assertIn('outcome.md', record)
        self.assertNotIn('Conduct via', record)

    def test_stderr_noise_does_not_keep_idle_turn_alive(self):
        rc, events, _requests, _record, _stderr = self.run_driver('stderr_noise')
        self.assertEqual(rc, 2)
        self.assertIn('turn_idle_timeout', [e['event'] for e in events])


if __name__ == '__main__':
    unittest.main()
