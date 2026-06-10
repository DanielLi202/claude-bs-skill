## Verification result

F1, F3, F4, F5, F6 are closed by code inspection. F2’s timeout branch is fixed, but the stronger “join both reader tasks on every return” claim is not true.

```yaml
r1_verify:
  findings:
    - id: F1
      closed: true
      reason: "Codex/Claude version/auth/login/ping probes route through run_probe_capture in process.rs, which uses process_group, timeout, terminate_and_reap, and bounded reader joins. I found no raw Command::output().await in crates/symphony-adapter/src."
    - id: F2
      closed: false
      reason: "The timeout branch now reaps and joins both tasks before VendorTimeout, but the post-wait path can return at process.rs:76-81 if stream_task fails/aborts before line 82 joins stderr_task. So the 'join both reader tasks on every return' property is still false."
    - id: F3
      closed: true
      reason: "run_codex_app_server stores cleanup_thread_id, exits the main RPC flow into result, then always calls cleanup_codex_thread before shutdown/terminate. cleanup_codex_thread sends thread/goal/clear and thread/archive with CODEX_CLEANUP_RPC_TIMEOUT bounds."
    - id: F4
      closed: true
      reason: "normalize_claude now returns Vec<NormalizedEvent>, and ingest_line appends every normalized event. system/init emits task_start plus goal_snapshot; result emits goal_snapshot plus task_end/failure."
    - id: F5
      closed: true
      reason: "redaction.rs matches the cited JSON/quoted token and Authorization: Bearer shapes, and both process.rs collect_stderr and codex/mod.rs stderr archival apply redact_secrets before writing vendor_stderr.txt."
    - id: F6
      closed: true
      reason: "login_status_is_logged_out parses JSON per line and matches loggedIn case-insensitively, with compact fallback for spacing/case variants. {\"loggedIn\": false} maps to LoginRequired before goal-RPC probing."
  tests_meaningful: false
  residual_risks: "Most cited tests are non-vacuous, but they do not cover run_vendor_stream's non-timeout stdout-reader failure/abort path where stderr_task is skipped."
```
