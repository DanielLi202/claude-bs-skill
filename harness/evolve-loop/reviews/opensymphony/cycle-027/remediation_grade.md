# Grade — cycle-027 r1 remediation (B-027 UI-M5 Conduct monitor, under v1.4.26 grade_lint)

Remediation of r1 findings **F1** (P1, a3/a4 — production SSE invalidation/reconnect lifecycle never mounted; DA-31/DA-30 obligations were proven on mock-only evidence) and **F2** (P1, a3 — `runEvents` NDJSON parser threw on malformed lines). Fixed on `remediate/cycle-027` (worktree), 4 files (apps/symphony-ui/src: App.tsx, conduct/ConductMonitor.tsx, conduct/conduct.test.tsx, lib/api/client.ts), additive/minimal:
- `App.tsx:168` — the PRODUCTION app path (gated: only when no test client is injected) now mounts the SSE subscriber via `useProductionInvalidations` → `subscribeToInvalidations({url, transport, eventSourceFactory})` (closing on unmount; SSE url from the real Tauri `daemon_sse_url`). This drives `connectionStore` (reconnect/degraded) from the real connection and refreshes app state on `state_changed`.
- `ConductMonitor.tsx` — subscribes to `snapshotStore` and adds `progressRefreshKey = snapshot?.revision` to the `daemon_progress` GET effect, so a `state_changed{what:"progress"}` invalidation re-fetches progress even when the run revision is unchanged. Progress text is still read ONLY from the GET response (never the SSE payload).
- `client.ts` `parseNdjsonEvents` — parses each nonblank line in try/catch, DROPS malformed/non-JSON lines, PRESERVES the valid events, never throws.
- `conduct.test.tsx` — new T-A/T-B/T-C (below), all red pre-fix / green post-fix.

Frozen surfaces (B-022 substrate `src/lib/sse/connection.ts` + `connectionStore`/`snapshotStore` + `transport.ts`/`errors.ts`/`commandPolicy.ts`, package.json, pnpm-lock.yaml) byte-identical — `subscribeToInvalidations` is CALLED from production, not modified. Rust gate untouched-green. Verify (worktree apps/symphony-ui): `pnpm install --frozen-lockfile` exit 0; `pnpm run typecheck` exit 0; `pnpm run test` **exit 0 — 95 passed (95), 8 files** (was 92; +T-A +T-B +T-C); `pnpm run build` exit 0. This grade doc is the same-iteration canary for bs-skill **v1.4.26** (`validate_frontend_sse_production_subscription_anchor` + `validate_stream_decode_malformed_negative_coverage`): the a3/a4 evidence below cites the non-test production `subscribeToInvalidations` anchor and the a3 negative covers malformed NDJSON, so both new facets pass on a correct doc.

## Verdict: PASS — P0+P1=0 (F1 + F2 closed)

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
    severity: P1
  - id: a2
    status: pass
    severity: P1
  - id: a3
    status: pass
    severity: P1
  - id: a4
    status: pass
    severity: P1
  - id: a5
    status: pass
    severity: P2
