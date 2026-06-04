# /bs

Execute the next bootstrap backlog task end-to-end. Do not only describe the workflow. Perform the shell operations, create the cycle artifacts, run the vendor driver, verify, create/merge the PR when gates allow, and close ledger plus backlog atomically.

## Preconditions

1. Resolve repo root with `git rev-parse --show-toplevel` and `cd` there.
2. Read `~/.claude/skills/bs/contract.md` before executing.
3. Load `.bootstrap.yaml`; validate binding, contract hash, `compatible_range`, runtime manifest hashes, backlog schema, and red-line docs.
4. Run the startup (pre-start) gate via `${runtime}/preflight.sh` before any start commit or cycle directory creation. If it exits non-zero, escalate without creating cycle artifacts.
5. Reject if the working tree is dirty, current branch is not `main`, or any backlog task is `in_progress`.
6. Select the lexicographically smallest pending task whose dependencies are completed. Skip `B-000`.

## Execution flow

1. Run Step 1 self-containment gate for the selected task:
   - required fields present;
   - `status == pending`;
   - all dependencies completed;
   - each `spec_refs` path exists after stripping anchors;
   - red-line docs are read.
2. Start the task on `main`:
   - edit `.bootstrap/backlog.yaml` from `pending` to `in_progress`;
   - keep `closed_in`, `closed_at`, `escalation_reason`, and `parked_reason` null;
   - commit `bs: start <ID> <title>`;
   - push `origin main`;
   - verify local `HEAD == origin/main`.
3. Create the cycle directory under `${binding.cycle_dir_root}/cycle-<NNN>/` and a worktree branch `bootstrap/cycle-<NNN>` from the pushed start commit.
4. Write initial artifacts:
   - `cycle.yaml` with binding snapshot, task snapshot, start commit, branch, timestamps;
   - `step_events.jsonl` using strict started/terminal pairs and `attempt` for retries;
   - `outcome.md`, evidence directory, and `preflight_initial.yaml` copied from the pre-start gate output (record only; this is not `step_0`).
5. Run the 11-step cycle from the contract:
   - Shape outcome and acceptance;
   - Conduct via `${runtime}/conduct.sh` with evidence captured. MUST NOT call `codex_driver.py`, `codex`, or `codex exec --json` directly;
   - The conduct driver starts a non-ephemeral Codex thread, sets the goal via `thread/goal/set` with a `BS_GOAL_V1` JSON header (`run_id`, absolute `outcome.md` path, sha256), then sends one fixed task-content-free launcher containing only the outcome path, sha256, and required `BS_OUTCOME_READ` JSON marker. It MUST NOT send text `/goal @<outcome.md>`, wrap/inject a conduct prompt, use `codex exec`, or fall back to another transport;
   - Before each Grade round, always run `${runtime}/grade_verify.py --cycle-dir <cycle-dir> --binding-file <binding-snapshot> --task-id <ID> --task-type <type> --round <N> --worktree <worktree>`. The helper selects `verify.grade.<type>`, maps legacy `${binding.verify_command}` to docs compatibility, fails for code tasks without `verify.grade.code`, or writes an explicit `not_required` result only when the binding/task declares verification is not required. This must create `evidence/grade_verify_round_<N>.yaml` before `grade_round_<N>.md` is authored. Legacy `${binding.verify_command}` is only compatibility input/final smoke and cannot substitute for per-round Grade verify helper invocation.
   - Grade by writing `grade_round_<N>.md` with parseable fenced `grade_summary` and `acceptance_status` YAML blocks. For code tasks, `grade_round_<N>.md` MUST cite `evidence/grade_verify_round_<N>.yaml`; missing required verify evidence is a blocking failure. For medium/high code tasks it MUST also include `adversarial_checks`, `trust_surface_inventory`, and `deferred_claims`. `grade_summary.p0_count + p1_count` is the blocking-failure metric.
   - For `type == code` and `risk_level in {medium, high}`, immediately run `${runtime}/grade_lint.py --task-type <type> --risk-level <risk_level> --grade-file grade_round_<N>.md --outcome-file outcome.md --evidence-file evidence/grade_lint_round_<N>.json` after each Grade round and before fix-loop decisions. Lint failure is a blocking Grade failure; do not proceed to auto-merge with a failing or missing applicable lint result.
   - If `grade_round_<g>.md` has blocking failures and `g < max_fix_rounds` (3), run `${runtime}/reshape_fix_round.py --cycle-dir <cycle-dir> --outcome-file <outcome.md> --grade-file grade_round_<g>.md --round <g+1>` before any fix delegation. The helper archives `outcome.v<g>.md`, folds only structured failed acceptance IDs plus optional bounded corrections into `outcome.md`, and emits the `bs-fix-round` marker.
   - Then run `${runtime}/conduct.sh --fix-round <g+1>`; it re-reads the re-shaped `outcome.md` and refuses to launch if the archive, grade file, or marker is missing. Never inject grade findings as a prompt and never pass a second `/goal` file.
   - Run `${runtime}/grade_verify.py ... --round <g+1>` again before the fix Grade is authored.
   - Re-grade as `grade_round_<g+1>.md`, citing `evidence/grade_verify_round_<g+1>.yaml` when required, then re-run applicable `grade_lint.py` for round `<g+1>`. Escalate if the helper refuses because `R > 3`, P0+P1 did not strictly decrease, lint remains failing, or if P0+P1 remains > 0 after round 3.
   - run `${binding.verify_command}` in the worktree before PR as deprecated compatibility/final smoke;
   - create PR from the worktree branch;
   - use balanced auto-merge only when P0/P1 counts are zero, required Grade verify evidence passes, checks pass, and the latest applicable `grade_lint.py` evidence is pass;
   - merge PR, pull latest `main`, then close.
6. Step 10 close is one atomic commit on `main` after PR merge:
   - append ledger entry to `${binding.ledger}`;
   - change backlog task to `completed` or `escalated`;
   - set `closed_in` and `closed_at`;
   - before proceeding to the close commit, run `python3 ${runtime}/validate_events.py <cycle-dir>/step_events.jsonl`;
   - if validation exits non-zero, do not close; repair the log append-only by appending a correcting or next-attempt event, never editing/inserting prior history, then re-run until it passes;
   - stage only ledger + backlog;
   - commit `ledger+backlog: close <cycle> <ID> <title>`;
   - push `origin main`;
   - append `step_10 completed` with the close commit.

## Hard stops

- If a side-effecting step fails after `started`, append `failed` for that same `step` and `attempt`; do not leave an unclosed `started` event.
- If retrying a step, increment `attempt` and start a new pair. Never nest a second `started` event for the same `(step, attempt)`.
- If Step 10 cannot atomically commit ledger + backlog, revert those two files and escalate.
- If user decision is required, stop with exact options; do not infer approval.
