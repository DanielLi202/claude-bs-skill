# Remediation Grade — cycle-021 C1 + F1-F4 (symphony-evolve M7 Evolve Agent)

**cycle**: cycle-021
**task**: Stage-5 remediation of C1 + F1-F4 in `crates/symphony-evolve`
**branch**: `/private/tmp/remediate-cycle-021` `remediate/cycle-021` @ `77d5d57`
**graded_at**: 2026-06-12
**grade_lint**: same-iteration canary for the v1.4.16 Evolve-agent facets

---

## grade_summary

```yaml
grade_summary:
  task_id: cycle-021-remediation
  round: 0
  risk_level: low
  p0_count: 0
  p1_count: 0
  p2_count: 0
  p3_count: 0
  overall_result: pass
  grade_verify_status: pass
  cargo_test: "cargo nextest run --workspace"
  cargo_test_pass: 207
  cargo_test_fail: 0
  notes: >
    All five remediation acceptances (C1 escalation blocker + r1 F1-F4) are covered by
    real symphony-evolve regression tests under
    /private/tmp/remediate-cycle-021/crates/symphony-evolve/src. The full gate stack is
    green: cargo build --workspace, cargo fmt --all --check, cargo clippy --workspace
    --all-targets -- -D warnings, cargo nextest run --workspace (207 passed, 1 skipped),
    bash scripts/verify-docs.sh.
```

---

## acceptance_status

```yaml
acceptance_status:
  - id: a1
    status: pass
    severity: P0
    text: "C1 locale-independent git error detection closed"
    evidence_ref: "cargo nextest run --workspace: tests::c1_git_revert_detection_uses_exit_status_under_localized_parent_env"
  - id: a2
    status: pass
    severity: P0
    text: "F1 D-P21 post-commit metadata persistence closed"
    evidence_ref: "cargo nextest run --workspace: tests::f1_post_commit_metadata_is_patched_and_committed; tests::f1_l2_pattern_artifact_carries_dp21_metadata"
  - id: a3
    status: pass
    severity: P1
    text: "F2 critic/pre-filter substance closed"
    evidence_ref: "cargo nextest run --workspace: tests::f2_no_source_candidate_is_rejected_with_structured_verdict; tests::f2_anchorless_candidate_is_rejected_before_critic; tests::f2_generic_template_candidate_is_rejected_before_critic; tests::f2_inconsistent_grade_claim_is_rejected"
  - id: a4
    status: pass
    severity: P0
    text: "F3 evolve-log write-with-git and real counts closed"
    evidence_ref: "cargo nextest run --workspace: tests::f3_evolve_log_is_committed_with_real_counts_and_verdicts"
  - id: a5
    status: pass
    severity: P1
    text: "F4 L0.5 lightweight commit and idempotence closed"
    evidence_ref: "cargo nextest run --workspace: tests::f4_lightweight_digest_write_is_committed; tests::f4_lightweight_digest_replay_is_idempotent_by_run_id"
```

---

## spec_compliance_matrix

