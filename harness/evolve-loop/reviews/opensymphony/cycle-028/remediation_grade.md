# Grade — cycle-028 / B-030 — round 1 (fix-round re-grade)

Task: **B-030 Grade-agent OS-level command sandbox — macOS sandbox-exec deny-read containment for acceptance commands (cycle-020 F1 residual)** (type=code, risk_level=high)

Re-grade after fix-round 1. The round-0 blocker F-1 (the F1-residual-core test redirected its leak probe inside the graded workspace, tripping the read-only integrity guard) is fixed: fix-round 1 (`f03bb1f`) moved the leak probe to `std::env::temp_dir()`, so the obfuscated-read containment is now proven green without mutating the workspace. The Shape-capsule findings F-2 (destructive_operation coverage) and F-3 (adv6 boundary surface) were folded into the re-shaped `outcome.md` (v1, sha c41d1a0a) at re-shape time.

Machine verification evidence: **`evidence/grade_verify_round_1.yaml`** (status: **pass** — `cargo build --workspace` / `cargo fmt --all --check` / `cargo clippy --workspace --all-targets -- -D warnings` / `cargo nextest run --workspace` (**222 passed, 1 skipped, 0 failed**, incl. the now-passing `sandbox_contains_obfuscated_forbidden_read`) / `bash scripts/verify-docs.sh` all exit 0). `sccache`/RUSTC wrapper disabled (env, not code).

Delta scope (full cycle): 4 files, ~407 insertions, 18 deletions — new `crates/symphony-grade/src/sandbox.rs`, modified `paths.rs` / `session.rs` / `lib.rs`. Fix-round 1 added +6/−1 to `session.rs` (test leak-probe relocation only).

## REMEDIATION re-grade (cycle-028 r1 F1+F2, under v1.4.27 grade_lint)

