# Remediation Grade — cycle-020 F1-F7 (symphony-grade M6 Grade Agent)

**cycle**: cycle-020
**task**: Stage remediation of F1-F7 in `crates/symphony-grade`
**branch**: `/private/tmp/remediate-cycle-020` `remediate/cycle-020` @ `096dbb3`
**graded_at**: 2026-06-11
**grade_lint**: same-iteration canary for v1.4.14 Grade-agent facets

---

## grade_summary

```yaml
grade_summary:
  task_id: cycle-020-remediation
  round: 0
  risk_level: low
  p0_count: 0
  p1_count: 0
  p2_count: 0
  p3_count: 0
  overall_result: pass
  grade_verify_status: pass
  cargo_test: "cargo test -p symphony-grade --lib"
  cargo_test_pass: 28
  cargo_test_fail: 0
  notes: >
    All F1-F7 Grade-agent remediation acceptances are covered by real symphony-grade
    regression tests under /private/tmp/remediate-cycle-020/crates/symphony-grade/src.
    The same-iteration canary is intentionally a low-risk code Grade artifact while
    citing the high-risk fixtures that exercise D-P13 inside the remediated crate.
```

---

## acceptance_status

```yaml
acceptance_status:
  - id: a1
    status: pass
    severity: P0
    text: "F1 read-only isolation and forbidden path surfaces closed"
    evidence_ref: "cargo test -p symphony-grade --lib: artifact_path_traversal_is_rejected; artifact_forbidden_pattern_root_is_rejected; command_that_tampers_with_outcome_is_detected_and_fails; read_only_isolation_does_not_touch_forbidden_dirs"
  - id: a2
    status: pass
    severity: P0
    text: "F2 D-P13 high-risk schema trigger branches closed"
    evidence_ref: "cargo test -p symphony-grade --lib: high_risk_top_level_action_without_per_acceptance_marker_fails; high_risk_human_review_requires_needs_human_not_fail"
  - id: a3
    status: pass
    severity: P0
    text: "F3 second-signal substring forgery closed"
    evidence_ref: "cargo test -p symphony-grade --lib: criteria_substring_does_not_forge_high_risk_second_signal"
  - id: a4
    status: pass
    severity: P1
    text: "F4 llm_judge fail-closed evidence gates closed"
    evidence_ref: "cargo test -p symphony-grade --lib: llm_judge_empty_evidence_refs_fails_closed; llm_judge_hard_gate_failure_fails; llm_judge_trace_ref_only_evidence_fails_closed"
  - id: a5
    status: pass
    severity: P1
    text: "F5 outcome path schema fields closed"
    evidence_ref: "cargo test -p symphony-grade --lib: command_required_exit_code_non_default_is_enforced; command_cwd_non_default_is_used; artifact_min_size_bytes_non_default_is_enforced"
  - id: a6
    status: pass
    severity: P1
    text: "F6 Grade critic substance gate closed"
    evidence_ref: "cargo test -p symphony-grade --lib: critic_rejects_naked_seeded_pass_grade_result"
  - id: a7
    status: pass
    severity: P1
    text: "F7 subprocess lifecycle and detached descendant cleanup closed"
    evidence_ref: "cargo test -p symphony-grade --lib: command_timeout_reaps_detached_grandchild_escape"
```

---

## spec_compliance_matrix

