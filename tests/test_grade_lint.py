from pathlib import Path
import importlib.util, json, subprocess, sys, tempfile, textwrap, unittest
LINTER=Path(__file__).resolve().parents[1]/'runtime'/'grade_lint.py'
GRADE_LINT_SPEC=importlib.util.spec_from_file_location('grade_lint_runtime', LINTER)
GRADE_LINT=importlib.util.module_from_spec(GRADE_LINT_SPEC)
GRADE_LINT_SPEC.loader.exec_module(GRADE_LINT)
BASIC='''# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
'''
OUTCOME='''# Outcome
```yaml
risk_surface:
  surfaces:
    process: {present: true}
    runtime_files: {present: true}
    identity_sentinel: {present: true}
    network_probe: {present: true}
    background_process: {present: true}
    file_modes: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-TRUST
    severity: P1
    surface: [process, runtime_files, identity_sentinel, network_probe, background_process, file_modes]
    statement: trust surface must be probed
    verification_hint: inspect code and run fault probe
```
'''
LOW_CODE_OUTCOME='''# Outcome
```yaml
acceptance:
  - id: CFG
    severity: P1
    statement: use locked crate dependency and reject malformed config safely
  - id: INIT
    severity: P2
    statement: init writes files
```
'''
AUTH_SECRET_CODE_OUTCOME='''# Outcome
```yaml
risk_surface:
  surfaces:
    auth_or_secret: {present: true}
```
```yaml
acceptance:
  - id: CFG
    severity: P1
    statement: auth token handling redacts secret values from evidence
  - id: INIT
    severity: P2
    statement: init writes files
```
'''
BASIC_CODE_SECTIONS='''```yaml
spec_compliance_matrix:
  - acceptance_id: CFG
    status: pass
    severity_if_fail: P1
    spec_ref: docs/spec.md#config
    evidence_ref: tests/config.rs::locked_dependency_and_yaml_comments
  - acceptance_id: INIT
    status: pass
    severity_if_fail: P2
    spec_ref: docs/spec.md#init
    evidence_ref: tests/init.rs::init_smoke
```
```yaml
negative_regression_tests:
  - acceptance_id: CFG
    status: pass
    severity_if_fail: P1
    scenario: malformed secret-bearing YAML does not echo the secret and locked dependency is present
    evidence_ref: tests/config.rs::malformed_secret_yaml_is_redacted
```
```yaml
secret_leakage_audit:
  status: pass
  checked_surfaces: [debug, display, errors, logs]
  cleartext_secret_probe:
    status: pass
    shapes:
      - token=sk-secret-test
      - '{"api_key":"sk-secret-test"}'
      - "Authorization: Bearer sk-secret-test"
  evidence_ref: tests/config.rs::malformed_secret_yaml_is_redacted
```
```yaml
dependency_spec_review:
  - dependency: serde_yaml_bw
    status: pass
    severity_if_fail: P1
    spec_ref: docs/architecture/tech-stack.yaml
    evidence_ref: cargo tree -p symphony-config
```
'''
A1_CODE_SECTIONS='''```yaml
spec_compliance_matrix:
  - acceptance_id: A1
    status: pass
    severity_if_fail: P1
    spec_ref: docs/spec.md#a1
    evidence_ref: tests/a1.rs::covers_a1
```
```yaml
negative_regression_tests:
  - acceptance_id: A1
    status: pass
    severity_if_fail: P1
    scenario: malformed or stale input does not pass the A1 invariant
    evidence_ref: tests/a1.rs::rejects_stale_input
```
```yaml
secret_leakage_audit:
  status: pass
  checked_surfaces: [debug, display, errors, logs]
  cleartext_secret_probe:
    status: pass
    shapes:
      - token=sk-secret-test
      - '{"api_key":"sk-secret-test"}'
      - "Authorization: Bearer sk-secret-test"
  evidence_ref: tests/a1.rs::secrets_are_redacted
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
COMPLETE='''# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - {id: stale-pid-wrong-process, acceptance_id: ADV-TRUST, status: pass, severity_if_fail: P1, surface: [process], evidence_ref: evidence/grade/stale_pid_probe.log}
```
```yaml
trust_surface_inventory:
  runtime_files: []
  identity_sentinels: []
  network_probes: []
  background_processes: []
  unverified_items: []
```
```yaml
deferred_claims:
  - {item: header, deferred_to: B-002, current_scope_implementable: false, rationale: future}
  - {item: body.instance_id comparison, current_scope_implementable: true, evidence_ref: src/status.rs}
```
''' + A1_CODE_SECTIONS
WAIVER=COMPLETE.replace('{item: body.instance_id comparison, current_scope_implementable: true, evidence_ref: src/status.rs}','{item: body.instance_id comparison, current_scope_implementable: true, waiver: true, severity_if_fail: P1, reason: defer current-scope safety}')
LOW_CODE_COMPLETE='''# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: CFG, status: pass, severity: P1}
  - {id: INIT, status: pass, severity: P2}
```
''' + BASIC_CODE_SECTIONS
CYCLE017_STYLE_OUTCOME='''---
title: "B-005 — Pattern Library reader + API endpoints"
type: code
risk_level: low
acceptance:
  - id: B005-PATH-SAFETY
    severity: P1
    statement: >
      skill_id is validated before any filesystem access. Any skill_id containing `..`, `/`,
      `\\`, or that is an absolute path is rejected so no read can traverse outside the
      pattern roots.
    verification_hint: >
      Test negative path traversal ids before reading from the filesystem.
---
# B-005
'''
CYCLE017_INSUFFICIENT_GRADE='''# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: B005-PATH-SAFETY, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B005-PATH-SAFETY
    status: pass
    severity_if_fail: P1
    spec_ref: docs/architecture/storage-layout.md
    evidence_ref: validate_skill_id + basic invalid id tests
```
```yaml
negative_regression_tests:
  - acceptance_id: B005-PATH-SAFETY
    status: pass
    severity_if_fail: P1
    scenario: skill_id with .., slash, backslash, absolute path, URL-encoded %2F/%5C is rejected
    evidence_ref: tests::rejects_dotdot_slash_backslash_absolute
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: path safety fixture does not touch secrets
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
CYCLE017_SUFFICIENT_GRADE=CYCLE017_INSUFFICIENT_GRADE.replace(
    'scenario: skill_id with .., slash, backslash, absolute path, URL-encoded %2F/%5C is rejected\n    evidence_ref: tests::rejects_dotdot_slash_backslash_absolute',
    'scenario: skill_id with .., slash, backslash, absolute path, URL-encoded %2F/%5C is rejected; symlinked skill directories cannot escape the root; canonicalized candidate paths must starts_with the canonical root\n    evidence_ref: tests::rejects_dotdot_slash_backslash_absolute + tests::rejects_symlink_escape_with_canonical_root_containment'
)
REQUEST_TARGET_OUTCOME='''---
title: "Raw HTTP detail path"
type: code
risk_level: low
acceptance:
  - id: CLIENT-REQUEST-TARGET
    severity: P1
    statement: >
      The client builds a raw HTTP/1.1 request target from a user-controlled path segment.
      It must percent-encode or reject request-target delimiters and control characters.
    verification_hint: >
      Test request target boundary ids.
---
# Request target
'''
REQUEST_TARGET_INSUFFICIENT_GRADE='''# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: CLIENT-REQUEST-TARGET, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: CLIENT-REQUEST-TARGET
    status: pass
    severity_if_fail: P1
    spec_ref: docs/api.md
    evidence_ref: tests::known_id_detail
```
```yaml
negative_regression_tests:
  - acceptance_id: CLIENT-REQUEST-TARGET
    status: pass
    severity_if_fail: P1
    scenario: unknown skill id returns 404
    evidence_ref: tests::unknown_id_404
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: request-target fixture does not touch secrets
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
REQUEST_TARGET_SUFFICIENT_GRADE=REQUEST_TARGET_INSUFFICIENT_GRADE.replace(
    'scenario: unknown skill id returns 404\n    evidence_ref: tests::unknown_id_404',
    'scenario: request-target delimiters ?, #, spaces, CRLF/control chars, and percent-encoded path segments are rejected or encoded\n    evidence_ref: tests::request_target_delimiters_and_control_chars'
)
REQUEST_TARGET_GENERIC_ONLY_GRADE=REQUEST_TARGET_INSUFFICIENT_GRADE.replace(
    'scenario: unknown skill id returns 404\n    evidence_ref: tests::unknown_id_404',
    'scenario: request-target smoke regression covers the ordinary unknown id path\n    evidence_ref: /Users/lidongyuan/workspace/tests/request_target_unknown_id_smoke.log'
)
REQUEST_TARGET_MALFORMED_ONLY_GRADE=REQUEST_TARGET_INSUFFICIENT_GRADE.replace(
    'scenario: unknown skill id returns 404\n    evidence_ref: tests::unknown_id_404',
    'scenario: malformed request is rejected\n    evidence_ref: /Users/lidongyuan/workspace/tests/malformed_request_smoke.log'
)
CYCLE018_SECRET_BARE_OUTCOME='''# Outcome Capsule — B-018 M5 Conduct adapter (cycle-018, Phase 2)
```yaml
acceptance:
  - id: B018-A11
    severity: P1
    statement: >
      **Secret / auth non-leakage.** The probe reads `codex login status` / `claude auth status`, but auth tokens, API keys, or OAuth material never appear in `AdapterError` `Debug`/`Display`, `tracing` output, normalized ledger events, or any `evidence/` file. `LoginRequired`/`NotAuthenticated` carry only an actionable remediation string, not captured auth output.
```
'''
CYCLE018_SECRET_BARE_GRADE='''# Grade — B-018 M5 Conduct adapter (cycle-018, round 1)
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B018-A11
    status: pass
    severity: P1
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B018-A11
    status: pass
    severity_if_fail: P1
    spec_refs: ["docs/ops/contributing.md", "docs/decisions/product.md"]
    evidence_ref: "src/process.rs:170-190 redact_secrets (token=/api_key=/sk-/oauth); src/lib.rs error messages carry no captured auth output; tests adapter_errors_do_not_display_token_material + codex_probe_maps_not_logged_in_without_secret_leakage"
```
```yaml
negative_regression_tests:
  - acceptance_id: B018-A11
    status: pass
    severity_if_fail: P1
    scenario: "A token-shaped secret in vendor stderr or a logged-out probe must not surface in AdapterError Debug/Display, evidence, or events; redact_secrets masks token=/api_key=/sk-/oauth."
    evidence_ref: "src/process.rs:170-190; tests adapter_errors_do_not_display_token_material + codex_probe_maps_not_logged_in_without_secret_leakage (nextest pass)"
```
```yaml
secret_leakage_audit:
  status: pass
  checked_surfaces:
    - "AdapterError Debug + Display (src/lib.rs:63-111)"
    - "vendor stderr capture redaction (src/process.rs:151-190, src/codex/mod.rs:210-226)"
    - "capability probe login/auth output (inspected for a boolean only, not stored; src/codex/mod.rs:80-88,540-559)"
    - "tracing warn! calls in normalize (no token/auth fields)"
    - "normalized vendor_event payloads + evidence trace/raw files"
  cleartext_secret_probe: pass
  evidence_ref: "tests adapter_errors_do_not_display_token_material + codex_probe_maps_not_logged_in_without_secret_leakage; src/process.rs:170-190 redact_secrets -> [REDACTED]; nextest green"
```
```yaml
dependency_spec_review:
  - dependency: "async-trait"
    status: pass
    severity_if_fail: P1
    spec_ref: "docs/ops/contributing.md (§9 license allowlist), docs/architecture/tech-stack.yaml"
    evidence_ref: "root Cargo.toml [workspace.dependencies] async-trait = \\"0.1.89\\" (pinned); Cargo.lock async-trait 0.1.89 from crates.io; license MIT OR Apache-2.0 (allowlisted)"
```
'''
CYCLE017_SECRET_NOT_APPLICABLE_OUTCOME='''# Grade round 0 — cycle-017 / B-005 Pattern Library reader + API endpoints
```yaml
acceptance:
  - id: B005-MALFORMED-ROBUST
    severity: P1
    statement: >
      parse_skill_file/parse_skill_text return degraded ParsedSkill (parse_ok=false + parse_error) for read error / non-utf8 / missing-frontmatter / malformed-yaml — never panic.
```
'''
CYCLE017_SECRET_NOT_APPLICABLE_GRADE='''# Grade round 0 — cycle-017 / B-005 Pattern Library reader + API endpoints
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B005-MALFORMED-ROBUST
    severity: P1
    status: pass
    evidence: "parse_skill_file/parse_skill_text return degraded ParsedSkill (parse_ok=false + parse_error) for read error / non-utf8 / missing-frontmatter / malformed-yaml — never panic; tests malformed_skills_degrade_without_breaking_listing (good+no-frontmatter+bad-yaml all list) + non_utf8_skill_degrades_without_error."
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B005-MALFORMED-ROBUST
    severity_if_fail: P1
    status: pass
    spec_refs: ["docs/ops/roadmap.md §4.1 dogfood task 2 (robust to missing YAML front matter)", "docs/decisions/product.md D-P25"]
    evidence_ref: "parse_skill_file degradation + tests malformed_skills_degrade_without_breaking_listing / non_utf8_skill_degrades_without_error"
```
```yaml
negative_regression_tests:
  - acceptance_id: B005-MALFORMED-ROBUST
    severity_if_fail: P1
    status: pass
    scenario: "malformed YAML front matter / missing front matter / non-UTF8 SKILL.md does not crash listing"
    evidence_ref: "tests malformed_skills_degrade_without_breaking_listing + non_utf8_skill_degrades_without_error (return Ok with degraded entry)"
```
```yaml
secret_leakage_audit:
  status: pass
  cleartext_secret_probe: not_applicable
  evidence_ref: "crates/symphony-patterns/src/lib.rs (PatternError/PatternEntry/PatternDetail) + crates/symphony-api/src/handlers/mod.rs (patterns_index/patterns_detail/pattern_error_to_api_error) + apps/symphony format_patterns; no auth/token/log code added (symphony-api auth.rs unchanged)"
  checked_surfaces:
    - "PatternError Debug/Display (thiserror): messages contain only path + skill_id (user-supplied dir name) — no tokens/keys/passwords."
    - "PatternEntry / PatternDetail Serialize (API JSON + CLI): id/name/description/risk_level/source/imported_from/has_usage/parse_ok/parse_error/body/usage — pattern metadata, not credentials."
    - "usage.json content surfaced verbatim in detail: local pattern metadata, not secret-bearing; reader never reads auth.json / daemon token."
    - "No logging added in this cycle; the crate touches no auth/token/network code."
```
```yaml
dependency_spec_review:
  - check: "no new third-party dependency introduced"
    status: pass
    severity_if_fail: P1
    spec_ref: "docs/architecture/tech-stack.yaml + docs/ops/contributing.md §6"
    evidence_ref: "crates/symphony-patterns/Cargo.toml uses only existing workspace deps serde/serde_json/serde_yaml_bw/thiserror/symphony-storage; no addition to root [workspace.dependencies]"
```
'''
SUBPROCESS_LIFECYCLE_OUTCOME='''# Outcome Capsule — B-018 M5 Conduct adapter (cycle-018, Phase 2)
```yaml
risk_surface:
  surfaces:
    external_subprocess: {present: true}
```
```yaml
adversarial_acceptance:
  - id: B018-ADV-PROBE-FAILCLOSED-1
    surface: external_subprocess
    severity: P1
    evidence_kind: subprocess_lifecycle_test
    verification_hint: "Simulate Codex/Claude capability probe version and auth-status helper commands plus a stream-json ping helper; assert unsupported_fatal and no exec fallback."
```
'''
SUBPROCESS_LIFECYCLE_INSUFFICIENT_GRADE='''# Grade — B-018 M5 Conduct adapter (cycle-018, round 1)
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: GADV-PROBE-1
    acceptance_id: B018-ADV-PROBE-FAILCLOSED-1
    status: pass
    severity_if_fail: P1
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "src/codex/mod.rs:327-404 real in-process round trip + ephemeral-negative; failures map to VersionTooOld/LoginRequired/GoalRpcUnavailable; never builds an exec/--json/text-goal fallback argv; tests codex_fake_vendor_probe_exercises_goal_rpc_round_trip + codex_probe_maps_not_logged_in_without_secret_leakage + handoff_argv_uses_goal_rpc_without_exec_json_or_text_goal_fallback (nextest green)"
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
''' + A1_CODE_SECTIONS
SUBPROCESS_LIFECYCLE_COMPLETE_GRADE=SUBPROCESS_LIFECYCLE_INSUFFICIENT_GRADE.replace(
    'src/codex/mod.rs:327-404 real in-process round trip + ephemeral-negative; failures map to VersionTooOld/LoginRequired/GoalRpcUnavailable; never builds an exec/--json/text-goal fallback argv; tests codex_fake_vendor_probe_exercises_goal_rpc_round_trip + codex_probe_maps_not_logged_in_without_secret_leakage + handoff_argv_uses_goal_rpc_without_exec_json_or_text_goal_fallback (nextest green)',
    'src/process.rs spawn_process_group .process_group(0) own process-group isolation; every probe/version/auth-status/ping helper command is wrapped in time::timeout wait timeout/deadline; after SIGTERM/SIGKILL the child.wait().await wait/reap path runs; stream-json stdout/stderr reader tasks are awaited, joined, and drained before return; nextest green'
)
B001_NO_NEW_DEPS_OUTCOME='''# Outcome — cycle-009-derived dependency row
```yaml
acceptance:
  - id: B001-NO-NEW-DEPS
    severity: P1
    statement: >
      B001-NO-NEW-DEPS (P1) — pass: all deps in tech-stack.yaml; no daemonize/nix/libc;
      `--detach` via std `CommandExt::process_group(0)`.
```
'''
B001_NO_NEW_DEPS_GRADE='''# Grade — cycle-009-derived dependency row
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: B001-NO-NEW-DEPS, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B001-NO-NEW-DEPS
    status: pass
    severity_if_fail: P1
    spec_ref: docs/architecture/tech-stack.yaml
    evidence_ref: "all deps in tech-stack.yaml; no daemonize/nix/libc; `--detach` via std `CommandExt::process_group(0)`"
```
```yaml
negative_regression_tests:
  - acceptance_id: B001-NO-NEW-DEPS
    status: pass
    severity_if_fail: P1
    scenario: "dependency review rejects new external daemon crates"
    evidence_ref: "tech-stack dependency check"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: dependency compliance fixture does not touch secrets
```
```yaml
dependency_spec_review:
  - dependency: "daemonize/nix/libc"
    status: pass
    severity_if_fail: P1
    spec_ref: docs/architecture/tech-stack.yaml
    evidence_ref: "all deps in tech-stack.yaml; no daemonize/nix/libc"
```
'''
B002_IFMATCH_OUTCOME='''# Outcome — cycle-013-derived If-Match row
```yaml
acceptance:
  - id: B002-IFMATCH
    severity: P1
    statement: >
      B002-IFMATCH (P0) — pass: `if_match_middleware` on execute/approve/re-shape/cancel:
      missing → 428 `missing_precondition` (endpoint + expected_header); stale → 409
      `revision_conflict` (expected/current/changed_since); match → 2xx; answer-qa/edit-outcome
      optional. Tested (428/409/match). (Atomic CAS for true concurrency is deferred to B-004 —
      see deferred_claims; B-002 handlers are stubs with no real state to corrupt.)
```
'''
B002_IFMATCH_GRADE='''# Grade — cycle-013-derived If-Match row
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: B002-IFMATCH, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B002-IFMATCH
    status: pass
    severity_if_fail: P1
    spec_ref: docs/api.md#if-match
    evidence_ref: "if_match_middleware on execute/approve/re-shape/cancel covers 428/409/match"
```
```yaml
negative_regression_tests:
  - acceptance_id: B002-IFMATCH
    status: pass
    severity_if_fail: P1
    scenario: "missing/stale/matching If-Match headers on execute/approve/re-shape/cancel endpoints"
    evidence_ref: "428/409/match endpoint tests"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: If-Match endpoint fixture does not touch secrets
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
B001_DAEMON_LIFECYCLE_OUTCOME='''# Outcome — cycle-009-derived daemon lifecycle rows
```yaml
acceptance:
  - id: B001-DAEMON-RUN
    severity: P1
    statement: >
      B001-DAEMON-RUN (P0) — pass: fs4 `try_lock` exclusive (WouldBlock → AlreadyRunning,
      no clobber); base64url 32B token; UUID-v7 instance.id; atomic tempfile+sync+rename in
      order with port last; modes 0600/0644; JSON tracing; axum bind 127.0.0.1:0; `--detach`
      re-exec + process_group; integration test asserts second run reports "already running".
  - id: B001-DAEMON-STOP
    severity: P1
    statement: >
      B001-DAEMON-STOP (P0) — pass: SIGTERM graceful shutdown; reverse-order removal
      (port→token→pid→instance.id) + lock release; integration test asserts all 4 files gone
      and a subsequent status reports "not running".
```
'''
B001_DAEMON_LIFECYCLE_GRADE='''# Grade — cycle-009-derived daemon lifecycle rows
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: B001-DAEMON-RUN, status: pass, severity: P1}
  - {id: B001-DAEMON-STOP, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B001-DAEMON-RUN
    status: pass
    severity_if_fail: P1
    spec_ref: docs/daemon.md#run
    evidence_ref: "integration test asserts second run reports already running"
  - acceptance_id: B001-DAEMON-STOP
    status: pass
    severity_if_fail: P1
    spec_ref: docs/daemon.md#stop
    evidence_ref: "integration test asserts all 4 files gone and status reports not running"
```
```yaml
negative_regression_tests:
  - acceptance_id: B001-DAEMON-RUN
    status: pass
    severity_if_fail: P1
    scenario: "second daemon run reports already running"
    evidence_ref: "already-running integration test"
  - acceptance_id: B001-DAEMON-STOP
    status: pass
    severity_if_fail: P1
    scenario: "stop removes runtime files and status reports not running"
    evidence_ref: "stop integration test"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: daemon lifecycle fixture does not touch secret leakage surfaces
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
B001_QUALITY_OUTCOME='''# Outcome — cycle-009 real quality row
```yaml
acceptance:
  - id: B001-QUALITY
    severity: P1
    statement: >
      No unwrap()/expect()/panic!() in non-test production code paths. Domain errors
      use a thiserror DaemonError enum modeled on daemon.md §9 (AlreadyRunning,
      LockFailed, BindFailed, ...); infra boundaries use anyhow::Result.
      `cargo clippy --workspace --all-targets -- -D warnings` is clean and
      `cargo nextest run --workspace` (or `cargo test --workspace`) passes, including
      the storage path/mode tests and the daemon run/status/stop integration test.
      Every test that touches the filesystem uses an isolated SYMPHONY_HOME tempdir,
      never the real ~/.symphony.
