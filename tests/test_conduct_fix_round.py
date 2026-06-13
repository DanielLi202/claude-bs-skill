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
goal = None
final_status = os.environ.get('FAKE_FINAL_GOAL_STATUS', 'complete')
def emit(obj):
    print(json.dumps(obj), flush=True)
def marker_from(text):
    prefix_v2 = 'BS_OUTCOME_READ_V2 '
    idx = text.find(prefix_v2)
    if idx >= 0:
        payload, _ = json.JSONDecoder().raw_decode(text[idx + len(prefix_v2):].lstrip())
        return prefix_v2 + json.dumps(payload, sort_keys=True, separators=(',', ':'))
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
            with open(record, 'w') as f:
                f.write(json.dumps(req.get('params', {}).get('input')))
        emit({'jsonrpc':'2.0','id':req['id'],'result':{'turn':{'id':'turn-1'}}})
        time.sleep(0.05)
        paths = [p for p in os.environ.get('FAKE_WRITE_PATHS', 'workspace-write.txt').split(os.pathsep) if p]
        content = os.environ.get('FAKE_WRITE_CONTENT', 'done')
        for path in paths:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)
        emit({'method':'item/completed','params':{'item':{'type':'agentMessage','phase':'final_answer','text':marker_from(text) + ' Done'}}})
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

