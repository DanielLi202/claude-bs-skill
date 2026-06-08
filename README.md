# claude-bs-skill

Bootstrap development workflow skill v1.4.10.

This repository contains the universal `/bs` workflow contract, command descriptions, bundled runtime placeholders, parser libraries, generic agent prompts, and YAML-only initialization templates.

## Contract

- Contract body: [`contract.md`](contract.md)
- Skill manifest: [`skill.yaml`](skill.yaml)
- Commands: [`commands/`](commands/)
- Runtime defaults: [`runtime/`](runtime/)
- Generic prompts: [`prompts/`](prompts/)
- Init templates: [`bundle/`](bundle/)

Adopter repositories should not copy the contract markdown into `.bootstrap/`. They should track:

- `.bootstrap.yaml`
- `.bootstrap/backlog.yaml`
- `.bootstrap/contract.sha256`

The contract hash is the trust root. The tagged source URL is a locator.

## v1.3 scope

- Single-threaded cycles only.
- Strict backlog enums.
- `step_events.jsonl` is the resume state machine.
- Step 10 closes ledger and backlog in one atomic commit.
- Repository-specific prompt overrides are deferred to v1.4+.
- TC-B medium/high code tasks require adversarial Shape/Grade schema and deterministic `runtime/grade_lint.py` before fix-loop and auto-merge decisions.
- Semantic completion, non-interrupting long-running supervision, typed per-round Grade verify, and warning-only council quorum by default.
