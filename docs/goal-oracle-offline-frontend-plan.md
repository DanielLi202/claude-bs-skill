<!-- runtime asset: bs-skill design spec; not vendor-facing -->
# Goal-completion oracle vs. offline-unverifiable deliverables (frontend cycles) — investigation & options

**Status**: Investigation / proposal — **NOT yet council-adjudicated**. The `goal_active_after_turn`
class was previously root-caused (cycle-025 `r2.md` GOAL finding + `closure.yaml`) and *partially*
mitigated by the opt-in `--goal-completion-nudge` (v1.4.22, fail-closed-hardened v1.4.23) per AI-council
`~/.claude/council-logs/20260613-211210-bs-evolve-7-escalations.md` (2026-06-13). This doc characterizes
the **residual structural cause** — frontend deliverables cannot be self-verified inside the offline
Conduct sandbox, so the agent never self-declares the goal complete — and lays out options. **Any option
that changes the success oracle, auto-completes the goal, or flips a default needs a fresh council verdict
before implementation** (the 2026-06-13 council ruled oracle-change / auto-complete out of scope;
determinism = needs_human).

**Source**: OpenSymphony dogfood cycles 018–031 — in the **OpenSymphony-V3 repo**
(`OpenSymphony-V3/docs/ops/dogfood-log.md` + `OpenSymphony-V3/.prompts/dogfood/cycle-*/recovery_decision.yaml`,
not in this repo); the prior `GOAL` root-cause in **this repo** at
`harness/evolve-loop/reviews/opensymphony/cycle-025/{r2.md,closure.yaml}`; cycle-027 `tk-003` / `wr-001`
(clearest mechanism statement + the proposed `conduct_blocked=frontend_gates_orchestrator_owned` signal);
cycle-031 `recovery_decision.yaml` (`waiver_scope = goal-status oracle only`); OpenSymphony `AGENTS.md` §8
"cycles 022-031 goal-oracle quirk". Mechanism + per-cycle evidence assembled by a 3-agent investigation,
2026-06-15.

---

## TL;DR

The "goal-oracle quirk" is **not a flaky oracle** — it is the predictable product of two facts:

1. **`goal=complete` is set only by the agent itself.** The exit-0 success oracle is
   `final thread/goal/get == "complete"` (`runtime/codex_driver.py:1195`). In Codex app-server goal-RPC,
   `thread/goal/get` returns `"complete"` **only because the model called `thread/goal/set status:complete`
   on its own thread**. Nothing in bs/OpenSymphony runs the outcome's acceptance and writes the status back;
   the bs driver only ever sets `status:active` at launch (`codex_driver.py:1008`) and otherwise *reads*.
   So completion is a **model self-declaration**.

2. **The Conduct sandbox is offline.** `turn/start` pins `sandboxPolicy networkAccess:false`
   (`codex_driver.py:1010`). **Rust** deliverables self-verify there — `cargo build/fmt/clippy/nextest` run
   offline → the model self-certifies → calls `thread/goal/set complete` → **exit 0**. **Frontend**
   deliverables cannot: `pnpm install` fails (`SecItemCopyMatching -50`, macOS keychain in the sandbox; never
   links `node_modules/.bin`), so `tsc`/`vitest`/`vite build` are unprovable in-sandbox. The model — told by
   the nudge text to "set complete **if** the acceptance is fully met" — conservatively leaves the goal
   `active` (or marks `blocked` in a fix-round) → `if final != "complete": return 6` → **exit 6**
   (`goal_active_after_turn` / `goal_blocked_after_turn`) → closed via the interrupted-with-delta path, with
   the orchestrator running pnpm **outside** the sandbox during Grade.

**The correlation is near-total: all 7 Rust cycles reached `goal=complete` (exit 0); 6 of 7 frontend cycles
left the round-0 goal non-complete (exit 6).** (The 7th frontend cycle — 026 — *did* reach complete at
round 0, then its fix-round blocked offline the moment a `pnpm` gate entered the goal; that **confirms** the
mechanism rather than breaking the pattern — see the table footnotes.) The residual issue is therefore
*structural*: most frontend Conduct turns pay an interrupted-with-delta `recovery_decision.yaml` tax (or are
routed as a Grade-stage finding, e.g. cycle-027), and `conduct_result=semantic_failed` mislabels a
*structural, expected* condition as a *failure*.

