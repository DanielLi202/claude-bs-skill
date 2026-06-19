<!-- runtime asset: bs-evolve orchestration command; invoked as /bs-evolve --config <path> [--once] -->
# /bs-evolve — one closure-ledger iteration

## Invocation contract

Required form:

```text
/bs-evolve --config <path-to-config.yaml> [--once]
```

The command is the single algorithm body for every adopter. Do not fork or render
per-project copies. The only project-specific inputs are read from `--config`.

### Config schema

`--config` is a YAML mapping owned by the target repo, typically
`<target>/.bs-evolve/config.yaml`:

```yaml
schema_version: 1
project_slug: short-stable-slug
target_repo: /absolute/path/to/target
skill_repo: /absolute/path/to/bs-skill   # optional; defaults to installed skill repo
state_dir: .                            # config lives in <target>/.bs-evolve/
reviews_root: ./reviews
corpus_dir: ./corpus
adopt_min_cycle: 18                     # explicit lower bound for corpus adoption
mode: auto                              # auto | dry-run
max_iterations: 5
wake_prompt: "/bs-evolve --config /absolute/path/to/config.yaml"
```

Every turn starts by resolving the installed skill root, then loading the config and
exporting the environment. Do not use `BS_LOOP_SKILL_REPO` to find the helper before
this export; that variable is an output of the helper.

```bash
# Resolve from the slash-command asset location: the directory containing `skill.yaml`.
# In a local checkout this is the repository root; in an installed skill this is the
# installed skill directory. If the runtime exposes the command file path, use its
# parent `commands/..`; otherwise locate the skill root by the loaded `/bs-evolve`
# command asset, not by target config.
BOOTSTRAP_SKILL_REPO="<directory containing skill.yaml for this command>"
test -f "$BOOTSTRAP_SKILL_REPO/skill.yaml"
eval "$(python3 "$BOOTSTRAP_SKILL_REPO/harness/evolve-loop/bin/bs-evolve-config.py" --config "$CONFIG" --emit-env)"
HARNESS="$BS_LOOP_HARNESS"
REVIEWS="$BS_LOOP_REVIEWS_ROOT"
CORPUS="$BS_LOOP_CORPUS_DIR"
WAKE_PROMPT="$BS_LOOP_WAKE_PROMPT"
```

Required exported names: `BS_LOOP_SKILL_REPO`, `BS_LOOP_TARGET_REPO`,
`BS_LOOP_PROJECT_SLUG`, `BS_LOOP_STATE_DIR`, `BS_LOOP_REVIEWS_ROOT`,
`BS_LOOP_CORPUS_DIR`, `BS_LOOP_HARNESS`, `BS_LOOP_WAKE_PROMPT`, `BS_LOOP_MODE`,
`BS_LOOP_MAX_ITERATIONS`, and `BS_LOOP_ADOPT_MIN_CYCLE`.

## `--once` contract

`--once` is transient single-step operator mode:

- advance exactly one pending stage or one new-stage decision;
- do not emit or arm `ScheduleWakeup`;
- do not write `dry-run` or otherwise mutate persistent `state.mode`;
- after the one stage finishes, release any held project lock with its owner token and end.

Self-check boundary:

Unit tests cover the state-only part of this contract by running the same persistent state operations used by a one-shot turn and asserting `mode: auto` remains `auto`. The wake-arm half is prompt-level/live-only: only the Stage A exit smoke (`/loop /bs-evolve --config <target>`) can prove that no Stage-7 wake is armed after `--once`; do not replace that live check with a simulated helper.

## Hard invariants

1. Algorithm single-source: this file is the only loop algorithm body.
2. Target-owned state: runtime state, closure ledgers, reviews, corpus, STOP/PAUSE,
   and RUNNING.lock live under the target-side config paths.
3. Single-project serial execution: one target may have at most one in-flight stage.
4. Commit target split: r1/r2/review/closure artifacts are committed to the target
   repo; skill releases commit only skill changes.
