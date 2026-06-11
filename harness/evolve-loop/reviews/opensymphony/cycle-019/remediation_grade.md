# Remediation Grade — cycle-019 r1 findings F1-F7 (symphony-shape M4 Shape Agent)

**cycle**: cycle-019
**task**: Stage-5 remediation of the seven escaped r1 defects in `crates/symphony-shape`
**branch**: remediate/cycle-019 @ bfbe87e
**graded_at**: 2026-06-11
**grade_lint**: this document is the same-iteration canary for the v1.4.13 Shape facets
(shape_forbidden_read_isolation_audit, outcome_capsule_v12_structural_schema,
shape_protocol_evidence).

---

## grade_summary

```yaml
grade_summary:
  task_id: cycle-019-remediation
  round: 0
  risk_level: low
  p0_count: 0
  p1_count: 0
  p2_count: 0
  p3_count: 0
  overall_result: pass
  grade_verify_status: pass
  nextest_count: 130
  nextest_pass: 130
  nextest_skip: 1
  notes: >
    All five verify.grade.code gates green (build / fmt --check / clippy -D warnings /
    nextest 130-pass-1-skip / verify-docs). All seven r1 findings F1-F7 closed with a
    per-finding regression test. No residual P0/P1.
```

---

## acceptance_status

```yaml
acceptance_status:
  - id: a1
    status: pass
    severity: P0
    text: "F1 isolation closed"
    evidence_ref: "nextest f1_shape_never_reads_user_or_imported_or_memory_sentinel_files"
  - id: a2
    status: pass
    severity: P1
    text: "F2 structured capsule schema closed"
    evidence_ref: "nextest capsule structured-object tests"
  - id: a3
    status: pass
    severity: P1
    text: "F3 output_contract target/artifact consistency closed"
    evidence_ref: "nextest f3_target_pr_requires_pr_artifact"
  - id: a4
    status: pass
    severity: P1
    text: "F4 nine-rule critic + JSON verdict envelope closed"
    evidence_ref: "nextest f4_critic_walks_spec_rules_and_emits_json_verdict_envelope"
  - id: a5
    status: pass
    severity: P0
    text: "F5 high-risk classification closed"
    evidence_ref: "nextest high-risk classifier tests"
  - id: a6
    status: pass
    severity: P1
    text: "F6 Q&A protocol + capsule merge closed"
    evidence_ref: "nextest qa protocol + merge tests"
  - id: a7
    status: pass
    severity: P1
    text: "F7 critic-approval output gate closed"
    evidence_ref: "nextest f7_rejected_critic_blocks_outcome_write"
```

---

## spec_compliance_matrix

