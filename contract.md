# Bootstrap Development Workflow Contract v1.4.11

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
- optional `conduct.mcp_policy` (`clean`, `allowlist`, or `full`; default `clean`) and `conduct.mcp_allowlist` (list of existing MCP server names allowed only when policy is `allowlist`)
- optional `status_marker` (v1.4.6): `status_marker.file` (the doc holding the pointer), `status_marker.next_task_marker` (the HTML-comment token, e.g. `§1-next-bs-task`, rewritten as `<!-- <token>: B-NNN -->`), optional `status_marker.next_task_line` (`start`/`end` sentinel strings + a `template` rendered from `{id}`/`{title}`), and optional `status_marker.post_sync_command` (shell run in repo root after a change, e.g. a CLAUDE.md re-sync). When present, Step 10 advances this pointer in the atomic close commit; when absent the close stages only ledger + backlog.

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

The Conduct driver (path A `codex app-server`) is designed to handle TC-B tasks in a single turn, including long-running turns. Silence or elapsed wall-clock is not a failure by default; lack of a first work item emits `turn_no_work_items_stale` telemetry by default while the app-server process remains alive. Failures come from transport failure, semantic failure after final answer, verify failure, bounded fix-loop failure, or an explicit binding policy that opts into hard wall-clock termination.

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
7. Create the cycle directory and worktree branch from that pushed commit; write `cycle.yaml`, binding snapshot, the captured startup gate output as `preflight_initial.yaml`, and strict `step_events.jsonl` started/terminal attempt pairs using the runtime event helpers so append-time `recorded_at` is machine-emitted.
8. Run the 11-step cycle: ingest, identify, shape, conduct, per-round machine verify, grade, fix loop, PR, auto-merge, escalation handling, reflection, ledger close.
9. Step 10 closes with one atomic commit on main containing both ledger append and backlog writeback.

## 5. Step events and resume

`step_events.jsonl` is append-only. Every normal step attempt emits exactly `started` and then either `completed` or `failed`. New writes SHOULD use the runtime event helpers (`append_started`, `append_completed`, `append_failed`) rather than hand-authored JSON so append-time `recorded_at` is machine-emitted. The helpers accept either `Path` or `str` paths; any helper exception is blocking evidence, not a cosmetic warning. The state key is `(step, attempt)` where `attempt` defaults to `0`; retries must increment `attempt`. A nested start for the same `(step, attempt)` or unclosed start is invalid. Semantic details go in `outcome`, `reason`, or the controlled `reason_code` vocabulary, never by inventing event names.

If a terminal event was durably appended without a preceding `started` because the helper failed, the only append-only repair is a later `repair` event with `repair_kind: missing_started`, `target_step`, `target_attempt`, `target_line`, `target_event_hash` (sha256 of the exact target JSONL line), `reason`, and optional `operator`. Validators process that repair after reading the full stream. Editing or inserting historical lines is not append-only and requires escalation outside the normal close path.

Every newly-written step event uses two canonical ISO-8601 UTC fields: `recorded_at` (the append time, monotonic non-decreasing across the log) and `occurred_at` (when the step actually happened; may be earlier for honest backfill and is not required to be monotonic). Canonical format is `YYYY-MM-DDTHH:MM:SS[.fraction]Z`. Readers and validators keep legacy `ts` fallback only when `recorded_at` is absent.

Controlled `reason_code` values are: `semantic_blocked_final_answer`, `semantic_refusal_final_answer`, `semantic_required_effect_missing`, `transport_eof_before_completion`, `launch_transient`, `launch_fatal`, `verify_command_failed`, `verify_evidence_missing`, `wall_clock_policy_exceeded`. Terminal events may include machine-readable `driver_exit`, `conduct_result`, `workspace_delta_files`, `evidence_delta_files`, `repo_delta_files`, `filesystem_delta_files`, `workspace_delta_count`, `write_actions`, and `file_change_events`. File-list fields must be lists; count fields must be non-negative integers. `file_change_events` is an event counter for `fileChange` notifications; `workspace_delta_files` remains the authoritative effect signal. Non-zero attempts may include `retry_kind` (`transport_retry`, `semantic_fix_round`, `launch_retry`) plus `changed`. Do not add a separate `environment_blocked` step; represent retries with `(step, attempt)`. `${runtime}/validate_events.py` enforces timestamp validity, append-only pairing/repair semantics, and the same event metadata schema as `lib.events` before close.

`/bs resume` rebuilds state from `step_events.jsonl` with strict pairing, not last-write-wins. If a step attempt is started without terminal event, runtime requires a human decision: `--redo`, `--mark-completed`, or `--escalate`. It must not infer success for side-effecting steps.

## 6. Required artifacts

