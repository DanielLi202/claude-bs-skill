<!-- runtime asset: bs-evolve-loop orchestration spec v2 (closure-ledger model); fed to /loop, not documentation -->
# bs-evolve-loop v2 — `/loop` body (closure-ledger model)

## Canonical wake prompt (WAKE_PROMPT)

Every `ScheduleWakeup` in this loop passes EXACTLY this line as `prompt` — never this
file's full text. Each wake therefore re-reads this file fresh, so edits to this file
(including the loop's own Stage-4 self-improvements) take effect next iteration:

    WAKE_PROMPT = 读取 /Users/lidongyuan/workspace/utils/bs-skill/harness/evolve-loop/loop-prompt.md 并严格按其执行一轮 bs-evolve-loop 迭代

The human launches the first turn with the same line prefixed by `/loop` (do NOT use
`"$(cat …)"` — the Claude Code input box performs no shell expansion; the explicit-read
line is the mechanism-correct form).

You are the **orchestrator**. The unit of work is a **cycle closure**, tracked on disk in
`reviews/opensymphony/cycle-NNN/closure.yaml` (committed to the bs-skill repo). An
iteration = *advance the newest incomplete closure*; a NEW `/bs` cycle may start only when
no incomplete closure exists. Leftover work is structurally impossible: unfinished work is
an open ledger, and the next turn resumes it from disk — never from context memory.

## Hard invariants
1. **SERIAL.** Exactly ONE in-flight stage at any time (backgrounded or not); no parallel
   stages; the `RUNNING` lock spans the whole iteration.
0. **NEVER hold the turn open waiting for an external process.** Long work runs in
   background and the turn ENDS; notifications/wakeups re-invoke you. A turn held open by
   polling freezes every pending ScheduleWakeup — the loop's entire recovery layer.
2. **Thin orchestrator.** Heavy work runs in the `/bs` subagent or `codex … > file`; you
   ingest summaries + ledger files only.
3. **Pause-and-surface, never fabricate.** Hard-stop / unrecoverable failure → write the
   ledger truthfully, release the lock, report exact options, END (no reschedule).
4. **Self-closing iteration.** Everything discovered this cycle is either (a) LANDED on
   main this iteration, or (b) explicitly listed in `closure.yaml.escalated_to_human` and
   named in your end-of-turn report. There is NO third bucket ("recorded for later" is
   forbidden).
5. **Full-auto release is GUARDED** by release.sh gates G1-G4 (versions / unittest /
   manifest relock / **backtest with fresh-context-verified adjudications**).
6. **Commit early, commit per stage.** Each stage's artifacts (r1, r2, closure.yaml
   updates, adjudications) are committed+pushed when produced, so an interruption loses
   at most the in-flight stage.

## Config (every turn)
```bash
export BS_LOOP_SKILL_REPO=/Users/lidongyuan/workspace/utils/bs-skill
export BS_LOOP_TARGET_REPO=/Users/lidongyuan/workspace/utils/OpenSymphony-V3
export BS_LOOP_STATE_DIR="$BS_LOOP_TARGET_REPO/.prompts/loop"     # gitignored runtime state
HARNESS="$BS_LOOP_SKILL_REPO/harness/evolve-loop"
REVIEWS="$HARNESS/reviews/opensymphony"        # closure ledgers + evidence live HERE (in git)
CORPUS="$BS_LOOP_TARGET_REPO/.prompts/dogfood" # historical cycle artifacts (machine-local)
```
First-ever launch: `python3 "$HARNESS/bin/loop-state.py" init --target … --skill … --mode auto --max 5`.

