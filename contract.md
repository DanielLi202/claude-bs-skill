# Bootstrap Development Workflow Contract v1.3

> Universal workflow contract for bootstrap-driven repositories. The contract owns orchestration semantics; each repository owns only its binding, backlog, ledger, verification command, and red-line documents.

## 1. Layer model

- **Skill layer**: this contract, `/bs*` commands, bundled runtime drivers, generic prompts, and YAML-only init templates.
- **Binding layer**: a repository `.bootstrap.yaml` plus `.bootstrap/backlog.yaml` and `.bootstrap/contract.sha256`.
- **Cycle artifact layer**: per-cycle scratch under the binding-declared cycle directory plus the binding-declared durable ledger.

The skill must not contain project-specific paths, product names, decision IDs, schemas, or council-member choices. The binding must not contain the 11-step workflow, severity rubric, command implementation, or driver algorithms.

## 2. Binding requirements

`/bs` discovers the git toplevel with `git rev-parse --show-toplevel`, reads `.bootstrap.yaml`, and rejects the run if schema or contract checks fail.

Required binding fields:

- `schema_version: 1`
- `contract.source_url`, `contract.source_tag`, `contract.source_commit`, `contract.source_sha256`, `contract.sha256_path`, `contract.compatible_range`
- `backlog`, `ledger`, `cycle_dir_root`, `red_lines`, `verify_command`
- optional `workflow_dir` override; null means use skill bundled runtime
- optional `register_prefixes` and `agent_prompts.*`

Contract verification is three-way: `.bootstrap.yaml.contract.source_sha256`, `.bootstrap/contract.sha256`, and the local skill `contract.md` sha256 must match. Semver compatibility uses `contract.compatible_range`; floating latest is forbidden.

## 3. Backlog requirements

`.bootstrap/backlog.yaml` schema version 1 contains `tasks[]`. Each task has:

- `id`: `^[A-Z]+-\d{3}$`; `B-000` is reserved for retroactive completed history and is skipped by next-task selection.
- `title`, `type`, `risk_level`, `status`, `blocked_by`, `spec_refs`
- optional `estimated_loc`, `acceptance_hints`, `non_goals_hints`
- closure fields: `closed_in`, `closed_at`, `escalation_reason`, `parked_reason`

Closed enums:

- `type`: `code`, `docs`, `infra`, `refactor`, `spec`
- `risk_level`: `low`, `medium`, `high`
- `status`: `pending`, `in_progress`, `completed`, `escalated`, `parked`

Parser checks are fail-fast: required fields, enum values, duplicate IDs, ID format, unknown dependencies, dependency cycles, parked/escalated reason invariants, and terminal `closed_in` invariants.

Next task is the lexicographically smallest pending task whose dependencies are completed.


## Expected Task Scale & Agent Autonomy

### Task scale

Bootstrap cycles span a wide range of task sizes:

- **TC-A** (~100 LOC): docs / tooling / spec patches; small validation cycles.
- **TC-B** (~thousands LOC): greenfield modules, large refactors, new daemon implementations. This is the **target task size** the workflow is designed for.
- **TC-C** (~500 LOC): mid-size refactors, documentation overhauls.

Early cycles in a fresh adopter's ledger may be predominantly TC-A (intentional validation runs). **Do not infer typical task size from prior cycle history** — task size is set by `backlog.yaml.tasks[*].estimated_loc` (or unknown if absent) and is the adopter's intent, not an emergent baseline.

If `estimated_loc` is **absent or null** for a task, the size is *unknown* — this is NOT a pause condition. Proceed to Step 2 Shape; the Shape agent will derive scope from `spec_refs` and `acceptance_hints`.

The Conduct driver (path A `codex app-server`) is designed to handle TC-B tasks in a single turn. If a single turn cannot produce the full implementation, that surfaces as a Step 3 `failed` event (heartbeat timeout / inferred completion exhaustion / vendor crash) and triggers the standard Step 5 fix loop, not a Step 2 pre-emptive pause.

### Agent autonomy bounds (normative)

The `/bs` agent **MUST NOT** pause or request user confirmation based on:

- Task LOC magnitude (absolute or relative to prior cycles)
- Subjective "task feels large / risky / unfamiliar" heuristics
- Comparison against prior cycle wall-clock or fix-loop counts
- Anything not enumerated below as a schema-defined gate

The agent **MUST** pause / escalate only on:

