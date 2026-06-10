# /bs-resume

Resume exactly one interrupted bootstrap cycle. This command is side-effecting only after event-state validation.

## Flow

1. Resolve repo root, load `.bootstrap.yaml`, validate contract hash and backlog schema.
2. Find exactly one `in_progress` task. If none or more than one exists, stop.
3. Locate its latest cycle directory from `cycle.yaml`/ledger/backlog metadata.
4. Parse `step_events.jsonl` with strict `(step, attempt)` pairing:
   - every `started` must have one terminal `completed` or `failed`;
   - terminal without matching `started` is invalid;
   - nested `started` for the same `(step, attempt)` is invalid;
   - retries must use incremented `attempt`.
5. If parsing fails, stop and report the exact line(s). Do not use last-write-wins.
6. If the last terminal is `failed`, ask for one explicit decision: redo that attempt, start next attempt, mark escalated, or abort.
7. Continue at the next contract step only after the state machine is valid.

## Merged-PR Step-10 recovery

Use this path only when preflight or doctor reports
`recovery_required=merged_pr_needs_step10_close cycle=<NNN> task=<ID>`. This is a
post-merge close-gap recovery, not permission to start a new cycle.

1. Re-resolve the same repo root, binding, backlog, and latest cycle directory.
   Cite:
   - the single `in_progress` backlog row (`.bootstrap/backlog.yaml`, task ID,
     title, status);
   - the cycle directory (`cycle-<NNN>/cycle.yaml`) showing the same `task_id`;
   - `auto_merge_gate.yaml` showing `decision: merge` and the PR number/URL.
2. Verify the PR merge SHA is already contained in main before appending any
   terminal recovery event. Required evidence:
   - the merge SHA source (PR metadata, `auto_merge_gate.yaml` field, or another
     durable cycle artifact; if no merge SHA can be established, stop);
   - `git fetch origin main` or equivalent freshness evidence;
   - `git merge-base --is-ancestor <merge_sha> origin/main` exit 0;
   - `git log -1 --oneline <merge_sha>` and `git branch -r --contains <merge_sha>`
     or equivalent containment output.
3. Parse `step_events.jsonl` with the strict pairing rules above. If `step_7`
   has an open `started` event and the merge-SHA containment check passed,
   append `step_7 completed` with the event helper. The event outcome must cite
   PR number/URL, merge SHA, `origin/main` containment evidence, and that this is
   a `merged_pr_needs_step10_close` recovery. Do not edit or insert old lines.
4. If event validation reports a contract-recognized append-only repair case
   (for example `terminal_without_started`), append the first-class `repair`
   event required by `/bs` (`repair_kind`, target step/attempt/line, sha256 of
   the exact orphan terminal line, reason, optional operator), then re-run
   validation. For any non-repairable pairing error, stop and escalate; do not
   fabricate terminal events.
5. Pull main with fast-forward evidence after the recovery event append:
   `git pull --ff-only origin main`. Cite the command output and resulting
   `HEAD`/`origin/main` SHA. If the pull is not fast-forward, stop.
6. Run the normal Step-10 atomic close from `/bs`:
   - append `step_10 started`;
   - run `python3 ${runtime}/validate_events.py <cycle-dir>/step_events.jsonl --allow-open-current step_10`;
   - append the ledger entry, change the backlog task to `completed` or
     `escalated`, set `closed_in`/`closed_at`, run `sync_status_marker.py` when
     declared, and stage exactly the close files;
   - commit `ledger+backlog: close <cycle> <ID> <title>`;
   - push `origin main`;
   - append `step_10 completed` with the close commit SHA;
   - run full post-close `validate_events.py`.

The recovery report must cite these artifacts explicitly: merge containment
command output, appended recovery event line(s), repair event line(s) if any,
`validate_events.py` before-close and post-close outputs, ledger diff, backlog
diff, status-marker diff when present, close commit SHA, push output, and final
`HEAD == origin/main` proof.

## Close rule

When resume reaches Step 10, use the same atomic ledger + backlog commit rule as `/bs`.
