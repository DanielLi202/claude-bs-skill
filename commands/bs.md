# /bs

Execute the next bootstrap backlog task end-to-end. Do not only describe the workflow. Perform the shell operations, create the cycle artifacts, run the vendor driver, verify, create/merge the PR when gates allow, and close ledger plus backlog atomically.

## Preconditions

1. Resolve repo root with `git rev-parse --show-toplevel` and `cd` there.
2. Read `~/.claude/skills/bs/contract.md` before executing.
3. Load `.bootstrap.yaml`; validate binding, contract hash, `compatible_range`, backlog schema, and red-line docs.
4. Reject if the working tree is dirty, current branch is not `main`, or any backlog task is `in_progress`.
5. Select the lexicographically smallest pending task whose dependencies are completed. Skip `B-000`.

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
   - `outcome.md`, `preflight_initial.yaml`, and evidence directory.
5. Run the 11-step cycle from the contract:
   - Shape outcome and acceptance;
   - Conduct via `${runtime}/codex_driver.py` with evidence captured;
   - Grade and, if needed, run bounded fix rounds via `${runtime}/codex_fix_driver.py`;
   - run `${binding.verify_command}` in the worktree before PR;
   - create PR from the worktree branch;
   - use balanced auto-merge only when P0/P1 counts are zero and checks pass;
   - merge PR, pull latest `main`, then close.
6. Step 10 close is one atomic commit on `main` after PR merge:
   - append ledger entry to `${binding.ledger}`;
   - change backlog task to `completed` or `escalated`;
   - set `closed_in` and `closed_at`;
   - stage only ledger + backlog;
   - commit `ledger+backlog: close <cycle> <ID> <title>`;
   - push `origin main`;
   - append `step_10 completed` with the close commit.

## Hard stops

- If a side-effecting step fails after `started`, append `failed` for that same `step` and `attempt`; do not leave an unclosed `started` event.
- If retrying a step, increment `attempt` and start a new pair. Never nest a second `started` event for the same `(step, attempt)`.
- If Step 10 cannot atomically commit ledger + backlog, revert those two files and escalate.
- If user decision is required, stop with exact options; do not infer approval.
