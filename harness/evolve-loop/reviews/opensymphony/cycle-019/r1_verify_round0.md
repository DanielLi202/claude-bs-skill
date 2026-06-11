# r1-verify round 0 — cycle-019 remediation (adversarial fresh-context, codex read-only)

Verifier instructed to refute-by-default against the remediation diff (caf1806..bfbe87e) in
the isolated worktree. Verdict: **overall_closed: false** — F1/F2/F3/F4/F6 closed; **F5 (P0)**
and **F7 (P1)** refuted. This drove a Stage-5 fix-round (see r1_verify.md for the final
all-closed verdict). Both refutations were independently confirmed against the actual code by
the orchestrator before iterating.

```yaml
r1_verify:
  findings:
    - id: F1
      closed: true
      severity: P0
      fix: "session.rs:280-283 + symphony-patterns/src/lib.rs:108-115 — Shape calls list_agent_patterns only (lists layout.patterns; user_authored/imported left empty)"
      regression_test: "f1_shape_never_reads_user_or_imported_or_memory_sentinel_files; list_agent_patterns_ignores_user_and_imported_sources"
      refutation_attempt: "Searched Shape for list_patterns/read_pattern/forbidden-tree access; production path reaches only list_agent_patterns — old transitive read path gone"
    - id: F2
      closed: true
      severity: P1
      fix: "capsule.rs:82-104,184-204,261-303 — assumptions/groundings are typed structs with required-field validation"
      regression_test: "f2_assumptions_serialize_as_structured_objects; f2_malformed_assumption_entry_is_rejected; f2_malformed_grounding_entry_without_url_or_path_is_rejected; f2_legacy_string_assumptions_are_rejected"
      refutation_attempt: "Legacy string assumptions + malformed fields are rejected by parse/validate"
    - id: F3
      closed: true
      severity: P1
      fix: "capsule.rs:242-258 + session.rs:494-514 — target must equal one artifact type; drafting emits matching target/artifact"
      regression_test: "f3_target_pr_requires_pr_artifact"
      refutation_attempt: "target=pr on a file_set capsule returns OutputContractTargetMismatch"
    - id: F4
      closed: true
      severity: P1
      fix: "critic.rs:39-54,54-121 — critic takes OutcomeCapsule + ShapeSessionTranscript, runs rules, serializes JSON envelope"
      regression_test: "f4_critic_walks_spec_rules_and_emits_json_verdict_envelope"
      refutation_attempt: "No old approved/findings YAML shape remains; shape_critic.json from CriticVerdict"
    - id: F5
      closed: false
      severity: P0
      fix: "session.rs:213-218,320-331 + critic.rs:76-101,304-335 — partial high-risk inference"
      regression_test: "f5_high_risk_oneliner_requires_high_risk_actions; critic_rejects_rule_3_risk_level_understated; f5_critic_rejects_high_risk_capsule_missing_high_risk_actions"
      refutation_attempt: "BYPASS: run_critic raises incident only when risk_level==Low. A deploy action with risk_level=Medium is rejected but incident=false — violates incident-on-high-risk-action-with-non-high-risk-level"
    - id: F6
      closed: true
      severity: P1
      fix: "qa.rs:3,58-145 + session.rs:361-445,494-514,517-584 — prefixes/skip option; answers flow into assumptions/acceptance/output_contract"
      regression_test: "questions_include_canonical_prefixes_and_skip_option; f6_qa_answers_are_merged_into_capsule_acceptance_and_assumptions"
      refutation_attempt: "draft_capsule persists selected answers into capsule — no longer session-only"
    - id: F7
      closed: false
      severity: P1
      fix: "session.rs:160-177,640-655 — partial gate writes outcome.md only when approved"
      regression_test: "f7_rejected_critic_blocks_outcome_write (write_gated_artifacts unit-level only)"
      refutation_attempt: "BYPASS (advance half): write_session returns Ok(ShapeSessionResult) for a rejected verdict; CLI prints outcome_path and exits 0. Negative test does not exercise the public run path or assert non-advance"
  residuals:
    - "docs/agents/shape/AGENT.md:355 pattern_lookup row claims it reads patterns-imported, contradicting capabilities.forbidden 81-83 (R-AGT-6) — fixed in fix-round (FIX 3)"
    - "F1 sentinel tests prove no forbidden content reaches artifacts, not OS-level reads (accepted; code review confirms list_agent_patterns scope)"
    - "Q4 risk answers recorded as assumptions but do not override risk_level (design nuance, not F1-F7)"
    - "Tests inspected not executed (read-only verifier); orchestrator independently ran nextest 130/130"
  overall_closed: false
  confidence: 0.86
```
