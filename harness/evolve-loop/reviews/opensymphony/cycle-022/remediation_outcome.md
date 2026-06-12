---
schema_version: "1.2"
id: T-20260612-remediation-c022
title: "Remediate cycle-022 F1-F3 in the UI-M0 frontend (apps/symphony-ui, React/Vite/Tauri scaffold)"
goal: "Close the three r1-escaped P1s in the merged B-022 UI-M0 delivery: real SSE EventSource reconnect lifecycle (DA-30), fail-closed instance-identity mismatch recovery, and canonical dependency pins per tech-stack.yaml frontend_locked."
mode: relaxed
risk_level: low
non_goals:
  - "No linter change in this canary; remediation evidence must come from the remediated apps/symphony-ui code."
  - "No tech-stack.yaml / governance doc changes (a canonical version change needs a council T-batch)."
assumptions:
  - id: as1
    text: "The cycle-022 r1 findings F1-F3 are the complete remediation scope for this canary."
    source: "harness/evolve-loop/reviews/opensymphony/cycle-022/r1.md"
    confirmed: true
    risk_if_wrong: "A missing finding would be falsely omitted; mitigated by mapping a1..a3 to F1..F3 one-to-one."
  - id: as2
    text: "The truthful evidence source is the remediated frontend under /private/tmp/remediate-cycle-022/apps/symphony-ui."
    source: "/private/tmp/remediate-cycle-022/apps/symphony-ui/src/lib/{sse/connection.ts,api/transport.ts,api/errors.ts,store/connectionStore.ts}"
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
    - grade_lint_v1_4_17_canary
acceptance:
  - id: a1
    severity: P1
    text: "F1: a 30s SSE heartbeat miss triggers a real reconnect lifecycle per DA-30 — the stale EventSource is closed/disposed, the source factory is invoked again to create a new EventSource with backoff, a full GET state refresh runs only after the NEW connection is established, events arriving on the stale old source cannot mark the connection healthy, and the snapshot is retained with writes disabled while disconnected."
  - id: a2
    severity: P1
    text: "F2: an instance-id identity mismatch forces stale-daemon recovery — the mismatched HTTP response is rejected with a typed error and never returned as data, a callback-only side effect is insufficient, connected()/write re-enable is blocked until a fresh MATCHING identity is observed, and an SSE connected event carrying a mismatched identity is not accepted as success."
  - id: a3
    severity: P1
    text: "F3: shipped frontend dependencies match the canonical docs/architecture/tech-stack.yaml frontend_locked versions — package.json pins exact canonical versions, pnpm-lock.yaml resolutions equal them, and the packageManager field pins the canonical pnpm."
---

# Remediation Outcome — cycle-022 F1-F3 (UI-M0 frontend)

Scope: fix the three r1-escaped P1s in the merged B-022 UI-M0 delivery at their
production loci in apps/symphony-ui (connection.ts / transport.ts / errors.ts /
connectionStore.ts / package.json / pnpm-lock.yaml), one regression test per finding,
under the full frontend (pnpm install --frozen-lockfile, typecheck, vitest, build) and
root (cargo build/fmt/clippy/nextest, verify-docs) gate stack.
