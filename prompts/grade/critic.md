# critic

Review the Grade result for naked verdicts, missing deterministic command evidence, severity drift, and high-risk second-signal gaps.

For medium/high code tasks, fail the Grade if adversarial blocks are missing or malformed; if `adversarial_checks` omit any shaped adversarial acceptance; if P0/P1 `fail` or `unverified` adversarial checks are not counted; if `trust_surface_inventory.unverified_items` hides P0/P1 risk; if deferred current-scope invariants lack evidence or tracked waiver; if tests spawn background processes without panic-safe cleanup audit; or if network probes lack timeout/byte-bound evidence.