```yaml
spec_compliance_matrix:
  - acceptance_id: a1
    spec_ref: "docs/agents/grade/AGENT.md R-AGT-6 read-only isolation; docs/ops/risks.md R-AGT-6"
    status: pass
    severity_if_fail: P0
    evidence_ref: "session::tests::artifact_path_traversal_is_rejected; session::tests::artifact_forbidden_pattern_root_is_rejected; session::tests::command_that_tampers_with_outcome_is_detected_and_fails; session::tests::read_only_isolation_does_not_touch_forbidden_dirs"
    notes: >
      F1 is closed by resolving artifact/source paths through resolve_workspace_path,
      normalize_relative_path, canonicalize, starts_with workspace root containment, and a
      deny-list for .symphony/memory-user, .symphony/patterns-user, and
      .symphony/patterns-imported. IntegrityBaseline captures before sha256/len for
      outcome.md and watched source files and rechecks after every acceptance, so hostile
      acceptance commands that write outcome.md are converted into failed Grade evidence.
  - acceptance_id: a2
    spec_ref: "docs/agents/grade/AGENT.md D-P13 high-risk actions require second signal or human review"
    status: pass
    severity_if_fail: P0
    evidence_ref: "session::tests::high_risk_top_level_action_without_per_acceptance_marker_fails; session::tests::high_risk_human_review_requires_needs_human_not_fail"
    notes: >
      F2 is closed by parsing outcome risk_level and top-level high_risk_actions, then
      apply_top_level_high_risk_gates injects a failing or pending gate when a high-risk
      action is not represented per acceptance. The second_signal branch fails closed;
      the human_review branch yields needs_human/pending_manual_review instead of pass.
  - acceptance_id: a3
    spec_ref: "docs/agents/grade/AGENT.md D-P13 independent second-signal semantics"
    status: pass
    severity_if_fail: P0
    evidence_ref: "session::tests::criteria_substring_does_not_forge_high_risk_second_signal"
    notes: >
      F3 is closed because criteria text containing second_signal_pass is only prose;
      it cannot set llm_judge_passed. apply_high_risk_gate records structured
      SecondSignal fields and keeps llm_judge_passed false without a real independent
      judge result or human_review artifact.
  - acceptance_id: a4
    spec_ref: "docs/agents/grade/AGENT.md llm_judge evidence requirements"
    status: pass
    severity_if_fail: P1
    evidence_ref: "session::tests::llm_judge_empty_evidence_refs_fails_closed; session::tests::llm_judge_hard_gate_failure_fails; session::tests::llm_judge_trace_ref_only_evidence_fails_closed"
    notes: >
      F4 is closed because evaluate_llm_judge initializes the hard_gate from real
      evidence_refs, keeps structured_stub_verdict false, rejects missing evidence ref
      paths, and rejects self-generated trace_ref paths such as evidence/trace_grade_a1.json
      as fabricated evidence.
  - acceptance_id: a5
    spec_ref: "docs/architecture/schemas/outcome-capsule.md acceptance command/artifact fields"
    status: pass
    severity_if_fail: P1
    evidence_ref: "session::tests::command_required_exit_code_non_default_is_enforced; session::tests::command_cwd_non_default_is_used; session::tests::artifact_min_size_bytes_non_default_is_enforced"
    notes: >
      F5 is closed because command acceptances honor required_exit_code and per-acceptance
      cwd, and artifact acceptances enforce min_size_bytes with trace fields for
      actual_size_bytes and min_size_ok.
  - acceptance_id: a6
    spec_ref: "docs/agents/grade/AGENT.md Grade critic substantive verdict contract"
    status: pass
    severity_if_fail: P1
    evidence_ref: "critic::tests::critic_rejects_naked_seeded_pass_grade_result"
    notes: >
      F6 is closed by run_critic rule_1 through rule_5. rule_1 is anchored to the
      outcome.md-derived GradeResult and rejects naked reasoning; rule_3 checks the
      grade_result.md body for deterministic command/artifact trace semantics; rule_4
      checks high-risk second-signal evidence backed by trace_json refs.
  - acceptance_id: a7
    spec_ref: "docs/agents/grade/AGENT.md command acceptance subprocess lifecycle"
    status: pass
    severity_if_fail: P1
    evidence_ref: "session::tests::command_timeout_reaps_detached_grandchild_escape"
    evidence_kind: subprocess_lifecycle_test
    evidence_summary: >
      F7 is closed by timeout_sec bounded execution, Unix CommandExt process_group(0)
      isolation, SIGTERM/SIGKILL negative pgid process-group cleanup, child.wait wait/reap,
      collect_descendants descendant-audit, and process-tree containment for a detached
      grandchild escape fixture using os.setsid.
    notes: >
      The detached grandchild escape fixture writes the descendant pid, times out, then
      wait_until_not_running asserts no grandchild remains after cleanup.
```

---

## negative_regression_tests

