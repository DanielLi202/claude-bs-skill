# Grade — cycle-029 / B-031 remediation (post-merge security fix of r1 F1+F2)

> **Remediation grade (post-merge)** — the bs-evolve-loop r1 security review of merged cycle-029 found two P0 escapes in the timeout reaper that the heavy adversarial Grade let through: **F1** — `block_contains_marker` did a raw byte-window SUBSTRING search over the KERN_PROCARGS2 argv+env block, so a process that merely mentioned `SYMPHONY_GRADE_CONTAINMENT_ID=<id>` in its **argv** or inside **another env var's value** (`OTHER=…<id>…`) was matched and signalled; **F2** — the kill path collected matching pids into a `Vec<u32>` and `kill()`'d them LATER without re-reading the marker, a PID-reuse TOCTOU that could SIGKILL a recycled-pid innocent. This grade re-verifies the security remediation on branch `remediate/cycle-029` (commit `2bb4dac`): F1 is now an exact NUL-delimited env-ENTRY match (argv skipped via the leading `argc`; whole-entry equality), F2 re-reads and re-validates the exact marker entry immediately before EVERY signal, and two new tests prove the selector is selective (`marker_substring_decoy_survives`) and PID-identity stable (`pid_identity_stable`) while the F7 win (`daemonizing_descendant_reaped_on_timeout`) is preserved. Re-verified green on the real macOS host: `cargo nextest -p symphony-grade` 50/50, fmt --check exit 0, clippy -D warnings exit 0. The C2 source-judgment residual (the Rust selector/kill-path truth a text lint cannot inspect) stays `escalated_to_human` in closure.yaml.

**Task**: Grade-agent OS-level descendant containment — reap daemonizing (double-fork+setsid+reparent) descendants on acceptance-command timeout (cycle-020 F7 residual).
**Type**: code · **risk_level**: high · **agent-contract predicate**: TRIGGERED (`docs/agents/grade/AGENT.md` in spec_refs + diff targets `crates/symphony-grade/`).
**Worktree**: `/Users/lidongyuan/workspace/utils/os-worktrees/cycle-029` · **branch**: `bootstrap/cycle-029` · **start_commit**: `df85499`.
**Machine verify evidence (REQUIRED, cited)**: `evidence/grade_verify_round_1.yaml` → **status: pass** (cargo build / fmt --check / clippy -D warnings / nextest --workspace / verify-docs all exit 0; 230/230 tests, 1 skipped). The round-0 grade_verify ran under nextest DEFAULT parallelism and recorded `fail` from a pre-existing OUT-OF-SCOPE flaky `symphony-adapter` forced-timeout test (`codex_timeout_still_clears_goal_and_archives_thread`, NotFound on `transcript.jsonl` when its 3s budget landed in spawn/handshake under full-suite load; preserved at `evidence/grade_verify_round_0.attempt0_default_j.yaml`); it PASSES in isolation, the B-031 delta does NOT touch `symphony-adapter`, and the authoritative gate (round 0 re-run + round 1) is green with `NEXTEST_TEST_THREADS=4` (binding command string unchanged). See `trust_surface_inventory` row `flake`.

## What the delta does (independently reviewed, `evidence/git_diff.patch`)

The vendor modified `crates/symphony-grade/src/{paths.rs,sandbox.rs,session.rs}` (+452/-73). Core (`paths.rs`):
- **`new_containment_id()`** — fresh per-spawn unique token `{nanos:032x}-{pid:08x}-{counter:016x}` (std-only `AtomicU64` + `SystemTime`; no new crate).
- **`evaluate_command`** exports `command_proc.env("SYMPHONY_GRADE_CONTAINMENT_ID", id)` into the spawned acceptance command (inherited by every `execve` descendant incl. a reparented daemonizer), alongside the retained `configure_new_session` (setsid → new session / process group).
- **`terminate_timed_out_child(child, containment_id)`** keeps the legacy process-group + PPID-subtree reap AND adds `reap_containment_id` — a bounded (`Instant + max_duration` deadline) loop that scans the WHOLE process table (`containment_targets` over `process_parent_pairs`), filters `is_allowed_reap_target` (excludes pid≤1, own pid, AND own pgid) then `process_has_containment_marker`, and SIGTERM→SIGKILLs matches (timeout → process-group + descendant + identity reap; child wait/reaped). **F2 remediation**: `signal_pids`/`signal_pid_if_allowed` now RE-READS the candidate pid's env and re-confirms it STILL carries the exact marker entry immediately before EACH `kill()` (re-validate-before-kill); a pid that exited or was recycled to an unmarked process between the scan and the signal is SKIPPED — the PID-reuse TOCTOU is narrowed to the syscall gap and no unmarked process is ever signalled.
- **`process_argv_env(pid)`** — macOS `KERN_PROCARGS2` sysctl / Linux `/proc/<pid>/environ` / other-unix `Err`; **fail-safe** (any read error/truncation → Err → no-match).
- **`block_contains_marker`** — **F1 remediation**: was a raw byte-window SUBSTRING search over the whole KERN_PROCARGS2 argv+env block (matched argv mentions and `OTHER=…<id>…` other-env substrings); now an exact NUL-delimited **env-ENTRY** match. `macos_procargs2_env_start` parses the procargs2 header (`argc:i32` → skip exec_path → skip NUL pad → skip `argc` argv tokens) so an **argv** token can never match, then `env_block_contains_marker` does a whole-token equality (`env_entry == "SYMPHONY_GRADE_CONTAINMENT_ID=<id>"`) — `OTHER=…<id>…` and a key like `X_SYMPHONY_GRADE_CONTAINMENT_ID` no longer match (malformed/truncated block → false, no panic).
- **Trace/reason narrowed**: from "double-fork+setsid+reparent … not guaranteed reaped" → "full process-table exact containment-id reap" + `timeout_reap_residual: deferred_claim` limited to a descendant that **scrubs its env or re-execs** dropping the id.