---

## Scope

**IN (this investigation):** characterize the root cause of `goal_active_after_turn` /
`goal_blocked_after_turn` on frontend `/bs` cycles; lay out options A/B/C; recommend A; define an observable
Definition-of-Done and the files each option would touch.

**OUT — explicitly deferred; MUST NOT be implemented from this doc without a fresh council verdict:**
changing the success oracle or auto-completing the goal; turning `--goal-completion-nudge` on by default;
auto-accepting non-complete deltas. The 2026-06-13 council ruled oracle-change / auto-complete out of scope
(determinism = needs_human). This doc is **investigation + options only**; implementing the chosen option
requires its own council verdict and a normal release cycle.

---

## Evidence — Conduct round-0 goal status, cycles 018–031

| Cycle | Task | Type | round-0 goal | driver exit | reached complete | recovery used |
|---|---|---|---|---|---|---|
| 018 | B-018 symphony-adapter | rust | complete | 0 | ✅ | no |
| 019 | B-019 symphony-shape | rust | complete | 0 | ✅ | no |
| 020 | B-020 symphony-grade | rust | complete | 0 | ✅ | no |
| 021 | B-021 symphony-evolve | rust | complete | 0 | ✅ | no¹ |
| 022 | B-022 UI-M0 | frontend | active | 6 | ❌ | yes (×3) |
| 023 | B-023 UI-M1 | frontend | active | 6 | ❌ | yes |
| 024 | B-024 UI-M2 | frontend | active | 6 | ❌ | yes |
| 025 | B-025 UI-M3 | frontend | active | 6 | ❌ | yes² |
| 026 | B-026 UI-M4 | frontend | **complete** | 0 | ✅³ | no |
| 027 | B-027 UI-M5 | frontend | **blocked** | 6 | ❌ | no⁴ |
| 028 | B-030 grade sandbox | rust | complete | 0 | ✅ | no |
| 029 | B-031 grade containment | rust | complete | 0 | ✅ | no |
| 030 | B-032 grade critic | rust | complete | 0 | ✅ | no |
| 031 | B-028 UI-M6 | frontend | active→blocked⁵ | 6 | ❌ | yes |

¹ cycle-021 was escalated, but for an **unrelated** reason (git Chinese-locale stderr matching broke 3 tests
→ P0+P1 strict-decrease violated). Its goal completed **every** turn — the cleanest counter-example: a Rust
task whose goal completed yet still failed Grade. Goal oracle was never the issue.
² cycle-025 round 0 was verify-accepted, but **both** fix-round-1 attempts left goal `active` with **zero
correction uptake** → escalated. That is a *distinct* failure (the cycle-025 `CONV` root cause, already
fixed via `BS_OUTCOME_READ_V2` + `fix_round_zero_uptake`), layered on top of the goal oracle. Later
remediated to PR #38.
³ cycle-026 round 0 reached complete cleanly — **but** the moment its fix-round folded an orchestrator-side
`pnpm install + tsc + vitest + build` gate into the goal, the fix-round turn **blocked** offline (`tk-001`).
This proves the discriminator is "is the goal's acceptance verifiable in-sandbox," not the file extension.
⁴ cycle-027 `tk-003` is the clearest statement: goal `blocked` **because** the offline sandbox cannot run
`pnpm install` (`SecItemCopyMatching -50`); treated as a Grade-stage finding (no `recovery_decision.yaml`
needed per contract). `wr-001` proposes a `conduct_blocked=frontend_gates_orchestrator_owned` signal.
⁵ cycle-031: round 0 `active`, fix-round 1 `blocked` after the nudge; gate-green delta accepted via
interrupted-with-delta. `recovery_decision.yaml` `waiver_scope = goal-status oracle only`; the pnpm gate
(typecheck / vitest 107/107) ran on the real host, not in-sandbox.

