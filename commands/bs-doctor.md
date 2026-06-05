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
7. Report next pending unblocked task and any `in_progress` task.
8. If a cycle directory exists, validate `step_events.jsonl` strict pairing and required artifacts. For Conduct rounds, expect round-scoped evidence under `evidence/conduct_round_<N>/`: `raw_vendor_output.jsonl`, `rpc_requests.jsonl`, `vendor_stderr.txt`, `driver_events.jsonl`, and `codex_env.json`.

Do not modify files. End with actionable repair commands only.
