# Remediation Grade — cycle-023 F1-F5 (UI-M1 app shell, apps/symphony-ui)

**cycle**: cycle-023
**task**: Stage-5 remediation of F1-F5 in the UI-M1 app shell (apps/symphony-ui, React/Vite frontend)
**branch**: `/private/tmp/remediate-cycle-023` `remediate/cycle-023` @ `a328a72`
**graded_at**: 2026-06-12
**grade_lint**: same-iteration canary for the v1.4.19 frontend facets (run with --repo-root)

---

## grade_summary

```yaml
grade_summary:
  task_id: cycle-023-remediation
  round: 0
  risk_level: low
  p0_count: 0
  p1_count: 0
  p2_count: 0
  p3_count: 0
  overall_result: pass
  grade_verify_status: pass
  cargo_test: "pnpm vitest run (apps/symphony-ui) + cargo nextest run --workspace"
  cargo_test_pass: 254
  cargo_test_fail: 0
  notes: >
    All five remediation acceptances (r1 F1-F5) are covered by real vitest regression
    tests (38/38, 7 new) under /private/tmp/remediate-cycle-023/apps/symphony-ui. Full
    gate stack green: pnpm install --frozen-lockfile, typecheck, vitest, build; cargo
    build/fmt/clippy -D warnings/nextest (216 passed, 1 skipped); verify-docs.
```

---

## acceptance_status

```yaml
acceptance_status:
  - id: a1
    status: pass
    severity: P1
    text: "F1 full terminal-state enum classification closed"
    evidence_ref: "pnpm vitest run: 'F1 terminal-states: failed, superseded, canceled, cancelled, parked and needs_human are excluded from Active counts and running sort'; 'F1 needs_human surfaces as blocking, not active'; 'F1 unknown stages do not default to an active Shape pellet'"
  - id: a2
    status: pass
    severity: P1
    text: "F2 Inspector required state regions closed"
    evidence_ref: "pnpm vitest run: 'F2 inspector-regions: blocking run renders the NEEDS YOU callout'; 'F2 inspector-regions: running run renders the RUN IN FLIGHT tile'; 'F2 inspector-regions: terminal run renders neither region'"
  - id: a3
    status: pass
    severity: P1
    text: "F3 DA-30 retry snapshot retention closed"
    evidence_ref: "pnpm vitest run: 'F3 stale-while-revalidate: retry failure preserves ledger and inspector when a snapshot exists'; 'F3 initial-load-error: error panels render when no prior snapshot exists'"
  - id: a4
    status: pass
    severity: P2
    text: "F4 Attention Shelf actions closed"
    evidence_ref: "pnpm vitest run: 'F4 attention-shelf-actions: jump-to-first selects and focuses the first blocking run'; 'F4 attention-shelf-actions: show-all applies the blocking run filter'"
  - id: a5
    status: pass
    severity: P2
    text: "F5 verbose phase labels closed"
    evidence_ref: "pnpm vitest run: 'F5 verbose-phase-pellets: verbose pellets render phase labels while compact pellets stay glyph-only'"
```

---

## spec_compliance_matrix

```yaml
spec_compliance_matrix:
  - acceptance_id: a1
    spec_ref: "docs/spec/behavior.md hot-loop terminal states; docs/decisions/ux.md UX-37"
    status: pass
    severity_if_fail: P1
    evidence_ref: "derive.ts now declares TerminalState = done | failed | superseded | canceled | cancelled | parked | needs_human and classifies every terminal run out of Active counts and running sort: done, failed, superseded, canceled and cancelled, parked, and needs_human are all terminal; needs_human additionally surfaces as blocking (blocking_on_user OR terminalState === needs_human). The active-Shape fallback for unknown macro stages is removed. Tests: 'F1 terminal-states...' covers each enum member; 'F1 needs_human surfaces as blocking, not active'; 'F1 unknown stages do not default to an active Shape pellet'."
    notes: >
      The round-0 escape (terminal-done-only classification inflating Active counts) is
      structurally gone; the enum is the complete behavior.md terminal set.
  - acceptance_id: a2
    spec_ref: "docs/ux/design-brief.md §4.5; docs/decisions/ux.md UX-53"
    status: pass
    severity_if_fail: P1
    evidence_ref: "Inspector.tsx renders the blocking NEEDS YOU callout (region-label '▴ NEEDS YOU') when the selected run blocks on the user, and the running RUN IN FLIGHT tile (heartbeat-dot region) when it is actively running — both driven by the run snapshot, neither rendered for terminal runs. Tests: 'F2 inspector-regions: blocking run renders the NEEDS YOU callout'; 'F2 ... running run renders the RUN IN FLIGHT tile'; 'F2 ... terminal run renders neither region'."
  - acceptance_id: a3
    spec_ref: "docs/architecture/api-contract.md DA-30 (~:417-425); docs/decisions/architecture.md DA-30"
    status: pass
    severity_if_fail: P1
    evidence_ref: "AppShell.tsx display state machine: when a snapshot exists, retry/degraded refresh keeps the last-known snapshot rendered in the Ledger and Inspector (snapshot retained; the degraded banner and reconnect indicators stay, writes disabled handling unchanged); loading and error panels are scoped to initial load with no prior snapshot and do not replace last-known state. Tests: 'F3 stale-while-revalidate: retry failure preserves ledger and inspector when a snapshot exists'; 'F3 initial-load-error: error panels render when no prior snapshot exists'."
    notes: >
      The round-0 escape (DegradedBanner retry set global loadStatus=loading/error and
      blanked both regions) is closed at the display-state locus.
  - acceptance_id: a4
    spec_ref: "docs/ux/design-brief.md §4.6"
    status: pass
    severity_if_fail: P2
    evidence_ref: "AttentionShelf.tsx now provides the jump to first action (selects and focuses the first blocking run) and the show all action (applies the blocking run filter to the run list); both wired to the shell store, absent when nothing needs attention. Tests: 'F4 attention-shelf-actions: jump-to-first selects and focuses the first blocking run'; 'F4 ... show-all applies the blocking run filter'."
  - acceptance_id: a5
    spec_ref: "docs/decisions/ux.md UX-11; docs/ux/prototype/atoms.jsx"
    status: pass
    severity_if_fail: P2
    evidence_ref: "RunCard.tsx verbose pellets render the visible Shape / Conduct / Grade labels alongside the sigils (inspector context); compact pellets stay glyph-only. Test: 'F5 verbose-phase-pellets: verbose pellets render phase labels while compact pellets stay glyph-only'."
```