**Codex invocation (MANDATORY form — cycle-019 incident; maintainer ruling: duration
never kills, only "no longer working" is an exception):** every codex call goes through
the liveness wrapper, launched with `run_in_background: true`, after which you END YOUR
TURN and let the completion notification (or a check-in wake) re-invoke you:
```bash
bash "$HARNESS/bin/run-codex-staged.sh" --stage <iterNNN-stagename> --stall-sec 1200 \
  --prompt <prompt-file> --log <log-file> --cwd <dir> [--expect-writes] \
  [-- --sandbox read-only|--sandbox workspace-write --full-auto]
```
(`--expect-writes` on implementation/remediation stages only.) The wrapper runs codex in
its own process group, refreshes `$BS_LOOP_STATE_DIR/inflight/<stage>.json` every sample
(`last_progress_at`, `suspect[]`), and treats three signals as liveness — log growth,
process-group CPU delta, workdir file activity. ALL quiet for stall-sec ⇒ evidence
snapshot (`<log>.stall_evidence/`) → group reaped → **exit 125** = ordinary stage failure:
salvage any partial delta by gates → retry the stage once → else pause-and-surface.
There is NO wall-clock kill: a genuinely productive 6-hour run keeps running.
- **Fake-alive (busy-loop) is handled by JUDGMENT, not by rules:** the wrapper only FLAGS
  suspicion (`repetitive_output`, `workspace_stagnant`) into the inflight record. After
  backgrounding a stage, arm `ScheduleWakeup(2700s, reason: "stage check-in", prompt:
  WAKE_PROMPT)`. Check-in wakes land in Step 0's lock-held triage, which adjudicates (see
  Step 0.4).
- **NEVER hold the turn open waiting** — no foreground polling, no sleep/grep watcher
  loops, no repeated Read-polling of the log. A held turn FREEZES every pending
  ScheduleWakeup (this is exactly how the cycle-019 remediation hung 12h+ with zero
  wake-ups). Background + end turn is the only allowed waiting pattern.
