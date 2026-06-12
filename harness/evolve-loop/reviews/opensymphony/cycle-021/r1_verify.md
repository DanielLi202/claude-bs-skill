# r1-verify — cycle-021 remediation @ead656e (round 1; fresh-context codex, read-only)

Round 0 (77d5d57) failed on F2 (fail-open missing-events traceability); round-1 commit ead656e
made the check fail-closed (critic.traceability.events_unreadable) with regression test
f2_missing_events_jsonl_is_rejected_fail_closed. Round 1 re-verified ALL five findings fresh.

```yaml
r1_verify:
  remediation_commit: "ead656e"
  findings:
    - id: C1
      closed: true
      production_locus_fixed: true
      evidence: "crates/symphony-evolve/src/git_write.rs:71-88 now uses exit-status prechecks via git_success before git log; git_write.rs:109-177 routes all git calls through stable_git_command with LC_ALL=C and LANG=C. Regression: c1_git_revert_detection_uses_exit_status_under_localized_parent_env at crates/symphony-evolve/src/lib.rs:603-679 would fail on old localized stderr matching."
    - id: F1
      closed: true
      production_locus_fixed: true
      evidence: "crates/symphony-evolve/src/git_write.rs:49-60 rewrites the artifact after the first commit and commits the metadata patch; git_write.rs:245-331 renders full D-P21 metadata for both L1 and L2, including commit_hash and git revert hint. Regression: f1_post_commit_metadata_is_patched_and_committed at lib.rs:690-720 and f1_l2_pattern_artifact_carries_dp21_metadata at lib.rs:722-748."
    - id: F2
      closed: true
      production_locus_fixed: true
      evidence: "crates/symphony-evolve/src/critic.rs:17-151 now rejects missing sources, unreadable/malformed grade_result.md, missing/unreadable events.jsonl, absent grade_completed, generic/no-anchor candidates, grade inconsistency, risk/path violations, and returns structured rule_id/reason. Regression: f2_missing_events_jsonl_is_rejected_fail_closed at lib.rs:822-837 specifically covers the round-1 missing-events fail-open; other F2 tests are lib.rs:750-820."
    - id: F3
      closed: true
      production_locus_fixed: true
      evidence: "crates/symphony-evolve/src/batch.rs:127-153 records per-candidate verdicts and appends the evolve-log commit; batch.rs:382-437 computes real counts from BatchReport; batch.rs:487-535 writes the evolve log then commits it with commit_paths_with_message. Regression: f3_evolve_log_is_committed_with_real_counts_and_verdicts at lib.rs:905-944."
    - id: F4
      closed: true
      production_locus_fixed: true
      evidence: "crates/symphony-evolve/src/lightweight.rs:132-164 returns the existing digest on replay and commits the digest plus MEMORY.md; lightweight.rs:167-200 prevents duplicate Recent Runs index entries by grade_result_ref. Regression: f4_lightweight_digest_replay_is_idempotent_by_run_id at lib.rs:434-456 and f4_lightweight_digest_write_is_committed at lib.rs:458-478."
  overall: pass
  notes: "Read-only verification only; tests were inspected, not executed. F2 round-1 missing-events failure mode is now fail-closed and regression-tested."
```
