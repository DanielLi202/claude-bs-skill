<!-- runtime asset: bs-skill design spec; not vendor-facing -->
# B2 — Reference-Source Contract Review (first release) — implementation spec

**Status**: spec (architect). Implements the AI-council verdict `~/.claude/council-logs/20260614-072620-bs-b2-semantic-conformance-ceiling.md` (Codex+Grok proposers / Agy critic, 2026-06-14). Target bs-skill release **v1.4.24**.

## Goal & why
bs has a strong deterministic grade_lint FLOOR but no semantic CEILING. Across cycles 020/022/023/024/025 the loop kept escalating the SAME class to a human: **"the cited evidence does not actually demonstrate the referenced canonical obligation"** — Grade/Shape passed presence-only DOM, mock/fixture-only, or narrowed-contract evidence when a referenced source (design-brief §, UX-N, locked prototype, api-contract, verifier/Grade-agent contract) required specific behavior / state / affordance / production-path / hostile-fixture coverage. 13 escalated items, one class.

This release builds the council's convergent hybrid — the **agent-contract pattern (already shipped as contract §6 / v1.4.15) applied to referenced design/UI/contract sources**. It is precision-biased: only conservative deterministic evidence-SHAPE predicates BLOCK (each backtest-gated); the LLM semantic judge is ADVISORY-only and never blocks in this release.

## Scope of THIS release (and explicit non-goals)
IN:
1. A DRY normative block `REFERENCE_SOURCE_CONTRACT_REVIEW_V1` in `contract.md` (§6-style) + the evidence-class taxonomy + the obligation-ledger schema + one-sentence pointers in the four prompts.
2. Shape emits a machine-readable **reference obligation ledger** in `outcome.md` when triggered.
3. `grade_lint.py` deterministic **evidence-SHAPE** facets enforcing the ledger + evidence classes — backtest-gated.
4. Advisory **reference-obligation review-request** emission + a never-blocking structured advisory-verdict slot, logged to evidence.