```yaml
negative_regression_tests:
  - id: nr1
    acceptance_id: a1
    scenario: "artifact_path: ../etc/hosts parent traversal is rejected before read"
    test_name: "session::tests::artifact_path_traversal_is_rejected"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo test -p symphony-grade --lib; paths.rs normalize_relative_path rejects .. and resolve_workspace_path canonicalize/starts_with workspace root containment"
  - id: nr2
    acceptance_id: a1
    scenario: "artifact_path under .symphony/patterns-user forbidden root is rejected before read"
    test_name: "session::tests::artifact_forbidden_pattern_root_is_rejected"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo test -p symphony-grade --lib; paths.rs deny-list covers .symphony/memory-user, .symphony/patterns-user, .symphony/patterns-imported"
  - id: nr3
    acceptance_id: a1
    scenario: "hostile acceptance command attempts to write outcome.md and is forced to fail by post-run integrity recheck"
    test_name: "session::tests::command_that_tampers_with_outcome_is_detected_and_fails"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo test -p symphony-grade --lib; session.rs IntegrityBaseline before/after sha256 hash and byte-stability recheck for outcome.md/source files"
  - id: nr4
    acceptance_id: a1
    scenario: "read-only run keeps outcome bytes unchanged and does not create forbidden user or imported pattern dirs"
    test_name: "session::tests::read_only_isolation_does_not_touch_forbidden_dirs"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo test -p symphony-grade --lib; outcome.md before bytes equal after bytes; .symphony/memory-user, patterns-user, patterns-imported absent"
  - id: nr5
    acceptance_id: a2
    scenario: "top-level risk_level high with high_risk_actions deploy requires represented second_signal branch and fails when no per-acceptance marker exists"
    test_name: "session::tests::high_risk_top_level_action_without_per_acceptance_marker_fails"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo test -p symphony-grade --lib; risk_level: high plus high_risk_actions: deploy requires second_signal branch and fails closed"
  - id: nr6
    acceptance_id: a2
    scenario: "high-risk human_review branch yields needs_human/pending_manual_review instead of pass"
    test_name: "session::tests::high_risk_human_review_requires_needs_human_not_fail"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo test -p symphony-grade --lib; human_review requires human_review artifact and maps to needs_human branch"
  - id: nr7
    acceptance_id: a3
    scenario: "criteria substring second_signal_pass cannot set llm_judge_passed"
    test_name: "session::tests::criteria_substring_does_not_forge_high_risk_second_signal"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo test -p symphony-grade --lib; structured independent judge result remains absent and llm_judge_passed stays false"
  - id: nr8
    acceptance_id: a4
    scenario: "empty evidence_refs fail closed"
    test_name: "session::tests::llm_judge_empty_evidence_refs_fails_closed"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo test -p symphony-grade --lib; empty evidence_refs fail closed and deterministic_hard_gate_passed=false"
  - id: nr9
    acceptance_id: a4
    scenario: "missing evidence_ref path fails closed"
    test_name: "session::tests::llm_judge_hard_gate_failure_fails"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo test -p symphony-grade --lib; missing evidence_ref fails and hard_gate defaults closed false"
  - id: nr10
    acceptance_id: a4
    scenario: "self-fabricated trace_ref-only evidence_refs are rejected"
    test_name: "session::tests::llm_judge_trace_ref_only_evidence_fails_closed"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo test -p symphony-grade --lib; trace_ref only evidence_refs are rejected as fabricated and cannot be sole evidence"
  - id: nr11
    acceptance_id: a5
    scenario: "non-default required_exit_code is enforced"
    test_name: "session::tests::command_required_exit_code_non_default_is_enforced"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo test -p symphony-grade --lib; required_exit_code: 7 is honored"
  - id: nr12
    acceptance_id: a5
    scenario: "per-acceptance cwd is used"
    test_name: "session::tests::command_cwd_non_default_is_used"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo test -p symphony-grade --lib; per-acceptance cwd: 'nested' is used"
  - id: nr13
    acceptance_id: a5
    scenario: "artifact min_size_bytes is enforced"
    test_name: "session::tests::artifact_min_size_bytes_non_default_is_enforced"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo test -p symphony-grade --lib; min_size_bytes: 64 is enforced"
  - id: nr14
    acceptance_id: a6
    scenario: "seeded-pass naked-verdict grade result is rejected by the Grade critic"
    test_name: "critic::tests::critic_rejects_naked_seeded_pass_grade_result"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo test -p symphony-grade --lib; seeded-pass naked-verdict critic rejects with rule_1 and rule_3 failures"
  - id: nr15
    acceptance_id: a7
    scenario: "timeout cleanup handles detached grandchild escape"
    test_name: "session::tests::command_timeout_reaps_detached_grandchild_escape"
    status: pass
    severity_if_fail: P1
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "cargo test -p symphony-grade --lib"
    evidence_summary: >
      timeout_sec=1 triggers timeout; CommandExt process_group(0) gives the command its
      own process-group; cleanup sends SIGTERM/SIGKILL to negative pgid and descendants;
      child.wait performs wait/reap; the detached grandchild escape fixture uses os.setsid;
      descendant-audit and process-tree containment assert no grandchild remains.
```

---

## secret_leakage_audit

```yaml
secret_leakage_audit:
  status: pass
  evidence_ref: "manual review of /private/tmp/remediate-cycle-020/crates/symphony-grade/src plus cargo test -p symphony-grade --lib"
  checked_surfaces:
    - "crates/symphony-grade/src/paths.rs"
    - "crates/symphony-grade/src/session.rs"
    - "crates/symphony-grade/src/critic.rs"
    - "crates/symphony-grade/src/result.rs"
  cleartext_secret_probe: not_applicable
  rationale: >
    symphony-grade evaluates local command/artifact/judge/manual-review acceptances and
    does not introduce a credential, bearer-token, API-key, OAuth, or network surface in
    this remediation, so cleartext secret probing is not applicable.
```

