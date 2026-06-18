<!-- runtime asset: bs-evolve target onboarding command -->
# /bs-evolve-init

Initialize a target repository for `/bs-evolve`.

Required form:

```text
/bs-evolve-init <target> [--mode auto|dry-run] [--max-iterations N] [--slug name]
```

Execute the bundled helper from the installed skill root:

```bash
python3 "$SKILL_REPO/harness/evolve-loop/bin/bs-evolve-init.py" <target> [--mode auto|dry-run] [--max-iterations N] [--slug name]
```

## Required behavior

1. Resolve `<target>` to a git repository.
2. Create `<target>/.bs-evolve/config.yaml` with target-owned paths:
   `state_dir: .`, `reviews_root: ./reviews`, `corpus_dir: ./corpus`, and a
   `wake_prompt` pointing at `/bs-evolve --config <target>/.bs-evolve/config.yaml`.
3. Initialize target state with config `mode` and `max_iterations`.
4. Install target `.gitignore` rules so `.bs-evolve/config.yaml`, `.bs-evolve/state.json`,
   locks, STOP/PAUSE, inflight, corpus, and fleet local state are ignored, while
   `.bs-evolve/reviews/**` remains trackable.
5. Discover at least one existing code cycle from target corpus roots; if no corpus cycle
   can be globbed, fail closed and do not report success.
6. Seed a committed-capable anonymous negative fixture under
   `tests/grade_lint_fixtures/anon-*/` with `metadata.yaml` and `grade.md`; if the helper
   cannot produce a minimal anonymized fixture without product names, absolute paths, or
   decision/task identifiers, fail closed.
7. Register local fleet state under skill `.bs-evolve/fleet.yaml`; this is machine-local
   and must be ignored by the skill repo.
8. Leave no unignored local state in the skill repo; only anonymous fixture files are
   intended to appear as skill-repo additions.

After init, the operator should commit the target `.gitignore` and later target review
ledgers in the target repo. Runtime config/state/corpus remain ignored local state by
contract.
