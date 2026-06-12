---
schema_version: "1.2"
id: T-20260612-remediation-c023
title: "Remediate cycle-023 F1-F5 in the UI-M1 app shell (apps/symphony-ui, React/Vite frontend)"
goal: "Close the five r1-escaped findings in the merged B-023 UI-M1 shell: full terminal-state classification, Inspector required state regions, DA-30 retry snapshot retention, Attention Shelf actions, and verbose phase labels."
mode: relaxed
risk_level: low
non_goals:
  - "No linter change in this canary; remediation evidence must come from the remediated apps/symphony-ui shell code."
  - "No tech-stack.yaml / governance doc changes; canonical pins untouched."
assumptions:
  - id: as1
    text: "The cycle-023 r1 findings F1-F5 are the complete remediation scope for this canary."
    source: "harness/evolve-loop/reviews/opensymphony/cycle-023/r1.md"
    confirmed: true
    risk_if_wrong: "A missing finding would be falsely omitted; mitigated by mapping a1..a5 to F1..F5 one-to-one."
  - id: as2
    text: "The truthful evidence source is the remediated shell under /private/tmp/remediate-cycle-023/apps/symphony-ui."
    source: "/private/tmp/remediate-cycle-023/apps/symphony-ui/src/shell/{derive.ts,Inspector.tsx,AppShell.tsx,AttentionShelf.tsx,RunCard.tsx}"
    confirmed: true
    risk_if_wrong: "The grade could cite unimplemented behavior; mitigated by naming the exact vitest regression tests."
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
    - grade_lint_v1_4_19_canary
acceptance:
  - id: a1
    severity: P1
    text: "F1: run-state classification covers the complete behavior.md terminal set — done, failed, superseded, canceled/cancelled, parked, needs_human — so no terminal run is counted Active or sorted as running; needs_human surfaces as blocking."
  - id: a2
    severity: P1
    text: "F2: the Inspector renders the design-brief §4.5 / UX-53 required state regions — the blocking NEEDS YOU callout and the running RUN IN FLIGHT tile — driven by the real run snapshot."
  - id: a3
    severity: P1
    text: "F3: per DA-30, retry/degraded refresh keeps the last-known snapshot rendered in the Ledger and Inspector; loading/error panels are scoped to initial load with no prior snapshot."
  - id: a4
    severity: P2
    text: "F4: the Attention Shelf provides the design-brief §4.6 actions — jump to first (selects the first blocking run) and show all (applies the blocking run filter)."
  - id: a5
    severity: P2
    text: "F5: verbose phase pellets render the visible Shape/Conduct/Grade labels per UX-11/prototype; compact pellets stay glyph-only."
---

# Remediation Outcome — cycle-023 F1-F5 (UI-M1 app shell)

Scope: fix the five r1-escaped findings in the merged B-023 shell at their production
loci (derive.ts / Inspector.tsx / AppShell.tsx / AttentionShelf.tsx / RunCard.tsx +
styles), one regression test per finding, under the full frontend + root gate stack.
