# Remediation Grade — cycle-024 F1-F4 (UI-M2 create + Shape Q&A)

**cycle**: cycle-024
**task**: Stage-5 remediation of F1-F4 in the UI-M2 create + Shape Q&A frontend (apps/symphony-ui + symphony-api)
**branch**: `/private/tmp/remediate-cycle-024` `remediate/cycle-024` @ `4e7db98`
**graded_at**: 2026-06-13
**grade_lint**: same-iteration canary for the v1.4.20 facets (run with --repo-root)

---

## grade_summary

```yaml
grade_summary:
  task_id: cycle-024-remediation
  round: 0
  risk_level: low
  p0_count: 0
  p1_count: 0
  p2_count: 0
  p3_count: 0
  overall_result: pass
  grade_verify_status: pass
  cargo_test: "pnpm vitest run (apps/symphony-ui) + cargo nextest run --workspace"
  cargo_test_pass: 268
  cargo_test_fail: 0
  notes: >
    All four remediation acceptances (r1 F1-F4) are covered by real regression tests
    (vitest 50/50 incl. new cases; cargo nextest 218/218 incl. new api_contract tests)
    under /private/tmp/remediate-cycle-024. Full gate stack green: pnpm frozen install,
    typecheck, vitest, build; cargo build/fmt/clippy -D warnings/nextest; verify-docs.
```

---

## acceptance_status

```yaml
acceptance_status:
  - id: a1
    status: pass
    severity: P1
    text: "F1 honest production Q&A provider state closed"
    evidence_ref: "pnpm vitest run: 'production default provider returns typed B-019 unavailable instead of null'; 'renders default-provider B-019 pending state'"
  - id: a2
    status: pass
    severity: P1
    text: "F2 answer persistence without merge over-claims closed"
    evidence_ref: "cargo nextest: answer_qa_rejects_malformed_body_and_persists_submitted_answers_without_merge_claim; pnpm vitest: 'records without claiming merge'"
  - id: a3
    status: pass
    severity: P1
    text: "F3 Advanced field plumbing closed"
    evidence_ref: "pnpm vitest: 'builds create payloads with advanced selections only when not inherited'; cargo nextest: create_persists_advanced_options_exposes_projection_and_rejects_invalid_enums"
  - id: a4
    status: pass
    severity: P1
    text: "F4 pessimistic dismissal lock closed"
    evidence_ref: "pnpm vitest: 'locks dismissal while pending'; 'keeps the modal open with draft and inline error when pessimistic create fails'"
```

---

## spec_compliance_matrix

```yaml
spec_compliance_matrix:
  - acceptance_id: a1
    spec_ref: "docs/ops/roadmap.md §3.8 (Shape Q&A panel) scoped against the unbuilt B-019 upstream"
    status: pass
    severity_if_fail: P1
    evidence_ref: "qaModel.ts production default provider now returns a typed result { kind: 'unavailable', dependency: 'B-019' } — the production wiring path is the default provider itself, and the row is honestly scoped fixture-only for rendered questions with missing_upstream: B-019. ShapeQaPanel renders the explicit 'Shape Q&A pending the Shape agent backend (B-019)' state, visibly distinct from an empty question list. Tests: 'production default provider returns typed B-019 unavailable instead of null'; 'renders default-provider B-019 pending state'. The fixture-injected provider seam is unchanged for B-019."
    notes: >
      The round-0 escape (null provider; fixture tests passing production-sounding rows)
      is closed by honesty: no production question rendering is claimed; the unavailable
      state names the blocking backlog id.
  - acceptance_id: a2
    spec_ref: "docs/architecture/api-contract.md answer-qa + §1.5 envelope"
    status: pass
    severity_if_fail: P1
    evidence_ref: "handlers/mod.rs answer-qa handler now performs request-body consumption: it validates answers (malformed answers.question_id / answers.answer_type rejected with §1.5 envelopes) and persists a typed qa_answers_submitted ledger event through the production client-to-handler request path and the existing event append machinery (the outcome-write/merge path is explicitly NOT claimed — merge is unavailable pending B-019, missing_upstream: B-019). ShapeQaPanel submit renders 'answers recorded — merge pending Shape agent (B-019)'. Tests: answer_qa_rejects_malformed_body_and_persists_submitted_answers_without_merge_claim (nextest); 'records without claiming merge' (vitest)."
    notes: >
      Recorded ≠ merged is now explicit at both loci (handler + UI); no fixture-passed
      merge claim survives.
  - acceptance_id: a3
    spec_ref: "docs/decisions/ux.md UX-45 (vendor/model/effort/persona; persona Shape-only; inherit semantics)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "createModel.ts/client.ts build the create request with all four Advanced fields riding the production request path (inherit = field omitted; persona only for Shape-first tasks); handlers/mod.rs create handler performs request-body consumption (validates enums; §1.5 rejection for invalid values) and persists the options; projection.rs exposes them on the run detail so the future Shape agent can consume them. Tests: 'builds create payloads with advanced selections only when not inherited' (vitest); create_persists_advanced_options_exposes_projection_and_rejects_invalid_enums (nextest)."
    notes: >
      Presence-only controls are gone: choices now traverse client-to-handler and persist;
      no fake defaults (inherit stays inherit).
  - acceptance_id: a4
    spec_ref: "docs/architecture/ui-responsiveness.md DA-28 (create = PESSIMISTIC) + api-contract §4.0"
    status: pass
    severity_if_fail: P1
    evidence_ref: "CreateTaskModal/createStore/AppShell: while the PESSIMISTIC create request is pending, every dismissal path is inert — Escape is ignored, overlay/backdrop click is ignored, and route/surface change is blocked for the modal surface; on failure the modal stays open with the inline error and the draft preserved. Tests: 'locks dismissal while pending' (covers Escape + overlay + route/surface change); 'keeps the modal open with draft and inline error when pessimistic create fails'."
```