---

## negative_regression_tests

```yaml
negative_regression_tests:
  - id: nr1
    acceptance_id: a1
    scenario: "each non-done terminal state — failed, superseded, canceled, cancelled, parked, needs_human — is excluded from Active counts and running sort (done already covered)"
    test_name: "shell.test.tsx > F1 terminal-states"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run; derive.ts terminalStates set covers the full enum"
  - id: nr2
    acceptance_id: a1
    scenario: "a needs_human run surfaces as blocking (attention), never active-running; unknown stages do not default to an active Shape pellet"
    test_name: "shell.test.tsx > F1 needs_human surfaces as blocking, not active; F1 unknown stages do not default to an active Shape pellet"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run; isBlocking includes terminalState === needs_human"
  - id: nr3
    acceptance_id: a2
    scenario: "non-blocking run does not render NEEDS YOU; terminal run renders neither NEEDS YOU nor RUN IN FLIGHT"
    test_name: "shell.test.tsx > F2 inspector-regions (blocking / running / terminal cases)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run; regions driven by run snapshot state"
  - id: nr4
    acceptance_id: a3
    scenario: "with a snapshot present, a failing retry keeps ledger/inspector content rendered — no loading/error replacement of the last-known snapshot"
    test_name: "shell.test.tsx > F3 stale-while-revalidate: retry failure preserves ledger and inspector when a snapshot exists"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run; snapshot retained during degraded retry"
  - id: nr5
    acceptance_id: a3
    scenario: "initial load with no prior snapshot still shows the error panel (loading/error panels initial-load scoped)"
    test_name: "shell.test.tsx > F3 initial-load-error: error panels render when no prior snapshot exists"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run"
  - id: nr6
    acceptance_id: a4
    scenario: "jump to first selects/focuses the first blocking run; show all applies the blocking filter; actions absent when nothing needs attention"
    test_name: "shell.test.tsx > F4 attention-shelf-actions (both actions)"
    status: pass
    severity_if_fail: P2
    evidence_ref: "pnpm vitest run"
  - id: nr7
    acceptance_id: a5
    scenario: "verbose pellets render Shape/Conduct/Grade labels; compact pellets remain glyph-only (no label leak)"
    test_name: "shell.test.tsx > F5 verbose-phase-pellets"
    status: pass
    severity_if_fail: P2
    evidence_ref: "pnpm vitest run"
```

---

## secret_leakage_audit

```yaml
secret_leakage_audit:
  status: pass
  evidence_ref: "manual review of /private/tmp/remediate-cycle-023/apps/symphony-ui/src/shell plus pnpm vitest run"
  checked_surfaces:
    - "apps/symphony-ui/src/shell/derive.ts"
    - "apps/symphony-ui/src/shell/Inspector.tsx"
    - "apps/symphony-ui/src/shell/AppShell.tsx"
    - "apps/symphony-ui/src/shell/AttentionShelf.tsx"
    - "apps/symphony-ui/src/shell/RunCard.tsx"
  cleartext_secret_probe: not_applicable
  rationale: >
    The remediation touches shell display/classification logic and CSS only; it
    introduces no credential, bearer-token, API-key, OAuth, auth-header, logging, or
    redaction surface (the token-out-of-webview trust model is untouched), so cleartext
    secret probing is not applicable to this delta.
```

---

## dependency_spec_review

```yaml
dependency_spec_review:
  - name: "(no new dependencies)"
    spec_ref: "docs/architecture/tech-stack.yaml frontend_locked; apps/symphony-ui/package.json unchanged"
    status: pass
    severity_if_fail: P1
    evidence_ref: "git diff main..remediate/cycle-023 -- apps/symphony-ui/package.json apps/symphony-ui/pnpm-lock.yaml is empty; canonical exact pins + packageManager pnpm@10.33.0 intact; dependencyPins.test.ts green in the suite"
    notes: >
      The remediation adds no dependency and changes no pin; the canonical manifest/lock
      state from the cycle-022 remediation is preserved.
```

---

## Gate evidence

- `pnpm install --frozen-lockfile` → Done (pnpm v10.33.0)
- `pnpm typecheck` (tsc --noEmit) → exit 0
- `pnpm vitest run` → 38/38 passed (3 files)
- `pnpm build` → built green
- `RUSTC_WRAPPER= cargo build --workspace` → Finished
- `RUSTC_WRAPPER= cargo fmt --all --check` → exit 0
- `RUSTC_WRAPPER= cargo clippy --workspace --all-targets -- -D warnings` → Finished, no warnings
- `RUSTC_WRAPPER= cargo nextest run --workspace` → 216 passed, 1 skipped
- `bash scripts/verify-docs.sh` → verify-docs OK
