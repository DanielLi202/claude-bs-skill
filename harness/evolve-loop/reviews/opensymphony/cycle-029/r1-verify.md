# r1-verify — cycle-029 remediation (F1+F2 security fix)

Independent fresh-context codex review of `git diff fbc1693..2bb4dac`. Full log: iter019-r1verify.log.

```r1verify_verdict
cycle: cycle-029-remediation
reviewed: "git diff fbc1693..2bb4dac -- crates/symphony-grade/src (2 files, +240/-21); paths.rs + session.rs in full; original r1 F1/F2"
f1_closed: "yes — paths.rs:406-449 parses macOS procargs2 to env start, skips argc argv tokens, then exact NUL-token equality only; Linux remains env-only exact-entry via /proc/environ at paths.rs:641-644; argv and OTHER=value substrings are excluded"
f2_closed: "yes — paths.rs:350-365 routes every reap signal through signal_marked_pids, and paths.rs:472-491 re-checks allowed target plus exact marker immediately before each kill; residual window is only the post-revalidation syscall gap"
new_tests_valid: "yes — session.rs:1583-1681 spawns live marked target plus argv and OTHER env decoys and would fail against the old substring selector; paths.rs:1171-1187 directly exercises the unmarked stale-candidate guard; F7 tests remain live at session.rs:1555-1578 and helper 1765-1846"
f7_preserved: "yes"
new_defects: []
overall: "remediation sound — F1/F2 are genuinely closed, F7 containment is preserved, and I found no new defect in the reviewed diff"
```