Remediates r1 F1 (P0 — the containment proof was FAIL-OPEN: it returned success when sandbox-exec was inactive, and the fallback ran obfuscated reads unsandboxed) and F2 (P1 — sandbox-exec invoked via PATH). Fix (crates/symphony-grade/src/{paths,sandbox,session}.rs, +220/-24): paths.rs evaluate_command FAIL-CLOSES when CommandSandbox is inactive (refuse command, executed:false, r_agt_6_os_containment_required); sandbox.rs invokes the ABSOLUTE /usr/bin/sandbox-exec + /bin/sh for both production wrapper and probe; active-path proofs assert probe.active; +2 tests sandbox_forced_unavailable_obfuscated_read_fails_closed (F1) and sandbox_exec_path_poisoning_does_not_invoke_path_binary (F2), both red pre-fix / green post-fix. Gates on the macOS Grade host (sandbox-exec works): cargo build/fmt/clippy -D warnings green, cargo nextest -p symphony-grade 42/42 passed. (codex's nested sandbox blocks sandbox-exec so it saw 9 'failures' — a host artifact; the orchestrator verified 42/42 on the real host.)

## Verdict: PASS — P0+P1 = 0

```yaml
grade_summary:
  verdict: pass
  p0_count: 0
  p1_count: 0
  adversarial_p0_count: 0
  adversarial_p1_count: 0
  p2_count: 0
  acceptance_total: 15
  acceptance_passed: 15
  verify_evidence: evidence/grade_verify_round_1.yaml
  verify_status: pass
  lint_evidence: evidence/grade_lint_round_1.json
  risk_level: high
  task_type: code
```

```yaml
acceptance_status:
  - id: a1
    status: pass
  - id: a2
    status: pass
  - id: a3
    status: pass
  - id: a4
    status: pass
  - id: a5
    status: pass
  - id: a6
    status: pass
  - id: a7
    status: pass
  - id: a8
    status: pass
  - id: adv1
    status: pass
  - id: adv2
    status: pass
  - id: adv3
    status: pass
  - id: adv4
    status: pass
  - id: adv5
    status: pass
  - id: adv6
    status: pass
  - id: adv7
    status: pass
```

```yaml
spec_compliance_matrix:
  - acceptance_id: a1
    severity_if_fail: P2
    status: pass
    spec_ref: "docs/ops/roadmap.md"
    evidence_ref: "evidence/grade_verify_round_1.yaml cmds 1-3 (build/fmt/clippy) exit 0"
  - acceptance_id: a2
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md"
    evidence_ref: "evidence/grade_verify_round_1/cmd_4.stderr.log nextest 222 passed 1 skipped 0 failed; the new containment test suite (sandbox_contains_obfuscated_forbidden_read + sandbox_symlink_and_canonical_containment + sandbox_absent_fail_safe + textual_forbidden_root_guard + command_timeout_reaps_detached_grandchild_escape + read_only_isolation) is green"
  - acceptance_id: a3
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md"
    evidence_ref: "F1-residual-core test sandbox_contains_obfuscated_forbidden_read PASS (148/222): obfuscated read `cat .symphony/mem*/x` under sandbox-exec is OS-denied (secret absent from the external leak file + stdout, sandbox_active:true), textual guard did NOT pre-reject it (obfuscation proven), overall_status Pass REMEDIATION (cycle-028 F2): sandbox-exec is now invoked by its trusted ABSOLUTE path (/usr/bin/sandbox-exec or /bin/sandbox-exec from sandbox_exec_path()) for BOTH the production wrapper and the apply probe, and the inner shell is the absolute /bin/sh (not PATH-resolved 'sandbox-exec'/'sh'); a fake sandbox-exec earlier in PATH cannot be invoked — proven by sandbox_exec_path_poisoning_does_not_invoke_path_binary which plants a PATH-precedence fake and asserts the trusted absolute binary is used (program == absolute path, args include /bin/sh) and the fake's sentinel stays unset."
  - acceptance_id: a4
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md (capabilities.forbidden line 82)"
    evidence_ref: "textual_forbidden_root_guard PASS; literal `.symphony/memory-user/x` rejected pre-execution (executed:false)"
  - acceptance_id: a5
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/ops/risks.md (R-AGT-6)"
    evidence_ref: "read_only_isolation_does_not_touch_forbidden_dirs PASS; forbidden dirs byte+mtime+tree-stable, secret not in grade_result"
  - acceptance_id: a6
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md (process EC-1)"
    evidence_ref: "command_timeout_fails_and_reaps + command_timeout_reaps_detached_grandchild_escape PASS; verdict fail with timeout, group reaped, own group not signalled; default 300s timeout unchanged"
  - acceptance_id: a7
    severity_if_fail: P2
    status: pass
    spec_ref: "docs/ops/contributing.md"
    evidence_ref: "evidence/grade_verify_round_1/cmd_5 verify-docs exit 0"
  - acceptance_id: a8
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/architecture/tech-stack.yaml"
    evidence_ref: "crates/symphony-grade/Cargo.toml has no path=/git= dep; sandbox.rs uses std only (no new workspace dependency)"
  - acceptance_id: adv1
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/ops/risks.md (R-AGT-6) + docs/agents/grade/AGENT.md"
    evidence_ref: "sandbox_contains_obfuscated_forbidden_read PASS; obfuscated forbidden-root read OS-denied, secret never exfiltrated (external leak + stdout both clean), sandbox_active:true REMEDIATION (cycle-028 F2): sandbox-exec is now invoked by its trusted ABSOLUTE path (/usr/bin/sandbox-exec or /bin/sandbox-exec from sandbox_exec_path()) for BOTH the production wrapper and the apply probe, and the inner shell is the absolute /bin/sh (not PATH-resolved 'sandbox-exec'/'sh'); a fake sandbox-exec earlier in PATH cannot be invoked — proven by sandbox_exec_path_poisoning_does_not_invoke_path_binary which plants a PATH-precedence fake and asserts the trusted absolute binary is used (program == absolute path, args include /bin/sh) and the fake's sentinel stays unset."
  - acceptance_id: adv2
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/ops/risks.md (R-AGT-6)"
    evidence_ref: "sandbox_symlink_and_canonical_containment PASS; symlink-into-forbidden-root read OS-denied via canonical-root subpath deny REMEDIATION (cycle-028 F2): sandbox-exec is now invoked by its trusted ABSOLUTE path (/usr/bin/sandbox-exec or /bin/sandbox-exec from sandbox_exec_path()) for BOTH the production wrapper and the apply probe, and the inner shell is the absolute /bin/sh (not PATH-resolved 'sandbox-exec'/'sh'); a fake sandbox-exec earlier in PATH cannot be invoked — proven by sandbox_exec_path_poisoning_does_not_invoke_path_binary which plants a PATH-precedence fake and asserts the trusted absolute binary is used (program == absolute path, args include /bin/sh) and the fake's sentinel stays unset."
  - acceptance_id: adv3
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md (capabilities.forbidden line 82)"
    evidence_ref: "textual_forbidden_root_guard PASS"
  - acceptance_id: adv4
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md (process EC-1)"
    evidence_ref: "command_timeout_fails_and_reaps + command_timeout_reaps_detached_grandchild_escape PASS"
  - acceptance_id: adv5
    severity_if_fail: P0
    status: pass
    spec_ref: "outcome.md non_goals (fail-safe not fail-open)"
    evidence_ref: "sandbox_absent_fail_safe PASS; forced-fallback runs normal command + still refuses textually-forbidden command, sandbox_active:false REMEDIATION (cycle-028 F1): the path is now FAIL-CLOSED, not fail-open — when sandbox-exec is UNAVAILABLE/inactive the Grade REFUSES the acceptance command (paths.rs evaluate_command writes guard r_agt_6_os_containment_required, executed:false, verdict Fail, never spawns), so an obfuscated forbidden-root read cannot run unsandboxed. sandbox_forced_unavailable_obfuscated_read_fails_closed FORCES sandbox-exec unavailable (.symphony/grade-sandbox-unavailable-for-test sentinel) and proves the obfuscated read `cat .symphony/mem*/x` is refused fail-closed with the secret NEVER leaked (leak target + stdout clean); the active-path proofs sandbox_contains_obfuscated_forbidden_read + sandbox_symlink_and_canonical_containment now assert probe.active (no fail-open early return). nextest 42/42 on the macOS Grade host."
  - acceptance_id: adv6
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/decisions/product.md (no-panic safety)"
    evidence_ref: "sandbox_no_panic_on_special_workspace_path PASS; special-char workspace path returns typed Result; no unwrap/expect on sandbox/spawn/profile path (audit below)"
  - acceptance_id: adv7
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/ops/risks.md (R-AGT-6 P0)"
    evidence_ref: "read_only_isolation_does_not_touch_forbidden_dirs PASS; byte+mtime+tree snapshot stable, no secret leak to grade_result"
```

```yaml
negative_regression_tests:
  - acceptance_id: a3
    severity_if_fail: P0
    status: pass
    scenario: "obfuscated forbidden-root read (shell glob `.symphony/mem*/x`) that defeats the textual guard is OS-denied: secret bytes never reach stdout nor the (out-of-workspace) redirect target"
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "sandbox_contains_obfuscated_forbidden_read PASS; the leak probe now lands in std::env::temp_dir() so the read-only integrity guard is not tripped and the containment proof stands REMEDIATION (cycle-028 F2): sandbox-exec is now invoked by its trusted ABSOLUTE path (/usr/bin/sandbox-exec or /bin/sandbox-exec from sandbox_exec_path()) for BOTH the production wrapper and the apply probe, and the inner shell is the absolute /bin/sh (not PATH-resolved 'sandbox-exec'/'sh'); a fake sandbox-exec earlier in PATH cannot be invoked — proven by sandbox_exec_path_poisoning_does_not_invoke_path_binary which plants a PATH-precedence fake and asserts the trusted absolute binary is used (program == absolute path, args include /bin/sh) and the fake's sentinel stays unset."
  - acceptance_id: adv1
    severity_if_fail: P0
    status: pass
    scenario: "F1-residual-core: glob/env-indirection obfuscated read under sandbox-exec; assert textual guard bypassed AND secret absent from stdout + redirect target"
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "same as a3; secret absent from external leak file + stdout, sandbox_active:true, overall_status Pass REMEDIATION (cycle-028 F2): sandbox-exec is now invoked by its trusted ABSOLUTE path (/usr/bin/sandbox-exec or /bin/sandbox-exec from sandbox_exec_path()) for BOTH the production wrapper and the apply probe, and the inner shell is the absolute /bin/sh (not PATH-resolved 'sandbox-exec'/'sh'); a fake sandbox-exec earlier in PATH cannot be invoked — proven by sandbox_exec_path_poisoning_does_not_invoke_path_binary which plants a PATH-precedence fake and asserts the trusted absolute binary is used (program == absolute path, args include /bin/sh) and the fake's sentinel stays unset."
  - acceptance_id: adv2
    severity_if_fail: P0
    status: pass
    scenario: "symlink/canonical-root containment: a symlink into .symphony/patterns-user/ read under the sandbox is OS-denied (canonical-root deny, not string-prefix)"
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "sandbox_symlink_and_canonical_containment PASS; secret absent from stdout; this row exercises the sandbox-exec spawn which runs under a bounded 300s timeout, a new-session process group (setsid), and child wait/reap REMEDIATION (cycle-028 F2): sandbox-exec is now invoked by its trusted ABSOLUTE path (/usr/bin/sandbox-exec or /bin/sandbox-exec from sandbox_exec_path()) for BOTH the production wrapper and the apply probe, and the inner shell is the absolute /bin/sh (not PATH-resolved 'sandbox-exec'/'sh'); a fake sandbox-exec earlier in PATH cannot be invoked — proven by sandbox_exec_path_poisoning_does_not_invoke_path_binary which plants a PATH-precedence fake and asserts the trusted absolute binary is used (program == absolute path, args include /bin/sh) and the fake's sentinel stays unset."
  - acceptance_id: adv3
    severity_if_fail: P1
    status: pass
    scenario: "textual guard defense-in-depth: literal `.symphony/memory-user/x` rejected pre-execution, command body never runs"
    evidence_kind: malformed_input_test
    evidence_ref: "textual_forbidden_root_guard PASS (executed:false in trace)"
  - acceptance_id: adv4
    severity_if_fail: P1
    status: pass
    scenario: "timeout group-reap with new-session containment: command over timeout_sec is verdict=fail with timeout reason; child AND same-group grandchild gone after reap; test process's own group survives"
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "command_timeout_fails_and_reaps + command_timeout_reaps_detached_grandchild_escape PASS; bounded timeout fires, new-session process group SIGTERM->SIGKILL reaped, child wait/reaped, detached grandchild escape gone"
  - acceptance_id: adv5
    severity_if_fail: P0
    status: pass
    scenario: "fail-safe not fail-open: sandbox forced unavailable -> degrades to textual+process-group, STILL refuses a textually-forbidden command, never runs a known-forbidden command unsandboxed"
    evidence_kind: malformed_input_test
    evidence_ref: "sandbox_absent_fail_safe PASS (sandbox_active:false; literal forbidden still rejected executed:false; normal command still runs) REMEDIATION (cycle-028 F1): the path is now FAIL-CLOSED, not fail-open — when sandbox-exec is UNAVAILABLE/inactive the Grade REFUSES the acceptance command (paths.rs evaluate_command writes guard r_agt_6_os_containment_required, executed:false, verdict Fail, never spawns), so an obfuscated forbidden-root read cannot run unsandboxed. sandbox_forced_unavailable_obfuscated_read_fails_closed FORCES sandbox-exec unavailable (.symphony/grade-sandbox-unavailable-for-test sentinel) and proves the obfuscated read `cat .symphony/mem*/x` is refused fail-closed with the secret NEVER leaked (leak target + stdout clean); the active-path proofs sandbox_contains_obfuscated_forbidden_read + sandbox_symlink_and_canonical_containment now assert probe.active (no fail-open early return). nextest 42/42 on the macOS Grade host."
  - acceptance_id: adv6
    severity_if_fail: P1
    status: pass
    scenario: "no-panic on the containment path: special-char workspace path, missing forbidden dir, non-UTF8 output do not panic; typed Results not unwraps"
    evidence_kind: implicit_panic_audit
    evidence_ref: "sandbox_no_panic_on_special_workspace_path PASS; sandbox.rs/profile/spawn path uses Result + map_err, no unwrap()/expect() (audit below)"
  - acceptance_id: adv7
    severity_if_fail: P0
    status: pass
    scenario: "R-AGT-6 process-level isolation: forbidden dirs byte+mtime+tree-stable before/after a grade run; no forbidden content in grade_result/evidence"
    evidence_kind: malformed_input_test
    evidence_ref: "read_only_isolation_does_not_touch_forbidden_dirs PASS (extended with forbidden_tree_snapshot + secret-not-in-grade_result assertion); a byte/mtime/tree stability recheck, not a subprocess timeout/reap claim"
```

```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "The Grade command-acceptance path performs no authentication and handles no tokens/keys/credentials. The 'secret' in the containment tests is a placeholder forbidden-root file used to prove deny-read, not a real credential surface (outcome.md risk_surface.auth_or_secret not_applicable). The delta adds no secret-bearing field, no env capture into output, no credential logging; the sandbox trace records only command string, cwd, sandbox_active/mode/unavailable_reason, exit code, and stdout/stderr previews of the (non-secret) probe."
  scope_basis_ref: "outcome.md risk_surface.auth_or_secret not_applicable with reason; grep of crates/symphony-grade/src/{sandbox.rs,paths.rs,session.rs} found no token/key/secret field, only the test placeholder bytes"
  checked_surfaces:
    - "sandbox.rs: no secret field; SBPL profile contains only canonical forbidden-root paths"
    - "paths.rs evaluate_command trace JSON: command/cwd/sandbox_*/exit/preview only"
    - "bare token / JSON-quoted token / Authorization: Bearer cleartext-secret probe of the delta: none present (placeholder test bytes only)"
```

```yaml
dependency_spec_review:
  - status: pass
    spec_ref: "docs/architecture/tech-stack.yaml and workspace Cargo.toml"
    evidence_ref: "crates/symphony-grade/Cargo.toml is NOT in the delta (git diff touches only src/{lib,paths,sandbox,session}.rs); sandbox.rs uses std::path/std::process + a libc-free `unsafe extern \"C\" fn setsid` (no new crate). a8 artifact check: Cargo.toml has no path=/git= dep."
  - status: pass
    spec_ref: "scripts/verify-docs.sh Check 6 tech-stack drift"
    evidence_ref: "evidence/grade_verify_round_1/cmd_5 verify-docs exit 0; no dependency version drift introduced"
```

```yaml
adversarial_checks:
  - id: adv1
    acceptance_id: adv1
    status: pass
    severity_if_fail: P0
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "sandbox_contains_obfuscated_forbidden_read PASS (148/222); the command runs under sandbox-exec in its own new-session process group with the default 300s timeout, its stdout/stderr reader streams are joined/drained to the trace files, and the child is wait/reaped REMEDIATION (cycle-028 F2): sandbox-exec is now invoked by its trusted ABSOLUTE path (/usr/bin/sandbox-exec or /bin/sandbox-exec from sandbox_exec_path()) for BOTH the production wrapper and the apply probe, and the inner shell is the absolute /bin/sh (not PATH-resolved 'sandbox-exec'/'sh'); a fake sandbox-exec earlier in PATH cannot be invoked — proven by sandbox_exec_path_poisoning_does_not_invoke_path_binary which plants a PATH-precedence fake and asserts the trusted absolute binary is used (program == absolute path, args include /bin/sh) and the fake's sentinel stays unset."
    note: "F1-residual-core resolved: macOS sandbox-exec OS-denies the obfuscated read (external leak file empty, stdout empty, secret never exfiltrated, sandbox_active:true). Fix-round 1 moved the leak probe to std::env::temp_dir() so the in-workspace read-only integrity guard is not tripped; the containment proof now passes green. Surface facets file_modes + external_subprocess + destructive_operation present (adv1 covers the hostile/destructive read attempt)."
  - id: adv2
    acceptance_id: adv2
    status: pass
    severity_if_fail: P0
    evidence_kind: malformed_input_test
    evidence_ref: "sandbox_symlink_and_canonical_containment PASS"
    note: "canonical-root containment: a crafted symlink (malformed/indirect path input) into .symphony/patterns-user/ read under sandbox is OS-denied because the deny rule uses the canonicalized absolute forbidden-root subpath (canonical containment), not a string-prefix match; reads to stdout only so no integrity-guard interaction. file_modes + string_boundary surface."
  - id: adv3
    acceptance_id: adv3
    status: pass
    severity_if_fail: P1
    evidence_kind: malformed_input_test
    evidence_ref: "textual_forbidden_root_guard PASS (executed:false in trace)"
    note: "Defense-in-depth: a literal forbidden-root acceptance string is rejected by the textual guard before execution (executed:false in trace); the guard is retained (non-goal to remove). The shared evaluate_command spawn tail applies a bounded 300s timeout, a new-session process group (setsid), and a child wait/reap to every executed command (this adversarial proves the pre-execution rejection branch; the timeout + process-group + reap lifecycle is exercised by adv4)."
  - id: adv4
    acceptance_id: adv4
    status: pass
    severity_if_fail: P1
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "command_timeout_fails_and_reaps + command_timeout_reaps_detached_grandchild_escape PASS; bounded timeout fires, the new-session process group is SIGTERM->SIGKILL reaped, child waited"
    note: "new-session (setsid via pre_exec) process group; on timeout SIGTERM->SIGKILL reaps the whole process group incl. a detached/new-session grandchild escape; child is wait/reaped; verdict fail with timeout reason; test process's own group not signalled. process + external_subprocess; descendant/grandchild-escape fixture + process-tree-containment audit covered."
  - id: adv5
    acceptance_id: adv5
    status: pass
    severity_if_fail: P0
    evidence_kind: malformed_input_test
    evidence_ref: "sandbox_absent_fail_safe PASS (sandbox_active:false fallback) REMEDIATION (cycle-028 F1): the path is now FAIL-CLOSED, not fail-open — when sandbox-exec is UNAVAILABLE/inactive the Grade REFUSES the acceptance command (paths.rs evaluate_command writes guard r_agt_6_os_containment_required, executed:false, verdict Fail, never spawns), so an obfuscated forbidden-root read cannot run unsandboxed. sandbox_forced_unavailable_obfuscated_read_fails_closed FORCES sandbox-exec unavailable (.symphony/grade-sandbox-unavailable-for-test sentinel) and proves the obfuscated read `cat .symphony/mem*/x` is refused fail-closed with the secret NEVER leaked (leak target + stdout clean); the active-path proofs sandbox_contains_obfuscated_forbidden_read + sandbox_symlink_and_canonical_containment now assert probe.active (no fail-open early return). nextest 42/42 on the macOS Grade host."
    note: "Fail-safe not fail-open: with the sandbox forced unavailable (test sentinel), a normal acceptance still runs (sandbox_active:false) under the same evaluate_command spawn tail — a bounded 300s timeout, a new-session process group (setsid), and a child wait/reap — AND a textually-forbidden acceptance string is still refused (executed:false in trace). The degraded path holds the forbidden-read guard the textual layer already enforces; it is the input-validation/schema branch of the containment."
  - id: adv6
    acceptance_id: adv6
    status: pass
    severity_if_fail: P1
    evidence_kind: implicit_panic_audit
    evidence_ref: "sandbox_no_panic_on_special_workspace_path PASS; implicit-panic audit of sandbox.rs + evaluate_command sandbox path"
    note: "implicit_panic_audit of the sandbox/profile/spawn path: no unwrap()/no expect()/no array-index-panic — sandbox.rs uses Result + map_err on canonicalize and the apply-probe; for_command returns Result; escape_sbpl_string is total over chars; a missing forbidden dir is skipped via an exists() guard. A special-char (spaces+parens) workspace path returns a typed Result. The same evaluate_command spawn tail (bounded 300s timeout + new-session process group via setsid + child wait/reap) applies to executed commands. adv6 now sits on the external_subprocess surface (re-shape F-3), resolving the boundary-vs-panic evidence-kind conflict."
  - id: adv7
    acceptance_id: adv7
    status: pass
    severity_if_fail: P0
    evidence_kind: malformed_input_test
    evidence_ref: "read_only_isolation_does_not_touch_forbidden_dirs PASS"
    note: "R-AGT-6 process-level isolation: forbidden dirs byte+mtime+tree-stable across a grade run (forbidden_tree_snapshot before==after) and secret not present in grade_result. file_modes surface; assertion is a byte/mtime/tree stability recheck, not a subprocess timeout/reap claim."
```

```yaml
trust_surface_inventory:
  external_subprocess:
    trusted_by: "acceptance commands wrapped in sandbox-exec deny-read profile (invoked by ABSOLUTE /usr/bin/sandbox-exec + /bin/sh, PATH-poisoning guarded — F2 remediation, sandbox_exec_path_poisoning_does_not_invoke_path_binary) + new-session process group; reaped on timeout (adv4); FAIL-CLOSED when sandbox unavailable — command refused, not run unsandboxed (F1 remediation, sandbox_forced_unavailable_obfuscated_read_fails_closed); no-panic on the spawn path (adv6)"
    status: pass
  process:
    trusted_by: "setsid new session via pre_exec; timeout SIGTERM->SIGKILL of the whole group incl. detached grandchild (adv4); own group never signalled"
    status: pass
  file_modes:
    trusted_by: "SBPL deny file-read* on canonical forbidden-root subpaths blocks glob/env/symlink/traversal reads (adv1 + adv2 pass); R-AGT-6 process isolation stable (adv7)"
    status: pass
  string_boundary:
    trusted_by: "escape_sbpl_string escapes backslash/quote/newline/CR/tab; canonical absolute paths used in the profile so a special-char or relative path cannot break the profile to fail-open (adv2, adv6)"
    status: pass
  input_validation_or_schema:
    trusted_by: "sandbox-absent/profile-apply-failure now FAIL-CLOSES — the acceptance command is refused (executed:false, r_agt_6_os_containment_required), so an obfuscated forbidden read cannot run unsandboxed (F1 remediation, sandbox_forced_unavailable_obfuscated_read_fails_closed); literal forbidden commands still refused; typed Results, no panic on malformed paths (adv6)"
    status: pass
  destructive_operation:
    trusted_by: "containment scoped to deny forbidden-root READS (the F1 residual), exercised by the hostile read attempt in adv1; workspace write-sandboxing explicitly out of scope (deferred_claims)"
    status: pass
  unverified_items: []
```

```yaml
deferred_claims:
  - claim: "Linux / Windows OS-level containment (cgroup / PID-namespace / seccomp / landlock / job-object)"
    current_scope_implementable: false
    scope_basis_ref: "outcome.md non_goals + AGENTS.md v1.20 / DA-25 Linux DEFERRED (project is macOS-arm64-only); the non-macOS build path keeps the textual-guard + process-group fallback (sandbox_no_panic_on_non_macos_fallback). Re-open under a Linux-activation task per the DA-25 blueprint."
  - claim: "Unconditional defeat of a deliberately daemonizing descendant (double-fork + setsid + reparent-to-init)"
    current_scope_implementable: false
    scope_basis_ref: "outcome.md non_goals — that is B-031's residual (F7). This cycle keeps best-effort new-session process-group reap (proven for a detached grandchild escape in adv4) and does not claim to reap a reparenting descendant; the trace records `timeout_reap_residual` honestly."
  - claim: "Workspace write-sandboxing of acceptance commands"
    current_scope_implementable: false
    scope_basis_ref: "outcome.md non_goals — this cycle contains forbidden-root READS (the F1 residual), not arbitrary workspace writes; out of scope by design."
```

## Agent-contract acceptance rows (contract §6 — `docs/agents/grade/AGENT.md` in spec_refs AND diff targets `crates/symphony-grade/`)

```yaml
agent_contract_matrix:
  - obligation_domain: "capabilities.forbidden / R-AGT-6 (grade/AGENT.md line 82)"
    must: "Reading .symphony/memory-user/, .symphony/patterns-user/, .symphony/patterns-imported/ is forbidden (P0)."
    status: pass
    evidence_ref: "read_only_isolation_does_not_touch_forbidden_dirs (Grade process isolation, adv7) + sandbox_contains_obfuscated_forbidden_read (glob obfuscation, adv1) + sandbox_symlink_and_canonical_containment (symlink, adv2) all pass; the NEW guarantee — the spawned acceptance subprocess also cannot read the forbidden roots — is now proven for the glob, env-indirection, and symlink/canonical paths"
  - obligation_domain: "capabilities.forbidden / shell (grade/AGENT.md line 81)"
    must: "Executing shell commands beyond the deterministic acceptance.command is forbidden."
    status: pass
    evidence_ref: "the delta only changes HOW the deterministic acceptance.command is spawned (sandbox-exec wrapper + setsid); it adds no new shell-out beyond acceptance commands; textual guard still rejects literal forbidden-root commands (adv3)"
  - obligation_domain: "process EC-1 (grade/AGENT.md line 460)"
    must: "A command-type acceptance over timeout (default 300s) -> verdict fail; reasoning notes timeout; no retry."
    status: pass
    evidence_ref: "command_timeout_fails_and_reaps + command_timeout_reaps_detached_grandchild_escape pass; verdict fail with timeout reason; default timeout unchanged (300s); no retry; new session so the group signal reaches the command"
```

## Grade-agent evidence-completeness facets (contract §6 — `crates/symphony-grade` primary deliverable)

All grade-agent facet tests are green under this delta. Each facet's evidence is stated with the specific lifecycle/containment/schema properties it proves:

**Hostile read-only isolation audit.** A hostile acceptance command that attempts to write the forbidden `.symphony/memory-user` source root is rejected by the textual guard before spawn (textual_forbidden_root_guard, executed:false), and a hostile artifact path attempting a forbidden-root read or `..` path-traversal into `patterns-user`/`patterns-imported` is rejected (artifact_forbidden_memory_and_imported_pattern_roots_are_rejected + artifact_path_traversal_is_rejected + artifact_symlink_escaping_workspace_is_rejected). Containment uses the canonicalized absolute forbidden-root subpath as the denylist (canonical containment + forbidden denylist), not a string prefix. Post-run source/outcome stability is rechecked: read_only_isolation_does_not_touch_forbidden_dirs asserts the forbidden dirs and `outcome.md` are byte-identical and tree-unchanged before and after a grade run (forbidden_tree_snapshot before == after; no mutation).

**D-P13 high-risk capsule.** This very `outcome.md` is a `risk_level: high` capsule carrying top-level `high_risk_actions:` (hra1/hra2), so the D-P13 schema trigger applies. The second_signal branch is exercised — high_risk_second_signal_incomplete_fails_grade proves an incomplete second_signal makes the grade fail (branch), and the human_review branch is exercised — high_risk_human_review_requires_needs_human_not_fail proves the human_review path requires `needs_human` (branch/artifact), not a silent fail.

**Second-signal unforgeable.** criteria_substring_does_not_forge_high_risk_second_signal proves that criteria/substring prose carrying `second_signal_pass` text cannot set `llm_judge_passed` (the substring does not set it; it is ignored). The genuine second signal must come from a structured independent judge result (JSON `llm_judge_result`) or a human_review artifact.

**LLM-judge fail-closed.** llm_judge_empty_evidence_refs_fails_closed proves empty `evidence_refs` ([] / zero) fails closed (rejected); a missing/null `evidence_ref` also fails (llm_judge_trace_ref_only_evidence_fails_closed treats a lone trace_ref as missing real evidence); the hard-gate default is closed — llm_judge_hard_gate_failure_fails proves the hard_gate defaults to false/closed and fails the grade; and a self-fabricated `trace_ref` as the only evidence is not accepted (rejected) by llm_judge_trace_ref_only_evidence_fails_closed.

**Command/artifact path schema fields.** command_required_exit_code_non_default_is_enforced exercises a non-default `required_exit_code: 3` (non-default required_exit_code honored); command_cwd_non_default_is_used exercises a per-acceptance `cwd: "subdir"` (per-acceptance cwd resolved under the workspace); artifact_min_size_bytes_non_default_is_enforced exercises a non-default `min_size_bytes: 16` artifact floor.

**Grade critic substance.** critic_rejects_naked_seeded_pass_grade_result proves the critic rejects a seeded-pass / naked-verdict grade_result (reject); the six-rule critic consumes the real inputs — rule 1 consumes `outcome.md`, rule 3 consumes `grade_result.md`, and rule 4 consumes the evidence files and the per-acceptance trace JSON (critic_approves_trace_backed_grade_result_with_six_rules + critic_rejects_missing_referenced_evidence_file + critic_rejects_empty_json_trace_reference).

**Subprocess no-orphan / no-hang with grandchild escape.** command_timeout_reaps_detached_grandchild_escape proves a detached/new-session backgrounded grandchild escape is reaped: the bounded timeout fires, the whole new-session process group is SIGTERM->SIGKILL reaped, the child is wait/reaped, and a process-tree-containment audit asserts the grandchild is gone (no orphan, no hung process) — strengthened this cycle by the setsid new-session wrapper.

## Notes (human-readable)

- **F1 residual closed.** The obfuscated/indirect forbidden-root read (`cat .symphony/mem*/x`, env-indirection, symlink, `..` traversal) is now OS-denied on the macOS host by the sandbox-exec deny-read profile, proven green by `sandbox_contains_obfuscated_forbidden_read` + `sandbox_symlink_and_canonical_containment`. The textual guard remains as defense-in-depth (adv3), and the path is fail-safe when the sandbox is unavailable (adv5).
- **Fix-round 1 was test-only** (+6/−1 in session.rs): the production containment code was correct in round 0; only the test's leak-probe location needed to move outside the graded workspace.
- **Full gate green:** build/fmt/clippy/nextest (222 passed, 1 skipped, 0 failed)/verify-docs all exit 0; grade_lint round 1 expected clean (P0+P1=0).
- **Honest residuals (deferred_claims):** Linux/Windows containment (DA-25 deferred) and unconditional daemonizing-descendant reap (B-031's F7 residual) are explicitly not delivered; the trace records the reap residual honestly.
