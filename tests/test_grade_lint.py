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
AUTH_SECRET_CODE_OUTCOME='''# Outcome
```yaml
risk_surface:
  surfaces:
    auth_or_secret: {present: true}
```
```yaml
acceptance:
  - id: CFG
    severity: P1
    statement: auth token handling redacts secret values from evidence
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
  cleartext_secret_probe:
    status: pass
    shapes:
      - token=sk-secret-test
      - '{"api_key":"sk-secret-test"}'
      - "Authorization: Bearer sk-secret-test"
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
  cleartext_secret_probe:
    status: pass
    shapes:
      - token=sk-secret-test
      - '{"api_key":"sk-secret-test"}'
      - "Authorization: Bearer sk-secret-test"
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
CYCLE017_STYLE_OUTCOME='''---
title: "B-005 — Pattern Library reader + API endpoints"
type: code
risk_level: low
acceptance:
  - id: B005-PATH-SAFETY
    severity: P1
    statement: >
      skill_id is validated before any filesystem access. Any skill_id containing `..`, `/`,
      `\\`, or that is an absolute path is rejected so no read can traverse outside the
      pattern roots.
    verification_hint: >
      Test negative path traversal ids before reading from the filesystem.
---
# B-005
'''
CYCLE017_INSUFFICIENT_GRADE='''# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: B005-PATH-SAFETY, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B005-PATH-SAFETY
    status: pass
    severity_if_fail: P1
    spec_ref: docs/architecture/storage-layout.md
    evidence_ref: validate_skill_id + basic invalid id tests
```
```yaml
negative_regression_tests:
  - acceptance_id: B005-PATH-SAFETY
    status: pass
    severity_if_fail: P1
    scenario: skill_id with .., slash, backslash, absolute path, URL-encoded %2F/%5C is rejected
    evidence_ref: tests::rejects_dotdot_slash_backslash_absolute
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: path safety fixture does not touch secrets
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
CYCLE017_SUFFICIENT_GRADE=CYCLE017_INSUFFICIENT_GRADE.replace(
    'scenario: skill_id with .., slash, backslash, absolute path, URL-encoded %2F/%5C is rejected\n    evidence_ref: tests::rejects_dotdot_slash_backslash_absolute',
    'scenario: skill_id with .., slash, backslash, absolute path, URL-encoded %2F/%5C is rejected; symlinked skill directories cannot escape the root; canonicalized candidate paths must starts_with the canonical root\n    evidence_ref: tests::rejects_dotdot_slash_backslash_absolute + tests::rejects_symlink_escape_with_canonical_root_containment'
)
REQUEST_TARGET_OUTCOME='''---
title: "Raw HTTP detail path"
type: code
risk_level: low
acceptance:
  - id: CLIENT-REQUEST-TARGET
    severity: P1
    statement: >
      The client builds a raw HTTP/1.1 request target from a user-controlled path segment.
      It must percent-encode or reject request-target delimiters and control characters.
    verification_hint: >
      Test request target boundary ids.
---
# Request target
'''
REQUEST_TARGET_INSUFFICIENT_GRADE='''# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: CLIENT-REQUEST-TARGET, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: CLIENT-REQUEST-TARGET
    status: pass
    severity_if_fail: P1
    spec_ref: docs/api.md
    evidence_ref: tests::known_id_detail
```
```yaml
negative_regression_tests:
  - acceptance_id: CLIENT-REQUEST-TARGET
    status: pass
    severity_if_fail: P1
    scenario: unknown skill id returns 404
    evidence_ref: tests::unknown_id_404
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: request-target fixture does not touch secrets
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
REQUEST_TARGET_SUFFICIENT_GRADE=REQUEST_TARGET_INSUFFICIENT_GRADE.replace(
    'scenario: unknown skill id returns 404\n    evidence_ref: tests::unknown_id_404',
    'scenario: request-target delimiters ?, #, spaces, CRLF/control chars, and percent-encoded path segments are rejected or encoded\n    evidence_ref: tests::request_target_delimiters_and_control_chars'
)
REQUEST_TARGET_GENERIC_ONLY_GRADE=REQUEST_TARGET_INSUFFICIENT_GRADE.replace(
    'scenario: unknown skill id returns 404\n    evidence_ref: tests::unknown_id_404',
    'scenario: request-target smoke regression covers the ordinary unknown id path\n    evidence_ref: /Users/lidongyuan/workspace/tests/request_target_unknown_id_smoke.log'
)
REQUEST_TARGET_MALFORMED_ONLY_GRADE=REQUEST_TARGET_INSUFFICIENT_GRADE.replace(
    'scenario: unknown skill id returns 404\n    evidence_ref: tests::unknown_id_404',
    'scenario: malformed request is rejected\n    evidence_ref: /Users/lidongyuan/workspace/tests/malformed_request_smoke.log'
)
CYCLE018_SECRET_BARE_OUTCOME='''# Outcome Capsule — B-018 M5 Conduct adapter (cycle-018, Phase 2)
```yaml
acceptance:
  - id: B018-A11
    severity: P1
    statement: >
      **Secret / auth non-leakage.** The probe reads `codex login status` / `claude auth status`, but auth tokens, API keys, or OAuth material never appear in `AdapterError` `Debug`/`Display`, `tracing` output, normalized ledger events, or any `evidence/` file. `LoginRequired`/`NotAuthenticated` carry only an actionable remediation string, not captured auth output.
```
'''
CYCLE018_SECRET_BARE_GRADE='''# Grade — B-018 M5 Conduct adapter (cycle-018, round 1)
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B018-A11
    status: pass
    severity: P1
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B018-A11
    status: pass
    severity_if_fail: P1
    spec_refs: ["docs/ops/contributing.md", "docs/decisions/product.md"]
    evidence_ref: "src/process.rs:170-190 redact_secrets (token=/api_key=/sk-/oauth); src/lib.rs error messages carry no captured auth output; tests adapter_errors_do_not_display_token_material + codex_probe_maps_not_logged_in_without_secret_leakage"
