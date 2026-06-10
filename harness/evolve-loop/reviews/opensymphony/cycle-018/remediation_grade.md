# Remediation grade — cycle-018 r1 findings F1-F6 (branch remediate/cycle-018, commit 31fe6c8)

Independent verification of the remediation delta (+~800/−240 across
`crates/symphony-adapter`, new `src/redaction.rs`) against the remediation outcome.
Gates: `cargo build --workspace`, `cargo fmt --all --check`, `cargo clippy --workspace
--all-targets -- -D warnings`, `cargo nextest run --workspace` (106/106, run twice),
`bash scripts/verify-docs.sh` — all exit 0.

- **R018-F1 (P1) — pass**: probes run via `run_probe_capture_with_timeout` — own process
  group spawn, explicit timeout bound, terminate-group then child wait/reap on expiry.
  Negative test `hung_probe_capture_times_out_fail_closed` runs a real `/bin/sh -c "sleep
  60"` probe under a 100ms timeout and asserts `ProbeFailed` within bounds (no hang).
- **R018-F2 (P1) — pass**: `run_vendor_stream` timeout path now terminates the process
  group, performs child wait/reap with bounded grace + SIGKILL fallback, and joins the
  stdout/stderr reader tasks before returning `VendorTimeout`. Negative test
  `vendor_stream_timeout_reaps_child_process_group` records the child PID and asserts the
  process is gone post-timeout (`assert_process_gone`) — real reap evidence, plus reader
  join before return.
- **R018-F3 (P1) — pass**: cleanup restructured so `thread/goal/clear` + `thread/archive`
  are issued (bounded best-effort, `CODEX_CLEANUP_RPC_TIMEOUT`) on the timeout/error exit
  path as well. Negative-path test `codex_timeout_still_clears_goal_and_archives_thread`
  forces the outer timeout against a never-completing fake app-server and asserts the
  fake's transcript records both `thread/goal/clear` and `thread/archive`.
- **R018-F4 (P1) — pass**: ingestion delivers every constructed normalized event.
  Per-source fixtures: test
  `normalizes_claude_init_and_result_goal_snapshots_without_post_turn_summary` asserts the
  `system/init` source event emits its `goal_snapshot` AND the `result` source event emits
  its `goal_snapshot`, with no `post_turn_summary` present to mask either source.
- **R018-F5 (P1) — pass**: new `redaction.rs` covers bare `token=`/`api_key=`/`sk-`,
  JSON/quoted (`{"api_key":"sk-..."}`, `"token":"..."`), and `Authorization: Bearer`
  header shapes. Test `codex_archived_stderr_redacts_json_and_bearer_secret_shapes`
  asserts none of the cleartext shapes survive into `evidence/vendor_stderr.txt` and
  `[REDACTED]` is present; existing bare-form tests retained.
- **R018-F6 (P1) — pass**: login status is JSON-parsed (serde_json) with a
  whitespace/key-case-tolerant fallback. Tests
  `login_status_detection_parses_json_false_variants` (unit, JSON-parsed variants) and
  `codex_probe_maps_logged_in_false_json_to_login_required` (e2e) cover
  `{"loggedIn": false}` format variants mapping to `LoginRequired`.

```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
  adversarial_p0_count: 0
  adversarial_p1_count: 0
  verdict: pass
```

```yaml
acceptance_status:
  - id: R018-F1
    status: pass
    severity: P1
  - id: R018-F2
    status: pass
    severity: P1
  - id: R018-F3
    status: pass
    severity: P1
  - id: R018-F4
    status: pass
    severity: P1
  - id: R018-F5
    status: pass
    severity: P1
  - id: R018-F6
    status: pass
    severity: P1
  - id: R018-ADV-SUBPROC-1
    status: pass
    severity: P1
  - id: R018-ADV-CLEANUP-1
    status: pass
    severity: P1
  - id: R018-ADV-SECRET-1
    status: pass
    severity: P1
  - id: R018-ADV-AUTH-1
    status: pass
    severity: P1
```