**Mechanism in one line:** not "frontend vs rust" per se, but **"can the sandbox self-verify the
deliverable?"** — Rust = yes (cargo offline) → self-complete → exit 0; Frontend = no (pnpm needs
network/keychain) → goal stays active/blocked → exit 6 → orchestrator runs pnpm outside the sandbox at
Grade.

### Key code citations (bs-skill `runtime/`)
- `codex_driver.py:1175-1202` — the oracle: `final_goal_check` → optional nudge → `if final != "complete": return 6`; `outcome_read` missing → 6; else `driver_success; return 0`.
- `codex_driver.py:1008,1010` — driver only sets `status:active`; `turn/start sandboxPolicy networkAccess:false`.
- `codex_driver.py:290-304` — `normalize_goal_status` whitelist + `extract_goal_status`; oracle compares the literal `"complete"`.
- `codex_driver.py:1037-1059,1120` (gated by the `if final == "active"` guard at `:1176`) — `GOAL_NUDGE_TEXT` + `send_goal_completion_nudge`: one extra `turn/start`, **never** sets complete, fires only on `active` (not `blocked`).
- `codex_driver.py:224-240,262-266` — goal objective: prose `"continue until the goal status is complete"`; no machine-checkable completion predicate; acceptance lives only inside the `outcome.md` the model is told to read.
- `conduct.sh:423-445` — exit 6 → `conduct_result="semantic_failed"`.
- `contract.md:219,227,232` — nudge oracle-preserving; terminal goal status is the oracle; `active` is non-success **by design**.

---

## Already done — do NOT re-propose

1. **Change the success oracle / auto-complete the goal** — ruled out by design (`contract.md:219,227,232`;
   council 2026-06-13, determinism = needs_human, maintainer-approval-required).
2. **`--goal-completion-nudge`** (v1.4.22; fail-closed v1.4.23) — one advisory follow-up turn when
   `final==active`; never sets complete, never relaxes the oracle, **does nothing for `blocked`**. Already
   shipped and SHOULD-recommended (`commands/bs.md`). It **cannot** rescue a model that genuinely cannot
   verify acceptance offline — which is exactly the frontend case.
3. **First-class interrupted-with-delta verify-and-accept** (v1.4.7) + the `recovery_decision.yaml`
   evidence gate (v1.4.8) — the current handling. **Build on it; do not reinvent it.**
4. **`turn_progress_suspect`** (v1.4.22/23, observe-only) — the cycle-019 12h-hang dual, a **different**
   class.
5. **Fix-round zero-uptake** (cycle-025 `CONV`) — already root-caused and fixed via `BS_OUTCOME_READ_V2` +
   `fix_round_zero_uptake` (`contract.md:211,236-238`). Don't re-derive it.

---

## The genuinely-open part + options

The nudge and the interrupted-with-delta path **handle the symptom** but leave the structural cause intact,
and they frame a *structurally expected* condition (frontend not in-sandbox-verifiable) as a recovery /
`semantic_failed` — requiring a hand-authored `recovery_decision.yaml` on the affected frontend cycles
(those whose round-0 goal stays non-complete and is accepted via the recovery path; cycles 026/027 took
other routes), instead of treating the offline-frontend case as a typed, expected outcome. Three
directions (A is the root fix; A and B are compatible):

### Option A — make frontend self-verifiable in the Conduct sandbox (root fix) — *recommended*
If `pnpm typecheck` / `vitest` can run **inside** the offline sandbox, the model self-verifies and
self-declares complete → exit 0, exactly like Rust, and the entire class disappears with **no oracle
change and no per-cycle recovery_decision.yaml**. Investigate:
- **Pre-provision `node_modules` before the turn** so no network/keychain is needed in-sandbox: an offline
  `pnpm install --offline` against a warmed content-addressed store, a read-only mounted pnpm store, or a
  vendored `node_modules`. The two failures to design around are `SecItemCopyMatching -50` (sandbox keychain)
  and no network — both avoided once install has already happened outside the turn.
- **OR** a narrowly-scoped, **install-only** network/keychain allowance for a dependency-fetch phase that is
  separate from (and precedes) the implementation turn.
