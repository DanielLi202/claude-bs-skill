# Remediation Grade — cycle-022 F1-F3 (UI-M0 frontend, apps/symphony-ui)

**cycle**: cycle-022
**task**: Stage-5 remediation of F1-F3 in the UI-M0 frontend (apps/symphony-ui, React/Vite/Tauri)
**branch**: `/private/tmp/remediate-cycle-022` `remediate/cycle-022` @ `1023371`
**graded_at**: 2026-06-12
**grade_lint**: same-iteration canary for the v1.4.17 frontend facets (run with --repo-root)

---

## grade_summary

```yaml
grade_summary:
  task_id: cycle-022-remediation
  round: 0
  risk_level: low
  p0_count: 0
  p1_count: 0
  p2_count: 0
  p3_count: 0
  overall_result: pass
  grade_verify_status: pass
  cargo_test: "pnpm vitest run (apps/symphony-ui) + cargo nextest run --workspace"
  cargo_test_pass: 237
  cargo_test_fail: 0
  notes: >
    All three remediation acceptances (r1 F1-F3) are covered by real vitest regression
    tests under /private/tmp/remediate-cycle-022/apps/symphony-ui. Full gate stack green:
    pnpm install --frozen-lockfile, pnpm typecheck (tsc --noEmit clean), pnpm vitest run
    (21/21), pnpm build, cargo build/fmt/clippy -D warnings/nextest (216 passed,
    1 skipped), bash scripts/verify-docs.sh.
```

---

## acceptance_status

```yaml
acceptance_status:
  - id: a1
    status: pass
    severity: P1
    text: "F1 SSE reconnect lifecycle closed"
    evidence_ref: "pnpm vitest run: 'keeps snapshot, disables writes, degrades after 60s, and refreshes on reconnect'; 'ignores stale old-source events after heartbeat disconnect'; 'refreshes state only after the replacement source connects'"
  - id: a2
    status: pass
    severity: P1
    text: "F2 instance-identity mismatch recovery closed"
    evidence_ref: "pnpm vitest run: 'rejects mismatched HTTP responses and surfaces a typed identity error'; 'prevents refresh bookkeeping from re-enabling writes while identity is mismatched'; 'keeps SSE instance mismatches disabled until a later matching identity is observed'"
  - id: a3
    status: pass
    severity: P1
    text: "F3 canonical dependency pins closed"
    evidence_ref: "pnpm vitest run: 'dependency-spec-review > keeps manifest and lockfile exact for frontend canonical pins'; pnpm install --frozen-lockfile green"
```

---

## spec_compliance_matrix

```yaml
spec_compliance_matrix:
  - acceptance_id: a1
    spec_ref: "docs/architecture/api-contract.md DA-30 SWR reconnect contract (~:419-425); docs/architecture/ui-responsiveness.md"
    status: pass
    severity_if_fail: P1
    evidence_ref: "apps/symphony-ui/src/lib/sse/connection.ts: on heartbeat miss the stale source is closed (source.close() at ~:95) and disposed, the eventSourceFactory is invoked a second time to create the replacement EventSource with backoff (~:129), and a full state refresh (GET /api/v1/state) runs only after the NEW connection is established. Vitest: 'ignores stale old-source events after heartbeat disconnect' proves stale old-source events are ignored and cannot satisfy reconnect; 'keeps snapshot, disables writes, degrades after 60s, and refreshes on reconnect' proves the snapshot retained with writes disabled while disconnected; 'refreshes state only after the replacement source connects' proves the full refresh ordering against the new connection."
    notes: >
      The round-0 escape (status flip to reconnecting with no close/dispose, factory called
      once, retryNow = refresh only) is structurally gone: the state machine now owns an
      old-source close + new-source creation transition, and the test that previously
      emitted connected on the same stale source is replaced by a stale-source negative.
  - acceptance_id: a2
    spec_ref: "docs/architecture/api-contract.md §1.2 instance identity (~:37-39) + DA-30"
    status: pass
    severity_if_fail: P1
    evidence_ref: "apps/symphony-ui/src/lib/api/transport.ts + errors.ts: a mismatched instance-id response is rejected with a typed identity error and never returned as data (rejection, no data acceptance); the onInstanceMismatch callback remains, but a callback-only side effect is insufficient by construction since the request now throws. connectionStore.ts blocks connected()/write re-enable until a fresh MATCHING identity is observed; an SSE connected event with a mismatched identity is not accepted as success. Vitest: 'rejects mismatched HTTP responses and surfaces a typed identity error'; 'prevents refresh bookkeeping from re-enabling writes while identity is mismatched'; 'keeps SSE instance mismatches disabled until a later matching identity is observed'."
    notes: >
      The round-0 escape (transport returned the mismatched response; refresh() then
      called connected() and re-enabled writes) is closed at both loci: transport
      (rejection) and the connection store (identity-gated write re-enable).
  - acceptance_id: a3
    spec_ref: "docs/architecture/tech-stack.yaml frontend_locked + AGENTS.md §4 red-line #11"
    status: pass
    severity_if_fail: P1
    evidence_ref: "apps/symphony-ui/package.json now pins exact canonical versions (react 19.2.6, react-dom, vite 8.0.14, typescript 6.0.3, zustand 5.x per frontend_locked) with caret ranges removed for canonical-exact deps, plus packageManager: pnpm@10.33.0; pnpm-lock.yaml regenerated so every canonical-exact dep resolves to exactly the canonical version. Vitest 'dependency-spec-review > keeps manifest and lockfile exact for frontend canonical pins' loads package.json + pnpm-lock.yaml + docs/architecture/tech-stack.yaml and asserts manifest/lock/canonical agreement; pnpm install --frozen-lockfile passes."
    notes: >
      No tech-stack.yaml edits (a canonical version change would need a council T-batch);
      the code was brought back to the canon rather than the canon rewritten.
```

