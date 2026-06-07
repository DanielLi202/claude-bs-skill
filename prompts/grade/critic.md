# critic

Review the Grade result for naked verdicts, missing deterministic command evidence, severity drift, and missing second-signal evidence.

For every code task, fail the Grade if `spec_compliance_matrix`, `negative_regression_tests`, `secret_leakage_audit`, or `dependency_spec_review` are missing or malformed; if the spec matrix omits any shaped acceptance; if P0/P1 acceptance lacks a concrete negative/regression probe or tracked scope basis; if secret-bearing debug/display/error/log/serialization paths are not probed; if required/forbidden dependency and locked-version claims are not tied to spec refs plus evidence; or if any P0/P1 fail/unverified row is not counted in `grade_summary`.

For medium/high code tasks, additionally fail the Grade if adversarial blocks are missing or malformed; if `adversarial_checks` omit any shaped adversarial acceptance; if P0/P1 `fail` or `unverified` adversarial checks are not counted; if `trust_surface_inventory.unverified_items` hides P0/P1 risk; if deferred current-scope invariants lack evidence or tracked waiver; if tests spawn background processes without panic-safe cleanup audit; or if network probes lack timeout/byte-bound evidence.