---

## negative_regression_tests

```yaml
negative_regression_tests:
  - id: nr1
    acceptance_id: a1
    scenario: "production default provider must not return null/blank: typed unavailable result with dependency B-019; panel renders the pending-upstream state distinct from 'no questions'"
    test_name: "shapeqa tests > production default provider returns typed B-019 unavailable instead of null; renders default-provider B-019 pending state"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run"
  - id: nr2
    acceptance_id: a2
    scenario: "malformed answers body rejected per §1.5; well-formed answers persisted as a typed qa_answers_submitted event; no merge claim emitted"
    test_name: "api_contract > answer_qa_rejects_malformed_body_and_persists_submitted_answers_without_merge_claim"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest run --workspace"
  - id: nr3
    acceptance_id: a2
    scenario: "UI submit shows recorded-not-merged (merge pending B-019), never a merged claim"
    test_name: "shapeqa tests > records without claiming merge"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run"
  - id: nr4
    acceptance_id: a3
    scenario: "inherit fields are omitted from the create payload; set fields ride the request; persona only for Shape-first tasks"
    test_name: "create tests > builds create payloads with advanced selections only when not inherited"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run"
  - id: nr5
    acceptance_id: a3
    scenario: "backend persists advanced options, projection exposes them, invalid enum values rejected"
    test_name: "api_contract > create_persists_advanced_options_exposes_projection_and_rejects_invalid_enums"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest run --workspace"
  - id: nr6
    acceptance_id: a4
    scenario: "while pending: Escape inert, overlay/backdrop click inert, route/surface change blocked; draft intact"
    test_name: "create tests > locks dismissal while pending"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run"
  - id: nr7
    acceptance_id: a4
    scenario: "failure after pending keeps the modal open with inline error + preserved draft (no silent reset)"
    test_name: "create tests > keeps the modal open with draft and inline error when pessimistic create fails"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run"
```

---

## secret_leakage_audit

```yaml
secret_leakage_audit:
  status: pass
  evidence_ref: "manual review of the remediation diff (apps/symphony-ui/src/{shape,create}, crates/symphony-api/src/{handlers,projection}) plus the full test suites"
  checked_surfaces:
    - "apps/symphony-ui/src/shape/qaModel.ts"
    - "apps/symphony-ui/src/create/createModel.ts"
    - "crates/symphony-api/src/handlers/mod.rs"
    - "crates/symphony-api/src/projection.rs"
  cleartext_secret_probe: not_applicable
  rationale: >
    The remediation adds Q&A unavailable states, answer/option persistence, and modal
    dismissal locking; it introduces no credential, bearer-token, API-key, OAuth,
    auth-header, logging, or redaction surface (auth middleware untouched), so cleartext
    secret probing is not applicable to this delta.
```

---

## dependency_spec_review

```yaml
dependency_spec_review:
  - name: "(no new dependencies)"
    spec_ref: "docs/architecture/tech-stack.yaml frontend_locked + workspace Cargo.toml"
    status: pass
    severity_if_fail: P1
    evidence_ref: "git diff main..remediate/cycle-024 -- apps/symphony-ui/package.json apps/symphony-ui/pnpm-lock.yaml Cargo.toml Cargo.lock is empty; canonical exact pins + packageManager pnpm@10.33.0 intact; dependencyPins.test.ts green in the suite"
    notes: >
      No dependency or pin change anywhere in the remediation.
```

---

## Gate evidence

- `pnpm install --frozen-lockfile` → Done (pnpm v10.33.0)
- `pnpm typecheck` (tsc --noEmit) → exit 0
- `pnpm test` (vitest) → 50/50 passed (5 files)
- `pnpm build` → built green
- `RUSTC_WRAPPER= cargo build --workspace` → Finished
- `RUSTC_WRAPPER= cargo fmt --all --check` → exit 0
- `RUSTC_WRAPPER= cargo clippy --workspace --all-targets -- -D warnings` → Finished, no warnings
- `RUSTC_WRAPPER= cargo nextest run --workspace` → 218 passed, 1 skipped
- `bash scripts/verify-docs.sh` → verify-docs OK