```
```yaml
negative_regression_tests:
  - acceptance_id: B018-A11
    status: pass
    severity_if_fail: P1
    scenario: "A token-shaped secret in vendor stderr or a logged-out probe must not surface in AdapterError Debug/Display, evidence, or events; redact_secrets masks token=/api_key=/sk-/oauth."
    evidence_ref: "src/process.rs:170-190; tests adapter_errors_do_not_display_token_material + codex_probe_maps_not_logged_in_without_secret_leakage (nextest pass)"
```
```yaml
secret_leakage_audit:
  status: pass
  checked_surfaces:
    - "AdapterError Debug + Display (src/lib.rs:63-111)"
    - "vendor stderr capture redaction (src/process.rs:151-190, src/codex/mod.rs:210-226)"
    - "capability probe login/auth output (inspected for a boolean only, not stored; src/codex/mod.rs:80-88,540-559)"
    - "tracing warn! calls in normalize (no token/auth fields)"
    - "normalized vendor_event payloads + evidence trace/raw files"
  cleartext_secret_probe: pass
  evidence_ref: "tests adapter_errors_do_not_display_token_material + codex_probe_maps_not_logged_in_without_secret_leakage; src/process.rs:170-190 redact_secrets -> [REDACTED]; nextest green"
```
```yaml
dependency_spec_review:
  - dependency: "async-trait"
    status: pass
    severity_if_fail: P1
    spec_ref: "docs/ops/contributing.md (§9 license allowlist), docs/architecture/tech-stack.yaml"
    evidence_ref: "root Cargo.toml [workspace.dependencies] async-trait = \\"0.1.89\\" (pinned); Cargo.lock async-trait 0.1.89 from crates.io; license MIT OR Apache-2.0 (allowlisted)"
```
'''
CYCLE017_SECRET_NOT_APPLICABLE_OUTCOME='''# Grade round 0 — cycle-017 / B-005 Pattern Library reader + API endpoints
```yaml
acceptance:
  - id: B005-MALFORMED-ROBUST
    severity: P1
    statement: >
      parse_skill_file/parse_skill_text return degraded ParsedSkill (parse_ok=false + parse_error) for read error / non-utf8 / missing-frontmatter / malformed-yaml — never panic.