Every cycle produces `outcome.md`, `shape_critic.yaml`, `preflight_initial.yaml`, `step_events.jsonl`, `grade_round_0.md`, `grade_result.md`, `auto_merge_gate.yaml`, `task_knowledge.yaml`, `workflow_reflection.yaml`, and evidence files: `git_diff.patch`, `git_status.txt`. Every Conduct round, including round 0, produces round-scoped evidence under `evidence/conduct_round_<N>/`: `raw_vendor_output.jsonl`, `rpc_requests.jsonl`, `vendor_stderr.txt`, `driver_events.jsonl`, and `codex_env.json`. Every Grade round also produces and cites `evidence/grade_verify_round_<N>.yaml` before `grade_round_<N>.md` is authored; the file records pass/fail/not_required plus per-command logs when commands run. Code Grade rounds also produce `evidence/grade_lint_round_<N>.json`; low-risk code gets a baseline spec/security/negative-test gate, and medium/high code additionally gets the full adversarial gate. If an interrupted Conduct delta is accepted, the cycle also produces `recovery_decision.yaml`.

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

For every `tasks[*].type == code` Grade, `grade_round_<N>.md` MUST also contain parseable fenced YAML blocks named `spec_compliance_matrix`, `negative_regression_tests`, `secret_leakage_audit`, and `dependency_spec_review`. `spec_compliance_matrix` maps every shaped `outcome.md` acceptance ID to at least one `spec_ref`/`spec_refs` plus `evidence_ref`; fail/unverified P0/P1 rows are blocking. `negative_regression_tests` must cover every P0/P1 shaped acceptance with a concrete negative or malformed-input/security-regression scenario and evidence; `not_applicable` for a P0/P1 acceptance requires `scope_basis_ref` or a tracked waiver. For P0/P1 safety properties, the negative evidence must cover the property facets, not only example inputs in `verification_hint`: path/root-containment claims require symlink or canonical-root-containment coverage in addition to string traversal, and raw HTTP request-target/path-segment claims require delimiter plus control-character/CRLF or percent-encoding coverage. `secret_leakage_audit` records checked surfaces such as debug/display/error/log/serialization output and a cleartext-secret probe; fail/unverified is blocking P1. `dependency_spec_review` records locked/forbidden dependency, package, version, and crate checks when the outcome references dependencies or versions; fail/unverified P0/P1 rows are blocking. This lightweight code baseline follows the same principle as OWASP logging guidance: secrets such as access tokens, passwords, keys, and similar sensitive values must be removed, masked, sanitized, hashed, or encrypted before logs or user-facing errors. It exists because green build/test commands alone did not catch low-risk-code P1 issues in spec-mandated dependencies, secret-bearing Debug/error paths, missing negative tests, and property-facet escapes.

For `tasks[*].type == code` and `risk_level in {medium, high}`, Shape MUST include parseable fenced YAML blocks named `risk_surface` and `adversarial_acceptance` in `outcome.md`. High-risk surfaces are `process`, `background_process`, `runtime_files`, `identity_sentinel`, `network_probe`, `auth_or_secret`, `file_modes`, `concurrency_or_locking`, `destructive_operation`, `external_subprocess`, `string_boundary`, and `input_validation_or_schema`. Every present high-risk surface must have at least one adversarial acceptance row with an evidence-oriented `verification_hint`; a surface may be marked not applicable only with a one-line reason. P0/P1 adversarial acceptance hints define current-round validation obligations: they MUST NOT use optional/deferred/future/not-reachable wording to make a current validation optional. Boundary risks involving length caps (for example `<=N chars`), truncation, user text, JSON, malformed input, or non-ASCII handling MUST use either `string_boundary` or `input_validation_or_schema`.

For the same medium/high code tasks, every `grade_round_<N>.md` MUST also contain parseable fenced YAML blocks named `adversarial_checks`, `trust_surface_inventory`, and `deferred_claims`. Missing or malformed medium/high code adversarial blocks are blocking P1. Any `adversarial_checks[*].status in {fail, unverified}` with `severity_if_fail in {P0, P1}` contributes to the blocking count. `trust_surface_inventory.unverified_items` with P0/P1 severity is blocking. A `deferred_claims` row with `current_scope_implementable: true` must cite `evidence_ref` or an acceptance/waiver reference; a P0/P1 waiver of current-scope foundation safety must cite a tracked maintainer/user waiver artifact. `deferred_claims` MUST NOT defer a current P0/P1 adversarial acceptance by assertion: if a row references or mentions a current P0/P1 adversarial acceptance ID, it must cite a tracked maintainer/user waiver or a clear `scope_basis_ref`. Grade cannot downgrade such a waiver or scope deferral by assertion alone.

