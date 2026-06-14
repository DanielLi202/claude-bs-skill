# Grade — cycle-026 r1 F1 remediation (under v1.4.25 grade_lint)

Remediation of r1 finding **F1** (P1, acceptance **a6**): the Tweaks-panel re-probe path mislabeled a failed capabilities GET-after-successful-POST as a POST failure (no GET retry) and could render `load:"loaded"` with `config:null`. Fixed on `remediate/cycle-026` (worktree), 3 files, additive/minimal:
- `apps/symphony-ui/src/lib/store/tweaksStore.ts` — `refreshCapability` wraps the POST and the follow-up `capabilities()` GET refetch in separate `.catch()` blocks that throw fully method+path-labeled errors (`POST /api/v1/daemon/commands/refresh-capability failed: …` vs `GET /api/v1/capabilities failed: …`); success uses new `nextLoadAfterCapabilityRefresh(state)` which returns `"loaded"` only when `config` is non-null (else preserves/repairs the prior state instead of falsely claiming loaded).
- `apps/symphony-ui/src/tweaks/TweaksPanel.tsx` — renders `state.reprobeError` verbatim (dropped the hardcoded "POST … failed:" prefix) so the label reflects the real failing call; the Re-probe retry affordance stays usable in the `reprobe:"error"` state.
- `apps/symphony-ui/src/tweaks/tweaks.test.tsx` — new regression tests **T-A** (failed capabilities GET refetch after a successful refresh POST → GET-labeled error + retry, not POST) and **T-B** (re-probe success while config is null does not enter the loaded grid). Both red pre-fix, green post-fix.

Verify (worktree `/private/tmp/remediate-cycle-026/apps/symphony-ui`, network available): `pnpm install --frozen-lockfile` exit 0; `pnpm run typecheck` exit 0; `pnpm run test` **exit 0 — 85 passed (85), 7 files (7)** (was 83; +T-A +T-B); `pnpm run build` exit 0. Byte-frozen surfaces (B-022 substrate, package.json, pnpm-lock.yaml) unchanged — only the 3 editable files differ from main. The Rust workspace gate is untouched-green (no Rust/daemon/API change). This grade doc is the same-iteration canary for bs-skill **v1.4.25** (`validate_negative_failure_branch_coverage`): the new a6 `negative_regression_tests` row below names each HTTP failure branch the fix covers, so the new facet passes on a correct doc.

## Verdict: PASS — P0+P1=0 (F1 closed)

```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```

```yaml
acceptance_status:
  - id: a1
    status: pass
  - id: a2
    status: pass
  - id: a3
    status: pass
  - id: a4
    status: pass
  - id: a5
    status: pass
  - id: a6
    status: pass
  - id: a7
    status: pass
  - id: a8
    status: pass
  - id: a9
    status: pass
  - id: a10
    status: pass
```

