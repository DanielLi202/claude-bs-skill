# r1-verify — cycle-027 F1+F2 remediation (fresh-context, codex read-only)

Independent re-read of the remediation diff (`remediate/cycle-027`) vs r1.md, default-to-not-closed, with explicit instruction to flag any "production" test that bypasses the controller. Verdict: **both findings closed** (overall_closed: true). (Vitest blocked by the read-only sandbox; orchestrator independently confirmed pnpm test 95/95.)

```r1_verify
cycle: cycle-027
findings:
  - id: F1
    severity: P1
    closed: true
    sub_claims:
      production_subscriber_mounted: true
      progress_invalidation_refetch: true
      reconnect_degraded_real_controller: true
      tests_drive_production_path: true
    evidence: "Production path: main.tsx:6-9 renders <App/> without a client; App.tsx:34-38 creates productionRuntime only when no injected client and calls useProductionInvalidations; App.tsx:161-188 resolves transport+sseUrl, calls subscribeToInvalidations at 168-176, and closes the controller at 184-187. Test gating: App.tsx:14-21 exposes runtime injection, while App.tsx:139-158 defaults to autoTransport/daemon_sse_url. Progress path: connection.ts:161-167 handles real state_changed by refresh(), connection.ts:49-53 calls client.state() then snapshotStore.replace; ConductMonitor.tsx:20-26 reads snapshot.revision, and ConductMonitor.tsx:32-45 re-runs client.runEvents(...type daemon_progress) when progressRefreshKey changes, even if run.revision is unchanged. Progress text is GET-only: ConductMonitor.tsx:35-37 sets events from runEvents, ConductMonitor.tsx:95-97 renders latestProgressText(events), and conductModel.ts:47-53 accepts only daemon_progress payload progress_text. Real controller reconnect/degraded: connection.ts:168 routes EventSource error to disconnect; connection.ts:110-115 sets connectionStore.reconnecting and arms degraded; connection.ts:84-90 sets connectionStore.degraded; ConductMonitor.tsx:51-53 renders the badges. Production-path tests: conduct.test.tsx:148-179 renders <App runtime=...>, emits connected and state_changed through fixture.sources[0], verifies a new GET /events request and rejects SSE progress_text; conduct.test.tsx:181-214 emits error through the same controller and observes reconnecting/degraded UI; fixture lines 367-407 use real createTransport plus an EventSource factory. Legacy direct connectionStore tests remain at conduct.test.tsx:127-146/267-273, but T-A/T-B provide the required production-path coverage."
  - id: F2
    severity: P1
    closed: true
    sub_claims:
      malformed_ndjson_tolerated: true
    evidence: "client.ts:279-283 routes string bodies into parseNdjsonEvents; client.ts:286-297 now iterates nonblank lines, wraps JSON.parse(line) in try/catch, drops malformed lines, and returns accumulated valid events. conduct.test.tsx:216-233 builds valid daemon_progress + malformed '{not json' NDJSON and asserts client.runEvents resolves with the valid event preserved."
overall_closed: true
notes: "Read-only verification. git diff/status inspected. pnpm exec tsc --noEmit --pretty false passed. Vitest execution was attempted but blocked by the read-only sandbox because Vite/Vitest tried to write temp files (EPERM), so runtime test execution was not used as evidence."
```