- NEVER pass `-m` (ChatGPT-auth rejects `gpt-5.2`; the config default, e.g. `gpt-5.5`, is
  the account's best model); the wrapper already forces `xhigh` + stdin prompt.
- **codex CANNOT git-commit under the sandbox** (`.git` read-only) — one codex run per
  item; the ORCHESTRATOR verifies each result (suite + targeted greps) and commits.
  Only release.sh tags/pushes.
- **Lease refresh:** after EVERY completed stage, `touch "$BS_LOOP_STATE_DIR/RUNNING.lock"`.
  The 2h stale threshold then means "no stage progress for 2h", which (with all budgets
  < 2h) cleanly separates a dead iteration from a healthy long one.

---

## Step 0 — Stop-checks, heartbeat, guard, closure scan (every turn, FIRST, in this order)
1. `loop-guard.sh check-stop` → exit 10 (STOP file) ⇒ report "kill-switch present"; END
   with NO reschedule. The STOP file is the universal absorber: every in-flight wakeup
   that lands here dies quietly, which is how the loop is cancelled despite ScheduleWakeup
   having no external cancel.
2. `loop-state.py should-stop` → a reason prints ⇒ report it; END with NO reschedule
   (stop conditions absorb stray heartbeats the same way).
3. **Fallback heartbeat (arm BEFORE taking the lock):** `ScheduleWakeup(delaySeconds:
   3600, reason: "bs-evolve fallback heartbeat", prompt: WAKE_PROMPT)`. If this turn later
   dies mid-iteration (session kill — observed twice in cycle-018), this probe resumes the
   loop from the closure ledger; after a NORMAL iteration it wakes into a held lock or a
   stop condition and exits harmlessly.
   ⚠️ **DO NOT END THE TURN HERE.** After this call the harness prints "Nothing more to do
   this turn — the harness re-invokes you when the wakeup fires". That hint is WRONG for
   this specific arm — it describes the normal work-then-schedule pattern, but this
   heartbeat is a pre-work SAFETY NET. IGNORE the hint and continue to Step 0.4 in the
   SAME turn. (A model that obeys the hint produces an idle do-nothing loop that re-arms
   a heartbeat every hour forever — observed with the Step-0.3 arm on 2026-06-12.) In
   this loop, a turn legitimately ends after ScheduleWakeup in exactly THREE places:
   Stage-7 chain re-arm, the check-in arm right after backgrounding a stage, and the
   Step-0.4 exit-11 retry arm. Nowhere else.
4. `loop-guard.sh acquire` → exit 11 (locked: an iteration is in flight — possibly this
   session's own backgrounded stage) ⇒ run the **lock-held triage**:
   a. read `$BS_LOOP_STATE_DIR/inflight/*.json`. NO inflight files + lock stale-aged ⇒
      holder died between stages: `rm RUNNING.lock`, PROCEED as the new owner (closure
      scan resumes; salvage uncommitted deltas by gates, as ever).
   b. inflight present, recorded `pgid` DEAD (`kill -0 -- -<pgid>` fails) but the stage
      artifact/log shows no completion ⇒ the wrapper died with its session: reap leftovers,
      delete the inflight file, `rm RUNNING.lock`, PROCEED as owner (re-run the stage,
      salvaging by gates).
   c. inflight present + pgid alive + `suspect` non-empty OR the stage has run >90min ⇒
      **JUDGMENT REVIEW (orchestrator self-adjudicates — maintainer ruling):** read the
      log tail (~200 lines) and, for write stages, `git -C <cwd> diff --stat`. Ask: is
      this CONVERGING (varied output, evolving errors, advancing work) or LOOPING (same
      error/action repeating, workspace frozen)? Converging ⇒ re-arm
      `ScheduleWakeup(2700s, check-in)` and END. Looping ⇒ snapshot the evidence into the
      iter dir, reap the group (TERM→poll→KILL), salvage partial delta by gates, retry the
      stage once; a second stall/loop verdict on the same stage ⇒ pause-and-surface with
      both evidence sets.
   d. otherwise (alive, no suspicion, young) ⇒ `ScheduleWakeup(delaySeconds: 1800,
      reason: "lock-held retry probe", prompt: WAKE_PROMPT)` then END.
5. **Closure scan:** `python3 "$HARNESS/bin/closure.py" --reviews-root "$REVIEWS" newest-open`
   - prints a dir ⇒ resume that closure: `closure.py --dir <dir> next` → jump to that stage
     (r1→Stage 2, r2→Stage 3, skill_release→Stage 4, remediation→Stage 5, close→Stage 6).
   - exit 10 (none open) ⇒ also check: latest CLOSED `/bs` cycle in `$CORPUS` (≥ cycle-018)
     without a closure dir ⇒ adopt it (`closure.py --dir "$REVIEWS/<cycle>" init`), start at
     Stage 2. Otherwise → Stage 1 (new cycle).
6. `loop-state.py begin-iteration`.

## Stage 1 — Dev cycle via `/bs` (BACKGROUND subagent)
Spawn ONE `general-purpose` subagent **with `run_in_background: true`, then END YOUR TURN**
(an awaited subagent would hold the turn for the whole multi-hour cycle and freeze every
wakeup — same trap as foreground codex). Arm `ScheduleWakeup(2700s, check-in)` before
ending. Subagent task: run `/bs` to completion in `$BS_LOOP_TARGET_REPO` (it self-commits,
merges its PR, closes ledger+backlog atomically), return ONLY the JSON: `{selected_task,
title, cycle_id, cycle_dir, start_commit, merge_commit, pr, merged, grade_pass,
backlog_exhausted, hard_stop, hard_stop_options, escalated, notes}`.
Check-in wakes triage via Step 0.4 — for this stage the liveness/judgment evidence is the
cycle dir itself: `step_events.jsonl` mtime, conduct evidence growth, and whether
`conduct.sh`/`codex_driver.py` processes are alive (`/bs` has its own internal driver
supervision; the loop only detects a wedged/dead subagent, not a slow one).
- `backlog_exhausted` ⇒ `loop-state.py set stop_reason backlog_exhausted`; release; report; END.
- `hard_stop || escalated || !merged || !grade_pass` ⇒ pause-and-surface (invariant 3).
- else `closure.py --dir "$REVIEWS/<cycle_id>" init`; commit closure.yaml; → Stage 2.

## Stage 2 — r1: independent delivery review (codex, read-only)
**Escalated cycles** (the adopted cycle closed `escalated` — its delta is UNMERGED, held
on `bootstrap/cycle-NNN`): r1 reviews `git diff main...bootstrap/cycle-NNN` plus the
escalation evidence (all grade rounds, the step_events escalation reason), and the review
question widens to BOTH "what escaped" AND "why did the fix loop fail to converge"
(rubric drift between rounds? unfixable shaping? tooling bug like locale-dependent
parsing?). Stage 5 for such cycles = drive the held delta to mergeable (worktree from
that branch, fix the escalation blockers, full gates, PR → merge) or, if gates prove it
unsalvageable, escalate-to-human with the evidence — never silently abandon a
materially-complete delta.
Merged cycles, as before: adversarial review of the merged delta vs outcome.md + the cycle's own grade docs;
output ends with fenced `r1_verdict` YAML (`escaped_findings[{id,severity,where,why,
evidence}]`). Write `$REVIEWS/<cycle>/r1.md`; validate the block exists.
→ `closure.py set r1 done`; `git add/commit/push` (bs-skill) the r1 + closure update.

## Stage 3 — r2: process review → DETERMINISTIC plan (codex, read-only)
Inputs: r1.md + the cycle's process evidence (`step_events.jsonl`, grade/lint/verify
evidence, incidents) + the bs-skill contract/runtime/prompts. For each r1 finding: which
gate should have caught it and why it didn't. **The prompt MUST require every
`proposed_changes[]` item to carry `determinism: deterministic | needs_human`** —
deterministic = patch-level, mechanically verifiable (lint rule + fixtures / contract
clause / runtime guard); needs_human = redesign or product judgment.
Write `$REVIEWS/<cycle>/r2.md` (fenced `r2_plan`).
→ `closure.py set r2 done`; copy `needs_human` items into
`closure.yaml.escalated_to_human`; commit+push.

## Stage 4 — Implement ALL deterministic r2 items into bs-skill + release
This stage lands **every** `determinism: deterministic` item this iteration. No top-N, no
backlog file.
1. Anchor: `loop-state.py set anchor.skill_sha $(git -C $BS_LOOP_SKILL_REPO rev-parse HEAD)`.
2. **Per-item implementation** (chunk related items into codex runs; each ITEM = its own
   commit). The implement prompt must require, per item:
   - the rule/guard itself, in the existing helper style;
   - an explicit **in-scope predicate** (fail-closed but narrow), error message naming the
     escaped class;
   - **paired fixtures from REAL corpus text**: must-fire derived from the escaping cycle's
     actual grade text; must-not-fire from a genuinely clean cycle's actual text (negated
     phrases included — synthetic-clean fixtures mask scope bugs);
   - unittest green before the item's commit; commit message `vNEXT <item-id>: <summary>`;
   - final commit: version bump (next patch) + contract changelog + client versions +
     **manifest relock**.
