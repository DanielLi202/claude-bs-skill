# r1-verify round 1 — cycle-019 remediation (after fix-round ea97d14)

Verdict: **overall_closed: false** (confidence 0.74). F7 now CLOSED. F1/F3/F6 still closed.
The round went DEEPER (semantic correctness, not structure) and flagged F2, F4, F5. Each was
adjudicated by the orchestrator against the actual code before iterating:

- **F2 (P1) — CONFIRMED real, in scope** → fix-round 2. `groundings_for` (session.rs) emits
  `source_type: "repo"`, which is NOT in the schema enum {web, repo_file, git_log,
  pattern_library, prior_run} (outcome-capsule.md:335); `validate_groundings` (capsule.rs:287)
  only trim-checks source_type. Shape emits schema-invalid capsules — squarely F2's "schema not
  actually modeled". Fix: emit `repo_file` + enforce the enum + url/path conditionals.
- **F5 (P0) — CONFIRMED real, in scope** → fix-round 2. `infer_high_risk_action_kinds` matches
  natural language ("db write", "external api", "merge to main", "delete file") but not the
  literal enum tokens `db_write`/`external_api`/`merge_pr`/`file_delete`. A one-liner using
  those literal tokens slips the second-signal path. Fix: add the underscore enum-token forms.
- **F4 (P1) — partly real** → fix-round 2 (safe hardening). Structurally the critic IS the spec
  critic (takes the shape_session, walks the nine rules, emits the JSON envelope) — F4's
  structural finding is closed. But `apply_rule_1_acceptance_support` is satisfied by a GLOBAL
  has_confirmed_assumption flag, so one unrelated confirmed assumption suppresses the
  AcceptanceUnsupported rejection for every acceptance. Hardened to per-acceptance support.
  (Deeper 9-rule semantic correctness is also covered by the escalated_to_human Grade-review
  handoffs — see closure.yaml.)

F7 closed evidence: write_session returns Err(CriticRejected) on a rejected verdict after
writing critic/session artifacts; outcome.md absent; CLI exits non-zero
(f7_rejected_run_skip_returns_error_after_writing_critic_artifact). F1/F3/F6 unchanged.
