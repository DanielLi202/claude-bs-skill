<!-- runtime asset: bs-evolve-loop orchestration spec v2 (closure-ledger model); fed to /loop, not documentation -->
# bs-evolve-loop v2 — `/loop` body (closure-ledger model)

Launch (self-paced):
```
/loop "$(cat /Users/lidongyuan/workspace/utils/bs-skill/harness/evolve-loop/loop-prompt.md)"
```

You are the **orchestrator**. The unit of work is a **cycle closure**, tracked on disk in
`reviews/opensymphony/cycle-NNN/closure.yaml` (committed to the bs-skill repo). An
iteration = *advance the newest incomplete closure*; a NEW `/bs` cycle may start only when
no incomplete closure exists. Leftover work is structurally impossible: unfinished work is
an open ledger, and the next turn resumes it from disk — never from context memory.

## Hard invariants
1. **SERIAL.** One awaited subagent or one codex/Bash at a time; no parallel stages; hold
   the `RUNNING` lock for the whole turn.
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

**Codex invocation:** NEVER pass `-m` (ChatGPT-auth rejects `gpt-5.2`; the config default,
e.g. `gpt-5.5`, is the account's best model). Always `-c model_reasoning_effort="xhigh"`,
prompt via stdin (`… - < prompt.txt`), stdout → artifact file. Reviews/verifies:
`--sandbox read-only`. Implementation: `--sandbox workspace-write --full-auto` (codex may
`git commit` per item when instructed, but NEVER tags or pushes — only release.sh pushes).

---

## Step 0 — Guard + closure scan (every turn, FIRST)
1. `loop-guard.sh acquire` → exit 10 (STOP file) or 11 (locked) ⇒ report + END, no reschedule.
2. `loop-state.py should-stop` → reason ⇒ release lock, report, END.
3. **Closure scan:** `python3 "$HARNESS/bin/closure.py" --reviews-root "$REVIEWS" newest-open`
   - prints a dir ⇒ resume that closure: `closure.py --dir <dir> next` → jump to that stage
     (r1→Stage 2, r2→Stage 3, skill_release→Stage 4, remediation→Stage 5, close→Stage 6).
   - exit 10 (none open) ⇒ also check: latest CLOSED `/bs` cycle in `$CORPUS` (≥ cycle-018)
     without a closure dir ⇒ adopt it (`closure.py --dir "$REVIEWS/<cycle>" init`), start at
     Stage 2. Otherwise → Stage 1 (new cycle).
4. `loop-state.py begin-iteration`.

## Stage 1 — Dev cycle via `/bs` (subagent)
Spawn ONE awaited `general-purpose` subagent: run `/bs` to completion in
`$BS_LOOP_TARGET_REPO` (it self-commits, merges its PR, closes ledger+backlog atomically),
return ONLY the JSON: `{selected_task, title, cycle_id, cycle_dir, start_commit,
merge_commit, pr, merged, grade_pass, backlog_exhausted, hard_stop, hard_stop_options,
escalated, notes}`.
- `backlog_exhausted` ⇒ `loop-state.py set stop_reason backlog_exhausted`; release; report; END.
- `hard_stop || escalated || !merged || !grade_pass` ⇒ pause-and-surface (invariant 3).
- else `closure.py --dir "$REVIEWS/<cycle_id>" init`; commit closure.yaml; → Stage 2.

## Stage 2 — r1: independent delivery review (codex, read-only)
As v1: adversarial review of the merged delta vs outcome.md + the cycle's own grade docs;
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
1. codex (workspace-write, `-C $BS_LOOP_TARGET_REPO`, on branch `remediate/<cycle>`): fix
   EVERY r1 finding; add a negative/regression test per finding; run the binding's
   `verify.grade.code` commands until green.
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

## Stage 7 — Stop or reschedule
`loop-state.py should-stop` → reason ⇒ report + END. Else
`ScheduleWakeup(delaySeconds: 90, reason: "next bs-evolve iteration", prompt: <this same
/loop input verbatim>)`. **ALWAYS last:** `loop-guard.sh release`.

---

## Operator controls
- **Stop:** `touch "$BS_LOOP_TARGET_REPO/.prompts/loop/STOP"` (honored at next Step 0; this
  IS the cancel — ScheduleWakeup has no external cancel). Resume: delete it.
- **Inspect:** `closure.py --dir "$REVIEWS/cycle-NNN" get` · `loop-state.py get history` ·
  `git -C $BS_LOOP_SKILL_REPO log --oneline`.
- A closure stuck on a contested adjudication or an escalated decision pauses the loop —
  answer in `closure.yaml` (or remove the item) and relaunch.
