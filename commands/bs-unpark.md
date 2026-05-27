# /bs-unpark

Move a parked backlog task back to pending.

Usage: `/bs unpark <id>`

Flow:

1. Resolve repo root and validate binding/backlog.
2. Require clean `main`.
3. Require target `status == parked`.
4. Set `status: pending`; clear `parked_reason`, `closed_in`, and `closed_at`.
5. Commit only `.bootstrap/backlog.yaml` with `bs: unpark <ID>` and push `origin main`.
6. Verify `HEAD == origin/main`.