`session.rs` adds the REAL daemonizing fixture `run_daemonizing_timeout` (Python `os.fork()` twice + `os.setsid()` + waits until `os.getppid()==1` + writes pid/ppid/pgid to `temp_dir()` OUTSIDE the workspace) driving the two P0 integration tests, plus a `#[cfg(all(target_os="macos", test))]`-only `allow_test_command_execution` sentinel so the timeout/reap tests spawn a real subtree via `/bin/sh -c` (sandbox-exec cannot nest in the build sandbox); `sandbox.rs` adds the matching `sandbox_direct_execution_allowed_by_workspace`, which under `not(test)` returns `false` (production read-containment intact).

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
  prior_round_blocking: 1
  resolution: "round-0 blocking P1 (capsule adv6 surface-tagging defect) resolved by the round-1 re-shape scoping capsule adv6 to surface external_subprocess only; reaper_no_panic + full gate stay green; P0+P1 strictly decreased 1 -> 0; no production-code change."
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
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/ops/roadmap.md"
    evidence_ref: "evidence/grade_verify_round_0.yaml cmds 1-3 (build/fmt/clippy -D warnings) exit 0"
  - acceptance_id: a2
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md"
    evidence_ref: "evidence/grade_verify_round_0.yaml cmd_4 nextest --workspace 230 passed 1 skipped 0 failed; the new containment suite (daemonizing_descendant_reaped_on_timeout + daemonizing_descendant_escaped_legacy_reap + command_timeout_fails_and_reaps + read_only_isolation + containment_id_is_unique_and_selective + reaper_never_signals_self_or_init + reap_match_fail_safe_on_unreadable_or_unmarked + reaper_no_panic + reap_loop_is_bounded) is green"
  - acceptance_id: a3
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md (process EC-1)"
    evidence_ref: "F7-residual-core test daemonizing_descendant_reaped_on_timeout PASS: a real double-fork+setsid+reparent-to-init grandchild is gone (process_exists==false) after the timeout reap; bounded timeout fires, the new-session process group is SIGTERM->SIGKILL reaped, the child is wait/reaped, and a full process-table descendant-audit identity scan contains the reparented grandchild (descendant_escape_fixture + descendant_audit_or_tree_containment)"
  - acceptance_id: a4
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md (process EC-1)"
    evidence_ref: "daemonizing_descendant_escaped_legacy_reap PASS: the grandchild's ppid==1 AND its pgid != the acceptance command process group at timeout, proving it escaped the new-session process group and the PPID subtree so the legacy timeout+process-group+wait/reap path could not reach it; the identity-tag full-table scan (descendant_audit_or_tree_containment) is what reaped it (descendant_escape_fixture)"
  - acceptance_id: a5
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md (process EC-1)"
    evidence_ref: "command_timeout_fails_and_reaps PASS: verdict=fail with timeout reason (no retry, EC-1); the spawned command runs in its own new session / process group (setsid) so the bounded timeout signal reaps the group; the Grade process's own process group is never signalled (test process survives wait/reap); grade_result asserts 'full process-table exact containment-id reap'"
  - acceptance_id: a6
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/ops/risks.md (R-AGT-6) + docs/agents/grade/AGENT.md (capabilities.forbidden line 82)"
    evidence_ref: "read_only_isolation_does_not_touch_forbidden_dirs PASS: forbidden roots byte+mtime+tree-stable before and after a grade run exercising the timeout/reap path; secret never in grade_result; the new reaper reads only the process table + per-pid argv/env, never the forbidden source/outcome roots (post_run source/outcome byte stability rechecked)"
  - acceptance_id: a7
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/ops/contributing.md"
    evidence_ref: "evidence/grade_verify_round_0.yaml cmd_5 verify-docs exit 0"
  - acceptance_id: a8
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/architecture/tech-stack.yaml"
    evidence_ref: "crates/symphony-grade/Cargo.toml is NOT in the delta (git diff touches only src/{paths,sandbox,session}.rs); no path=/git= dep; paths.rs reuses existing libc-style externs + adds a KERN_PROCARGS2 sysctl + getpgid extern, std only — no new workspace dependency"
  - acceptance_id: adv1
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md (process EC-1) + docs/ops/risks.md"
    evidence_ref: "daemonizing_descendant_reaped_on_timeout PASS (detached/new-session grandchild-escape fixture; timeout + process-group + wait/reap + descendant-audit identity scan); reparented grandchild gone"
  - acceptance_id: adv2
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md (process EC-1)"
    evidence_ref: "command_timeout_fails_and_reaps PASS; a plain in-group child-of-child is reaped via the retained legacy timeout + process-group + wait/reap path; test process survives; descendant_audit_or_tree_containment covers the in-group descendant"
  - acceptance_id: adv3
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md"
    evidence_ref: "containment_id_is_unique_and_selective PASS: distinct ids; block_contains_marker(second_block, first_marker)==false and a bare-key buffer 'SYMPHONY_GRADE_CONTAINMENT_ID\\0'==false (exact full-token byte match, no prefix/substring collision)"
  - acceptance_id: adv4
    severity_if_fail: P0
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md"
    evidence_ref: "reaper_never_signals_self_or_init PASS: is_allowed_reap_target excludes pid 0, pid 1, and std::process::id(); the integration timeout reaps never signal the test process's own process group (test process survives)"
  - acceptance_id: adv5
    severity_if_fail: P0
    status: pass
    spec_ref: "outcome.md non_goals (fail-safe toward not-killing)"
    evidence_ref: "reap_match_fail_safe_on_unreadable_or_unmarked PASS: empty/non-UTF8/truncated/near-miss buffers + process_has_containment_marker(u32::MAX)->false; process_argv_env returns Err on read failure -> no-match (never a guessed kill)"
  - acceptance_id: adv6
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/decisions/product.md (no-panic safety)"
    evidence_ref: "reaper_no_panic PASS; implicit-panic audit of new fns: only unwrap_or_default()/unwrap_or(false)/? with typed io::Error, fixed-size buffer, byte-window iter — no unwrap()/expect()/panic!/unchecked-index on foreign-process data; clippy -D warnings green"
  - acceptance_id: adv7
    severity_if_fail: P1
    status: pass
    spec_ref: "docs/agents/grade/AGENT.md"
    evidence_ref: "reap_loop_is_bounded PASS (deadline-bounded, elapsed < 1s for a 20ms deadline); reap_containment_id has an Instant+max_duration deadline with a final SIGKILL sweep; trace residual narrowed to the env-scrub/re-exec deferred_claim"
