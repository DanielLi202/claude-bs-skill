# Bootstrap Development Workflow Contract v1.3.8

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
- `backlog`, `ledger`, `cycle_dir_root`, `red_lines`, `verify_command` (`verify_command` is deprecated final smoke compatibility; per-round Grade uses `grade_verify.py`)
- optional `verify.grade.<task_type>` command lists and `verify.env.clear` environment sanitizers; `type: code` tasks require `verify.grade.code` before Grade
- optional `preflight.require_council` (default false), `preflight.council_quorum_min` (default 2), and `preflight.council_required_when` policy
- optional `workflow_dir` override; null means use skill bundled runtime
- optional `register_prefixes` and `agent_prompts.*`

Contract verification is three-way: `.bootstrap.yaml.contract.source_sha256`, `.bootstrap/contract.sha256`, and the local skill `contract.md` sha256 must match. Semver compatibility uses `contract.compatible_range`; floating latest is forbidden. If the contract contains a Runtime manifest, every listed runtime or command-surface file must match its locked sha256 during binding validation.

## 3. Backlog requirements

`.bootstrap/backlog.yaml` schema version 1 contains `tasks[]`. Each task has:

- `id`: `^[A-Z]+-\d{3}$`; `B-000` is reserved for retroactive completed history and is skipped by next-task selection.
- `title`, `type`, `risk_level`, `status`, `blocked_by`, `spec_refs`
- optional `estimated_loc`, `risk_surfaces`, `acceptance_hints`, `non_goals_hints`
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

The Conduct driver (path A `codex app-server`) is designed to handle TC-B tasks in a single turn, including long-running turns. Silence or elapsed wall-clock is not a failure by default; it is supervisor telemetry while the app-server process remains alive. Failures come from transport failure, semantic failure after final answer, verify failure, bounded fix-loop failure, or an explicit binding policy that opts into hard wall-clock termination.

### Agent autonomy bounds (normative)

The `/bs` agent **MUST NOT** pause or request user confirmation based on:

- Task LOC magnitude (absolute or relative to prior cycles)
- Subjective "task feels large / risky / unfamiliar" heuristics
- Comparison against prior cycle wall-clock or fix-loop counts
- Anything not enumerated below as a schema-defined gate

The agent **MUST** pause / escalate only on:

- Step 1 self-containment gate failure (missing required field, broken `spec_refs` path, unsatisfied `blocked_by`)
- Step 3 driver crash / transport failure / semantic failure after final answer / launch exhaustion
- Step 4 missing required machine verify evidence, or P0+P1 > 0 after fix loop max iterations or non-strictly-decreasing
- Step 7 auto-merge gate fails (conflict / hook fail / pending review)
- Explicit `/bs park`, `/bs resume --escalate`, user-initiated abort
- Backlog/binding schema validation failure at startup
- required `verify.grade.<task_type>` command failure or final compatibility `verify_command` non-zero exit

If the agent encounters a situation it considers concerning but not covered by the above gates, it **MUST proceed and record the concern as a `workflow_reflection.yaml` entry** in Step 9, rather than pause to ask. If experience shows a real new gate is needed, it gets added to the contract via a patch cycle (like this v1.3.1).

## 4. Main `/bs` flow

1. Find repo root, validate `.bootstrap.yaml`, contract hash, and backlog schema.
2. Reject if any task is already `in_progress`; use `/bs resume` instead.
3. Select the next unblocked pending task.
4. Run the startup (pre-start) gate via `${runtime}/preflight.sh` before the start commit or cycle directory. Non-zero exit escalates with no cycle artifacts.
5. Run Step 1 self-containment gate: required fields, status precondition, closed enums, dependency closure, `spec_refs` length, and file/dir existence for `spec_refs` after stripping informational anchors.
6. On main with clean working tree, change the task to `in_progress`, commit `bs: start <ID> <title>`, push `origin main`, and verify remote main equals local HEAD.
7. Create the cycle directory and worktree branch from that pushed commit; write `cycle.yaml`, binding snapshot, the captured startup gate output as `preflight_initial.yaml`, and strict `step_events.jsonl` started/terminal attempt pairs.
8. Run the 11-step cycle: ingest, identify, shape, conduct, per-round machine verify, grade, fix loop, PR, auto-merge, escalation handling, reflection, ledger close.
9. Step 10 closes with one atomic commit on main containing both ledger append and backlog writeback.

## 5. Step events and resume

