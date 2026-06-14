# r1-verify — cycle-028 F1+F2 security remediation (fresh-context, codex read-only)

Independent source-level re-read of the remediation diff (`remediate/cycle-028`) vs r1.md, default-to-not-closed, with explicit instruction to flag a test-only fix that leaves production fail-open. Verdict: **both findings closed** (overall_closed: true). (codex verifier sandbox can't run sandbox-exec; orchestrator independently confirmed cargo nextest -p symphony-grade 42/42 on the real macOS host + fmt/clippy -D warnings clean.)

```r1_verify
cycle: cycle-028
findings:
  - id: F1
    severity: P0
    closed: true
    sub_claims:
      production_fail_closed_when_sandbox_inactive: true
      proof_tests_assert_active: true
      forced_unavailable_proof_present: true
    evidence: "paths.rs:131-170 gets CommandSandbox and returns Fail with guard r_agt_6_os_containment_required, executed:false, exit_code:null when sandbox.active is false; the spawn path starts only after that at paths.rs:171-187. sandbox.rs:34-41 marks fallback active:false. session.rs:1086-1091 and 1135-1140 assert probe.active. session.rs:1197-1245 forces sandbox unavailable, uses obfuscated cat .symphony/mem*/x, asserts textual guard none, overall Fail, no leaked secret/stdout, trace sandbox_active:false/executed:false/os_containment_required."
  - id: F2
    severity: P1
    closed: true
    sub_claims:
      absolute_path_invocation_production_and_probe: true
      path_poisoning_test_present: true
    evidence: "sandbox.rs:52-60 stores sandbox_exec from sandbox_exec_path and passes it to sandbox_exec_can_apply; sandbox.rs:62-69 sets production CommandSandbox.program to that absolute path and uses /bin/sh; sandbox.rs:78-90 probe uses Command::new(sandbox_exec) with /bin/sh -c true; sandbox.rs:115-120 only returns absolute /usr/bin/sandbox-exec or /bin/sandbox-exec. sandbox.rs:228-283 plants fake PATH sandbox-exec, prepends it to PATH, asserts active prepared.program equals the real absolute path and /bin/sh is used, runs prepared.program, and asserts fake sentinel was not created."
overall_closed: true
notes: "Read-only source verification. I did not rely on a full cargo run because this verifier sandbox may not exercise macOS sandbox-exec. F2 PATH-poisoning test's strongest absolute-program assertion is inside the active path, but production and probe source now directly thread the discovered absolute sandbox-exec path."
```