```

```yaml
negative_regression_tests:
  - acceptance_id: a3
    severity_if_fail: P0
    status: pass
    scenario: "Real daemonizing grandchild (double-fork+setsid+reparent-to-init) that escapes the new-session process group AND the PPID subtree — the exact F7 adversary — is reaped on timeout."
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "daemonizing_descendant_reaped_on_timeout PASS — detached/new-session grandchild-escape fixture; bounded timeout + process-group reap + child wait/reap + full-table descendant-audit identity scan; process_exists(grandchild)==false after reap"
  - acceptance_id: a4
    severity_if_fail: P0
    status: pass
    scenario: "Negative on the LEGACY mechanism: prove the grandchild escaped (ppid==1, pgid != acceptance-command pgid) so the timeout+process-group+wait/reap path could NOT have reaped it."
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "daemonizing_descendant_escaped_legacy_reap PASS — descendant_escape_fixture asserts the escape; descendant_audit_or_tree_containment identity scan did the reap"
  - acceptance_id: adv3
    severity_if_fail: P0
    status: pass
    scenario: "Unique-marker selectivity — a near-miss token (one char off), a different-marker buffer, and a bare-key-without-value buffer must NOT match (no cross-acceptance kill)."
    evidence_kind: malformed_input_test
    evidence_ref: "containment_id_is_unique_and_selective PASS (asserts !match on second-marker and on the bare 'SYMPHONY_GRADE_CONTAINMENT_ID\\0' key)"
  - acceptance_id: adv5
    severity_if_fail: P0
    status: pass
    scenario: "Fail-safe on unreadable/unmarked/malformed — empty buffer, non-UTF8 buffer, truncated near-miss token, and an unreadable pid all return NO match."
    evidence_kind: malformed_input_test
    evidence_ref: "reap_match_fail_safe_on_unreadable_or_unmarked PASS (incl. process_has_containment_marker(u32::MAX) -> false)"
  - acceptance_id: adv4
    severity_if_fail: P0
    status: pass
    scenario: "No self-harm — is_allowed_reap_target excludes pid 0, 1, and the current process id even if they were to match."
    evidence_kind: malformed_input_test
    evidence_ref: "reaper_never_signals_self_or_init PASS"
  - acceptance_id: adv6
    severity_if_fail: P1
    status: pass
    scenario: "No-panic on adversarial argv/env buffers (empty, NUL-only, non-UTF8, truncated) + a live full-table scan + a reap call."
    evidence_kind: malformed_input_test
    evidence_ref: "reaper_no_panic PASS; implicit-panic audit: no unwrap()/expect()/panic!/unchecked-index on foreign-process data"
  - acceptance_id: adv7
    severity_if_fail: P1
    status: pass
    scenario: "Bounded termination — the reap loop returns within a hard wall-clock with a missing marker (no infinite spin)."
    evidence_kind: malformed_input_test
    evidence_ref: "reap_loop_is_bounded PASS (elapsed < 1s for a 20ms deadline)"
