# r1-verify round 0 — cycle-020 remediation (adversarial fresh-context, codex read-only)

Verdict: **overall_closed: false** (confidence 0.86). F3, F4, F5 CLOSED. F1, F2, F6 refuted
(real fixable bugs); F7 refuted at a fundamental limit (honest-scope + best-effort). All
confirmed against the actual code by the orchestrator before iterating. Drives a fix-round.

- **F1 (P0)** — IntegrityBaseline watches only outcome.md + declared context_pointers, so a command
  that mutates an UNREFERENCED source file (e.g. README.md) exits 0 and passes; and there is no
  test for symlink escape / absolute artifact path / memory-user / patterns-imported. Fix-round:
  broaden the integrity snapshot to detect any non-output workspace mutation + add the missing
  containment tests.
- **F2 (P0)** — apply_top_level_high_risk_gates writes every unmarked top-level action onto
  evaluations.first_mut(), so multiple actions collide on evaluations[0] and a later human_review
  overwrites an earlier fail. Fix-round: one representation per top-level action; a fail must not be
  overwritten; overall fails if any high-risk action lacks its second_signal/human_review.
- **F6 (P1)** — the critic checks evidence_refs non-empty + trace_ref string presence but never reads
  the referenced files, so a grade_result citing a nonexistent evidence/trace_grade_a1.json is
  approved. Fix-round: the critic must verify referenced evidence/trace files EXIST + are non-trivial.
- **F7 (P1)** — collect_descendants snapshots the shell's process tree at timeout; a double-fork /
  setsid daemon that REPARENTS to init before timeout escapes the tree. This is the fundamental
  limit of tree-walk reaping (no cgroup / job-object / PID-namespace). Fix-round: best-effort
  workspace-cwd descendant scan + HONESTLY scope the no-orphan claim (a deliberately-daemonizing
  double-fork process is a documented residual requiring OS-level containment, deferred) — not an
  over-claim.

F3/F4/F5 confirmed closed: F3 llm_judge_passed is always false for high-risk (no substring forge);
F4 hard gate requires readable non-self evidence + structured_stub_verdict always false (fail-closed);
F5 required_exit_code / cwd / min_size_bytes parsed and enforced.
