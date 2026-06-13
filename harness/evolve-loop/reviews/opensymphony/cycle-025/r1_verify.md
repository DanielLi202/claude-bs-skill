# r1-verify — cycle-025 remediation (fresh-context, post-F7-fix)

Independent codex re-run of the remediation diff (df4eda6..remediation HEAD). First pass
found F7 not fully closed (high_risk_actions enum too permissive: 8 values incl. wrong
delete/payment vs the schema's exact 6; canonical fixture output_contract.artifacts as
string array vs schema artifact objects). Both residuals fixed + a regression assertion
added (invalid 'delete' action → malformed naming the correct six). This re-verify:
all 10 findings closed, gates re-run green (typecheck 0, 76/76), isolation clean.

---

F7 is now closed.

The enum residual is fixed: the schema lists exactly six high-risk actions at `docs/architecture/schemas/outcome-capsule.md:185-192`; `capsuleModel.ts` now defines exactly `db_write, file_delete, external_api, deploy, merge_pr, payment_api` at `apps/symphony-ui/src/outcome/capsuleModel.ts:104`, with rejection at `apps/symphony-ui/src/outcome/capsuleModel.ts:276-280`. The regression test injects invalid `action: "delete"` at `apps/symphony-ui/src/outcome/outcome.test.tsx:139-141` and asserts malformed output naming the correct six at `apps/symphony-ui/src/outcome/outcome.test.tsx:157`.

The fixture residual is fixed: schema §5 shows `output_contract.artifacts` as artifact objects with `type` at `docs/architecture/schemas/outcome-capsule.md:205-215`; `completeCapsule()` now uses object artifacts at `apps/symphony-ui/src/outcome/outcome.test.tsx:613-614`.

Rest of F7 is also covered: required top-level fields are enumerated and validated at `apps/symphony-ui/src/outcome/capsuleModel.ts:105-120,347-367`; tags vocabulary at `apps/symphony-ui/src/outcome/capsuleModel.ts:103,311-327`; source-aware groundings and non-empty `supports` at `apps/symphony-ui/src/outcome/capsuleModel.ts:235-252`; test coverage is `apps/symphony-ui/src/outcome/outcome.test.tsx:132-160`.

Required rerun passed: `pnpm run typecheck && pnpm run test` exited 0; Vitest reported 76/76. Isolation spot-check diff was empty. F1-F5 and F8-F11 remain closed by current code/tests.

```yaml
r1_verify:
  reran_gates: true
  typecheck_exit: 0
  test_pass: "76/76"
  findings:
    - id: F1
      closed: true
      evidence: "apps/symphony-ui/src/lib/store/outcomeStore.ts:35,145-147 stable EMPTY_RUN_STATE; apps/symphony-ui/src/outcome/outcome.test.tsx:20-31 asserts stable unknown-run snapshot"
    - id: F2
      closed: true
      evidence: "apps/symphony-ui/src/shell/AppShell.tsx:25,28-29,191-209 uses required-4 plus Partial outcome methods and completes stubs; apps/symphony-ui/src/outcome/outcome.test.tsx:34-44 covers 4-method client"
    - id: F3
      closed: true
      evidence: "apps/symphony-ui/src/outcome/outcome.test.tsx:563-588 typed client mocks; apps/symphony-ui/src/test/node-globals.d.ts:1-10 declares fs/path globals; pnpm run typecheck exit 0"
    - id: F4
      closed: true
      evidence: "apps/symphony-ui/src/outcome/capsuleModel.ts:195-204 prefers string llm_judge criteria and tolerates legacy array; apps/symphony-ui/src/outcome/outcome.test.tsx:87-98 covers string preview and fallback"
    - id: F5
      closed: true
      evidence: "apps/symphony-ui/src/outcome/outcome.test.tsx:462-499 outcome-secret-redaction asserts bare, JSON token, and Bearer shapes absent from DOM, console capture, and outcomeStore snapshot"
    - id: F7
      closed: true
      evidence: "apps/symphony-ui/src/outcome/capsuleModel.ts:104,276-280 exact six high-risk actions and rejects delete/payment aliases; apps/symphony-ui/src/outcome/outcome.test.tsx:132-160 tests top-level schema guard, tags, invalid delete action, source-aware groundings, non-empty supports; apps/symphony-ui/src/outcome/outcome.test.tsx:613-614 uses artifact objects with type"
    - id: F8
      closed: true
      evidence: "apps/symphony-ui/src/outcome/OutcomeReadyCard.tsx:35,165-172 renders non-empty tags and hides empty row; apps/symphony-ui/src/outcome/outcome.test.tsx:180-192 proves render/hide"
    - id: F9
      closed: true
      evidence: "apps/symphony-ui/src/shell/AppShell.tsx:35,50-73,216-221 drops stale detail when snapshot leaves/freshens; apps/symphony-ui/src/shell/Inspector.tsx:85-89 prefers freshest revision; apps/symphony-ui/src/outcome/outcome.test.tsx:348-361 covers stale detail not overriding snapshot"
    - id: F10
      closed: true
      evidence: "apps/symphony-ui/src/outcome/OutcomeActions.tsx:19-22,33-40,89-113 implements scoped pessimistic re-shape pending/error; apps/symphony-ui/src/outcome/OutcomeReadyCard.tsx:142-156 disables reject during re-shape; apps/symphony-ui/src/outcome/outcome.test.tsx:284-316 covers failures"
    - id: F11
      closed: true
      evidence: "apps/symphony-ui/src/outcome/OutcomeActions.tsx:71-83 catches 409 refetch failure and clears pending via executeError; apps/symphony-ui/src/outcome/outcome.test.tsx:391-412 covers inline error and re-enabled Execute"
  isolation_ok: true
  overall: pass
```
