---
schema_version: "1.2"
id: T-20260612-remediation-c021
title: "Remediate cycle-021 C1 + F1-F4 in the M7 Evolve Agent crates/symphony-evolve"
goal: "Close the cycle-021 escalation blocker (locale-dependent git error detection) and the four r1 escaped findings in crates/symphony-evolve with regression-test-backed evidence, driving the held delta to mergeable."
mode: relaxed
risk_level: low
non_goals:
  - "No linter change in this canary; remediation evidence must come from the remediated symphony-evolve crate."
  - "No Shape-agent or Grade-agent crate scope."
assumptions:
  - id: as1
    text: "The cycle-021 r1 findings F1-F4 plus the C1 escalation blocker are the complete remediation scope for this canary."
    source: "harness/evolve-loop/reviews/opensymphony/cycle-021/r1.md + r2.md"
    confirmed: true
    risk_if_wrong: "A missing finding would be falsely omitted from the canary; mitigated by mapping a1..a5 to C1,F1..F4 one-to-one."
  - id: as2
    text: "The truthful evidence source is the remediated symphony-evolve crate under /private/tmp/remediate-cycle-021."
    source: "/private/tmp/remediate-cycle-021/crates/symphony-evolve/src/{git_write.rs,memory.rs,critic.rs,batch.rs,lightweight.rs}"
    confirmed: true
    risk_if_wrong: "The grade could cite unimplemented behavior; mitigated by naming the exact regression tests in remediation_grade.md."
groundings: []
output_contract:
  target: file_set
  artifacts:
    - type: file_set
      path: "crates/symphony-evolve/"
provenance:
  source: agent_authored
verification:
  mode: agent-driven
  required_evidence:
    - cargo_nextest_workspace
    - grade_lint_v1_4_16_canary
acceptance:
  - id: a1
    severity: P0
    text: "C1: git error detection in crates/symphony-evolve/src/git_write.rs is locale-independent: every git invocation pins LC_ALL=C and LANG=C, and revert/conflict detection keys off exit status rather than localized error text; a regression test runs the detection path under a zh_CN.UTF-8 parent locale."
  - id: a2
    severity: P0
    text: "F1: D-P21 metadata is persisted post-commit: the artifact's commit_hash is patched from the pending placeholder to the real commit sha with a post-commit readback, revert_hint references that real sha, and L2 pattern artifacts carry the full D-P21 metadata block."
  - id: a3
    severity: P1
    text: "F2: the evolve critic and mechanical pre-filter are substantive: candidates without a source grade_completed/grade_result reference are rejected, validation text requires an observable anchor and is screened against the generic-template blacklist, claims inconsistent with the cited grade outcome are rejected, and every candidate gets a per-candidate structured verdict persisted in the evolve-log body."
  - id: a4
    severity: P0
    text: "F3: the evolve-log artifact is written through the same write-with-git path as candidate artifacts (git committed) and its frontmatter counts (total_candidates, l1_written, l2_written, skipped_per_recent_revert) reflect the actual batch results."
  - id: a5
    severity: P1
    text: "F4: the L0.5 lightweight memory write is git committed and idempotent: replaying the same digest produces no duplicate Recent Runs line in MEMORY.md and no duplicate recent-runs artifact."
---

# Remediation Outcome — cycle-021 C1 + F1-F4 (M7 Evolve Agent)

Scope: drive the escalated cycle-021 held delta (`bootstrap/cycle-021`, wip 4625b5c) to
mergeable by fixing the escalation blocker and all four r1 escaped findings at their
production loci in `crates/symphony-evolve/src/`, with one negative/regression test per
finding, under the full repo gate stack (build, fmt, clippy -D warnings, nextest,
verify-docs).
