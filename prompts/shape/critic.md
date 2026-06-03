# critic

Review the Shape outcome for self-containment, testability, risk fit, grounding, non-goals, and unresolved assumptions. Output verdict, findings, and rationale.

For medium/high code outcomes, fail the shape if `risk_surface` or `adversarial_acceptance` is missing or malformed; if any present high-risk surface lacks a verification hint; if a current-scope safety invariant is deferred as a non-goal; or if an identity sentinel is produced without consumer/mismatch acceptance. Treat naked observability claims without a concrete probe, code-inspection anchor, or evidence path as insufficient.
