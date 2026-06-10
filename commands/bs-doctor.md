# /bs-doctor

Read-only health diagnosis for a bootstrap-enabled repository.

## Checks

1. Resolve repo root and verify `.bootstrap.yaml` exists.
2. Validate required binding fields, path containment, and `workflow_dir` override if set.
3. Verify contract hash three-way equality:
   - `.bootstrap.yaml.contract.source_sha256`;
   - `.bootstrap/contract.sha256`;
   - `~/.claude/skills/bs/contract.md` actual sha256.
4. Report version-skew diagnostics even when hashes match:
   - `.bootstrap.yaml.contract.source_tag`;
   - installed `contract.md` title version;
   - `skill.yaml` version / contract_version when readable;
   - bundled driver `clientInfo.version` values when grep-readable.
   These are warnings, not hash failures; include the exact files to refresh or a `/bs refresh-contract` suggestion.
5. Verify `contract.source_commit` still matches `contract.source_tag` on the remote when network is available.
6. Validate `.bootstrap/backlog.yaml`: enums, duplicate IDs, unknown blockers, dependency cycles, terminal closure invariants, parked/escalated reason invariants.
7. Before reporting a generic `in_progress` blocker, check for the close-gap
   recovery state:
   - exactly one backlog task is `in_progress`;
   - that task's latest cycle directory contains `auto_merge_gate.yaml` with
     `decision: merge`;
   - `step_events.jsonl` has an open `step_7` or `step_10` `started` event
     without its terminal pair, or the cycle artifacts contain offline evidence
     that the PR was already merged;
   - no `step_10 completed` event exists.

   Report this as RED, not as a generic in-progress task:

   ```text
   RED recovery_required=merged_pr_needs_step10_close cycle=<NNN> task=<ID>
   exact_resume_instruction: run /bs-resume in this repo and use the "Merged-PR Step-10 recovery" path; do not run /bs until Step 10 atomic close completes
   evidence: <cycle-dir>/auto_merge_gate.yaml decision=merge; <cycle-dir>/step_events.jsonl open step_7|step_10 or merged-PR evidence; .bootstrap/backlog.yaml task=<ID> status=in_progress
   ```

   The action text must point to `/bs-resume` and the named recovery section.
   Do not flatten this state to "task in_progress"; the key defect is that the
   PR is already merged and only the Step-10 atomic close is missing.
8. Report next pending unblocked task and any remaining `in_progress` task.
9. If a cycle directory exists, validate `step_events.jsonl` strict pairing and required artifacts. For Conduct rounds, expect round-scoped evidence under `evidence/conduct_round_<N>/`: `raw_vendor_output.jsonl`, `rpc_requests.jsonl`, `vendor_stderr.txt`, `driver_events.jsonl`, and `codex_env.json`.

Do not modify files. End with actionable repair commands only.