- Step 1 self-containment gate failure (missing required field, broken `spec_refs` path, unsatisfied `blocked_by`)
- Step 3 driver crash / heartbeat timeout / inferred completion fails after retry
- Step 4 P0+P1 > 0 after fix loop max iterations or non-strictly-decreasing
- Step 7 auto-merge gate fails (conflict / hook fail / pending review)
- Explicit `/bs park`, `/bs resume --escalate`, user-initiated abort
- Backlog/binding schema validation failure at startup
- `verify_command` non-zero exit

If the agent encounters a situation it considers concerning but not covered by the above gates, it **MUST proceed and record the concern as a `workflow_reflection.yaml` entry** in Step 9, rather than pause to ask. If experience shows a real new gate is needed, it gets added to the contract via a patch cycle (like this v1.3.1).

## 4. Main `/bs` flow

1. Find repo root, validate `.bootstrap.yaml`, contract hash, and backlog schema.
2. Reject if any task is already `in_progress`; use `/bs resume` instead.
3. Select the next unblocked pending task.
4. Run Step 1 self-containment gate: required fields, status precondition, closed enums, dependency closure, `spec_refs` length, and file/dir existence for `spec_refs` after stripping informational anchors.
5. On main with clean working tree, change the task to `in_progress`, commit `bs: start <ID> <title>`, push `origin main`, and verify remote main equals local HEAD.
6. Create the cycle directory and worktree branch from that pushed commit; write `cycle.yaml`, binding snapshot, and strict `step_events.jsonl` started/terminal attempt pairs.
7. Run the 11-step cycle: ingest, identify, shape, conduct, grade, fix loop, PR, auto-merge, escalation handling, reflection, ledger close.
8. Step 10 closes with one atomic commit on main containing both ledger append and backlog writeback.

## 5. Step events and resume

`step_events.jsonl` is append-only. Every step attempt emits exactly `started` and then either `completed` or `failed`. The state key is `(step, attempt)` where `attempt` defaults to `0`; retries must increment `attempt`. A terminal event without a matching start, nested start for the same `(step, attempt)`, or unclosed start is invalid. Semantic details go in `outcome` or `reason`, never by inventing event names.

`/bs resume` rebuilds state from `step_events.jsonl` with strict pairing, not last-write-wins. If a step attempt is started without terminal event, runtime requires a human decision: `--redo`, `--mark-completed`, or `--escalate`. It must not infer success for side-effecting steps.

## 6. Required artifacts

Every cycle produces `outcome.md`, `shape_critic.yaml`, `preflight_initial.yaml`, `step_events.jsonl`, `grade_round_0.md`, `grade_result.md`, `auto_merge_gate.yaml`, `task_knowledge.yaml`, `workflow_reflection.yaml`, and evidence files: `raw_vendor_output.jsonl`, `rpc_requests.jsonl`, `vendor_stderr.txt`, `driver_events.jsonl`, `git_diff.patch`, `git_status.txt`.

Fix-round artifacts are conditional on fix rounds. Medium/high risk grade raw output goes under `evidence/grade/`.

## 7. Step 10 atomic close

Step 10 reads the cycle data, verifies the backlog task is still `in_progress`, prepares new ledger and backlog content in memory, writes both, stages both, and commits once:

`ledger+backlog: close <cycle> <ID> <title>`

If the commit fails, runtime reverts both files and escalates.

## 8. Commands

- `/bs`: run next pending unblocked task.
- `/bs init`: write `.bootstrap.yaml`, `.bootstrap/backlog.yaml`, and `.bootstrap/contract.sha256`; no markdown, no commit.
- `/bs status`: read-only status summary.
- `/bs resume`: event-state recovery.
- `/bs park <id> --reason "..."` and `/bs unpark <id>`: status-only main commits.
- `/bs doctor`: read-only health diagnosis.
- `/bs refresh-contract`: explicit contract update and hash writeback.

## 9. Driver robustness

The Codex app-server driver emits a heartbeat every 30 seconds while waiting for turn completion. If an app-server final-answer/idle signal arrives but `turn/completed` is missing or raced, the driver arms a 5-second inferred-completion timer, records `inferred_completion: true` in `driver_events.jsonl`, and treats that turn as completed unless an explicit terminal event arrives first.

## 10. Non-goals

No parallel cycles, enum extension, severity override, council-member override, multi-backlog, markdown-embedded backlog compatibility, automatic v1.2 ledger migration, `/bs gc`, or repository-specific prompt override in v1.3.
