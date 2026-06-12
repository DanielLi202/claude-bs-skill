# r1-verify round 0 — cycle-021 remediation @77d5d57 (fresh-context codex, read-only)

Verdict: overall FAIL — C1/F1/F3/F4 closed; F2 open (missing events.jsonl accepted fail-open, no regression test).

```yaml
r1_verify:
  remediation_commit: "77d5d57"
  findings:
    - id: C1
      closed: true
      production_locus_fixed: true
      evidence: "r1.md:44-47; git_write.rs:71-78 now uses rev-parse exit status before git log, and git_write.rs:172-179 forces LC_ALL/LANG=C for all git children. Regression: c1_git_revert_detection_uses_exit_status_under_localized_parent_env at lib.rs:603-680 uses fake localized git and would fail the old stderr-text/env-leaking path."
    - id: F1
      closed: true
      production_locus_fixed: true
      evidence: "r1.md:24-28; git_write.rs:49-56 patches artifact metadata after the artifact commit, git_write.rs:245-250 gives L2 patterns the same metadata block, and git_write.rs:262-341 renders D-P21 fields including revert_hint/commit_hash. Regressions: f1_post_commit_metadata_is_patched_and_committed lib.rs:690-720; f1_l2_pattern_artifact_carries_dp21_metadata lib.rs:722-748."
    - id: F2
      closed: false
      production_locus_fixed: false
      evidence: "r1.md:29-33; critic.rs:17-143 adds structured verdicts, source grade parsing, anchors, template rejection, risk, and grade consistency, but critic.rs:70-78 only checks events.jsonl when fs::read_to_string succeeds. A missing events.jsonl still passes, so grade_completed traceability is not enforced. Tests at lib.rs:751-820 cover no-source, anchorless, generic template, and inconsistent grade, but not the missing-events failure mode."
    - id: F3
      closed: true
      production_locus_fixed: true
      evidence: "r1.md:34-38; batch.rs:150-153 now commits the evolve log and records the commit; batch.rs:395-437 derives real candidate counts; batch.rs:487-535 writes counts and commits the log path. Regression: f3_evolve_log_is_committed_with_real_counts_and_verdicts lib.rs:888-927 checks nonzero counts/verdicts and git log for the log artifact."
    - id: F4
      closed: true
      production_locus_fixed: true
      evidence: "r1.md:39-43; lightweight.rs:132-164 skips existing run digests and commits digest+MEMORY.md; lightweight.rs:196-198 prevents duplicate Recent Runs lines; lightweight.rs:279-303 finds existing digest files by run_id. Regressions: f4_lightweight_digest_replay_is_idempotent_by_run_id lib.rs:434-456; f4_lightweight_digest_write_is_committed lib.rs:458-478."
  overall: fail
  notes: "F2 remains open because missing events.jsonl/grade_completed evidence is accepted in production and lacks a regression test. Tests were inspected, not executed, to preserve read-only verification."
```
