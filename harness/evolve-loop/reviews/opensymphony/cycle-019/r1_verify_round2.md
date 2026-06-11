# r1-verify round 2 — cycle-019 remediation (after fix-round 2, 6540dc1)

Verdict: **overall_closed: false**. F1, F2, F3, F4, F6, F7 all CLOSED. Only **F5 (P0)** remains,
with a third, distinct bypass (adjudicated real against the code → fix-round 3):

- **F5 (P0) — declared-action bypass**: a capsule with `risk_level: low` and
  `high_risk_actions: [deploy]` but NO high-risk keyword in title/goal/acceptance/output passes,
  because `capsule_action_surface` omits the declared `high_risk_actions` (so inference finds
  nothing) and `apply_rule_7_high_risk_actions` returns early when `risk_level != high`. The
  high-risk safety invariant must hold whether the action is INFERRED from text OR DECLARED in
  the structured field. Fix-round 3: high-risk-present = inferred OR declared; include
  high_risk_actions in the action surface; capsule.validate() enforces high_risk_actions
  non-empty => risk_level high.

F5 closure history (each a real, distinct gap): round 0 = incident only fired for risk_level
Low; round 1 = detector missed the literal enum tokens (db_write/external_api/merge_pr/
file_delete); round 2 = declared high_risk_actions with non-high risk_level bypasses the
inference + rule-7 early-return. The other six findings are confirmed closed at structural and
semantic levels.
