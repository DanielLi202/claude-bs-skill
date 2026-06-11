---
schema_version: "1.2"
id: T-20260611-remediation-c019
mode: relaxed
one_liner: "Remediate cycle-019 r1 findings F1-F7 in the symphony-shape M4 Shape Agent"
risk_level: low
non_goals:
  - "No change to bs-skill Grade/Shape process gates (those are escalated_to_human, tracked separately)"
  - "No new external dependency beyond the workspace serde_json already pinned in tech-stack.yaml"
assumptions:
  - id: as1
    text: "The r1.md escaped_findings F1-F7 are the complete set of defects to remediate in symphony-shape"
    source: "reviews/opensymphony/cycle-019/r1.md"
    confirmed: true
    risk_if_wrong: "A missed defect ships in the M4 Shape Agent; mitigated by the fresh-context r1-verify stage"
  - id: as2
    text: "R-AGT-6 / RL-2 forbid Shape from reading memory-user, patterns-user, and patterns-imported (read AND write)"
    source: "docs/ops/risks.md R-AGT-6; docs/ops/contributing.md RL-2; docs/agents/shape/AGENT.md capabilities.forbidden"
    confirmed: true
    risk_if_wrong: "Isolation boundary misread; mitigated by sentinel regression test proving the trees are never opened"
groundings: []
output_contract:
  target: file_set
  artifacts:
    - type: file_set
      path: "crates/symphony-shape/"
provenance:
  source: agent_authored
verification:
  mode: agent-driven
  required_evidence:
    - git_diff
    - cargo_nextest
acceptance:
  - id: a1
    severity: P0
    text: "F1: Shape reads only agent-authored patterns; it never opens the memory-user, patterns-user, or patterns-imported trees (R-AGT-6 / docs/agents/shape/AGENT.md capabilities.forbidden)"
  - id: a2
    severity: P1
    text: "F2: Outcome Capsule assumptions and groundings are structured objects, not scalar strings, with full required fields and validation"
  - id: a3
    severity: P1
    text: "F3: output_contract.target must equal one artifacts[*].type; target pr requires a pr artifact"
  - id: a4
    severity: P1
    text: "F4: the Shape critic walks the nine rules over the shape_session and emits the JSON verdict envelope"
  - id: a5
    severity: P0
    text: "F5: high-risk one-liners are classified risk_level high with non-empty high_risk_actions and the critic enforces it"
  - id: a6
    severity: P1
    text: "F6: Q&A questions carry My assumption / Source prefixes and a Skip option, and answers are merged into the Outcome Capsule"
  - id: a7
    severity: P1
    text: "F7: the critic-approval output gate blocks the outcome write when the verdict is rejected"
---

# Remediation Outcome — cycle-019 r1 findings F1-F7 (symphony-shape M4 Shape Agent)

This outcome capsule frames the Stage-5 remediation of the seven escaped P0/P1 defects
that the independent r1 review found in the B-019 `symphony-shape` crate. It is a
schema_version 1.2 Outcome Capsule with structured `assumptions`, an empty `groundings`
list (no external sources required), and an `output_contract` whose `target` (`file_set`)
matches the single artifact type — exactly the shape the remediated Shape code now emits.

The acceptance list a1..a7 maps one-to-one onto findings F1..F7 with their r1 severities
(F1, F5 = P0; the rest = P1). The remediation is graded in `remediation_grade.md`.