3. **Backtest gate:**
   `python3 "$HARNESS/bin/backtest.py" --skill-repo $BS_LOOP_SKILL_REPO --corpus-root
   $CORPUS --baseline-ref <last-release-tag> --target-cycle <cycle> --out
   "$REVIEWS/<cycle>/backtest/<new-version>/"`
   - exit 1 (must-fire failed) ⇒ the new rules don't catch the known escape: fix rules
     (more commits), rerun. Do NOT release.
   - misfire candidates ⇒ **adjudicate in-loop**: write `backtest_adjudication.yaml`
     (verdict per fire: `true_positive_historical | false_positive`, rationale, evidence
     quotes). `false_positive` ⇒ refine the rule now (new commit), rerun backtest, until
     misfires are only true_positive_historical or eliminated.
   - **Fresh-context verification (mandatory when any adjudication exists):** ONE clean
     codex read-only session (no shared thread; prompt = adjudication + artifact paths
     only) instructed to REFUTE each verdict → `backtest_adjudication_verify.md` with
     fenced `adj_verify`. Any `agree: false` ⇒ treat as false_positive (refine + rerun) or
     pause-and-surface if contested twice.
4. **Release:** `release.sh --skill … --target … --version vNEXT --summary …
   --backtest-report <report> --adj-verify <verify>` (per-item-commit model: gates → tag →
   push → pin-sync → health). Gate failure (exit 2) ⇒ fix or revert per-item commits;
   exit 3/4 ⇒ `rollback.sh` (+`--pushed` if needed) then pause-and-surface.
→ `closure.py set skill_release vNEXT`; commit+push closure + backtest evidence.

## Stage 5 — Remediate the r1 findings in the TARGET repo (under the NEW gates)
Direct codex fix (maintainer decision: not via `/bs` — lexicographic task selection cannot
prioritize a dynamic remediation task), with the full gate stack:
1. **ISOLATED WORKTREE, never the main checkout** (cycle-019 incident left the user's main
   repo stranded on a remediation branch):
   `git -C $BS_LOOP_TARGET_REPO worktree add /private/tmp/remediate-<cycle> -b remediate/<cycle>`,
   then codex (workspace-write, `--cwd` the worktree) fixes EVERY r1 finding; add a
   negative/regression test per finding; run the binding's `verify.grade.code` commands
   until green. Remove the worktree after merge.
