# r1-verify — cycle-026 F1 remediation (fresh-context, codex read-only)

Independent re-read of the remediation diff (`remediate/cycle-026`) vs r1.md, default-to-not-closed. Verdict: **F1 closed** (all sub-claims true).

```r1_verify
cycle: cycle-026
findings:
  - id: F1
    severity: P1
    closed: true
    sub_claims:
      distinct_error_labeling: true
      honest_load_state: true
      retry_affordance: true
      regression_coverage: true
    evidence: "apps/symphony-ui/src/lib/store/tweaksStore.ts:73-81 now separates the POST and GET catches: POST failures are labeled POST /api/v1/daemon/commands/refresh-capability failed, while post-success capabilities refetch failures are labeled GET /api/v1/capabilities failed. tweaksStore.ts:90-92 stores that labeled message verbatim, and apps/symphony-ui/src/tweaks/TweaksPanel.tsx:59 renders state.reprobeError directly instead of hardcoding a POST prefix. Honest load state is fixed by tweaksStore.ts:109-112: nextLoadAfterCapabilityRefresh returns loaded only when state.config exists, otherwise preserves the current non-loaded state or downgrades stale loaded+null to idle; TweaksPanel.tsx:61 renders the grid only for load === loaded. Retry remains available because TweaksPanel.tsx:42-49 always renders Re-probe vendors and disables it only while reprobe === pending; tweaksStore.ts:90-92 sets GET-refetch failure to reprobe error, not pending. Regression coverage is meaningful: tweaks.test.tsx:184-195 mocks capabilities rejection after the default successful refresh POST and asserts the GET label, absence of POST label, and enabled Re-probe; tweaks.test.tsx:197-210 starts with config GET failure, re-probes successfully, then asserts the config error remains and the source-layer grid/Vendor control are absent. Both tests would fail against the old hardcoded POST-prefix and unconditional load loaded behavior."
overall_closed: true
notes: "Read-only verification: inspected diff and full changed source/test files; did not execute tests."
```
