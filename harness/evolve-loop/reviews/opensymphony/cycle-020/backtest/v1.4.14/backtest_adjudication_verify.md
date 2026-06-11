# backtest adjudication — fresh-context verification (codex read-only, refute-by-default)

Verifies the cycle-018 misfire verdict (true_positive_historical) for the v1.4.14 backtest.

```yaml
adj_verify:
  - cycle: cycle-018
    facet: "subprocess_lifecycle[B018-A9]"
    adjudicated_verdict: true_positive_historical
    agree: true
    b018a9_claim_quote: "An orphaned grandchild after the leader exits must be reaped; terminate_process_group signals the whole group SIGTERM then SIGKILL on timeout and normal-exit paths, exercised by the fake-vendor e2e + probe."
    evidence_is_process_group_only: true
    rule_overbroad: false
    reason: "B018-A9 explicitly claims orphaned-grandchild reaping, but its cited evidence is .process_group(0), negative-pgid SIGTERM/SIGKILL reaping, handoff/probe refs, and fake-vendor e2e/probe only; I found no detached/new-session/setsid grandchild escape fixture or descendant audit/tree-containment evidence in the cycle-018 grade text. The new rule adds descendant_escape_fixture and descendant_audit_or_tree_containment only when descendant/no-orphan/process-tree claim terms are present, so this fire is scoped to the strong B018-A9 claim rather than a benign timeout-only surface."
  overall_agree: true
```