`adversarial_checks[*].evidence_kind` is required for risk-specific evidence classes where generic evidence would be ambiguous. `concurrency_or_locking` checks whose statement or hint mentions concurrent access, lost updates, same-revision races, one-2xx/409 split behavior, or If-Match semantics MUST use `evidence_kind: concurrency_test` or `evidence_kind: atomicity_proof`. Boundary/input checks MUST use a boundary evidence kind such as `non_ascii_boundary_test`, `malformed_input_test`, `length_boundary_test`, `json_boundary_test`, or `schema_validation_test`. No-panic/implicit-panic audits for medium/high code MUST use `evidence_kind: panic_audit` or `evidence_kind: implicit_panic_audit`; mere grep/regex search is not sufficient evidence for no-panic safety because it misses implicit panics, parse paths, and call-graph context.

`${runtime}/grade_lint.py` is the deterministic schema/accounting gate. It prefers `yaml.safe_load` for fenced YAML so valid YAML authoring behaves like normal tooling, while retaining legacy compatibility for older unquoted prose scalars; for code outcomes it also reads YAML front matter so front-matter `acceptance:` arrays are linted like fenced outcome blocks. Step 4 MUST run it after each Grade round and before fix-loop decision for every code task, writing `evidence/grade_lint_round_<N>.json`. For low-risk code it enforces the baseline blocks above, covering shaped `outcome.md` acceptance IDs when present and otherwise the Grade `acceptance_status` IDs; for medium/high code it additionally enforces adversarial `risk_surface` / `adversarial_acceptance` / `adversarial_checks` / `trust_surface_inventory` / `deferred_claims` rules. The gate also derives lightweight property obligations from P0/P1 acceptance text for path/root containment and raw request-target/path-segment boundaries, so example-only negative tests cannot clear broad safety claims. Step 7 auto-merge MUST require the latest applicable grade-lint result to pass. Low-risk docs/spec cycles keep the lightweight `grade_summary` + `acceptance_status` contract.

Backlog authors SHOULD include `risk_surfaces`, happy-path `acceptance_hints`, adversarial `acceptance_hints`, and `non_goals_hints` for medium/high code tasks. Shape remains responsible for deriving missing risk surfaces from `spec_refs`; repository-specific details stay in backlog/cycle artifacts, not in this contract.

Fix-round artifacts are conditional on fix rounds: `outcome.v<g>.md` archives for every re-shape, a `bs-fix-round: R` marker in live `outcome.md`, and per-round evidence under `evidence/conduct_round_<N>/` including round 0. Medium/high risk grade raw output goes under `evidence/grade/`.

## 7. Step 10 atomic close

If any Conduct attempt for the cycle failed or was interrupted and the run continued by accepting a non-empty workspace delta without a later successful Conduct attempt, Step 10 MUST first verify a structured `recovery_decision.yaml` exists. The artifact must include `cycle`, `failed_step`, `failed_attempt`, `failure_result`, `workspace_delta_files`, `options`, `selected`, `approver`, `decided_at`, `evidence_reviewed`, `waiver_scope`, and `required_followups`; `selected` must be one of `accept_interrupted_delta`, `retry_conduct`, or `park_or_escalate`. Closing a cycle with `accept_interrupted_delta` requires `evidence_reviewed` to cite the passing `grade_verify_round_<N>.yaml`, the latest applicable `grade_lint_round_<N>.json`, and the workspace delta. Prose-only maintainer approval is not replayable enough for atomic close.

Step 10 appends `step_10 started`, then runs the pre-close gate `python3 ${runtime}/validate_events.py <cycle-dir>/step_events.jsonl --allow-open-current step_10`. That flag tolerates exactly the current open `step_10` pair and nothing else. It then reads the cycle data, verifies the backlog task is still `in_progress`, prepares new ledger and backlog content in memory, writes both, and — if the binding declares `status_marker` — runs `python3 ${runtime}/sync_status_marker.py --binding-file <binding-file> --repo-root <repo>` after the backlog writeback so it reads the freshly-completed task and resolves the *next* selectable task, advancing the declared pointer (and any `post_sync_command` output). Bindings with dynamic status prose SHOULD also configure `status_marker.stale_id_guard` around that prose block; when enabled, close fails before file write if the previous marker ID remains in the guarded status prose after marker/line rewrites. It stages ledger + backlog plus any `status_marker`-touched files, and commits once:

`ledger+backlog: close <cycle> <ID> <title>`

When the binding has no `status_marker`, the close stages only ledger + backlog and is otherwise identical (backward compatible). After the close commit, Step 10 appends `step_10 completed` and runs the post-close full re-validation without `--allow-open-current`; that complete-log validation is the real close gate. If the commit or post-close validation fails, runtime reverts the close-commit files where possible and escalates.

