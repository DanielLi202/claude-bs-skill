<!-- runtime asset: bs-evolve-loop orchestration spec; fed to /loop, not documentation -->
# bs-evolve-loop — `/loop` body (ONE iteration per turn)

Launch (self-paced):
```
/loop "$(cat /Users/lidongyuan/workspace/utils/bs-skill/harness/evolve-loop/loop-prompt.md)"
```

You are the **orchestrator**. Each turn you run **exactly one iteration** of the
dogfood evolution pipeline, then either `ScheduleWakeup` (auto) or stop (dry-run /
stop condition). Re-derive state from disk every turn; keep your own context thin.

## Hard invariants (do not violate)
1. **SERIAL.** Never `run_in_background`. Never spawn parallel Agent batches. Exactly
   one awaited subagent **or** one `codex`/Bash per stage. Hold the `RUNNING` lock for
   the whole iteration. (Requirement 5: one task at a time.)
2. **Thin orchestrator.** Heavy work runs inside the `/bs` subagent or `codex … > file`.
   Ingest only short summaries + read `state.json`. Full r1/r2 text stays on disk.
3. **Pause-and-surface, never fabricate.** If `/bs` needs a human decision, escalates,
   or any stage fails unrecoverably → write state, release the lock, **do NOT reschedule**,
   report the exact options/evidence, end the turn. (Decision Q4.)
4. **Full-auto release is GUARDED:** unittest-green gate + manifest-relock gate +
   patch-only bump + rollback anchor + kill-switch. (Decision Q2 + guardrails.)

## Config (export once per turn)
```bash
export BS_LOOP_SKILL_REPO=/Users/lidongyuan/workspace/utils/bs-skill
export BS_LOOP_TARGET_REPO=/Users/lidongyuan/workspace/utils/OpenSymphony-V3
export BS_LOOP_STATE_DIR="$BS_LOOP_TARGET_REPO/.prompts/loop"   # gitignored runtime state
HARNESS="$BS_LOOP_SKILL_REPO/harness/evolve-loop"
REVIEWS="$HARNESS/reviews/opensymphony"
WORKSPACE_PARENT=/Users/lidongyuan/workspace/utils                # parent of both repos
```
First-ever launch only:
```bash
python3 "$HARNESS/bin/loop-state.py" init \
  --target "$BS_LOOP_TARGET_REPO" --skill "$BS_LOOP_SKILL_REPO" --mode dry-run --max 5
```
`dry-run` = single iteration, **stop before release**. Switch to auto with
`loop-state.py set mode auto` only AFTER a supervised dry-run passes.

---

## Step 0 — Guard (FIRST, every turn)
- `bash "$HARNESS/bin/loop-guard.sh" acquire "$BS_LOOP_STATE_DIR"`
  - exit **10** (STOP file) → report "kill-switch present"; **end; no reschedule**.
  - exit **11** (locked) → another iteration is live → end immediately (no double-run).
- `python3 "$HARNESS/bin/loop-state.py" should-stop` → if it exits 10 it prints a reason
  (`stop_file|backlog_exhausted|max_iterations|consecutive_failures`) → release lock,
  report, **end; no reschedule**.
- `N=$(python3 "$HARNESS/bin/loop-state.py" begin-iteration)` ; `MODE=$(… get mode)`.
- `ITERDIR="$BS_LOOP_STATE_DIR/iter-$(printf %03d "$N")"`.

## Step 1 — Dev cycle via `/bs` (subagent — context isolation, Requirement 1)
Spawn ONE `general-purpose` subagent, **awaited (not background)**, prompt:
> Run the `/bs` skill to completion in `<BS_LOOP_TARGET_REPO>`. Perform the real work —
> `/bs` self-commits, merges its PR, and atomically closes the ledger. Stay strictly
> within `/bs`; do not improvise outside it. Then return ONLY this JSON (no prose):
> ```json
> {"selected_task":"","title":"","cycle_id":"","cycle_dir":"","start_commit":"",
>  "merge_commit":"","pr":"","merged":false,"grade_pass":false,
>  "backlog_exhausted":false,"hard_stop":false,"hard_stop_options":"",
>  "escalated":false,"evidence_dir":"","notes":""}
> ```
> If `/bs` stops for a human decision, do NOT infer approval — set `hard_stop:true` with
> the exact options and return.

Branch on the payload:
- `backlog_exhausted:true` → `loop-state set stop_reason backlog_exhausted`; release lock;
  report; **end** (this is success — nothing left to do until Phase-2 backlog grows).