```yaml
spec_compliance_matrix:
  - id: R018-F1
    spec_ref: "docs/architecture/adapters/codex.md §1 (fail-closed probe); r1.md F1"
    status: pass
    evidence_ref: "run_probe_capture_with_timeout (process.rs): own process group + timeout + terminate-group + child wait/reap; test hung_probe_capture_times_out_fail_closed"
  - id: R018-F2
    spec_ref: "r1.md F2 (timeout must reap)"
    status: pass
    evidence_ref: "run_vendor_stream timeout branch: child spawned in its own process_group with a timeout bound; on expiry the process group is terminated, the child is waited/reaped (grace + SIGKILL fallback) and stdout/stderr reader tasks joined; test vendor_stream_timeout_reaps_child_process_group asserts recorded child PID gone"
  - id: R018-F3
    spec_ref: "docs/architecture/adapters/codex.md §2 (cleanup clear+archive); r1.md F3"
    status: pass
    evidence_ref: "cleanup on timeout/error exit path issues thread/goal/clear + thread/archive (bounded); negative-path test codex_timeout_still_clears_goal_and_archives_thread (forced timeout -> transcript asserts both RPCs)"
  - id: R018-F4
    spec_ref: "docs/architecture/adapters/claude-code.md; events.md §3.2; r1.md F4"
    status: pass
    evidence_ref: "per-source emission fixtures: system/init -> goal_snapshot asserted; result -> goal_snapshot asserted (test normalizes_claude_init_and_result_goal_snapshots_without_post_turn_summary)"
  - id: R018-F5
    spec_ref: "r1.md F5 (multi-shape secret redaction)"
    status: pass
    evidence_ref: "redaction.rs shape set bare/JSON-quoted/Authorization Bearer; test codex_archived_stderr_redacts_json_and_bearer_secret_shapes"
  - id: R018-F6
    spec_ref: "docs/architecture/adapters/codex.md §5 (LoginRequired distinct); r1.md F6"
    status: pass
    evidence_ref: "serde_json-parsed login status + tolerant fallback; tests login_status_detection_parses_json_false_variants + codex_probe_maps_logged_in_false_json_to_login_required"
```

```yaml
negative_regression_tests:
  - acceptance_id: R018-F1
    status: pass
    severity_if_fail: P1
    scenario: "A probe command that hangs (sleep 60) must fail closed within the 100ms timeout instead of hanging the adapter."
    evidence_ref: "process.rs test hung_probe_capture_times_out_fail_closed: own process group + timeout + group terminate + child wait/reap; asserts ProbeFailed within bounds"
  - acceptance_id: R018-F2
    status: pass
    severity_if_fail: P1
    scenario: "A streaming vendor that never exits must be reaped on timeout: child process group terminated, child waited/reaped, stdout/stderr reader tasks joined."
    evidence_ref: "process.rs test vendor_stream_timeout_reaps_child_process_group: records child PID, asserts process gone post-timeout (assert_process_gone), reader join before VendorTimeout"
  - acceptance_id: R018-F3
    status: pass
    severity_if_fail: P1
    scenario: "Forcing the outer timeout against a never-completing fake app-server must still issue thread/goal/clear + thread/archive on the timeout exit path."
    evidence_ref: "adapter_e2e codex_timeout_still_clears_goal_and_archives_thread: fake transcript asserts both cleanup RPCs after forced timeout"
  - acceptance_id: R018-F4
    status: pass
    severity_if_fail: P1
    scenario: "Claude transcripts containing system/init and result WITHOUT post_turn_summary must still emit a goal_snapshot per source event."
    evidence_ref: "normalize.rs test normalizes_claude_init_and_result_goal_snapshots_without_post_turn_summary: per-source fixtures, one assertion per source"
  - acceptance_id: R018-F5
    status: pass
    severity_if_fail: P1
    scenario: "Vendor stderr carrying JSON ({"api_key":"sk-..."}/quoted) and Authorization: Bearer secrets must be redacted in the archived evidence."
    evidence_ref: "adapter_e2e codex_archived_stderr_redacts_json_and_bearer_secret_shapes: cleartext shapes absent, [REDACTED] present; bare-form tests retained"
  - acceptance_id: R018-F6
    status: pass
    severity_if_fail: P1
    scenario: "Login-status JSON variants with whitespace/key-case differences ({"loggedIn": false}) must map to LoginRequired, not be misclassified."
    evidence_ref: "unit login_status_detection_parses_json_false_variants + adapter_e2e codex_probe_maps_logged_in_false_json_to_login_required"
  - acceptance_id: R018-ADV-SUBPROC-1
    status: pass
    severity_if_fail: P1
    scenario: "Lifecycle facets each negatively exercised: timeout bound, own process group, child wait/reap after signal, stream-task join."
    evidence_ref: "hung_probe_capture_times_out_fail_closed + vendor_stream_timeout_reaps_child_process_group"
  - acceptance_id: R018-ADV-CLEANUP-1
    status: pass
    severity_if_fail: P1
    scenario: "Cleanup must survive the timeout path: vendor child in its own process group is terminated and reaped only after clear+archive are attempted."
    evidence_ref: "codex_timeout_still_clears_goal_and_archives_thread"
  - acceptance_id: R018-ADV-SECRET-1
    status: pass
    severity_if_fail: P1
    scenario: "Three-shape cleartext probe (bare / JSON-quoted / Bearer) through the archived-stderr path; none may survive."
    evidence_ref: "codex_archived_stderr_redacts_json_and_bearer_secret_shapes"
  - acceptance_id: R018-ADV-AUTH-1
    status: pass
    severity_if_fail: P1
    scenario: "Format-variant login-status fixtures must be JSON-parsed, not literal-substring matched."
    evidence_ref: "login_status_detection_parses_json_false_variants"
```

