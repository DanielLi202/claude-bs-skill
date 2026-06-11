# r1-verify round 1 — cycle-020 remediation (after fix-round 1d1a3ce)

Verdict: **overall_closed: false** (confidence 0.78). F2, F3, F4, F5, F7 CLOSED. F1, F6 still open
at the fundamental-limit / deferred-LLM-critic boundary; each has a cheap best-effort hardening
worth one more fix-round, after which the residual is documented + escalated.

- **F1 (P0)** — artifact-path containment is fixed (traversal/symlink/absolute/forbidden-root all
  rejected + tests), but `evaluate_command` runs raw `sh -c <command>` with NO forbidden-root guard
  on the command TEXT, so a command `cat .symphony/memory-user/x` reads a forbidden root. A
  command-execution verifier cannot fully sandbox arbitrary commands without OS-level containment
  (cgroup/namespace) — but the OBVIOUS case (argv references a forbidden root) is cheaply guardable.
  Fix-round: add a forbidden-command-text guard (reject commands referencing memory-user/
  patterns-user/patterns-imported) + test + honest-scope comment for the un-sandboxable residual.
- **F6 (P1)** — the critic now reads referenced files (existence + non-empty), but a non-empty but
  MEANINGLESS `{}` trace + keyword-matching body is still approved; full trace-semantics validation
  is the deferred LLM critic. Fix-round: parse the referenced trace JSON and reject a trivial /
  empty-object trace (best-effort) + test; deeper semantic validation stays escalated.

F2 closed (synthetic per-action high-risk gates; no overwrite). F3 closed (llm_judge_passed always
false for high-risk). F4 closed (hard gate fail-closed + self-trace rejected). F5 closed
(required_exit_code/cwd/min_size_bytes enforced). F7 closed for detached/new-session descendants in
the tree at timeout; the double-fork+setsid reparent-to-init escape is the documented OS-containment
residual.

## Convergence boundary (recorded)
After the F1-argv-guard + F6-trace-parse fix-round, the remaining residuals are FUNDAMENTAL /
DEFERRED, not fixable deterministically here: (a) full sandboxing of arbitrary acceptance commands
needs OS-level containment; (b) full trace-semantics validation needs the deferred LLM critic; (c)
the double-fork daemon escape needs OS containment. These are tracked under the escalated_to_human
Grade-review handoffs + documented in code. The loop converges there rather than chasing
unbounded/fundamental gaps.
