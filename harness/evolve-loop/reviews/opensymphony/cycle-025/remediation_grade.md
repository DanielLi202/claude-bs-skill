# Remediation Grade — cycle-025 r1 F1-F5 + F7-F11 (UI-M3 Outcome ready, escalated delta driven to mergeable)

**cycle**: cycle-025
**task**: Stage-5 remediation of the held B-025 UI-M3 delta (apps/symphony-ui) — grade_round_0 fix directive F1-F5 + r1 escapes F7-F11
**branch**: `/private/tmp/remediate-cycle-025` `remediate/cycle-025` @ `4934046` (base: held `bootstrap/cycle-025` @ `df4eda6`)
**graded_at**: 2026-06-13
**grade_lint**: same-iteration canary for the v1.4.21 facets (run with --repo-root)

---

## grade_summary

```yaml
grade_summary:
  task_id: cycle-025-remediation
  round: 0
  risk_level: low
  p0_count: 0
  p1_count: 0
  p2_count: 0
  p3_count: 0
  overall_result: pass
  grade_verify_status: pass
  cargo_test: "pnpm vitest run (apps/symphony-ui) + cargo nextest run --workspace"
  cargo_test_pass: 294
  cargo_test_fail: 0
  notes: >
    All ten remediation acceptances (r1 F1-F5 directive + F7-F11 escapes) are covered by real
    regression tests (vitest 76/76 incl. the new cases; cargo nextest 218/218 untouched-Rust
    confirmation) under /private/tmp/remediate-cycle-025. Full gate stack green: pnpm typecheck
    exit 0, vitest 76/76, build exit 0 with dist/index.html emitted; cargo build/fmt/clippy
    -D warnings/nextest; bash scripts/verify-docs.sh exit 0. Frozen files byte-identical to the
    a0a3359 start commit; changes confined to apps/symphony-ui/src/**.
```

---

## acceptance_status

```yaml
acceptance_status:
  - id: a1
    status: pass
    severity: P1
    text: "F1 stable empty run-state snapshot"
    evidence_ref: "pnpm vitest 'outcome-store: returns a stable empty run-state snapshot for unknown runs'"
  - id: a2
    status: pass
    severity: P1
    text: "F2 completeShellClient absorbs the frozen shapeqa.test.tsx"
    evidence_ref: "pnpm vitest 'app-shell-client: completes optional outcome command methods for non-outcome test clients'; frozen src/shape/shapeqa.test.tsx passes byte-identical; tsc exit 0"
  - id: a3
    status: pass
    severity: P1
    text: "F3 typed mocks + node-globals declarations; typecheck green"
    evidence_ref: "tsc --noEmit exit 0; pnpm vitest 'capsule-unavailable: renders an honest unavailable card and keeps fixture text out of production source'"
  - id: a4
    status: pass
    severity: P1
    text: "F4 schema-true string llm_judge criteria preview"
    evidence_ref: "pnpm vitest 'capsule-malformed: previews schema-true llm_judge criteria and falls back for malformed criteria'"
  - id: a5
    status: pass
    severity: P1
    text: "F5 outcome-secret-redaction coverage"
    evidence_ref: "pnpm vitest 'outcome-secret-redaction: redacts SymphonyApiError details from DOM, console capture, and outcome store snapshots'"
  - id: a6
    status: pass
    severity: P1
    text: "F7 capsuleModel as schema-v1.2 guard"
    evidence_ref: "pnpm vitest 'capsule-malformed: guards schema-v1.2 top-level fields, controlled tags, high-risk actions, and source-aware groundings'"
  - id: a7
    status: pass
    severity: P1
    text: "F8 tags chips rendered when non-empty"
    evidence_ref: "pnpm vitest 'capsule-tags: renders controlled non-empty outcome tags as chips and hides the row when empty'"
  - id: a8
    status: pass
    severity: P1
    text: "F9 stale detail vs snapshot state authority"
    evidence_ref: "pnpm vitest 'stale-run-detail: ignores stale outcome_ready detail after a fresher snapshot leaves shape'"
  - id: a9
    status: pass
    severity: P1
    text: "F10 pessimistic Re-shape/reject discipline"
    evidence_ref: "pnpm vitest 'reshape-pessimistic: keeps re-shape pending scoped, catches failures inline, and re-enables the control' + 'handles assumption reject re-shape failures without leaving the reject control disabled'"
  - id: a10
    status: pass
    severity: P1
    text: "F11 conflict-refetch failure path"
    evidence_ref: "pnpm vitest 'execute-conflict: clears pending and renders an inline error when the conflict refetch fails'"
```

