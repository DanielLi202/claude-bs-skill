# Bootstrap Development Workflow Contract v1.3.6

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

Contract verification is three-way: `.bootstrap.yaml.contract.source_sha256`, `.bootstrap/contract.sha256`, and the local skill `contract.md` sha256 must match. Semver compatibility uses `contract.compatible_range`; floating latest is forbidden. If the contract contains a Runtime manifest, every listed runtime or command-surface file must match its locked sha256 during binding validation.

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
4. Run the startup (pre-start) gate via `${runtime}/preflight.sh` before the start commit or cycle directory. Non-zero exit escalates with no cycle artifacts.
5. Run Step 1 self-containment gate: required fields, status precondition, closed enums, dependency closure, `spec_refs` length, and file/dir existence for `spec_refs` after stripping informational anchors.
6. On main with clean working tree, change the task to `in_progress`, commit `bs: start <ID> <title>`, push `origin main`, and verify remote main equals local HEAD.
7. Create the cycle directory and worktree branch from that pushed commit; write `cycle.yaml`, binding snapshot, the captured startup gate output as `preflight_initial.yaml`, and strict `step_events.jsonl` started/terminal attempt pairs.
8. Run the 11-step cycle: ingest, identify, shape, conduct, grade, fix loop, PR, auto-merge, escalation handling, reflection, ledger close.
9. Step 10 closes with one atomic commit on main containing both ledger append and backlog writeback.

## 5. Step events and resume

`step_events.jsonl` is append-only. Every step attempt emits exactly `started` and then either `completed` or `failed`. The state key is `(step, attempt)` where `attempt` defaults to `0`; retries must increment `attempt`. A terminal event without a matching start, nested start for the same `(step, attempt)`, or unclosed start is invalid. Semantic details go in `outcome` or `reason`, never by inventing event names.

`/bs resume` rebuilds state from `step_events.jsonl` with strict pairing, not last-write-wins. If a step attempt is started without terminal event, runtime requires a human decision: `--redo`, `--mark-completed`, or `--escalate`. It must not infer success for side-effecting steps.

## 6. Required artifacts

Every cycle produces `outcome.md`, `shape_critic.yaml`, `preflight_initial.yaml`, `step_events.jsonl`, `grade_round_0.md`, `grade_result.md`, `auto_merge_gate.yaml`, `task_knowledge.yaml`, `workflow_reflection.yaml`, and evidence files: `raw_vendor_output.jsonl`, `rpc_requests.jsonl`, `vendor_stderr.txt`, `driver_events.jsonl`, `git_diff.patch`, `git_status.txt`.

Each `grade_round_<N>.md` MUST contain parseable fenced YAML blocks for both:

```yaml
grade_summary:
  p0_count: 0
  p1_count: 1
  p2_count: 0
```

```yaml
acceptance_status:
  - id: B011-FORCED-RESHAPE-CONTROL
    status: fail
    severity: P1
```

`grade_summary.p0_count + p1_count` is the blocking-failure metric for fix-loop stop conditions. Missing or malformed `grade_summary` / `acceptance_status` is fail-fast because the loop cannot evaluate itself blind.

Fix-round artifacts are conditional on fix rounds: `outcome.v<g>.md` archives for every re-shape, a `bs-fix-round: R` marker in live `outcome.md`, and per-round evidence under `evidence/conduct_round_<N>/` including round 0. Medium/high risk grade raw output goes under `evidence/grade/`.

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

The Codex app-server driver sends `/goal @<outcome.md>` through `codex app-server --listen stdio://`; no prompt wrapper and no `codex exec --json` fallback exist. Fix rounds (`--fix-round R`, R >= 1) re-read the cycle's `outcome.md` after `reshape_fix_round.py` has re-shaped it; the driver still sends exactly one `/goal @<outcome.md>`, never a second file or a prompt wrapper. Launch/handshake transient failures retry, then exit 3 on exhaustion. Deterministic launch failures exit 4 without retry. Turn failures after `turn/start` exit 2.

The driver emits a heartbeat every 30 seconds while waiting for turn completion. If an app-server final-answer/idle signal arrives but `turn/completed` is missing or raced, the driver arms a 5-second inferred-completion timer, records `inferred_completion: true` in `driver_events.jsonl`, and treats that turn as completed unless an explicit terminal event arrives first. Idle timeout is based only on stdout JSON-RPC activity; stderr sidecar noise does not keep a stuck turn alive.

## Conduct invariants (normative)