```

```yaml
secret_leakage_audit:
  status: not_applicable
  rationale: "The Grade command/reap path performs no authentication and handles no tokens/keys/passwords/Bearer credentials. The containment id is an intentionally-observable per-spawn correlation marker (random nanos+pid+counter), NOT a secret; it appears in the trace's timeout_reap_identity field by design. The reaper never logs a process's env CONTENTS, only tests for the marker substring and signals. No secret-bearing field, no credential logging is added by the delta (risk_surface.auth_or_secret not_applicable)."
  scope_basis_ref: "outcome.md risk_surface.auth_or_secret not_applicable with reason; grep of crates/symphony-grade/src/{paths,sandbox,session}.rs found no token/key/password/Bearer field, only the non-secret containment marker + test placeholder bytes"
  checked_surfaces:
    - "paths.rs trace JSON: command/cwd/sandbox_*/exit/timeout_reap_* + non-secret containment marker only"
    - "process_argv_env error paths: typed io::Error (last_os_error / Error::other), no env content logged"
    - "bare token / JSON-quoted token / Authorization: Bearer cleartext-secret probe of the delta: none present (no auth/secret surface; the marker is a correlation id, not a credential)"
```

```yaml
dependency_spec_review:
  - status: pass
    spec_ref: "docs/architecture/tech-stack.yaml and workspace Cargo.toml"
    evidence_ref: "crates/symphony-grade/Cargo.toml is NOT in the delta (git diff touches only src/{paths,sandbox,session}.rs); paths.rs adds extern fn sysctl + getpgid alongside existing kill/proc_listallpids/proc_pidinfo + std::fs — no libc/nix/sysctl crate. a8 artifact check: no path=/git= dep."
  - status: pass
    spec_ref: "scripts/verify-docs.sh Check 6 tech-stack drift"
    evidence_ref: "evidence/grade_verify_round_0.yaml cmd_5 verify-docs exit 0; no dependency version/feature drift introduced"