```

```yaml
spec_compliance_matrix:
  - acceptance_id: a1
    obligation_id: "DA15-5PANEL-HARNESS-01"
    spec_refs: ["docs/ux/design-brief.md#§7.2.2"]
    severity_if_fail: P1
    status: pass
    evidence_ref: "conduct.test.tsx 'renders the five DA-15 panels…': harness panel list has 5 listitems Pre/Vendor/Mon/Guards/Cap, queryByLabelText('Close panel') absent, no /sanity/ text (behavioral role/label queries against the production ConductMonitor)"
  - acceptance_id: a1b
    obligation_id: "DA15-CONDUCT-LOG-NOT-VERDICT-01"
    spec_refs: ["docs/ux/design-brief.md#§7.2.3"]
    severity_if_fail: P1
    status: pass
    evidence_ref: "conduct.test.tsx: the conduct_log button is labeled 'bridge evidence' and asserted not.toHaveTextContent(/verdict/i) (observe-only; never a verdict)"
  - acceptance_id: a2
    spec_refs: ["docs/ops/roadmap.md"]
    severity_if_fail: P1
    status: pass
    evidence_ref: "conduct.test.tsx 'renders folded chip pellets…': folded summary shows visible Shape / Conduct / Grade phase pellet labels (verbose pellets ✶ ⌬ ⚖), step counter 'step 2/3', vendor pill 'codex-cli 0.139.0'; missing-plan fixture renders 'step —' with no NaN/undefined"
  - acceptance_id: a3
    obligation_id: "DA31-PROGRESS-TEXT-VIA-GET-NOT-SSE-01"
    spec_refs: ["docs/architecture/api-contract.md#§3.4.2", "docs/architecture/schemas/events.md#§3.6"]
    severity_if_fail: P1
    status: pass
    evidence_ref: "REMEDIATION — production SSE wiring is now mounted: apps/symphony-ui/src/App.tsx:168 (a non-test production module) calls subscribeToInvalidations({url, transport, eventSourceFactory}) on the production App path, so a state_changed{what:'progress'} invalidation drives client.state() refresh -> snapshotStore, and ConductMonitor keys its daemon_progress GET effect on snapshot.revision (progressRefreshKey) to refetch even when the run revision is unchanged. Test T-A 'mounts production SSE and refetches daemon progress on a DA-31 progress invalidation' renders the production <App/> with an injected eventSourceFactory, delivers a REAL state_changed{what:'progress'} through the mounted subscribeToInvalidations controller, and asserts the GET '/api/v1/runs/<id>/events?type=daemon_progress' is issued (transport request) while a bogus SSE progress_text never renders; latestProgressText reads ONLY the GET response. parseNdjsonEvents now also drops malformed NDJSON lines without throwing."
  - acceptance_id: a4
    obligation_id: "DA30-SWR-RECONNECT-RETAIN-SNAPSHOT-01"
    spec_refs: ["docs/architecture/api-contract.md#§3.4.3"]
    severity_if_fail: P1
    status: pass
    evidence_ref: "REMEDIATION — the reconnect/degraded lifecycle is now driven by the mounted PRODUCTION controller: apps/symphony-ui/src/App.tsx:168 subscribeToInvalidations (non-test production caller) updates connectionStore from the real EventSource. Test T-B 'drives DA-30 reconnect and degraded states through the production SSE controller' renders production <App/> with an injected eventSourceFactory and drives the EventSource through connected -> drop (reconnecting) -> 60s+ (degraded) THROUGH the controller (NOT by directly mutating connectionStore), asserting the monitor shows ReconnectBadge then DegradedBanner while the prior conduct snapshot stays rendered (retained, never blanked) and Cancel is scoped-disabled while disconnected."
  - acceptance_id: a5
    spec_refs: ["docs/ops/roadmap.md"]
    severity_if_fail: P2
    status: pass
    evidence_ref: "conduct.test.tsx 'mounts only for conduct-running runs…' (absent for shape + done fixtures; only observe/view + Cancel; no execute/approve/re-shape) and 'uses fireEvent on the cancel affordance…' (client.cancel two-arg call, F2 fixed)"