## 8. Commands

- `/bs`: run next pending unblocked task.
- `/bs init`: write `.bootstrap.yaml`, `.bootstrap/backlog.yaml`, and `.bootstrap/contract.sha256`; no markdown, no commit.
- `/bs status`: read-only status summary.
- `/bs resume`: event-state recovery.
- `/bs park <id> --reason "..."` and `/bs unpark <id>`: status-only main commits.
- `/bs doctor`: read-only health diagnosis.
- `/bs refresh-contract`: explicit contract update and hash writeback.

## 9. Driver robustness

The Codex app-server driver uses a non-ephemeral `codex app-server --listen stdio://` thread and delegates via `thread/goal/set`, not text `/goal`. The goal objective starts with one `BS_GOAL_V1` compact JSON header carrying `run_id`, absolute `outcome.md` path, and the driver-computed sha256 of the frozen capsule. Fix rounds (`--fix-round R`, R >= 1) re-read the cycle's re-shaped `outcome.md`; the driver sets one goal and starts one task-content-free launcher turn containing only the path, sha, and required `BS_OUTCOME_READ` JSON read-evidence marker. Launch/handshake transient failures retry, then exit 3 on exhaustion. Deterministic launch failures exit 4 without retry. Turn failures after `turn/start` exit 2.

The driver emits a heartbeat every 30 seconds while waiting for turn completion. If an app-server final-answer/idle signal arrives but `turn/completed` is missing or raced, the driver arms a 5-second inferred-completion timer, records `inferred_completion: true` in `driver_events.jsonl`, and treats that turn as completed unless an explicit terminal event arrives first. The legacy idle-kill flag is disabled by default; if an operator explicitly enables it, it is based only on stdout JSON-RPC activity and stderr sidecar noise does not keep a stuck turn alive.

The driver spawns `codex app-server` in its own POSIX process group (`start_new_session`) and, on every exit path (success, turn failure, timeout/idle/no-work/terminal-candidate termination, still-active or terminal non-success goal, launch fatal after thread start, uncaught exception, SIGINT, SIGTERM), reaps the whole group — SIGTERM then SIGKILL after a grace — using the process-group id captured at spawn so an orphaned grandchild (e.g. a runaway vendor `find` across `$HOME`) is reaped even after the app-server leader has exited. The reaper never signals the driver's own process group. The goal objective additionally carries a generic operating rule that the vendor resolve dependencies only through the project package manager/registry and never run broad filesystem searches (no `find`/recursive scans across `$HOME`, the home directory, caches, or any tree outside the worktree); this prevents the cycle-015 self-hang trigger and contains no project-specific content.

## Conduct invariants (normative)

