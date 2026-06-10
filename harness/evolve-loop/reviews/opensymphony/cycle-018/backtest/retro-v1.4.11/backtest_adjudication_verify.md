## Verification result

I could not refute the adjudication.

- `cycle-016`: current rule fires for the stated class of reason: `status: pass`, probe is plain `pass`, the secret audit text matches scope terms (`Event`, `Debug`, `events`, `logs`, `token`, `Bearer`, etc.), and none of the three required token-shape patterns are present. The verdict is correct: these are secret-adjacent log/event/API surfaces, and a source grep is weaker than shaped runtime probes.
- `cycle-017`: current rule really lacks an early return for `cleartext_secret_probe: not_applicable`; it accepts the value, then still runs the scope predicate. The regex is triggered by negated/benign text such as “no auth/token/log code”, “not secret-bearing”, plus `Debug/Display`. False positive verdict is correct.
- Fix assessment: sound. A `not_applicable` exemption, including structured `status/result: not_applicable`, plus a fixture using the real cycle-017 text is the minimal targeted fix. It does not weaken cycle-018 because cycle-018 has `cleartext_secret_probe: pass`, not `not_applicable`, and still lacks required shaped evidence.

One correction: the adjudication’s “cycle-018 bare-only probe” wording is not what this validator sees in the `secret_leakage_audit` block; by `text_blob(secret)`, cycle-018 appears missing all three required shapes, so the must-fire case is even stronger.

```yaml
adj_verify:
  verdicts:
    - cycle: cycle-016
      agree: true
      reason: "The rule fires because the pass probe is unstructured, the audit text matches secret/log/event/auth terms, and no bare, JSON/quoted, or Authorization Bearer shape is demonstrated. The surfaces are genuinely secret-adjacent, and grep-only evidence is weaker than shaped probes through those paths."
    - cycle: cycle-017
      agree: true
      reason: "The rule accepts cleartext_secret_probe: not_applicable but does not return before scope matching, so negated/benign auth-token-log wording still demands shapes. That makes this a rule false positive, not a grade gap."
  fix_assessment: sound
  notes: "Add the not_applicable early return before secret_audit_requires_multi_shape for both string and structured probe forms. The cycle-017 real-text fixture is important; cycle-018 remains must-fire because its probe is pass, not not_applicable, and the validator sees missing required shapes."
```
