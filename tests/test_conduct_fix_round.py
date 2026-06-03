from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

CONDUCT = Path(__file__).resolve().parents[1] / 'runtime' / 'conduct.sh'
HELPER = Path(__file__).resolve().parents[1] / 'runtime' / 'reshape_fix_round.py'

FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, sys, time
if sys.argv[1:3] == ['login', 'status']:
    sys.exit(0)
if len(sys.argv) < 2 or sys.argv[1] != 'app-server':
    sys.exit(64)
record = os.environ.get('FAKE_CODEX_RECORD')
def emit(obj):
    print(json.dumps(obj), flush=True)
for line in sys.stdin:
    req = json.loads(line)
    method = req.get('method')
    if method == 'initialize':
        emit({'jsonrpc':'2.0','id':req['id'],'result':{}})
    elif method == 'thread/start':
        emit({'jsonrpc':'2.0','id':req['id'],'result':{'thread':{'id':'thread-1'}}})
    elif method == 'turn/start':
        text = req.get('params', {}).get('input', [{}])[0].get('text', '')
        if record:
            with open(record, 'w') as f:
                f.write(json.dumps(req.get('params', {}).get('input')))
        emit({'jsonrpc':'2.0','id':req['id'],'result':{'turn':{'id':'turn-1'}}})
        time.sleep(0.05)
        open('workspace-write.txt', 'w').write('done')
        emit({'method':'item/completed','params':{'item':{'type':'agentMessage','phase':'final_answer','text':'Done'}}})
        emit({'jsonrpc':'2.0','method':'turn/completed','params':{'turn':{'status':'completed'}}})
    else:
        emit({'jsonrpc':'2.0','id':req.get('id'),'result':{}})
'''


GRADE = textwrap.dedent('''
# Grade
```yaml
grade_summary:
  p0_count: 0
  p1_count: 1
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B011-FORCED-RESHAPE-CONTROL
    status: fail
    severity: P1
```
''')


class ConductFixRoundTests(unittest.TestCase):
    def setup_repo(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
        fake_dir = root / 'bin'
        fake_dir.mkdir()
        fake = fake_dir / 'codex'
        fake.write_text(FAKE_CODEX, encoding='utf-8')
        fake.chmod(0o755)
        cycle = root / 'cycle'
        cycle.mkdir()
        outcome = cycle / 'outcome.md'
        outcome.write_text('# Outcome\n', encoding='utf-8')
        (cycle / 'grade_round_0.md').write_text(GRADE, encoding='utf-8')
        return root, cycle, outcome, fake_dir

    def run_conduct(self, root: Path, cycle: Path, outcome: Path, fake_dir: Path, fix_round='1'):
        record = root / 'record.json'
        env = os.environ.copy()
        env.update({'PATH': f'{fake_dir}{os.pathsep}' + env.get('PATH', ''), 'FAKE_CODEX_RECORD': str(record)})
        cmd = [str(CONDUCT), '--cycle-dir', str(cycle), '--outcome-file', str(outcome), '--evidence-dir', str(cycle / 'evidence'), '--fix-round', fix_round]
        proc = subprocess.run(cmd, cwd=root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return proc, record

    def test_fix_round_refuses_without_reshape(self):
        root, cycle, outcome, fake_dir = self.setup_repo()
        proc, record = self.run_conduct(root, cycle, outcome, fake_dir)
        self.assertEqual(proc.returncode, 5, proc.stdout + proc.stderr)
        self.assertIn('reshape_missing', proc.stdout)
        self.assertFalse(record.exists())

    def test_fix_round_refuses_prose_substring_without_html_marker(self):
        root, cycle, outcome, fake_dir = self.setup_repo()
        (cycle / 'outcome.v0.md').write_text('# Archived\n', encoding='utf-8')
        outcome.write_text('# Outcome\n\nprose says bs-fix-round: 1 but this is not the marker\n', encoding='utf-8')
        proc, record = self.run_conduct(root, cycle, outcome, fake_dir)
        self.assertEqual(proc.returncode, 5, proc.stdout + proc.stderr)
        self.assertIn('reshape_missing', proc.stdout)
        self.assertFalse(record.exists())

    def test_fix_round_launches_after_helper_reshape_with_one_goal_and_round_evidence(self):
        root, cycle, outcome, fake_dir = self.setup_repo()
        prep = subprocess.run([sys.executable, str(HELPER), '--cycle-dir', str(cycle), '--outcome-file', str(outcome), '--grade-file', 'grade_round_0.md', '--round', '1'], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(prep.returncode, 0, prep.stderr)
        proc, record = self.run_conduct(root, cycle, outcome, fake_dir)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        recorded = json.loads(record.read_text(encoding='utf-8'))
        self.assertEqual(len(recorded), 1)
        self.assertIn('/goal @', recorded[0]['text'])
        self.assertIn('outcome.md', recorded[0]['text'])
        self.assertTrue((cycle / 'evidence' / 'conduct_round_1' / 'rpc_requests.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