---

## spec_compliance_matrix

```yaml
spec_compliance_matrix:
  - acceptance_id: a1
    spec_ref: "React 19 useSyncExternalStore snapshot stability (tech-stack.yaml frontend_locked) + grade_round_0.md fix directive item 1"
    status: pass
    severity_if_fail: P1
    evidence_ref: "src/lib/store/outcomeStore.ts module-level EMPTY_RUN_STATE constant; useOutcomeState selects state.runs[runId] ?? EMPTY_RUN_STATE. Test: 'returns a stable empty run-state snapshot for unknown runs' asserts referential identity across renders."
  - acceptance_id: a2
    spec_ref: "grade_round_0.md fix directive item 2 + capsule a12 freeze (src/shape/shapeqa.test.tsx byte-identical)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "src/shell/AppShell.tsx ShellClient = required-4 Pick & Partial Pick<execute|reShape|editOutcome>; useMemo(completeShellClient) fills the optionals with throwing 'unavailable in test client' stubs mirroring App.tsx completeClient. Test: 'completes optional outcome command methods for non-outcome test clients'; the frozen shapeqa.test.tsx suite passes unmodified."
  - acceptance_id: a3
    spec_ref: "grade_round_0.md fix directive items 4-5 (typed mocks; additive node-globals declarations)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "src/outcome/outcome.test.tsx typed vi.fn implementations in clientFor and SymphonyClient-typed overrides at the 4 sites; src/test/node-globals.d.ts additive readdirSync/statSync (node:fs) + join (node:path). pnpm run typecheck exit 0."
  - acceptance_id: a4
    spec_ref: "docs/architecture/schemas/outcome-capsule.md §3.4 llm_judge criteria (string; legacy array tolerated)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "src/outcome/capsuleModel.ts acceptancePreview prefers the first non-empty line of a schema-true string criteria, tolerates the legacy array shape, else renders the honest unavailable preview. Test: 'previews schema-true llm_judge criteria and falls back for malformed criteria'."
  - acceptance_id: a5
    spec_ref: "cycle-025 outcome.md risk_surface secret_leakage (new user-visible error/log surfaces must never expose a token)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "outcome-secret-redaction describe plants sk-test token in SymphonyApiError.details (bare, JSON, Authorization: Bearer), drives the execute failure path, and asserts all three shapes absent from document.body.textContent, captured console lines, and JSON.stringify of the outcome store snapshot."
  - acceptance_id: a6
    spec_ref: "docs/architecture/schemas/outcome-capsule.md schema v1.2 §2/§3/§4/§9/§10 — capsuleModel narrowing layer as the input_validation_or_schema guard (r1 F7)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "src/outcome/capsuleModel.ts validates the schema_version top-level field, the iteration field, and the output_contract block (absence degrades to the honest malformed card state); high_risk_actions rows take the §4 action enum (deploy/delete/db_write/external_api/payment/merge_pr) and out-of-enum action strings degrade to malformed rows; tags are checked against the controlled vocabulary (tdd/exploratory/dogfood/migration/experiment) with unknown tags flagged honestly; groundings rows enforce source_type-aware locators (url-sourced requires url, path-sourced requires path) and supports[] must be non-empty; the canonical outcome.test.tsx fixture is itself a schema-valid fixture passing the full guard. Test: 'guards schema-v1.2 top-level fields, controlled tags, high-risk actions, and source-aware groundings'."
  - acceptance_id: a7
    spec_ref: "docs/ux/prototype/screens/outcome.jsx ('Real outcome.tags[] surfaces here when non-empty') + outcome-capsule.md tags vocabulary (r1 F8)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "src/outcome/OutcomeReadyCard.tsx renders a visible tags chip row when model.tags is non-empty — the dogfood fixture renders its tag chips on the card — and when tags are empty/absent the row is hidden (nothing rendered, calm-tone). Test: 'renders controlled non-empty outcome tags as chips and hides the row when empty'."
  - acceptance_id: a8
    spec_ref: "cycle-025 outcome.md 'UI MUST NOT fabricate stage transitions' + api-contract §3.1/§3.2 read-path truth (r1 F9)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "DA-30 display contract holds during this dataflow change: throughout the detail refetch retry the existing snapshot remains rendered in the Inspector and affected state regions; the loading panels are scoped to the initial load with no prior snapshot and are not replacements for an existing snapshot — locked by the frozen B-022 'swr-snapshot' substrate suite, green in this same vitest run. Stale-detail dataflow fix: src/shell/AppShell.tsx detail-fetch effect now keys on the snapshot revision and invalidates stale detail; src/shell/Inspector.tsx ignores RunDetail once the snapshot has left shape or carries a newer revision; src/outcome/OutcomeActions.tsx derives the Execute If-Match revision from the freshest known truth. Test: 'ignores stale outcome_ready detail after a fresher snapshot leaves shape' — a snapshot at revision N+1 / conduct.probing with stale detail at N / outcome_ready renders the conduct stage and withholds the stale If-Match."
  - acceptance_id: a9
    spec_ref: "docs/architecture/api-contract.md §4.0 (re-shape mode=continue PESSIMISTIC, If-Match REQUIRED) + docs/architecture/ui-responsiveness.md scoped disable + inline failure (r1 F10)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "The secondary Re-shape button and the assumption Reject control are PESSIMISTIC: src/lib/store/outcomeStore.ts adds a scoped re-shape pending/error state (independent of Execute's), src/outcome/OutcomeActions.tsx + OutcomeReadyCard.tsx disable the affected region controls while pending, catch rejections into inline error copy naming the failed re-shape call, and re-enable after failure; the request carries If-Match: <revision>. Tests: 'keeps re-shape pending scoped, catches failures inline, and re-enables the control'; 'handles assumption reject re-shape failures without leaving the reject control disabled'. Pending dismissal-path coverage (Escape, overlay-backdrop click, route-surface change) is not_applicable here: re-shape and reject are plain inline region buttons that lack any dismissable surface, and pending is store-scoped per run id. scope_basis_ref: docs/architecture/api-contract.md §4.0 're-shape continue is PESSIMISTIC with modal explicitly excluded' and docs/ux/design-brief.md §10.9 outcome-ready button pairing. The Execute region's own dismissal coverage is provided separately by the execute-pending-dismissal suite."
  - acceptance_id: a10
    spec_ref: "docs/architecture/api-contract.md §1.5 409 revision_conflict envelope + recommended refetch recovery (r1 F11)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "src/outcome/OutcomeActions.tsx wraps the 409 revision_conflict refetch in its own failure handling: when the conflict refetch (the recovery GET) fails, pending is cleared (status reset to idle-with-error) and an inline error renders in the Execute region — the region is never stranded pending. Test: 'clears pending and renders an inline error when the conflict refetch fails'."
```

