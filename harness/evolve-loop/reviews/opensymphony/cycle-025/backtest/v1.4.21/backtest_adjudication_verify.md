# backtest adjudication — fresh-context verification (v1.4.21, cycle-025)

Clean codex read-only session, prompt = adjudication + artifact paths only, instructed to refute.

I could not refute the cycle-022 false-positive adjudication.

Cycle-022’s own scope says “UI-M0 Contract substrate” and explicitly excludes app-shell layout; it ships client/transport substrate, commandPolicy, If-Match wrapper, SSE/SWR, and small substrate components like reconnect/degraded/toast. The command mentions in `outcome.md` and `grade_round_3.md` are wrapper/table claims: stage-transition writes carry If-Match; `commandPolicy` encodes the §4.0 matrix. I found no execute/re-shape interactive surface: no “Approve & start Conduct”, no execute/re-shape button region, no per-command pending lock, no inline execute/re-shape error region. So the original fire on cycle-022 was not a true historical positive.

Cycle-025 is different: its outcome repeatedly names actual command UI surfaces: outcome-ready region, primary “Approve & start Conduct”, secondary “Re-shape”, clicking Execute, scoped-disabled controls, inline conflict copy, retry, and pending lock. The refined rule still fires on the real cycle-025 backtest for `re_shape` and `conflict_refetch`, and the report shows `must_fire: true`, `misfire_candidates: []`.

Spot-checks matched the adjudication: cycle-022 title, grade a5/a7 quotes, outcome line 63 command-wrapper claim, commit `c889b84`, and post-refinement report are consistent. One residual risk remains: the affordance-token gate is heuristic and can miss plausible future UI wording such as “primary CTA/control/action” if no listed token like `button`, `click`, `render`, `region`, or `affordance` appears near the command.

```yaml
adj_verify:
  - fire: "frontend_pessimistic_command_matrix[execute]+[re_shape] on cycle-022"
    adjudicated: false_positive
    agree: true
    reasoning: "Cycle-022's artifacts describe a UI-M0 client/transport substrate: If-Match wrappers, commandPolicy matrix, SSE/SWR stores, and generic reconnect/degraded/toast components. The execute/re-shape mentions are wrapper/table assertions, not interactive command UI; the cycle explicitly defers app-shell layout and contains no execute/re-shape button/region/pending/inline-error surface. Cycle-025, by contrast, clearly has outcome-ready command UI and the refined rule still fires there, so the cycle-022 fire was a false positive."
    residual_risk: "The UI-affordance token gate can miss future command-UI wording that says primary CTA/control/action/tap/submit/menu without any listed affordance token near execute or re-shape."
```