```
'''
B001_QUALITY_GRADE='''# Grade — cycle-009 real quality row
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: B001-QUALITY, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B001-QUALITY
    status: pass
    severity_if_fail: P1
    spec_ref: docs/daemon.md#quality
    evidence_ref: "B001-QUALITY (P1) — pass: no unwrap/expect/panic in production paths; thiserror `DaemonError` enum (AlreadyRunning/LockFailed/BindFailed/…); clippy `-D warnings` clean; nextest 5/5; every fs-touching test uses an isolated SYMPHONY_HOME tempdir."
```
```yaml
negative_regression_tests:
  - acceptance_id: B001-QUALITY
    status: pass
    severity_if_fail: P1
    scenario: "daemon run/status/stop integration test remains covered by nextest"
    evidence_ref: "nextest 5/5"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: quality fixture does not touch secret leakage surfaces
```
```yaml
dependency_spec_review:
  - dependency: "workspace quality tooling"
    status: pass
    severity_if_fail: P1
    spec_ref: docs/architecture/tech-stack.yaml
    evidence_ref: "cargo clippy and cargo nextest use workspace-pinned tooling"
```
'''
B002_STATUS_HTTP_PROBE_OUTCOME='''# Outcome — cycle-013 real HTTP status probe row
```yaml
acceptance:
  - id: B002-STATUS
    severity: P1
    statement: >
      Authenticated `GET /api/v1/daemon/status` returns 200 with JSON containing at
      least instance_id, pid, port, version, uptime_sec, binding ("127.0.0.1"), and
      log_path (B-001 fields preserved; §3.7 count fields like workspaces_active /
      runs_active / vendor_subprocesses / autostart_enabled may be derived from the
      minimal projection or 0/false). No secret field (token) is ever present. The
      daemon's internal readiness/status/stop probe sends `Authorization: Bearer
      <token>` read from daemon.token.
```
'''
B002_STATUS_HTTP_PROBE_GRADE='''# Grade — cycle-013 real HTTP status probe row
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: B002-STATUS, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B002-STATUS
    status: pass
    severity_if_fail: P1
    spec_ref: docs/api.md#status
    evidence_ref: "B002-STATUS (P0) — pass: authenticated `GET /api/v1/daemon/status` returns the §3.7 JSON (instance_id, pid, port, version, uptime_sec, started_at, binding=127.0.0.1, workspaces_active, runs_active, vendor_subprocesses, autostart_enabled, log_path); no token field. The internal probe (`fetch_status_bounded`) + stop (`post_stop_bounded`) send `Authorization: Bearer <token>` read from `daemon.token`, plus an `X-Symphony-Instance-Id` response check. `symphony daemon status`/`stop` pass in `daemon_cli.rs`."
```
```yaml
negative_regression_tests:
  - acceptance_id: B002-STATUS
    status: pass
    severity_if_fail: P1
    scenario: "authenticated GET /api/v1/daemon/status plus Authorization Bearer status probe"
    evidence_ref: "daemon_cli.rs status probe"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: HTTP status probe fixture does not expose token fields
```
```yaml
dependency_spec_review:
  - dependency: "status endpoint version field"
    status: pass
    severity_if_fail: P1
    spec_ref: docs/architecture/tech-stack.yaml
    evidence_ref: "status response version field is application metadata, no new dependency"
```
'''
B002_NO_REGRESSION_OUTCOME='''# Outcome — cycle-013 real daemon lifecycle regression row
```yaml
acceptance:
  - id: B002-NO-REGRESSION
    severity: P1
    statement: >
      B-001 behavior is preserved: `symphony daemon run` / `daemon status` / `daemon
      stop` lifecycle still works (now against the authenticated status endpoint),
      runtime-file atomic-write ordering + modes (token 600) unchanged, single-instance
      fs4 lock unchanged, reverse-order cleanup unchanged, terminal close does not kill
      the daemon. The existing apps/symphony/tests/daemon_cli.rs integration test passes
      (updated as needed for the auth change).
```
'''
B002_NO_REGRESSION_GRADE='''# Grade — cycle-013 real daemon lifecycle regression row
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: B002-NO-REGRESSION, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B002-NO-REGRESSION
    status: pass
    severity_if_fail: P1
    spec_ref: docs/daemon.md#lifecycle
    evidence_ref: "B002-NO-REGRESSION (P1) — pass: B-001 daemon run/status/stop lifecycle, atomic runtime-file ordering + modes, fs4 lock, reverse-order cleanup preserved; `daemon_cli.rs` (run→authed status 200→stop→files removed, stale-port/instance recovery) passes; stop now uses the authenticated API endpoint rather than raw `kill -TERM`."
```
```yaml
negative_regression_tests:
  - acceptance_id: B002-NO-REGRESSION
    status: pass
    severity_if_fail: P1
    scenario: "daemon_cli.rs run→authed status 200→stop→files removed"
    evidence_ref: "daemon_cli.rs"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: daemon lifecycle regression fixture does not touch secret leakage surfaces
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
ADV_CONCURRENCY_OUTCOME='''# Outcome — cycle-016 real concurrency adversarial row
```yaml
risk_surface:
  surfaces:
    concurrency_or_locking: {present: true}
```
```yaml
adversarial_acceptance:
  - id: B004-ADV-CONCURRENCY-1
    surface: concurrency_or_locking
    severity: P1
    evidence_kind: concurrency_test
    verification_hint: "Spawn 2+ concurrent appenders writing distinct idempotency keys to one events.jsonl guarded by the fs4 exclusive lock; assert the final line count equals the total number of appends, every line parses as exactly one JSON object, and there are no interleaved or partial writes."
```
'''
ADV_CONCURRENCY_GRADE='''# Grade — cycle-016 real concurrency adversarial row
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: ADV-CHECK-CONCURRENCY
    acceptance_ref: B004-ADV-CONCURRENCY-1
    surface: concurrency_or_locking
    status: pass
    severity_if_fail: P1
    evidence_kind: concurrency_test
    evidence_ref: "symphony-ledger::tests::concurrent_appenders_write_complete_lf_terminated_json_lines — 16 concurrent appenders (separate fds) under the fs4 exclusive lock yield exactly 16 complete, LF-terminated, individually-parseable JSON lines (no interleave/torn write)."
```
```yaml
trust_surface_inventory:
  verified_items:
    - surface: concurrent_ledger_append
      status: verified
      note: "fs4 exclusive lock + 5s timeout (FileLockTimeout) + fsync; validate-before-write; 16-thread test green"
  unverified_items: []
```
```yaml
deferred_claims: []
```
''' + A1_CODE_SECTIONS
VENDOR_PROBE_OUTCOME='''# Outcome — vendor command probe row
```yaml
acceptance:
  - id: VENDOR-PROBE
    severity: P1
    statement: >
      Codex capability probe invokes the vendor CLI binary via Command and checks
      --version before use.
```
'''
VENDOR_PROBE_GRADE='''# Grade — vendor command probe row
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: VENDOR-PROBE, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: VENDOR-PROBE
    status: pass
    severity_if_fail: P1
    spec_ref: docs/vendor.md#probe
    evidence_ref: "Codex capability probe verifies --version"
```
```yaml
negative_regression_tests:
  - acceptance_id: VENDOR-PROBE
    status: pass
    severity_if_fail: P1
    scenario: "vendor CLI binary probe maps unsupported version"
    evidence_ref: "probe status mapping test"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: vendor probe fixture does not touch secret leakage surfaces
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
RPC_CLEANUP_OUTCOME='''# Outcome Capsule — B-018 M5 Conduct adapter (cycle-018, Phase 2)
```yaml
acceptance:
  - id: B018-A6
    severity: P1
    statement: >
      Codex handoff uses app-server non-ephemeral goal-RPC only. Cleanup
      (`thread/goal/clear` + `thread/archive`) runs on every exit path.
```
'''
RPC_CLEANUP_HAPPY_ONLY_GRADE='''# Grade — B-018 M5 Conduct adapter (cycle-018, round 1)
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B018-A6
    status: pass
    severity: P1
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B018-A6
    status: pass
    severity_if_fail: P1
    spec_refs: ["docs/architecture/adapters/codex.md", "docs/agents/conduct/AGENT.md"]
    evidence_ref: "src/codex/mod.rs:242-276 5s inferred-completion timer after item/completed final answer -> session.emit_inferred_task_end(); explicit turn/completed wins; test codex_fake_vendor_infers_terminal_event_after_final_answer_race resolves ~5s (nextest pass)"
```
```yaml
negative_regression_tests:
  - acceptance_id: B018-A6
    status: pass
    severity_if_fail: P1
    scenario: "A turn whose final answer arrives but whose explicit turn/completed is missing/raced must still resolve to a terminal task_end (inferred) within ~5s rather than hanging to the full timeout."
    evidence_ref: "src/codex/mod.rs:242-276; test codex_fake_vendor_infers_terminal_event_after_final_answer_race asserts TaskEnd + extra.inferred_completion=true (nextest pass)"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: rpc cleanup fixture has no auth/token/log secret surface
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
RPC_CLEANUP_TIMEOUT_EVIDENCE_GRADE=RPC_CLEANUP_HAPPY_ONLY_GRADE.replace(
    'scenario: "A turn whose final answer arrives but whose explicit turn/completed is missing/raced must still resolve to a terminal task_end (inferred) within ~5s rather than hanging to the full timeout."\n    evidence_ref: "src/codex/mod.rs:242-276; test codex_fake_vendor_infers_terminal_event_after_final_answer_race asserts TaskEnd + extra.inferred_completion=true (nextest pass)"',
    'scenario: "A timeout path test forces the outer timeout after non-ephemeral thread creation and asserts thread/goal/clear + thread/archive are recorded before return."\n    evidence_ref: "tests codex_timeout_path_cleans_goal_and_archives_thread asserts clear/archive calls still happen (nextest pass)"'
)
RPC_CLEANUP_SOURCE_ROW_OUTCOME='''# Outcome Capsule — B-018 M5 Conduct adapter (cycle-018, Phase 2)
```yaml
acceptance:
  - id: B018-A5
    severity: P1
    statement: >
      Codex RPC check performs a real non-ephemeral goal-RPC round trip and
      fails closed when the round trip is unavailable.
```
'''
RPC_CLEANUP_SOURCE_ROW_GRADE='''# Grade — B-018 M5 Conduct adapter (cycle-018, round 1)
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B018-A5
    status: pass
    severity: P1
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B018-A5
    status: pass
    severity_if_fail: P1
    spec_refs: ["docs/architecture/adapters/codex.md", "docs/agents/conduct/AGENT.md"]
    evidence_ref: "src/codex/mod.rs:327-404 run_codex_goal_rpc_probe — real in-process initialize{experimentalApi}(goals:true) -> thread/start(ephemeral:false) -> goal/set -> goal/get(active) -> goal/clear -> archive + ephemeral-negative (ephemeral:true goal/set must /error); failure->GoalRpcUnavailable, success->capability_probe_result=supported; tests codex_fake_vendor_probe_exercises_goal_rpc_round_trip (nextest pass)"
```
```yaml
negative_regression_tests:
  - acceptance_id: B018-A5
    status: pass
    severity_if_fail: P1
    scenario: "Each probe failure must map to the correct AdapterError with no fallback: a handshake/round-trip/ephemeral-negative failure -> GoalRpcUnavailable."
    evidence_ref: "tests codex_probe_maps_not_logged_in_without_secret_leakage + handoff_argv_uses_goal_rpc_without_exec_json_or_text_goal_fallback (nextest pass)"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: rpc cleanup fixture has no auth/token/log secret surface
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
CYCLE016_LEDGER_CLEAN_OUTCOME='''# Outcome — cycle-016 B-004 Run Event Ledger + State Machine Projection
```yaml
acceptance:
  - id: B004-A1
    severity: P1
    statement: >
      Ledger append is idempotent and collision-safe under fs4 lock_with_timeout;
      duplicate idempotency keys are skipped and changed payloads return IdempotencyCollision.
```
'''
CYCLE016_LEDGER_CLEAN_GRADE='''# Grade — cycle-016 B-004 Run Event Ledger + State Machine Projection (round 0)
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B004-A1
    status: pass
    severity: P1
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B004-A1
    status: pass
    severity_if_fail: P1
    spec_refs: ["docs/architecture/schemas/events.md"]
    evidence_ref: "symphony-ledger::tests::append_is_idempotent_and_collision_safe; lib.rs append()/append_locked() (fs4 lock_with_timeout + SeekFrom::End + sync_data; dup-skip vs IdempotencyCollision)"
```
```yaml
negative_regression_tests:
  - acceptance_id: B004-A1
    status: pass
    severity_if_fail: P1
    scenario: "Re-append the same idempotency_key with a CHANGED payload returns LedgerError::IdempotencyCollision and never overwrites or duplicates the existing line."
    evidence_ref: "symphony-ledger::tests::append_is_idempotent_and_collision_safe"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "symphony-ledger append fixture has no auth/token/log secret surface"
```
```yaml
dependency_spec_review:
  - dependency: "symphony-ledger crate dependencies (fs4, serde, serde_json, thiserror, time)"
    status: pass
    severity_if_fail: P1
    spec_ref: "docs/architecture/tech-stack.yaml"
    evidence_ref: "crates/symphony-ledger/Cargo.toml uses *.workspace = true only; matches tech-stack.yaml pins"
```
'''
AUTH_STATUS_MAPPING_OUTCOME='''# Outcome Capsule — B-018 M5 Conduct adapter (cycle-018-derived)
```yaml
acceptance:
  - id: B018-A5
    severity: P1
    statement: >
      Codex capability probing must fail closed and route login/auth status
      failures to distinct remediation states.
```
'''
AUTH_STATUS_LITERAL_ONLY_GRADE='''# Grade — B-018-derived login-status mapping
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B018-A5
    status: pass
    severity: P1
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B018-A5
    status: pass
    severity_if_fail: P1
    spec_refs: ["docs/architecture/adapters/codex.md"]
    evidence_ref: "src/codex/mod.rs:327-404 run_codex_goal_rpc_probe; auth-status helper is wrapped in time::timeout, spawned with .process_group(0), and child.wait().await reaps it; no fabricated flag"
```
```yaml
negative_regression_tests:
  - acceptance_id: B018-A5
    status: pass
    severity_if_fail: P1
    scenario: "Each probe failure must map to the correct AdapterError with no fallback: an old version -> VersionTooOld; a not-logged-in vendor -> LoginRequired (with no secret leaked); a handshake failure -> GoalRpcUnavailable."
    evidence_ref: "tests codex_probe_maps_not_logged_in_without_secret_leakage (nextest pass)"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: login-status mapping fixture asserts status classification only and does not capture token material
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
AUTH_STATUS_JSON_PARSED_GRADE=AUTH_STATUS_LITERAL_ONLY_GRADE.replace(
    'tests codex_probe_maps_not_logged_in_without_secret_leakage (nextest pass)',
    'tests codex_probe_json_parsed_login_status_maps_logged_in_false_to_login_required uses serde_json::from_str and covers {"loggedIn": false} (nextest pass)'
)
AUTH_STATUS_VARIANT_FIXTURES_GRADE=AUTH_STATUS_LITERAL_ONLY_GRADE.replace(
    'tests codex_probe_maps_not_logged_in_without_secret_leakage (nextest pass)',
    'parameterized login-status format variants cover {"loggedin":false}, {"loggedIn": false}, and whitespace around the colon (nextest pass)'
)
EVENT_SOURCE_OUTCOME='''# Outcome — cycle-018-derived Claude source mapping
```yaml
acceptance:
  - id: B018-A7
    severity: P1
    statement: >
      Claude GoalSnapshot is driven by evaluator-loop source events:
      `system/init` and `result` produce `goal_snapshot` vendor events.
```
'''
EVENT_SOURCE_AGGREGATE_GRADE='''# Grade — cycle-018-derived aggregate evidence
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: B018-A7
    status: pass
    severity: P1
```
```yaml
spec_compliance_matrix:
  - acceptance_id: B018-A7
    status: pass
    severity_if_fail: P1
    spec_refs: ["docs/architecture/adapters/claude-code.md"]
    evidence_ref: "tests/adapter_e2e.rs claude_fake_vendor_demonstrates_m5_exit_condition asserts >=1 goal_snapshot + >=1 plan_snapshot + exactly one task_end; fake vendor includes post_turn_summary; nextest pass"
```
```yaml
negative_regression_tests:
  - acceptance_id: B018-A7
    status: pass
    severity_if_fail: P1
    scenario: "A Claude stream missing goal/plan/terminal events would fail the aggregate exit-condition assertion."
    evidence_ref: "tests/adapter_e2e.rs assert_exit_condition aggregate count"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: event source fixture has no auth/token/log secret surface
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: no dependency changes in this fixture
```
'''
EVENT_SOURCE_PER_SOURCE_GRADE=EVENT_SOURCE_AGGREGATE_GRADE.replace(
    'tests/adapter_e2e.rs claude_fake_vendor_demonstrates_m5_exit_condition asserts >=1 goal_snapshot + >=1 plan_snapshot + exactly one task_end; fake vendor includes post_turn_summary; nextest pass',
    'tests::claude_system_init_emits_goal_snapshot + tests::claude_result_emits_goal_snapshot; each fixture asserts its named source event produces goal_snapshot'
).replace(
    'scenario: "A Claude stream missing goal/plan/terminal events would fail the aggregate exit-condition assertion."\n    evidence_ref: "tests/adapter_e2e.rs assert_exit_condition aggregate count"',
    'scenario: "Per-source regressions assert system/init and result each emit goal_snapshot rather than relying on aggregate counts."\n    evidence_ref: "tests::claude_system_init_emits_goal_snapshot + tests::claude_result_emits_goal_snapshot"'
)
CYCLE019_SHAPE_ESCAPE_OUTCOME='''---
schema_version: "1.2"
title: "M4 Shape Agent — outcome capsule draft + assumptions + Shape critic"
goal: "Implement the symphony-shape crate: Shape Agent session driver, outcome capsule draft generation, Q&A round-trip, and Shape critic; expose symphony shape CLI subcommand."
risk_level: medium
non_goals:
  - "Do NOT write to patterns-user/, patterns-imported/, or memory-user/ directories (R-AGT-6 P0)"
context_pointers:
  - "docs/agents/shape/AGENT.md"
  - "prompts/agents/shape/critic.md"
assumptions:
  - "Pattern Library retrieval (D-P25) can be stubbed — call the existing symphony-patterns API but if patterns dir is empty, proceed with empty groundings"
  - "The Q&A round-trip for the CLI path means: Shape generates the questions, prints them to stdout, reads answers from stdin (or accepts --skip flag per D-P6 power-user path), then merges into outcome.md"
groundings: []
output_contract:
  artifacts:
    - type: file_set
      paths:
        - "crates/symphony-shape/src/session.rs"
        - "crates/symphony-shape/src/critic.rs"
  target: pr
acceptance:
  - id: a4
    severity: P1
    text: "symphony shape --skip one-liner produces a well-formed outcome.md in .symphony/runs/<run-id>/outcome.md (file exists, YAML front matter parses, has required fields: schema_version, id, title, goal, non_goals, acceptance, verification, risk_level)"
---
# Background
This milestone is deliberately scoped to the CLI-standalone path: `symphony shape --skip <one-liner>` runs without a daemon and directly produces `outcome.md` + `shape_session.md` + `shape_critic.yaml`.
'''
CYCLE019_SHAPE_ESCAPE_GRADE='''# Grade Round 0 — B-019 M4 Shape Agent
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: a4
    status: pass
    severity: P1
    text: "symphony shape --skip produces outcome.md with required schema_version 1.2 fields"
    evidence_ref: "manual: T-20260610-112850-9ec58cb8/outcome.md present with schema_version 1.2"
```
```yaml
spec_compliance_matrix:
  - acceptance_id: a4
    spec_ref: "docs/agents/shape/AGENT.md §3 runtime"
    status: pass
    severity_if_fail: P1
    evidence_ref: "manual: T-20260610-112850-9ec58cb8/outcome.md present with schema_version 1.2"
    notes: "ShapeSession.run_skip writes outcome.md via write_new (create_new=true)"
```
```yaml
negative_regression_tests:
  - id: nr2
    acceptance_id: a4
    scenario: "malformed YAML front matter returns Err(Yaml) without process crash"
    description: "parse_outcome_markdown on '---\\nbad: {unclosed\\n---\\n' returns Err(Yaml)"
    test_name: "symphony-shape capsule::tests::malformed_yaml_returns_error_without_panic"
    status: pass
    severity_if_fail: P1
    evidence_ref: evidence/grade_verify_round_0.yaml
```
```yaml
secret_leakage_audit:
  status: pass
  evidence_ref: evidence/grade_verify_round_0.yaml
  checked_surfaces:
    - "crates/symphony-shape/src/capsule.rs"
    - "crates/symphony-shape/src/session.rs"
    - "crates/symphony-shape/src/critic.rs"
    - "crates/symphony-shape/src/qa.rs"
  cleartext_secret_probe:
    - shape: bare_token_or_key
      result: pass
      note: "probe for bare api_key= or TOKEN= patterns: none found"
    - shape: json_or_quoted_token
      result: not_applicable
      reason: "no JSON serialization with 'api_key' or 'token' quoted fields"
    - shape: bearer_header
      result: not_applicable
      reason: "no HTTP calls or Authorization bearer headers in this crate"
```
```yaml
dependency_spec_review:
  - name: symphony-patterns
    spec_ref: "docs/architecture/api-contract.md §3.6 (B-005)"
    status: pass
    severity_if_fail: P1
    evidence_ref: evidence/grade_verify_round_0.yaml
    notes: "workspace path dep; read-only list_patterns call per R-AGT-6; no write path introduced"
```