- **Caveat:** bundling `node_modules` into the worktree can collide with frozen-surface isolation and
  worktree hygiene; scope the provisioning so it never counts as a `workspace_delta` and never trips the
  read-only / frozen-file guards.

### Option B — first-class "in-sandbox-unverifiable" Conduct outcome (classify, don't fix)
If A proves impractical, stop mislabeling. Add a first-class, **non-failure** `conduct_result` — cycle-027
`wr-001` already named it `conduct_blocked=frontend_gates_orchestrator_owned` — for the case where the turn
produced a complete `workspace_delta` but the goal's acceptance is, **by construction**, only verifiable by
the orchestrator (pnpm gates run outside the sandbox during Grade). This:
- distinguishes *structurally orchestrator-owned verification* from a genuine `semantic_failed`;
- auto-routes to the existing interrupted-with-delta verify-and-accept **without** a hand-authored
  `recovery_decision.yaml` per cycle (or via a single pre-approved standing waiver for the offline-frontend
  class);
- keeps the oracle **unchanged** (still not `"complete"`; just a typed, expected non-complete result).
- Cost: a `contract.md` amendment (new `conduct_result` + reason_code, recovery-path wording) and a council
  nod (new result class + a default behavior change).

### Option C — default-on nudge / auto-accept (lowest value, mention only)
Turning `--goal-completion-nudge` on by default, or auto-accepting gate-green non-complete deltas, is the
cheapest but weakest: the nudge **cannot** fix the structural cause (the model still can't verify offline)
and only fires on `active`, not the fix-round `blocked`. Requires a fresh council verdict to flip a default
under the oracle-unchanged constraint. Not recommended as the primary fix.

**Recommendation:** scope **Option A** as the real fix (it removes the class and the per-cycle tax); fall
back to **Option B** if offline pnpm proves impractical. Either way, get a short council verdict for the
chosen option **before** implementing — both touch sandbox policy / a `conduct_result` class / a default.

---

## Acceptance criteria (Definition of Done for the eventual implementation — observable)
- **MUST:** a fresh frontend `/bs` cycle (a new `apps/symphony-ui` task) reaches Conduct `goal=complete`
  exit 0 at round 0 **without** an interrupted-with-delta `recovery_decision.yaml` — **OR**, under Option B,
  terminates with the new typed non-failure `conduct_result` and closes without a hand-authored
  `recovery_decision.yaml`.
- **MUST:** the Rust path is unchanged (still self-completes, exit 0).
- **MUST:** the oracle is unchanged for genuinely-unverifiable / refused turns — no auto-complete; a real
  semantic failure still exits 6.
- **MUST:** no regression in the backtest corpus; `release.sh` G1–G4 gates green.
- **SHOULD:** the dogfood-log stops recording the offline-frontend case as `semantic_failed`.

## Files likely touched (depends on chosen option)
- **Option A:** `runtime/conduct.sh` (pre-turn dependency provisioning for frontend worktrees) +
  possibly `runtime/preflight.sh` (warmed-store probe) + `contract.md` (sandbox/provisioning note +
  §changelog) + version bumps (`skill.yaml`, contract title, `README.md`, `codex_driver.py` /
  `preflight.sh` client version, `bundle/` template) + manifest relock via
  `harness/evolve-loop/bin/verify-manifest.sh`.
- **Option B:** `runtime/codex_driver.py` (new `conduct_result` + reason_code) + `runtime/conduct.sh`
  (map it) + `contract.md` (§Conduct invariants + recovery-path amendment + §changelog) + version bumps +
  manifest relock + backtest if `grade_lint` is touched.

## Process
Isolated worktree; frozen-design framing (no deviation from the resolved option without a re-shape);
**council verdict for the chosen option BEFORE implementation** (cite
`~/.claude/council-logs/20260613-211210-bs-evolve-7-escalations.md` + the oracle-unchanged constraint);
release via `harness/evolve-loop/bin/release.sh` G1–G4; backtest gate REQUIRED only if `grade_lint` changes
(else skipped-with-reason); independent Codex deep-review to PASS before done.