---

## negative_regression_tests

```yaml
negative_regression_tests:
  - acceptance_id: a1
    status: pass
    severity_if_fail: P1
    scenario: "unknown runId selected repeatedly — snapshot must be referentially stable (the round-0 crash class)"
    evidence_ref: "pnpm vitest 'returns a stable empty run-state snapshot for unknown runs'"
  - acceptance_id: a2
    status: pass
    severity_if_fail: P1
    scenario: "frozen 4-method test client mounts AppShell; calling an absent outcome method throws the typed 'unavailable in test client' stub error instead of undefined-call"
    evidence_ref: "pnpm vitest 'completes optional outcome command methods for non-outcome test clients'"
  - acceptance_id: a3
    status: pass
    severity_if_fail: P1
    scenario: "tsc strict over the full suite incl. frozen shapeqa.test.tsx (the 22-error baseline class)"
    evidence_ref: "pnpm run typecheck exit 0 (was exit 2 with TS2739/TS2322 on the held delta)"
  - acceptance_id: a4
    status: pass
    severity_if_fail: P1
    scenario: "malformed llm_judge criteria (neither string nor array) must fall back honestly, not crash or fabricate"
    evidence_ref: "pnpm vitest 'previews schema-true llm_judge criteria and falls back for malformed criteria'"
  - acceptance_id: a5
    status: pass
    severity_if_fail: P1
    scenario: "cleartext token probe in bare, JSON, and Bearer shapes through the rejected execute path"
    evidence_ref: "pnpm vitest 'redacts SymphonyApiError details from DOM, console capture, and outcome store snapshots'"
  - acceptance_id: a6
    status: pass
    severity_if_fail: P1
    scenario: "capsules missing schema_version/iteration/output_contract, carrying unknown tags, out-of-enum high_risk_actions ('execute', 'second check'), url-typed groundings without url, and empty supports[] must all degrade to honest malformed states"
    evidence_ref: "pnpm vitest 'guards schema-v1.2 top-level fields, controlled tags, high-risk actions, and source-aware groundings' + 'degrades malformed sections and rows without dropping valid rows' + 'marks a non-array acceptance section malformed'"
  - acceptance_id: a7
    status: pass
    severity_if_fail: P1
    scenario: "empty tags must render NO row (calm-tone negative)"
    evidence_ref: "pnpm vitest 'renders controlled non-empty outcome tags as chips and hides the row when empty' (empty branch assertion)"
  - acceptance_id: a8
    status: pass
    severity_if_fail: P1
    scenario: "stale detail at revision N/outcome_ready with snapshot at N+1/conduct.probing — must not render ghost outcome_ready nor send If-Match: N"
    evidence_ref: "pnpm vitest 'ignores stale outcome_ready detail after a fresher snapshot leaves shape'"
  - acceptance_id: a9
    status: pass
    severity_if_fail: P1
    scenario: "re-shape transport rejection — inline error renders, control re-enables, no unhandled rejection; reject route same"
    evidence_ref: "pnpm vitest 'keeps re-shape pending scoped, catches failures inline, and re-enables the control'; 'handles assumption reject re-shape failures without leaving the reject control disabled'"
  - acceptance_id: a10
    status: pass
    severity_if_fail: P1
    scenario: "409 followed by a FAILING recovery GET — pending cleared and inline error instead of infinite pending"
    evidence_ref: "pnpm vitest 'clears pending and renders an inline error when the conflict refetch fails'"
```