- `hard_stop || escalated || !merged || !grade_pass` → **PAUSE-AND-SURFACE**:
  `loop-state append-history` an entry `stage:"paused_stage1"`; release lock; report the
  exact options/evidence to the user; **end; no reschedule**.
- else: record `cycle_id`, `pr`, commits into state; continue. Set `CYCLE=<cycle_id>`.

## Step 2 — r1.md (codex, delivery review — INDEPENDENT second signal)
```bash
mkdir -p "$REVIEWS/$CYCLE"
codex exec --skip-git-repo-check -C "$BS_LOOP_TARGET_REPO" \
  -m gpt-5.2 --config model_reasoning_effort="xhigh" --sandbox read-only \
  "<R1_PROMPT>" > "$REVIEWS/$CYCLE/r1.md" 2>/dev/null
```
**R1_PROMPT** (fill the cycle bounds): "You are an INDEPENDENT reviewer. The bs workflow
already ran its own Grade and merged this delivery — your job is to find what its Grade
MISSED or let ESCAPE, not to re-confirm it. Read the merged delta
`git diff <start_commit>..<merge_commit>`, the acceptance in `<cycle_dir>/outcome.md`, and
the self-grade `<cycle_dir>/grade_round_*.md`. Review deeply for: correctness/logic bugs,
unmet or misread acceptance criteria, weak/example-only/missing negative tests, security &
trust-boundary gaps, spec drift. Output Markdown ending with a fenced `r1_verdict` YAML
block: `{overall: pass|concerns|fail, escaped_findings: [{id, severity: P0|P1|P2, where,
why, evidence}], confidence}`. Review only — modify nothing."
- Validate `r1.md` is non-empty and contains `r1_verdict`; else stage failure → pause-surface + `consecutive_failures += 1`.

## Step 3 — r2.md (codex, process/evolution review — depends on r1)
```bash
codex exec --skip-git-repo-check -C "$WORKSPACE_PARENT" \
  -m gpt-5.2 --config model_reasoning_effort="xhigh" --sandbox read-only \
  "<R2_PROMPT>" > "$REVIEWS/$CYCLE/r2.md" 2>/dev/null
```
**R2_PROMPT**: "Read `r1.md` at `<abs path>` and this cycle's PROCESS evidence in
`<cycle_dir>`: `step_events.jsonl`, `grade_round_*.md`, `evidence/grade_lint_*.json`,
`evidence/grade_verify_*.yaml`, any `*_incident.md` / conduct evidence. Also read the
bs-skill contract `<BS_LOOP_SKILL_REPO>/contract.md` and helpers in
`<BS_LOOP_SKILL_REPO>/runtime/`. For each r1 escaped finding answer: WHY did it escape —
which gate (Shape capsule / Conduct / Grade rubric / `grade_lint.py` / `grade_verify.py` /
critic) should have caught it and did not? Propose the MINIMAL, PATCH-level bs-skill change
that would have caught each escaped class (exact file + the rule/check to add or tighten).
Reject anything needing a major redesign. Output Markdown ending with a fenced `r2_plan`
YAML block: `{escape_analysis: [{finding_id, escaped_through, root_cause}],
proposed_changes: [{file, change, which_gate, expected_catch, patch_size: S|M}], net_risk,
no_change_ok: bool}`. If nothing is actionable, set `no_change_ok: true`."
- Validate `r2.md` non-empty and contains `r2_plan`.

## Step 3.5 — Commit + push reviews (Requirement 4: completed work is tracked)
The reviews are done → make them durable BEFORE any release/pause. (bs-skill tree is
otherwise clean here; Step-4 codex edits come next.)
```bash
git -C "$BS_LOOP_SKILL_REPO" add "harness/evolve-loop/reviews/opensymphony/$CYCLE"
git -C "$BS_LOOP_SKILL_REPO" commit -m "reviews($CYCLE): r1 delivery + r2 evolution"
git -C "$BS_LOOP_SKILL_REPO" push origin main
```

## Step 4 — Verify & implement into bs-skill (FULL-AUTO RELEASE, guarded)
1. **Record rollback anchor:**
   `loop-state set anchor.skill_sha $(git -C "$BS_LOOP_SKILL_REPO" rev-parse HEAD)` and
   `anchor.skill_version $(grep '^version:' "$BS_LOOP_SKILL_REPO/skill.yaml" | tr -dc '0-9.')`.
2. **Verify r2 reasonableness.** Read `r2_plan`. If `no_change_ok:true`, empty, or
   over-scoped (any `patch_size` other than S/M, or a redesign) → record
   `"no skill change this cycle"`; **skip to Step 6** (still a successful iteration).
