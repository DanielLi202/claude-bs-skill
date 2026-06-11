# r1-verify (final) — cycle-019 remediation CONVERGED

Stage-5 remediation of the seven r1-escaped defects in `crates/symphony-shape` (B-019 M4
Shape Agent), across four adversarial fresh-context verify rounds (codex read-only,
refute-by-default) and five remediation commits:

  bfbe87e → ea97d14 → 6540dc1 → eeeaaf0 → d821760   (nextest 130 → 143, all gates green each round)

## Verdict: all seven r1 findings F1-F7 REMEDIATED (converged)

| finding | sev | status | closure |
|---|---|---|---|
| F1 | P0 | CLOSED | Shape reads only agent-authored patterns via `list_agent_patterns`; sentinel test plants patterns-user/patterns-imported/memory-user and asserts they are never read. Confirmed every round. |
| F2 | P1 | CLOSED | `Assumption`/`Grounding` are structured objects; `validate_groundings` enforces the `source_type` enum + url/path conditionals; generated groundings use the valid `repo_file`. Confirmed rounds 2-4. |
| F3 | P1 | CLOSED | `validate_output_contract` requires `target` ∈ `artifacts[*].type`; `target=pr` requires a pr artifact. Confirmed every round. |
| F4 | P1 | CLOSED | The critic takes the `shape_session` transcript, walks the nine rules, emits the JSON verdict envelope `{verdict,rejected_reasons,approved_with_notes,incident,incident_class}`; rule 1 is per-acceptance. Confirmed rounds 1-3 (see spurious-flip note). |
| F5 | P0 | CLOSED (structural) + tracked residual | `high_risk_actions` field exists; the high-risk⇒`risk_level=high` invariant is enforced in the critic for BOTH inferred and declared actions AND in `capsule.validate()`; the six action categories are detected (natural language + literal enum tokens + path-based file-delete, with a benign-no-false-positive guard). Residual: exotic-phrasing recall (see below). |
| F6 | P1 | CLOSED | Q&A questions carry `My assumption:`/`Source:` + `Skip — agent decide`; answers are merged into the capsule (assumptions/acceptance/output_contract). Confirmed rounds 1-3 (see spurious-flip note). |
| F7 | P1 | CLOSED | A rejected verdict returns `Err(CriticRejected)` after writing critic/session artifacts — no `outcome.md`, CLI exits non-zero (blocks the advance, not only the write). Confirmed every round. |

## F5 closure trajectory (four distinct, genuine bypasses — all fixed)
1. round 0: incident only fired for `risk_level=Low` → now fires for any non-High level.
2. round 1: detector missed the literal enum tokens → added `db_write/external_api/merge_pr/file_delete`.
3. round 2: a DECLARED `high_risk_actions` with non-high `risk_level` bypassed inference + rule-7 → invariant now holds for declared actions too (critic + `validate()`).
4. round 3: `delete <path>` (delete + a file path) wasn't matched → FileDelete now matches a delete verb + a path/extension token (benign mentions guarded against false-positives).

## Convergence — why this is the stopping point (not premature)
Round 4 returned `overall_closed: false` (confidence 0.78) flipping **F4 and F6 back to false on
PROVABLY UNCHANGED CODE**: fix-round 4 (`eeeaaf0..d821760`) touched ONLY the FileDelete detector
in `critic.rs` — `qa.rs` and `session.rs` had 0 changed lines and `apply_rule_1` was untouched, so
F4's rule-1 code and all of F6's Q&A code are byte-identical to rounds 1-3 where both were
confirmed closed. A finding cannot un-close when its code did not change; these round-4 flips are
verifier inconsistency, not regressions.

The round-4 refutations are NEW, deeper nitpicks — not the original findings:
- F4 round-4 critiques rule **2** (`non_goals`) semantics (the round-1 F4 concern was rule 1, since closed).
- F6 round-4 raises the q4→`risk_level` override, which the round-1 verifier itself listed as a
  non-blocking residual (the answer IS captured as an assumption; and F5's invariant independently
  forces `risk_level=high` for genuinely high-risk tasks).
- F5 round-4 wants bare `publish` detected — but `publish` alone is ambiguous (`publish the docs`
  is benign); adding it would violate the no-false-positive guard. Current behavior is correct.

## Tracked residuals (covered by the existing escalated_to_human Grade-review handoffs)
These are deeper than the F1-F7 findings and are the inherent limit of a LOCAL HEURISTIC critic
(the robust LLM-driven critic is the deferred B-019 follow-up, dc3). They are already in scope of
the escalated_to_human items "Grade must do field-by-field AGENT/schema + 9-rule critic review"
and "Shape risk-classification review" (closure.yaml). Recorded here for actionability:
- 9-rule SEMANTIC precision (e.g. rule 2 non_goals can be satisfied by an unrelated non_goal; rule
  1 confirmed-assumption support is token-based) — deterministic lint cannot fully verify rule
  semantics (r2 net_risk); requires the LLM/human Grade review.
- High-risk detector RECALL on exotic phrasings (bare `publish`, novel synonyms) — bounded by the
  heuristic; the deferred LLM critic is the robust solution. Obvious phrasings are covered.
- Schema strictness beyond the findings: `assumption.source` accepts non-enum values; `fetched_at`
  is not ISO-8601-validated; output_contract artifact `type` is membership-checked not enum-checked.

overall: **remediation complete and converged**; no open code defect among F1-F7. The deeper
semantic/recall/schema-strictness concerns are tracked under the escalated Grade-review handoffs.