```
'''
CYCLE017_SECRET_NOT_APPLICABLE_GRADE='''# Grade round 0 — cycle-017 / B-005 Pattern Library reader + API endpoints
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B005-MALFORMED-ROBUST
    severity: P1
    status: pass
    evidence: "parse_skill_file/parse_skill_text return degraded ParsedSkill (parse_ok=false + parse_error) for read error / non-utf8 / missing-frontmatter / malformed-yaml — never panic; tests malformed_skills_degrade_without_breaking_listing (good+no-frontmatter+bad-yaml all list) + non_utf8_skill_degrades_without_error."
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B005-MALFORMED-ROBUST
    severity_if_fail: P1
    status: pass
    spec_refs: ["docs/ops/roadmap.md §4.1 dogfood task 2 (robust to missing YAML front matter)", "docs/decisions/product.md D-P25"]
    evidence_ref: "parse_skill_file degradation + tests malformed_skills_degrade_without_breaking_listing / non_utf8_skill_degrades_without_error"
```
```yaml
negative_regression_tests:
  - acceptance_id: B005-MALFORMED-ROBUST
    severity_if_fail: P1
    status: pass
    scenario: "malformed YAML front matter / missing front matter / non-UTF8 SKILL.md does not crash listing"
    evidence_ref: "tests malformed_skills_degrade_without_breaking_listing + non_utf8_skill_degrades_without_error (return Ok with degraded entry)"
```
```yaml
secret_leakage_audit:
  status: pass
  cleartext_secret_probe: not_applicable
  evidence_ref: "crates/symphony-patterns/src/lib.rs (PatternError/PatternEntry/PatternDetail) + crates/symphony-api/src/handlers/mod.rs (patterns_index/patterns_detail/pattern_error_to_api_error) + apps/symphony format_patterns; no auth/token/log code added (symphony-api auth.rs unchanged)"
  checked_surfaces:
    - "PatternError Debug/Display (thiserror): messages contain only path + skill_id (user-supplied dir name) — no tokens/keys/passwords."
    - "PatternEntry / PatternDetail Serialize (API JSON + CLI): id/name/description/risk_level/source/imported_from/has_usage/parse_ok/parse_error/body/usage — pattern metadata, not credentials."
    - "usage.json content surfaced verbatim in detail: local pattern metadata, not secret-bearing; reader never reads auth.json / daemon token."
    - "No logging added in this cycle; the crate touches no auth/token/network code."
```
```yaml
dependency_spec_review:
  - check: "no new third-party dependency introduced"
    status: pass
    severity_if_fail: P1
    spec_ref: "docs/architecture/tech-stack.yaml + docs/ops/contributing.md §6"
    evidence_ref: "crates/symphony-patterns/Cargo.toml uses only existing workspace deps serde/serde_json/serde_yaml_bw/thiserror/symphony-storage; no addition to root [workspace.dependencies]"
```
'''
SUBPROCESS_LIFECYCLE_OUTCOME='''# Outcome Capsule — B-018 M5 Conduct adapter (cycle-018, Phase 2)
```yaml
risk_surface:
  surfaces:
    external_subprocess: {present: true}
```
```yaml
adversarial_acceptance:
  - id: B018-ADV-PROBE-FAILCLOSED-1
    surface: external_subprocess
    severity: P1
    evidence_kind: subprocess_lifecycle_test
    verification_hint: "Simulate Codex/Claude capability probe version and auth-status helper commands plus a stream-json ping helper; assert unsupported_fatal and no exec fallback."
```
'''
SUBPROCESS_LIFECYCLE_INSUFFICIENT_GRADE='''# Grade — B-018 M5 Conduct adapter (cycle-018, round 1)
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: GADV-PROBE-1
    acceptance_id: B018-ADV-PROBE-FAILCLOSED-1
    status: pass
    severity_if_fail: P1
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "src/codex/mod.rs:327-404 real in-process round trip + ephemeral-negative; failures map to VersionTooOld/LoginRequired/GoalRpcUnavailable; never builds an exec/--json/text-goal fallback argv; tests codex_fake_vendor_probe_exercises_goal_rpc_round_trip + codex_probe_maps_not_logged_in_without_secret_leakage + handoff_argv_uses_goal_rpc_without_exec_json_or_text_goal_fallback (nextest green)"
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
''' + A1_CODE_SECTIONS
SUBPROCESS_LIFECYCLE_COMPLETE_GRADE=SUBPROCESS_LIFECYCLE_INSUFFICIENT_GRADE.replace(
    'src/codex/mod.rs:327-404 real in-process round trip + ephemeral-negative; failures map to VersionTooOld/LoginRequired/GoalRpcUnavailable; never builds an exec/--json/text-goal fallback argv; tests codex_fake_vendor_probe_exercises_goal_rpc_round_trip + codex_probe_maps_not_logged_in_without_secret_leakage + handoff_argv_uses_goal_rpc_without_exec_json_or_text_goal_fallback (nextest green)',
    'src/process.rs spawn_process_group .process_group(0) own process-group isolation; every probe/version/auth-status/ping helper command is wrapped in time::timeout wait timeout/deadline; after SIGTERM/SIGKILL the child.wait().await wait/reap path runs; stream-json stdout/stderr reader tasks are awaited, joined, and drained before return; nextest green'
)
RPC_CLEANUP_OUTCOME='''# Outcome Capsule — B-018 M5 Conduct adapter (cycle-018, Phase 2)
```yaml
acceptance:
  - id: B018-A6
    severity: P1
    statement: >
      Codex handoff uses app-server non-ephemeral goal-RPC only. Cleanup
      (`thread/goal/clear` + `thread/archive`) runs on every exit path.
```
'''
RPC_CLEANUP_HAPPY_ONLY_GRADE='''# Grade — B-018 M5 Conduct adapter (cycle-018, round 1)
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B018-A6
    status: pass
    severity: P1
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B018-A6
    status: pass
    severity_if_fail: P1
    spec_refs: ["docs/architecture/adapters/codex.md", "docs/agents/conduct/AGENT.md"]
    evidence_ref: "src/codex/mod.rs:242-276 5s inferred-completion timer after item/completed final answer -> session.emit_inferred_task_end(); explicit turn/completed wins; test codex_fake_vendor_infers_terminal_event_after_final_answer_race resolves ~5s (nextest pass)"