2. Author `$REVIEWS/<cycle>/remediation_grade.md` (spec_compliance_matrix over the r1
   findings + negative_regression_tests + secret_leakage_audit + dependency_spec_review,
   same schema as a bs Grade) and run the **NEW** `grade_lint.py` on it — this is the
   same-iteration canary consuming the just-released rules. Lint failure from a rule bug ⇒
   fix the rule (patch release vNEXT+1); from a remediation gap ⇒ fix the code.
3. **Fresh-context r1-verify:** clean codex read-only session re-reads the remediation diff
   vs r1.md and confirms each finding closed → `$REVIEWS/<cycle>/r1_verify.md` (fenced
   `r1_verify`, per-finding `closed: true|false`). Any `closed: false` ⇒ iterate.
4. PR → merge to target main; append a `post_close_amendments` row (commit + purpose) to
   the cycle's dogfood-log entry; commit+push target main.
→ `closure.py set remediation <merge-commit>`; commit+push.

## Stage 6 — Close the ledger
`closure.py set closed true`; commit+push bs-skill. Verify both repos: clean trees, HEAD ==
origin/main. Then report (REQUIRED content): cycle, r1 verdict, skill release + item count,
backtest summary (fires/adjudications), remediation commit, and **every
`escalated_to_human` item verbatim** — these are live handoffs to the user, not records.

## Stage 7 — Stop or reschedule (the self-chaining step)
1. `loop-state.py should-stop` → a reason prints ⇒ report it; END with NO reschedule —
   the chain terminates here, and any still-pending heartbeat is absorbed by the same
   stop condition on its next firing.
2. `loop-state.py get mode` == `dry-run` ⇒ single-iteration mode: report and END with NO
   reschedule.
2b. **Graceful quiesce:** if `$BS_LOOP_STATE_DIR/PAUSE` exists ⇒ report "paused at
   iteration boundary (PAUSE present — typically a release window)" and END with NO
   reschedule. Unlike STOP, PAUSE never aborts an in-flight iteration or its supervision
   wakes — it only declines to start the next one. Do NOT delete the file (the operator
   removes it and relaunches).
3. Else **re-arm the chain:** `ScheduleWakeup(delaySeconds: 90, reason: "next bs-evolve
   iteration", prompt: WAKE_PROMPT)` — always the canonical WAKE_PROMPT line, never this
   file's contents.
4. **ALWAYS last:** `loop-guard.sh release`.

---

## Operator controls
- **Stop (hard):** `touch "$BS_LOOP_TARGET_REPO/.prompts/loop/STOP"` (honored at next Step 0
  by EVERY wake incl. in-flight supervision; this IS the cancel — ScheduleWakeup has no
  external cancel). Resume: delete it.
- **Pause (graceful, for release windows):** `touch "$BS_LOOP_TARGET_REPO/.prompts/loop/PAUSE"`
  — the current iteration finishes WITH full supervision; the chain simply doesn't re-arm
  at Stage 7. Release the skill in the quiet window, then `rm PAUSE` and relaunch.
- **Relaunch checklist** (after ANY stop — `stop_reason` is a LATCH and survives the
  condition that set it): `rm -f STOP PAUSE`; `loop-state.py set stop_reason null`;
  confirm `iteration < max_iterations` (raise via `set max_iterations N` if at the
  ceiling); then `loop-state.py should-stop` must print nothing (exit 0) BEFORE typing
  the /loop line. When a turn latches `stop_reason`, it should record only the durable
  reason (e.g. `backlog_exhausted`), never transient conditions like a max-iterations
  ceiling that the operator may later raise.
- **Inspect:** `closure.py --dir "$REVIEWS/cycle-NNN" get` · `loop-state.py get history` ·
  `git -C $BS_LOOP_SKILL_REPO log --oneline`.
- A closure stuck on a contested adjudication or an escalated decision pauses the loop —
  answer in `closure.yaml` (or remove the item) and relaunch.
