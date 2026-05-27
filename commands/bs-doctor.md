# /bs-doctor

Read-only health diagnosis for a bootstrap-enabled repository.

## Checks

1. Resolve repo root and verify `.bootstrap.yaml` exists.
2. Validate required binding fields, path containment, and `workflow_dir` override if set.
3. Verify contract hash three-way equality:
   - `.bootstrap.yaml.contract.source_sha256`;
   - `.bootstrap/contract.sha256`;
   - `~/.claude/skills/bs/contract.md` actual sha256.
4. Verify `contract.source_commit` still matches `contract.source_tag` on the remote when network is available.
5. Validate `.bootstrap/backlog.yaml`: enums, duplicate IDs, unknown blockers, dependency cycles, terminal closure invariants, parked/escalated reason invariants.
6. Report next pending unblocked task and any `in_progress` task.
7. If a cycle directory exists, validate `step_events.jsonl` strict pairing and required artifacts.

Do not modify files. End with actionable repair commands only.
