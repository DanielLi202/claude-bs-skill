## Verification result

I agree with all 8 adjudicated row verdicts. The false positives are real scoping collisions, and the three historical true positives are legitimate weak lifecycle-evidence claims.

I **do not** accept the stronger convergence/soundness claim. The report arithmetic converges, but A2c is overfit: `strong-term-only` would miss a realistic lifecycle assertion phrased without `process_group` / `SIGTERM` / `kill` / `spawn`. Corpus example: `B002-NO-REGRESSION`’s real claim is “daemon run/status/stop lifecycle … run→status→stop→files removed”; the current predicate fires only because the same sentence also has incidental negated text, “rather than raw kill -TERM.” That is brittle.

Also: target cycle has 14 current errors, but only 13 deltas because the secret-shape error already existed in baseline. So the “13 fires” are not proof that v1.4.12 newly caught the secret-shape escape.

```yaml
adj_verify:
  verdicts:
    - fired_on: B001-DAEMON-RUN
      agree: true
      reason: >-
        Correct true positive. The row claims detach/re-exec/process_group but only cites an already-running integration smoke; it does not prove timeout, reap, or stream join lifecycle facets.
    - fired_on: B001-DAEMON-STOP
      agree: true
      reason: >-
        Correct true positive. The row claims SIGTERM graceful shutdown and cleanup, but file removal plus status not-running is not termination accounting or wait/reap evidence.
    - fired_on: B001-NO-NEW-DEPS
      agree: true
      reason: >-
        Correct false positive. This is a dependency-compliance row; process_group is only cited to justify no new daemonization crate.
    - fired_on: B002-IFMATCH
      agree: true
      reason: >-
        Correct false positive. "cancel" is an HTTP endpoint name in an If-Match claim, not a subprocess lifecycle action.
    - fired_on: B002-NO-REGRESSION
      agree: true
      reason: >-
        Correct true positive as adjudicated: the row reasserts daemon run/status/stop lifecycle preservation but gives only run-status-stop-files-removed evidence. However, the current rule fires for a brittle reason: incidental negated "kill -TERM" text.
    - fired_on: B002-STATUS
      agree: true
      reason: >-
        Correct false positive. The probe is an authenticated HTTP status/stop request, not a vendor subprocess or process lifecycle probe.
    - fired_on: B001-QUALITY
      agree: true
      reason: >-
        Correct false positive. This is a code-quality/no-panic/clippy/tempdir row with no subprocess lifecycle claim.
    - fired_on: ADV-CHECK-CONCURRENCY
      agree: true
      reason: >-
        Correct false positive. The "spawn appenders" idea is file-lock concurrency, not child-process lifecycle.
  convergence: unsound
  under_fire_risk: >-
    Corpus-backed risk: B002-NO-REGRESSION contains a genuine daemon run/status/stop lifecycle assertion whose meaningful text has no strong term; the rule currently fires only because the row also says "rather than raw kill -TERM". Equivalent wording without that incidental negated strong term would under-fire.
  notes: >-
    Report arithmetic shows zero remaining adjudicated false-positive deltas and 13 target-cycle deltas, but not full rule soundness. Secret-shape is not a v1.4.12 delta because baseline already fired it. A safer predicate would keep the dep-row and HTTP-probe guards, add negation handling for "rather than/instead of/no longer", and scope weak lifecycle phrases only when paired with daemon/app-server/vendor/process lifecycle nouns, excluding dependency, HTTP, and file-lock concurrency rows.
```