---

## execute/pending dismissal coverage (DA-28 PESSIMISTIC)

The Execute button's PESSIMISTIC pending lock retains its dismissal-path negatives from the
delta: Escape, overlay/backdrop stray clicks, and run-selection (surface) change are all inert
while pending and no global overlay renders — pnpm vitest 'execute-pending-dismissal: keeps
pending locked across Escape, stray clicks, run selection changes, and renders no overlay'.
The Execute command itself sends If-Match: <freshest revision> with an empty body
('sends execute through the transport with If-Match and an empty body'), is scoped-disabled
while pending, renders inline error copy for typed failures incl. the 428 envelope
('renders a typed inline error for a server 428 envelope'), and its missing-revision guard
throws client-side before transport ('disables Execute without a local revision and
client.execute throws before transport'). Catch/rejection coverage for the Execute promise
chain is proven by the conflict and redaction suites driving rejected transports.

Honesty seams: the daemon's run_command handler remains a projection stub pending the Shape
backend — post-202 rendering re-reads ONLY refetched daemon truth and the unchanged-stage copy
names the boundary (missing_upstream: B-019); capsule fixtures live in test files only and flow
through the §3.2-typed mocked client at the production read-path seam (no production fixture
text — 'renders an honest unavailable card and keeps fixture text out of production source').

---

## secret_leakage_audit

```yaml
secret_leakage_audit:
  status: pass
  evidence_ref: "pnpm vitest 'outcome-secret-redaction: redacts SymphonyApiError details from DOM, console capture, and outcome store snapshots'"
  cleartext_secret_probe: pass
  checked_surfaces:
    - "rendered DOM (document.body.textContent)"
    - "captured console.error/warn lines"
    - "serialized outcome store snapshot (JSON.stringify dump)"
  notes: >
    The probe plants an sk-test token in SymphonyApiError.details in all three shapes — the
    bare token, the JSON token shape ('{"token":"sk-test-..."}' quoted-key form), and the
    Authorization: Bearer header text — drives the rejected execute path, and asserts none of
    the three shapes appears in the rendered DOM (document.body.textContent), the captured
    console.error/warn lines, or the serialized outcome store dump. No new token-handling code
    paths were added (transport frozen); the new user-visible surfaces (conflict copy, inline
    errors, store dumps) are the audited surfaces.
```

---

## dependency_spec_review

```yaml
dependency_spec_review:
  - status: pass
    severity_if_fail: P1
    spec_ref: "docs/architecture/tech-stack.yaml frontend_locked"
    evidence_ref: "apps/symphony-ui/package.json and pnpm-lock.yaml are byte-identical to the a0a3359 start commit (git diff empty for both); no new npm dependency, no version pin churn; React 19.2.6 / TypeScript 6.0.3 / Vite 8 / Zustand / Vitest pins unchanged per tech-stack.yaml frontend_locked."
  - status: pass
    severity_if_fail: P1
    spec_ref: "capsule a12 isolation (no Rust, no docs, no manifests)"
    evidence_ref: "git status confined to apps/symphony-ui/src/**; crates/**, src-tauri/**, docs/**, scripts/**, .bootstrap* untouched; cargo nextest 218/218 confirms the Rust workspace is unaffected."
```

---

## verdict

All ten r1 findings closed with per-finding regression tests; full gate stack green
(pnpm typecheck/test/build; cargo build/fmt/clippy/nextest; verify-docs). The delta is
mergeable pending the fresh-context r1-verify pass.