3. **Implement via codex (workspace-write):**
```bash
codex exec --skip-git-repo-check -C "$BS_LOOP_SKILL_REPO" \
  -m gpt-5.2 --config model_reasoning_effort="xhigh" --sandbox workspace-write --full-auto \
  "<IMPLEMENT_PROMPT>" 2>/dev/null
```
   **IMPLEMENT_PROMPT**: "Apply `r2_plan.proposed_changes` from `<r2 path>` as a
   PATCH-level change to this bs-skill repo. Then prepare a release: (1) bump `skill.yaml`
   `version` AND `contract_version` to the next PATCH (e.g. 1.4.10→1.4.11); (2) update the
   `contract.md` title version and add a `## 11. Changelog` row describing the change;
   (3) if you changed any file in the contract 'Runtime manifest (locked)' table, RELOCK
   it — recompute `shasum -a 256` of each changed file and update its row; (4) bump the
   client version strings in `runtime/codex_driver.py`, `runtime/preflight.sh`,
   `bundle/bootstrap.yaml.template`, and `README.md` to the new version; (5) add or extend
   a `tests/test_*.py` unittest proving the new gate catches the escaped class; (6) run
   `python3 -m unittest discover -s tests -p 'test_*.py'` and iterate until ALL pass. Do
   NOT git commit, tag, or push. Print `NEW_VERSION=vX.Y.Z` and a one-line summary."
   - Parse `NEW_VERSION` + summary from codex output.

### MODE == dry-run → SUPERVISED CHECKPOINT (stop before release)
- `loop-state append-history` entry `stage:"dryrun_paused"`.
- Show the user: `git -C "$BS_LOOP_SKILL_REPO" diff --stat`, `NEW_VERSION`, the r1/r2 paths,
  and a digest of `git -C "$BS_LOOP_SKILL_REPO" diff`. State plainly that release/tag/push
  are **HELD** pending their review.
- Release lock. **END. Never reschedule in dry-run.**

### MODE == auto → release
```bash
bash "$HARNESS/bin/release.sh" --skill "$BS_LOOP_SKILL_REPO" --target "$BS_LOOP_TARGET_REPO" \
  --version "$NEW_VERSION" --summary "<summary>"
```
- exit **0** → `loop-state` history `stage:"released"`, `release_tag`; `set consecutive_failures 0`.
- exit **2** (pre-commit gate) → discard codex edits
  (`git -C "$BS_LOOP_SKILL_REPO" checkout -- . && git -C "$BS_LOOP_SKILL_REPO" clean -fd`);
  `consecutive_failures += 1`; PAUSE-AND-SURFACE; end.
- exit **3** (committed, not pushed) →
  `rollback.sh --skill … --target … --anchor-sha <anchor.skill_sha> --bad-tag $NEW_VERSION`;
  `consecutive_failures += 1`; pause-surface; end.
- exit **4** (partial push) → same `rollback.sh … --pushed`; `consecutive_failures += 1`;
  pause-surface; end.

## Step 5 — Post-release health (auto only)
The TRUE regression test is the NEXT `/bs` preflight. Defer hard judgment to Step 1 of the
next iteration: if the next `/bs` subagent reports preflight/`/bs doctor` failure → treat
as a bad release → `rollback.sh … --pushed` to the anchor → pause-surface.

## Step 6 — Close iteration
- `loop-state append-history '{"iteration":N,"cycle":"<CYCLE>","pr":"…","stage":"…",
  "r1":"…","r2":"…","release_tag":"…|null","ts":"…"}'`.
- **MODE == dry-run** → already ended at the Step-4 checkpoint.
- **MODE == auto** → `loop-state should-stop`; if a reason prints → report + end (no
  reschedule). Else `ScheduleWakeup(delaySeconds: 90, reason: "next bs-evolve iteration",
  prompt: "<this same /loop input verbatim>")`.
- **ALWAYS last:** `bash "$HARNESS/bin/loop-guard.sh" release "$BS_LOOP_STATE_DIR"`.

---

## Operator controls
- **Stop the loop:** `touch "$BS_LOOP_TARGET_REPO/.prompts/loop/STOP"` — honored at the next
  Step 0 (ScheduleWakeup has no external cancel, so this file IS the cancel). Resume: delete it.
- **Inspect:** `python3 "$HARNESS/bin/loop-state.py" get history`.
- **Go live after dry-run:** `python3 "$HARNESS/bin/loop-state.py" set mode auto`, optionally
  raise `set max_iterations N`, then relaunch `/loop` with this file.