- A startup (pre-start) gate MUST run `${runtime}/preflight.sh` BEFORE the `bs: start` commit / cycle dir creation / step_0 ingest. Non-zero exit MUST escalate with no artifacts created (fail-fast on dependency failure). Codex and gh remain hard dependencies. External council quorum is warning-only by default and hard-required only when binding policy explicitly requires it. This gate is distinct from the cycle's step_0 ingest; preflight detail is recorded post-start in `preflight_initial.yaml`.
- Conduct (Step 3) and Fix (Step 5) MUST resolve `conduct.mcp_policy` / `conduct.mcp_allowlist` from the binding (default `clean`) and invoke `${runtime}/conduct.sh --worktree <worktree> --mcp-policy <resolved> [--mcp-allow <comma-list>]` explicitly. The `--worktree` path is the git worktree where product changes should land; cycle artifacts may still live elsewhere by absolute path. They MUST NOT rely on `conduct.sh`'s shell default when the binding declares `full` or `allowlist`. They MUST NOT invoke `codex_driver.py` / `codex_fix_driver.py` / `codex` directly, MUST NOT use `codex exec --json`, and MUST NOT substitute any other vendor binary path. Bootstrap is intentionally stricter than the product's DA-24 transport fallback because bootstrap exists partly to validate the app-server path.
- Goal mode is mandatory and RPC-backed: the driver MUST use `thread/goal/set` on an `ephemeral:false` thread, MUST NOT send text `/goal @<outcome.md>`, and MUST NOT silently fall back to inline prompt transport or `codex exec`. The agent MUST pass `--outcome-file`; the driver computes the capsule sha out-of-band and places it in the `BS_GOAL_V1` objective header.
- The launcher is task-content-free: it may contain only the absolute outcome path, the sha256, and the required compact JSON `BS_OUTCOME_READ` marker instruction. The marker is model-visible read evidence only; the driver-computed sha is the integrity anchor.
- Terminal goal status is the success oracle. `thread/goal/updated` notifications are observability; exit 0 requires turn liveness to reach explicit or inferred completion, final `thread/goal/get` normalized status `complete`, and a matching `BS_OUTCOME_READ` marker. `blocked`, `usage_limited`, `budget_limited`, `paused`, `unknown`, and still-`active` statuses are non-success and map to `conduct_result=semantic_failed`. Raw vendor statuses such as `usageLimited` and `budgetLimited` are preserved in evidence while branching uses snake_case canonical statuses.
- Silence is not failure by default. The driver MUST NOT kill a live agent due to stdout idle time, elapsed wall-clock, or missing first work item unless binding/runtime policy explicitly opts into `fail`/`terminate`; silence emits supervisor telemetry such as `turn_silent_soft_limit`, `turn_progress_stale`, `turn_long_running`, `turn_monitor_snapshot`, and `turn_no_work_items_stale`. Launch/handshake timeout, transport EOF, malformed observation, and explicit semantic failure remain hard failures.
- The driver MUST spawn `codex app-server` in its own POSIX process group and MUST reap the whole group (SIGTERM then SIGKILL after a grace) on every exit path, using a process-group id captured at spawn so an orphaned grandchild is reaped even after the leader exits. It MUST NOT signal its own process group. This makes a runaway vendor subprocess (the cycle-015 `find` across `$HOME`) recoverable rather than an orphan that outlives the turn.
- Post-answer/post-delta idle is a distinct, opt-in decision point. When `--terminal-candidate-idle-sec N` is set and a turn is silent for more than `N` seconds while a non-empty `workspace_delta` already exists, the driver emits one `turn_terminal_candidate` event (`reason_code=post_delta_idle`) carrying the delta and idle telemetry. With the default `--on-terminal-candidate observe` this is telemetry only and the turn keeps running (silence is not failure). With opt-in `--on-terminal-candidate terminate` the driver reaps the process group and exits 8, which `conduct.sh` maps to `conduct_result=interrupted_with_delta` for the verify-and-accept path. This targets only the post-delta deadlock; a genuinely-long active turn with no delta yet is never a candidate.
- Kill-resistant launch is recommended for long Conduct turns: the orchestrator SHOULD launch `${runtime}/conduct.sh` detached (`setsid`/`nohup`) or under `tmux`/a background job so the turn survives the caller's turn/session lifecycle. A near-complete 17-min turn was lost in cycle-015 to an external SIGTERM of the foreground launcher; durable launch avoids abandoning a gate-green delta.
- Interrupted-with-delta verify-and-accept. When a Conduct turn does not reach goal `complete` (exit 8 `interrupted_with_delta`, an external interruption that leaves no `conduct_result`, or any other non-success result) but the worktree carries a non-empty `workspace_delta`, the agent MUST run the per-round Grade verify (`${runtime}/grade_verify.py`, plus `${runtime}/grade_lint.py` for code) on the delta before discarding it or blindly re-running. If the full `verify.grade.<type>` gate passes, the agent MAY accept the delta as the Conduct deliverable and continue to Grade, and MUST record the acceptance as a `workflow_reflection.yaml` deviation citing the grade-verify evidence and the `workspace_delta`. If the gate fails, the agent re-launches Conduct (or reshapes) per the normal failure path. Acceptance is evidence-gated: it REQUIRES passing verify evidence plus the recorded `recovery_decision.yaml` plus workflow-reflection deviation and MUST NOT silently re-run or discard a complete, gate-green delta. cycle-015 is the motivating evidence.
- Before each Grade round, the agent MUST run `${runtime}/grade_verify.py` and produce `evidence/grade_verify_round_<N>.yaml`. The helper selects `verify.grade.<type>`, maps legacy `verify_command` to docs compatibility, fails for code tasks without `verify.grade.code`, or records explicit `not_required` only when the binding/task declares verification is not required. `grade_round_<N>.md` MUST cite that evidence. Legacy `verify_command` is final-smoke compatibility input and cannot substitute for per-round Grade verify helper invocation.
- A grade failure (Step 4 P0+P1 > 0) is repaired by re-shaping the capsule via `${runtime}/reshape_fix_round.py`, never by prompt injection. For fix round R (R >= 1) the helper MUST archive the prior capsule to `outcome.v<R-1>.md`, fold structured findings from `grade_round_<R-1>.md` (failed acceptance IDs plus an optional length-bounded corrections list plus a reference to that grade file, not a verbatim paste), and emit a `bs-fix-round: R` marker.
- `${runtime}/conduct.sh --fix-round R` MUST refuse to launch unless `outcome.v<R-1>.md` and `grade_round_<R-1>.md` exist and `outcome.md` carries the `bs-fix-round: R` marker. The driver then uses the same goal-RPC transport against the re-shaped `outcome.md`; it must not pass a second file or inject grade findings.
- Step 4 MUST run `${runtime}/grade_lint.py --task-type <type> --risk-level <risk> --grade-file grade_round_<N>.md --outcome-file outcome.md --evidence-file evidence/grade_lint_round_<N>.json` before computing fix-loop decisions when `<type> == code`. Lint failure is a blocking Grade failure and must be reflected in `grade_summary.p0_count + p1_count`.
- The fix loop is bounded by `max_fix_rounds = 3`. The agent MUST escalate at Step 4 if required machine verify evidence is absent, if P0+P1 > 0 after round 3, or if P0+P1 does not strictly decrease across rounds. Strict decrease is measured from `grade_summary.p0_count + p1_count`, not acceptance pass/fail. No unbounded looping.
- After a persistent thread is obtained, every exit path (success, turn failure, timeout/idle/no-work termination, still-active goal, terminal non-success goal, launch fatal after thread start, uncaught exception, SIGINT, SIGTERM) must best-effort `thread/goal/clear` then `thread/archive`, recording cleanup events. There is no `thread/delete` in Codex 0.136.0; switch to hard delete only if a future protocol exposes it. If `codex app-server` launch fails transiently, the driver retries up to `--launch-retries` then exits 3. On exhaustion (exit 3), deterministic launch fatal (exit 4), semantic failure (exit 6), or no-work termination (exit 7), the agent MUST record the Step 3 terminal event with machine-readable fields and MUST NOT try another transport except the conduct-internal one-time clean retry for non-clean MCP policies.