---

## negative_regression_tests

```yaml
negative_regression_tests:
  - id: nr1
    acceptance_id: a1
    scenario: "heartbeat miss => old EventSource closed AND factory invoked a second time (new source created); reconnect cannot be satisfied without a new source"
    test_name: "substrate.test.tsx > keeps snapshot, disables writes, degrades after 60s, and refreshes on reconnect"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run; connection.ts source.close() + factory(options.url) second call; snapshot retained and writes disabled while disconnected per the degraded-state assertions"
  - id: nr2
    acceptance_id: a1
    scenario: "stale old-source events after disconnect are ignored and cannot mark the connection healthy (the exact round-0 test forgery)"
    test_name: "substrate.test.tsx > ignores stale old-source events after heartbeat disconnect"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run; stale old-source events are ignored by generation/identity of the active source"
  - id: nr3
    acceptance_id: a1
    scenario: "full state refresh (GET /api/v1/state) fires only AFTER the replacement source connects, not before"
    test_name: "substrate.test.tsx > refreshes state only after the replacement source connects"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run; refresh ordering asserted against the new source's open event"
  - id: nr4
    acceptance_id: a2
    scenario: "mismatched instance-id HTTP response is rejected: typed identity error thrown, no data returned to the caller"
    test_name: "substrate.test.tsx > rejects mismatched HTTP responses and surfaces a typed identity error"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run; transport throws the typed error; callback-only side effect insufficient"
  - id: nr5
    acceptance_id: a2
    scenario: "refresh()/connected() bookkeeping cannot re-enable writes while the last seen identity mismatches"
    test_name: "substrate.test.tsx > prevents refresh bookkeeping from re-enabling writes while identity is mismatched"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run; connectionStore identity gate"
  - id: nr6
    acceptance_id: a2
    scenario: "an SSE connected event with a mismatched identity is not accepted as success; a later MATCHING identity restores writes"
    test_name: "substrate.test.tsx > keeps SSE instance mismatches disabled until a later matching identity is observed"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run; write re-enable requires fresh matching identity"
  - id: nr7
    acceptance_id: a3
    scenario: "a manifest caret range or lockfile resolution diverging from a canonical-exact tech-stack version fails the test; packageManager must be present and canonical"
    test_name: "dependencyPins.test.ts > dependency-spec-review > keeps manifest and lockfile exact for frontend canonical pins"
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm vitest run; loads package.json + pnpm-lock.yaml + tech-stack.yaml frontend_locked and asserts exact agreement"
```

---

## secret_leakage_audit

```yaml
secret_leakage_audit:
  status: pass
  evidence_ref: "manual review of /private/tmp/remediate-cycle-022/apps/symphony-ui/src/lib plus pnpm vitest run"
  checked_surfaces:
    - "apps/symphony-ui/src/lib/api/transport.ts"
    - "apps/symphony-ui/src/lib/api/errors.ts"
    - "apps/symphony-ui/src/lib/sse/connection.ts"
    - "apps/symphony-ui/src/lib/store/connectionStore.ts"
  cleartext_secret_probe: not_applicable
  rationale: >
    The remediation touches reconnect/identity state machines and dependency pins only;
    it introduces no credential, bearer-token, API-key, OAuth, auth-header, logging, or
    redaction surface (the daemon token stays outside the webview per DA-23's invoke-shim
    trust model, untouched here), so cleartext secret probing is not applicable.
```

---

## dependency_spec_review

```yaml
dependency_spec_review:
  - name: "frontend canonical pins (react, react-dom, vite, typescript, zustand, packageManager)"
    spec_ref: "docs/architecture/tech-stack.yaml frontend_locked"
    status: pass
    severity_if_fail: P1
    evidence_ref: "apps/symphony-ui/package.json exact pins + packageManager pnpm@10.33.0; pnpm-lock.yaml resolutions equal the canonical versions; dependencyPins.test.ts asserts manifest/lock/canonical agreement; no new dependency added by the remediation"
    notes: >
      The r1 F3 drift (caret ranges resolving react to 19.2.7 and vite to 8.0.16, missing
      packageManager) is reconciled by pinning the code back to the canonical exact
      versions; tech-stack.yaml itself is untouched.
```

---

## Gate evidence

- `pnpm install --frozen-lockfile` → Done (pnpm v10.33.0)
- `pnpm typecheck` (tsc --noEmit) → exit 0
- `pnpm vitest run` → 21/21 passed (2 files)
- `pnpm build` → built green
- `RUSTC_WRAPPER= cargo build --workspace` → Finished
- `RUSTC_WRAPPER= cargo fmt --all --check` → exit 0
- `RUSTC_WRAPPER= cargo clippy --workspace --all-targets -- -D warnings` → Finished, no warnings
- `RUSTC_WRAPPER= cargo nextest run --workspace` → 216 passed, 1 skipped
- `bash scripts/verify-docs.sh` → verify-docs OK