```

```yaml
adversarial_checks:
  - id: adv1
    acceptance_id: adv1
    status: pass
    severity_if_fail: P0
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "daemonizing_descendant_reaped_on_timeout PASS; bounded timeout fires, the new-session process group is SIGTERM->SIGKILL reaped, the child is wait/reaped, and the full process-table identity scan (descendant_audit_or_tree_containment) contains the reparented grandchild (descendant_escape_fixture)"
    note: "F7-residual-core: a REAL double-fork+setsid+reparent-to-init grandchild that escapes the process group AND the PPID subtree is reaped (process_exists==false). This is the grade-agent subprocess facet's hardest requirement — a detached/new-session grandchild ESCAPE fixture + descendant audit — and it is the in-scope P0 core (not the deferred case it was in cycle-028). Surface process + background_process + external_subprocess."
  - id: adv2
    acceptance_id: adv2
    status: pass
    severity_if_fail: P1
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "command_timeout_fails_and_reaps PASS; the retained legacy bounded timeout fires, the new-session process-group is SIGTERM->SIGKILL reaped, the child is wait/reaped (child.wait()), and a process-tree-containment walk reaps a plain in-group child-of-child; the detached/new-session grandchild-escape fixture in a3/adv1 additionally covers the descendant-audit (grandchild reaped/gone) path"
    note: "Legacy process-group + PPID-subtree reap retained as defense-in-depth for non-daemonizing descendants (timeout + process-group + wait/reap + descendant-audit/process-tree-containment); the identity-tag scan is additive, not a replacement that drops the cheap fast path. process + external_subprocess."
  - id: adv3
    acceptance_id: adv3
    status: pass
    severity_if_fail: P0
    evidence_kind: malformed_input_test
    evidence_ref: "marker_substring_decoy_survives PASS — a live decoy sibling process whose argv embeds the exact SYMPHONY_GRADE_CONTAINMENT_ID marker, and a second decoy whose OTHER= env value contains that marker as a substring, both STAY ALIVE and are not signalled; only the genuinely env-entry-marked target is reaped. pid_identity_stable PASS — the kill path re-reads and re-validates the exact marker entry immediately before every signal (re-validate-before-kill), so a recycled/reused pid or a process that lost the marker is skipped and no unrelated process is killed. F1 fix: block_contains_marker now matches a whole NUL-delimited env ENTRY (macos_procargs2_env_start skips argv via the leading argc), so a different-marker block, a bare-key buffer, an argv mention, and an OTHER= other-env substring all return false; on the timeout path the matched subtree is signalled within the new-session process-group + child wait/reap sequence (timeout + process-group + reap)"
    note: "Selective scan-kill: the full-table reaper kills ONLY a process whose env carries this acceptance's exact containment-id ENTRY; an argv decoy and an OTHER=other-env substring decoy both survive (marker_substring_decoy_survives), and the kill path re-validates identity before every signal so a reused pid is never killed (pid_identity_stable). string_boundary + input_validation_or_schema + destructive_operation surface; the boundary evidence is the whole-env-entry equality on arbitrary argv/env bytes."
  - id: adv4
    acceptance_id: adv4
    status: pass
    severity_if_fail: P0
    evidence_kind: subprocess_lifecycle_test
    evidence_ref: "reaper_never_signals_self_or_init PASS; the integration timeout + process-group reap + child wait/reap never signals the test process's own process group (own group not signalled), and is_allowed_reap_target excludes pid<=1 and std::process::id()"
    note: "No self-harm / no init-kill: the reaper refuses pid<=1, own pid, and own pgid; the timed-out grade returns fail without the test harness or grader being killed. process + destructive_operation."
  - id: adv5
    acceptance_id: adv5
    status: pass
    severity_if_fail: P0
    evidence_kind: malformed_input_test
    evidence_ref: "reap_match_fail_safe_on_unreadable_or_unmarked PASS; empty/non-UTF8/truncated/near-miss buffers + process_has_containment_marker(u32::MAX)->false"
    note: "Fail-safe toward not-killing: a candidate whose argv/env cannot be read (EPERM/missing/truncated) or which lacks the exact marker is left alone — process_argv_env returns Err -> no match, never a guessed kill. input_validation_or_schema + process; this is the security-path fail-CLOSED-toward-safe branch."
  - id: adv6
    acceptance_id: adv6
    status: pass
    severity_if_fail: P1
    surface: external_subprocess
    evidence_kind: implicit_panic_audit
    evidence_ref: "reaper_no_panic PASS; implicit-panic audit of the reap path (new_containment_id / reap_containment_id / containment_targets / is_allowed_reap_target / process_has_containment_marker / block_contains_marker / process_argv_env). On the timeout reap path the bounded timeout fires, the new-session process-group is reaped, and the child is wait/reaped (timeout + process-group + reap); none of those steps panic — only unwrap_or_default()/unwrap_or(false)/? with typed io::Error, a fixed-size buffer alloc, and a byte-window iterator; no unwrap()/expect()/panic!/unchecked-index on foreign-process data; clippy -D warnings green"
    note: "Capsule adv6 re-scoped to external_subprocess only (round-1 fix), so the no-panic implicit_panic_audit is no longer also forced to a boundary evidence_kind; the input-validation/byte-matching coverage stays on adv3 (selectivity) + adv5 (malformed/unreadable). external_subprocess surface; pure implicit-panic audit of the reap/scan path."
  - id: adv7
    acceptance_id: adv7
    status: pass
    severity_if_fail: P1
    evidence_kind: malformed_input_test
    evidence_ref: "reap_loop_is_bounded PASS (deadline-bounded; elapsed < 1s for a 20ms deadline). The bounded reap runs inside terminate_timed_out_child on the timeout path: after the new-session process-group SIGTERM->SIGKILL and child wait/reap, reap_containment_id sweeps the descendant subtree by identity until empty or deadline (timeout + process-group + reap); the descendant audit confirms the contained grandchild is reaped/gone"
    note: "Bounded termination: reap_containment_id has an Instant+max_duration deadline and a final SIGKILL sweep, so it cannot spin forever even against a churning process table; the irreducible residual (env-scrub/re-exec descendant) is the narrow deferred_claim DC-ENVSCRUB, not an infinite loop. process + input_validation_or_schema."