OUT (deferred, named as the residual hard problems — do NOT silently assume solved):
- **Trusted evidence provenance/attestation** (Agy's load-bearing finding): a coding agent can still satisfy an evidence-shape rule with a static mock/fixture that never wires to production, or rewrite a test artifact. This release RAISES the floor (production-path-anchor requirement) but does NOT close gaming. No claim of gaming-proofness.
- **Promoting the LLM judge to blocking** — gated behind a future backtest that must show zero false-blocks for a mismatch category + multi-run (temp=0) agreement. Not in this release.
- Any new mandatory model-server dependency (vLLM/Ollama). The advisory verdict backend is pluggable/optional; default = emit request + record an advisory verdict if a backend is configured, else leave the slot empty. Grade pass/fail NEVER reads it.
- Running Playwright/visual/Pact/browser inside Grade.

## Trigger (machine-checkable, mirrors the agent-contract §6 trigger)
`task_type == code` AND the outcome's `spec_refs`/`context_pointers` contain a canonical-source path matching the reference-source set: `docs/ux/design-brief.md`, `docs/decisions/ux.md` (UX-N), `docs/ux/prototype/**`, `docs/architecture/api-contract.md`, `docs/architecture/schemas/*.md`, `docs/agents/*/AGENT.md`. A claim is in-scope only when it is a PRIMARY-deliverable claim referencing one of these (reuse the existing primary-deliverable scoping; do NOT fire on incidental cross-references, dependency-review rows, or historical/backtest prose). Schema-only/agent-contract tasks already covered by §6 are not re-triggered here — this block is the *frontend/UI + general referenced-source* twin; where they overlap, §6 wins for agent-implementation tasks.

## Shape output: reference obligation ledger
When triggered, Shape MUST add a parseable fenced YAML block `reference_obligations` to `outcome.md`. Each entry:
```yaml
- obligation_id: "UX-030-SNAPSHOT-RETAIN-01"     # stable id
  source_ref: { path: "docs/ux/design-brief.md", section: "§4.5 degraded reconnect", quote_hash: "sha256:…" }
  kind: "ui_state_behavior"                       # see evidence-class taxonomy
  must: "During degraded reconnect retry, retained snapshot content stays visible while retry/degraded status shows."
  required_evidence_classes: ["behavioral_ui_test", "production_path_anchor"]
  not_sufficient: ["heading_present", "mock_fixture_only", "static_dom_snapshot_only"]
  waiver: null
```
Silent narrowing is forbidden: if Shape excludes/weakens a referenced obligation it MUST emit a row with `waiver: {reason, waiver_id}` OR mark the obligation `status: UNVERIFIED` with a `scope_basis_ref`. Carry only small normative labels/enums verbatim with `source_ref` (no full-text restatement — §4 red-line #3).

## Evidence-class taxonomy (defined in the contract block; enforced by grade_lint)
| obligation `kind` | required evidence class(es) | NOT sufficient alone |
|---|---|---|
| `ui_action_state_label` | `behavioral_ui_test` (Testing-Library `getByRole`/`getByLabelText`/accessible-name + `userEvent` + state assertion, or Storybook `play()`) | heading/landmark/testid present; screenshot |
| `ui_state_behavior` (retry/degraded/reconnect/snapshot-retention) | `behavioral_ui_test` exercising the production state machine/hook with controlled transport/timers asserting before/during/after + `production_path_anchor` | fixture-only rendered state |
| `production_behavior` | `production_path_anchor` (test imports/invokes the production wiring path; names entry point + substituted deps) | seam/mock that bypasses production |
| `api_contract` | `pact_or_schema` (Pact provider verification / OpenAPI / schema conformance / request-body assertion) | mock-server success only |
| `terminal_enum_coverage` | `enum_or_property_coverage` (exhaustive enum/property/model-based test or executed state table) | single happy-path fixture |
| `verifier_hostile_contract` | `hostile_fixture_manifest` (named adversarial fixtures + executed results) | benign example fixtures |

## grade_lint.py deterministic facets (the hard floor — block only on evidence SHAPE; backtest-gated)
Add a frontend-family-style facet group scoped by a new `reference_source_in_scope` predicate (primary-deliverable based, mirroring `frontend_primary_deliverable_in_scope` and the §6 agent-contract trigger). Mirror the existing `validate_frontend_*` facet implementation style (paired real-corpus must-fire/must-not-fire fixtures; strong-term scoping; no over-fire). BLOCK (P0/P1, counted in `grade_summary`) only when, for an in-scope referenced-source PASS row:
1. `reference_obligations` block is missing entirely while a PASS row cites a reference-source obligation. (`reference_obligations` required when triggered.)
2. A PASS row for a referenced obligation lacks `obligation_id` linking to the ledger, or the ledger entry lacks `required_evidence_classes`.
3. A `production_behavior`/`ui_state_behavior` PASS cites ONLY fixture/mock/seam evidence (the existing `FRONTEND_FIXTURE_OR_SEAM_TERMS` + `FRONTEND_PRODUCTION_*` machinery already does most of this — extend/reuse, don't duplicate) without a `production_path_anchor`.
4. A `ui_action_state_label`/`ui_state_behavior` PASS cites ONLY static DOM/heading/landmark/testid/screenshot presence — no behavioral (role/label + userEvent/state) evidence.
5. A referenced source obligation was narrowed/excluded with no `waiver` and no `UNVERIFIED` row (silent narrowing).
6. A `verifier_hostile_contract` obligation omits the required hostile-fixture ids.
DO NOT have deterministic lint decide the semantic ADEQUACY of prose evidence — only the presence/shape of the required evidence CLASS. Reuse existing frontend facets where they already cover a case (v1.4.17–21 shipped many — `validate_frontend_production_wiring_or_unavailable_honesty`, `_pessimistic_*`, `_outcome_capsule_schema_guard_*`, terminal-enum coverage, etc.). The NEW work is the obligation-ledger requirement + the `obligation_id↔evidence_class` binding + the behavioral-vs-presence and narrowing predicates that generalize the per-cycle facets into the taxonomy.

**Backtest gate (MANDATORY, same invariant as every prior grade_lint rule):** each new BLOCKING predicate must MUST-FIRE on its target historical cycle(s) (020 Grade-agent hostile-fixture; 022 SSE mock-vs-behavior; 023 presence-vs-affordance; 024 fixture-vs-production + unbuilt-upstream; 025 capsule-schema/tags/pessimistic) AND produce ZERO misfires on the full historical corpus (cycles 018–025). Author paired real-corpus must-fire (the actual escaped grade/outcome text) + must-not-fire (clean/satisfied/negated phrasing) fixtures in `tests/test_grade_lint.py`. Run `harness/evolve-loop/bin/backtest.py`; converge to zero misfires (expect 2–3 refinement rounds — strong-term-only scoping).

## Advisory LLM judge (NEVER blocking this release)
- The grade flow emits `evidence/reference_obligation_review_request.jsonl` — one object per in-scope obligation: `{obligation_id, source_quote, normalized_obligation, grade_claim, evidence_summary, evidence_artifacts:[{type,path,span}]}` (narrow per-obligation context, NOT the whole codebase — keeps context focused, mitigates "lost in the middle").
- A pluggable advisory verdict slot: if a judge backend is configured, record `evidence/reference_obligation_review_verdict.jsonl` — `{obligation_id, verdict: DEMONSTRATED|NOT_DEMONSTRATED|UNVERIFIED_DEPENDENCY|INSUFFICIENT_INFO, mismatch_category: presence_vs_affordance|fixture_vs_production|source_narrowing|hostile_fixture_missing|none, source_span_used, evidence_span_used, one_sentence_reason}` + the prompt hash / model id / temp for replay. Reference-guided + structured-JSON; anti-gaming guidance documented (temp=0, exact-span citation). Default backend = none (slot empty) — the request is still emitted for a human or a future judge.
- **Grade pass/fail MUST NOT read the advisory verdict.** It is telemetry/calibration only. A `grade_lint` check may assert the request artifact EXISTS when triggered (shape), but never that a verdict says PASS.

## DRY prompt shape (no 13 paragraphs)
`contract.md` carries the one normative block + the taxonomy table + the ledger schema + the advisory spec. The four prompts (`prompts/shape/role.md`, `prompts/shape/critic.md`, `prompts/grade/role.md`, `prompts/grade/critic.md`) gain ONE sentence each, e.g.:
- shape/role: "When `REFERENCE_SOURCE_CONTRACT_REVIEW_V1` triggers, emit `reference_obligations` per the contract block: freeze each referenced obligation with its required evidence class; never narrow a source without a waiver/UNVERIFIED row."
- grade/role: "When `REFERENCE_SOURCE_CONTRACT_REVIEW_V1` triggers, judge each obligation against its required evidence class — a PASS needs evidence that demonstrates the behavior, not tokens/DOM presence/mocks; cite the obligation_id."
- the two critics: fail Shape outcomes that silently narrow / lack evidence classes; fail Grades that accept presence/fixture-only for a referenced behavior obligation or lack the `reference_obligations` binding.

## Files to touch
- `contract.md`: new `REFERENCE_SOURCE_CONTRACT_REVIEW_V1` block in §6 area + taxonomy + ledger schema + advisory spec + §11 changelog v1.4.24.
- `prompts/shape/role.md`, `prompts/shape/critic.md`, `prompts/grade/role.md`, `prompts/grade/critic.md`: one-sentence pointers.
- `runtime/grade_lint.py`: `reference_source_in_scope` predicate + the new evidence-SHAPE facets + dispatch wiring; the request-artifact emission (or wire it in the grade flow / `commands/bs.md`).
- `tests/test_grade_lint.py`: paired must-fire/must-not-fire fixtures per new predicate (real cycle-020/022/023/024/025 corpus text).
- Version bumps to 1.4.24 (skill.yaml, contract.md title, README.md, codex_driver/preflight client versions, bundle template) + manifest relock (`harness/evolve-loop/bin/verify-manifest.sh`).

## Acceptance criteria (Definition of Done — observable)
- MUST: a referenced canonical source cannot silently disappear from a triggered outcome (Shape narrowing without waiver/UNVERIFIED → grade_lint blocks).
- MUST: a PASS cannot cite "heading exists"/static-DOM-only for a `ui_action_state_label`/`ui_state_behavior` obligation.
- MUST: a PASS cannot cite fixture/mock-only evidence for a `production_behavior` obligation (no `production_path_anchor`).
- MUST: a `verifier_hostile_contract` obligation without hostile-fixture ids blocks.
- MUST: each new BLOCKING grade_lint predicate must-fires on its target cycle and produces ZERO misfires across cycles 018–025 (backtest evidence committed).
- MUST: the advisory request artifact is emitted when triggered; Grade pass/fail never reads the advisory verdict.
- MUST: full `python3 -m unittest discover -s tests` green; manifest relocked; versions consistent at 1.4.24.
- SHOULD: the 13 B2 escapes, replayed, now produce a deterministic block OR a structured advisory review row (calibration data), with zero new false-block classes on the historical corpus.
- OUT-OF-SCOPE acknowledged in the changelog: trusted evidence provenance + LLM-judge blocking promotion are deferred with their own evidence bars.

## Process
Implement in an isolated worktree. grade_lint backtest convergence is expected to need 2–3 rounds (precision tuning). Release via `harness/evolve-loop/bin/release.sh` (G1 versions / G2 unittest / G3 manifest / **G4 backtest — REQUIRED here, NOT skipped**, since this ships new grade_lint rules). Then an independent Codex deep-review to PASS before declaring done (mirrors the E7/goal-nudge v1.4.22→v1.4.23 discipline).
