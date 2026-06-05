from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

CONDUCT = Path(__file__).resolve().parents[1] / 'runtime' / 'conduct.sh'

FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, sys, time
if len(sys.argv) >= 3 and sys.argv[1:3] == ['login', 'status']:
    sys.exit(0)
if len(sys.argv) < 2 or sys.argv[1] != 'app-server':
    sys.exit(64)
goal = None
real_home = os.environ.get('REAL_CODEX_HOME_FOR_TEST')
full_no_work = os.environ.get('FAKE_FULL_NO_WORK') == '1' and os.environ.get('CODEX_HOME') == real_home

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
    if method == 'initialize':
        emit({'jsonrpc':'2.0','id':req['id'],'result':{}})
    elif method == 'thread/start':
        emit({'jsonrpc':'2.0','id':req['id'],'result':{'thread':{'id':'thread-1'}}})
    elif method == 'thread/goal/get':
        if goal is None:
            emit({'jsonrpc':'2.0','id':req['id'],'result':{}})
        else:
            emit({'jsonrpc':'2.0','id':req['id'],'result':{'goal':{'objective':goal['objective'],'status':'complete' if req['id'] == 800001 else 'active'}}})
    elif method == 'thread/goal/set':
        goal = {'objective':req.get('params', {}).get('objective'), 'status':req.get('params', {}).get('status')}
        emit({'jsonrpc':'2.0','id':req['id'],'result':{'goal':goal}})
    elif method in ('thread/goal/clear', 'thread/archive'):
        emit({'jsonrpc':'2.0','id':req['id'],'result':{}})
    elif method == 'turn/start':
        text = req.get('params', {}).get('input', [{}])[0].get('text', '')
        emit({'jsonrpc':'2.0','id':req['id'],'result':{'turn':{'id':'turn-1'}}})
        if full_no_work:
            while True:
                emit({'method':'mcpServer/startupStatus/updated','params':{'serverName':'alpha'}})
                time.sleep(0.05)
        marker = marker_from(text)
        if marker:
            emit({'method':'item/agentMessage/delta','params':{'itemId':'msg-1','delta':marker}})
        open('workspace-write.txt', 'w').write('done')
        emit({'method':'item/started','params':{'item':{'type':'command'}}})
        time.sleep(0.05)
        emit({'method':'item/completed','params':{'item':{'type':'agentMessage','phase':'final_answer','text':'Done'}}})
        emit({'jsonrpc':'2.0','method':'turn/completed','params':{'turn':{'status':'completed'}}})
    else:
        emit({'jsonrpc':'2.0','id':req.get('id'),'result':{}})
'''


class ConductPolicyTests(unittest.TestCase):
    def make_repo(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        subprocess.run(['git', 'init'], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
        (root / 'cycle').mkdir()
        (root / 'evidence').mkdir()
        fake_dir = root / 'bin'; fake_dir.mkdir()
        fake = fake_dir / 'codex'
        fake.write_text(FAKE_CODEX, encoding='utf-8')
        fake.chmod(0o755)
        real_home = root / 'real-codex-home'; real_home.mkdir()
        (real_home / 'auth.json').write_text('{"ok":true}\n', encoding='utf-8')
        (real_home / 'config.toml').write_text(textwrap.dedent('''
            [mcp_servers.alpha]
            command = "alpha"

            [mcp_servers.beta]
            command = "beta"
        ''').strip() + '\n', encoding='utf-8')
        env = os.environ.copy()
        env.update({
            'PATH': str(fake_dir) + os.pathsep + env.get('PATH', ''),
            'CODEX_HOME': str(real_home),
            'REAL_CODEX_HOME_FOR_TEST': str(real_home),
        })
        return root, env, real_home

    def run_conduct(self, extra_args=None, extra_env=None, timeout=15):
        root, env, real_home = self.make_repo()
        if extra_env:
            env.update(extra_env)
        cmd = [str(CONDUCT), '--cycle-dir', str(root / 'cycle'), '--outcome-file', str(root / 'outcome.md'), '--evidence-dir', str(root / 'evidence')]
        if extra_args:
            cmd.extend(extra_args)
        proc = subprocess.run(cmd, cwd=root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        env_dir = root / 'evidence' / 'conduct_round_0'
        payload = json.loads((env_dir / 'codex_env.json').read_text()) if (env_dir / 'codex_env.json').exists() else None
        return proc, payload, real_home, root

    def test_source_exposes_policy_flags(self):
        text = CONDUCT.read_text(encoding='utf-8')
        self.assertIn('--mcp-policy', text)
        self.assertIn('--mcp-allow', text)
        self.assertIn('--first-work-item-stale-sec', text)
        self.assertIn('--on-no-work-items', text)
        self.assertIn('result="no_work_items"', text)

    def test_default_clean_builds_auth_only_home_with_zero_mcp_servers(self):
        proc, payload, real_home, _root = self.run_conduct()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(payload['clean_codex_home'])
        self.assertEqual(payload['mcp_policy'], 'clean')
        self.assertEqual(payload['config_mcp_servers'], [])
        self.assertEqual(payload['suppressed_mcp_servers'], ['alpha', 'beta'])
        self.assertNotEqual(Path(payload['codex_home']), real_home.resolve())

    def test_allowlist_keeps_only_declared_existing_servers(self):
        proc, payload, _real_home, _root = self.run_conduct(['--mcp-policy', 'allowlist', '--mcp-allow', 'alpha,missing'])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(payload['clean_codex_home'])
        self.assertEqual(payload['mcp_policy'], 'allowlist')
        self.assertEqual(payload['config_mcp_servers'], ['alpha'])
        self.assertEqual(payload['suppressed_mcp_servers'], ['beta'])

    def test_full_inherits_real_home_unchanged(self):
        proc, payload, real_home, _root = self.run_conduct(['--mcp-policy', 'full'])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(payload['clean_codex_home'])
        self.assertEqual(Path(payload['codex_home']), real_home.resolve())
        self.assertEqual(payload['config_mcp_servers'], ['alpha', 'beta'])

    def test_full_exit_7_retries_once_under_clean(self):
        proc, payload, real_home, root = self.run_conduct(['--mcp-policy', 'full', '--first-work-item-stale-sec', '1', '--first-work-item-terminate-sec', '2', '--on-no-work-items', 'terminate'], extra_env={'FAKE_FULL_NO_WORK': '1'}, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(payload['clean_codex_home'])
        self.assertEqual(payload['mcp_policy'], 'clean')
        self.assertNotEqual(Path(payload['codex_home']), real_home.resolve())
        before = json.loads((root / 'evidence' / 'conduct_round_0' / 'codex_env.before_clean_retry.json').read_text())
        self.assertFalse(before['clean_codex_home'])
        self.assertEqual(before['mcp_policy'], 'full')
        self.assertEqual(Path(before['codex_home']), real_home.resolve())


if __name__ == '__main__':
    unittest.main()