```yaml
spec_compliance_matrix:
  - acceptance_id: a1
    spec_ref: "docs/agents/shape/AGENT.md capabilities.forbidden; R-AGT-6 (docs/ops/risks.md); docs/ops/contributing.md RL-2"
    status: pass
    severity_if_fail: P0
    evidence_ref: "test f1_shape_never_reads_user_or_imported_or_memory_sentinel_files; cargo nextest 130/130"
    notes: >
      Shape reads only agent-authored patterns via symphony_patterns::list_agent_patterns;
      it never opens the memory-user, patterns-user, or patterns-imported trees. No code
      path reads those roots. The regression test plants sentinel skills under patterns-user
      and patterns-imported and asserts Shape does not read them into its result — proving a
      no-reads boundary, not merely no-writes.
  - acceptance_id: a2
    spec_ref: "docs/architecture/schemas/outcome-capsule.md (schema_version 1.2)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest 130/130; capsule.rs Assumption/Grounding structs + validation"
    notes: >
      assumptions is a list of Assumption{id,text,source,confirmed,risk_if_wrong};
      groundings is a list of Grounding{id,source_type,fetched_at,supports,...}; malformed
      entries are rejected by capsule validation (no longer Vec<String>).
  - acceptance_id: a3
    spec_ref: "docs/architecture/schemas/outcome-capsule.md output_contract"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest 130/130; f3_target_pr_requires_pr_artifact"
    notes: >
      output_contract.target must equal one of artifacts[*].type; target=pr requires a pr
      artifact row (file_set alone is rejected).
  - acceptance_id: a4
    spec_ref: "docs/agents/shape/AGENT.md critic contract (nine rules, JSON verdict envelope)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest 130/130; f4_critic_walks_spec_rules_and_emits_json_verdict_envelope"
    notes: >
      The Shape critic consumes the shape_session transcript, walks the nine rules, and emits
      the JSON verdict envelope with fields verdict, rejected_reasons, approved_with_notes,
      the incident flag, and incident_class.
  - acceptance_id: a5
    spec_ref: "docs/agents/shape/AGENT.md risk classification / high_risk_actions"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo nextest 130/130; high-risk classifier tests"
    notes: >
      One-liners invoking deploy, delete (file_delete), db_write, external_api, payment
      (payment_api), or merge_pr are classified risk_level: high with a non-empty
      high_risk_actions list; the critic raises incident_class risk_level_understated_hard
      when a high-risk action is present but risk_level is not high.
  - acceptance_id: a6
    spec_ref: "docs/agents/shape/AGENT.md Q&A protocol"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest 130/130; qa.rs protocol + session merge tests"
    notes: >
      Generated questions carry the 'My assumption:' and 'Source:' prefixes plus a
      'Skip — agent decide' option; user answers are merged into the Outcome Capsule
      (answers merged into assumptions and acceptance), not only into shape_session.md.
  - acceptance_id: a7
    spec_ref: "docs/agents/shape/AGENT.md outputs.gate critic_approved"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest 130/130; f7_rejected_critic_blocks_outcome_write"
    notes: >
      The critic-approval output gate: when the critic verdict is rejected (approved: false),
      outcome.md is not written and the session does not advance.
```

---

## negative_regression_tests

```yaml
negative_regression_tests:
  - id: nr1
    acceptance_id: a1
    scenario: "sentinel skills under patterns-user and patterns-imported are never opened by Shape (R-AGT-6 no-reads, docs/agents/shape/AGENT.md capabilities.forbidden, memory-user / patterns-user / patterns-imported all absent from result)"
    test_name: "symphony-shape session::tests::f1_shape_never_reads_user_or_imported_or_memory_sentinel_files"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo nextest 130/130"
  - id: nr2
    acceptance_id: a2
    scenario: "Assumption/Grounding objects missing a required field are rejected by capsule validation"
    test_name: "symphony-shape capsule::tests structured assumption/grounding validation"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest 130/130"
  - id: nr3
    acceptance_id: a3
    scenario: "output_contract.target=pr with only a file_set artifact is rejected; target must match an artifact type"
    test_name: "symphony-shape capsule::tests::f3_target_pr_requires_pr_artifact"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest 130/130"
  - id: nr4
    acceptance_id: a4
    scenario: "critic over the shape_session emits the nine-rule JSON verdict envelope (verdict, rejected_reasons, approved_with_notes, incident, incident_class)"
    test_name: "symphony-shape critic::tests::f4_critic_walks_spec_rules_and_emits_json_verdict_envelope"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest 130/130"
  - id: nr5
    acceptance_id: a5
    scenario: "a high-risk one-liner (deploy/delete/db_write/external_api/payment/merge_pr) without risk_level high and high_risk_actions is rejected; critic raises risk_level_understated_hard"
    test_name: "symphony-shape critic/session high-risk classifier tests"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo nextest 130/130"
  - id: nr6
    acceptance_id: a6
    scenario: "Q&A questions without the My assumption / Source / Skip — agent decide protocol, or answers not merged into the capsule, are caught"
    test_name: "symphony-shape qa::tests + session::tests::f6_qa_answers_are_merged_into_capsule_acceptance_and_assumptions"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest 130/130"
  - id: nr7
    acceptance_id: a7
    scenario: "when the critic verdict is rejected (approved: false), outcome.md is not written and the session does not advance"
    test_name: "symphony-shape session::tests::f7_rejected_critic_blocks_outcome_write"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest 130/130"
```

---

## secret_leakage_audit