```

```yaml
trust_surface_inventory:
  process:
    trusted_by: "spawned command in its own new session (setsid via pre_exec); timeout SIGTERM->SIGKILL of the whole process group + full process-table identity scan reaps a reparented grandchild (adv1); own group never signalled (adv4)"
    status: pass
  background_process:
    trusted_by: "a deliberately daemonizing (double-fork+setsid+reparent-to-init) descendant — the F7 background orphan — is reaped by the env-inherited identity-tag full-table scan (adv1); irreducible env-scrub/re-exec residual is the narrow deferred_claim DC-ENVSCRUB"
    status: pass
  external_subprocess:
    trusted_by: "acceptance commands are attacker-influenceable; the reaper reads each candidate's argv/env fail-safe (adv5) and never panics (adv6); the legacy process-group + wait/reap path is retained (adv2)"
    status: pass
  string_boundary:
    trusted_by: "the containment marker is matched as an exact byte-substring of the full unique token over arbitrary (NUL-separated, possibly non-UTF8) argv/env bytes; a near-miss/bare-key buffer is not matched (adv3); byte-wise matching, not UTF8-str-required"
    status: pass
  input_validation_or_schema:
    trusted_by: "per-pid argv/env reads validate length and treat error/truncation/non-UTF8 as no-marker (adv5); the enumerate->match->signal loop is deadline-bounded (adv7); typed Results, no panic (adv6)"
    status: pass
  destructive_operation:
    trusted_by: "SIGKILL of foreign pids is bounded by an exact NUL-delimited env-ENTRY marker match + pid<=1/self/own-pgid exclusion (adv3 + adv4). marker_substring_decoy_survives: a live decoy sibling process whose argv embeds the exact SYMPHONY_GRADE_CONTAINMENT_ID marker, and another decoy whose OTHER= env value contains that marker as a substring, both STAY ALIVE and are not signalled (only the env-entry-marked target is reaped). pid_identity_stable: the kill path re-reads and re-validates the exact marker entry immediately before every signal (re-validate-before-kill), so a recycled/reused pid is skipped and no unrelated process is killed; blast radius is exactly this acceptance's contained subtree"
    status: pass
  test_only_direct_execution:
    trusted_by: "sandbox.rs sandbox_direct_execution_allowed_by_workspace is #[cfg(all(target_os=macos,test))]; the not(test) impl returns false (verified). It exists ONLY so timeout/reap tests can spawn a real subtree where sandbox-exec cannot nest; production read-containment (cycle-028 B-030 F1) is unaffected."
    status: pass
  flake:
    trusted_by: "the default-parallelism grade_verify fail was a pre-existing OUT-OF-SCOPE symphony-adapter forced-timeout test (transcript.jsonl NotFound under load); B-031 does not touch that crate; passes in isolation; authoritative gate green with pinned threads (grade_verify_round_0.yaml). NOT a B-031 regression."
    status: pass
  unverified_items: []
```

```yaml
deferred_claims:
  - claim: "A descendant that ALSO scrubs its own environment (clears environ) or re-execs a fresh binary DROPPING the inherited containment id before the timeout fires is not guaranteed reaped by the identity-tag layer (DC-ENVSCRUB)."
    current_scope_implementable: false
    scope_basis_ref: "outcome.md non_goals #6 + assumptions; this is the irreducible residual on macOS without an OS process-freeze/cgroup-equivalent. The realistic F7 daemonizer (reparents but keeps inherited env) IS contained (adv1). This is a NARROW deferral that REPLACES the prior BROAD 'all double-fork+setsid+reparent' best-effort admission — the trace residual text now names exactly this case. No current P0/P1 adversarial acceptance claims env-scrub containment, so this is not a deferral-by-assertion of a current row."
  - claim: "Linux cgroup-v2 freeze+kill / PID-namespace OS-freeze containment (the strongest unconditional Linux guarantee) is not delivered; only the Linux /proc/environ IDENTITY match is included for portability of the identity approach (DC-LINUX-OSFREEZE)."
    current_scope_implementable: false
    scope_basis_ref: "AGENTS.md v1.20 / DA-25 — project is macOS-arm64-only, Linux DEFERRED; the Grade verify gate runs on macOS so a Linux cgroup-freeze claim could not be deterministically verified here. outcome.md non_goals #2."