`step_events.jsonl` is append-only. Every step attempt emits exactly `started` and then either `completed` or `failed`. The state key is `(step, attempt)` where `attempt` defaults to `0`; retries must increment `attempt`. A terminal event without a matching start, nested start for the same `(step, attempt)`, or unclosed start is invalid. Semantic details go in `outcome`, `reason`, or the controlled `reason_code` vocabulary, never by inventing event names.

Controlled `reason_code` values are: `semantic_blocked_final_answer`, `semantic_refusal_final_answer`, `semantic_required_effect_missing`, `transport_eof_before_completion`, `launch_transient`, `launch_fatal`, `verify_command_failed`, `verify_evidence_missing`, `wall_clock_policy_exceeded`. Terminal events may include machine-readable `driver_exit`, `conduct_result`, `workspace_delta_files`, `evidence_delta_files`, and `write_actions`. Do not add a separate `environment_blocked` step; represent retries with `(step, attempt)`.

`/bs resume` rebuilds state from `step_events.jsonl` with strict pairing, not last-write-wins. If a step attempt is started without terminal event, runtime requires a human decision: `--redo`, `--mark-completed`, or `--escalate`. It must not infer success for side-effecting steps.

## 6. Required artifacts

Every cycle produces `outcome.md`, `shape_critic.yaml`, `preflight_initial.yaml`, `step_events.jsonl`, `grade_round_0.md`, `grade_result.md`, `auto_merge_gate.yaml`, `task_knowledge.yaml`, `workflow_reflection.yaml`, and evidence files: `raw_vendor_output.jsonl`, `rpc_requests.jsonl`, `vendor_stderr.txt`, `driver_events.jsonl`, `git_diff.patch`, `git_status.txt`. Every Grade round also produces and cites `evidence/grade_verify_round_<N>.yaml` before `grade_round_<N>.md` is authored; the file records pass/fail/not_required plus per-command logs when commands run. Medium/high code Grade rounds also produce `evidence/grade_lint_round_<N>.json`.

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

For `tasks[*].type == code` and `risk_level in {medium, high}`, Shape MUST include parseable fenced YAML blocks named `risk_surface` and `adversarial_acceptance` in `outcome.md`. High-risk surfaces are `process`, `background_process`, `runtime_files`, `identity_sentinel`, `network_probe`, `auth_or_secret`, `file_modes`, `concurrency_or_locking`, `destructive_operation`, and `external_subprocess`. Every present high-risk surface must have at least one adversarial acceptance row with an evidence-oriented `verification_hint`; a surface may be marked not applicable only with a one-line reason.

For the same medium/high code tasks, every `grade_round_<N>.md` MUST also contain parseable fenced YAML blocks named `adversarial_checks`, `trust_surface_inventory`, and `deferred_claims`. Missing or malformed medium/high code adversarial blocks are blocking P1. Any `adversarial_checks[*].status in {fail, unverified}` with `severity_if_fail in {P0, P1}` contributes to the blocking count. `trust_surface_inventory.unverified_items` with P0/P1 severity is blocking. A `deferred_claims` row with `current_scope_implementable: true` must cite `evidence_ref` or an acceptance/waiver reference; a P0/P1 waiver of current-scope foundation safety must cite a tracked maintainer/user waiver artifact. Grade cannot downgrade such a waiver by assertion alone.

`${runtime}/grade_lint.py` is the deterministic schema/accounting gate. Step 4 MUST run it after each Grade round and before fix-loop decision for medium/high code tasks, writing `evidence/grade_lint_round_<N>.json`. Step 7 auto-merge MUST require the latest applicable grade-lint result to pass. Low-risk docs/spec cycles keep the lightweight `grade_summary` + `acceptance_status` contract.

Backlog authors SHOULD include `risk_surfaces`, happy-path `acceptance_hints`, adversarial `acceptance_hints`, and `non_goals_hints` for medium/high code tasks. Shape remains responsible for deriving missing risk surfaces from `spec_refs`; repository-specific details stay in backlog/cycle artifacts, not in this contract.

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

The Codex app-server driver sends `/goal @<outcome.md>` through `codex app-server --listen stdio://`; no prompt wrapper and no `codex exec --json` fallback exist. Fix rounds (`--fix-round R`, R >= 1) re-read the cycle's re-shaped `outcome.md` after `reshape_fix_round.py` has re-shaped it; the driver still sends exactly one `/goal @<outcome.md>`, never a second file or a prompt wrapper. Launch/handshake transient failures retry, then exit 3 on exhaustion. Deterministic launch failures exit 4 without retry. Turn failures after `turn/start` exit 2. Transport completion is not work completion: every explicit or inferred completion path must pass semantic validation before exit 0; semantic failure exits 6.