## Runtime manifest (locked)

| file | sha256 |
|---|---|
| runtime/preflight.sh | 4ea35e944cec2fcf9567f11100ac1e6cb0c04f13fd9db3d790bc21f94295d2ef |
| runtime/codex_driver.py | 39f9e865cc94f9f83f19783551869e2060dc31783936dd3a0b891fd0cc701c5d |
| runtime/codex_fix_driver.py | 0ba1be44f6ddf4f8ff8d40a8a661bd317c85752c5e9597f6c2ac13afb9d1ae4a |
| runtime/reshape_fix_round.py | ce6caf0114102fc706798963f6756e75c90b2d7d12caa854eca6352e30f9a73a |
| runtime/conduct.sh | c9a7dab3798a384d3929256457e9b05da7a4b413b980ec128286f81c5f4b726e |
| runtime/grade_lint.py | 32f29c3718a98edd28dbe4c3755052cb3f07ba99d905430231f87fe73f6b0b29 |
| runtime/grade_verify.py | cd7baca6f0102d8920408bfd03d18711f76ad003d353cded54c74935c223407f |
| runtime/sync_status_marker.py | 4e0371d55d855dd18b6fd403e5c57a27099de412d99349efcd469e2595a3555a |
| commands/bs.md | 0a8dd8525ac93ce097f67808bec9720200099b7b4377921480796974e396b8cc |
| runtime/validate_events.py | 65b29d5c8a8535c7306368435c2d6665d5ea0f6170689c36615f44d62a587682 |
| lib/events.py | c01d756672df1661bc444a55ac6f1c0905fac2ad1c8d85ebbd4f51f03b10ce46 |
| lib/binding.py | 5533753bcc94da082bfbc0fe7054973a7c3d3dfcac9142184dc8402cb44321c6 |

The manifest locks runtime, helper, and slash-command surfaces by making file hashes part of the contract hash. Any listed file change requires updating this table and refreshing adopter bindings.

## 10. Non-goals

No parallel cycles, enum extension, severity override, council-member override, multi-backlog, markdown-embedded backlog compatibility, automatic v1.2 ledger migration, `/bs gc`, repository-specific prompt override, text `/goal` conduct transport, second goal file, raw grade markdown paste into the capsule, universal heavy adversarial process for low-risk docs/spec tasks, or unbounded fix loop. The v1.4.7 post-delta idle terminate and interrupted-with-delta verify-and-accept paths are opt-in and evidence-gated respectively; they do not change the default "silence is not failure" success path or make idle silence a failure by default. The optional `status_marker` advance (v1.4.6+) is the only status-doc write Step 10 performs; it rewrites only the declared marker, optional `next_task_line`, and `post_sync_command` output, and is a no-op when unconfigured. The optional v1.4.9 `stale_id_guard` validates narrative prose but does not rewrite it.


## 11. Changelog

