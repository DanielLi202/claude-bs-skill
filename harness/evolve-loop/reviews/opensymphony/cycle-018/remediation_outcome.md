---
run_id: cycle-018-remediation
cycle: 018
task_type: code
risk_level: medium
task_class: remediation
---

# Remediation outcome — cycle-018 r1 findings F1-F6 (post-merge hardening)

Scope: fix the 6 P1 escapes found by the independent post-merge review (r1.md) in
`crates/symphony-adapter`, each with a regression test, under the repo's full Rust gate.

## Acceptance criteria

| ID | Acceptance | Severity | spec_refs |
|---|---|---|---|
| R018-F1 | Every capability-probe subprocess (`codex --version`, `codex login status`, `claude --version`, `claude auth status`, claude ping) runs fail-closed through a bounded helper: spawned in its own process group, subject to a timeout, and on timeout the group is terminated AND the child is reaped (wait); a hung probe yields `ProbeFailed`, never a hang. | P1 | docs/architecture/adapters/codex.md (§1), r1.md F1 |
| R018-F2 | The `run_vendor_stream` timeout path reaps the child process group after signalling (wait with bounded grace, SIGKILL fallback) and joins the stdout/stderr reader tasks before returning `VendorTimeout` — no zombie process and no leaked reader task. | P1 | r1.md F2 |
| R018-F3 | The Codex adapter issues `thread/goal/clear` + `thread/archive` cleanup on every exit path including the outer timeout/error path (bounded best-effort), not only the happy path. | P1 | docs/architecture/adapters/codex.md (§2), r1.md F3 |
| R018-F4 | Claude `system/init` and `result` source events each emit their constructed `goal_snapshot` normalized event (ingestion delivers every constructed event, not just the last). | P1 | docs/architecture/adapters/claude-code.md, events.md §3.2, r1.md F4 |
| R018-F5 | Secret redaction of archived vendor stderr covers bare `token=`/`api_key=`/`sk-` forms, JSON/quoted forms (`{"api_key":"sk-..."}`, `"token":"..."`), and HTTP header form (`Authorization: Bearer ...`). | P1 | r1.md F5 |
| R018-F6 | Codex login-status detection JSON-parses the status output where possible and tolerates whitespace/key-case variants (e.g. `{"loggedIn": false}`), mapping not-logged-in to `LoginRequired`. | P1 | docs/architecture/adapters/codex.md (§5), r1.md F6 |

## Risk surface (lint block)

```yaml
risk_surface:
  surfaces:
    external_subprocess: { present: true }
    process: { not_applicable: true, reason: "the child-process lifecycle surface is covered by external_subprocess (same rows R018-ADV-SUBPROC-1/CLEANUP-1); no separate in-process risk added" }
    auth_or_secret: { present: true }
    input_validation_or_schema: { present: true }
    concurrency_or_locking: { not_applicable: true, reason: "no lock-protocol change; reader-task join is covered under subprocess lifecycle" }
    string_boundary: { not_applicable: true, reason: "no request-target/path parsing change in this remediation" }
    runtime_files: { not_applicable: true, reason: "evidence/redaction file layout unchanged; only content redaction extended" }
    background_process: { not_applicable: true, reason: "vendor remains a monitored foreground child within handoff()" }
    network_probe: { not_applicable: true, reason: "adapter still performs no network IO itself" }
    identity_sentinel: { not_applicable: true, reason: "daemon instance/token files untouched" }
    file_modes: { not_applicable: true, reason: "no mode changes" }
    destructive_operation: { not_applicable: true, reason: "append-only ledger + evidence sidecars unchanged" }
```

## Adversarial acceptance (lint block)

```yaml
adversarial_acceptance:
  - id: R018-ADV-SUBPROC-1
    surface: external_subprocess
    severity: P1
    evidence_kind: subprocess_lifecycle_test
    verification_hint: "Hung probe (sleep 60) under a 100ms budget must fail closed within bounds; stream timeout must leave the child process group reaped (assert the recorded child PID is gone) and reader tasks joined."
  - id: R018-ADV-CLEANUP-1
    surface: external_subprocess
    severity: P1
    evidence_kind: malformed_input_test
    verification_hint: "Force the outer timeout against a fake app-server that never completes the goal; assert the fake's transcript still records thread/goal/clear and thread/archive."
  - id: R018-ADV-SECRET-1
    surface: auth_or_secret
    severity: P1
    evidence_kind: secret_leakage_probe
    verification_hint: "Fake vendor emits secrets in bare token=, JSON {\"api_key\":\"sk-...\"} and Authorization: Bearer forms on stderr; archived vendor_stderr.txt must contain [REDACTED] and none of the cleartext shapes."
  - id: R018-ADV-AUTH-1
    surface: input_validation_or_schema
    severity: P1
    evidence_kind: malformed_input_test
    verification_hint: "Login-status fixtures in JSON with whitespace/key-case variants ({\"loggedIn\": false}) must map to LoginRequired."
```