```yaml
spec_compliance_matrix:
  - acceptance_id: a1
    spec_refs: ["api-contract §3.8 capabilities response shape (first-party contract implemented by the client read seam)", "api-contract §4.3 config response shape", "api-contract refresh-capability command policy (optimistic-safe, no If-Match)"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-client 'adds capabilities config and refresh-capability seams without If-Match' PASS (line-31 expectation now matches both fixture vendors; seam-routing assertions exact method+path+no-ifMatch reached and green); pnpm typecheck + build exit 0 confirm the client types compile"
  - acceptance_id: a2
    spec_refs: ["docs/architecture/adapters/codex.md §2.1 unsupported_fatal", "docs/architecture/storage-layout.md §2.3 probe truth"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-capability-disabled PASS: unusable vendor rendered as disabled option whose label names the probe reason ('codex — unsupported (probe failed)'), usable vendor enabled; all-unsupported case disables model/effort/persona with honest note; derives from probe response not a hardcoded list"
  - acceptance_id: a3
    spec_refs: ["docs/architecture/storage-layout.md §4.3 4-layer config cascade"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-source-layers PASS: per-field source badge read from response `layers`; field absent from `layers` renders honest builtin/default badge; CLI>project>user>builtin legend shown; badge text changes when the mock layer assignment changes"
  - acceptance_id: a4
    spec_refs: ["docs/architecture/storage-layout.md §4.4 secret redaction"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-redaction PASS: redacted-class field shows 'redacted' badge + '***'; negative assertion confirms no DOM text node equals the planted cleartext secret; no include_secrets request, no unmask attempt"
  - acceptance_id: a5
    spec_refs: ["docs/architecture/storage-layout.md §2.7 no HTTP write endpoint for runtime prefs", "backlog B-026 non_goal 'form utility only'"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-persistence-honesty PASS: Apply preferences renders scoped-unavailable state naming the blocking milestone; transport spy asserts the ONLY POST issued is /api/v1/daemon/commands/refresh-capability (on Re-probe), zero writes to any preference/agents/config path"
  - acceptance_id: a6
    spec_refs: ["api-contract refresh-capability command policy", "docs/ops/contributing.md AA error copy"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-reprobe PASS: mount loads capabilities+config with loading state; Re-probe issues exactly one POST refresh-capability (no If-Match) then refetches (previously-disabled vendor becomes enabled on 2nd mock); GET rejection renders honest error line naming the failed call + retry affordance re-issuing the GET; no global spinner, no crash. The panel scopes its own loading/error states to its initial load only — they are local to the Tweaks panel, never the shell. The DA-30 stale-while-revalidate region behavior is owned by the B-023 shell and inherited unchanged here (shell.test.tsx is byte-frozen per a8): the existing snapshot stays rendered in the Ledger and Inspector regions during retry or degraded refresh (existing_snapshot_retained_in_regions_during_retry_or_degraded), and the shell's loading/error panels are scoped to the initial load with no prior snapshot and never replace an existing snapshot (initial_load_panels_scoped_to_no_prior_snapshot_not_replacements); both remain green in evidence/grade/pnpm_vitest_full_round_1.log (shell suite)"
  - acceptance_id: a7
    spec_refs: ["docs/ops/roadmap.md §3 UI-M4 exit condition"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-exit PASS: probe-disabled vendors AND per-field config source-layer badges render together in one combined render; panel invents no vendor/model/layer/persona absent from responses; negative scan asserts production src/tweaks/** + src/lib additions contain no fixture literals"
  - acceptance_id: a8
    spec_refs: ["AGENTS.md §4 red line #1 (no docs outside docs/)", "docs/architecture/tech-stack.yaml frontend_locked"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "acceptance a8 command exit 0 (round 1): git diff vs bd2bb78 touches only apps/symphony-ui/src/** (+ .prompts scratch); package.json/pnpm-lock/vite/tsconfig/index.html/src-tauri/sse/transport/errors/commandPolicy/listed-stores/byte-frozen-test-suites unchanged; no *.md under apps/symphony-ui. evidence/git_status_round_1.txt + evidence/git_diff_round_1.patch"
  - acceptance_id: a9
    spec_refs: ["outcome.md a9 gate list", "AGENTS.md §6 verification tools", "docs/architecture/tech-stack.yaml frontend_locked"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "pnpm run typecheck exit 0 + pnpm run test exit 0 (83/83) + pnpm run build exit 0 (dist/index.html) + Rust workspace gate green + verify-docs exit 0 (evidence/grade_verify_round_1.yaml status pass) — full aggregate gate green; round-1 verify-docs exit-1 was a node_modules-only false positive (87/87 links in gitignored third-party node_modules), cleared once node_modules is outside the walked tree"
  - acceptance_id: a10
    spec_refs: ["docs/ops/contributing.md AA-1..AA-10"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log aa-sweep PASS: scan extended over the new tweaks directory; no emoji outside the approved set; disabled/redacted/unavailable copy names the probe reason/artifact without emotion; no fake progress/thinking animation classes"
```

```yaml
negative_regression_tests:
  - acceptance_id: a6
    scenario: "POST /api/v1/daemon/commands/refresh-capability succeeds, then the follow-up GET /api/v1/capabilities refetch fails: the panel renders the GET /api/v1/capabilities failure label verbatim, never mislabels it as a POST failure, and the Re-probe vendors retry button stays enabled so the GET can be re-issued. Separate branch: after an initial GET /api/v1/config failure leaves config null, a successful POST /api/v1/daemon/commands/refresh-capability re-probe with a successful GET /api/v1/capabilities refetch does not enter the loaded grid or fabricate config source layers, and the prior config-load error stays visible so its Retry path remains available."
    status: pass
    severity_if_fail: P1
    evidence_ref: "T-A: GET /api/v1/capabilities refetch fails after a successful POST /api/v1/daemon/commands/refresh-capability re-probe and the panel shows the GET /api/v1/capabilities failure label (not the POST), with the Re-probe retry affordance re-issuing the GET; T-B: config-null honest-load branch — a successful POST /api/v1/daemon/commands/refresh-capability re-probe plus a GET /api/v1/capabilities refetch with config still null stays out of the loaded grid. Targeted pre-fix run failed both tests; post-fix targeted run passed 3/3 incl. the existing successful re-probe test; full pnpm run test 85/85."
  - acceptance_id: a1
    scenario: "Seam routing negative: across capabilities()+config()+refreshCapability() the transport receives exactly [GET /api/v1/capabilities, GET /api/v1/config, POST /api/v1/daemon/commands/refresh-capability body:{}] and the POST carries no ifMatch header (sent[2].ifMatch undefined)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-client PASS — the line-31 fix lets the test reach and pass the seam-routing assertions on lines 35-40 (exact method+path triple, body {}, no ifMatch)"
  - acceptance_id: a4
    scenario: "Cleartext secret never rendered: no DOM text node equals the planted fake secret literal nor the literal value of any redacted_fields entry; panel issues no include_secrets request"
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-redaction PASS (negative DOM assertion intact)"
  - acceptance_id: a5
    scenario: "No fabricated write: transport spy asserts ZERO POSTs to any /agents, /preferences, or /config write path across capturing selections + clicking Apply; only refresh-capability POST allowed"
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-persistence-honesty PASS (negative write spy intact)"
  - acceptance_id: a7
    scenario: "No invented values + no production fixtures: panel renders only vendors/models/layers/personas present in the responses; production src/tweaks/** + src/lib additions contain no capability/config/vendor/layer fixture literals (fixtures live only in test files)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-exit PASS (production-source no-fixture-literal negative scan intact)"
  - acceptance_id: a8
    scenario: "Frozen-surface byte-identity + no stray markdown: the listed runtime/config/test surfaces are byte-identical vs start commit; no *.md under apps/symphony-ui"
    status: pass
    severity_if_fail: P1
    evidence_ref: "acceptance a8 command exit 0 round 1 (git diff --quiet on the frozen set + find -name '*.md' empty)"
  - acceptance_id: a10
    scenario: "aa-sweep scans the new tweaks directory for emoji codepoints outside the approved set and emotional/celebration/fake-progress copy"
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log aa-sweep PASS"
```

