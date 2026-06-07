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
LOW_CODE_OUTCOME='''# Outcome
```yaml
acceptance:
  - id: CFG
    severity: P1
    statement: use locked crate dependency and reject malformed config safely
  - id: INIT
    severity: P2
    statement: init writes files
```
'''
BASIC_CODE_SECTIONS='''```yaml
spec_compliance_matrix:
  - acceptance_id: CFG
    status: pass
    severity_if_fail: P1
    spec_ref: docs/spec.md#config
    evidence_ref: tests/config.rs::locked_dependency_and_yaml_comments
  - acceptance_id: INIT
    status: pass
    severity_if_fail: P2
    spec_ref: docs/spec.md#init
    evidence_ref: tests/init.rs::init_smoke
```
```yaml
negative_regression_tests:
  - acceptance_id: CFG
    status: pass
    severity_if_fail: P1
    scenario: malformed secret-bearing YAML does not echo the secret and locked dependency is present
    evidence_ref: tests/config.rs::malformed_secret_yaml_is_redacted
```
```yaml
secret_leakage_audit:
  status: pass
  checked_surfaces: [debug, display, errors, logs]
  cleartext_secret_probe: pass
  evidence_ref: tests/config.rs::malformed_secret_yaml_is_redacted
```
```yaml
dependency_spec_review:
  - dependency: serde_yaml_bw
    status: pass
    severity_if_fail: P1
    spec_ref: docs/architecture/tech-stack.yaml
    evidence_ref: cargo tree -p symphony-config
```
'''
A1_CODE_SECTIONS='''```yaml
spec_compliance_matrix:
  - acceptance_id: A1
    status: pass
    severity_if_fail: P1
    spec_ref: docs/spec.md#a1
    evidence_ref: tests/a1.rs::covers_a1
```
```yaml
negative_regression_tests:
  - acceptance_id: A1
    status: pass
    severity_if_fail: P1
    scenario: malformed or stale input does not pass the A1 invariant
    evidence_ref: tests/a1.rs::rejects_stale_input
```
```yaml
secret_leakage_audit:
  status: pass
  checked_surfaces: [debug, display, errors, logs]
  cleartext_secret_probe: pass
  evidence_ref: tests/a1.rs::secrets_are_redacted
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
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
''' + A1_CODE_SECTIONS
WAIVER=COMPLETE.replace('{item: body.instance_id comparison, current_scope_implementable: true, evidence_ref: src/status.rs}','{item: body.instance_id comparison, current_scope_implementable: true, waiver: true, severity_if_fail: P1, reason: defer current-scope safety}')
LOW_CODE_COMPLETE='''# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: CFG, status: pass, severity: P1}
  - {id: INIT, status: pass, severity: P2}
```
''' + BASIC_CODE_SECTIONS
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

    def test_low_risk_code_requires_baseline_evidence_blocks(self):
        proc,p=self.run_lint('code','low',BASIC,LOW_CODE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('spec_compliance_matrix',errors)
        self.assertIn('negative_regression_tests',errors)
        self.assertIn('secret_leakage_audit',errors)
        self.assertIn('dependency_spec_review',errors)
        self.assertTrue(p['grade_lint']['code_baseline_gate'])
        self.assertFalse(p['grade_lint']['medium_high_code_gate'])

    def test_low_risk_code_prose_only_outcome_still_requires_baseline_blocks(self):
        proc,p=self.run_lint('code','low',BASIC,'# Outcome\n\nAcceptance: A1 must pass.\n')
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('code grade missing parseable spec_compliance_matrix block', errors)
        self.assertIn('spec_compliance_matrix missing outcome acceptance IDs: A1', errors)

    def test_low_risk_code_complete_baseline_passes(self):
        proc,p=self.run_lint('code','low',LOW_CODE_COMPLETE,LOW_CODE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_yaml_parser_accepts_colon_containing_scalar_lists(self):
        grade=LOW_CODE_COMPLETE.replace(
            'checked_surfaces: [debug, display, errors, logs]',
            'checked_surfaces:\n  - "Authorization: Bearer redaction"\n  - "Debug: no secret echo"\n  - logs'
        )
        proc,p=self.run_lint('code','low',grade,LOW_CODE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_low_risk_code_requires_p1_negative_test_coverage(self):
        grade=LOW_CODE_COMPLETE.replace('  - acceptance_id: CFG\n    status: pass\n    severity_if_fail: P1\n    scenario: malformed secret-bearing YAML does not echo the secret and locked dependency is present\n    evidence_ref: tests/config.rs::malformed_secret_yaml_is_redacted\n','')
        proc,p=self.run_lint('code','low',grade,LOW_CODE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('negative_regression_tests missing P0/P1 outcome acceptance IDs: CFG','\n'.join(p['grade_lint']['errors']))

    def test_missing_shaped_adversarial_acceptance_check_fails(self):
        grade=COMPLETE.replace('acceptance_id: ADV-TRUST, ', '')
        proc,p=self.run_lint(grade=grade); self.assertEqual(proc.returncode,1); self.assertIn('missing shaped adversarial_acceptance IDs','\n'.join(p['grade_lint']['errors']))

    def test_unverified_p1_adversarial_check_must_be_counted_and_blocks(self):
        grade=COMPLETE.replace('status: pass, severity_if_fail: P1', 'status: unverified, severity_if_fail: P1', 1).replace('p1_count: 0','p1_count: 1').replace('adversarial_p1_count: 0','adversarial_p1_count: 1')
        proc,p=self.run_lint(grade=grade); self.assertEqual(proc.returncode,1); self.assertIn('blocking: unverified/P1','\n'.join(p['grade_lint']['errors']))

    def test_blocking_acceptance_hint_cannot_make_current_validation_optional(self):
        outcome=OUTCOME.replace('inspect code and run fault probe', 'optional future follow-up; not reachable in current validation')
        proc,p=self.run_lint(grade=COMPLETE,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('verification_hint makes current validation optional', '\n'.join(p['grade_lint']['errors']))

    def test_deferred_claim_cannot_defer_current_p1_adversarial_acceptance_by_assertion(self):
        grade=COMPLETE.replace('deferred_claims:\n  - {item: header, deferred_to: B-002, current_scope_implementable: false, rationale: future}', 'deferred_claims:\n  - {item: ADV-TRUST is deferred by assertion, deferred_to: B-999, current_scope_implementable: false, rationale: future}')
        proc,p=self.run_lint(grade=grade)
        self.assertEqual(proc.returncode,1)
        self.assertIn('defers current P0/P1 adversarial acceptance without tracked waiver or scope_basis_ref', '\n'.join(p['grade_lint']['errors']))

    def test_deferred_current_adversarial_acceptance_allows_scope_basis_ref(self):
        grade=COMPLETE.replace('deferred_claims:\n  - {item: header, deferred_to: B-002, current_scope_implementable: false, rationale: future}', 'deferred_claims:\n  - {item: ADV-TRUST explicitly out of current task, deferred_to: B-999, current_scope_implementable: false, scope_basis_ref: docs/scope.md#non-goal}')
        proc,p=self.run_lint(grade=grade)
        self.assertEqual(proc.returncode,0,p)

    def test_adv_ifmatch_split_optional_concurrency_test_fails(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    concurrency_or_locking: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-IFMATCH-SPLIT
    severity: P1
    surface: [concurrency_or_locking]
    statement: Same-revision concurrent PATCH requests must produce one 2xx and one 409, preventing lost update.
    verification_hint: optional concurrency test may be deferred because this is not reachable now
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: ifmatch-split
    acceptance_id: ADV-IFMATCH-SPLIT
    status: pass
    severity_if_fail: P1
    surface: [concurrency_or_locking]
    evidence_ref: evidence/grade/http_status.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('verification_hint makes current validation optional', errors)
        self.assertIn('concurrency_or_locking check requires evidence_kind', errors)

    def test_concurrency_check_accepts_concurrency_test_evidence_kind(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    concurrency_or_locking: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-IFMATCH-SPLIT
    severity: P1
    surface: [concurrency_or_locking]
    statement: Same-revision concurrent PATCH requests must produce one 2xx and one 409, preventing lost update.
    verification_hint: run concurrent PATCH probe and verify one 2xx plus one 409
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: ifmatch-split
    acceptance_id: ADV-IFMATCH-SPLIT
    status: pass
    severity_if_fail: P1
    surface: [concurrency_or_locking]
    evidence_kind: concurrency_test
    evidence_ref: evidence/grade/ifmatch_concurrency.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
""" + A1_CODE_SECTIONS
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,0,p)

    def test_boundary_acceptance_requires_boundary_surface(self):
        outcome=OUTCOME.replace('statement: trust surface must be probed', 'statement: user text <=280 chars JSON boundary must not truncate non-ASCII')
        proc,p=self.run_lint(grade=COMPLETE,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('boundary/input risk must use string_boundary or input_validation_or_schema surface', '\n'.join(p['grade_lint']['errors']))

    def test_boundary_check_requires_boundary_evidence_kind(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    input_validation_or_schema: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-JSON-BOUNDARY
    severity: P1
    surface: [input_validation_or_schema]
    statement: malformed JSON and user text <=280 chars are rejected without truncation.
    verification_hint: run malformed JSON and non-ASCII boundary probes
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: json-boundary
    acceptance_id: ADV-JSON-BOUNDARY
    status: pass
    severity_if_fail: P1
    surface: [input_validation_or_schema]
    evidence_ref: evidence/grade/json_boundary.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('boundary/input check requires evidence_kind', '\n'.join(p['grade_lint']['errors']))

    def test_no_panic_audit_rejects_mere_grep(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    runtime_files: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-NO-PANIC
    severity: P1
    surface: [runtime_files]
    statement: no-panic path: parsing malformed runtime files must not panic through unwrap or expect.
    verification_hint: audit implicit panic paths and run malformed file probe
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: no-panic-grep
    acceptance_id: ADV-NO-PANIC
    status: pass
    severity_if_fail: P1
    surface: [runtime_files]
    evidence_kind: panic_audit
    audit_method: grep only
    evidence_ref: evidence/grade/grep_panic.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('panic/no-panic audit cannot be mere grep', '\n'.join(p['grade_lint']['errors']))

    def test_no_panic_audit_requires_panic_evidence_kind(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    runtime_files: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-NO-PANIC
    severity: P1
    surface: [runtime_files]
    statement: no-panic path: malformed runtime files must not panic through unwrap or expect.
    verification_hint: audit implicit panic paths and run malformed file probe
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: no-panic
    acceptance_id: ADV-NO-PANIC
    status: pass
    severity_if_fail: P1
    surface: [runtime_files]
    evidence_kind: malformed_input_test
    evidence_ref: evidence/grade/no_panic.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('panic/no-panic audit requires evidence_kind', '\n'.join(p['grade_lint']['errors']))


    def test_block_scalar_optional_hint_is_rejected(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    concurrency_or_locking: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-BLOCK-SCALAR
    severity: P1
    surface: [concurrency_or_locking]
    statement: Concurrent writes must not lose updates.
    verification_hint: >
      optional future follow-up; not reachable in current validation
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: block-scalar
    acceptance_id: ADV-BLOCK-SCALAR
    status: pass
    severity_if_fail: P1
    surface: [concurrency_or_locking]
    evidence_kind: concurrency_test
    evidence_ref: evidence/grade/concurrency.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('verification_hint makes current validation optional', '\n'.join(p['grade_lint']['errors']))

    def test_no_panic_audit_rejects_grep_only_in_evidence_ref(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    runtime_files: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-NO-PANIC-GREP-REF
    severity: P1
    surface: [runtime_files]
    statement: no-panic path: malformed runtime files must not panic through unwrap or expect.
    verification_hint: audit implicit panic paths and run malformed file probe
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: no-panic-grep-ref
    acceptance_id: ADV-NO-PANIC-GREP-REF
    status: pass
    severity_if_fail: P1
    surface: [runtime_files]
    evidence_kind: panic_audit
    evidence_ref: grep -R panic found no hits
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('panic/no-panic audit cannot be mere grep', '\n'.join(p['grade_lint']['errors']))



    def test_no_panic_audit_rejects_grep_only_in_summary(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    runtime_files: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-NO-PANIC-SUMMARY
    severity: P1
    surface: [runtime_files]
    statement: no-panic path: malformed runtime files must not panic through unwrap or expect.
    verification_hint: audit implicit panic paths and run malformed file probe
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: no-panic-summary
    acceptance_id: ADV-NO-PANIC-SUMMARY
    status: pass
    severity_if_fail: P1
    surface: [runtime_files]
    evidence_kind: panic_audit
    summary: grep -R panic found no hits
    evidence_ref: evidence/grade/no_panic.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('panic/no-panic audit cannot be mere grep', '\n'.join(p['grade_lint']['errors']))

if __name__=='__main__': unittest.main()