The driver emits a heartbeat every 30 seconds while waiting for turn completion. If an app-server final-answer/idle signal arrives but `turn/completed` is missing or raced, the driver arms a 5-second inferred-completion timer, records `inferred_completion: true` in `driver_events.jsonl`, and treats that turn as completed unless an explicit terminal event arrives first. The legacy idle-kill flag is disabled by default; if an operator explicitly enables it, it is based only on stdout JSON-RPC activity and stderr sidecar noise does not keep a stuck turn alive.

## Conduct invariants (normative)

- A startup (pre-start) gate MUST run `${runtime}/preflight.sh` BEFORE the `bs: start` commit / cycle dir creation / step_0 ingest. Non-zero exit MUST escalate with no artifacts created (fail-fast on dependency failure). Codex and gh remain hard dependencies. External council quorum is warning-only by default and hard-required only when binding policy explicitly requires it. This gate is distinct from the cycle's step_0 ingest; preflight detail is recorded post-start in `preflight_initial.yaml`.
- Conduct (Step 3) and Fix (Step 5) MUST invoke `${runtime}/conduct.sh`. They MUST NOT invoke `codex_driver.py` / `codex_fix_driver.py` / `codex` directly, MUST NOT use `codex exec --json`, and MUST NOT substitute any other vendor binary path. Bootstrap is intentionally stricter than the product's DA-24 transport fallback because bootstrap exists partly to validate the app-server path.
- Goal mode is mandatory and file-referenced: the driver sends exactly `/goal @<outcome.md>`. The agent MUST pass `--outcome-file`; it MUST NOT wrap a conduct prompt, inject any prompt during delegation, silently fall back to another transport, or use `codex exec`.
- Semantic completion is mandatory: final-answer/inferred/explicit transport completion only exits 0 after `post_turn_validate()` confirms no hard refusal and the configured required effect is present. Hard refusal markers such as `Blocked: true` fail even when `expected_effect.kind=none`; missing required workspace/evidence delta exits 6 as `semantic_failed`.
- Delta checks compare turn-start snapshots to turn-end snapshots for workspace/evidence roots. A pre-existing dirty tree cannot satisfy required effect.
- Silence is not failure by default. The driver MUST NOT kill a live agent due to stdout idle time or elapsed wall-clock unless binding/runtime policy explicitly opts into `fail`/`terminate`; silence emits supervisor telemetry such as `turn_silent_soft_limit`, `turn_progress_stale`, `turn_long_running`, and `turn_monitor_snapshot`. Launch/handshake timeout, transport EOF, malformed observation, and explicit semantic failure remain hard failures.
- Before each Grade round, the agent MUST run `${runtime}/grade_verify.py` and produce `evidence/grade_verify_round_<N>.yaml`. The helper selects `verify.grade.<type>`, maps legacy `verify_command` to docs compatibility, fails for code tasks without `verify.grade.code`, or records explicit `not_required` only when the binding/task declares verification is not required. `grade_round_<N>.md` MUST cite that evidence. Legacy `verify_command` is final-smoke compatibility input and cannot substitute for per-round Grade verify helper invocation.
- A grade failure (Step 4 P0+P1 > 0) is repaired by re-shaping the capsule via `${runtime}/reshape_fix_round.py`, never by prompt injection. For fix round R (R >= 1) the helper MUST archive the prior capsule to `outcome.v<R-1>.md`, fold structured findings from `grade_round_<R-1>.md` (failed acceptance IDs plus an optional length-bounded corrections list plus a reference to that grade file, not a verbatim paste), and emit a `bs-fix-round: R` marker.
- `${runtime}/conduct.sh --fix-round R` MUST refuse to launch unless `outcome.v<R-1>.md` and `grade_round_<R-1>.md` exist and `outcome.md` carries the `bs-fix-round: R` marker. The driver still sends exactly one `/goal @<outcome.md>`; it must not pass a second file or inject grade findings.
- Step 4 MUST run `${runtime}/grade_lint.py --task-type <type> --risk-level <risk> --grade-file grade_round_<N>.md --outcome-file outcome.md --evidence-file evidence/grade_lint_round_<N>.json` before computing fix-loop decisions when `<type> == code` and `<risk> in {medium, high}`. Lint failure is a blocking Grade failure and must be reflected in `grade_summary.p0_count + p1_count`.
- The fix loop is bounded by `max_fix_rounds = 3`. The agent MUST escalate at Step 4 if required machine verify evidence is absent, if P0+P1 > 0 after round 3, or if P0+P1 does not strictly decrease across rounds. Strict decrease is measured from `grade_summary.p0_count + p1_count`, not acceptance pass/fail. No unbounded looping.
- If `codex app-server` launch fails transiently, the driver retries up to `--launch-retries` then exits 3. On exhaustion (exit 3), deterministic launch fatal (exit 4), or semantic failure (exit 6), the agent MUST record the Step 3 terminal event with machine-readable fields and MUST NOT try another transport.

