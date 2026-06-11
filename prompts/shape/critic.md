# critic

Review the Shape outcome for self-containment, testability, risk fit, grounding, non-goals, and unresolved assumptions. Output verdict, findings, and rationale.

For predicate-hit agent-contract outcomes, reject the shape before Conduct if it weakens, paraphrases away, or narrows any referenced AGENT red line versus the source text, with read-vs-write narrowing as the canonical failure; if it omits acceptance and adversarial coverage for structured-schema nested objects, high-risk-action classifier examples, protocol-compliant Q&A answer merge, or critic-rejection-blocks-write; or if its target or artifact mismatches the referenced AGENT, such as the wrong agent, wrong crate, or wrong output artifact. This rejection scope is shaping completeness only; do not validate Rust implementation details.

For medium/high code outcomes, fail the shape if `risk_surface` or `adversarial_acceptance` is missing or malformed; if any present high-risk surface lacks a verification hint; if a current-scope safety invariant is deferred as a non-goal; or if an identity sentinel is produced without consumer/mismatch acceptance. Treat naked observability claims without a concrete probe, code-inspection anchor, or evidence path as insufficient.

For every code outcome, fail P0/P1 acceptance that states a broad safety property but only gives happy-path or example-only verification. Path/root containment must require symlink or canonical-root containment in addition to `..`/slash/absolute-path strings. Raw HTTP request-target or path-segment construction must require delimiter plus control-character/CRLF or percent-encoding probes. API-facing local-file reads must cover error/output leakage boundaries, not only parser success.
