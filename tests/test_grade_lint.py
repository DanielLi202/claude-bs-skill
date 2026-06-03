from pathlib import Path
import json, subprocess, sys, tempfile, textwrap, unittest
LINTER=Path(__file__).resolve().parents[1]/'runtime'/'grade_lint.py'
BASIC='''# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
'''
OUTCOME='''# Outcome
```yaml
risk_surface:
  surfaces:
    process: {present: true}
    runtime_files: {present: true}
    identity_sentinel: {present: true}
    network_probe: {present: true}
    background_process: {present: true}
    file_modes: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-TRUST
    severity: P1
    surface: [process, runtime_files, identity_sentinel, network_probe, background_process, file_modes]
    statement: trust surface must be probed
    verification_hint: inspect code and run fault probe
```
'''
COMPLETE='''# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - {id: stale-pid-wrong-process, acceptance_id: ADV-TRUST, status: pass, severity_if_fail: P1, surface: [process], evidence_ref: evidence/grade/stale_pid_probe.log}
```
```yaml
trust_surface_inventory:
  runtime_files: []
  identity_sentinels: []
  network_probes: []
  background_processes: []
  unverified_items: []
```
```yaml
deferred_claims:
  - {item: header, deferred_to: B-002, current_scope_implementable: false, rationale: future}
  - {item: body.instance_id comparison, current_scope_implementable: true, evidence_ref: src/status.rs}
```
'''
WAIVER=COMPLETE.replace('{item: body.instance_id comparison, current_scope_implementable: true, evidence_ref: src/status.rs}','{item: body.instance_id comparison, current_scope_implementable: true, waiver: true, severity_if_fail: P1, reason: defer current-scope safety}')
class GradeLintTests(unittest.TestCase):
    def run_lint(self,task_type='code',risk_level='medium',grade=BASIC,outcome=OUTCOME):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); gf=root/'grade.md'; of=root/'outcome.md'; ef=root/'evidence'/'grade_lint_round_0.json'
            gf.write_text(textwrap.dedent(grade)); of.write_text(textwrap.dedent(outcome))
            proc=subprocess.run([sys.executable,str(LINTER),'--task-type',task_type,'--risk-level',risk_level,'--grade-file',str(gf),'--outcome-file',str(of),'--evidence-file',str(ef)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertTrue(proc.stdout, proc.stderr)
            self.assertTrue(ef.exists())
            return proc,json.loads(proc.stdout)
    def test_old_cycle009_happy_path_only_medium_code_fails(self):
        proc,p=self.run_lint(); self.assertEqual(proc.returncode,1); e='\n'.join(p['grade_lint']['errors']); self.assertIn('adversarial_checks',e); self.assertIn('trust_surface_inventory',e); self.assertIn('deferred_claims',e)
    def test_low_risk_docs_basic_grade_passes_without_adversarial_blocks(self):
        proc,p=self.run_lint('docs','low',BASIC,'# Outcome\n'); self.assertEqual(proc.returncode,0,p); self.assertFalse(p['grade_lint']['medium_high_code_gate'])
    def test_complete_adversarial_medium_code_grade_passes(self):
        proc,p=self.run_lint(grade=COMPLETE); self.assertEqual(proc.returncode,0,p)
    def test_current_scope_blocking_waiver_without_tracked_ref_fails(self):
        proc,p=self.run_lint(grade=WAIVER); self.assertEqual(proc.returncode,1); self.assertIn('tracked maintainer/user waiver ref','\n'.join(p['grade_lint']['errors']))

    def test_missing_shaped_adversarial_acceptance_check_fails(self):
        grade=COMPLETE.replace('acceptance_id: ADV-TRUST, ', '')
        proc,p=self.run_lint(grade=grade); self.assertEqual(proc.returncode,1); self.assertIn('missing shaped adversarial_acceptance IDs','\n'.join(p['grade_lint']['errors']))

    def test_unverified_p1_adversarial_check_must_be_counted_and_blocks(self):
        grade=COMPLETE.replace('status: pass, severity_if_fail: P1', 'status: unverified, severity_if_fail: P1', 1).replace('p1_count: 0','p1_count: 1').replace('adversarial_p1_count: 0','adversarial_p1_count: 1')
        proc,p=self.run_lint(grade=grade); self.assertEqual(proc.returncode,1); self.assertIn('blocking: unverified/P1','\n'.join(p['grade_lint']['errors']))
if __name__=='__main__': unittest.main()