5. ScheduleWakeup is terminal: every non-terminating turn ends with exactly one
   `ScheduleWakeup`, and it is the final action.
6. `--once` never schedules a wake and never changes persistent mode.

## Step 0 — load config, stop checks, guard, closure scan

1. Parse args. `CONFIG` is required. `ONCE=1` only when `--once` is present.
2. Run the config export block above. This is repeated every turn; do not rely on
   context memory for paths or mode.
3. Initialize state if absent with config mode:
   `loop-state.py init --target "$BS_LOOP_TARGET_REPO" --skill "$BS_LOOP_SKILL_REPO" --mode "$BS_LOOP_MODE" --max "$BS_LOOP_MAX_ITERATIONS"`.
4. `loop-guard.sh check-stop "$BS_LOOP_STATE_DIR"`; on STOP, report and end.
5. `loop-state.py --state-dir "$BS_LOOP_STATE_DIR" should-stop`; on stop reason,
   report and end.
6. Acquire the per-project lock: `loop-guard.sh acquire "$BS_LOOP_STATE_DIR"`.
   The command creates `RUNNING.lock` atomically with a persisted owner token and
   prints JSON containing `token`; store that token in turn-local state and pass it
   to every `heartbeat` and `release`. Exit 11 means another stage is live; run
   the same lock-held retry supervision as the old loop, but against target-side
   state:
   - no inflight files + stale lock ⇒ the lock helper may atomically take over;
   - stale lock + any unresolved inflight record/live pgid ⇒ fail closed as
     locked/waiting; do **not** start a second stage;
   - live pgid with suspect markers or age >90 minutes ⇒ inspect log tail and, for
     write stages, `git diff --stat`; converging work re-arms a check-in wake,
     looping work is reaped and retried once with evidence;
   - otherwise re-arm `ScheduleWakeup(delaySeconds: 1800, reason: "lock-held retry probe", prompt: WAKE_PROMPT)`
     and end, unless `ONCE=1`, in which case report locked/waiting and end without
     scheduling.
   During long stages, periodically run
   `loop-guard.sh heartbeat "$BS_LOOP_STATE_DIR" "$RUNNING_LOCK_TOKEN"`; a token
   mismatch is blocking because another owner took over or the lock state is corrupt.
7. Closure scan uses target-owned reviews:
   `closure.py --reviews-root "$REVIEWS" newest-open`.
8. If no open closure exists, adopt the latest eligible target corpus cycle with the
   explicit config lower bound:
   `adopt-cycle.py --corpus-root "$CORPUS" --reviews-root "$REVIEWS" --min-cycle "$BS_LOOP_ADOPT_MIN_CYCLE"`.
   Never scan below that bound; otherwise start a new `/bs` cycle in the target repo.

## Target-side state and git hygiene

The config paths must resolve inside `BS_LOOP_TARGET_REPO`, normally under
`.bs-evolve/`. Runtime files are local-only; reviews/closure ledgers are durable and
must be committed by the target repo. Install/check the target ignore policy with:

```bash
python3 "$HARNESS/bin/bs-evolve-gitignore.py" --target "$BS_LOOP_TARGET_REPO"
python3 "$HARNESS/bin/bs-evolve-gitignore.py" --target "$BS_LOOP_TARGET_REPO" --check
```

Ignored local state: `.bs-evolve/config.yaml`, `.bs-evolve/state.json`,
`.bs-evolve/RUNNING.lock*`, `.bs-evolve/STOP`, `.bs-evolve/PAUSE`,
`.bs-evolve/inflight/**`, `.bs-evolve/corpus/**`, and fleet local state.
Do not ignore `.bs-evolve/reviews/**`; closure ledgers must survive a clean checkout.

## Background stage supervision skeleton

