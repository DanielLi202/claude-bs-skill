# /bs-park

Park a pending backlog task.

Usage: `/bs park <id> --reason "..."`

Flow:

1. Resolve repo root and validate binding/backlog.
2. Require clean `main` and no `in_progress` task unless the target task is unrelated and the user explicitly confirms.
3. Require target `status == pending`.
4. Set `status: parked`, `parked_reason`, `closed_in: parked-<YYYYMMDDHHMMSSZ>`, and `closed_at`.
5. Commit only `.bootstrap/backlog.yaml` with `bs: park <ID>` and push `origin main`.
6. Verify `HEAD == origin/main`.