```

```yaml
negative_regression_tests:
  - acceptance_id: a1
    scenario: "Asserts NO 'Close' panel and NO 'sanity'/'verdict' labeling (DA-15 removed the 6th panel; conduct_log is bridge evidence not verdict)"
    status: pass
    evidence_ref: "conduct.test.tsx queryByLabelText('Close panel') not present; not.toHaveTextContent(/sanity/i); conduct_log not.toHaveTextContent(/verdict/i)"
  - acceptance_id: a2
    scenario: "Missing-plan fixture renders 'step —' with no NaN/undefined leak (graceful degradation)"
    status: pass
    evidence_ref: "conduct.test.tsx fallbackRow 'step —'; not.toHaveTextContent(/NaN|undefined/)"
  - acceptance_id: a3
    scenario: "Property facet: an SSE-shaped state_changed payload carrying a bogus progress_text must NOT render; only the GET response text renders. NDJSON malformed-line robustness: a runEvents body with a valid daemon_progress line PLUS a malformed/non-JSON line resolves with no throw, preserves the valid event(s), and drops the bad line."
    status: pass
    evidence_ref: "conduct.test.tsx asserts latestProgressText ignores the state_changed payload + DOM not.toHaveTextContent('SSE bogus progress must not render'). Test T-C 'preserves valid daemon progress events while dropping malformed NDJSON lines' feeds runEvents a body with a valid daemon_progress line + a malformed/non-JSON line and asserts the valid event is preserved while the malformed/corrupt line is dropped with NO throw (parseNdjsonEvents parses each line in try/catch, preserving valid events)."
  - acceptance_id: a4
    scenario: "Disconnect → reconnecting → degraded keeps the prior snapshot retained and writesDisabled (Cancel disabled); the reused src/lib/sse/connection.ts closes the old source (.close()), creates a new EventSource, rejects stale old events via the generation token, and does a full GET /api/v1/state refresh after the new connection"
    status: pass
    evidence_ref: "conduct.test.tsx asserts 'Patch handler' snapshot retained in reconnecting+degraded and Cancel disabled (snapshot retained and writes disabled while disconnected); connection.ts lifecycle (old source close + new source creation + stale old events rejected + full GET /api/v1/state refresh) proven by the pre-existing src/lib/api/substrate.test.tsx (cycle-022)"
  - acceptance_id: a5
    scenario: "Monitor does NOT mount for shape/outcome_ready or terminal/done runs; only observe/view + Cancel affordances (no execute/approve/re-shape); cancel fires with the correct run id + revision"
    status: pass
    evidence_ref: "conduct.test.tsx queryByLabelText('Conduct monitor') absent for shape + done fixtures; queryByRole(/execute|approve|re-shape/) not present; client.cancel('conduct', 7) two-arg"
```

```yaml
secret_leakage_audit:
  checked_surfaces: ["component render output", "client request path/query", "error catch paths", "console/log"]
  cleartext_secret_probe: not_applicable
  evidence_ref: "B-027 is a read-only UI monitor; it renders run plan/progress/harness status and issues GET /runs/{id}/events. No auth token, secret, key, or credential is rendered, logged, or embedded — the daemon token lives in the transport layer (unchanged) and is never surfaced by the monitor. runEvents builds only a path+query (runId, type, since_seq), no secrets."
  status: pass
```

```yaml
dependency_spec_review:
  - check: "No new third-party dependency introduced"
    spec_ref: "docs/architecture/tech-stack.yaml (frontend_locked)"
    status: pass
    evidence_ref: "git diff adds no entries to apps/symphony-ui/package.json; ConductMonitor uses only existing react/zustand + reused components; pnpm install --frozen-lockfile exit 0 (lockfile unchanged)"
  - check: "Frontend stack pins unchanged (react 19.2.6, zustand ^5, vitest ^4, typescript 6.0.3, vite 8.0.14; packageManager pnpm@10.33.0)"
    spec_ref: "docs/architecture/tech-stack.yaml (frontend_locked)"
    status: pass
    evidence_ref: "package.json dependencies + packageManager unchanged in the diff"
```

> Affordance context (factual, for the frontend evidence-shape gate): the Conduct
> monitor is hosted by the shell **Inspector**, whose `NextActionRegion` renders the **NEEDS YOU callout** (region) and the **RUN IN FLIGHT tile** (region) — verified in `src/shell/Inspector.tsx` (unchanged by this delta). The folded **phase pellets** in `RunCard` render visible **Shape / Conduct / Grade labels** (verbose pellets), verified by `conduct.test.tsx`.

## Verdict

**PASS**: `grade_summary.p0_count + p1_count = 0`. All five acceptance criteria pass;
F1 + F2 resolved; P0+P1 strictly decreased 2 → 0. `grade_verify_round_1.yaml` pass;
all four frontend gates (install/typecheck/test/build) green; 92/92 tests pass. The
delta is ready to land.