The migrated command preserves the old long-stage supervision model. Heavy work never
runs as foreground polling inside the orchestrator turn. For every `/bs`, codex review,
implementation, backtest, and remediation stage:

```bash
bash "$HARNESS/bin/run-codex-staged.sh" --stage "<iter>-<stage>" --stall-sec 1200 \
  --prompt "<prompt-file>" --log "<log-file>" --cwd "<repo-or-worktree>" [--expect-writes] \
  [-- --sandbox workspace-write --expect-writes|--sandbox workspace-write --full-auto]
```

After launching background work, immediately do the cheap completion/staleness check
against `$BS_LOOP_STATE_DIR/inflight/<stage>.json` and the log DONE/rc line. If the
stage already finished, consume it in the current turn and continue. If still running
and `ONCE` is not set, the final action is a supervision wake:

```text
ScheduleWakeup(delaySeconds: 2700, reason: "stage check-in", prompt: WAKE_PROMPT)
```

Use 900 seconds for short review/backtest/canary stages and 2700 seconds for long
`/bs`, conduct, implementation, and remediation stages. `--once` never arms these
check-in wakes; it reports the launched/completed single stage and ends.

## Stage 1 — target `/bs` cycle

Run `/bs` in `BS_LOOP_TARGET_REPO` as the background work item under the supervision skeleton above. On success, initialize
`$REVIEWS/<cycle>/closure.yaml`. Commit the closure ledger to the target repo:

```bash
git -C "$BS_LOOP_TARGET_REPO" add "$REVIEWS/<cycle>/closure.yaml"
git -C "$BS_LOOP_TARGET_REPO" commit -m "bs-evolve: adopt <cycle> closure"
git -C "$BS_LOOP_TARGET_REPO" push origin HEAD:main
```

If `ONCE=1`, stop after this stage without scheduling a wake.

## Stage 2 — r1 independent delivery review

Run a semantically read-only review of the delivered target delta via `run-codex-staged.sh` under the supervision skeleton above, but invoke Codex with workspace-write because the stage must write review artifacts. Write `$REVIEWS/<cycle>/r1.md`,
validate the fenced `r1_verdict`, update closure, and commit/push the target repo.

```bash
git -C "$BS_LOOP_TARGET_REPO" add "$REVIEWS/<cycle>/r1.md" "$REVIEWS/<cycle>/closure.yaml"
git -C "$BS_LOOP_TARGET_REPO" commit -m "bs-evolve: r1 review <cycle>"
git -C "$BS_LOOP_TARGET_REPO" push origin HEAD:main
```

If `ONCE=1`, stop after this stage without scheduling a wake.

## Stage 3 — r2 process review to deterministic plan

Run a semantically read-only process review via `run-codex-staged.sh` under the supervision skeleton above, but invoke Codex with workspace-write because the stage must write review artifacts. Require each `proposed_changes[]` item to carry
`determinism: deterministic | needs_human`. Write `$REVIEWS/<cycle>/r2.md`, copy
`needs_human` entries into closure, and commit/push the target repo.

If `ONCE=1`, stop after this stage without scheduling a wake.

## Stage 3 read isolation

r2 and any other review that reads skill rules must use the cycle binding source
commit, not current `origin/main` or a content hash. Use `skill-read-ref.py --ref
<binding-source-commit> --path <file>` or equivalent `git show <ref>:<path>` so a
concurrent Stage 4 release cannot change the rule set under a long-running review.

## Stage 4 — skill release for deterministic r2 items

Implement deterministic r2 items in a private skill worktree via `run-codex-staged.sh` under the supervision skeleton above. Stage B wraps every
skill-repo write in `$BS_LOOP_SKILL_REPO/.bs-evolve/SKILL.lock` using
`evolve-lock.py acquire --lock-file ...`; persist the printed owner token, heartbeat
with it, and release with compare-token semantics. Release commits and tags are
skill-repo writes only.

