# bs-evolve-loop (v2 — closure-ledger model)

A self-paced `/loop` that dogfoods the `bs` skill and **evolves it from its own output** —
and whose every iteration is **self-closing**: the dev task lands, the reviews land, the
review findings land (both in the skill and in the deliverable), all on `main`, before any
new cycle may start. Nothing is "recorded for later"; work either ships this iteration or
is explicitly escalated to the human in the iteration report.

```
┌────────────── one iteration = advance the newest open closure ───────────────┐
│ 0 guard      STOP? lock? stop-conditions? → closure scan (resume or new)      │
│ 1 dev        subagent runs /bs in OpenSymphony (self-commits + merges)        │
│ 2 r1         codex xhigh ro — independent delivery review        → commit    │
│ 3 r2         codex xhigh ro — why did r1 escape bs? DETERMINISTIC plan       │
│ 4 skill      implement ALL deterministic items, per-item commits             │
│              → BACKTEST vs corpus (must-fire + adjudicate + fresh-verify)    │
│              → release.sh G1-G4 → tag → push → pin-sync                      │
│ 5 remediate  codex fixes r1 findings in target repo UNDER THE NEW GATES      │
│              → fresh r1-verify → PR → merge → post_close_amendments          │
│ 6 close      closure.yaml closed:true → push both repos → report             │
│ 7 loop       ScheduleWakeup | stop                                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

## The closure ledger (why leftovers are impossible)
`reviews/opensymphony/cycle-NNN/closure.yaml` (committed) tracks per-cycle:
`r1 → r2 → skill_release → remediation → closed`, plus `escalated_to_human[]`.
An iteration must **resume the newest incomplete closure**; a new `/bs` cycle is allowed
only when none is open. Stage position is re-derived from disk every turn — interruptions,
compaction, or kills lose at most the in-flight stage. Helper: `bin/closure.py`.

## Where confidence comes from (the verification stack)
1. **Backtest** (`bin/backtest.py`): replay the NEW `grade_lint` against all historical
   code cycles, baseline = last release tag; only **delta** failures are attributed to the
   new rules. The target cycle MUST fire (proves the rules catch the known escape); any
   other fire is adjudicated `true_positive_historical | false_positive` with evidence.
   *Maiden run caught a real bug: v1.4.11's F5 rule lacked a `not_applicable` exemption and
   its scope regex matched negated phrases (fired on cycle-017's clean audit).*
2. **Fresh-context verification**: every adjudication (and every remediation) is reviewed
   by a CLEAN codex session prompted to refute it. Trusted only if it agrees.
3. **Paired fixtures from real corpus text**: every new rule ships a must-fire test taken
   from the escaping cycle's actual grade text and a must-not-fire test from a genuinely
   clean cycle's actual text (negated phrases included).
4. **Scope predicates**: every rule carries an explicit in-scope predicate — fail-closed
   but narrow.
5. **Per-item commits, one tag**: a bad rule is `git revert <one commit>` + patch release,
   not a full-release rollback. Anchor-based `rollback.sh` remains the emergency path.
6. **Same-iteration canary**: Stage 5's remediation grade is linted by the *just-released*
   rules — a misfiring rule is discovered within the same iteration, not the next.

## Two repos, two git targets
| What | Repo | Committed by |
|---|---|---|
| Dev deliverable | OpenSymphony-V3 | `/bs` itself |
| r1/r2, closure.yaml, backtest + adjudication evidence | bs-skill `harness/evolve-loop/reviews/opensymphony/cycle-NNN/` | Stages 2-4 |
| Skill improvements (per-item commits) + patch release tag | bs-skill main | Stage 4 (`release.sh`) |
| Contract pin refresh | OpenSymphony-V3 `.bootstrap*` | `release.sh` → `sync-bs-binding.py` |
| r1-finding remediation + `post_close_amendments` | OpenSymphony-V3 main | Stage 5 |

## Layout
```
harness/evolve-loop/
├── README.md / loop-prompt.md       runbook / the executable /loop body
├── bin/
│   ├── loop-guard.sh                kill-switch + single-iteration time-lease lock
│   ├── loop-state.py                per-run state.json (iterations, anchors, stop)
│   ├── closure.py                   per-cycle closure ledger (the self-closing core)
│   ├── backtest.py                  corpus replay: delta attribution + must-fire
│   ├── verify-manifest.sh           contract manifest relock gate
│   ├── release.sh                   gates G1-G4 → tag → push → pin-sync
│   └── rollback.sh                  restore both repos to the pre-release anchor
└── reviews/opensymphony/cycle-NNN/  r1.md r2.md closure.yaml r1_verify.md
                                     remediation_grade.md backtest/<ver>/…
```
Runtime state (gitignored): `OpenSymphony-V3/.prompts/loop/` (`STOP`, `RUNNING.lock`,
`state.json`, `iter-NNN/`).

## Launch

One-time state prep (terminal):
```bash
HARNESS=/Users/lidongyuan/workspace/utils/bs-skill/harness/evolve-loop
python3 "$HARNESS/bin/loop-state.py" init \
  --target /Users/lidongyuan/workspace/utils/OpenSymphony-V3 \
  --skill  /Users/lidongyuan/workspace/utils/bs-skill --mode auto --max 5
```
Then type ONE line in the Claude Code input box (this is the canonical WAKE_PROMPT with a
`/loop` prefix — do NOT use `"$(cat …)"`, the input box performs no shell expansion):
```
/loop 读取 /Users/lidongyuan/workspace/utils/bs-skill/harness/evolve-loop/loop-prompt.md 并严格按其执行一轮 bs-evolve-loop 迭代
```

**How it self-chains:** the launch line only ignites turn 1. Continuation lives in the
prompt file itself — Stage 7 re-arms `ScheduleWakeup(90s, WAKE_PROMPT)` after every
completed iteration, and each wake re-READS loop-prompt.md (file = single source of
truth; edits, including the loop's own self-improvements, apply next iteration). Two
safety wakeups also fly: a Step-0 fallback heartbeat (3600s — resumes from the closure
ledger if a turn dies mid-iteration) and a lock-held retry probe (1800s). Stray wakeups
are harmless by construction: the RUNNING lock prevents double-runs, and stop conditions
/ the STOP file absorb every leftover firing.

Stop: `touch OpenSymphony-V3/.prompts/loop/STOP` (the universal absorber — the only
external cancel, honored by every wakeup at Step 0). Single-iteration test run:
`loop-state.py set mode dry-run` (Stage 7 then never re-arms).

## Failure policy
Pause-and-surface (never fabricate approval): `/bs` hard-stops, gate failures after
retry, contested adjudications, and `escalated_to_human` items all stop the loop with the
exact evidence and options. Stop conditions: STOP file · backlog exhausted · max
iterations (default 5) · consecutive failures (default 2).

## Codex invocation (account gotcha)
Omit `-m` (ChatGPT-auth rejects `gpt-5.2`; config default `gpt-5.5` is the best available);
always `-c model_reasoning_effort="xhigh"`; prompt via stdin; reviews `--sandbox read-only`,
implementation `--sandbox workspace-write --full-auto`. bs-skill tests:
`python3 -m unittest discover -s tests -p 'test_*.py'`.

## Cost / cadence
An iteration is heavy: a full `/bs` cycle + 2 review runs + N implement runs + backtest +
fresh verifies + a remediation PR ≈ 2-3 h wall-clock. `max_iterations` and `STOP` are the
throttles.
