# r1-verify — cycle-022 remediation @1023371 (fresh-context codex, read-only)

All three r1 findings verified closed at production loci on the first verify round
(the canary's lint round had already forced one truthful doc re-author + the v1.4.18
plural-events rule patch before this verification).

```yaml
r1_verify:
  remediation_commit: "1023371"
  findings:
    - id: F1
      closed: true
      production_locus_fixed: true
      evidence: "apps/symphony-ui/src/lib/sse/connection.ts:77-116 closes current EventSource, invalidates generation, and schedules reconnect; substrate.test.tsx:169-220 tests old source is closed and stale old-source connected event cannot refresh"
    - id: F2
      closed: true
      production_locus_fixed: true
      evidence: "apps/symphony-ui/src/lib/api/transport.ts:36-55,148-170 throws InstanceIdentityMismatchError before returning mismatched HTTP data; connectionStore.ts:25-43 prevents bare connected() from re-enabling writes while mismatched; substrate.test.tsx:355-424 tests rejection/no data, no write re-enable, and SSE mismatch disable-until-match"
    - id: F3
      closed: true
      production_locus_fixed: true
      evidence: "apps/symphony-ui/package.json:13-31 pins react/react-dom/typescript/vite and packageManager; pnpm-lock.yaml:14-50,689-699,784-799 resolves react 19.2.6 and vite 8.0.14; dependencyPins.test.ts:29-63 enforces manifest/lock/packageManager against frontend_locked"
  overall: pass
  notes: "No contested r1 blocker remains under read-only inspection; tests were inspected, not executed."
```