```yaml
secret_leakage_audit:
  status: pass
  evidence_ref: "manual review of the remediation diff bfbe87e; cargo nextest 130/130"
  checked_surfaces:
    - "crates/symphony-shape/src/capsule.rs"
    - "crates/symphony-shape/src/critic.rs"
    - "crates/symphony-shape/src/session.rs"
    - "crates/symphony-shape/src/qa.rs"
    - "crates/symphony-patterns/src/lib.rs list_agent_patterns"
  cleartext_secret_probe: not_applicable
  rationale: >
    symphony-shape has no credential, token, auth, or network surface — it generates an
    Outcome Capsule (YAML/Markdown) and a critic verdict from a local one-liner and the
    agent-authored pattern index. No secret material is read, serialized, or logged, so the
    multi-shape cleartext-secret probe is not applicable.
```

---

## dependency_spec_review

```yaml
dependency_spec_review:
  - name: serde_json
    spec_ref: "docs/architecture/tech-stack.yaml (workspace dep serde_json 1.0.149)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "crates/symphony-shape/Cargo.toml serde_json.workspace = true; Cargo.lock edge only"
    notes: >
      F4 introduces the JSON verdict envelope via render_critic_json; serde_json is added
      as `serde_json.workspace = true` (the existing workspace dependency, version 1.0.149,
      already used by other crates). No new external version is introduced.
  - name: symphony-patterns
    spec_ref: "docs/architecture/api-contract.md §3.6 (B-005)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "crates/symphony-patterns/src/lib.rs list_agent_patterns"
    notes: >
      F1 adds list_agent_patterns to the existing workspace path dependency; it scopes the
      pattern index to the agent-authored tree only, with user_authored and imported held
      empty. No new dependency.
```

---

## Shape AGENT contract evidence (F4 / F5 / F6 / F7)

This section makes the Shape-agent contract evidence explicit for the v1.4.13
shape_protocol_evidence facet; every claim is backed by a named regression test above.

- **Critic contract (F4)** — the Shape critic consumes the `shape_session` transcript,
  walks the nine rules, and emits the JSON verdict envelope whose fields are `verdict`,
  `rejected_reasons`, `approved_with_notes`, the `incident` flag, and `incident_class`
  (test `f4_critic_walks_spec_rules_and_emits_json_verdict_envelope`).
- **High-risk classifier (F5)** — one-liners invoking `deploy`, `delete` (`file_delete`),
  `db_write`, `external_api`, `payment` (`payment_api`), or `merge_pr` are classified
  `risk_level: high` with a non-empty `high_risk_actions` list; the critic raises
  `incident_class` `risk_level_understated_hard` when a high-risk action is present but
  `risk_level` is not `high`.
- **Q&A protocol (F6)** — generated questions carry the `My assumption:` and `Source:`
  prefixes plus a `Skip — agent decide` option, and user answers are merged into the
  Outcome Capsule (answers merged into assumptions and acceptance), not only into
  `shape_session.md`.
- **Rejected-critic gate (F7)** — regression test `f7_rejected_critic_blocks_outcome_write`
  proves that when the critic verdict is rejected (`approved: false`), `outcome.md` is not
  written and the session does not advance.

---

## Grade Narrative

The Stage-5 remediation closes all seven r1-escaped defects in the B-019 `symphony-shape`
M4 Shape Agent, each with a dedicated `f1_`..`f7_` regression test. The two P0 findings —
F1 (R-AGT-6 forbidden-read isolation; Shape now reads only agent-authored patterns via
`list_agent_patterns` and never opens the memory-user / patterns-user / patterns-imported
trees) and F5 (high-risk classification with `high_risk_actions` enforcement) — and the
five P1 findings (F2 structured Outcome Capsule schema, F3 output_contract target/artifact
consistency, F4 nine-rule JSON critic, F6 Q&A protocol + capsule merge, F7 critic-approval
output gate) are all CLOSED. Gate verdict: build / fmt --check / clippy -D warnings /
nextest 130 pass 1 skip / verify-docs all green. No residual P0/P1.