```yaml
spec_compliance_matrix:
  - acceptance_id: a1
    spec_ref: "docs/ops/dogfood-log.md cycle-021 escalation reason; docs/agents/evolve/AGENT.md write-with-git red line"
    status: pass
    severity_if_fail: P0
    evidence_ref: "tests::c1_git_revert_detection_uses_exit_status_under_localized_parent_env; git_write.rs pins LC_ALL=C and LANG=C on every git invocation and keys revert/conflict detection off exit status, not localized error text"
    notes: >
      The escalation blocker is closed at the production locus git_write.rs (not a test
      helper): every git invocation sets env LC_ALL=C and LANG=C, and detection is
      exit-status/porcelain based. The regression test runs the previously failing
      detection path with a zh_CN.UTF-8 parent locale in the environment and passes.
  - acceptance_id: a2
    spec_ref: "docs/architecture/schemas/memory-artifact.md:35-43,91,101 (D-P21 metadata); docs/agents/evolve/AGENT.md:161-166; prompts/agents/evolve/role.md:87-91,150-166"
    status: pass
    severity_if_fail: P0
    evidence_ref: "tests::f1_post_commit_metadata_is_patched_and_committed proves the persisted artifact's commit_hash is patched from the pending placeholder to the real sha of the write commit (pending -> 0a1b2c3 shape in the test fixture) with a post-commit readback verified after the git commit; the persisted revert_hint: 'git revert 0a1b2c3' cites that real sha. tests::f1_l2_pattern_artifact_carries_dp21_metadata proves L2 pattern PROPOSAL.md artifacts carry the full D-P21 metadata block (commit_hash, revert_hint, source_run_ids, validation, owner_scope)."
    notes: >
      No 'pending' placeholder survives persistence: after the artifact write commit
      succeeds, the artifact is re-opened, commit_hash and revert_hint are patched to the
      real commit sha, and the patch itself is committed (post-commit readback then
      verifies the file content). L2 patterns no longer drop the metadata block.
  - acceptance_id: a3
    spec_ref: "prompts/agents/evolve/critic.md:22-48; prompts/agents/evolve/role.md:81-85; docs/agents/evolve/AGENT.md:190-197 (critic contract + mechanical pre-filter)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "tests::f2_no_source_candidate_is_rejected_with_structured_verdict (candidate without a source grade_completed/grade_result reference is rejected — source_run_id traceability is required); tests::f2_anchorless_candidate_is_rejected_before_critic and tests::f2_generic_template_candidate_is_rejected_before_critic (validation text must contain an observable anchor — file path, command, or event id — and is rejected when it matches the generic-template blacklist, e.g. the literal 'Read the cited grade_result.md...' filler); tests::f2_inconsistent_grade_claim_is_rejected (grade-consistency: a candidate claim that contradicts the cited grade outcome's overall_status is rejected); review_candidate returns a per-candidate structured verdict (accept/reject + rule id + reason) persisted in the evolve-log body."
    notes: >
      The pre-filter and critic now enforce grade_completed source traceability,
      validation observable-anchor + template-blacklist screening, grade consistency
      cross-checks against overall_status, and per-candidate structured verdicts. The
      generated candidate validation text now embeds the concrete run-scoped artifact
      paths instead of the generic template.
  - acceptance_id: a4
    spec_ref: "docs/agents/evolve/AGENT.md:105,112 (write-with-git red line); docs/architecture/schemas/evolve-log.md:163-205 (frontmatter counts)"
    status: pass
    severity_if_fail: P0
    evidence_ref: "tests::f3_evolve_log_is_committed_with_real_counts_and_verdicts — the evolve-log artifact is git committed through the same write-with-git path as candidate artifacts, and its frontmatter counts (total_candidates, l1_written, l2_written, skipped_per_recent_revert) match the actual candidate writes of the batch (non-zero after a batch that wrote candidates)."
    notes: >
      write_evolve_log now routes through the write-with-git path; every memory-artifact
      write (L1 and L2) and the evolve-log itself is committed. The hardcoded-zero counts
      are gone: counts are computed from the real batch results, so the canonical batch
      ledger no longer lies.
  - acceptance_id: a5
    spec_ref: "docs/architecture/schemas/lightweight-memory.md:17,84-96 (L0.5 git commit + append-only idempotent replay)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "tests::f4_lightweight_digest_write_is_committed — the recent-runs digest write and MEMORY.md index update produce a git commit; tests::f4_lightweight_digest_replay_is_idempotent_by_run_id — replaying the same digest produces no duplicate Recent Runs line (exactly one line per run_id, MEMORY.md unchanged on replay)."
    notes: >
      write_recent_run_digest now guards on the run_id/grade_result_ref already being
      present (idempotent replay) and commits the L0.5 mechanical write per the
      lightweight-memory schema.
```

---

## negative_regression_tests