```
```yaml
negative_regression_tests:
  - acceptance_id: B018-A6
    status: pass
    severity_if_fail: P1
    scenario: "A turn whose final answer arrives but whose explicit turn/completed is missing/raced must still resolve to a terminal task_end (inferred) within ~5s rather than hanging to the full timeout."
    evidence_ref: "src/codex/mod.rs:242-276; test codex_fake_vendor_infers_terminal_event_after_final_answer_race asserts TaskEnd + extra.inferred_completion=true (nextest pass)"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: rpc cleanup fixture has no auth/token/log secret surface
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
RPC_CLEANUP_TIMEOUT_EVIDENCE_GRADE=RPC_CLEANUP_HAPPY_ONLY_GRADE.replace(
    'scenario: "A turn whose final answer arrives but whose explicit turn/completed is missing/raced must still resolve to a terminal task_end (inferred) within ~5s rather than hanging to the full timeout."\n    evidence_ref: "src/codex/mod.rs:242-276; test codex_fake_vendor_infers_terminal_event_after_final_answer_race asserts TaskEnd + extra.inferred_completion=true (nextest pass)"',
    'scenario: "A timeout path test forces the outer timeout after non-ephemeral thread creation and asserts thread/goal/clear + thread/archive are recorded before return."\n    evidence_ref: "tests codex_timeout_path_cleans_goal_and_archives_thread asserts clear/archive calls still happen (nextest pass)"'
)
RPC_CLEANUP_SOURCE_ROW_OUTCOME='''# Outcome Capsule — B-018 M5 Conduct adapter (cycle-018, Phase 2)
```yaml
acceptance:
  - id: B018-A5
    severity: P1
    statement: >
      Codex RPC check performs a real non-ephemeral goal-RPC round trip and
      fails closed when the round trip is unavailable.
```
'''
RPC_CLEANUP_SOURCE_ROW_GRADE='''# Grade — B-018 M5 Conduct adapter (cycle-018, round 1)
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B018-A5
    status: pass
    severity: P1
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B018-A5
    status: pass
    severity_if_fail: P1
    spec_refs: ["docs/architecture/adapters/codex.md", "docs/agents/conduct/AGENT.md"]
    evidence_ref: "src/codex/mod.rs:327-404 run_codex_goal_rpc_probe — real in-process initialize{experimentalApi}(goals:true) -> thread/start(ephemeral:false) -> goal/set -> goal/get(active) -> goal/clear -> archive + ephemeral-negative (ephemeral:true goal/set must /error); failure->GoalRpcUnavailable, success->capability_probe_result=supported; tests codex_fake_vendor_probe_exercises_goal_rpc_round_trip (nextest pass)"
```
```yaml
negative_regression_tests:
  - acceptance_id: B018-A5
    status: pass
    severity_if_fail: P1
    scenario: "Each probe failure must map to the correct AdapterError with no fallback: a handshake/round-trip/ephemeral-negative failure -> GoalRpcUnavailable."
    evidence_ref: "tests codex_probe_maps_not_logged_in_without_secret_leakage + handoff_argv_uses_goal_rpc_without_exec_json_or_text_goal_fallback (nextest pass)"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: rpc cleanup fixture has no auth/token/log secret surface
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
CYCLE016_LEDGER_CLEAN_OUTCOME='''# Outcome — cycle-016 B-004 Run Event Ledger + State Machine Projection
```yaml
acceptance:
  - id: B004-A1
    severity: P1
    statement: >
      Ledger append is idempotent and collision-safe under fs4 lock_with_timeout;
      duplicate idempotency keys are skipped and changed payloads return IdempotencyCollision.
```
'''
CYCLE016_LEDGER_CLEAN_GRADE='''# Grade — cycle-016 B-004 Run Event Ledger + State Machine Projection (round 0)
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B004-A1
    status: pass
    severity: P1
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B004-A1
    status: pass
    severity_if_fail: P1
    spec_refs: ["docs/architecture/schemas/events.md"]
    evidence_ref: "symphony-ledger::tests::append_is_idempotent_and_collision_safe; lib.rs append()/append_locked() (fs4 lock_with_timeout + SeekFrom::End + sync_data; dup-skip vs IdempotencyCollision)"