B-019 delivers a complete, standalone `symphony-shape` crate implementing Phase 2 M4 Shape Agent.
All checks pass. R-AGT-6 upheld: symphony-shape calls symphony_patterns read-only only; writes only to `.symphony/runs/<run_id>/`.
'''
CYCLE018_ADAPTER_NON_SHAPE_GRADE=LOW_CODE_COMPLETE + '''

## Trust-boundary notes

- No write to `memory-user/` / `patterns-user/` / `patterns-imported/` (RL-1/RL-2); no
  daemon/api/client dependency (correct adapter dependency direction, contributing §6).
'''
CYCLE018_ADAPTER_NON_SHAPE_OUTCOME=LOW_CODE_OUTCOME + '''

## 4. Non-goals (explicit — out of scope this cycle)

- **No Shape / Grade / Evolve agent runtime** (M4/M6/M7). This crate provides the
  trait + adapters only; do not implement agents, critics, or their prompts.
- Do not read or write `memory-user/` / `patterns-user/` / `patterns-imported/`
  (RL-1/RL-2); they do not exist and must not be created.
'''
CYCLE020_GRADE_AGENT_ESCAPE_OUTCOME='''---
schema_version: "1.2"
id: "T-20260611-042208-1870ceb1"
title: "M6 Grade Agent + Critic — independent verdict + structured grade_result"
goal: "Implement the symphony-grade crate: an independent, read-only Grade Agent that verifies vendor output via command / artifact / llm_judge / manual_review paths, enforces the high-risk second-signal gate, runs the Grade critic, and exposes a symphony grade CLI subcommand."
risk_level: medium
non_goals:
  - "Do NOT read or write .symphony/memory-user/, .symphony/patterns-user/, or .symphony/patterns-imported/ (R-AGT-6 P0); Grade is read-only over source and may only read its own run dir + git"
context_pointers:
  - "docs/agents/grade/AGENT.md"
  - "docs/agents/shape/AGENT.md"
  - "crates/symphony-shape/src/lib.rs"
assumptions:
  - "The high-risk second-signal gate (D-P13) is exercised from outcome.high_risk_actions[]: any acceptance whose high_risk_action_id is non-null requires both deterministic_check_passed AND llm_judge_passed."
output_contract:
  artifacts:
    - type: file_set
      paths:
        - "crates/symphony-grade/src/lib.rs"
        - "crates/symphony-grade/src/result.rs"
        - "crates/symphony-grade/src/paths.rs"
        - "crates/symphony-grade/src/critic.rs"
        - "apps/symphony/src/main.rs"
  target: pr
acceptance:
  - id: a10
    severity: P0
    text: "high-risk second-signal gate is enforced: a high_risk_action_id acceptance with only deterministic_check_passed (llm_judge_passed=false) yields verdict fail"
  - id: adv1
    severity: P1
    text: "A command-type acceptance whose command exceeds timeout_sec is fail-closed and reaped with no orphaned/hung process"
  - id: adv7
    severity: P0
    text: "Grade does not read or write memory-user/, patterns-user/, or patterns-imported/ and outcome.md byte content is unchanged after grading"
---

## Background
B-020 follows Shape (M4/B-019) and Conduct (M5/B-018). These Shape references are
cross-references only: docs/agents/shape/AGENT.md and symphony-shape are not the
primary deliverable for this cycle.
'''
CYCLE020_GRADE_AGENT_ESCAPE_GRADE='''# Grade — cycle-020 / B-020 — round 1 (fix-round)

Task: **B-020 M6 Grade Agent + Critic — independent verdict + structured grade_result** (type=code, risk_level=medium)

Independent verification covered `crates/symphony-grade`; this Grade text also cross-references
docs/agents/shape/AGENT.md and symphony-shape only as prior-stage context.

```yaml
grade_summary:
  verdict: pass
  p0_count: 0
  p1_count: 0
  adversarial_p0_count: 0
  adversarial_p1_count: 0
  p2_count: 0
```

```yaml
acceptance_status:
  - id: a10
    status: pass
  - id: adv1
    status: pass
  - id: adv7
    status: pass
```

```yaml
spec_compliance_matrix:
  - acceptance_id: a10
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/decisions/product.md"
    evidence_ref: "high_risk_second_signal_incomplete_fails_grade 1 passed"
  - acceptance_id: adv1
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md"
    evidence_ref: "command_timeout_fails_and_reaps 1 passed ~1.04s; bounded timeout; process_group(0) on spawn + negative-pgid SIGTERM/SIGKILL wait/reap"
  - acceptance_id: adv7
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/ops/risks.md"
    evidence_ref: "read_only_isolation_does_not_touch_forbidden_dirs 1 passed"
```

```yaml
negative_regression_tests:
  - acceptance_id: a10
    severity_if_fail: P0
    status: pass
    scenario: "high_risk_action with only deterministic_check_passed yields verdict fail; incomplete second signal fails grade"
    evidence_kind: schema_validation_test
    evidence_ref: "high_risk_second_signal_incomplete_fails_grade 1 passed"
  - acceptance_id: adv1
    severity_if_fail: P1
    status: pass
    scenario: "command-type acceptance exceeding timeout_sec is marked fail and the whole process group is reaped, no orphan grandchild, no hang"
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "command_timeout_fails_and_reaps 1 passed ~1.04s; bounded timeout; process_group(0) + terminate_process_group/kill_process_group + child.wait"
  - acceptance_id: adv7
    severity_if_fail: P0
    status: pass
    scenario: "grade run leaves outcome byte-identical before and after and never creates the forbidden memory or patterns dirs"
    evidence_kind: schema_validation_test
    evidence_ref: "read_only_isolation_does_not_touch_forbidden_dirs 1 passed"
```

```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "The Grade agent performs no authentication and handles no secrets."
  scope_basis_ref: "outcome.md risk_surface.auth_or_secret not_applicable with reason"
```

```yaml
dependency_spec_review:
  - status: pass
    spec_ref: "docs/architecture/tech-stack.yaml and workspace Cargo.toml"
    evidence_ref: "crates/symphony-grade/Cargo.toml uses serde, serde_json, serde_yaml_bw, thiserror, time, symphony-storage all .workspace = true"
```

```yaml
adversarial_checks:
  - id: adv1
    acceptance_id: adv1
    status: pass
    severity_if_fail: P1
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "command_timeout_fails_and_reaps 1 passed ~1.04s (fix-round 1)"
    note: "The command path now spawns sh -c with process_group(0); on Duration timeout it sends SIGTERM to the negative pgid, waits a 250ms grace, then SIGKILL the group, then reaps via child.wait. A backgrounded grandchild can no longer orphan."
  - id: adv7
    acceptance_id: adv7
    status: pass
    severity_if_fail: P0
    evidence_kind: schema_validation_test
    evidence_ref: "read_only_isolation_does_not_touch_forbidden_dirs 1 passed"
    note: "read-only isolation: outcome.md is byte-identical before and after; forbidden dirs never created"
```

```yaml
trust_surface_inventory:
  external_subprocess:
    trusted_by: "bounded timeout plus child reap, no orphan, adv1"
    status: pass
  runtime_files:
    trusted_by: "writes confined to the run dir, run-id validated, no source or outcome mutation, adv7"
    status: pass
  unverified_items: []
```

```yaml
deferred_claims: []
```

## Notes

- **High-risk second signal** (D-P13 P0): `high_risk_second_signal_incomplete_fails_grade`
  proves an incomplete second signal fails the grade.
- **Structured verdict, no naked verdict** (D-P16 P0): per-acceptance `trace_ref` +
  `evidence_refs` + resolvable reasoning anchors are enforced by the schema.
- **Grade critic**: `check_critic.py` found an approved verdict and 5 per-rule findings.
- **Read-only isolation** (R-AGT-6 P0): outcome.md is byte-stable and forbidden dirs are
  never created.
'''
CYCLE021_EVOLVE_AGENT_ESCAPE_OUTCOME='''---
schema_version: "1.2"
id: "T-20260611-072700-b021e7c1"
title: "M7 Evolve Agent (Layer-2) — L0.5 memory + grade-gated candidates + revert-aware writes"
goal: "Implement the symphony-evolve crate: L0.5 lightweight-memory inline writer (daemon main thread), the Evolve batch processor that generates L1 memory candidates only from grade-pass runs (negative_reflection only from grade-fail runs), full D-P21 metadata before write, the .evolve.lock advisory-lock IPC + storage marker layout, git-commit-with-revert-footer for every accepted write, and a revert-history check that suppresses user-reverted candidates; expose symphony evolve CLI subcommand."
risk_level: medium
non_goals:
  - "Do NOT write any memory/pattern artifact without complete D-P21 metadata (RL-10) and do NOT write any artifact without a git commit carrying source + revert footer (D-T1 / D-P24 / RL-11)"
  - "Do NOT run Evolve inline at the grade_completed event — that is the daemon main-thread L0.5 inline write; the Evolve batch is scheduler-triggered"
context_pointers:
  - "docs/agents/evolve/AGENT.md"
  - "docs/architecture/schemas/lightweight-memory.md"
  - "docs/architecture/schemas/evolve-log.md"
output_contract:
  artifacts:
    - type: file_set
      paths:
        - "crates/symphony-evolve/src/lib.rs"
        - "crates/symphony-evolve/src/lightweight.rs"
        - "crates/symphony-evolve/src/critic.rs"
        - "crates/symphony-evolve/src/git_write.rs"
        - "apps/symphony/src/main.rs"
  target: pr
---

## Background
This cycle's primary deliverable is the M7 Evolve Agent and the `symphony evolve` CLI.
'''
CYCLE021_EVOLVE_AGENT_ESCAPE_GRADE='''# Grade Round 2 — B-021 M7 Evolve Agent (Layer-2)

Task type: code · risk_level: medium · round: 2

The delta is materially complete and the non-git surfaces all pass: D-P21 metadata
completeness, the evolve-critic and mechanical pre-filter pass, the evolve-log artifact
is atomically written, and L0.5 lightweight-memory writes the Recent Runs line.

```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```

```yaml
acceptance_status:
  - id: a4
    status: pass
  - id: a6
    status: pass
  - id: a9
    status: pass
  - id: a12
    status: pass
```

```yaml
spec_compliance_matrix:
  - acceptance_id: a4
    spec_ref: "docs/architecture/schemas/lightweight-memory.md"
    evidence_ref: "src/lightweight.rs lightweight_memory_inline_write_recent_runs_only (PASS); placement-only check proves MEMORY.md Recent Runs section receives the digest narrative"
    status: pass
    severity_if_fail: P1
  - acceptance_id: a6
    spec_ref: "docs/decisions/product.md D-P21"
    evidence_ref: "src/lib.rs incomplete_metadata_rejected_before_write + metadata_complete_rejects_missing_fields (PASS); pre-write in-memory candidate metadata includes source_run_id, validation, owner_scope, revert_hint, and commit_hash: pending"
    status: pass
    severity_if_fail: P0
  - acceptance_id: a9
    spec_ref: "docs/agents/evolve/AGENT.md; docs/architecture/schemas/evolve-log.md"
    evidence_ref: "dogfood_batch_end_to_end writes >=1 memory fact and records a git commit for that fact; evolve-log atomic-write smoke reviewed as a non-git surface"
    status: pass
    severity_if_fail: P1
  - acceptance_id: a12
    spec_ref: "docs/agents/evolve/AGENT.md critic + mechanical_pre_filter"
    evidence_ref: "mechanical pre-filter length/risk/path-only smoke; in-process evolve-critic returns approved for the batch"
    status: pass
    severity_if_fail: P1
```

```yaml
negative_regression_tests:
  - acceptance_id: a6
    scenario: "Candidate missing any D-P21 metadata field is rejected before write/commit"
    evidence_ref: "src/lib.rs incomplete_metadata_rejected_before_write (PASS)"
    status: pass
    severity_if_fail: P0
```

```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "symphony-evolve handles run traces / grade verdicts / memory candidates; it has no auth/secret/token/API-key surface."
```

```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "fixture focuses on Evolve evidence completeness, not dependency changes"
```
'''
CYCLE022_FRONTEND_ESCAPE_OUTCOME='''---
schema_version: "1.2"
title: "UI-M0 Contract substrate — Tauri/React scaffold + SSE/SWR + If-Match client"
goal: "Create the UI-M0 contract substrate at apps/symphony-ui: a Tauri 2 + React 19 + TypeScript 6 + Vite 8 + Zustand scaffold whose TypeScript client substrate implements an SSE invalidation subscriber over an injectable native-EventSource factory with a 30s heartbeat watchdog and the DA-30 SWR-on-reconnect contract."
output_contract:
  artifacts:
    - type: file_set
      paths:
        - "apps/symphony-ui/package.json"
        - "apps/symphony-ui/vite.config.ts"
        - "apps/symphony-ui/src/App.tsx"
        - "apps/symphony-ui/src/lib/sse/connection.ts"
  target: pr
acceptance:
  - id: a8
    text: "SSE subscriber + SWR-on-reconnect ('sse-reconnect' + 'swr-snapshot' describe blocks, fake timers): heartbeat gap > 30s transitions the connection store to reconnecting WITHOUT clearing the snapshot store; writesDisabled becomes true; reconnect triggers exactly one full GET /api/v1/state refresh that REPLACES (never blanks) the snapshot; failure persisting past 60s transitions to degraded; X-Symphony-Instance-Id / connected-event instance mismatch is treated as a disconnect trigger."
    type: command
    command: "cd apps/symphony-ui && pnpm run test -- -t 'sse-reconnect|swr-snapshot'"
risk_surface:
  surfaces:
    identity_sentinel:
      present: true
      note: "X-Symphony-Instance-Id mismatch (HTTP header or SSE connected event) signals a stale daemon; the substrate must treat it as a disconnect trigger, retain the snapshot, and never silently keep writing against the stale identity."
adversarial_acceptance:
  - id: adv6
    text: "Stale-identity sentinel: a changed X-Symphony-Instance-Id on an HTTP response header or a different instance id in a subsequent SSE connected event forces the connection store into reconnecting (stale-daemon path), retains the snapshot, and blocks further writes until a fresh identity is observed; the mismatch is never silently accepted."
    severity: P1
    surface: identity_sentinel
    type: command
    command: "cd apps/symphony-ui && pnpm run test -- -t instance-mismatch"
    evidence_kind: schema_validation_test
    verification_hint: "vitest 'instance-mismatch' tests deliver a mismatched instance id via mocked response headers and via a second connected event; assert reconnecting transition + writesDisabled + snapshot retained."
---
'''
CYCLE022_FRONTEND_ESCAPE_GRADE='''# Grade round 3 — cycle-022 / B-022 (UI-M0 Contract substrate) — PASS

```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
  adversarial_p0_count: 0
  adversarial_p1_count: 0
```
```yaml
acceptance_status:
  - id: a8
    status: pass
    severity: null
    evidence: "evidence/grade/r2_a8_sse_swr.log + r3_vitest.log — 31s heartbeat gap → reconnecting + writesDisabled with snapshot retained; 61s → degraded; reconnect triggers exactly one GET /api/v1/state refresh that replaces (never blanks) the snapshot; instance mismatch treated as disconnect"
```
```yaml
spec_compliance_matrix:
  - acceptance_id: a8
    spec_refs: ["docs/architecture/api-contract.md §3.4/§3.4.3 (DA-30/DA-31)"]
    evidence_ref: "evidence/grade/r2_a8_sse_swr.log + r3_vitest.log"
    status: pass
    severity_if_fail: P1
```
```yaml
negative_regression_tests:
  - acceptance_id: a8
    scenario: "heartbeat gap >30s → reconnecting + writesDisabled with snapshot retained; 60s+ → degraded; reconnect replaces (never blanks) snapshot; malformed SSE keeps subscriber alive; instance mismatch → disconnect"
    evidence_ref: "evidence/grade/r2_a8_sse_swr.log + r2_adv6_mismatch.log + r3_vitest.log"
    status: pass
    severity_if_fail: P1
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "frontend escape fixture does not exercise auth-token surfaces"
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "fixture focuses on frontend evidence completeness, not dependency changes"
```
```yaml
adversarial_checks:
  - id: adv6
    acceptance_id: adv6
    statement: "Stale-identity sentinel: instance-id mismatch forces reconnecting, retains snapshot, blocks writes"
    surface: identity_sentinel
    evidence_kind: schema_validation_test
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/r2_adv6_mismatch.log + r3_vitest.log + Rust instance-header mismatch typed error (a2 log)"
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
'''
CYCLE022_RUST_ONLY_REQUEST_TARGET_OUTCOME='''---
title: "crates/symphony-client request-target validation"
goal: "Add a Rust-only generic loopback request API with request-target delimiter and control-character validation in crates/symphony-client."
output_contract:
  artifacts:
    - type: file_set
      paths:
        - "crates/symphony-client/src/lib.rs"
acceptance:
  - id: CLIENT-REQUEST-TARGET
    severity: P1
    statement: >
      The client builds a raw HTTP/1.1 request target from a user-controlled path segment.
      It must percent-encode or reject request-target delimiters and control characters.
---
'''
FRONTEND_DEP_OUTCOME='''---
schema_version: "1.2"
title: "UI-M0 React/Vite dependency substrate"
goal: "Ship the apps/symphony-ui package manifest aligned to docs/architecture/tech-stack.yaml frontend_locked."
output_contract:
  artifacts:
    - type: file_set
      paths:
        - "apps/symphony-ui/package.json"
        - "apps/symphony-ui/pnpm-lock.yaml"
        - "apps/symphony-ui/vite.config.ts"
        - "apps/symphony-ui/src/App.tsx"
acceptance:
  - id: deps
    severity: P1
    text: "Frontend package versions follow docs/architecture/tech-stack.yaml frontend_locked."
---
'''
FRONTEND_DEP_GRADE='''# Grade — UI-M0 dependency fixture
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: deps, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: deps
    status: pass
    severity_if_fail: P1
    spec_ref: docs/architecture/tech-stack.yaml frontend_locked
    evidence_ref: apps/symphony-ui/package.json + apps/symphony-ui/pnpm-lock.yaml
```
```yaml
negative_regression_tests:
  - acceptance_id: deps
    status: pass
    severity_if_fail: P1
    scenario: manifest and lockfile are checked against frontend_locked
    evidence_ref: apps/symphony-ui/pnpm-lock.yaml
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: dependency fixture does not touch secrets
```
```yaml
dependency_spec_review:
  - dependency: "react ^19.2.6 / typescript ~6.0.3 / vite ^8.0.14 / @tauri-apps/cli ^2.11.2 / pnpm packageManager pin"
    declared: "(as listed)"
    spec_ref: "docs/architecture/tech-stack.yaml frontend_locked"
    evidence_ref: "apps/symphony-ui/package.json + apps/symphony-ui/pnpm-lock.yaml"
    status: pass
    severity_if_fail: P1
```
'''
FRONTEND_NEGATED_RECONNECT_OUTCOME='''---
schema_version: "1.2"
title: "UI-M0 React package-only scaffold"
goal: "Create apps/symphony-ui/package.json for React/Vite only."
output_contract:
  artifacts:
    - type: file_set
      paths:
        - "apps/symphony-ui/package.json"
acceptance:
  - id: no-sse
    severity: P1
    text: "SSE/EventSource reconnect is not applicable: no reconnect required for this package-only change."
---
'''
FRONTEND_NEGATED_RECONNECT_GRADE=FRONTEND_DEP_GRADE.replace('id: deps','id: no-sse').replace('acceptance_id: deps','acceptance_id: no-sse').replace(
    'manifest and lockfile are checked against frontend_locked',
    'no reconnect required (not applicable: no old-source close, no second EventSource, no full GET refresh)'
)
CYCLE023_UI_M1_OUTCOME_EXCERPT='''---
schema_version: "1.2"
title: "UI-M1 App shell — project rail + run list + inspector + core states"
goal: "Build the UI-M1 app shell inside the existing apps/symphony-ui scaffold: the design-brief §4 four-region layout (conditional Attention Shelf + left Rail + center Outcome Ledger + right Inspector), themed with the native warm-dark token set, driven by a new Zustand shell store, and rendering the three core states (empty / loading / error) from the B-022 contract substrate."
risk_level: low
non_goals:
  - "No SSE behavior changes, no reconnect/If-Match logic changes — the B-022 substrate is consumed as-is and substrate unchanged."
acceptance:
  - id: a2
    text: "Four-region shell: AppShell renders Rail (aria-label 'Rail'), Outcome Ledger (aria-label 'Outcome Ledger'), Inspector (aria-label 'Inspector') always; the Attention Shelf (aria-label 'Attention Shelf', copy '<N> tasks need you') renders when the snapshot has >=1 run with blocking_on_user true and is completely absent at 0 blocking runs. RTL tests assert both shelf branches ('shell-layout' describe block)."
    type: command
  - id: a3
    text: "Contract-true state types: shell rendering reads only api-contract §3.1 fields; derive.ts maps pellet/blocking/heartbeat derivation including a terminal-done run rendering ✶✓ ⌬✓ ⚖✓."
    type: command
  - id: a4
    text: "Three core states render without runtime errors: loading = initial GET /api/v1/state still in flight with no snapshot yet rendering skeleton placeholders in Ledger + Inspector; empty = resolved snapshot with zero workspaces/runs; error = rejected initial fetch rendering 'GET /api/v1/state failed: <reason>' with a Retry button."
    type: command
  - id: a6
    text: "Ledger run list: each run renders three phase pellets (✶/⌬/⚖ with ✓/▸/○), title, micro-stage subtitle, blocking chip, and heartbeat dot; within a project section cards sort blocking → running (by heartbeat_age_sec ascending) → done."
    type: command
  - id: a7
    text: "Inspector + selection: on first snapshot the Inspector auto-selects blocking > running-by-heartbeat > most-recent run and shows header plus workspace path; clicking another run card updates the shell store and the Inspector."
    type: command