```yaml
negative_regression_tests:
  - id: nr1
    acceptance_id: a1
    scenario: "git revert/conflict detection under a zh_CN.UTF-8 parent locale still detects the condition (fails against the old localized-error-text matching)"
    test_name: "tests::c1_git_revert_detection_uses_exit_status_under_localized_parent_env"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo nextest run --workspace; git_write.rs env LC_ALL=C / LANG=C pinning + exit-status detection"
  - id: nr2
    acceptance_id: a2
    scenario: "persisted artifact retains no pending placeholder: commit_hash patched to the real write-commit sha and read back post-commit"
    test_name: "tests::f1_post_commit_metadata_is_patched_and_committed"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo nextest run --workspace; post-commit readback asserts commit_hash != pending and revert_hint contains 'git revert <real sha>'"
  - id: nr3
    acceptance_id: a2
    scenario: "L2 pattern artifact without the D-P21 metadata block would fail; the rendered PROPOSAL.md carries commit_hash, revert_hint, source_run_ids, validation, owner_scope"
    test_name: "tests::f1_l2_pattern_artifact_carries_dp21_metadata"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo nextest run --workspace; render_candidate L2 path emits the full metadata block"
  - id: nr4
    acceptance_id: a3
    scenario: "candidate with no source grade_completed/grade_result reference is rejected with a structured verdict"
    test_name: "tests::f2_no_source_candidate_is_rejected_with_structured_verdict"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest run --workspace; per-candidate structured verdict (reject + rule id + reason) is persisted"
  - id: nr5
    acceptance_id: a3
    scenario: "candidate whose validation text lacks an observable anchor is rejected by the mechanical pre-filter"
    test_name: "tests::f2_anchorless_candidate_is_rejected_before_critic"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest run --workspace; validation observable-anchor requirement"
  - id: nr6
    acceptance_id: a3
    scenario: "candidate whose validation matches the generic-template blacklist is rejected before the critic"
    test_name: "tests::f2_generic_template_candidate_is_rejected_before_critic"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest run --workspace; template blacklist screening"
  - id: nr7
    acceptance_id: a3
    scenario: "candidate claim inconsistent with the cited grade outcome (e.g. 'what worked' citing a failed acceptance) is rejected"
    test_name: "tests::f2_inconsistent_grade_claim_is_rejected"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest run --workspace; grade-consistency cross-check against overall_status"
  - id: nr8
    acceptance_id: a4
    scenario: "evolve-log written without a git commit or with hardcoded-zero counts would fail; the log is committed and counts match the batch"
    test_name: "tests::f3_evolve_log_is_committed_with_real_counts_and_verdicts"
    status: pass
    severity_if_fail: P0
    evidence_ref: "cargo nextest run --workspace; git log shows the evolve-log commit; frontmatter counts total_candidates/l1_written/l2_written reflect actual candidate writes"
  - id: nr9
    acceptance_id: a5
    scenario: "double-write of the same digest leaves exactly one Recent Runs line (no duplicate) in MEMORY.md"
    test_name: "tests::f4_lightweight_digest_replay_is_idempotent_by_run_id"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest run --workspace; same digest replay is a no-op, MEMORY.md unchanged"
  - id: nr10
    acceptance_id: a5
    scenario: "the L0.5 recent-runs/MEMORY.md write without a git commit would fail; the write produces a commit"
    test_name: "tests::f4_lightweight_digest_write_is_committed"
    status: pass
    severity_if_fail: P1
    evidence_ref: "cargo nextest run --workspace; git log shows the lightweight write commit"
```

---

## secret_leakage_audit

```yaml
secret_leakage_audit:
  status: pass
  evidence_ref: "manual review of /private/tmp/remediate-cycle-021/crates/symphony-evolve/src plus cargo nextest run --workspace"
  checked_surfaces:
    - "crates/symphony-evolve/src/git_write.rs"
    - "crates/symphony-evolve/src/memory.rs"
    - "crates/symphony-evolve/src/critic.rs"
    - "crates/symphony-evolve/src/batch.rs"
    - "crates/symphony-evolve/src/lightweight.rs"
  cleartext_secret_probe: not_applicable
  rationale: >
    symphony-evolve reads local run artifacts (grade_result.md, outcome.md) and writes
    local memory/pattern/log artifacts via git; the remediation introduces no credential,
    bearer-token, API-key, OAuth, auth-header, log-redaction, or network surface, so
    cleartext secret probing is not applicable to this delta.
```