- v1.4.11: Cycle-018 F5 secret-shape Grade hardening. `grade_lint.py` now requires in-scope `secret_leakage_audit` cleartext probes to show bare token/key-value, JSON/quoted token/API-key, and `Authorization: Bearer` shapes for auth/secret/log/evidence surfaces, while preserving scoped `not_applicable` audits. Runtime manifest relocked; driver/preflight client versions plus `skill.yaml` bumped to 1.4.11. No Conduct success-oracle or goal-RPC transport change.
- v1.4.10: Property-obligation Grade hardening after cycle-017 escape analysis. `grade_lint.py` now reads code outcome YAML front matter as well as fenced YAML blocks, derives lightweight property obligations from P0/P1 acceptance text, and blocks example-only negative coverage for path/root containment (string traversal without symlink/canonical-root containment) and raw request-target/path-segment boundaries (generic request-target or malformed-request smoke without delimiter/control-character/CRLF/encoding coverage). Shape and Grade prompts now require property-facet evidence even for low-risk code when trust-boundary surfaces exist. Runtime manifest relocked; driver/preflight client versions plus `skill.yaml` bumped to 1.4.10. No Conduct success-oracle or goal-RPC transport change.
- v1.4.9: Cycle-016 review hardening. `lib.events` now accepts `str | Path`, exposes a first-class append-only `repair` event for missing-start orphan terminals, and shares event metadata schema with `validate_events.py`, which now rejects count/list/null ambiguity such as integer `workspace_delta_files` or null `file_change_events`. `grade_lint.py` prefers `yaml.safe_load` for valid fenced YAML, fixing colon-containing scalar-list ergonomics while retaining legacy compatibility. `status_marker.stale_id_guard` can fail close when old dynamic task IDs remain in guarded status prose. `/bs` close guidance now blocks helper failures, raw-smoke contradictions, and silent history insertion. Runtime/helper manifest relocked; driver/preflight client versions plus `skill.yaml` bumped to 1.4.9. No Conduct success-oracle or goal-RPC transport change.
- v1.4.8: Cycle-015 review hardening for Grade and recovery evidence. All code Grades now run `grade_lint.py`; low-risk code must include deterministic `spec_compliance_matrix`, `negative_regression_tests`, `secret_leakage_audit`, and `dependency_spec_review` blocks so green build/test commands cannot hide spec-mandated dependency gaps, secret-bearing Debug/error leaks, or missing negative tests. Interrupted-with-delta acceptance now requires a structured `recovery_decision.yaml` before Step 10 close, tying the maintainer decision to options, selected path, approver, timestamp, reviewed evidence, waiver scope, and required follow-ups. Runtime manifest relocked (`grade_lint.py`, `commands/bs.md`, `preflight.sh`, `codex_driver.py`); driver/preflight client versions plus `skill.yaml` bumped to 1.4.8. No Conduct success-oracle or goal-RPC transport change.
- v1.4.7: Conduct self-hang hardening after cycle-015 (a vendor `find` across `$HOME` deadlocked the round-0 turn; the complete, gate-green delta was nearly lost). The driver spawns `codex app-server` in its own POSIX process group and reaps the whole group (SIGTERM→SIGKILL after a grace) on every exit path via a spawn-time pgid, so an orphaned runaway grandchild is reaped even after the leader exits, and never signals the driver's own group. The goal objective now carries a generic registry-only / no-broad-filesystem-scan dependency rule, and `/bs` Shape makes it an explicit capsule non-goal. New opt-in `--terminal-candidate-idle-sec` / `--on-terminal-candidate` surfaces a post-answer/post-delta idle deadlock as a distinct `turn_terminal_candidate` decision point (observe-only by default; opt-in terminate reaps the group and exits 8 → `conduct_result=interrupted_with_delta`). A first-class interrupted-with-delta verify-and-accept path lets the orchestrator run `verify.grade.<type>` on a non-empty `workspace_delta` left by an interrupted turn and accept it with evidence plus a recorded `workflow_reflection` deviation, instead of discarding it or blindly re-running. Kill-resistant detached/`tmux` launch is recommended for long turns. Runtime manifest relocked (`codex_driver.py`, `conduct.sh`, `commands/bs.md`, `preflight.sh`); driver and preflight `clientInfo.version` plus `skill.yaml` bumped to 1.4.7. No goal-RPC transport-semantics change to the success path; the default remains "silence is not failure".
- v1.4.6: Optional Step-10 `status_marker` advance. A new opt-in binding block (`status_marker.file` + `next_task_marker`, optional `next_task_line` sentinels + `template`, optional `post_sync_command`) lets the atomic close commit advance a repo's "next /bs task" pointer from the freshly-written backlog via `runtime/sync_status_marker.py` (the in_progress task if a cycle is open, else the next pending-unblocked task). Eliminates the per-cycle manual marker refresh / drift-warning. Backward compatible: absent `status_marker` ⇒ close stages only ledger + backlog, unchanged. New hash-locked runtime helper; `lib/binding.py` validates the block; runtime manifest relocked; no transport-semantics change.
- v1.4.5: Adversarial-lint hardening over v1.4.4. Adds high-risk surfaces `string_boundary` and `input_validation_or_schema`, requires risk-specific `adversarial_checks[*].evidence_kind` (concurrency/atomicity, boundary, panic-audit classes) where generic evidence is ambiguous, and forbids deferring a current P0/P1 adversarial acceptance by assertion (must cite a tracked waiver or `scope_basis_ref`). Grade-lint (`runtime/grade_lint.py`) tightening; no transport-semantics change; runtime manifest relocked.
- v1.4.4: Process-evidence hardening after the first medium/code adopter cycle. Adds machine timestamp defaults and helper APIs for `step_events.jsonl`, first-class `conduct.sh --worktree` execution, `/bs init` guidance for required `verify.grade.<type>` setup, `/bs doctor` version-skew diagnostics, round-scoped Conduct evidence path clarification, deterministic auto-merge-gate authoring guidance, and release label/client-version alignment.
- v1.4.3: Fix-round marker guard hotfix over v1.4.2; contract-body-neutral in the v1.4.3 tag.
- v1.4.2: Conduct no-first-work-item telemetry/optional exit 7, Codex environment snapshots, default clean/allowlist/full MCP exposure policy with binding passthrough, validator canonical timestamp hardening plus `--allow-open-current`, `occurred_at`/`recorded_at` evidence split, `retry_kind` attempt metadata, hard rename to `file_change_events`, version skew fix, and manifest relock. Resilience/observability/evidence-honesty patch; no goal-RPC transport-semantics change.
- v1.4.1: step_events append-only validator (`runtime/validate_events.py` + Step 10 close-gate wiring) and fileChange edit accounting in `codex_driver.py` (new `file_change_events` field; `workspace_delta` remains authoritative success signal); manifest relocked. Tooling/observability patch; no transport-semantics change.
- v1.4.0: Codex goal-RPC transport migration. Preserves v1.3.8 Grade verify/lint hardening while migrating Conduct to non-ephemeral `thread/goal/set`, `BS_GOAL_V1` objective headers, driver-side outcome sha integrity, task-content-free launcher with `BS_OUTCOME_READ` evidence, final `thread/goal/get == complete` success oracle, status normalization, cleanup clear+archive, and a mandatory preflight goal-RPC probe.
- v1.3.8: unattended real-code workflow hardening after cycle-009. Adds semantic completion validation (exit 6 for refusal/missing required effect), non-interrupting long-running supervisor defaults, per-round typed Grade verify evidence via `grade_verify.py`, warning-only council quorum by default, controlled reason codes, terminal driver outcome fields, and buffered app-server notification handling so immediate final-answer/turn-completed events after `turn/start` are not lost. P0.2 `/goal` skill interception is explicitly split to a separate issue.
- v1.3.7: TC-B adversarial acceptance and Grade lint gate. Medium/high code Shape outputs `risk_surface` + `adversarial_acceptance`; Grade outputs `adversarial_checks`, `trust_surface_inventory`, and `deferred_claims`; `runtime/grade_lint.py` deterministically blocks malformed/missing adversarial blocks, P0/P1 fail/unverified checks, P0/P1 unverified trust items, and untracked current-scope safety waivers. `/bs` runs grade lint before fix-loop decisions and auto-merge for applicable tasks. Low-risk docs/spec cycles stay lightweight.
- v1.3.6: multi-round fix loop hardening. `reshape_fix_round.py` scopes resume/idempotency state to the current fix round so prior `bs-fix-round` markers do not block strict-decrease R >= 2 re-shapes; `conduct.sh --fix-round R` anchors the guard on the full HTML marker with matching archive and grade; tests cover the R=2 strict-decrease happy path and prose-substring false positive.
- v1.3.5: mechanically-enforced fix-round capsule re-shape. `reshape_fix_round.py` archives `outcome.v<R-1>.md`, folds structured grade findings (failed acceptance IDs plus bounded corrections, not pasted raw markdown) and a `bs-fix-round` marker; `conduct.sh --fix-round R` guards on archive + grade + marker; the driver still sends one `/goal @outcome.md`; per-round evidence dirs and `max_fix_rounds=3` with strict P0+P1 decrease are locked.
- v1.3.4: code-enforced app-server-only Conduct path, `/goal @outcome.md`, startup preflight dependency gate, transient launch retry-then-stop, mandatory `conduct.sh`, stdout-only idle timeout, test-only fake Codex injection, and runtime manifest hash.