---
'''
CYCLE023_UI_M1_GRADE_EXCERPT='''# Grade round 2 — B-023 UI-M1 App shell (cycle-023, after fix round 2) — PASS

Round-2 battery: vitest exit 0: 31/31 pass (3 files); typecheck exit 0; build exit 0.

```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```

```yaml
acceptance_status:
  - id: a2
    status: pass
    severity: null
  - id: a3
    status: pass
    severity: null
  - id: a4
    status: pass
    severity: null
  - id: a6
    status: pass
    severity: null
  - id: a7
    status: pass
    severity: null
```

```yaml
spec_compliance_matrix:
  - acceptance_id: a2
    spec_refs: ["docs/ux/design-brief.md §4.1 + §4.6"]
    evidence_ref: "evidence/grade/r2_vitest_verbose.log ('shell-layout' pass: Rail/Outcome Ledger/Inspector landmarks always rendered; Attention Shelf '1 tasks need you' with one blocking run and ABSENT at zero blocking)"
    status: pass
    severity_if_fail: P1
  - acceptance_id: a3
    spec_refs: ["docs/architecture/api-contract.md §3.1"]
    evidence_ref: "src/lib/api/client.ts diff vs 0a600b9 (type-only widening to §3.1 workspaces/runs fields, no runtime statements, no invented fields) + 'derive' test pass (✶✓⌬✓⚖✓ terminal mapping, blocking>running-by-heartbeat>done ordering, 'conduct.vendor_working · 8m' label)"
    status: pass
    severity_if_fail: P1
  - acceptance_id: a4
    spec_refs: ["docs/ops/roadmap.md §3.7 exit condition", "docs/ux/design-brief.md §6.1"]
    evidence_ref: "evidence/grade/r2_vitest_verbose.log ('core-states' PASS: loading skeletons, §6.1 empty state with 'No workspaces yet.' + 'Add workspace…' CTA + skeleton preview, AA-6 error copy 'GET /api/v1/state failed: port unavailable' + Retry re-invocation + recovery, console.error spy clean)"
    status: pass
    severity_if_fail: P1
  - acceptance_id: a6
    spec_refs: ["docs/ux/design-brief.md §4.4", "docs/architecture/api-contract.md §3.1"]
    evidence_ref: "evidence/grade/r2_vitest_verbose.log ('ledger' pass: workspace grouping header name+path, blocking→running→done card order, pellets, 'Needs you' chip, heartbeat dots)"
    status: pass
    severity_if_fail: P1
  - acceptance_id: a7
    spec_refs: ["docs/ux/design-brief.md §4.5 + §6.4 (UX-48)"]
    evidence_ref: "evidence/grade/r2_vitest_verbose.log ('inspector' 2 tests pass: auto-select blocking run header/iteration/stage; manual selection updates inspector + .selected class; skeleton preview names+metadata only with permanent disclosure line and negative content assertion)"
    status: pass
    severity_if_fail: P1
```

```yaml
negative_regression_tests:
  - acceptance_id: a2
    scenario: "Attention Shelf asserted ABSENT at 0 blocking runs (queryByLabelText negative branch after rerender)"
    evidence_ref: "evidence/grade/r2_vitest_verbose.log ('shell-layout' pass)"
    status: pass
    severity_if_fail: P1
  - acceptance_id: a3
    scenario: "terminal-done run maps to all-✓ pellets; done run with newest last_event_ts still sorts last (exact order array equality)"
    evidence_ref: "evidence/grade/r2_vitest_verbose.log ('derive' pass)"
    status: pass
    severity_if_fail: P1
  - acceptance_id: a4
    scenario: "REJECTED initial fetch renders AA-6 copy naming the failed call, Retry re-invokes fetch (mock call-count 1→2), recovery to empty state, console.error spy clean throughout"
    evidence_ref: "evidence/grade/r2_vitest_verbose.log ('core-states' pass)"
    status: pass
    severity_if_fail: P1
  - acceptance_id: a6
    scenario: "blocking card sorts first despite fresher events on running runs; mis-sort fails exact textContent equality"
    evidence_ref: "evidence/grade/r2_vitest_verbose.log ('ledger' pass)"
    status: pass
    severity_if_fail: P1
  - acceptance_id: a7
    scenario: "UX-48 negative: skeleton preview markup asserted to NOT contain file body text; all-pending placeholders are italic angle-bracket names"
    evidence_ref: "evidence/grade/r2_vitest_verbose.log ('inspector' zero-task test pass)"
    status: pass
    severity_if_fail: P1
```

```yaml
secret_leakage_audit:
  status: pass
  checked_surfaces:
    - "shell error copy"
    - "shell rendered output"
  evidence_ref: "evidence/grade/r0_secret_grep.log + evidence/grade/r2_vitest_verbose.log"
  cleartext_secret_probe: not_applicable
```

```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "fixture focuses on cycle-023 frontend evidence facets, not dependency changes"
```
'''
CYCLE023_UI_M1_SATISFIED_GRADE=CYCLE023_UI_M1_GRADE_EXCERPT + '''

Additional deterministic evidence facets:
- Terminal state enum coverage: run terminal states done, failed, superseded, canceled, parked, needs_human are all tested for bucket classification.
- During DA-30 retry/degraded loading, the existing snapshot remains rendered in Ledger and Inspector state regions as last-known state.
- Inspector state region renders NEEDS YOU callout panel for blocking runs.
- Inspector state region renders RUN IN FLIGHT tile panel for running runs.
- Attention Shelf action buttons expose jump to first action and show all action.
- Phase pellets include visible labels Shape, Conduct, Grade in the verbose Inspector context.
- Loading/error panels are scoped to initial load with no prior snapshot and are not replacements for last-known Ledger/Inspector state.
'''
FRONTEND_NEGATED_CYCLE023_FACET_OUTCOME='''---
schema_version: "1.2"
title: "UI-M1 App shell negated facet fixture"
goal: "Frontend AppShell package row only."
acceptance:
  - id: n1
    severity: P1
    text: "No terminal classification required; no DA-30 retry snapshot display required; no Inspector §4.5 or Attention Shelf §4.6 or phase pellet evidence required."
---
'''
FRONTEND_NEGATED_CYCLE023_FACET_GRADE='''# Grade — UI-M1 negated cycle-023 facet fixture
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: n1, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: n1
    status: pass
    severity_if_fail: P1
    spec_ref: docs/ux/design-brief.md
    evidence_ref: "No terminal classification required; no DA-30 retry snapshot display required; no Inspector §4.5 or Attention Shelf §4.6 or phase pellet evidence required."
```
```yaml
negative_regression_tests:
  - acceptance_id: n1
    status: pass
    severity_if_fail: P1
    scenario: "no terminal classification required; no retry snapshot display required; no source affordance facet required"
    evidence_ref: "negated phrasing fixture"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "negated frontend facet fixture does not touch secrets"
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "no dependency changes in this fixture"
```
'''
CYCLE024_UI_M2_OUTCOME_EXCERPT='''---
schema_version: "1.2"
title: "UI-M2 Task create + Shape Q&A — create modal + awaiting-QA panel + persona selector"
goal: "Build the UI-M2 task-create and Shape Q&A surfaces inside the existing apps/symphony-ui app shell: create-task surfaces wired to POST /api/v1/tasks/commands/create with the api-contract §4.0 PESSIMISTIC pattern; Advanced vendor row expanding to vendor / model / reasoning_effort / persona; Shape awaiting-QA Inspector panel; submission via POST /runs/{id}/commands/answer-qa; after a 202 the run-detail refetch renders the merged outcome draft so 'user answers Shape questions from the UI and the outcome draft updates' is proven end-to-end with mocked transports; client.run(runId) plus an injectable ShapeQaProvider seam for question bodies; the default provider returns null and tests drive the panel through fixture providers."
risk_level: low
acceptance:
  - id: a3
    text: "Advanced vendor row (UX-45 fields; storage-layout §2.6): the Vendor row renders collapsed by default with honest inherit copy (no concrete vendor name is fabricated); clicking 'Advanced' expands exactly four labeled controls — Vendor (inherit | codex | claude-code), Model (inherit | free text), Reasoning effort (inherit | low | medium | high), and Persona labeled as Shape-only offering EXACTLY the V1 personas 'default' and 'socratic-skeptic' with 'default' preselected (manifest persona_default) plus cascade hint copy noting user-set values resolve via the 4-layer cascade; persona/model/effort choices update UI state and the composer summary ('advanced-row' describe block)."
  - id: a4
    text: "Create submission is contract-true PESSIMISTIC (§4.0/§4.1): Start Shape issues POST /api/v1/tasks/commands/create whose JSON body contains user_one_liner + workspace, contains vendor ONLY when a non-inherit vendor was explicitly chosen, and NEVER contains model/reasoning_effort/persona keys or any key outside §4.1 (negative assertion on the captured request); the request carries no If-Match header; while in flight the composer's own controls are disabled with in-flight copy but the rest of the shell stays interactive (a Rail view button still responds); on 202 {run_id, revision} the shell refetches state, the new run's card renders in the Ledger and is selected in the Inspector; on failure the composer retains its text and shows inline error copy naming the call ('POST /api/v1/tasks/commands/create failed: <reason>') with a resubmit affordance that re-issues the command (asserted via mock call count); no global blocking overlay is ever rendered ('create-flow' describe block)."
  - id: a5
    text: "Awaiting-QA typeform panel (design-brief §7.1.2; ui_contract qa_style): when the selected run has macro_stage=shape + micro_stage=awaiting_qa the Inspector renders the Q&A panel with a progress header 'Question N of M'; already-answered questions render as collapsed rows; the current question renders expanded with its single-select choice list, [Skip this question], and [Next]; not-yet-asked questions render as placeholder rows."
  - id: a7
    text: "Answer submission is contract-true OPTIMISTIC-SAFE and the outcome draft updates (§4.0/§4.2; roadmap §3.8 exit): completing the final question issues POST /api/v1/runs/{run_id}/commands/answer-qa whose body is exactly {answers: [...], skipped: [...]} where each answers row is {question_id, answer_type, value}; on 202 the run detail is refetched and the Inspector's outcome draft module renders content from the merged outcome_capsule returned by the (mocked) §3.2 response — asserting the draft text visibly changed from the pre-answer capsule ('qa-submit' describe block)."
  - id: a8
    text: "Contract-true client seams: client.run(runId) GETs /api/v1/runs/{encoded id}; question bodies enter the panel ONLY via the injectable ShapeQaProvider seam — the default provider returns null and the panel then renders the §3.2 counts plus an honest unavailable line naming shape_session.md; a negative test asserts production source contains no hardcoded question fixture text ('run-detail' describe block)."
---
'''
CYCLE024_UI_M2_GRADE_EXCERPT='''# Grade Round 2 — B-024 UI-M2 Task create + Shape Q&A (cycle-024)

All 11 shaped acceptance rows now pass, including both milestone exits: a4 (contract-true PESSIMISTIC create with §4.1-only body, scoped disable, refetch + select, inline AA-6 failure + resubmit, no global overlay) and a7 (§4.2 exact-body optimistic submit, rollback on failure preserving answers, merged outcome draft rendered after refetch — roadmap §3.8 'user answers Shape questions from the UI and the outcome draft updates').

```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: a3
    status: pass
  - id: a4
    status: pass
  - id: a5
    status: pass
  - id: a7
    status: pass
  - id: a8
    status: pass