GRADE_WITH_PRODUCTION_LOCUS = textwrap.dedent('''
# Grade
Blocking P1 root cause is localized to production code `crates/symphony-evolve/src/git_write.rs`;
the prior fix edited a helper-only test setup instead.

```yaml
grade_summary:
  p0_count: 0
  p1_count: 1
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B021-GIT-WRITE
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

    def run_conduct(self, root: Path, cycle: Path, outcome: Path, fake_dir: Path, fix_round='1', extra_env=None):
        record = cycle / 'evidence' / 'fake_record.json'
        env = os.environ.copy()
        env.update({'PATH': f'{fake_dir}{os.pathsep}' + env.get('PATH', ''), 'FAKE_CODEX_RECORD': str(record)})
        if extra_env:
            env.update(extra_env)
        cmd = [str(CONDUCT), '--cycle-dir', str(cycle), '--outcome-file', str(outcome), '--evidence-dir', str(cycle / 'evidence'), '--fix-round', fix_round]
        proc = subprocess.run(cmd, cwd=root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return proc, record

    def reshape_with_production_locus(self, cycle: Path, outcome: Path):
        (cycle / 'grade_round_0.md').write_text(GRADE_WITH_PRODUCTION_LOCUS, encoding='utf-8')
        prep = subprocess.run(
            [sys.executable, str(HELPER), '--cycle-dir', str(cycle), '--outcome-file', str(outcome), '--grade-file', 'grade_round_0.md', '--round', '1'],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(prep.returncode, 0, prep.stderr)

    def write_fix_round_corrections(self, cycle: Path, outcome: Path):
        (cycle / 'outcome.v0.md').write_text('# Archived\n', encoding='utf-8')
        outcome.write_text(textwrap.dedent('''
            # Outcome

            ## Fix Round 1 (auto re-shape; bounded)
            Unmet acceptance: a1, a2
            Grade detail (reference, not inlined): grade_round_0.md
            Corrections:
            1. src/lib/store/outcomeStore.ts: add module-level `const EMPTY_RUN_STATE: OutcomeRunState = { execute: { status: "idle" }, assumptions: {} };`.
            2. src/shell/AppShell.tsx: complete inside AppShell via useMemo(completeShellClient) filling optionals with throwing "unavailable in test client" stubs.
            3. src/outcome/outcome.test.tsx: ADD missing outcome-secret-redaction describe and string "No fabricated stage\\nNo fixture text".
            4. src/test/node-globals.d.ts: add readdirSync/statSync (node:fs) + join (node:path).
            <!-- bs-fix-round: 1; archive=outcome.v0.md; grade=grade_round_0.md; failed=["a1","a2"] -->
        ''').lstrip(), encoding='utf-8')

    def commit_baseline(self, root: Path):
        subprocess.run(['git', 'add', '.'], cwd=root, check=True)
        subprocess.run(
            ['git', '-c', 'user.email=test@example.com', '-c', 'user.name=Test User', 'commit', '-q', '-m', 'baseline'],
            cwd=root,
            check=True,
        )

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

    def test_fix_round_refuses_incomplete_html_marker_without_failed_list(self):
        root, cycle, outcome, fake_dir = self.setup_repo()
        (cycle / 'outcome.v0.md').write_text('# Archived\n', encoding='utf-8')
        outcome.write_text(
            '# Outcome\n\n<!-- bs-fix-round: 1; archive=outcome.v0.md; grade=grade_round_0.md; -->\n',
            encoding='utf-8',
        )
        proc, record = self.run_conduct(root, cycle, outcome, fake_dir)
        self.assertEqual(proc.returncode, 5, proc.stdout + proc.stderr)
        self.assertIn('reshape_missing', proc.stdout)
        self.assertFalse(record.exists())

    def test_fix_round_refuses_unclosed_html_marker(self):
        root, cycle, outcome, fake_dir = self.setup_repo()
        (cycle / 'outcome.v0.md').write_text('# Archived\n', encoding='utf-8')
        outcome.write_text(
            '# Outcome\n\n<!-- bs-fix-round: 1; archive=outcome.v0.md; grade=grade_round_0.md; failed=[]\n',
            encoding='utf-8',
        )
        proc, record = self.run_conduct(root, cycle, outcome, fake_dir)
        self.assertEqual(proc.returncode, 5, proc.stdout + proc.stderr)
        self.assertIn('reshape_missing', proc.stdout)
        self.assertFalse(record.exists())

    def test_fix_round_accepts_full_html_marker_with_whitespace(self):
        root, cycle, outcome, fake_dir = self.setup_repo()
        (cycle / 'outcome.v0.md').write_text('# Archived\n', encoding='utf-8')
        outcome.write_text(
            '# Outcome\n\n<!--   bs-fix-round:   1;   archive=outcome.v0.md;   grade=grade_round_0.md;   failed=[]   -->\n',
            encoding='utf-8',
        )
        proc, record = self.run_conduct(root, cycle, outcome, fake_dir)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(record.exists())

    def test_fix_round_launches_after_helper_reshape_with_one_goal_and_round_evidence(self):
        root, cycle, outcome, fake_dir = self.setup_repo()
        prep = subprocess.run([sys.executable, str(HELPER), '--cycle-dir', str(cycle), '--outcome-file', str(outcome), '--grade-file', 'grade_round_0.md', '--round', '1'], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(prep.returncode, 0, prep.stderr)
        proc, record = self.run_conduct(root, cycle, outcome, fake_dir)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        recorded = json.loads(record.read_text(encoding='utf-8'))
        self.assertEqual(len(recorded), 1)
        self.assertNotIn('/goal @', recorded[0]['text'])
        self.assertIn('BS_OUTCOME_READ', recorded[0]['text'])
        self.assertIn('outcome.md', recorded[0]['text'])
        self.assertTrue((cycle / 'evidence' / 'conduct_round_1' / 'rpc_requests.jsonl').exists())

    def test_fix_round_misaligned_helper_only_diff_is_rejected(self):
        root, cycle, outcome, fake_dir = self.setup_repo()
        self.reshape_with_production_locus(cycle, outcome)
        proc, _record = self.run_conduct(
            root,
            cycle,
            outcome,
            fake_dir,
            extra_env={'FAKE_WRITE_PATHS': 'crates/symphony-evolve/src/lib.rs'},
        )
        self.assertEqual(proc.returncode, 9, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(result['conduct_result'], 'fix_round_misaligned')
        self.assertEqual(result['required_production_loci'], ['crates/symphony-evolve/src/git_write.rs'])
        self.assertIn('crates/symphony-evolve/src/lib.rs', result['changed_files'])

    def test_fix_round_aligned_production_locus_diff_stays_green(self):
        root, cycle, outcome, fake_dir = self.setup_repo()
        self.reshape_with_production_locus(cycle, outcome)
        proc, _record = self.run_conduct(
            root,
            cycle,
            outcome,
            fake_dir,
            extra_env={'FAKE_WRITE_PATHS': 'crates/symphony-evolve/src/git_write.rs'},
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(result['conduct_result'], 'completed')
        self.assertEqual(result['fix_round_alignment'], 'aligned')

    def test_fix_round_zero_uptake_gate_rejects_changed_files_without_correction_tokens(self):
        root, cycle, outcome, fake_dir = self.setup_repo()
        self.write_fix_round_corrections(cycle, outcome)
        self.commit_baseline(root)
        proc, _record = self.run_conduct(root, cycle, outcome, fake_dir)
        self.assertEqual(proc.returncode, 10, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(result['conduct_result'], 'fix_round_zero_uptake')
        self.assertEqual(result['matched_markers'], [])
        self.assertIn('EMPTY_RUN_STATE', result['required_markers'])
        self.assertIn('completeShellClient', result['required_markers'])
        self.assertIn('outcome-secret-redaction', result['required_markers'])
        self.assertIn('node-globals.d.ts', result['required_markers'])
        self.assertIn('workspace-write.txt', result['changed_files'])
        self.assertGreaterEqual(result['corrections_start_line'], 1)

    def test_fix_round_partial_uptake_passes_zero_uptake_gate(self):
        root, cycle, outcome, fake_dir = self.setup_repo()
        self.write_fix_round_corrections(cycle, outcome)
        self.commit_baseline(root)
        proc, _record = self.run_conduct(
            root,
            cycle,
            outcome,
            fake_dir,
            extra_env={'FAKE_WRITE_CONTENT': 'const EMPTY_RUN_STATE = {}'},
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(result['conduct_result'], 'completed')

    def test_fix_round_alignment_gate_runs_on_rc6_delta(self):
        root, cycle, outcome, fake_dir = self.setup_repo()
        self.write_fix_round_corrections(cycle, outcome)
        (cycle / 'fix_round_1_alignment.yaml').write_text(textwrap.dedent('''
            round: 1
            failed_ids: [a1]
            prior_blocking_count: 1
            required_production_loci:
              - crates/symphony-evolve/src/git_write.rs
            alt_justification: false
        '''), encoding='utf-8')
        self.commit_baseline(root)
        proc, _record = self.run_conduct(
            root,
            cycle,
            outcome,
            fake_dir,
            extra_env={
                'FAKE_FINAL_GOAL_STATUS': 'usageLimited',
                'FAKE_WRITE_PATHS': 'crates/symphony-evolve/src/lib.rs',
                'FAKE_WRITE_CONTENT': 'const EMPTY_RUN_STATE = {}',
            },
        )
        self.assertEqual(proc.returncode, 9, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(result['conduct_result'], 'fix_round_misaligned')
        self.assertIn('crates/symphony-evolve/src/lib.rs', result['changed_files'])


if __name__ == '__main__':
    unittest.main()
