# bs-evolve-loop

A self-paced `/loop` that dogfoods the `bs` skill and **evolves it from its own output**:
run a `/bs` dev cycle, independently review the delivery, review the *process* that produced
it, then patch the `bs` skill so the next cycle can't leak the same class of defect — and
repeat. One iteration = one full pipeline. Strictly serial.

```
┌──────────────── one iteration (one /loop turn) ────────────────────────────┐
│ 0 guard        STOP-file? lock? stop-conditions?                            │
│ 1 dev          subagent runs /bs in OpenSymphony  (self-commits + merges)   │
│ 2 r1.md        codex xhigh, read-only  — independent delivery review        │
│ 3 r2.md        codex xhigh, read-only  — why did r1's findings escape bs?   │
│ 3.5 commit     push r1+r2 to bs-skill main                                  │
│ 4 implement    codex xhigh, workspace-write — patch bs-skill + release      │
│ 5 health       next /bs preflight is the regression test                    │
│ 6 close        ScheduleWakeup(next) | stop                                  │
└────────────────────────────────────────────────────────────────────────────┘
```

## Two repos, two git targets
| What | Repo | Committed by |
|---|---|---|
| The dev deliverable (Phase-2 backend/UI) | **OpenSymphony-V3** | `/bs` itself (start + close + PR merge) |
| r1.md / r2.md review docs | **bs-skill** `harness/evolve-loop/reviews/opensymphony/cycle-NNN/` | Step 3.5 |
| The skill improvement + patch release | **bs-skill** main + tag | Step 4 `release.sh` |
| The refreshed contract pin | **OpenSymphony-V3** `.bootstrap*` | `release.sh` → `sync-bs-binding.py` |

The strict OpenSymphony doc red lines never see r1/r2 — they live here, where the tool being
evaluated lives. OpenSymphony only ever gets its normal `/bs` commits + the binding refresh.

## Layout
```
harness/evolve-loop/
├── README.md            ← this runbook
├── loop-prompt.md       ← the /loop body (the executable spec; feed it to /loop)
├── bin/
│   ├── loop-guard.sh    ← kill-switch + single-iteration time-lease lock
│   ├── loop-state.py    ← state.json ledger (init/get/set/begin-iteration/should-stop)
│   ├── verify-manifest.sh ← contract manifest sha table == actual file hashes (release gate)
│   ├── release.sh       ← Stage-4 git/tag/push + pin-sync plumbing (auto mode)
│   └── rollback.sh      ← restore both repos to the pre-release anchor
└── reviews/opensymphony/cycle-NNN/{r1.md,r2.md}
```
Runtime state (gitignored, machine-local) lives in `OpenSymphony-V3/.prompts/loop/`:
`STOP`, `RUNNING.lock`, `state.json`, `iter-NNN/`.

## Launch

**1. First run — supervised dry-run (single iteration, stops before any skill release):**
```bash
HARNESS=/Users/lidongyuan/workspace/utils/bs-skill/harness/evolve-loop
python3 "$HARNESS/bin/loop-state.py" init \
  --target /Users/lidongyuan/workspace/utils/OpenSymphony-V3 \
  --skill  /Users/lidongyuan/workspace/utils/bs-skill --mode dry-run --max 5
/loop "$(cat "$HARNESS/loop-prompt.md")"
```
The dry-run runs `/bs` → r1 → r2 → commits the reviews → has codex *author* the skill patch,
then **pauses and shows you the diff**. Nothing is tagged/pushed to the skill until you OK it.

**2. Go live (after the dry-run looks right):**
```bash
python3 "$HARNESS/bin/loop-state.py" set mode auto
/loop "$(cat "$HARNESS/loop-prompt.md")"
```

## Decisions baked in
- **Q1 artifacts → bs-skill repo.** OpenSymphony stays clean.
- **Q2 Stage-4 → full-auto release**, fenced by the four guardrails below.
- **Q3 mechanism → dynamic self-paced `/loop`** + file kill-switch + state ledger.
- **Q4 failures → pause-and-surface**, never fabricate approval.

## The four guardrails on full-auto skill release
1. **Unittest gate.** `release.sh` re-runs `python3 -m unittest discover -s tests` (150 tests)
   and refuses to commit if red.
2. **Manifest-relock gate.** `verify-manifest.sh` proves the contract sha table matches actual
   file hashes — a botched relock can't ship (it would later fail `/bs doctor`).
3. **Patch-only.** The bump is always the next PATCH and `sync-bs-binding.py` independently
   refuses to cross `compatible_range` (`>=1.3,<2.0`).
4. **Rollback anchor + kill-switch.** The pre-release skill sha is recorded; if the *next*
   `/bs` preflight fails, `rollback.sh` restores both repos. `touch .prompts/loop/STOP` ends
   the loop at the next iteration boundary.

## Stop conditions (any one ends the loop, no reschedule)
- `STOP` file present (the manual kill-switch).
- `/bs` reports the backlog is exhausted (nothing to do until Phase-2 tasks are groomed).
- `max_iterations` reached (default 5).
- `consecutive_failures` ≥ threshold (default 2) — circuit breaker.
- Any pause-and-surface event (hard-stop / escalation / unrecoverable stage failure).

## Recovery
- **Inspect:** `loop-state.py get history` and `OpenSymphony-V3/.prompts/loop/iter-NNN/`.
- **A bad release shipped:** `rollback.sh --skill … --target … --anchor-sha <state.anchor.skill_sha> --bad-tag vX.Y.Z [--pushed]`, then `cd OpenSymphony-V3 && /bs doctor`.
- **Stuck lock** (a crashed iteration): the lock is a 2h time-lease; or `rm .prompts/loop/RUNNING.lock`.

> **Validation status:** `loop-guard.sh`, `loop-state.py`, `verify-manifest.sh` are unit-smoke
> tested. `release.sh` / `rollback.sh` are exercised end-to-end only at the **first real
> (auto-mode) release**, which is why the first run is a supervised dry-run that stops before
> them. Treat the first auto release as itself supervised.

## Cost / cadence
Each iteration is heavy: a full `/bs` cycle (~10–30 min) + two `codex xhigh` reviews +
an implement pass. Budget ~40–70 min and significant tokens per iteration. The
`max_iterations` cap and the `STOP` file are your throttles.
