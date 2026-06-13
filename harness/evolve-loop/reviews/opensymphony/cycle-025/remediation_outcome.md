---
schema_version: "1.2"
id: T-20260613-remediation-c025
title: "Remediate cycle-025 r1 findings (F1-F5 directive + F7-F11 escapes) in the held UI-M3 Outcome-ready delta (apps/symphony-ui)"
goal: "Drive the escalated, held bootstrap/cycle-025 delta to mergeable: apply the probe-validated grade_round_0 fix directive (F1-F5) and close the five r1-escaped P1s — capsuleModel as a real outcome-capsule.md schema-v1.2 input_validation_or_schema guard, outcome.tags[] chips rendering, stale RunDetail vs snapshot state authority, pessimistic Re-shape/reject discipline, and the Execute 409 conflict-refetch failure path."
mode: relaxed
risk_level: low
non_goals:
  - "No Shape agent backend work (B-019/M4 unbuilt; edit-outcome merge semantics and the daemon capsule projection stay pending it — honest states name missing_upstream: B-019)."
  - "No linter change in this canary; evidence comes from the remediated code under the NEW v1.4.21 gates."
  - "No changes outside apps/symphony-ui/src/** (capsule a12 isolation; frozen files stay byte-identical)."
assumptions:
  - id: as1
    text: "The cycle-025 grade_round_0 fix directive items 1-5 (F1-F5) plus r1 escaped findings F7-F11 are the complete remediation scope; F6 (OutcomeDraft removal) stays P2-deferred per the cycle's own grade."
    source: "harness/evolve-loop/reviews/opensymphony/cycle-025/r1.md + OpenSymphony .prompts/dogfood/cycle-025/grade_round_0.md"
    confirmed: true
    risk_if_wrong: "A missing finding would be falsely omitted; mitigated by mapping a1..a10 to F1..F5,F7..F11 and the fresh-context r1-verify pass."
  - id: as2
    text: "The truthful evidence source is the remediated code on remediate/cycle-025 @ 4934046 under /private/tmp/remediate-cycle-025."
    source: "/private/tmp/remediate-cycle-025/apps/symphony-ui/src/{outcome,shell,lib}/"
    confirmed: true
    risk_if_wrong: "The grade could cite unimplemented behavior; mitigated by naming exact vitest test names per finding."
groundings: []
output_contract:
  target: file_set
  artifacts:
    - type: file_set
      path: "apps/symphony-ui/"
provenance:
  source: agent_authored
verification:
  mode: agent-driven
  required_evidence:
    - pnpm_vitest_run
    - pnpm_typecheck_and_build
    - cargo_nextest_workspace
    - grade_lint_v1_4_21_canary
acceptance:
  - id: a1
    severity: P1
    text: "F1: useOutcomeState returns a stable module-level EMPTY_RUN_STATE snapshot for unknown runs (no per-render fresh object; OutcomeActions no longer crashes on the unstable selector)."
  - id: a2
    severity: P1
    text: "F2: AppShell accepts the required-4 client Pick plus Partial execute/reShape/editOutcome and completes the optionals via useMemo(completeShellClient) throwing stubs, absorbing the frozen byte-identical src/shape/shapeqa.test.tsx."
  - id: a3
    severity: P1
    text: "F3: outcome.test.tsx uses typed vi.fn mocks (clientFor + 4 override sites), correct unmount ordering and duplicate-element queries, and src/test/node-globals.d.ts gains additive readdirSync/statSync/join declarations; typecheck exits 0."
  - id: a4
    severity: P1
    text: "F4: capsuleModel acceptancePreview prefers schema-true STRING llm_judge criteria (first non-empty line), tolerates the legacy array shape, and falls back to the honest unavailable preview otherwise."
  - id: a5
    severity: P1
    text: "F5: the outcome-secret-redaction suite plants a token in SymphonyApiError.details and proves bare, JSON, and Authorization: Bearer shapes are absent from the rendered DOM, captured console lines, and the serialized outcome store snapshot."
  - id: a6
    severity: P1
    text: "F7: capsuleModel is a real outcome-capsule.md schema-v1.2 input_validation_or_schema guard — missing schema_version/id/iteration/output_contract degrade to the honest malformed state; tags outside the controlled vocabulary are flagged unknown (never trusted); high_risk_actions rows with action strings outside the §4 enum (deploy/delete/db_write/external_api/payment/merge_pr) are malformed; groundings enforce source_type-aware url/path locators; supports[] must be non-empty; the canonical test fixture is itself schema-valid."
  - id: a7
    severity: P1
    text: "F8: non-empty outcome.tags[] renders as a visible chips row on the Outcome ready card (per docs/ux/prototype/screens/outcome.jsx); empty or absent tags render no row."
  - id: a8
    severity: P1
    text: "F9: a stale RunDetail can no longer override fresher snapshot truth — detail is refetched/invalidated on snapshot revision change and ignored once the snapshot leaves shape or carries a newer revision; Execute's If-Match always uses the freshest known revision."
  - id: a9
    severity: P1
    text: "F10: Re-shape (mode=continue) and the assumption Reject route are PESSIMISTIC: scoped pending state in outcomeStore, affected controls disabled while pending, failures caught into inline error copy naming the failed call, controls re-enabled after failure."
  - id: a10
    severity: P1
    text: "F11: Execute's 409 revision_conflict branch survives a failing conflict refetch — pending is cleared and an inline error renders instead of stranding the region pending forever."
---

# Remediation outcome — cycle-025 (escalated UI-M3 delta driven to mergeable)

Scope: the held bootstrap/cycle-025 delta (df4eda6) remediated on remediate/cycle-025 (4934046).
Gate stack: pnpm typecheck/test/build green (76/76) + cargo build/fmt/clippy/nextest (218 passed) +
verify-docs + the NEW bs-skill v1.4.21 grade_lint canary on this grade document.