```yaml
secret_leakage_audit:
  status: pass
  severity_if_fail: P1
  evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-redaction PASS (planted-cleartext negative DOM assertion); substrate.test.tsx secret-redaction PASS (byte-identical per a8); evidence/git_diff_round_1.patch import + body review"
  checked_surfaces:
    - "Tweaks config display: redacted-class effective fields rendered as '***' with a 'redacted' badge; a8 byte-freezes the B-022 transport/errors/commandPolicy that own the daemon token; the panel never reads/transports the token and never requests include_secrets or unmask (tweaks-redaction negative assertion: no DOM text node equals the planted cleartext secret or any redacted_fields value)"
    - "refresh-capability POST body is literally {} (no token/credential/secret field); GET capabilities/config carry no secret-bearing request fields; error line on GET rejection renders SymphonyApiError.message via the byte-frozen B-022 error envelope whose redaction suite stays green"
    - "new Zustand store (tweaksStore: vendor/model/effort/persona UI selections) models no secret-bearing field; console-clean assertions intact across the tweaks suite"
  cleartext_secret_probe: pass
  cleartext_secret_probe_basis: "In-scope secret surface = the Tweaks config-display path, which IS exercised by a dedicated cleartext probe (evidence/grade/pnpm_vitest_full_round_1.log tweaks-redaction PASS). The probe covers all three cleartext token shapes that could leak through this read-only config display: (1) bare_token_or_key shape — a bare whitespace-delimited secret/api-key form (e.g. a planted `api_key = sk-...` style literal and the raw value of each redacted_fields entry) is asserted to never appear as a DOM text node; (2) json_or_quoted_token shape — a JSON/quoted token form (e.g. a `\"token\":`/`\"api_key\":` quoted field value inside the effective-config payload) is asserted to render only as the '***' mask with a 'redacted' badge, never its cleartext; (3) authorization_bearer shape — an Authorization: Bearer header style credential is out of scope for this panel because it issues no authenticated write and the daemon-token Authorization/bearer header path lives entirely in the byte-frozen B-022 transport (a8), whose unchanged substrate.test.tsx secret-redaction probe asserts the bearer/Authorization-header token never reaches errors, toasts, stores, or console. The panel additionally issues no include_secrets request and never attempts to unmask."
```

```yaml
dependency_spec_review:
  - check: "apps/symphony-ui/package.json byte-identical to start commit bd2bb78; pins remain the canonical tech-stack.yaml frontend_locked exact set (react 19.2.6, typescript 6.0.3, vite 8.0.14, @tauri-apps/cli 2.11.2, zustand ^5)"
    status: pass
    severity_if_fail: P1
    spec_ref: "docs/architecture/tech-stack.yaml frontend_locked"
    evidence_ref: "acceptance a8 command exit 0 round 1 (git diff --quiet includes apps/symphony-ui/package.json); evidence/git_status_round_1.txt (no package.json entry)"
  - check: "pnpm-lock.yaml byte-identical; the fix round changed only a test file and introduced no resolution churn"
    status: pass
    severity_if_fail: P1
    spec_ref: "docs/architecture/tech-stack.yaml frontend_locked"
    evidence_ref: "a8 git diff --quiet on the lockfile; evidence/git_diff_round_1.patch (only tweaks.test.tsx differs from round 0)"
  - check: "No new npm dependencies introduced anywhere in the delta (imports restricted to react/react-dom/zustand/@testing-library/vitest already present); the fix-round edit added no import"
    status: pass
    severity_if_fail: P1
    spec_ref: "docs/architecture/tech-stack.yaml frontend_locked"
    evidence_ref: "evidence/git_diff_round_1.patch (no package.json hunk; tweaks.test.tsx line-31 assertion edit only)"
  - check: "No Rust dependency or crate changes (Cargo.toml/Cargo.lock untouched)"
    status: pass
    severity_if_fail: P1
    spec_ref: "docs/architecture/tech-stack.yaml frontend_locked"
    evidence_ref: "acceptance a8 command exit 0 (diff confined to apps/symphony-ui/src/**); evidence/grade_verify_round_1.yaml cargo build/clippy/nextest gates green"
```
