from pathlib import Path
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

DRIVER = Path(__file__).resolve().parents[1] / 'runtime' / 'codex_driver.py'
spec = importlib.util.spec_from_file_location('codex_driver', DRIVER)
codex_driver = importlib.util.module_from_spec(spec)
sys.modules['codex_driver'] = codex_driver
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

    def test_goal_objective_header_is_json_parseable_for_paths_with_spaces(self):
        path = Path('/tmp/path with spaces/outcome.md')
        objective = codex_driver.build_goal_objective(path, 'a' * 64, 'cycle-013')
        parsed = codex_driver.parse_goal_header(objective)
        self.assertEqual(parsed['run_id'], 'cycle-013')
        self.assertEqual(parsed['outcome_sha256'], 'a' * 64)
        self.assertEqual(parsed['outcome_path'], str(path))
        self.assertLessEqual(len(objective), 4000)

    def test_status_normalization_preserves_vendor_semantics(self):
        self.assertEqual(codex_driver.normalize_goal_status('usageLimited'), 'usage_limited')
        self.assertEqual(codex_driver.normalize_goal_status('budgetLimited'), 'budget_limited')
        self.assertEqual(codex_driver.normalize_goal_status('complete'), 'complete')
        self.assertEqual(codex_driver.normalize_goal_status('weird'), 'unknown')

    def test_driver_defaults_include_required_flags(self):
        source = DRIVER.read_text(encoding='utf-8')
        self.assertIn('--idle-timeout-sec', source)
        self.assertIn('deprecated hard idle kill', source)
        self.assertIn('turn_silent_soft_limit', source)
        self.assertIn('turn_semantic_failed', source)
        self.assertIn('--expected-effect-kind', source)
        self.assertIn('--on-wall-clock-limit', source)
        self.assertIn('--first-work-item-stale-sec', source)
        self.assertIn('--first-work-item-terminate-sec', source)
        self.assertIn('--on-no-work-items', source)
        self.assertIn('turn_no_work_items_stale', source)
        self.assertNotIn('exec --json', source)

    def test_codex_bin_env_requires_test_gate(self):
        ns = type('Args', (), {'codex_bin': None})()
        with mock.patch.dict(os.environ, {'CODEX_BIN': '/tmp/fake'}, clear=True):
            self.assertEqual(codex_driver.resolve_codex_bin(ns), 'codex')
        with mock.patch.dict(os.environ, {'CODEX_BIN': '/tmp/fake', 'BS_TEST_FAKE_CODEX': '1'}, clear=True):
            self.assertEqual(codex_driver.resolve_codex_bin(ns), '/tmp/fake')

    def test_snapshot_delta_ignores_dirty_tree_at_start(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence = root / 'evidence'; evidence.mkdir()
            dirty = root / 'dirty.txt'; dirty.write_text('already dirty', encoding='utf-8')
            obs = codex_driver.TurnObservation(root, evidence)
            obs.start(); obs.finish()
            self.assertEqual(obs.workspace_delta_files, [])
            dirty.write_text('changed now', encoding='utf-8')
            obs.finish()
            self.assertEqual(obs.workspace_delta_files, ['dirty.txt'])

    def test_text_delta_does_not_disarm_first_work_item_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence = root / 'evidence'; evidence.mkdir()
            obs = codex_driver.TurnObservation(root, evidence)
            codex_driver.observe_event({'method': 'item/agentMessage/delta', 'params': {'itemId': 'a', 'delta': 'BS_OUTCOME_READ {}'}}, obs)
            self.assertIsNone(obs.first_work_item_at)
            self.assertEqual(len(obs.outcome_read_markers), 1)

    def test_real_work_item_disarms_first_work_item_gate_and_counts_churn(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence = root / 'evidence'; evidence.mkdir()
            obs = codex_driver.TurnObservation(root, evidence)
            codex_driver.observe_event({'method': 'mcpServer/startupStatus/updated', 'params': {'serverName': 'alpha'}}, obs)
            codex_driver.observe_event({'method': 'skills/changed', 'params': {'skillName': 'beta'}}, obs)
            codex_driver.observe_event({'method': 'item/started', 'params': {'item': {'type': 'fileChange'}}}, obs)
            self.assertIsNotNone(obs.first_work_item_at)
            self.assertEqual(obs.file_change_events, 1)
            self.assertEqual(obs.mcp_events_seen, 1)
            self.assertEqual(obs.skill_events_seen, 1)
            self.assertEqual(obs.observed_mcp_servers, {'alpha'})
            self.assertEqual(obs.observed_skills, {'beta'})

    def test_evidence_delta_ignores_preexisting_and_driver_logs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence = root / 'evidence'; evidence.mkdir()
            (evidence / 'preexisting.log').write_text('old', encoding='utf-8')
            (evidence / 'raw_vendor_output.jsonl').write_text('driver log start', encoding='utf-8')
            obs = codex_driver.TurnObservation(root, evidence)
            obs.start()
            (evidence / 'raw_vendor_output.jsonl').write_text('driver log changed', encoding='utf-8')
            obs.finish()
            self.assertEqual(obs.evidence_delta_files, [])
            (evidence / 'grade_verify_round_0.yaml').write_text('status: pass', encoding='utf-8')
            obs.finish()
            self.assertEqual(obs.evidence_delta_files, ['grade_verify_round_0.yaml'])

    def test_goal_objective_forbids_broad_filesystem_scans(self):
        objective = codex_driver.build_goal_objective(Path('/tmp/cycle/outcome.md'), 'a' * 64, 'cycle-015')
        low = objective.lower()
        self.assertIn('never run broad filesystem searches', low)
        self.assertIn('$home', low)
        self.assertIn('package manager/registry', low)
        # The integrity header must still parse and the cap must hold.
        self.assertIsNotNone(codex_driver.parse_goal_header(objective))
        self.assertLessEqual(len(objective), 4000)

    def test_driver_spawns_app_server_in_own_process_group(self):
        source = DRIVER.read_text(encoding='utf-8')
        self.assertIn('start_new_session=(os.name == "posix")', source)
        self.assertIn('_stash_pgid(proc)', source)
        self.assertIn('os.killpg', source)
        self.assertIn('"version": "1.4.14"', source)
        self.assertIn('--terminal-candidate-idle-sec', source)
        self.assertIn('--on-terminal-candidate', source)

    def test_kill_proc_reaps_orphaned_grandchild_via_process_group(self):
        # Reproduces the cycle-015 shape: a leader spawns a long-lived grandchild
        # then the leader exits, orphaning the grandchild. The driver must still
        # reap the grandchild via the stashed process group.
        script = (
            "import os, sys, subprocess, time\n"
            "p = subprocess.Popen(['sleep', '120'])\n"
            "open(sys.argv[1], 'w').write(str(p.pid))\n"
            "sys.exit(0)\n"
        )
        with tempfile.TemporaryDirectory() as td:
            pidfile = Path(td) / 'gc.pid'
            proc = subprocess.Popen([sys.executable, '-c', script, str(pidfile)], start_new_session=True)
            codex_driver._stash_pgid(proc)
            proc.wait(timeout=5)  # leader exits; grandchild is now orphaned
            gc_pid = None
            for _ in range(50):
                if pidfile.exists() and pidfile.read_text().strip():
                    gc_pid = int(pidfile.read_text().strip())
                    break
                time.sleep(0.1)
            self.assertIsNotNone(gc_pid, 'grandchild pid was never written')

            def _safe_kill():
                try:
                    os.kill(gc_pid, signal.SIGKILL)
                except OSError:
                    pass
            self.addCleanup(_safe_kill)
            os.kill(gc_pid, 0)  # alive before reaping (raises if not)
            codex_driver.kill_proc(proc)
            reaped = False
            for _ in range(50):
                try:
                    os.kill(gc_pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    reaped = True
                    break
            self.assertTrue(reaped, 'orphaned grandchild survived process-group reaping')

    def test_signal_handler_invokes_cleanup_before_exit(self):
        meta = io.StringIO()
        proc = object()
        codex_driver.ACTIVE_CLEANUP.clear()
        codex_driver.ACTIVE_CLEANUP.update({'proc': proc, 'raw': io.StringIO(), 'rpc': io.StringIO(), 'err': io.StringIO(), 'meta': meta, 'thread_id': 'thread-1'})
        with mock.patch.object(codex_driver, 'cleanup_thread') as cleanup, mock.patch.object(codex_driver, 'kill_proc') as kill:
            with self.assertRaises(SystemExit) as raised:
                codex_driver._signal_handler(signal.SIGTERM, None)
        self.assertEqual(raised.exception.code, 2)
        cleanup.assert_called_once()
        kill.assert_called_once_with(proc)
        self.assertIn('signal_received', meta.getvalue())
        codex_driver.ACTIVE_CLEANUP.clear()


FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, subprocess, sys, time
mode = os.environ.get('FAKE_CODEX_MODE', 'ok')
if len(sys.argv) < 2 or sys.argv[1] != 'app-server':
    sys.exit(64)
if mode == 'exit':
    sys.exit(99)
record = os.environ.get('FAKE_CODEX_RECORD')
goal = None
final_status = os.environ.get('FAKE_FINAL_GOAL_STATUS', 'complete')
emit_marker = os.environ.get('FAKE_EMIT_MARKER', '1') == '1'

def emit(obj):
    print(json.dumps(obj), flush=True)

def marker_from(text):
    prefix = 'BS_OUTCOME_READ '
    idx = text.find(prefix)
    if idx < 0:
        return ''
    payload, _ = json.JSONDecoder().raw_decode(text[idx + len(prefix):].lstrip())
    return prefix + json.dumps(payload, sort_keys=True, separators=(',', ':'))

for line in sys.stdin:
    req = json.loads(line)
    method = req.get('method')
    if mode == 'fatal' and method == 'initialize':
        emit({'jsonrpc':'2.0','id':req['id'],'error':{'code':-32602,'message':'validation error'}})
        continue
    if method == 'initialize':
        emit({'jsonrpc':'2.0','id':req['id'],'result':{}})
    elif method == 'thread/start':
        if req.get('params', {}).get('ephemeral') is not False:
            emit({'jsonrpc':'2.0','id':req['id'],'error':{'code':-32600,'message':'ephemeral must be false'}})
        else:
            emit({'jsonrpc':'2.0','id':req['id'],'result':{'thread':{'id':'thread-1'}}})
    elif method == 'thread/goal/get':
        if goal is None:
            emit({'jsonrpc':'2.0','id':req['id'],'result':{}})
        else:
            status = final_status if req['id'] == 800001 else goal.get('status', 'active')
            emit({'jsonrpc':'2.0','id':req['id'],'result':{'goal':{'objective':goal['objective'],'status':status}}})
    elif method == 'thread/goal/set':
        goal = {'objective':req.get('params', {}).get('objective'), 'status':req.get('params', {}).get('status')}
        emit({'jsonrpc':'2.0','id':req['id'],'result':{'goal':goal}})
    elif method in ('thread/goal/clear', 'thread/archive'):
        emit({'jsonrpc':'2.0','id':req['id'],'result':{}})
    elif method == 'turn/start':
        text = req.get('params', {}).get('input', [{}])[0].get('text', '')
        if record:
            open(record, 'w').write(json.dumps({'input': req.get('params', {}).get('input'), 'text': text}))
        emit({'jsonrpc':'2.0','id':req['id'],'result':{'turn':{'id':'turn-1'}}})
        marker = marker_from(text) if emit_marker else ''
        if mode == 'stderr_noise':
            end = time.time() + 1.4
            while time.time() < end:
                print('token refresh noise', file=sys.stderr, flush=True)
                time.sleep(0.05)
            open('workspace-write.txt', 'w').write('done')
            emit({'method':'item/completed','params':{'item':{'type':'agentMessage','phase':'final_answer','text':marker + ' Done'}}})
            emit({'jsonrpc':'2.0','method':'turn/completed','params':{'turn':{'status':'completed'}}})
        elif mode == 'blocked':
            time.sleep(0.1)
            emit({'method':'item/completed','params':{'item':{'type':'agentMessage','phase':'final_answer','text':marker + ' Blocked: true required tools are unavailable'}}})
        elif mode == 'immediate':
            open('workspace-write.txt', 'w').write('done')
            if marker:
                emit({'method':'item/completed','params':{'item':{'type':'agentMessage','phase':'final_answer','text':marker + ' Done'}}})
            emit({'jsonrpc':'2.0','method':'turn/completed','params':{'turn':{'status':'completed'}}})
        elif mode == 'mcp_churn':
            while True:
                emit({'method':'mcpServer/startupStatus/updated','params':{'serverName':'alpha'}})
                emit({'method':'skills/changed','params':{'skillName':'beta'}})
                time.sleep(0.05)
        elif mode == 'text_delta_only':
            if marker:
                emit({'method':'item/agentMessage/delta','params':{'itemId':'msg-1','delta':marker}})
            while True:
                emit({'method':'mcpServer/startupStatus/updated','params':{'serverName':'alpha'}})
                time.sleep(0.05)
        elif mode == 'real_work_then_wait':
            emit({'method':'item/started','params':{'item':{'type':'command'}}})
            while True:
                emit({'method':'mcpServer/startupStatus/updated','params':{'serverName':'alpha'}})
                time.sleep(0.05)
        elif mode == 'no_output':
            while True:
                time.sleep(1)
        elif mode == 'delta_then_idle':
            if marker:
                emit({'method':'item/agentMessage/delta','params':{'itemId':'msg-1','delta':marker}})
            emit({'method':'item/started','params':{'item':{'type':'fileChange'}}})
            # Write the workspace delta AFTER the driver's turn-start snapshot so it
            # registers as an in-turn delta, then go silent (post-delta deadlock).
            time.sleep(0.6)
            open('workspace-write.txt', 'w').write('done')
            while True:
                time.sleep(1)
        elif mode == 'grandchild_then_complete':
            gc = subprocess.Popen(['sleep', '120'])
            open('grandchild.pid', 'w').write(str(gc.pid))
            open('workspace-write.txt', 'w').write('done')
            if marker:
                emit({'method':'item/completed','params':{'item':{'type':'agentMessage','phase':'final_answer','text':marker + ' Done'}}})
            emit({'jsonrpc':'2.0','method':'turn/completed','params':{'turn':{'status':'completed'}}})
        else:
            time.sleep(0.1)
            open('workspace-write.txt', 'w').write('done')
            if marker:
                emit({'method':'item/completed','params':{'item':{'type':'agentMessage','phase':'final_answer','text':marker + ' Done'}}})
            emit({'jsonrpc':'2.0','method':'turn/completed','params':{'turn':{'status':'completed'}}})
    else:
        emit({'jsonrpc':'2.0','id':req.get('id'),'result':{}})
'''


class CodexDriverIntegrationTests(unittest.TestCase):
    def run_driver(self, mode: str, extra_args=None, timeout=10, extra_env=None):
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
            if extra_env:
                env.update(extra_env)
            cmd = [sys.executable, str(DRIVER), '--cwd', str(root), '--outcome-file', str(outcome), '--evidence-dir', str(evidence), '--launch-retries', '2', '--launch-backoff', '0', '--handshake-timeout-sec', '3', '--silent-soft-limit-sec', '1', '--stale-notice-sec', '2', '--progress-report-sec', '1', '--inferred-completion-sec', '1']
            if extra_args:
                cmd.extend(extra_args)
            proc = subprocess.run(cmd, cwd=str(root), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            events_path = evidence / 'driver_events.jsonl'
            events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()] if events_path.exists() else []
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
        self.assertEqual(rc, 0, _stderr)
        self.assertIn('launch_ok', [e['event'] for e in events])
        self.assertNotIn('/goal @', record)
        self.assertIn('BS_OUTCOME_READ', record)
        self.assertIn('BS_GOAL_V1', _requests)
        self.assertIn('\"ephemeral\": false', _requests)
        self.assertIn('thread/goal/set', _requests)
        self.assertIn('thread/goal/get', _requests)
        self.assertIn('thread/archive', _requests)
        self.assertIn('outcome.md', record)
        self.assertNotIn('Conduct via', record)

    def test_immediate_completion_uses_goal_oracle_even_if_turn_signal_races(self):
        rc, events, _requests, record, _stderr = self.run_driver('immediate', timeout=5)
        self.assertEqual(rc, 0, _stderr)
        self.assertIn('BS_OUTCOME_READ', record)
        self.assertIn('goal_status_final', [e['event'] for e in events])
        self.assertEqual([e for e in events if e['event'] == 'goal_status_final'][-1]['goal_status'], 'complete')

    def test_blocked_final_answer_returns_semantic_failed(self):
        rc, events, _requests, _record, _stderr = self.run_driver('blocked')
        self.assertEqual(rc, 0)
        semantic = [e for e in events if e['event'] == 'turn_semantic_observation']
        self.assertEqual(semantic[-1]['reason_code'], 'semantic_blocked_final_answer')

    def test_expected_effect_none_allows_complete_goal_with_refusal_observation(self):
        rc, events, _requests, _record, _stderr = self.run_driver('blocked', extra_args=['--expected-effect-kind', 'none'])
        self.assertEqual(rc, 0)
        self.assertEqual([e for e in events if e['event'] == 'turn_semantic_observation'][-1]['reason_code'], 'semantic_blocked_final_answer')

    def test_final_goal_non_success_returns_nonzero_with_raw_status(self):
        rc, events, _requests, _record, _stderr = self.run_driver('ok', extra_env={'FAKE_FINAL_GOAL_STATUS': 'usageLimited'})
        self.assertEqual(rc, 6)
        final = [e for e in events if e['event'] == 'goal_status_final'][-1]
        self.assertEqual(final['goal_status'], 'usage_limited')
        self.assertEqual(final['raw_goal_status'], 'usageLimited')
        self.assertIn('cleanup_goal_clear', [e['event'] for e in events])
        self.assertIn('cleanup_thread_archive', [e['event'] for e in events])

    def test_missing_outcome_read_marker_fails_even_when_goal_complete(self):
        rc, events, _requests, _record, _stderr = self.run_driver('ok', extra_env={'FAKE_EMIT_MARKER': '0'})
        self.assertEqual(rc, 6)
        self.assertIn('outcome_read_marker_missing_or_mismatch', [e['event'] for e in events])
        self.assertIn('cleanup_goal_clear', [e['event'] for e in events])
        self.assertIn('cleanup_thread_archive', [e['event'] for e in events])

    def test_stderr_noise_does_not_keep_or_kill_idle_turn(self):
        rc, events, _requests, _record, _stderr = self.run_driver('stderr_noise')
        self.assertEqual(rc, 0, _stderr)
        names = [e['event'] for e in events]
        self.assertIn('turn_silent_soft_limit', names)
        self.assertNotIn('turn_idle_timeout', names)

    def test_wall_clock_fail_policy_is_explicit_opt_in(self):
        rc, events, _requests, _record, _stderr = self.run_driver('no_output', extra_args=['--wall-clock-limit-sec', '1', '--on-wall-clock-limit', 'fail'], timeout=5)
        self.assertEqual(rc, 2)
        self.assertIn('turn_wall_clock_limit', [e['event'] for e in events])

    def test_legacy_timeout_sec_does_not_kill_by_default(self):
        rc, events, _requests, _record, _stderr = self.run_driver('stderr_noise', extra_args=['--timeout-sec', '1'])
        self.assertEqual(rc, 0, _stderr)
        self.assertNotIn('turn_total_timeout', [e['event'] for e in events])

    def test_no_work_items_stale_then_terminate_exit_7(self):
        rc, events, _requests, _record, _stderr = self.run_driver('mcp_churn', extra_args=['--first-work-item-stale-sec', '1', '--first-work-item-terminate-sec', '2', '--on-no-work-items', 'terminate'], timeout=6)
        self.assertEqual(rc, 7, _stderr)
        names = [e['event'] for e in events]
        self.assertIn('turn_no_work_items_stale', names)
        self.assertIn('turn_no_work_items_terminated', names)
        stale = [e for e in events if e['event'] == 'turn_no_work_items_stale'][-1]
        self.assertGreater(stale['mcp_events_seen'], 0)
        self.assertGreater(stale['skill_events_seen'], 0)

    def test_text_delta_marker_does_not_disarm_no_work_gate(self):
        rc, events, _requests, _record, _stderr = self.run_driver('text_delta_only', extra_args=['--first-work-item-stale-sec', '1', '--first-work-item-terminate-sec', '2', '--on-no-work-items', 'terminate'], timeout=6)
        self.assertEqual(rc, 7, _stderr)
        self.assertIn('turn_no_work_items_stale', [e['event'] for e in events])

    def test_real_work_item_disarms_no_work_gate(self):
        rc, events, _requests, _record, _stderr = self.run_driver('real_work_then_wait', extra_args=['--first-work-item-stale-sec', '1', '--first-work-item-terminate-sec', '2', '--on-no-work-items', 'terminate', '--wall-clock-limit-sec', '3', '--on-wall-clock-limit', 'fail'], timeout=7)
        self.assertEqual(rc, 2, _stderr)
        names = [e['event'] for e in events]
        self.assertNotIn('turn_no_work_items_stale', names)
        self.assertIn('turn_wall_clock_limit', names)

    def test_terminal_candidate_terminate_returns_exit_8_with_delta(self):
        rc, events, _requests, _record, _stderr = self.run_driver(
            'delta_then_idle',
            extra_args=['--terminal-candidate-idle-sec', '1', '--on-terminal-candidate', 'terminate'],
            timeout=10,
        )
        self.assertEqual(rc, 8, _stderr)
        cand = [e for e in events if e['event'] == 'turn_terminal_candidate']
        self.assertTrue(cand, 'expected a turn_terminal_candidate event')
        self.assertEqual(cand[-1]['reason_code'], 'post_delta_idle')
        self.assertIn('workspace-write.txt', cand[-1]['workspace_delta_files'])
        self.assertIn('turn_terminal_candidate_terminated', [e['event'] for e in events])

    def test_terminal_candidate_observe_does_not_terminate(self):
        # observe mode emits the decision-point telemetry but keeps waiting
        # (silence is not failure); the turn ends here only via opt-in wall clock.
        rc, events, _requests, _record, _stderr = self.run_driver(
            'delta_then_idle',
            extra_args=['--terminal-candidate-idle-sec', '1', '--on-terminal-candidate', 'observe', '--wall-clock-limit-sec', '4', '--on-wall-clock-limit', 'fail'],
            timeout=10,
        )
        self.assertEqual(rc, 2, _stderr)
        names = [e['event'] for e in events]
        self.assertIn('turn_terminal_candidate', names)
        self.assertNotIn('turn_terminal_candidate_terminated', names)
        self.assertIn('turn_wall_clock_limit', names)

    def test_no_terminal_candidate_when_idle_threshold_unset(self):
        # default (disabled) keeps prior behavior: no terminal-candidate events
        rc, events, _requests, _record, _stderr = self.run_driver('ok')
        self.assertEqual(rc, 0, _stderr)
        self.assertNotIn('turn_terminal_candidate', [e['event'] for e in events])

    def test_turn_completion_reaps_grandchild_process_group(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = root / 'fake_codex.py'
            fake.write_text(FAKE_CODEX, encoding='utf-8')
            fake.chmod(0o755)
            outcome = root / 'outcome.md'; outcome.write_text('# Outcome\n', encoding='utf-8')
            evidence = root / 'evidence'
            env = os.environ.copy()
            env.update({'BS_TEST_FAKE_CODEX': '1', 'CODEX_BIN': str(fake), 'FAKE_CODEX_MODE': 'grandchild_then_complete'})
            proc = subprocess.run([sys.executable, str(DRIVER), '--cwd', str(root), '--outcome-file', str(outcome), '--evidence-dir', str(evidence), '--launch-backoff', '0', '--inferred-completion-sec', '1'], cwd=str(root), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            gc_pid = int((root / 'grandchild.pid').read_text().strip())

            def _safe_kill():
                try:
                    os.kill(gc_pid, signal.SIGKILL)
                except OSError:
                    pass
            self.addCleanup(_safe_kill)
            reaped = False
            for _ in range(50):
                try:
                    os.kill(gc_pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    reaped = True
                    break
            self.assertTrue(reaped, 'grandchild survived driver exit-path reaping')

    def test_codex_env_snapshot_is_written(self):
        rc, events, _requests, _record, _stderr = self.run_driver('ok', extra_args=['--mcp-policy', 'clean', '--clean-codex-home'])
        self.assertEqual(rc, 0, _stderr)
        # Re-run in a bespoke temp dir so we can inspect the generated evidence path.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = root / 'fake_codex.py'
            fake.write_text(FAKE_CODEX, encoding='utf-8')
            fake.chmod(0o755)
            outcome = root / 'outcome.md'; outcome.write_text('# Outcome\n', encoding='utf-8')
            evidence = root / 'evidence'
            env = os.environ.copy()
            env.update({'BS_TEST_FAKE_CODEX': '1', 'CODEX_BIN': str(fake), 'FAKE_CODEX_MODE': 'ok'})
            proc = subprocess.run([sys.executable, str(DRIVER), '--cwd', str(root), '--outcome-file', str(outcome), '--evidence-dir', str(evidence), '--launch-backoff', '0', '--mcp-policy', 'clean', '--clean-codex-home'], cwd=str(root), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads((evidence / 'codex_env.json').read_text())
            self.assertTrue(payload['clean_codex_home'])
            self.assertEqual(payload['mcp_policy'], 'clean')


if __name__ == '__main__':
    unittest.main()
