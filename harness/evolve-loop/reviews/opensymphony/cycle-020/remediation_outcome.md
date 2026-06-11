---
schema_version: "1.2"
id: T-20260611-remediation-c020
title: "Remediate cycle-020 F1-F7 in the M6 Grade Agent crates/symphony-grade"
goal: "Close the cycle-020 remediation findings in crates/symphony-grade with trace-backed Grade-agent regression coverage."
mode: relaxed
risk_level: low
non_goals:
  - "No linter change in this canary; remediation evidence must come from the remediated symphony-grade crate."
  - "No Shape-agent or symphony-shape scope."
assumptions:
  - id: as1
    text: "The cycle-020 findings F1-F7 are the complete remediation scope for this canary."
    source: "harness/evolve-loop/reviews/opensymphony/cycle-020/r2.md"
    confirmed: true
    risk_if_wrong: "A missing finding would be falsely omitted from the Grade canary; mitigated by mapping every a1..a7 item to F1..F7."
  - id: as2
    text: "The truthful evidence source is the remediated symphony-grade crate under /private/tmp/remediate-cycle-020."
    source: "/private/tmp/remediate-cycle-020/crates/symphony-grade/src/{paths.rs,session.rs,critic.rs}"
    confirmed: true
    risk_if_wrong: "The grade could cite unimplemented behavior; mitigated by naming the exact regression tests in remediation_grade.md."
groundings: []
output_contract:
  target: file_set
  artifacts:
    - type: file_set
      path: "crates/symphony-grade/"
provenance:
  source: agent_authored
verification:
  mode: agent-driven
  required_evidence:
    - cargo_test_symphony_grade
    - grade_lint_v1_4_14_canary
acceptance:
  - id: a1
    severity: P0
    text: "F1: Grade Agent enforces R-AGT-6 read-only isolation for outcome.md and source artifacts: hostile write attempts fail with source/outcome byte-stability rechecks, artifact traversal is rejected, and forbidden .symphony roots are denied by canonical containment and deny-list checks."
  - id: a2
    severity: P0
    text: "F2: D-P13 high-risk outcome schema trigger is enforced: outcome risk_level high plus top-level high_risk_actions must be represented by a per-acceptance second_signal branch or human_review branch."
  - id: a3
    severity: P0
    text: "F3: The high-risk second signal is unforgeable: a criteria substring second_signal_pass cannot set llm_judge_passed, and only a structured independent judge result or human_review artifact may satisfy the branch."
  - id: a4
    severity: P1
    text: "F4: llm_judge evidence gates fail closed when evidence_refs are empty, missing, or self-fabricated trace_ref-only evidence."
  - id: a5
    severity: P1
    text: "F5: Outcome acceptance schema fields required_exit_code, cwd, and min_size_bytes are enforced per acceptance."
  - id: a6
    severity: P1
    text: "F6: The Grade critic rejects seeded-pass or naked-verdict grade_result content and requires substantive trace-backed reasoning."
  - id: a7
    severity: P1
    text: "F7: Timed-out subprocess command lifecycle uses process-tree containment and wait/reap cleanup for detached grandchild escape fixtures."
---

# Remediation Outcome — cycle-020 F1-F7 (M6 Grade Agent)

This schema_version 1.2 Outcome Capsule scopes the cycle-020 remediation canary to
`crates/symphony-grade`. The acceptance list a1..a7 maps directly to F1..F7 with
F1-F3 marked P0 and F4-F7 marked P1. The canary grade is in `remediation_grade.md`.
