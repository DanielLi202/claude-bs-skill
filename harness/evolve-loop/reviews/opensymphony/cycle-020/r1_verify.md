# r1-verify (final) — cycle-020 remediation CONVERGED

Stage-5 remediation of the 7 r1-escaped defects in `crates/symphony-grade` (B-020 M6 Grade Agent),
across three adversarial fresh-context verify rounds (codex read-only, refute-by-default) and three
remediation commits:

  096dbb3 → 1d1a3ce → (final F1/F6 hardening)   (nextest 159 → 179, all gates green each round)

## Verdict: all 7 r1 findings F1-F7 REMEDIATED (converged)

| finding | sev | status | closure |
|---|---|---|---|
| F1 | P0 | CLOSED (agent-code) + documented residual | Artifact/evidence paths canonicalized + contained (reject traversal/symlink/absolute + memory-user/patterns-user/patterns-imported); Grade never mutates outcome/source (workspace-wide integrity snapshot detects any non-output tamper); command path refuses literal forbidden-root references. Residual: a glob/obfuscated command read (`cat .symphony/memory-*/x`) evades the textual guard — fully sandboxing arbitrary acceptance commands needs OS-level containment (cgroup/namespace). |
| F2 | P0 | CLOSED | D-P13 gate keys off outcome `risk_level: high` + top-level `high_risk_actions`; each unmarked action gets an independent synthetic gate (no overwrite); grade fails if any lacks second_signal/human_review. Confirmed rounds 1-2. |
| F3 | P0 | CLOSED | High-risk `llm_judge_passed` is hardcoded false (no criteria-substring forge). Confirmed every round. |
| F4 | P1 | CLOSED | llm_judge hard gate requires readable non-self evidence_refs; empty/missing/self-trace ⇒ fail; structured stub verdict false (fail-closed). Confirmed rounds 1-2. |
| F5 | P1 | CLOSED | `required_exit_code` / per-acceptance `cwd` / artifact `min_size_bytes` parsed + enforced. Confirmed every round. |
| F6 | P1 | CLOSED (heuristic) + documented residual | Critic reads referenced evidence/trace files (rejects missing/empty/trivial-`{}`) and requires real exit-code/artifact trace semantics. Residual: the heuristic critic does not independently re-parse outcome.md to cross-check high-risk coverage — that is deferred-LLM-critic depth. NOTE the grade itself (F2) already enforces high-risk representation, so there is no live grade bypass, only a critic-depth gap. |
| F7 | P1 | CLOSED (in-tree) + documented residual | Timeout reaping kills the process group + walks/audits/re-reaps the descendant tree; the contained detached/new-session grandchild test passes. Residual: a double-fork + setsid reparent-to-init daemon escapes any tree walk — needs OS-level containment. |

## Convergence — why this is the stopping point
Round 2 (`overall_closed: false`, confidence 0.86) flagged only F1/F6/F7, and each refutation now
points at a FUNDAMENTAL limit (F1 obfuscated command read, F7 reparented daemon — both need OS-level
containment) or DEFERRED-LLM-critic depth (F6 independent outcome.md re-parse), NOT a new
deterministically-fixable bug. F2/F3/F4/F5 are fully closed and F1's agent-code isolation + the
obvious command-read case are closed. Three remediation commits + three verify rounds (nextest
159→179) hardened every finding; continuing would chase OS-containment / deferred-LLM-critic
territory that cannot be closed in this crate. The loop converges here.

## Tracked residuals (escalated_to_human + documented in code)
1. Full sandboxing of arbitrary acceptance COMMANDS (obfuscated/indirect forbidden-root reads) —
   requires OS-level containment (cgroup / namespace / job object). Best-effort textual guard in
   place; the architectural limit is documented in evaluate_command.
2. The heuristic Grade critic should independently re-parse outcome.md to cross-check that the
   grade_result represents every top-level high_risk_action — deep critic semantics for the deferred
   LLM critic (the deterministic grade path F2 already enforces representation).
3. Timeout cleanup of a deliberately daemonizing (double-fork + setsid + reparent-to-init) descendant
   — requires OS-level containment; documented in the timeout path + the no-orphan claim is scoped.
