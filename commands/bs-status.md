# /bs-status

Read-only bootstrap status summary.

Report:

1. contract source tag, source commit, and local hash status;
2. backlog counts by status;
3. current `in_progress` task, if any;
4. next pending unblocked task, if any;
5. latest cycle ID, PR URL, merge commit, and close commit from the ledger when present;
6. event-state status for the current cycle using strict `(step, attempt)` pairing.

Do not modify files.