- A startup (pre-start) gate MUST run `${runtime}/preflight.sh` BEFORE the `bs: start` commit / cycle dir creation / step_0 ingest. Non-zero exit MUST escalate with no artifacts created (fail-fast on dependency failure). This gate is distinct from the cycle's step_0 ingest; preflight detail is recorded post-start in `preflight_initial.yaml`.
- Conduct (Step 3) and Fix (Step 5) MUST invoke `${runtime}/conduct.sh`. They MUST NOT invoke `codex_driver.py` / `codex_fix_driver.py` / `codex` directly, MUST NOT use `codex exec --json`, and MUST NOT substitute any other vendor binary path. Bootstrap is intentionally stricter than the product's DA-24 transport fallback because bootstrap exists partly to validate the app-server path.
- Goal mode is mandatory and file-referenced: the driver sends `/goal @<outcome.md>`. The agent MUST pass `--outcome-file`; it MUST NOT wrap a conduct prompt or inject any prompt during delegation.
- A grade failure (Step 4 P0+P1 > 0) is repaired by re-shaping the capsule via `${runtime}/reshape_fix_round.py`, never by prompt injection. For fix round R (R >= 1) the helper MUST archive the prior capsule to `outcome.v<R-1>.md`, fold structured findings from `grade_round_<R-1>.md` (failed acceptance IDs plus an optional length-bounded corrections list plus a reference to that grade file, not a verbatim paste), and emit a `bs-fix-round: R` marker.
- `${runtime}/conduct.sh --fix-round R` MUST refuse to launch unless `outcome.v<R-1>.md` and `grade_round_<R-1>.md` exist and `outcome.md` carries the `bs-fix-round: R` marker. The driver still sends exactly one `/goal @<outcome.md>`.
- The fix loop is bounded by `max_fix_rounds = 3`. The agent MUST escalate at Step 4 if P0+P1 > 0 after round 3, or if P0+P1 does not strictly decrease across rounds. Strict decrease is measured from `grade_summary.p0_count + p1_count`, not acceptance pass/fail. No unbounded looping.
- If `codex app-server` launch fails transiently, the driver retries up to `--launch-retries` then exits 3. On exhaustion (exit 3) or deterministic launch fatal (exit 4), the agent MUST escalate at Step 3 and MUST NOT try another transport.

## Runtime manifest (locked)

| file | sha256 |
|---|---|
| runtime/preflight.sh | 9b3904e33a7f2c3fef56bceb614f62bf6987c994ec630d3f4444f41a73aabfd5 |
| runtime/codex_driver.py | f2afcad77177d58e122f24a46491eb4294dc1d5967182bed98eba383aabe3ab0 |
| runtime/codex_fix_driver.py | 0ba1be44f6ddf4f8ff8d40a8a661bd317c85752c5e9597f6c2ac13afb9d1ae4a |
| runtime/reshape_fix_round.py | ce6caf0114102fc706798963f6756e75c90b2d7d12caa854eca6352e30f9a73a |
| runtime/conduct.sh | 02a10c8e21ccca4bf5d5b6262027b5f44a84d596733fcb683b70edb631cc6e3c |
| commands/bs.md | be9736ec041da48c2170f95514624a831cd34827883c6b311c5964dcc4158b61 |

The manifest locks runtime and slash-command surface by making file hashes part of the contract hash. Any listed file change requires updating this table and refreshing adopter bindings.

## 10. Non-goals

No parallel cycles, enum extension, severity override, council-member override, multi-backlog, markdown-embedded backlog compatibility, automatic v1.2 ledger migration, `/bs gc`, repository-specific prompt override, second `/goal` file, raw grade markdown paste into the capsule, or unbounded fix loop in v1.3.6.


## 11. Changelog

- v1.3.6: multi-round fix loop hardening. `reshape_fix_round.py` scopes resume/idempotency state to the current fix round so prior `bs-fix-round` markers do not block strict-decrease R >= 2 re-shapes; `conduct.sh --fix-round R` anchors the guard on the full HTML marker with matching archive and grade; tests cover the R=2 strict-decrease happy path and prose-substring false positive.
- v1.3.5: mechanically-enforced fix-round capsule re-shape. `reshape_fix_round.py` archives `outcome.v<R-1>.md`, folds structured grade findings (failed acceptance IDs plus bounded corrections, not pasted raw markdown) and a `bs-fix-round` marker; `conduct.sh --fix-round R` guards on archive + grade + marker; the driver still sends one `/goal @outcome.md`; per-round evidence dirs and `max_fix_rounds=3` with strict P0+P1 decrease are locked.
- v1.3.4: code-enforced app-server-only Conduct path, `/goal @outcome.md`, startup preflight dependency gate, transient launch retry-then-stop, mandatory `conduct.sh`, stdout-only idle timeout, test-only fake Codex injection, and runtime manifest hash.