```
```yaml
spec_compliance_matrix:
  - acceptance_id: a3
    spec_refs: ["docs/agents/shape/AGENT.md §3 runtime.prompts.available_personas + persona_default", "docs/architecture/storage-layout.md §2.6 4-layer cascade"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_2.log advanced-row PASS: collapsed honest-inherit summary; Advanced expands exactly Vendor/Model/Reasoning effort/Persona; persona labeled 'Persona · Shape-only' with options exactly [default, socratic-skeptic], default preselected; 4-layer cascade hint copy; selections update UI state + summary"
  - acceptance_id: a4
    spec_refs: ["docs/architecture/api-contract.md §4.0 create=PESSIMISTIC no If-Match", "docs/architecture/api-contract.md §4.1"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_2.log create-flow both tests PASS: POST /api/v1/tasks/commands/create with exactly {user_one_liner, workspace, vendor(only when non-inherit)}; stringified body contains no model/reasoning/persona; no If-Match; composer-scoped disable with 'Starting Shape…' while Rail stays interactive; 202 → state refetch → 'Created task' card selected; failure retains text + 'POST /api/v1/tasks/commands/create failed: transport down' + resubmit re-issues (3 calls); no .global-blocking-overlay"
  - acceptance_id: a5
    spec_refs: ["docs/ux/design-brief.md §7.1.2", "docs/agents/shape/AGENT.md §6 ui_contract qa_style"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_2.log qa-panel PASS: 'Question N of M' heading advances on answer and on skip; answered rows collapse with summary + Edit; placeholder rows for unasked; Skip + Next affordances; critic footer hint present"
  - acceptance_id: a7
    spec_refs: ["docs/architecture/api-contract.md §4.0 answer-qa=OPTIMISTIC-SAFE", "docs/architecture/api-contract.md §4.2", "docs/ops/roadmap.md §3.8 exit condition"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_2.log qa-submit PASS: §4.2 body exactly {answers:[{question_id, answer_type, value} x5], skipped:[]} with each id once; optimistic 'Submitting answers…' disabled state before settle; rejection rolls back to editable 'Submit answers' preserving answers with alert copy naming the failed call (inline + toast); resubmit 202 → run-detail refetch → 'After answers merged' outcome draft rendered — milestone exit proven"
  - acceptance_id: a8
    spec_refs: ["docs/architecture/api-contract.md §3.2", "docs/architecture/schemas/events.md shape_qa_emitted counts-only"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_2.log run-detail PASS: GET /api/v1/runs/run%2Fid (encoded); RunDetail additive §3.2 typing; null default provider renders 'Shape question detail unavailable: shape_session.md is not yet served by the daemon.' + '0 answered · 5 total · shape_session.md'; production source scan contains no question fixture text; commandPolicy rows reused byte-identical"
```
```yaml
negative_regression_tests:
  - acceptance_id: a3
    scenario: "Persona options exactly [default, socratic-skeptic] — no free-text custom id; collapsed row fabricates no concrete vendor name"
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_2.log advanced-row PASS"
  - acceptance_id: a4
    scenario: "Negative body assertion: stringified POST body matches no /model|reasoning|persona/; no If-Match header; rejection branch retains composer text + AA-6 copy naming the call + resubmit re-issues (asserted via 3 mock calls); document contains no .global-blocking-overlay"
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_2.log create-flow PASS"
  - acceptance_id: a5
    scenario: "Unasked questions render placeholders only ('Question pending', no fabricated answers); skip records without an answer; Edit re-opens an answered row"
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_2.log qa-panel PASS"
  - acceptance_id: a7
    scenario: "Transport rejection rolls back the optimistic submit, preserves all answers, raises alert copy naming the failed call on BOTH required surfaces (inline error + toast)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_2.log qa-submit PASS"
  - acceptance_id: a8
    scenario: "Null default provider renders honest unavailable copy naming shape_session.md + contract-true counts; production source scan proves no hardcoded question fixture text"
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_2.log run-detail PASS"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "cycle-024 fixture focuses on frontend wiring honesty and pending dismissal facets"
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "no dependency changes in this fixture"
```
'''
CYCLE024_SATISFIED_GRADE=CYCLE024_UI_M2_GRADE_EXCERPT.replace(
    "evidence_ref: \"evidence/grade/pnpm_vitest_full_round_2.log create-flow both tests PASS: POST /api/v1/tasks/commands/create with exactly {user_one_liner, workspace, vendor(only when non-inherit)}; stringified body contains no model/reasoning/persona; no If-Match; composer-scoped disable with 'Starting Shape…' while Rail stays interactive; 202 → state refetch → 'Created task' card selected; failure retains text + 'POST /api/v1/tasks/commands/create failed: transport down' + resubmit re-issues (3 calls); no .global-blocking-overlay\"",
    "evidence_ref: \"evidence/grade/pnpm_vitest_full_round_2.log create-flow both tests PASS: POST /api/v1/tasks/commands/create with exactly {user_one_liner, workspace, vendor(only when non-inherit)}; client-to-handler request path client.createTask -> daemon handler /api/v1/tasks/commands/create; stringified body contains no model/reasoning/persona; no If-Match; composer-scoped disable with 'Starting Shape…' while Rail stays interactive; 202 → state refetch → 'Created task' card selected; failure retains text + 'POST /api/v1/tasks/commands/create failed: transport down' + resubmit re-issues (3 calls); while create is pending/in-flight, Escape is ignored and does not close or reset, overlay/backdrop click is ignored and does not dismiss, and route/surface change via Rail view switch is blocked and does not close or reset the composer\"",
).replace(
    "evidence_ref: \"evidence/grade/pnpm_vitest_full_round_2.log qa-panel PASS: 'Question N of M' heading advances on answer and on skip; answered rows collapse with summary + Edit; placeholder rows for unasked; Skip + Next affordances; critic footer hint present\"",
    "evidence_ref: \"evidence/grade/pnpm_vitest_full_round_2.log qa-panel PASS: 'Question N of M' heading advances on answer and on skip; answered rows collapse with summary + Edit; placeholder rows for unasked; Skip + Next affordances; critic footer hint present; Inspector state region renders NEEDS YOU callout panel and Inspector state region renders RUN IN FLIGHT tile panel\"",
).replace(
    "evidence_ref: \"evidence/grade/pnpm_vitest_full_round_2.log qa-submit PASS: §4.2 body exactly {answers:[{question_id, answer_type, value} x5], skipped:[]} with each id once; optimistic 'Submitting answers…' disabled state before settle; rejection rolls back to editable 'Submit answers' preserving answers with alert copy naming the failed call (inline + toast); resubmit 202 → run-detail refetch → 'After answers merged' outcome draft rendered — milestone exit proven\"",
    "evidence_ref: \"evidence/grade/pnpm_vitest_full_round_2.log qa-submit PASS: fixture-only until missing_upstream: B-019; §4.2 body exactly {answers:[{question_id, answer_type, value} x5], skipped:[]} with each id once; client-to-handler request path client.answerQa -> daemon handler /api/v1/runs/{id}/commands/answer-qa; handler consumes the request body answers[]; optimistic 'Submitting answers…' disabled state before settle; rejection rolls back to editable 'Submit answers' preserving answers with alert copy naming the failed call (inline + toast); resubmit 202 → daemon handler writes outcome.md and returns merged outcome_capsule via run-detail refetch → 'After answers merged' outcome draft rendered — milestone exit proven\"",
).replace(
    "evidence_ref: \"evidence/grade/pnpm_vitest_full_round_2.log run-detail PASS: GET /api/v1/runs/run%2Fid (encoded); RunDetail additive §3.2 typing; null default provider renders 'Shape question detail unavailable: shape_session.md is not yet served by the daemon.' + '0 answered · 5 total · shape_session.md'; production source scan contains no question fixture text; commandPolicy rows reused byte-identical\"",
    "evidence_ref: \"evidence/grade/pnpm_vitest_full_round_2.log run-detail PASS: fixture-only; real provider pending B-019 (unavailable state shown); production provider/default wiring: default runtime provider is wired to the unavailable B-019 null provider until the daemon serves shape_session.md; GET /api/v1/runs/run%2Fid (encoded); RunDetail additive §3.2 typing; null default provider renders 'Shape question detail unavailable: shape_session.md is not yet served by the daemon.' + '0 answered · 5 total · shape_session.md'; production source scan contains no question fixture text; commandPolicy rows reused byte-identical\"",
)
CYCLE026_NEGATIVE_FAILURE_OUTCOME_EXCERPT='''---
schema_version: "1.2"
title: "UI-M4 Tweaks panel — vendor/model/effort/persona + config source layers"
goal: "Build the UI-M4 Tweaks panel inside the existing apps/symphony-ui app shell as a read-truth runtime-preferences form."
risk_level: low
acceptance:
  - id: a6
    text: "Re-probe + load/error states (commandPolicy refresh-capability; AA copy): on mount the panel loads capabilities + config through the injected client and shows a loading state, then the loaded controls; a 'Re-probe vendors' button issues exactly one POST /api/v1/daemon/commands/refresh-capability (no If-Match) and on success refetches capabilities so the controls reflect the new probe (asserted by changing the second capabilities mock and seeing a previously-disabled vendor become enabled); when GET /api/v1/capabilities or GET /api/v1/config rejects, the panel renders an honest error line naming the failed call ('GET /api/v1/capabilities failed: <reason>') and a retry affordance that re-issues the GET — never a global spinner, never a crash ('tweaks-reprobe' describe block)."
---
'''
CYCLE026_NEGATIVE_FAILURE_GRADE_EXCERPT='''# Grade Round 1 — B-026 UI-M4 Tweaks panel (cycle-026)
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: a6
    status: pass
```
```yaml
spec_compliance_matrix:
  - acceptance_id: a6
    spec_refs: ["api-contract refresh-capability command policy", "docs/ops/contributing.md AA error copy"]
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-reprobe PASS: mount loads capabilities+config with loading state; Re-probe issues exactly one POST refresh-capability (no If-Match) then refetches (previously-disabled vendor becomes enabled on 2nd mock); GET rejection renders honest error line naming the failed call + retry affordance re-issuing the GET; no global spinner, no crash. The panel scopes its own loading/error states to its initial load only — they are local to the Tweaks panel, never the shell. The DA-30 stale-while-revalidate region behavior is owned by the B-023 shell and inherited unchanged here (shell.test.tsx is byte-frozen per a8): the existing snapshot stays rendered in the Ledger and Inspector regions during retry or degraded refresh (existing_snapshot_retained_in_regions_during_retry_or_degraded), and the shell's loading/error panels are scoped to the initial load with no prior snapshot and never replace an existing snapshot (initial_load_panels_scoped_to_no_prior_snapshot_not_replacements); both remain green in evidence/grade/pnpm_vitest_full_round_1.log (shell suite)"
```
```yaml
negative_regression_tests:
  - acceptance_id: a1
    scenario: "Seam routing negative: across capabilities()+config()+refreshCapability() the transport receives exactly [GET /api/v1/capabilities, GET /api/v1/config, POST /api/v1/daemon/commands/refresh-capability body:{}] and the POST carries no ifMatch header (sent[2].ifMatch undefined)"
    status: pass
    severity_if_fail: P1
    evidence_ref: "evidence/grade/pnpm_vitest_full_round_1.log tweaks-client PASS"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "cycle-026 fixture has no secret audit surface"
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "no dependency changes in this fixture"
```
'''
CYCLE027_SSE_MOCK_ONLY_OUTCOME_EXCERPT='''---
schema_version: "1.2"
title: "UI-M5 Conduct monitor — 5-panel harness inspector + reconnect + progress invalidation"
goal: "Conduct monitor: 5-panel harness inspector + folded chip + reconnect/degraded + progress-invalidation fetch (no SSE text)"
output_contract:
  artifacts:
    - type: file_set
      paths:
        - "apps/symphony-ui/src/conduct/ConductMonitor.tsx"
        - "apps/symphony-ui/src/conduct/conduct.test.tsx"
        - "apps/symphony-ui/src/lib/api/client.ts"
acceptance:
  - id: a3
    title: "Progress text is fetched via GET, never read from the SSE payload (DA-31)"
    severity: P1
    requirement: >
      On a state_changed{what:"progress"} invalidation, the monitor obtains the
      latest daemon_progress progress_text via SymphonyClient.runEvents(runId,
      {type:'daemon_progress'}) which issues GET /api/v1/runs/{id}/events
      ?type=daemon_progress (api-contract §3.4.2; events.md §3.6). The monitor MUST
      NOT read progress_text (or any delta) from the SSE state_changed payload — the
      SSE payload is invalidation-only and carries only {revision, changed, what}
      (api-contract §3.4 invariant). The rendered progress line shows the latest
      progress_text only.
    verification_hint: >
      Behavioral test: (1) assert the client method issues a GET to the exact path
      '/api/v1/runs/<id>/events' with query type=daemon_progress (assert on the
      transport request, the production request path — not a mock-only fixture).
      (2) Property facet: feed the monitor an SSE-shaped payload that contains a
      'progress_text' field and assert the rendered text comes ONLY from the GET
      response, never from the SSE payload (i.e. a SSE payload with a bogus
      progress_text does not appear in the DOM). (3) Parse a daemon_progress event
      with progress_text and assert it renders.
  - id: a4
    title: "Reconnect/degraded SWR wiring never clears the snapshot (DA-30)"
    severity: P1
    requirement: >
      The monitor surface reflects the existing connectionStore SSE lifecycle:
      while reconnecting it shows the reconnect badge and keeps the last-known
      Conduct snapshot rendered (never blanked to a spinner/empty), and at 60s+
      disconnect the degraded banner is shown while the snapshot stays visible
      (DA-30 SWR; api-contract §3.4.3; reuse ReconnectBadge/DegradedBanner). Write
      affordances (Cancel) are scoped-disabled while disconnected per DA-30 (no
      stale-revision writes).
    verification_hint: >
      Behavioral test driving connectionStore through connected → reconnecting →
      degraded: assert the monitor still renders the prior run/plan content in each
      non-connected state (snapshot retained, not an initial-load skeleton/empty),
      assert the reconnect badge appears in 'reconnecting' and the degraded banner
      appears in 'degraded', and assert the Cancel affordance is disabled while
      disconnected. Cover the full DA-30 retain-snapshot facet, not just the
      connected happy path.
---
# Outcome
Existing code reused: `src/lib/sse/connection.ts` (already treats
`what:"progress"` as a valid `state_changed` invalidation, line ~208).
No re-implementation of the SSE reconnect lifecycle — reuse the existing
`subscribeToInvalidations` + `connectionStore`; the monitor consumes that state.

```yaml
reference_obligations:
  - obligation_id: "DA31-PROGRESS-TEXT-VIA-GET-NOT-SSE-01"
    source_ref:
      path: "docs/architecture/api-contract.md"
      section: "§3.4 / §3.4.2"
      quote_hash: "sha256:api-contract-3.4.2-progress-get-not-sse"
    kind: "api_contract"
    must: >
      progress_text is fetched via GET /api/v1/runs/{id}/events?type=daemon_progress;
      SSE state_changed payload is invalidation-only ({revision,changed,what}) and
      MUST NOT carry progress_text. Monitor renders text from the GET response only.
    required_evidence_classes: ["behavioral_ui_test", "production_path_anchor", "enum_or_property_coverage"]
    not_sufficient: ["mock_fixture_only", "static_dom_snapshot_only"]
    status: null
  - obligation_id: "DA30-SWR-RECONNECT-RETAIN-SNAPSHOT-01"
    source_ref:
      path: "docs/architecture/api-contract.md"
      section: "§3.4.3"
      quote_hash: "sha256:api-contract-3.4.3-swr-reconnect-da30"
    kind: "ui_state_behavior"
    must: >
      On disconnect/reconnect the monitor never clears the last-known snapshot;
      reconnect badge in 'reconnecting'; degraded banner at 60s+; write
      affordances scoped-disabled while disconnected (DA-30 SWR-on-reconnect).
    required_evidence_classes: ["behavioral_ui_test", "production_path_anchor"]
    not_sufficient: ["mock_fixture_only", "static_dom_snapshot_only"]
    status: null
```
'''
CYCLE027_SSE_MOCK_ONLY_GRADE_EXCERPT='''# Grade round 1 — B-027 UI-M5 Conduct monitor (fix round)

**Task**: B-027 (type=code, risk_level=low). **Cycle**: cycle-027. **Round**: 1
(fix round for the round-0 F1/F2 findings).

- **F1 (P1, a3) RESOLVED**: `apps/symphony-ui/src/lib/api/client.ts` `runEvents()`
  now delegates to `coerceRunEvents(response.data)` which handles array → as-is,
  string → `parseNdjsonEvents`, single non-null object → `[object]`, else `[]`;
  `parseNdjsonEvents(body: unknown)` guards non-string input. The single-line
  `?type=daemon_progress` body no longer crashes. Test "fetches daemon progress
  through the production GET path and ignores progress text shaped like an SSE
  delta" passes (production GET path `/api/v1/runs/run%2F1/events?type=daemon_progress`
  asserted; the SSE `state_changed` bogus `progress_text` is NOT rendered).

```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```

```yaml
acceptance_status:
  - id: a3
    status: pass
    severity: P1
  - id: a4
    status: pass
    severity: P1
```

```yaml
spec_compliance_matrix:
  - acceptance_id: a3
    obligation_id: "DA31-PROGRESS-TEXT-VIA-GET-NOT-SSE-01"
    spec_refs: ["docs/architecture/api-contract.md#§3.4.2", "docs/architecture/schemas/events.md#§3.6"]
    severity_if_fail: P1
    status: pass
    evidence_ref: "conduct.test.tsx: runEvents issues the production GET '/api/v1/runs/run%2F1/events?type=daemon_progress' (assert on the transport request) and returns RunEvent[]; latestProgressText ignores the SSE state_changed payload and the DOM does not render the bogus SSE text; coerceRunEvents handles single-line NDJSON (F1 fixed)"
  - acceptance_id: a4
    obligation_id: "DA30-SWR-RECONNECT-RETAIN-SNAPSHOT-01"
    spec_refs: ["docs/architecture/api-contract.md#§3.4.3"]
    severity_if_fail: P1
    status: pass
    evidence_ref: "conduct.test.tsx 'retains the prior conduct snapshot while reconnecting and degraded…' green; reconnect lifecycle reused from src/lib/sse/connection.ts (unchanged)"
```

```yaml
negative_regression_tests:
  - acceptance_id: a3
    scenario: "Property facet: an SSE-shaped state_changed payload carrying a bogus progress_text must NOT render; only the GET response text renders; single-line NDJSON body must not crash"
    status: pass
    severity_if_fail: P1
    evidence_ref: "conduct.test.tsx asserts latestProgressText ignores the state_changed payload + DOM not.toHaveTextContent('SSE bogus progress must not render'); runEvents single-object body returns [event] (coerceRunEvents), no TypeError"
  - acceptance_id: a4
    scenario: "Disconnect → reconnecting → degraded keeps the prior snapshot retained and writesDisabled (Cancel disabled); the reused src/lib/sse/connection.ts closes the old source (.close()), creates a new EventSource, rejects stale old events via the generation token, and does a full GET /api/v1/state refresh after the new connection"
    status: pass
    severity_if_fail: P1
    evidence_ref: "conduct.test.tsx asserts 'Patch handler' snapshot retained in reconnecting+degraded and Cancel disabled (snapshot retained and writes disabled while disconnected); connection.ts lifecycle (old source close + new source creation + stale old events rejected + full GET /api/v1/state refresh) proven by the pre-existing src/lib/api/substrate.test.tsx (cycle-022)"
```

```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "B-027 is a read-only UI monitor; runEvents builds only a path+query (runId, type, since_seq), no secrets."
```

```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "No new third-party dependency introduced"
```
'''
FRONTEND_NEGATED_CYCLE024_FACET_OUTCOME='''---
schema_version: "1.2"
title: "UI-M2 negated fixture-honesty row"
goal: "Frontend package-only cleanup in apps/symphony-ui."
acceptance:
  - id: n1
    severity: P1
    text: "No fixture-backed production Q&A capability is accepted; answer-qa merge and outcome draft update are not in scope; no PESSIMISTIC pending-disable claim is made."
---
'''
FRONTEND_NEGATED_CYCLE024_FACET_GRADE='''# Grade — UI-M2 negated cycle-024 facet fixture
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: n1, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: n1
    status: pass
    severity_if_fail: P1
    spec_ref: docs/ux/design-brief.md
    evidence_ref: "No fixture-backed production Q&A capability accepted; no answer-qa merge claim; no PESSIMISTIC pending-disable claim."
```
```yaml
negative_regression_tests:
  - acceptance_id: n1
    status: pass
    severity_if_fail: P1
    scenario: "negated wording only; no fixture-backed runtime claim and no pending dismissal claim"
    evidence_ref: "negated cycle-024 phrasing fixture"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "negated frontend facet fixture does not touch secrets"
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "no dependency changes in this fixture"
```
'''
CYCLE025_UI_M3_OUTCOME_EXCERPT='''---
schema_version: "1.2"
title: "UI-M3 Outcome ready — render capsule + Execute with If-Match"
goal: "Build the UI-M3 Outcome-ready surfaces inside the existing apps/symphony-ui app shell: the card renders outcome-capsule.md schema-v1.2 fields including tags; capsuleModel.ts narrowing layer validates RunDetail.outcome_capsule; Execute is PESSIMISTIC with If-Match REQUIRED; Re-shape is PESSIMISTIC with If-Match REQUIRED; a 409 revision_conflict triggers refetch."
risk_level: low
acceptance:
  - id: a1
    severity: P1
    text: "capsuleModel.ts narrows outcome_capsule per outcome-capsule.md schema v1.2 and malformed rows degrade without crashing."
  - id: a7
    severity: P1
    text: "Execute issues PESSIMISTIC If-Match command and refetches after 202."
  - id: a8
    severity: P1
    text: "409 revision_conflict refetch path renders inline conflict and retries with fresh revision."
---
risk_surface:
  surfaces:
    input_validation_or_schema:
      present: true
      note: "RunDetail.outcome_capsule is untyped parsed YAML crossing the daemon→UI boundary; capsuleModel.ts must narrow per outcome-capsule.md schema v1.2."
grounding_refs:
  - "docs/ux/prototype/screens/outcome.jsx"
  - "docs/architecture/schemas/outcome-capsule.md §2.1 top-level fields including tags + schema_version + output_contract + iteration + groundings + high_risk_actions"
'''
CYCLE025_UI_M3_GRADE_EXCERPT='''# Grade round 0 — cycle-025 / B-025 (UI-M3 Outcome ready — render capsule + Execute with If-Match)

Verdict: FAIL — blocking P1 rows remain.

```yaml
grade_summary: {p0_count: 0, p1_count: 3, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: a1, status: fail, severity: P1}
  - {id: a7, status: fail, severity: P1}
  - {id: a8, status: fail, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: a1
    status: fail
    severity_if_fail: P1
    spec_refs: ["docs/architecture/schemas/outcome-capsule.md §2/§3/§9/§10"]
    evidence_ref: "capsule-malformed FAIL via F1; capsuleModel.ts narrows acceptance/assumptions/groundings/high_risk_actions per schema with per-row malformed degradation"
  - acceptance_id: a7
    status: fail
    severity_if_fail: P1
    spec_refs: ["docs/architecture/api-contract.md §4.0/§4.4 (DA-28)", "docs/decisions/architecture.md DA-29"]
    evidence_ref: "execute-flow FAIL; OutcomeActions.execute sends client.execute(runId, revision, {}) through the frozen commandPolicy execute row (PESSIMISTIC, ifMatch required); post-202 stage rendering re-reads refetched §3.2 truth only"
  - acceptance_id: a8
    status: fail
    severity_if_fail: P1
    spec_refs: ["docs/architecture/api-contract.md §1.2/§1.5 (DA-29 409 revision_conflict)"]
    evidence_ref: "execute-conflict FAIL; OutcomeActions.execute catches code==revision_conflict, refetches detail, renders both revisions inline, retry path re-reads currentRevision()"
```
```yaml
negative_regression_tests:
  - acceptance_id: a1
    status: fail
    severity_if_fail: P1
    scenario: "Malformed sections/rows degrade per-row without crash"
    evidence_ref: "capsule-malformed blocked"
  - acceptance_id: a7
    status: fail
    severity_if_fail: P1
    scenario: "UI never renders a conduct stage before the refetched detail reports it"
    evidence_ref: "execute-flow blocked"
  - acceptance_id: a8
    status: fail
    severity_if_fail: P1
    scenario: "One-2xx/one-409 split; no ghost conduct state between 409 and accepted retry; retry carries the fresh revision"
    evidence_ref: "execute-conflict blocked"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "fixture focuses on cycle-025 frontend facets"
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "no dependency changes in this fixture"
```
'''
CYCLE025_SATISFIED_GRADE=CYCLE025_UI_M3_GRADE_EXCERPT + '''

Additional cycle-025 hardening evidence:
- outcome capsule schema guard matrix covers schema_version, iteration, output_contract, tags controlled vocabulary plus unknown tag handling, high_risk_actions action enum deploy/delete/db_write/external_api/payment/merge_pr, groundings source_type and url/path rule, supports non-empty required, and a schema-valid fixture passes full schema.
- outcome.tags[] render evidence: tags chip row is visible and rendered; a non-empty dogfood fixture surfaces a tag chip; empty tags are hidden/absent with no blank row.
- execute command matrix: execute uses If-Match, pending scoped disable, inline error rendering, and catch failure handling/rejection coverage in the execute row.
- re-shape command matrix: re-shape uses If-Match, pending scoped disable, inline error rendering, and catch failure handling/rejection coverage in the re-shape row.
- 409 revision_conflict refetch branch: refetch failure / GET failure renders inline error, pending cleared and status reset before retry.
'''
FRONTEND_NEGATED_CYCLE025_FACET_OUTCOME='''---
schema_version: "1.2"
title: "UI-M3 negated fixture"
goal: "Frontend shell copy only."
acceptance:
  - id: n1
    severity: P1
    text: "No capsuleModel narrowing layer is in scope; no outcome.tags[] rendering obligation; no PESSIMISTIC execute or re-shape command matrix."
---
'''
FRONTEND_NEGATED_CYCLE025_FACET_GRADE='''# Grade — negated cycle-025 fixture
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: n1, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: n1
    status: pass
    severity_if_fail: P1
    spec_ref: docs/ux/design-brief.md
    evidence_ref: "No capsuleModel narrowing layer required; no outcome.tags[] rendering required; no PESSIMISTIC execute/re-shape command matrix required."
```
```yaml
negative_regression_tests:
  - acceptance_id: n1
    status: pass
    severity_if_fail: P1
    scenario: "negated phrasing only"
    evidence_ref: "no capsule schema guard, no tags render, no command matrix"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "negated fixture"
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "no dependency changes"
```
'''
# v1.4.21 backtest false_positive regression (cycle-022): a client/transport substrate names
# execute/re-shape with If-Match/PESSIMISTIC context (wrapper + commandPolicy table) but ships
# no command UI — the pessimistic-command matrix must NOT demand UI evidence there.
CYCLE022_COMMAND_SUBSTRATE_OUTCOME=CYCLE022_FRONTEND_ESCAPE_OUTCOME.replace('''adversarial_acceptance:''', '''  - id: a5
    text: "Stage-transition writes (execute/approve/re-shape/cancel) must carry If-Match; missing header in a stage-transition request is rejected client-side before any network call; stale revision surfaces the 409 revision_conflict envelope with expected_revision/current_revision/changed_since details"
    type: command
    command: "cd apps/symphony-ui && pnpm run test -- -t if-match"
adversarial_acceptance:''')
CYCLE022_COMMAND_SUBSTRATE_GRADE=CYCLE022_FRONTEND_ESCAPE_GRADE + '''

If-Match wrapper evidence (real cycle-022 grade_round_3 rows):
- "evidence/grade/r2_a5_ifmatch.log (filter exit 0) re-confirmed by r3_vitest.log full suite — stage commands always send If-Match; missing revision rejects with client_missing_revision; optional commands per contract"
- "evidence/grade/r2_a7_policy.log + r3_vitest.log — commandPolicy asserts the full api-contract §4.0 matrix incl. approve:fail confirm-required, cancel:vendor-working confirm-required, off-switch per-scope rows, If-Match required exactly on execute/approve/re-shape/cancel"
'''
REFERENCE_VALID_OUTCOME='''---
title: "UI-MX Reference source contract"
goal: "Frontend React action-state behavior from docs/ux/design-brief.md §10.11."
acceptance:
  - id: RS-A1
    severity: P1
    statement: "The referenced action button exposes its label and disabled/enabled state behavior."
---
# Outcome
```yaml
reference_obligations:
  - obligation_id: "UX-101-ACTION-STATE"
    source_ref: {path: "docs/ux/design-brief.md", section: "§10.11", quote_hash: "sha256:test"}
    kind: "ui_action_state_label"
    must: "Action button label and state behavior are demonstrated."
    required_evidence_classes: ["behavioral_ui_test"]
    not_sufficient: ["heading_present", "static_dom_snapshot_only"]
    waiver: null
```
'''
REFERENCE_VALID_GRADE='''# Grade — reference source valid fixture
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: RS-A1, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: RS-A1
    obligation_id: UX-101-ACTION-STATE
    status: pass
    severity_if_fail: P1
    spec_refs: ["docs/ux/design-brief.md §10.11"]
    evidence_ref: "src/action.test.tsx: getByRole('button', {name:/Next/}) + userEvent.click asserts disabled then enabled state assertion"
```
```yaml
negative_regression_tests:
  - acceptance_id: RS-A1
    status: pass
    severity_if_fail: P1
    scenario: "accessible-name action button does not proceed while disabled"
    evidence_ref: "src/action.test.tsx: userEvent.click disabled button keeps state unchanged"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "reference fixture has no secrets"
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "reference fixture changes no dependencies"
```
'''
REFERENCE_MISSING_BINDING_AND_CLASSES_OUTCOME=REFERENCE_VALID_OUTCOME.replace('required_evidence_classes: ["behavioral_ui_test"]\n    ', '')
REFERENCE_MISSING_BINDING_GRADE=REFERENCE_VALID_GRADE.replace('    obligation_id: UX-101-ACTION-STATE\n', '')
REFERENCE_PRODUCTION_OUTCOME=REFERENCE_VALID_OUTCOME.replace('''kind: "ui_action_state_label"
    must: "Action button label and state behavior are demonstrated."
    required_evidence_classes: ["behavioral_ui_test"]''', '''kind: "production_behavior"
    must: "The referenced production behavior is exercised through the production path."
    required_evidence_classes: ["production_path_anchor"]''')
REFERENCE_FIXTURE_ONLY_GRADE=REFERENCE_VALID_GRADE.replace(
    "src/action.test.tsx: getByRole('button', {name:/Next/}) + userEvent.click asserts disabled then enabled state assertion",
    "mocked fixture provider renders the production behavior through a provider seam only"
)
REFERENCE_FIXTURE_ONLY_BACKLOG_GRADE=REFERENCE_FIXTURE_ONLY_GRADE.replace(
    "provider seam only",
    "provider seam only; missing_upstream: B-123"
)
REFERENCE_PRODUCTION_ANCHOR_GRADE=REFERENCE_FIXTURE_ONLY_GRADE.replace(
    "provider seam only",
    "provider seam plus production_path_anchor: client-to-handler request path and handler consumes request body"
)
REFERENCE_STATIC_ONLY_GRADE=REFERENCE_VALID_GRADE.replace(
    "src/action.test.tsx: getByRole('button', {name:/Next/}) + userEvent.click asserts disabled then enabled state assertion",
    "heading and landmark present in a static DOM screenshot; data-testid exists; assert visible state"
)
REFERENCE_NARROWED_OUTCOME=REFERENCE_VALID_OUTCOME.replace('waiver: null', 'status: excluded\n    rationale: "narrowed out of current scope"')
REFERENCE_NARROWED_NULL_WAIVER_OUTCOME=REFERENCE_VALID_OUTCOME.replace('waiver: null', 'status: excluded\n    waiver: null')
REFERENCE_NARROWED_WAIVED_OUTCOME=REFERENCE_VALID_OUTCOME.replace('waiver: null', 'status: UNVERIFIED\n    scope_basis_ref: "scope note"')
REFERENCE_UNADDRESSED_OUTCOME=REFERENCE_VALID_OUTCOME.replace('''    waiver: null
```
''', '''    waiver: null
  - obligation_id: "UX-102-UNBOUND"
    source_ref: {path: "docs/ux/design-brief.md", section: "§10.12", quote_hash: "sha256:test2"}
    kind: "ui_action_state_label"
    must: "A second referenced obligation must be addressed."
    required_evidence_classes: ["behavioral_ui_test"]
    waiver: null
```
''')
REFERENCE_HISTORICAL_ONLY_OUTCOME='''---
title: "Frontend React copy cleanup"
goal: "Frontend React copy-only task with no current referenced design source."
acceptance:
  - id: HIST-A1
    severity: P1
    text: "The local copy cleanup is verified."
---
'''
REFERENCE_HISTORICAL_ONLY_GRADE='''# Grade — historical prose must not trigger B2
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: HIST-A1, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: HIST-A1
    status: pass
    severity_if_fail: P1
    spec_ref: "local outcome acceptance"
    evidence_ref: "copy cleanup test passed"
```
```yaml
negative_regression_tests:
  - acceptance_id: HIST-A1
    status: pass
    severity_if_fail: P1
    scenario: "historical backtest old escape mentioned docs/ux/design-brief.md but that source is not current scope"
    evidence_ref: "copy cleanup regression passed"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "copy fixture has no secrets"
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "copy fixture changes no dependencies"
```
'''
REFERENCE_BACKEND_API_OUTCOME='''---
title: "Rust daemon API schema helper"
goal: "Backend daemon helper checks an internal API shape without frontend UI work."
context_pointers:
  - "docs/architecture/api-contract.md"
acceptance:
  - id: API-A1
    severity: P1
    text: "The backend helper validates the response envelope shape."
---
'''
REFERENCE_BACKEND_API_GRADE='''# Grade — backend api taxonomy deferred fixture
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: API-A1, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: API-A1
    status: pass
    severity_if_fail: P1
    spec_ref: "docs/architecture/api-contract.md §3"
    evidence_ref: "backend response envelope schema test passed"
```
```yaml
negative_regression_tests:
  - acceptance_id: API-A1
    status: pass
    severity_if_fail: P1
    scenario: "malformed response envelope is rejected"
    evidence_ref: "backend malformed envelope test passed"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "backend schema fixture has no secrets"
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "backend schema fixture changes no dependencies"
```
'''
REFERENCE_HOSTILE_OUTCOME=CYCLE020_GRADE_AGENT_ESCAPE_OUTCOME + '''
```yaml
reference_obligations:
  - obligation_id: "GRADE-HOSTILE-01"
    source_ref: {path: "docs/agents/grade/AGENT.md", section: "capabilities.forbidden", quote_hash: "sha256:test"}
    kind: "verifier_hostile_contract"
    must: "Grade verifier rejects hostile command/path escape fixtures."
    required_evidence_classes: ["hostile_fixture_manifest"]
    waiver: null
```
'''
REFERENCE_HOSTILE_GRADE=CYCLE020_GRADE_AGENT_ESCAPE_GRADE.replace(
    'spec_ref: "docs/agents/grade/AGENT.md"',
    'spec_ref: "docs/agents/grade/AGENT.md"\n    obligation_id: GRADE-HOSTILE-01',
    1,
)
REFERENCE_HOSTILE_IDS_OUTCOME=REFERENCE_HOSTILE_OUTCOME.replace('waiver: null', 'hostile_fixture_ids: ["cmd-write-forbidden-root", "artifact-path-traversal"]\n    waiver: null')
REFERENCE_HOSTILE_MIN_OUTCOME='''---
title: "Frontend React verifier source review"
goal: "Frontend React verification panel tracks a referenced verifier contract."
context_pointers:
  - "docs/agents/grade/AGENT.md"
acceptance:
  - id: RS-H1
    severity: P1
    text: "Referenced verifier hostile fixtures are executed and named."
---
# Outcome
```yaml
reference_obligations:
  - obligation_id: "GRADE-HOSTILE-01"
    source_ref: {path: "docs/agents/grade/AGENT.md", section: "capabilities.forbidden", quote_hash: "sha256:test"}
    kind: "verifier_hostile_contract"
    must: "Grade verifier rejects hostile command/path escape fixtures."
    required_evidence_classes: ["hostile_fixture_manifest"]
    waiver: null
```
'''
REFERENCE_HOSTILE_MIN_IDS_OUTCOME=REFERENCE_HOSTILE_MIN_OUTCOME.replace(
    'waiver: null',
    'hostile_fixture_ids: ["cmd-write-forbidden-root", "artifact-path-traversal"]\n    waiver: null'
)
REFERENCE_HOSTILE_MIN_GRADE='''# Grade — hostile fixture id shape fixture
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0}
```
```yaml
acceptance_status:
  - {id: RS-H1, status: pass, severity: P1}
```
```yaml
spec_compliance_matrix:
  - acceptance_id: RS-H1
    obligation_id: GRADE-HOSTILE-01
    status: pass
    severity_if_fail: P1
    spec_ref: "docs/agents/grade/AGENT.md"
    evidence_ref: "hostile_fixture_ids executed but not named"
```
```yaml
negative_regression_tests:
  - acceptance_id: RS-H1
    status: pass
    severity_if_fail: P1
    scenario: "hostile verifier fixture execution"
    evidence_ref: "hostile fixture regression passed"
```
```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "hostile fixture id shape fixture has no secrets"
```
```yaml
dependency_spec_review:
  - status: not_applicable
    severity_if_fail: P2
    rationale: "hostile fixture id shape fixture changes no dependencies"
```
'''
class GradeLintTests(unittest.TestCase):
    def run_lint(self,task_type='code',risk_level='medium',grade=BASIC,outcome=OUTCOME,repo_root=None):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); gf=root/'grade.md'; of=root/'outcome.md'; ef=root/'evidence'/'grade_lint_round_0.json'
            gf.write_text(textwrap.dedent(grade)); of.write_text(textwrap.dedent(outcome))
            cmd=[sys.executable,str(LINTER),'--task-type',task_type,'--risk-level',risk_level,'--grade-file',str(gf),'--outcome-file',str(of),'--evidence-file',str(ef)]
            if repo_root is not None:
                cmd.extend(['--repo-root',str(repo_root)])
            proc=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertTrue(proc.stdout, proc.stderr)
            self.assertTrue(ef.exists())
            return proc,json.loads(proc.stdout)

    def assert_reference_clean(self, grade, outcome):
        proc,p=self.run_lint('code','low',grade,outcome)
        self.assertEqual(proc.returncode,0,p)
        self.assertEqual(p['grade_lint']['status'],'pass',p)
        self.assertNotIn('reference_source_contract_review', '\n'.join(p['grade_lint']['errors']))
        return p

    def test_old_cycle009_happy_path_only_medium_code_fails(self):
        proc,p=self.run_lint(); self.assertEqual(proc.returncode,1); e='\n'.join(p['grade_lint']['errors']); self.assertIn('adversarial_checks',e); self.assertIn('trust_surface_inventory',e); self.assertIn('deferred_claims',e)

    def test_low_risk_docs_basic_grade_passes_without_adversarial_blocks(self):
        proc,p=self.run_lint('docs','low',BASIC,'# Outcome\n'); self.assertEqual(proc.returncode,0,p); self.assertFalse(p['grade_lint']['medium_high_code_gate'])

    def test_complete_adversarial_medium_code_grade_passes(self):
        proc,p=self.run_lint(grade=COMPLETE); self.assertEqual(proc.returncode,0,p)

    def test_current_scope_blocking_waiver_without_tracked_ref_fails(self):
        proc,p=self.run_lint(grade=WAIVER); self.assertEqual(proc.returncode,1); self.assertIn('tracked maintainer/user waiver ref','\n'.join(p['grade_lint']['errors']))

    def test_low_risk_code_requires_baseline_evidence_blocks(self):
        proc,p=self.run_lint('code','low',BASIC,LOW_CODE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('spec_compliance_matrix',errors)
        self.assertIn('negative_regression_tests',errors)
        self.assertIn('secret_leakage_audit',errors)
        self.assertIn('dependency_spec_review',errors)
        self.assertTrue(p['grade_lint']['code_baseline_gate'])
        self.assertFalse(p['grade_lint']['medium_high_code_gate'])

    def test_low_risk_code_prose_only_outcome_still_requires_baseline_blocks(self):
        proc,p=self.run_lint('code','low',BASIC,'# Outcome\n\nAcceptance: A1 must pass.\n')
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('code grade missing parseable spec_compliance_matrix block', errors)
        self.assertIn('spec_compliance_matrix missing outcome acceptance IDs: A1', errors)

    def test_low_risk_code_complete_baseline_passes(self):
        proc,p=self.run_lint('code','low',LOW_CODE_COMPLETE,LOW_CODE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_secret_leakage_audit_rejects_bare_only_probe_for_in_scope_surface(self):
        grade=LOW_CODE_COMPLETE.replace(
            "      - '{\"api_key\":\"sk-secret-test\"}'\n      - \"Authorization: Bearer sk-secret-test\"\n",
            ''
        )
        proc,p=self.run_lint('code','low',grade,AUTH_SECRET_CODE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('secret_leakage_audit.cleartext_secret_probe missing required token shapes', errors)
        self.assertIn('json_or_quoted_token', errors)
        self.assertIn('authorization_bearer', errors)

    def test_secret_leakage_audit_accepts_all_shapes_and_not_applicable(self):
        with self.subTest('all shapes'):
            proc,p=self.run_lint('code','low',LOW_CODE_COMPLETE,AUTH_SECRET_CODE_OUTCOME)
            self.assertEqual(proc.returncode,0,p)
        with self.subTest('not applicable'):
            proc,p=self.run_lint('code','low',CYCLE017_SUFFICIENT_GRADE,CYCLE017_STYLE_OUTCOME)
            self.assertEqual(proc.returncode,0,p)

    def test_cycle018_real_secret_audit_bare_pass_probe_requires_shapes(self):
        proc,p=self.run_lint('code','low',CYCLE018_SECRET_BARE_GRADE,CYCLE018_SECRET_BARE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('secret_leakage_audit.cleartext_secret_probe missing required token shapes', errors)
        self.assertIn('json_or_quoted_token', errors)
        self.assertIn('authorization_bearer', errors)

    def test_cycle017_real_not_applicable_probe_with_negated_auth_terms_does_not_require_shapes(self):
        proc,p=self.run_lint('code','low',CYCLE017_SECRET_NOT_APPLICABLE_GRADE,CYCLE017_SECRET_NOT_APPLICABLE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle018_subprocess_lifecycle_claim_requires_per_facet_evidence(self):
        proc,p=self.run_lint('code','medium',SUBPROCESS_LIFECYCLE_INSUFFICIENT_GRADE,SUBPROCESS_LIFECYCLE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertEqual(p['grade_lint']['errors'], [
            'subprocess_lifecycle[GADV-PROBE-1] missing facets: timeout,process_group,reap,stream_join — probe/stream subprocess surfaces require timeout + process-group + wait/reap (+ stream-task join) evidence'
        ])

    def test_subprocess_lifecycle_claim_passes_with_all_facets(self):
        proc,p=self.run_lint('code','medium',SUBPROCESS_LIFECYCLE_COMPLETE_GRADE,SUBPROCESS_LIFECYCLE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle009_dependency_row_process_group_rationale_does_not_trigger_subprocess_lifecycle(self):
        proc,p=self.run_lint('code','low',B001_NO_NEW_DEPS_GRADE,B001_NO_NEW_DEPS_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle013_ifmatch_cancel_endpoint_does_not_trigger_subprocess_lifecycle(self):
        proc,p=self.run_lint('code','low',B002_IFMATCH_GRADE,B002_IFMATCH_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle009_daemon_run_stop_lifecycle_rows_still_trigger_subprocess_lifecycle(self):
        proc,p=self.run_lint('code','low',B001_DAEMON_LIFECYCLE_GRADE,B001_DAEMON_LIFECYCLE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('subprocess_lifecycle[B001-DAEMON-RUN] missing facets:', errors)
        self.assertIn('subprocess_lifecycle[B001-DAEMON-STOP] missing facets:', errors)

    def test_cycle009_quality_stop_word_near_daemon_does_not_trigger_subprocess_lifecycle(self):
        """A2b fired because weak stop in daemon run/status/stop co-located with daemon; A2c deletes weak-term scoping."""
        proc,p=self.run_lint('code','low',B001_QUALITY_GRADE,B001_QUALITY_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle013_http_status_probe_does_not_trigger_subprocess_lifecycle(self):
        proc,p=self.run_lint('code','low',B002_STATUS_HTTP_PROBE_GRADE,B002_STATUS_HTTP_PROBE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle013_no_regression_kill_term_still_triggers_subprocess_lifecycle(self):
        proc,p=self.run_lint('code','low',B002_NO_REGRESSION_GRADE,B002_NO_REGRESSION_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('subprocess_lifecycle[B002-NO-REGRESSION] missing facets:', '\n'.join(p['grade_lint']['errors']))

    def test_cycle016_concurrency_spawn_appenders_does_not_trigger_subprocess_lifecycle(self):
        """A2b fired because broad spawn matched Spawn 2+ concurrent appenders; A2c treats spawn as process-action scope only."""
        proc,p=self.run_lint('code','medium',ADV_CONCURRENCY_GRADE,ADV_CONCURRENCY_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_vendor_probe_context_triggers_but_http_probe_guard_wins(self):
        proc,p=self.run_lint('code','low',VENDOR_PROBE_GRADE,VENDOR_PROBE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('subprocess_lifecycle[VENDOR-PROBE] missing facets:', '\n'.join(p['grade_lint']['errors']))
        http_outcome=VENDOR_PROBE_OUTCOME.replace('Codex capability probe invokes the vendor CLI binary via Command and checks\n      --version before use.', 'Codex capability probe checks GET /api/v1/daemon/status endpoint URL with Authorization before use.')
        proc,p=self.run_lint('code','low',VENDOR_PROBE_GRADE,http_outcome)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle016_clean_ledger_timeout_text_does_not_trigger_subprocess_lifecycle(self):
        proc,p=self.run_lint('code','low',CYCLE016_LEDGER_CLEAN_GRADE,CYCLE016_LEDGER_CLEAN_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle018_real_rpc_clear_archive_source_claim_requires_negative_path_cleanup_evidence(self):
        proc,p=self.run_lint('code','low',RPC_CLEANUP_SOURCE_ROW_GRADE,RPC_CLEANUP_SOURCE_ROW_OUTCOME)
        self.assertEqual(proc.returncode,1)
        # the real B018-A5 text carries vendor-probe strong terms, so under the A2c
        # strong-term-only scoping it legitimately fires the lifecycle obligation too
        self.assertEqual(p['grade_lint']['errors'], [
            'subprocess_lifecycle[B018-A5] missing facets: timeout,process_group,reap — probe/stream subprocess surfaces require timeout + process-group + wait/reap (+ stream-task join) evidence',
            'rpc_cleanup[B018-A5] cleanup-on-every-exit-path claimed but no timeout/error-path cleanup evidence (negative-path test required)'
        ])

    def test_cycle018_source_event_mapping_requires_per_source_evidence(self):
        proc,p=self.run_lint('code','low',EVENT_SOURCE_AGGREGATE_GRADE,EVENT_SOURCE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertEqual(p['grade_lint']['errors'], [
            'event_source[B018-A7] names required source events (result, system/init) but evidence is aggregate-only; per-source emission fixtures required'
        ])

    def test_source_event_mapping_passes_with_per_named_source_fixtures(self):
        proc,p=self.run_lint('code','low',EVENT_SOURCE_PER_SOURCE_GRADE,EVENT_SOURCE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_clean_cycle_text_without_source_event_mapping_does_not_trigger_event_source(self):
        proc,p=self.run_lint('code','low',CYCLE016_LEDGER_CLEAN_GRADE,CYCLE016_LEDGER_CLEAN_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle018_auth_status_mapping_requires_format_tolerant_evidence(self):
        proc,p=self.run_lint('code','low',AUTH_STATUS_LITERAL_ONLY_GRADE,AUTH_STATUS_MAPPING_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertEqual(p['grade_lint']['errors'], [
            'auth_status[B018-A5] login-status mapping claimed but evidence covers one literal form only; JSON-parsed or format-variant fixtures required'
        ])

    def test_auth_status_mapping_passes_with_json_parse_or_format_variants(self):
        with self.subTest('json parsed'):
            proc,p=self.run_lint('code','low',AUTH_STATUS_JSON_PARSED_GRADE,AUTH_STATUS_MAPPING_OUTCOME)
            self.assertEqual(proc.returncode,0,p)
        with self.subTest('format variants'):
            proc,p=self.run_lint('code','low',AUTH_STATUS_VARIANT_FIXTURES_GRADE,AUTH_STATUS_MAPPING_OUTCOME)
            self.assertEqual(proc.returncode,0,p)

    def test_clean_cycle_text_without_auth_status_mapping_does_not_trigger_auth_status(self):
        proc,p=self.run_lint('code','low',CYCLE016_LEDGER_CLEAN_GRADE,CYCLE016_LEDGER_CLEAN_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle019_shape_excerpt_fires_forbidden_read_schema_and_protocol_facets(self):
        proc,p=self.run_lint('code','low',CYCLE019_SHAPE_ESCAPE_GRADE,CYCLE019_SHAPE_ESCAPE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertEqual(p['grade_lint']['errors'], [
            'shape_forbidden_read_isolation_audit: Shape forbidden-read proof missing — grade proves no-writes but not no-READS of memory-user/patterns-user/patterns-imported (R-AGT-6/AGENT.md capabilities.forbidden)',
            'outcome_capsule_v12_structural_schema.assumptions: Shape schema_version 1.2 assumptions must be a list of objects with id,text,source,confirmed,risk_if_wrong',
            "outcome_capsule_v12_structural_schema.output_contract.target: target 'pr' must equal one of output_contract.artifacts[*].type",
            'shape_protocol_evidence: missing Grade evidence groups for Shape-agent work: [critic_envelope_input, high_risk_classifier, qa_protocol, rejected_critic_gate]',
        ])

    def test_cycle018_adapter_excerpt_forbidden_roots_do_not_trigger_shape_facets(self):
        proc,p=self.run_lint('code','low',CYCLE018_ADAPTER_NON_SHAPE_GRADE,CYCLE018_ADAPTER_NON_SHAPE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertNotIn('shape_forbidden_read_isolation_audit', errors)
        self.assertNotIn('outcome_capsule_v12_structural_schema', errors)
        self.assertNotIn('shape_protocol_evidence', errors)

    def test_cycle020_grade_with_shape_cross_refs_does_not_trigger_shape_facets(self):
        proc,p=self.run_lint('code','low',CYCLE020_GRADE_AGENT_ESCAPE_GRADE,CYCLE020_GRADE_AGENT_ESCAPE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertNotIn('shape_forbidden_read_isolation_audit', errors)
        self.assertNotIn('outcome_capsule_v12_structural_schema', errors)
        self.assertNotIn('shape_protocol_evidence', errors)

    def test_frontend_scope_cycle022_true_and_non_frontend_false(self):
        cycle022=textwrap.dedent(CYCLE022_FRONTEND_ESCAPE_OUTCOME)
        self.assertTrue(GRADE_LINT.frontend_primary_deliverable_in_scope(
            textwrap.dedent(CYCLE022_FRONTEND_ESCAPE_GRADE),
            cycle022,
            self.outcome_blocks_from_text(cycle022),
        ))
        cycle018=textwrap.dedent(CYCLE018_ADAPTER_NON_SHAPE_OUTCOME)
        self.assertFalse(GRADE_LINT.frontend_primary_deliverable_in_scope(
            textwrap.dedent(CYCLE018_ADAPTER_NON_SHAPE_GRADE),
            cycle018,
            self.outcome_blocks_from_text(cycle018),
        ))
        rust_only=textwrap.dedent(CYCLE022_RUST_ONLY_REQUEST_TARGET_OUTCOME)
        self.assertFalse(GRADE_LINT.frontend_primary_deliverable_in_scope(
            textwrap.dedent(REQUEST_TARGET_SUFFICIENT_GRADE),
            rust_only,
            self.outcome_blocks_from_text(rust_only),
        ))

    def test_cycle022_frontend_sse_reconnect_and_identity_mismatch_must_fire(self):
        proc,p=self.run_lint('code','medium',CYCLE022_FRONTEND_ESCAPE_GRADE,CYCLE022_FRONTEND_ESCAPE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('frontend_sse_reconnect_lifecycle[a8] missing facets:', errors)
        self.assertIn('old_source_close_or_dispose,new_source_creation,stale_old_source_events_rejected', errors)
        self.assertIn('frontend_identity_mismatch_recovery[adv6] missing facets:', errors)
        self.assertIn('callback_only_side_effect_insufficient', errors)
        self.assertIn('sse_connected_mismatched_identity_not_success', errors)

    def test_non_frontend_cycle018_and_rust_only_cycle022_do_not_fire_frontend_facets(self):
        for grade,outcome in (
            (CYCLE018_ADAPTER_NON_SHAPE_GRADE, CYCLE018_ADAPTER_NON_SHAPE_OUTCOME),
            (REQUEST_TARGET_SUFFICIENT_GRADE, CYCLE022_RUST_ONLY_REQUEST_TARGET_OUTCOME),
        ):
            with self.subTest(outcome=outcome[:40]):
                proc,p=self.run_lint('code','low',grade,outcome)
                self.assertEqual(proc.returncode,0,p)
                self.assertNotIn('frontend_', '\n'.join(p['grade_lint']['errors']))

    def test_frontend_reconnect_negated_not_applicable_text_does_not_satisfy_or_trigger(self):
        proc,p=self.run_lint('code','low',FRONTEND_NEGATED_RECONNECT_GRADE,FRONTEND_NEGATED_RECONNECT_OUTCOME)
        self.assertEqual(proc.returncode,0,p)
        self.assertNotIn('frontend_sse_reconnect_lifecycle', '\n'.join(p['grade_lint']['errors']))

    def test_cycle023_ui_m1_real_excerpts_fire_terminal_da30_and_source_affordances(self):
        proc,p=self.run_lint('code','low',CYCLE023_UI_M1_GRADE_EXCERPT,CYCLE023_UI_M1_OUTCOME_EXCERPT)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('frontend_terminal_state_enum_coverage[a3] missing terminal states:', errors)
        self.assertIn('failed,superseded,canceled/cancelled,parked,needs_human', errors)
        self.assertIn('frontend_da30_retry_snapshot_retention[a4] missing display facets:', errors)
        self.assertIn('existing_snapshot_retained_in_regions_during_retry_or_degraded', errors)
        self.assertIn('initial_load_panels_scoped_to_no_prior_snapshot_not_replacements', errors)
        self.assertIn('frontend_ui_source_affordance_evidence[a2] cited Attention Shelf/§4.6 missing affordances: jump_to_first_action,show_all_action', errors)
        self.assertIn('frontend_ui_source_affordance_evidence[a7] cited Inspector/§4.5/UX-53 missing affordances: needs_you_callout,run_in_flight_tile', errors)
        self.assertIn('frontend_ui_source_affordance_evidence[a6] cited Phase pellets/UX-11/prototype atoms missing affordances: shape_conduct_grade_visible_labels', errors)

    def test_cycle023_satisfied_evidence_fixture_passes_new_frontend_facets(self):
        proc,p=self.run_lint('code','low',CYCLE023_UI_M1_SATISFIED_GRADE,CYCLE023_UI_M1_OUTCOME_EXCERPT)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertNotIn('frontend_terminal_state_enum_coverage', errors)
        self.assertNotIn('frontend_da30_retry_snapshot_retention', errors)
        self.assertNotIn('frontend_ui_source_affordance_evidence', errors)

    def test_cycle018_and_cycle022_excerpts_do_not_fire_cycle023_frontend_facets(self):
        new_prefixes=(
            'frontend_terminal_state_enum_coverage',
            'frontend_da30_retry_snapshot_retention',
            'frontend_ui_source_affordance_evidence',
        )
        fixtures=(
            (CYCLE018_ADAPTER_NON_SHAPE_GRADE, CYCLE018_ADAPTER_NON_SHAPE_OUTCOME + '\nno reconnect required\n'),
            (CYCLE022_FRONTEND_ESCAPE_GRADE + '\nsubstrate unchanged; no shell UI-region claim; no reconnect required\n', CYCLE022_FRONTEND_ESCAPE_OUTCOME),
        )
        for grade,outcome in fixtures:
            with self.subTest(outcome=outcome[:40]):
                _proc,p=self.run_lint('code','low',grade,outcome)
                errors='\n'.join(p['grade_lint']['errors'])
                for prefix in new_prefixes:
                    self.assertNotIn(prefix, errors)

    def test_frontend_negated_cycle023_phrasing_does_not_trigger_new_facets(self):
        proc,p=self.run_lint('code','low',FRONTEND_NEGATED_CYCLE023_FACET_GRADE,FRONTEND_NEGATED_CYCLE023_FACET_OUTCOME)
        self.assertEqual(proc.returncode,0,p)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertNotIn('frontend_terminal_state_enum_coverage', errors)
        self.assertNotIn('frontend_da30_retry_snapshot_retention', errors)
        self.assertNotIn('frontend_ui_source_affordance_evidence', errors)

    def test_cycle024_ui_m2_real_excerpts_fire_production_wiring_and_pending_dismissal_facets(self):
        proc,p=self.run_lint('code','low',CYCLE024_UI_M2_GRADE_EXCERPT,CYCLE024_UI_M2_OUTCOME_EXCERPT)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('frontend_production_wiring_or_unavailable_honesty[a4]', errors)
        self.assertIn('frontend_production_wiring_or_unavailable_honesty[a7]', errors)
        self.assertIn('frontend_production_wiring_or_unavailable_honesty[a8]', errors)
        self.assertIn('frontend_pessimistic_pending_dismissal_guard[a4] missing pending dismissal paths:', errors)
        self.assertIn('Escape,overlay/backdrop click,route/surface change', errors)

    def test_cycle022_and_cycle023_excerpts_do_not_fire_cycle024_frontend_facets(self):
        new_prefixes=(
            'frontend_production_wiring_or_unavailable_honesty',
            'frontend_pessimistic_pending_dismissal_guard',
        )
        fixtures=(
            (CYCLE022_FRONTEND_ESCAPE_GRADE, CYCLE022_FRONTEND_ESCAPE_OUTCOME),
            (CYCLE023_UI_M1_GRADE_EXCERPT, CYCLE023_UI_M1_OUTCOME_EXCERPT),
        )
        for grade,outcome in fixtures:
            with self.subTest(outcome=outcome[:40]):
                _proc,p=self.run_lint('code','low',grade,outcome)
                errors='\n'.join(p['grade_lint']['errors'])
                for prefix in new_prefixes:
                    self.assertNotIn(prefix, errors)

    def test_cycle024_satisfied_fixture_and_negated_phrasing_do_not_fire_new_facets(self):
        new_prefixes=(
            'frontend_production_wiring_or_unavailable_honesty',
            'frontend_pessimistic_pending_dismissal_guard',
        )
        for grade,outcome in (
            (CYCLE024_SATISFIED_GRADE, CYCLE024_UI_M2_OUTCOME_EXCERPT),
            (FRONTEND_NEGATED_CYCLE024_FACET_GRADE, FRONTEND_NEGATED_CYCLE024_FACET_OUTCOME),
        ):
            with self.subTest(outcome=outcome[:40]):
                _proc,p=self.run_lint('code','low',grade,outcome)
                errors='\n'.join(p['grade_lint']['errors'])
                for prefix in new_prefixes:
                    self.assertNotIn(prefix, errors)

    def test_negative_failure_branch_coverage_cycle026_real_escape_must_fire(self):
        proc,p=self.run_lint('code','low',CYCLE026_NEGATIVE_FAILURE_GRADE_EXCERPT,CYCLE026_NEGATIVE_FAILURE_OUTCOME_EXCERPT)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn(
            'negative_failure_branch_coverage[a6] missing branches: GET /api/v1/capabilities after POST /api/v1/daemon/commands/refresh-capability (failure+retry); GET /api/v1/config (failure+retry)',
            errors,
        )

    def test_negative_failure_branch_coverage_cycle023_get_retry_real_clean(self):
        _proc,p=self.run_lint('code','low',CYCLE023_UI_M1_GRADE_EXCERPT,CYCLE023_UI_M1_OUTCOME_EXCERPT)
        self.assertNotIn('negative_failure_branch_coverage', '\n'.join(p['grade_lint']['errors']))

    def test_negative_failure_branch_coverage_cycle024_post_resubmit_real_clean(self):
        _proc,p=self.run_lint('code','low',CYCLE024_UI_M2_GRADE_EXCERPT,CYCLE024_UI_M2_OUTCOME_EXCERPT)
        self.assertNotIn('negative_failure_branch_coverage', '\n'.join(p['grade_lint']['errors']))

    def test_cycle027_frontend_sse_production_subscription_anchor_real_escape_must_fire(self):
        proc,p=self.run_lint('code','low',CYCLE027_SSE_MOCK_ONLY_GRADE_EXCERPT,CYCLE027_SSE_MOCK_ONLY_OUTCOME_EXCERPT)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn(
            'frontend_sse_production_subscription_anchor[a3] SSE/progress-invalidation PASS cites only test/mock evidence (conduct.test.tsx, hand-built SSE object)',
            errors,
        )
        self.assertIn(
            'frontend_sse_production_subscription_anchor[a4] SSE/reconnect lifecycle PASS cites only test/mock evidence (conduct.test.tsx, connection.ts definition)',
            errors,
        )

    def test_frontend_sse_production_subscription_anchor_accepts_non_test_production_caller(self):
        grade=CYCLE027_SSE_MOCK_ONLY_GRADE_EXCERPT.replace(
            'conduct.test.tsx: runEvents issues the production GET',
            'src/shell/AppShell.tsx calls subscribeToInvalidations() and runEvents issues the production GET',
        ).replace(
            "conduct.test.tsx 'retains the prior conduct snapshot while reconnecting and degraded…' green; reconnect lifecycle reused from src/lib/sse/connection.ts (unchanged)",
            "src/shell/AppShell.tsx mounts the SSE invalidation controller by calling subscribeToInvalidations(); conduct.test.tsx retains the prior conduct snapshot while reconnecting and degraded",
        )
        _proc,p=self.run_lint('code','low',grade,CYCLE027_SSE_MOCK_ONLY_OUTCOME_EXCERPT)
        self.assertNotIn('frontend_sse_production_subscription_anchor', '\n'.join(p['grade_lint']['errors']))

    def test_cycle026_no_sse_obligation_does_not_fire_subscription_anchor(self):
        _proc,p=self.run_lint('code','low',CYCLE026_NEGATIVE_FAILURE_GRADE_EXCERPT,CYCLE026_NEGATIVE_FAILURE_OUTCOME_EXCERPT)
        self.assertNotIn('frontend_sse_production_subscription_anchor', '\n'.join(p['grade_lint']['errors']))

    def test_cycle027_stream_decode_malformed_negative_coverage_real_escape_must_fire(self):
        proc,p=self.run_lint('code','low',CYCLE027_SSE_MOCK_ONLY_GRADE_EXCERPT,CYCLE027_SSE_MOCK_ONLY_OUTCOME_EXCERPT)
        self.assertEqual(proc.returncode,1)
        self.assertIn(
            'stream_decode_malformed_negative_coverage[a3] NDJSON/parser claim lacks malformed/non-JSON negative evidence (preserve-valid / no-throw)',
            '\n'.join(p['grade_lint']['errors']),
        )

    def test_cycle022_and_cycle026_do_not_fire_stream_decode_malformed_negative_coverage(self):
        for grade,outcome in (
            (CYCLE022_FRONTEND_ESCAPE_GRADE, CYCLE022_FRONTEND_ESCAPE_OUTCOME),
            (CYCLE026_NEGATIVE_FAILURE_GRADE_EXCERPT, CYCLE026_NEGATIVE_FAILURE_OUTCOME_EXCERPT),
        ):
            with self.subTest(outcome=outcome[:40]):
                _proc,p=self.run_lint('code','low',grade,outcome)
                self.assertNotIn('stream_decode_malformed_negative_coverage', '\n'.join(p['grade_lint']['errors']))

    def test_cycle025_ui_m3_real_excerpts_fire_schema_tags_command_facets(self):
        proc,p=self.run_lint('code','low',CYCLE025_UI_M3_GRADE_EXCERPT,CYCLE025_UI_M3_OUTCOME_EXCERPT)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('frontend_outcome_capsule_schema_guard_evidence missing families:', errors)
        self.assertIn('schema_version,iteration,output_contract,tags_controlled_or_unknown', errors)
        self.assertIn('frontend_outcome_tags_render_evidence missing facets:', errors)
        self.assertIn('frontend_pessimistic_command_matrix[re_shape] missing facets:', errors)
        self.assertIn('frontend_pessimistic_command_matrix[conflict_refetch] missing facets:', errors)

    def test_cycle022_command_substrate_does_not_fire_pessimistic_command_matrix(self):
        # cycle-022 backtest false_positive: wrapper/commandPolicy claims name the commands with
        # If-Match/PESSIMISTIC context but carry no UI-affordance claim — the matrix must stay silent.
        _proc,p=self.run_lint('code','low',CYCLE022_COMMAND_SUBSTRATE_GRADE,CYCLE022_COMMAND_SUBSTRATE_OUTCOME)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertNotIn('frontend_pessimistic_command_matrix', errors)

    def test_cycle023_and_cycle024_excerpts_do_not_fire_cycle025_frontend_facets(self):
        new_prefixes=(
            'frontend_outcome_capsule_schema_guard_evidence',
            'frontend_outcome_tags_render_evidence',
            'frontend_pessimistic_command_matrix',
        )
        fixtures=(
            (CYCLE023_UI_M1_GRADE_EXCERPT, CYCLE023_UI_M1_OUTCOME_EXCERPT),
            (CYCLE024_SATISFIED_GRADE, CYCLE024_UI_M2_OUTCOME_EXCERPT),
        )
        for grade,outcome in fixtures:
            with self.subTest(outcome=outcome[:40]):
                _proc,p=self.run_lint('code','low',grade,outcome)
                errors='\n'.join(p['grade_lint']['errors'])
                for prefix in new_prefixes:
                    self.assertNotIn(prefix, errors)

    def test_cycle025_satisfied_fixture_and_negated_phrasing_do_not_fire_new_facets(self):
        new_prefixes=(
            'frontend_outcome_capsule_schema_guard_evidence',
            'frontend_outcome_tags_render_evidence',
            'frontend_pessimistic_command_matrix',
        )
        for grade,outcome in (
            (CYCLE025_SATISFIED_GRADE, CYCLE025_UI_M3_OUTCOME_EXCERPT),
            (FRONTEND_NEGATED_CYCLE025_FACET_GRADE, FRONTEND_NEGATED_CYCLE025_FACET_OUTCOME),
        ):
            with self.subTest(outcome=outcome[:40]):
                _proc,p=self.run_lint('code','low',grade,outcome)
                errors='\n'.join(p['grade_lint']['errors'])
                for prefix in new_prefixes:
                    self.assertNotIn(prefix, errors)

    def test_reference_source_missing_ledger_must_fire_on_real_cycle023_text(self):
        proc,p=self.run_lint('code','low',CYCLE023_UI_M1_GRADE_EXCERPT,CYCLE023_UI_M1_OUTCOME_EXCERPT)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('reference_source_contract_review.reference_obligations_missing', errors)

    def test_reference_source_missing_ledger_must_not_fire_on_non_reference_cycle018(self):
        proc,p=self.run_lint('code','low',CYCLE018_ADAPTER_NON_SHAPE_GRADE,CYCLE018_ADAPTER_NON_SHAPE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)
        self.assertNotIn('reference_source_contract_review', '\n'.join(p['grade_lint']['errors']))

    def test_reference_source_historical_backtest_prose_must_not_trigger_b2(self):
        self.assert_reference_clean(REFERENCE_HISTORICAL_ONLY_GRADE,REFERENCE_HISTORICAL_ONLY_OUTCOME)

    def test_reference_source_backend_api_taxonomy_is_defined_but_trigger_deferred(self):
        self.assert_reference_clean(REFERENCE_BACKEND_API_GRADE,REFERENCE_BACKEND_API_OUTCOME)

    def test_reference_source_agent_task_without_ledger_must_not_force_b2(self):
        proc,p=self.run_lint('code','low',CYCLE020_GRADE_AGENT_ESCAPE_GRADE,CYCLE020_GRADE_AGENT_ESCAPE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertNotIn('reference_source_contract_review.reference_obligations_missing', '\n'.join(p['grade_lint']['errors']))

    def test_reference_source_binding_and_required_classes_must_fire_and_clean_pair(self):
        proc,p=self.run_lint('code','low',REFERENCE_MISSING_BINDING_GRADE,REFERENCE_MISSING_BINDING_AND_CLASSES_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('reference_source_contract_review.reference_obligations[UX-101-ACTION-STATE].required_evidence_classes is required', errors)
        self.assertIn('reference_source_contract_review.obligation_binding_missing[spec_compliance_matrix[0]]', errors)
        self.assert_reference_clean(REFERENCE_VALID_GRADE,REFERENCE_VALID_OUTCOME)

    def test_reference_source_unaddressed_ledger_obligation_must_fire(self):
        proc,p=self.run_lint('code','low',REFERENCE_VALID_GRADE,REFERENCE_UNADDRESSED_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('reference_source_contract_review.reference_obligation_unaddressed[UX-102-UNBOUND]', '\n'.join(p['grade_lint']['errors']))

    def test_reference_source_fixture_only_production_anchor_must_fire_and_clean_pair(self):
        proc,p=self.run_lint('code','low',REFERENCE_FIXTURE_ONLY_GRADE,REFERENCE_PRODUCTION_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('reference_source_contract_review.production_path_anchor_missing[UX-101-ACTION-STATE]', '\n'.join(p['grade_lint']['errors']))
        proc,p=self.run_lint('code','low',REFERENCE_FIXTURE_ONLY_BACKLOG_GRADE,REFERENCE_PRODUCTION_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('reference_source_contract_review.production_path_anchor_missing[UX-101-ACTION-STATE]', '\n'.join(p['grade_lint']['errors']))
        self.assert_reference_clean(REFERENCE_PRODUCTION_ANCHOR_GRADE,REFERENCE_PRODUCTION_OUTCOME)

    def test_reference_source_static_presence_ui_must_fire_and_behavioral_clean_pair(self):
        proc,p=self.run_lint('code','low',REFERENCE_STATIC_ONLY_GRADE,REFERENCE_VALID_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('reference_source_contract_review.behavioral_ui_test_missing[UX-101-ACTION-STATE]', '\n'.join(p['grade_lint']['errors']))
        self.assert_reference_clean(REFERENCE_VALID_GRADE,REFERENCE_VALID_OUTCOME)

    def test_reference_source_silent_narrowing_must_fire_and_unverified_clean_pair(self):
        proc,p=self.run_lint('code','low',REFERENCE_VALID_GRADE,REFERENCE_NARROWED_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('reference_source_contract_review.silent_narrowing[UX-101-ACTION-STATE]', '\n'.join(p['grade_lint']['errors']))
        proc,p=self.run_lint('code','low',REFERENCE_VALID_GRADE,REFERENCE_NARROWED_NULL_WAIVER_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('reference_source_contract_review.silent_narrowing[UX-101-ACTION-STATE]', '\n'.join(p['grade_lint']['errors']))
        self.assert_reference_clean(REFERENCE_VALID_GRADE,REFERENCE_NARROWED_WAIVED_OUTCOME)

    def test_reference_source_hostile_fixture_ids_must_fire_on_vague_prose_and_clean_pair(self):
        proc,p=self.run_lint('code','low',REFERENCE_HOSTILE_MIN_GRADE,REFERENCE_HOSTILE_MIN_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('reference_source_contract_review.hostile_fixture_ids_missing[GRADE-HOSTILE-01]', '\n'.join(p['grade_lint']['errors']))
        self.assert_reference_clean(REFERENCE_HOSTILE_MIN_GRADE,REFERENCE_HOSTILE_MIN_IDS_OUTCOME)

    def test_reference_source_bare_click_without_userevent_must_fire_behavioral(self):
        # review P2-9: getByRole + static presence + bare "click" (no userEvent/fireEvent) is NOT behavioral
        grade=REFERENCE_VALID_GRADE.replace(
            "src/action.test.tsx: getByRole('button', {name:/Next/}) + userEvent.click asserts disabled then enabled state assertion",
            "src/action.test.tsx: heading and data-testid present; getByRole queried; click handler invoked; expect(state).toBeVisible()")
        proc,p=self.run_lint('code','low',grade,REFERENCE_VALID_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('reference_source_contract_review.behavioral_ui_test_missing[UX-101-ACTION-STATE]', '\n'.join(p['grade_lint']['errors']))
        self.assert_reference_clean(REFERENCE_VALID_GRADE,REFERENCE_VALID_OUTCOME)

    def test_reference_source_hostile_kebab_prose_still_fires(self):
        # review P1-8: kebab-case prose tokens (read-only, command-timeout) are NOT fixture ids
        grade=REFERENCE_HOSTILE_MIN_GRADE.replace(
            "hostile_fixture_ids executed but not named",
            "read-only isolation passed; command-timeout negative-pgid test passed")
        proc,p=self.run_lint('code','low',grade,REFERENCE_HOSTILE_MIN_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('reference_source_contract_review.hostile_fixture_ids_missing[GRADE-HOSTILE-01]', '\n'.join(p['grade_lint']['errors']))

    def test_reference_source_current_example_citation_still_triggers(self):
        # review NEW-P2-1: bare "example" must not over-exclude a genuine CURRENT source citation
        import re as _re
        outcome_no_ledger=_re.sub(r"```yaml\nreference_obligations:.*?```", "Outcome body without a reference_obligations ledger.", REFERENCE_VALID_OUTCOME, flags=_re.S)
        grade=REFERENCE_VALID_GRADE.replace('    obligation_id: UX-101-ACTION-STATE\n','').replace(
            "src/action.test.tsx: getByRole('button', {name:/Next/}) + userEvent.click asserts disabled then enabled state assertion",
            "example current docs/ux/design-brief.md §10.11 behavior covered")
        proc,p=self.run_lint('code','low',grade,outcome_no_ledger)
        self.assertEqual(proc.returncode,1)
        self.assertIn('reference_source_contract_review.reference_obligations_missing', '\n'.join(p['grade_lint']['errors']))

    def test_reference_source_advisory_request_artifact_emitted_never_verdict_gated(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); gf=root/'grade.md'; of=root/'outcome.md'; ef=root/'evidence'/'grade_lint_round_0.json'
            gf.write_text(textwrap.dedent(REFERENCE_VALID_GRADE)); of.write_text(textwrap.dedent(REFERENCE_VALID_OUTCOME))
            proc=subprocess.run([sys.executable,str(LINTER),'--task-type','code','--risk-level','low','--grade-file',str(gf),'--outcome-file',str(of),'--evidence-file',str(ef)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
            request=ef.parent/'reference_obligation_review_request.jsonl'
            verdict=ef.parent/'reference_obligation_review_verdict.jsonl'
            self.assertTrue(request.exists())
            rows=[json.loads(line) for line in request.read_text().splitlines()]
            self.assertEqual([row['obligation_id'] for row in rows], ['UX-101-ACTION-STATE'])
            self.assertFalse(verdict.exists())

    def test_reference_source_advisory_request_write_failure_is_non_gating(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); gf=root/'grade.md'; of=root/'outcome.md'; ef=root/'evidence'/'grade_lint_round_0.json'
            request_dir=ef.parent/'reference_obligation_review_request.jsonl'
            request_dir.mkdir(parents=True)
            gf.write_text(textwrap.dedent(REFERENCE_VALID_GRADE)); of.write_text(textwrap.dedent(REFERENCE_VALID_OUTCOME))
            proc=subprocess.run([sys.executable,str(LINTER),'--task-type','code','--risk-level','low','--grade-file',str(gf),'--outcome-file',str(of),'--evidence-file',str(ef)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
            payload=json.loads(proc.stdout)
            self.assertEqual(payload['grade_lint']['status'],'pass')

    def write_frontend_dependency_repo(self, root, *, drift):
        (root/'docs'/'architecture').mkdir(parents=True)
        (root/'apps'/'symphony-ui').mkdir(parents=True)
        (root/'docs'/'architecture'/'tech-stack.yaml').write_text(textwrap.dedent('''
        frontend_locked:
          - name: react
            version: "19.2.6"
          - name: typescript
            version: "6.0.3"
          - name: vite
            version: "8.0.14"
          - name: "@tauri-apps/cli"
            version: "2.11.2"
          - name: zustand
            version: "5.0+"
          - name: pnpm
            version: "10.33+"
        '''), encoding='utf-8')
        package={
            "name":"symphony-ui",
            "version":"0.1.0",
            "private":True,
            "type":"module",
            "dependencies":{"react":"^19.2.6","zustand":"^5.0.0"},
            "devDependencies":{"typescript":"~6.0.3","vite":"^8.0.14","@tauri-apps/cli":"^2.11.2"},
        }
        if not drift:
            package["packageManager"]="pnpm@10.33.0"
        (root/'apps'/'symphony-ui'/'package.json').write_text(json.dumps(package,indent=2), encoding='utf-8')
        react_version='19.2.7' if drift else '19.2.6'
        vite_version='8.0.16' if drift else '8.0.14'
        (root/'apps'/'symphony-ui'/'pnpm-lock.yaml').write_text(textwrap.dedent(f'''
        lockfileVersion: '9.0'
        importers:
          .:
            dependencies:
              react:
                specifier: ^19.2.6
                version: {react_version}
              zustand:
                specifier: ^5.0.0
                version: 5.0.14(react@{react_version})
            devDependencies:
              '@tauri-apps/cli':
                specifier: ^2.11.2
                version: 2.11.2
              typescript:
                specifier: ~6.0.3
                version: 6.0.3
              vite:
                specifier: ^8.0.14
                version: {vite_version}
        '''), encoding='utf-8')

    def test_frontend_dependency_lock_guard_detects_real_cycle022_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.write_frontend_dependency_repo(root, drift=True)
            proc,p=self.run_lint('code','low',FRONTEND_DEP_GRADE,FRONTEND_DEP_OUTCOME,repo_root=root)
            self.assertEqual(proc.returncode,1)
            errors='\n'.join(p['grade_lint']['errors'])
            self.assertIn('frontend_dependency_lock_guard[react]', errors)
            self.assertIn('canonical 19.2.6', errors)
            self.assertIn('resolves 19.2.7', errors)
            self.assertIn('frontend_dependency_lock_guard[vite]', errors)
            self.assertIn('canonical 8.0.14', errors)
            self.assertIn('resolves 8.0.16', errors)
            self.assertIn('frontend_dependency_lock_guard[pnpm]', errors)
            self.assertIn('omits packageManager', errors)

    def test_frontend_dependency_lock_guard_exact_match_passes_and_skips_without_repo_root(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.write_frontend_dependency_repo(root, drift=False)
            proc,p=self.run_lint('code','low',FRONTEND_DEP_GRADE,FRONTEND_DEP_OUTCOME,repo_root=root)
            self.assertEqual(proc.returncode,0,p)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.write_frontend_dependency_repo(root, drift=True)
            proc,p=self.run_lint('code','low',FRONTEND_DEP_GRADE,FRONTEND_DEP_OUTCOME)
            self.assertEqual(proc.returncode,0,p)

    def assert_cycle020_grade_error(self, expected):
        proc,p=self.run_lint('code','low',CYCLE020_GRADE_AGENT_ESCAPE_GRADE,CYCLE020_GRADE_AGENT_ESCAPE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn(expected, '\n'.join(p['grade_lint']['errors']))

    def assert_cycle021_evolve_error(self, expected):
        proc,p=self.run_lint('code','low',CYCLE021_EVOLVE_AGENT_ESCAPE_GRADE,CYCLE021_EVOLVE_AGENT_ESCAPE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn(expected, '\n'.join(p['grade_lint']['errors']))

    def assert_cycle018_non_evolve_lacks_error(self, unexpected):
        proc,p=self.run_lint('code','low',CYCLE018_ADAPTER_NON_SHAPE_GRADE,CYCLE018_ADAPTER_NON_SHAPE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)
        self.assertNotIn(unexpected, '\n'.join(p['grade_lint']['errors']))

    def outcome_blocks_from_text(self, outcome_text):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'outcome.md'
            path.write_text(textwrap.dedent(outcome_text))
            return GRADE_LINT.blocks(path, include_front_matter=True)

    def assert_cycle016_clean_lacks_error(self, unexpected):
        proc,p=self.run_lint('code','low',CYCLE016_LEDGER_CLEAN_GRADE,CYCLE016_LEDGER_CLEAN_OUTCOME)
        self.assertEqual(proc.returncode,0,p)
        self.assertNotIn(unexpected, '\n'.join(p['grade_lint']['errors']))

    def test_evolve_agent_scope_cycle021_true_and_cycle018_cross_ref_false(self):
        cycle021_outcome=textwrap.dedent(CYCLE021_EVOLVE_AGENT_ESCAPE_OUTCOME)
        cycle018_outcome=textwrap.dedent(CYCLE018_ADAPTER_NON_SHAPE_OUTCOME)
        self.assertTrue(GRADE_LINT.evolve_agent_task_in_scope(
            textwrap.dedent(CYCLE021_EVOLVE_AGENT_ESCAPE_GRADE),
            cycle021_outcome,
            self.outcome_blocks_from_text(cycle021_outcome),
        ))
        self.assertFalse(GRADE_LINT.evolve_agent_task_in_scope(
            textwrap.dedent(CYCLE018_ADAPTER_NON_SHAPE_GRADE),
            cycle018_outcome,
            self.outcome_blocks_from_text(cycle018_outcome),
        ))

    def test_evolve_metadata_persisted_post_commit_cycle021_must_fire(self):
        self.assert_cycle021_evolve_error('evolve_metadata_persisted_post_commit')

    def test_evolve_metadata_persisted_post_commit_cycle018_must_not_fire(self):
        self.assert_cycle018_non_evolve_lacks_error('evolve_metadata_persisted_post_commit')

    def test_evolve_critic_prefilter_substance_cycle021_must_fire(self):
        self.assert_cycle021_evolve_error('evolve_critic_prefilter_substance')

    def test_evolve_critic_prefilter_substance_cycle018_must_not_fire(self):
        self.assert_cycle018_non_evolve_lacks_error('evolve_critic_prefilter_substance')

    def test_evolve_write_with_git_and_log_counts_cycle021_must_fire(self):
        self.assert_cycle021_evolve_error('evolve_write_with_git_and_log_counts')

    def test_evolve_write_with_git_and_log_counts_cycle018_must_not_fire(self):
        self.assert_cycle018_non_evolve_lacks_error('evolve_write_with_git_and_log_counts')

    def test_evolve_lightweight_commit_idempotence_cycle021_must_fire(self):
        self.assert_cycle021_evolve_error('evolve_lightweight_commit_idempotence')

    def test_evolve_lightweight_commit_idempotence_cycle018_must_not_fire(self):
        self.assert_cycle018_non_evolve_lacks_error('evolve_lightweight_commit_idempotence')

    def test_grade_agent_read_only_isolation_audit_cycle020_must_fire(self):
        self.assert_cycle020_grade_error('grade_agent_read_only_isolation_audit')

    def test_grade_agent_read_only_isolation_audit_cycle016_must_not_fire(self):
        self.assert_cycle016_clean_lacks_error('grade_agent_read_only_isolation_audit')

    def test_grade_agent_dp13_schema_trigger_cycle020_must_fire(self):
        self.assert_cycle020_grade_error('grade_agent_dp13_schema_trigger')

    def test_grade_agent_dp13_schema_trigger_cycle016_must_not_fire(self):
        self.assert_cycle016_clean_lacks_error('grade_agent_dp13_schema_trigger')

    def test_grade_agent_second_signal_unforgeable_cycle020_must_fire(self):
        self.assert_cycle020_grade_error('grade_agent_second_signal_unforgeable')

    def test_grade_agent_second_signal_unforgeable_cycle016_must_not_fire(self):
        self.assert_cycle016_clean_lacks_error('grade_agent_second_signal_unforgeable')

    def test_grade_agent_llm_judge_fail_closed_cycle020_must_fire(self):
        self.assert_cycle020_grade_error('grade_agent_llm_judge_fail_closed')

    def test_grade_agent_llm_judge_fail_closed_cycle016_must_not_fire(self):
        self.assert_cycle016_clean_lacks_error('grade_agent_llm_judge_fail_closed')

    def test_grade_agent_outcome_path_schema_fields_cycle020_must_fire(self):
        self.assert_cycle020_grade_error('grade_agent_outcome_path_schema_fields')

    def test_grade_agent_outcome_path_schema_fields_cycle016_must_not_fire(self):
        self.assert_cycle016_clean_lacks_error('grade_agent_outcome_path_schema_fields')

    def test_grade_agent_critic_substance_cycle020_must_fire(self):
        self.assert_cycle020_grade_error('grade_agent_critic_substance')

    def test_grade_agent_critic_substance_cycle016_must_not_fire(self):
        self.assert_cycle016_clean_lacks_error('grade_agent_critic_substance')

    def test_subprocess_lifecycle_descendant_escape_cycle020_must_fire(self):
        self.assert_cycle020_grade_error('subprocess_lifecycle[adv1] missing facets: descendant_escape_fixture')

    def test_subprocess_lifecycle_descendant_escape_cycle016_must_not_fire(self):
        self.assert_cycle016_clean_lacks_error('descendant_escape_fixture')

    def test_cycle018_rpc_cleanup_every_exit_claim_requires_negative_path_cleanup_evidence(self):
        proc,p=self.run_lint('code','low',RPC_CLEANUP_HAPPY_ONLY_GRADE,RPC_CLEANUP_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertEqual(p['grade_lint']['errors'], [
            'rpc_cleanup[B018-A6] cleanup-on-every-exit-path claimed but no timeout/error-path cleanup evidence (negative-path test required)'
        ])

    def test_rpc_cleanup_every_exit_claim_passes_with_forced_timeout_cleanup_test(self):
        proc,p=self.run_lint('code','low',RPC_CLEANUP_TIMEOUT_EVIDENCE_GRADE,RPC_CLEANUP_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle016_clean_ledger_timeout_text_does_not_trigger_rpc_cleanup(self):
        proc,p=self.run_lint('code','low',CYCLE016_LEDGER_CLEAN_GRADE,CYCLE016_LEDGER_CLEAN_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_cycle017_style_path_root_acceptance_requires_symlink_or_canonical_coverage(self):
        proc,p=self.run_lint('code','low',CYCLE017_INSUFFICIENT_GRADE,CYCLE017_STYLE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('property_obligation[B005-PATH-SAFETY]', errors)
        self.assertIn('symlink_or_canonical_containment', errors)

    def test_cycle017_style_path_root_acceptance_passes_with_canonical_coverage(self):
        proc,p=self.run_lint('code','low',CYCLE017_SUFFICIENT_GRADE,CYCLE017_STYLE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_raw_request_target_acceptance_requires_delimiter_control_char_coverage(self):
        proc,p=self.run_lint('code','low',REQUEST_TARGET_INSUFFICIENT_GRADE,REQUEST_TARGET_OUTCOME)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('property_obligation[CLIENT-REQUEST-TARGET]', errors)
        self.assertIn('request_target_delimiter_or_control_chars', errors)

    def test_raw_request_target_generic_mention_is_not_enough(self):
        proc,p=self.run_lint('code','low',REQUEST_TARGET_GENERIC_ONLY_GRADE,REQUEST_TARGET_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('request_target_delimiter_or_control_chars', '\n'.join(p['grade_lint']['errors']))

    def test_raw_request_target_malformed_request_is_not_enough(self):
        proc,p=self.run_lint('code','low',REQUEST_TARGET_MALFORMED_ONLY_GRADE,REQUEST_TARGET_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('request_target_delimiter_or_control_chars', '\n'.join(p['grade_lint']['errors']))

    def test_raw_request_target_acceptance_passes_with_delimiter_control_char_coverage(self):
        proc,p=self.run_lint('code','low',REQUEST_TARGET_SUFFICIENT_GRADE,REQUEST_TARGET_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_yaml_parser_accepts_colon_containing_scalar_lists(self):
        grade=LOW_CODE_COMPLETE.replace(
            'checked_surfaces: [debug, display, errors, logs]',
            'checked_surfaces:\n  - "Authorization: Bearer redaction"\n  - "Debug: no secret echo"\n  - logs'
        )
        proc,p=self.run_lint('code','low',grade,LOW_CODE_OUTCOME)
        self.assertEqual(proc.returncode,0,p)

    def test_low_risk_code_requires_p1_negative_test_coverage(self):
        grade=LOW_CODE_COMPLETE.replace('  - acceptance_id: CFG\n    status: pass\n    severity_if_fail: P1\n    scenario: malformed secret-bearing YAML does not echo the secret and locked dependency is present\n    evidence_ref: tests/config.rs::malformed_secret_yaml_is_redacted\n','')
        proc,p=self.run_lint('code','low',grade,LOW_CODE_OUTCOME)
        self.assertEqual(proc.returncode,1)
        self.assertIn('negative_regression_tests missing P0/P1 outcome acceptance IDs: CFG','\n'.join(p['grade_lint']['errors']))

    def test_missing_shaped_adversarial_acceptance_check_fails(self):
        grade=COMPLETE.replace('acceptance_id: ADV-TRUST, ', '')
        proc,p=self.run_lint(grade=grade); self.assertEqual(proc.returncode,1); self.assertIn('missing shaped adversarial_acceptance IDs','\n'.join(p['grade_lint']['errors']))

    def test_unverified_p1_adversarial_check_must_be_counted_and_blocks(self):
        grade=COMPLETE.replace('status: pass, severity_if_fail: P1', 'status: unverified, severity_if_fail: P1', 1).replace('p1_count: 0','p1_count: 1').replace('adversarial_p1_count: 0','adversarial_p1_count: 1')
        proc,p=self.run_lint(grade=grade); self.assertEqual(proc.returncode,1); self.assertIn('blocking: unverified/P1','\n'.join(p['grade_lint']['errors']))

    def test_blocking_acceptance_hint_cannot_make_current_validation_optional(self):
        outcome=OUTCOME.replace('inspect code and run fault probe', 'optional future follow-up; not reachable in current validation')
        proc,p=self.run_lint(grade=COMPLETE,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('verification_hint makes current validation optional', '\n'.join(p['grade_lint']['errors']))

    def test_deferred_claim_cannot_defer_current_p1_adversarial_acceptance_by_assertion(self):
        grade=COMPLETE.replace('deferred_claims:\n  - {item: header, deferred_to: B-002, current_scope_implementable: false, rationale: future}', 'deferred_claims:\n  - {item: ADV-TRUST is deferred by assertion, deferred_to: B-999, current_scope_implementable: false, rationale: future}')
        proc,p=self.run_lint(grade=grade)
        self.assertEqual(proc.returncode,1)
        self.assertIn('defers current P0/P1 adversarial acceptance without tracked waiver or scope_basis_ref', '\n'.join(p['grade_lint']['errors']))

    def test_deferred_current_adversarial_acceptance_allows_scope_basis_ref(self):
        grade=COMPLETE.replace('deferred_claims:\n  - {item: header, deferred_to: B-002, current_scope_implementable: false, rationale: future}', 'deferred_claims:\n  - {item: ADV-TRUST explicitly out of current task, deferred_to: B-999, current_scope_implementable: false, scope_basis_ref: docs/scope.md#non-goal}')
        proc,p=self.run_lint(grade=grade)
        self.assertEqual(proc.returncode,0,p)

    def test_adv_ifmatch_split_optional_concurrency_test_fails(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    concurrency_or_locking: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-IFMATCH-SPLIT
    severity: P1
    surface: [concurrency_or_locking]
    statement: Same-revision concurrent PATCH requests must produce one 2xx and one 409, preventing lost update.
    verification_hint: optional concurrency test may be deferred because this is not reachable now
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: ifmatch-split
    acceptance_id: ADV-IFMATCH-SPLIT
    status: pass
    severity_if_fail: P1
    surface: [concurrency_or_locking]
    evidence_ref: evidence/grade/http_status.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        errors='\n'.join(p['grade_lint']['errors'])
        self.assertIn('verification_hint makes current validation optional', errors)
        self.assertIn('concurrency_or_locking check requires evidence_kind', errors)

    def test_concurrency_check_accepts_concurrency_test_evidence_kind(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    concurrency_or_locking: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-IFMATCH-SPLIT
    severity: P1
    surface: [concurrency_or_locking]
    statement: Same-revision concurrent PATCH requests must produce one 2xx and one 409, preventing lost update.
    verification_hint: run concurrent PATCH probe and verify one 2xx plus one 409
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: ifmatch-split
    acceptance_id: ADV-IFMATCH-SPLIT
    status: pass
    severity_if_fail: P1
    surface: [concurrency_or_locking]
    evidence_kind: concurrency_test
    evidence_ref: evidence/grade/ifmatch_concurrency.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
""" + A1_CODE_SECTIONS
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,0,p)

    def test_boundary_acceptance_requires_boundary_surface(self):
        outcome=OUTCOME.replace('statement: trust surface must be probed', 'statement: user text <=280 chars JSON boundary must not truncate non-ASCII')
        proc,p=self.run_lint(grade=COMPLETE,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('boundary/input risk must use string_boundary or input_validation_or_schema surface', '\n'.join(p['grade_lint']['errors']))

    def test_boundary_check_requires_boundary_evidence_kind(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    input_validation_or_schema: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-JSON-BOUNDARY
    severity: P1
    surface: [input_validation_or_schema]
    statement: malformed JSON and user text <=280 chars are rejected without truncation.
    verification_hint: run malformed JSON and non-ASCII boundary probes
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: json-boundary
    acceptance_id: ADV-JSON-BOUNDARY
    status: pass
    severity_if_fail: P1
    surface: [input_validation_or_schema]
    evidence_ref: evidence/grade/json_boundary.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('boundary/input check requires evidence_kind', '\n'.join(p['grade_lint']['errors']))

    def test_no_panic_audit_rejects_mere_grep(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    runtime_files: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-NO-PANIC
    severity: P1
    surface: [runtime_files]
    statement: no-panic path: parsing malformed runtime files must not panic through unwrap or expect.
    verification_hint: audit implicit panic paths and run malformed file probe
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: no-panic-grep
    acceptance_id: ADV-NO-PANIC
    status: pass
    severity_if_fail: P1
    surface: [runtime_files]
    evidence_kind: panic_audit
    audit_method: grep only
    evidence_ref: evidence/grade/grep_panic.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('panic/no-panic audit cannot be mere grep', '\n'.join(p['grade_lint']['errors']))

    def test_no_panic_audit_requires_panic_evidence_kind(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    runtime_files: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-NO-PANIC
    severity: P1
    surface: [runtime_files]
    statement: no-panic path: malformed runtime files must not panic through unwrap or expect.
    verification_hint: audit implicit panic paths and run malformed file probe
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: no-panic
    acceptance_id: ADV-NO-PANIC
    status: pass
    severity_if_fail: P1
    surface: [runtime_files]
    evidence_kind: malformed_input_test
    evidence_ref: evidence/grade/no_panic.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('panic/no-panic audit requires evidence_kind', '\n'.join(p['grade_lint']['errors']))


    def test_block_scalar_optional_hint_is_rejected(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    concurrency_or_locking: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-BLOCK-SCALAR
    severity: P1
    surface: [concurrency_or_locking]
    statement: Concurrent writes must not lose updates.
    verification_hint: >
      optional future follow-up; not reachable in current validation
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: block-scalar
    acceptance_id: ADV-BLOCK-SCALAR
    status: pass
    severity_if_fail: P1
    surface: [concurrency_or_locking]
    evidence_kind: concurrency_test
    evidence_ref: evidence/grade/concurrency.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('verification_hint makes current validation optional', '\n'.join(p['grade_lint']['errors']))

    def test_no_panic_audit_rejects_grep_only_in_evidence_ref(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    runtime_files: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-NO-PANIC-GREP-REF
    severity: P1
    surface: [runtime_files]
    statement: no-panic path: malformed runtime files must not panic through unwrap or expect.
    verification_hint: audit implicit panic paths and run malformed file probe
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: no-panic-grep-ref
    acceptance_id: ADV-NO-PANIC-GREP-REF
    status: pass
    severity_if_fail: P1
    surface: [runtime_files]
    evidence_kind: panic_audit
    evidence_ref: grep -R panic found no hits
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('panic/no-panic audit cannot be mere grep', '\n'.join(p['grade_lint']['errors']))



    def test_no_panic_audit_rejects_grep_only_in_summary(self):
        outcome="""# Outcome
```yaml
risk_surface:
  surfaces:
    runtime_files: {present: true}
```
```yaml
adversarial_acceptance:
  - id: ADV-NO-PANIC-SUMMARY
    severity: P1
    surface: [runtime_files]
    statement: no-panic path: malformed runtime files must not panic through unwrap or expect.
    verification_hint: audit implicit panic paths and run malformed file probe
```
"""
        grade="""# Grade
```yaml
grade_summary: {p0_count: 0, p1_count: 0, p2_count: 0, adversarial_p0_count: 0, adversarial_p1_count: 0}
```
```yaml
acceptance_status:
  - {id: A1, status: pass, severity: P1}
```
```yaml
adversarial_checks:
  - id: no-panic-summary
    acceptance_id: ADV-NO-PANIC-SUMMARY
    status: pass
    severity_if_fail: P1
    surface: [runtime_files]
    evidence_kind: panic_audit
    summary: grep -R panic found no hits
    evidence_ref: evidence/grade/no_panic.log
```
```yaml
trust_surface_inventory:
  unverified_items: []
```
```yaml
deferred_claims: []
```
"""
        proc,p=self.run_lint(grade=grade,outcome=outcome)
        self.assertEqual(proc.returncode,1)
        self.assertIn('panic/no-panic audit cannot be mere grep', '\n'.join(p['grade_lint']['errors']))

if __name__=='__main__': unittest.main()
