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
        self.assertEqual(proc.returncode,0,p)

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