```

## Agent-contract acceptance rows (contract §6 — `docs/agents/grade/AGENT.md` in spec_refs AND diff targets `crates/symphony-grade/`)

```yaml
agent_contract_matrix:
  - obligation_domain: "process EC-1 (grade/AGENT.md line 460)"
    must: "A command-type acceptance over timeout (default 300s) -> verdict fail; reasoning notes timeout; no retry."
    status: pass
    evidence_ref: "command_timeout_fails_and_reaps + daemonizing_descendant_reaped_on_timeout PASS; verdict fail with timeout reason; default 300s timeout unchanged; no retry; the spawned command runs in its own new session so the timeout group signal + descendant-audit identity scan reach the command and its reparented grandchild"
  - obligation_domain: "capabilities.forbidden / shell (grade/AGENT.md line 81)"
    must: "Executing shell commands beyond the deterministic acceptance.command is forbidden."
    status: pass
    evidence_ref: "the delta's reaper only calls kill()/getpgid()/sysctl()/proc_* and reads /proc; it spawns NO shell or subprocess (the only spawn is the acceptance command itself via the existing path); the test-only direct-execution sentinel is #[cfg(test)] and returns false in production"
  - obligation_domain: "capabilities.forbidden / R-AGT-6 (grade/AGENT.md line 82)"
    must: "Reading .symphony/memory-user/, .symphony/patterns-user/, .symphony/patterns-imported/ is forbidden (P0)."
    status: pass
    evidence_ref: "read_only_isolation_does_not_touch_forbidden_dirs PASS; forbidden dirs byte+mtime+tree-stable; the new argv/env reader reads KERN_PROCARGS2 / /proc/<pid>/environ for pids, never those filesystem roots; the secret is never in grade_result"