---

## dependency_spec_review

```yaml
dependency_spec_review:
  - name: "(no new dependencies)"
    spec_ref: "docs/architecture/tech-stack.yaml; workspace Cargo.toml unchanged by this remediation"
    status: pass
    severity_if_fail: P1
    evidence_ref: "git diff 4625b5c..77d5d57 -- Cargo.toml Cargo.lock crates/symphony-evolve/Cargo.toml is empty; the remediation touches only src files within crates/symphony-evolve"
    notes: >
      The remediation adds no external crate and changes no version pin; all fixes use
      existing workspace dependency wiring.
```

---

## Evolve-agent contract evidence (v1.4.16 facets)

Every token below is tied to a real code path or named regression test in
`/private/tmp/remediate-cycle-021/crates/symphony-evolve/src`.

- D-P21 metadata persisted post-commit: commit_hash is patched from the pending
  placeholder to the real write-commit sha (pending -> 0a1b2c3 shape in the fixture) and a
  post-commit readback verifies the persisted file after the git commit;
  `tests::f1_post_commit_metadata_is_patched_and_committed` proves no placeholder
  survives.
- Actionable revert hint: the persisted artifact's revert_hint: "git revert 0a1b2c3"
  cites the real commit sha, never the pending placeholder.
- L2 pattern metadata: L2 pattern PROPOSAL.md artifacts carry the full D-P21 metadata
  block (commit_hash, revert_hint, source_run_ids, validation, owner_scope);
  `tests::f1_l2_pattern_artifact_carries_dp21_metadata` proves it.
- Critic traceability: every candidate must cite its source grade_completed /
  grade_result.md (source_run_id traceability) or it is rejected;
  `tests::f2_no_source_candidate_is_rejected_with_structured_verdict`.
- Pre-filter anchors: candidate validation text must contain an observable anchor (file
  path, command, or event id) and is rejected when it matches the generic-template
  blacklist; `tests::f2_anchorless_candidate_is_rejected_before_critic` and
  `tests::f2_generic_template_candidate_is_rejected_before_critic`.
- Grade-consistency: candidate claims are cross-checked against the cited grade's
  overall_status and inconsistent claims are rejected;
  `tests::f2_inconsistent_grade_claim_is_rejected`.
- Per-candidate structured verdict: review_candidate returns accept/reject + rule id +
  reason per candidate, persisted in the evolve-log body.
- The evolve-log artifact is git committed via the same write-with-git path as candidate
  artifacts; `tests::f3_evolve_log_is_committed_with_real_counts_and_verdicts`.
- Every memory-artifact write (L1 and L2) goes through write-with-git and is committed
  with a commit_hash recorded in the artifact.
- Real counts: the evolve-log frontmatter counts (total_candidates, l1_written,
  l2_written, skipped_per_recent_revert) match the actual candidate writes of the batch.
- L0.5 commit: the recent-runs digest write and MEMORY.md index update produce a git
  commit; `tests::f4_lightweight_digest_write_is_committed`.
- L0.5 idempotence: replaying the same digest produces no duplicate Recent Runs line
  (exactly one line per run_id, MEMORY.md unchanged on replay);
  `tests::f4_lightweight_digest_replay_is_idempotent_by_run_id`.

## Gate evidence

- `RUSTC_WRAPPER= cargo build --workspace` → Finished dev profile
- `RUSTC_WRAPPER= cargo fmt --all --check` → exit 0
- `RUSTC_WRAPPER= cargo clippy --workspace --all-targets -- -D warnings` → Finished, no warnings
- `RUSTC_WRAPPER= cargo nextest run --workspace` → 207 tests run: 207 passed, 1 skipped
- `bash scripts/verify-docs.sh` → verify-docs OK (all checks + semantic guardrails D1-D9)