Immediately after acquiring `SKILL.lock` and before backtest, run
`release-plan.py --skill "$BS_LOOP_SKILL_REPO" --out "$REVIEWS/<cycle>/release_plan.yaml"`
to freeze `baseline_ref`, `baseline_sha`, and `candidate_version` from the fresh
maximum release tag. Backtest must use that `baseline_ref`; `release.sh` receives
`--plan-file` and rejects stale-anchor evidence. Candidate implementation happens
in a private skill worktree, then `release.sh` pushes candidate `HEAD` explicitly
to `origin/main`, pushes the tag, and fast-forwards the local canonical checkout
to the tag. It never deletes a pushed tag and never reaches into target repos.

Before implementing, run `skill-release-dedup.py plan --write` with the r2 items
and current-upstream covered ids. Only items with status `implement` may be
changed. Items marked `covered_upstream` are recorded in the closure, and items
already present in `skill_release_items_done` are skipped on re-entry after a
killed Stage 4 turn. If there is no release to make because all items are covered,
all deterministic items were already done, all remaining items need human review,
or there are no deterministic items, the helper writes a non-empty
`skill_release: {status: no_release, ...}` sentinel so `closure.py next` advances
to remediation instead of wedging on Stage 4.

Backtest and release evidence are stored under the target-owned `$REVIEWS/<cycle>/` and
committed to the target repo after release. Target pin-sync is deferred to each
target Step 0 rather than called from the release path. G2 must run the hermetic
`grade-fixture-walker.py` over committed anonymous must-not-fire fixtures; an empty
or unreadable fixture root is a hard failure. G4 uses `release-gates.py g4` to
parse structured misfire adjudications: every misfire needs a matching true-positive
adjudication plus fresh-verify pass, any false-positive blocks release, and
unmatched adjudications block release. `--no-backtest` is accepted only when the
anchor diff avoids grade_lint/rule/fixture/backtest surfaces. Any release touching
`grade_lint` rule surfaces must add a committed anonymous near-miss fixture.

If `ONCE=1`, stop after this stage without scheduling a wake.

## Stage 5 — target remediation under new gates

Use a target remediation worktree whose path includes both project slug and repo hash:

```bash
repo_hash="$(printf '%s' "$BS_LOOP_TARGET_REPO" | shasum -a 256 | awk '{print substr($1,1,12)}')"
remediate_dir="/private/tmp/bs-evolve-remediate/${BS_LOOP_PROJECT_SLUG}-<cycle>-${repo_hash}"
git -C "$BS_LOOP_TARGET_REPO" worktree add "$remediate_dir" -b "remediate/${BS_LOOP_PROJECT_SLUG}/<cycle>"
```

Fix every r1 finding via `run-codex-staged.sh` under the supervision skeleton above, run target gates, write remediation review artifacts under
`$REVIEWS/<cycle>/`, merge to target main, update closure, and commit/push the target
repo.

If `ONCE=1`, stop after this stage without scheduling a wake.

## Stage 6 — close ledger

Set `closed: true`, commit/push the target closure ledger, and verify clean target and
skill trees. Surface every `escalated_to_human` entry verbatim.

If `ONCE=1`, release the project lock and end without scheduling a wake.

## Stage 7 — stop or reschedule

Order is mandatory:

1. Check `loop-state.py should-stop`; if set, report and end without re-arm.
2. If mode is `dry-run`, release the project lock and end without re-arm.
3. If `PAUSE` exists, release the project lock and end without re-arm.
4. Release the project lock before terminal wake:

```bash
bash "$HARNESS/bin/loop-guard.sh" release "$BS_LOOP_STATE_DIR" "$RUNNING_LOCK_TOKEN"
```

5. As the final action, and only when `ONCE` is not set, arm the next iteration:

```text
ScheduleWakeup(delaySeconds: 90, reason: "next bs-evolve iteration", prompt: WAKE_PROMPT)
```

No command or cleanup may appear after that terminal wake.
