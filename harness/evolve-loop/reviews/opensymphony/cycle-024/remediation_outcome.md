---
schema_version: "1.2"
id: T-20260613-remediation-c024
title: "Remediate cycle-024 F1-F4 in the UI-M2 create + Shape Q&A frontend (apps/symphony-ui + symphony-api)"
goal: "Close the four r1-escaped P1s in the merged B-024 UI-M2 delivery: honest production Q&A provider state, answer persistence without merge over-claims, real Advanced field plumbing, and pessimistic-create dismissal locking."
mode: relaxed
risk_level: low
non_goals:
  - "No Shape agent backend work (B-019/M4 is unbuilt; merge semantics stay pending it)."
  - "No linter change in this canary; evidence comes from the remediated code."
assumptions:
  - id: as1
    text: "The cycle-024 r1 findings F1-F4 are the complete remediation scope."
    source: "harness/evolve-loop/reviews/opensymphony/cycle-024/r1.md"
    confirmed: true
    risk_if_wrong: "A missing finding would be falsely omitted; mitigated by mapping a1..a4 to F1..F4."
  - id: as2
    text: "The truthful evidence source is the remediated code under /private/tmp/remediate-cycle-024."
    source: "/private/tmp/remediate-cycle-024/apps/symphony-ui/src/{shape,create}/ + crates/symphony-api/src/handlers/mod.rs"
    confirmed: true
    risk_if_wrong: "The grade could cite unimplemented behavior; mitigated by naming exact regression tests."
groundings: []
output_contract:
  target: file_set
  artifacts:
    - type: file_set
      path: "apps/symphony-ui/"
    - type: file_set
      path: "crates/symphony-api/"
provenance:
  source: agent_authored
verification:
  mode: agent-driven
  required_evidence:
    - pnpm_vitest_run
    - cargo_nextest_workspace
    - grade_lint_v1_4_20_canary
acceptance:
  - id: a1
    severity: P1
    text: "F1: the PRODUCTION default Q&A provider returns a typed unavailable result (fixture-only rendering remains test-injected) and the panel renders an explicit pending state naming the missing upstream — missing_upstream: B-019 — visibly distinct from 'no questions'."
  - id: a2
    severity: P1
    text: "F2: the answer-qa handler consumes the request body (rejects malformed per §1.5) and persists submitted answers as a typed qa_answers_submitted ledger event via the production client-to-handler request path; the UI states answers are recorded with merge unavailable pending B-019 (no merge claim)."
  - id: a3
    severity: P1
    text: "F3: Advanced vendor/model/effort/persona selections ride the production create request path with request-body consumption by the handler and are persisted + exposed by the run projection (inherit = field omitted; persona Shape-only; invalid enums rejected)."
  - id: a4
    severity: P1
    text: "F4: the PESSIMISTIC create modal locks every dismissal path while pending — Escape, overlay/backdrop click, and route/surface change are inert — and failure keeps the modal open with the inline error and preserved draft."
---

# Remediation Outcome — cycle-024 F1-F4 (UI-M2 create + Shape Q&A)

Scope: close the scaffold-as-feature escapes honestly — production wiring where the
backend exists (answer persistence, Advanced field plumbing), explicit unavailable
states naming B-019 where it does not, and DA-28 pessimistic dismissal locking — one
regression test per finding, full gate stack green.