---

## dependency_spec_review

```yaml
dependency_spec_review:
  - name: "serde_json"
    spec_ref: "workspace Cargo.toml existing dependency; remediated trace rendering uses the existing workspace dependency"
    status: pass
    severity_if_fail: P1
    evidence_ref: "/private/tmp/remediate-cycle-020/crates/symphony-grade/src/paths.rs write_trace uses serde_json::to_string_pretty; Cargo.lock unchanged for this crate remediation"
    notes: >
      The remediation uses existing workspace dependency wiring for serde_json trace
      emission and does not introduce a new external crate or version pin.
```

---

## Grade-agent contract evidence (v1.4.14 facets)

Every token below is tied to a real code path or named regression test in
`/private/tmp/remediate-cycle-020/crates/symphony-grade/src`.

- Read-only isolation hostile write command: hostile acceptance command `sh -c` writes outcome.md, and `session::tests::command_that_tampers_with_outcome_is_detected_and_fails` proves the post-run integrity check fails the Grade instead of accepting the mutation.
- Read-only isolation hostile artifact traversal: hostile artifact_path `../etc/hosts` path-traversal and forbidden-root read attempts are rejected by `session::tests::artifact_path_traversal_is_rejected` and `session::tests::artifact_forbidden_pattern_root_is_rejected`.
- Read-only isolation containment: `paths.rs::resolve_workspace_path` uses canonicalize/realpath-style canonical paths, starts_with root containment within workspace root, and a deny-list for `.symphony/memory-user`, `.symphony/patterns-user`, and `.symphony/patterns-imported`.
- Read-only isolation byte stability: post-run before/after sha256 hash and byte-stability recheck covers outcome.md and watched source paths via `IntegrityBaseline`; `session::tests::command_that_tampers_with_outcome_is_detected_and_fails` and `session::tests::read_only_isolation_does_not_touch_forbidden_dirs` prove it.

D-P13 fixture shape used by `session::tests::high_risk_top_level_action_without_per_acceptance_marker_fails`:

```yaml
risk_level: high
high_risk_actions:
  - action: deploy
    requires: second_signal
```

- D-P13 second_signal branch: `apply_top_level_high_risk_gates` and `apply_high_risk_gate` require the second_signal branch to have deterministic_check and llm_judge both_required pass; otherwise it fails closed.
- D-P13 human_review branch: `session::tests::high_risk_human_review_requires_needs_human_not_fail` proves a human_review branch requires a human_review artifact and yields needs_human/pending_manual_review rather than pass.
- Unforgeable second signal: criteria substring `second_signal_pass` cannot set llm_judge_passed; `session::tests::criteria_substring_does_not_forge_high_risk_second_signal` proves llm_judge_passed remains false.
- Structured second signal: the only acceptable high-risk auto-pass path is a structured independent judge result recorded into `SecondSignal`; absent that result, or absent a human_review artifact, the gate fails or stays pending.
- llm_judge empty evidence: empty evidence_refs fail closed in `session::tests::llm_judge_empty_evidence_refs_fails_closed`.
- llm_judge missing evidence: missing evidence_ref paths fail closed in `session::tests::llm_judge_hard_gate_failure_fails`.
- llm_judge hard gate: the hard_gate defaults closed/false because `structured_stub_verdict=false` and no real independent judge result can auto-pass.
- llm_judge fabricated trace: self-fabricated trace_ref only evidence_refs are rejected as invalid and cannot be sole evidence in `session::tests::llm_judge_trace_ref_only_evidence_fails_closed`.
- Outcome schema fields: `session::tests::command_required_exit_code_non_default_is_enforced` proves required_exit_code: 7, `session::tests::command_cwd_non_default_is_used` proves per-acceptance cwd: 'nested', and `session::tests::artifact_min_size_bytes_non_default_is_enforced` proves min_size_bytes: 64.
- Critic substance: seeded-pass naked-verdict critic rejects with `approved: false` / verdict rejected behavior in `critic::tests::critic_rejects_naked_seeded_pass_grade_result`; rule_1 is tied to outcome.md-derived GradeResult trace-backed reasoning, rule_3 is checked before grade_result.md is written, and rule_4 requires high-risk evidence with trace_json refs.
- Subprocess descendant escape: `session::tests::command_timeout_reaps_detached_grandchild_escape` is a detached grandchild escape fixture; timeout, process_group(0), SIGTERM/SIGKILL, child.wait wait/reap, descendant-audit, and process-tree containment assert no descendant or grandchild remains.