## Runtime manifest (locked)

| file | sha256 |
|---|---|
| runtime/preflight.sh | 539fbb89d7ebf3b4ab18c89d779cd19f12cb1cfc8be1d9040e3cd4009dc70d58 |
| runtime/codex_driver.py | 215b7e0817b35387408bb219dc51eb4f5b6f0d982f8943c916447dabdb011db8 |
| runtime/codex_fix_driver.py | 0ba1be44f6ddf4f8ff8d40a8a661bd317c85752c5e9597f6c2ac13afb9d1ae4a |
| runtime/reshape_fix_round.py | ce6caf0114102fc706798963f6756e75c90b2d7d12caa854eca6352e30f9a73a |
| runtime/conduct.sh | 7f2f9530c20b1e06d12ddc5bb9b1e94047b542647ca3b2f85f3d6643df5b5e53 |
| runtime/grade_lint.py | 5240666933aed85b6182b4ac15cb545f76dff6a70c5cc8c494ccc1f4d4371e5f |
| runtime/grade_verify.py | cd7baca6f0102d8920408bfd03d18711f76ad003d353cded54c74935c223407f |
| commands/bs.md | 49bfc09512aeff272c93afa783651ae212be5a51ec32eb1761ebff919a69a02d |

The manifest locks runtime and slash-command surface by making file hashes part of the contract hash. Any listed file change requires updating this table and refreshing adopter bindings.

## 10. Non-goals

No parallel cycles, enum extension, severity override, council-member override, multi-backlog, markdown-embedded backlog compatibility, automatic v1.2 ledger migration, `/bs gc`, repository-specific prompt override, second `/goal` file, raw grade markdown paste into the capsule, P0.2 `/goal` skill-surface isolation/interception detection, universal heavy adversarial process for low-risk docs/spec tasks, or unbounded fix loop in v1.3.8.


## 11. Changelog

- v1.3.8: unattended real-code workflow hardening after cycle-009. Adds semantic completion validation (exit 6 for refusal/missing required effect), non-interrupting long-running supervisor defaults, per-round typed Grade verify evidence via `grade_verify.py`, warning-only council quorum by default, controlled reason codes, terminal driver outcome fields, and buffered app-server notification handling so immediate final-answer/turn-completed events after `turn/start` are not lost. P0.2 `/goal` skill interception is explicitly split to a separate issue.
- v1.3.7: TC-B adversarial acceptance and Grade lint gate. Medium/high code Shape outputs `risk_surface` + `adversarial_acceptance`; Grade outputs `adversarial_checks`, `trust_surface_inventory`, and `deferred_claims`; `runtime/grade_lint.py` deterministically blocks malformed/missing adversarial blocks, P0/P1 fail/unverified checks, P0/P1 unverified trust items, and untracked current-scope safety waivers. `/bs` runs grade lint before fix-loop decisions and auto-merge for applicable tasks. Low-risk docs/spec cycles stay lightweight.
- v1.3.6: multi-round fix loop hardening. `reshape_fix_round.py` scopes resume/idempotency state to the current fix round so prior `bs-fix-round` markers do not block strict-decrease R >= 2 re-shapes; `conduct.sh --fix-round R` anchors the guard on the full HTML marker with matching archive and grade; tests cover the R=2 strict-decrease happy path and prose-substring false positive.
- v1.3.5: mechanically-enforced fix-round capsule re-shape. `reshape_fix_round.py` archives `outcome.v<R-1>.md`, folds structured grade findings (failed acceptance IDs plus bounded corrections, not pasted raw markdown) and a `bs-fix-round` marker; `conduct.sh --fix-round R` guards on archive + grade + marker; the driver still sends one `/goal @outcome.md`; per-round evidence dirs and `max_fix_rounds=3` with strict P0+P1 decrease are locked.
- v1.3.4: code-enforced app-server-only Conduct path, `/goal @outcome.md`, startup preflight dependency gate, transient launch retry-then-stop, mandatory `conduct.sh`, stdout-only idle timeout, test-only fake Codex injection, and runtime manifest hash.