```
```yaml
negative_regression_tests:
  - acceptance_id: B004-A1
    status: pass
    severity_if_fail: P1
    scenario: "Re-append the same idempotency_key with a CHANGED payload returns LedgerError::IdempotencyCollision and never overwrites or duplicates the existing line."
    evidence_ref: "symphony-ledger::tests::append_is_idempotent_and_collision_safe"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "symphony-ledger append fixture has no auth/token/log secret surface"
```
```yaml
dependency_spec_review:
  - dependency: "symphony-ledger crate dependencies (fs4, serde, serde_json, thiserror, time)"
    status: pass
    severity_if_fail: P1
    spec_ref: "docs/architecture/tech-stack.yaml"
    evidence_ref: "crates/symphony-ledger/Cargo.toml uses *.workspace = true only; matches tech-stack.yaml pins"
```
'''
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

    def test_secret_leakage_audit_rejects_bare_only_probe_for_in_scope_surface(self):
        grade=LOW_CODE_COMPLETE.replace(
            "      - '{\"api_key\":\"sk-secret-test\"}'\n      - \"Authorization: Bearer sk-secret-test\"\n",
            ''
        )
        proc,p=self.run_lint('code','low',grade,AUTH_SECRET_CODE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('secret_leakage_audit.cleartext_secret_probe missing required token shapes', errors)
        self.assertIn('json_or_quoted_token', errors)
        self.assertIn('authorization_bearer', errors)

    def test_secret_leakage_audit_accepts_all_shapes_and_not_applicable(self):
        with self.subTest('all shapes'):
            proc,p=self.run_lint('code','low',LOW_CODE_COMPLETE,AUTH_SECRET_CODE_OUTCOME)
            self.assertEqual(proc.returncode,0,p)
        with self.subTest('not applicable'):
            proc,p=self.run_lint('code','low',CYCLE017_SUFFICIENT_GRADE,CYCLE017_STYLE_OUTCOME)
            self.assertEqual(proc.returncode,0,p)

    def test_cycle018_real_secret_audit_bare_pass_probe_requires_shapes(self):
        proc,p=self.run_lint('code','low',CYCLE018_SECRET_BARE_GRADE,CYCLE018_SECRET_BARE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('secret_leakage_audit.cleartext_secret_probe missing required token shapes', errors)
        self.assertIn('json_or_quoted_token', errors)
        self.assertIn('authorization_bearer', errors)

    def test_cycle017_real_not_applicable_probe_with_negated_auth_terms_does_not_require_shapes(self):
        proc,p=self.run_lint('code','low',CYCLE017_SECRET_NOT_APPLICABLE_GRADE,CYCLE017_SECRET_NOT_APPLICABLE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle018_subprocess_lifecycle_claim_requires_per_facet_evidence(self):
        proc,p=self.run_lint('code','medium',SUBPROCESS_LIFECYCLE_INSUFFICIENT_GRADE,SUBPROCESS_LIFECYCLE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertEqual(p['grade_lint']['errors'], [
            'subprocess_lifecycle[GADV-PROBE-1] missing facets: timeout,process_group,reap,stream_join — probe/stream subprocess surfaces require timeout + process-group + wait/reap (+ stream-task join) evidence'
        ])

    def test_subprocess_lifecycle_claim_passes_with_all_facets(self):
        proc,p=self.run_lint('code','medium',SUBPROCESS_LIFECYCLE_COMPLETE_GRADE,SUBPROCESS_LIFECYCLE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle016_clean_ledger_timeout_text_does_not_trigger_subprocess_lifecycle(self):
        proc,p=self.run_lint('code','low',CYCLE016_LEDGER_CLEAN_GRADE,CYCLE016_LEDGER_CLEAN_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle018_real_rpc_clear_archive_source_claim_requires_negative_path_cleanup_evidence(self):
        proc,p=self.run_lint('code','low',RPC_CLEANUP_SOURCE_ROW_GRADE,RPC_CLEANUP_SOURCE_ROW_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertEqual(p['grade_lint']['errors'], [
            'rpc_cleanup[B018-A5] cleanup-on-every-exit-path claimed but no timeout/error-path cleanup evidence (negative-path test required)'
        ])

    def test_cycle018_rpc_cleanup_every_exit_claim_requires_negative_path_cleanup_evidence(self):
        proc,p=self.run_lint('code','low',RPC_CLEANUP_HAPPY_ONLY_GRADE,RPC_CLEANUP_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertEqual(p['grade_lint']['errors'], [
            'rpc_cleanup[B018-A6] cleanup-on-every-exit-path claimed but no timeout/error-path cleanup evidence (negative-path test required)'
        ])

    def test_rpc_cleanup_every_exit_claim_passes_with_forced_timeout_cleanup_test(self):
        proc,p=self.run_lint('code','low',RPC_CLEANUP_TIMEOUT_EVIDENCE_GRADE,RPC_CLEANUP_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle016_clean_ledger_timeout_text_does_not_trigger_rpc_cleanup(self):
        proc,p=self.run_lint('code','low',CYCLE016_LEDGER_CLEAN_GRADE,CYCLE016_LEDGER_CLEAN_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle017_style_path_root_acceptance_requires_symlink_or_canonical_coverage(self):
        proc,p=self.run_lint('code','low',CYCLE017_INSUFFICIENT_GRADE,CYCLE017_STYLE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('property_obligation[B005-PATH-SAFETY]', errors)
        self.assertIn('symlink_or_canonical_containment', errors)

    def test_cycle017_style_path_root_acceptance_passes_with_canonical_coverage(self):
        proc,p=self.run_lint('code','low',CYCLE017_SUFFICIENT_GRADE,CYCLE017_STYLE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_raw_request_target_acceptance_requires_delimiter_control_char_coverage(self):
        proc,p=self.run_lint('code','low',REQUEST_TARGET_INSUFFICIENT_GRADE,REQUEST_TARGET_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('property_obligation[CLIENT-REQUEST-TARGET]', errors)
        self.assertIn('request_target_delimiter_or_control_chars', errors)

    def test_raw_request_target_generic_mention_is_not_enough(self):
        proc,p=self.run_lint('code','low',REQUEST_TARGET_GENERIC_ONLY_GRADE,REQUEST_TARGET_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('request_target_delimiter_or_control_chars', '\n'.join(p['grade_lint']['errors']))

    def test_raw_request_target_malformed_request_is_not_enough(self):
        proc,p=self.run_lint('code','low',REQUEST_TARGET_MALFORMED_ONLY_GRADE,REQUEST_TARGET_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('request_target_delimiter_or_control_chars', '\n'.join(p['grade_lint']['errors']))

    def test_raw_request_target_acceptance_passes_with_delimiter_control_char_coverage(self):
        proc,p=self.run_lint('code','low',REQUEST_TARGET_SUFFICIENT_GRADE,REQUEST_TARGET_OUTCOME)
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