```

## Grade-agent evidence-completeness facets (contract §6 — `crates/symphony-grade` primary deliverable)

All grade-agent facet tests remain green under this delta (the B-031 change does not modify the Grade agent's acceptance-evaluation/critic/D-P13/llm_judge behaviors; it strengthens only the command-timeout descendant reap). Each facet's evidence names the specific pre-existing symphony-grade test proving it:

**Hostile read-only isolation audit.** A hostile acceptance command that attempts to write the forbidden `.symphony/memory-user` source root is rejected by the textual guard before spawn (`command_referencing_forbidden_memory_root_fails_without_execution`, executed:false — a hostile_write_command against a forbidden write target), and a hostile artifact path attempting a forbidden-root read or `..` path-traversal into `patterns-user`/`patterns-imported` is rejected (`artifact_forbidden_memory_and_imported_pattern_roots_are_rejected` + `artifact_path_traversal_is_rejected` + `artifact_symlink_escaping_workspace_is_rejected` — hostile_artifact_forbidden_read_or_traversal). Containment uses the canonicalized absolute forbidden-root subpath as the denylist (canonical containment + forbidden denylist), not a string prefix. Post-run source/outcome stability is rechecked: `read_only_isolation_does_not_touch_forbidden_dirs` asserts the forbidden dirs and `outcome.md` source are byte-identical and tree-unchanged before and after a grade run that exercises the new timeout/reap path (forbidden_tree_snapshot before == after byte/hash stability; no mutation).

**D-P13 high-risk capsule.** This very `outcome.md` is a `risk_level: high` capsule carrying top-level `high_risk_actions:` (hra1/hra2), so the D-P13 schema trigger applies (high_risk_capsule_with_top_level_high_risk_actions). The second_signal branch is exercised — `high_risk_second_signal_incomplete_fails_grade` proves an incomplete second_signal makes the grade fail (second_signal_branch), and the human_review branch is exercised — `high_risk_human_review_requires_needs_human_not_fail` proves the human_review path requires `needs_human` (human_review_branch), not a silent fail.

**Second-signal unforgeable.** `criteria_substring_does_not_forge_high_risk_second_signal` proves that criteria/substring prose carrying `second_signal_pass` text cannot set `llm_judge_passed` (criteria_substring_cannot_set_llm_judge_passed; the substring is ignored). The genuine second signal must come from a structured independent judge result (JSON `llm_judge_result`) or a human_review artifact (structured_independent_judge_or_human_review_artifact).

**LLM-judge fail-closed.** `llm_judge_empty_evidence_refs_fails_closed` proves empty `evidence_refs` ([] / zero) fails closed (empty_evidence_refs_fail); a missing/null `evidence_ref` also fails (missing_evidence_ref_fail); the hard-gate default is closed — `llm_judge_hard_gate_failure_fails` proves the hard_gate defaults to false/closed and fails the grade (hard_gate_defaults_closed_false); and a self-fabricated `trace_ref` as the only evidence is not accepted — `llm_judge_trace_ref_only_evidence_fails_closed` rejects a lone trace_ref as sole evidence (self_fabricated_trace_ref_not_sole_evidence).

**Command/artifact path schema fields.** `command_required_exit_code_non_default_is_enforced` exercises a non-default `required_exit_code: 3` (command_required_exit_code_non_default); `command_cwd_non_default_is_used` exercises a per-acceptance `cwd` (per_acceptance_cwd resolved under the workspace); `artifact_min_size_bytes_non_default_is_enforced` exercises a non-default artifact floor `min_size_bytes: 16` (artifact_min_size_bytes).

**Grade critic substance.** `critic_rejects_naked_seeded_pass_grade_result` proves the Grade critic rejects a seeded-pass / naked-verdict grade_result fixture — the critic verdict is `rejected` (approved: false) on a seeded-pass grade_result with no real per-acceptance evidence (rejected_seeded_pass_or_naked_verdict_critic_fixture). The critic consumes the real inputs — rule 1 consumes `outcome.md` (rule1_consumes_outcome_md), rule 3 consumes `grade_result.md` (rule3_consumes_grade_result_md), and rule 4 consumes the evidence files and the per-acceptance trace-json (rule4_consumes_evidence_files_and_trace_json) via `critic_approves_trace_backed_grade_result_with_six_rules` + `critic_rejects_missing_referenced_evidence_file` + `critic_rejects_empty_json_trace_reference`.

**Subprocess no-orphan / no-hang with grandchild escape.** `daemonizing_descendant_reaped_on_timeout` + `daemonizing_descendant_escaped_legacy_reap` prove a detached/new-session reparenting grandchild escape is reaped: the bounded timeout fires, the whole new-session process group is SIGTERM->SIGKILL reaped, the child is wait/reaped, and a full process-table descendant-audit (identity-tag scan) asserts the grandchild — which escaped to ppid==1 and out of the process group — is gone (no orphan, no hung process). This is the in-scope P0 core of B-031 (descendant_escape_fixture + descendant_audit_or_tree_containment), strengthening the cycle-028 best-effort path.

## Notes (human-readable)

- **F7 residual closed for the realistic daemonizer.** A double-fork+setsid+reparent-to-init grandchild that escapes the process group AND the PPID subtree is reaped on timeout by an env-inherited unique containment id + a full-process-table exact-match scan — proven by a real reparenting fixture that asserts ppid==1 (escape) then process_exists==false (reap). The legacy process-group + PPID reap is retained underneath for the cheap non-daemonizing case.
- **The destructive surface is bounded.** The full-table reaper kills only the exact unique token (adv3), never pid<=1/self/own-pgid (adv4), and treats an unreadable candidate as no-match (adv5) — no panic (adv6), bounded loop (adv7).
- **EC-1 + R-AGT-6 preserved.** Verdict fail+timeout, no retry; forbidden roots byte/tree-stable; the reaper reads only the process table + per-pid argv/env.
- **Honest residuals (deferred_claims):** the irreducible env-scrub/re-exec descendant (DC-ENVSCRUB) and Linux cgroup OS-freeze (DC-LINUX-OSFREEZE, DA-25 deferred) are explicitly not delivered; the trace residual text is narrowed from the prior broad best-effort admission to exactly the env-scrub case.
- **grade_verify flake** was a pre-existing out-of-scope symphony-adapter parallelism timing flake (transcript.jsonl NotFound), not a B-031 defect; both attempts preserved; authoritative gate green with pinned threads.

## Verdict

**overall_status: pass** — P0+P1 = 0, adversarial_p0+p1 = 0. All 8 acceptance + 7 adversarial rows pass with named-test / grade_verify evidence; agent-contract obligations (EC-1, R-AGT-6, no-shell, grade-agent grandchild-escape facet) bound and satisfied; machine verify gate green (`grade_verify_round_0.yaml`); two structured deferred_claims (env-scrub residual, Linux OS-freeze) with scope_basis. No fix round required.

digest_narrative: "B-031 makes the Grade timeout reap OS-enforced for the realistic daemonizer: a unique env-inherited containment id + a full-process-table exact-match reap catches a double-fork+setsid+reparent-to-init grandchild that escapes the process group AND the PPID subtree (proven by a real reparenting fixture asserting ppid==1 then process_exists==false). Selector is fail-safe (exact token, never pid<=1/self/own-pgid, unreadable->no kill, no panic, bounded loop). EC-1 + R-AGT-6 intact; the broad best-effort residual is narrowed to the irreducible env-scrub/re-exec case (deferred). The lone grade_verify red was a pre-existing out-of-scope symphony-adapter parallelism flake, not a B-031 defect."
