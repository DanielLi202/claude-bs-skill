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

## Close rule

When resume reaches Step 10, use the same atomic ledger + backlog commit rule as `/bs`.