```yaml
secret_leakage_audit:
  status: pass
  checked_surfaces:
    - "archived vendor stderr (evidence/vendor_stderr.txt) via redaction.rs"
    - "AdapterError Display/Debug messages (no token material; existing test retained)"
    - "capability probe login/auth output (parsed for a boolean; not stored)"
    - "normalized vendor_event payloads + evidence trace/raw files"
  cleartext_secret_probe:
    - shape: "bare token= / api_key= / sk- prefix"
      status: pass
      evidence_ref: "existing bare-form redaction tests retained (token=sk-secret-test class)"
    - shape: "JSON or quoted token/api_key ({\"api_key\":\"sk-...\"}, \"token\":\"...\")"
      status: pass
      evidence_ref: "codex_archived_stderr_redacts_json_and_bearer_secret_shapes asserts sk-json-secret and quoted-secret absent, [REDACTED] present"
    - shape: "Authorization: Bearer header"
      status: pass
      evidence_ref: "codex_archived_stderr_redacts_json_and_bearer_secret_shapes asserts bearer-secret absent"
  evidence_ref: "crates/symphony-adapter/src/redaction.rs + adapter_e2e redaction tests; nextest 106/106"
```

```yaml
dependency_spec_review:
  - dependency: "no new external crate introduced by the remediation"
    status: pass
    severity_if_fail: P1
    spec_ref: "docs/architecture/tech-stack.yaml; docs/ops/contributing.md"
    evidence_ref: "new src/redaction.rs uses std + already-workspace-pinned serde_json; Cargo.toml of symphony-adapter unchanged in [dependencies]"
```

```yaml
adversarial_checks:
  - id: ADV-SUBPROC-LIFECYCLE
    acceptance_ref: R018-ADV-SUBPROC-1
    surface: external_subprocess
    status: pass
    severity_if_fail: P1
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "lifecycle facets each evidenced: timeout bound (100ms hung-probe test), own process_group spawn (run_probe_capture_with_timeout + run_vendor_stream spawn), child wait/reap after signal (assert_process_gone on recorded PID; grace + SIGKILL fallback), stdout/stderr reader task join before return"
  - id: ADV-RPC-CLEANUP
    acceptance_ref: R018-ADV-CLEANUP-1
    surface: external_subprocess
    status: pass
    severity_if_fail: P1
    evidence_kind: malformed_input_test
    evidence_ref: "forced-timeout negative path: codex_timeout_still_clears_goal_and_archives_thread proves thread/goal/clear + thread/archive issued on the timeout exit path (transcript assertion); the app-server child runs in its own process_group with a timeout and is terminated + waited/reaped only after the bounded cleanup RPCs"
  - id: ADV-SECRET-SHAPES
    acceptance_ref: R018-ADV-SECRET-1
    surface: auth_or_secret
    status: pass
    severity_if_fail: P1
    evidence_kind: secret_leakage_probe
    evidence_ref: "three-shape cleartext probe (bare / JSON-quoted / Authorization Bearer) through the archived-stderr path; all redacted"
  - id: ADV-AUTH-FORMAT
    acceptance_ref: R018-ADV-AUTH-1
    surface: auth_or_secret
    status: pass
    severity_if_fail: P1
    evidence_kind: malformed_input_test
    evidence_ref: "JSON-parsed login status with whitespace/key-case variant fixtures mapping to LoginRequired"
```

```yaml
trust_surface_inventory:
  unverified_items: []
  verified_surfaces:
    - "external_subprocess: probes + stream + app-server child all spawn in their own process group with timeout; on every exit path the group is terminated and the child waited/reaped; stream reader tasks joined (tests: hung_probe_capture_times_out_fail_closed, vendor_stream_timeout_reaps_child_process_group, codex_timeout_still_clears_goal_and_archives_thread)"
    - "auth_or_secret: archived vendor output redacted across bare/JSON-quoted/Authorization Bearer shapes; login output parsed for a boolean and never stored"
    - "input_validation_or_schema: vendor login-status output JSON-parsed with whitespace/key-case-tolerant fallback before error mapping"
```

```yaml
deferred_claims: []
```
