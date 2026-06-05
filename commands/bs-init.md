# /bs-init

Initialize the current git repository for the bootstrap workflow. This command writes files but does not commit.

## Flow

1. Resolve repo root. Stop if `.bootstrap.yaml` or `.bootstrap/backlog.yaml` already exists unless the user explicitly requested overwrite.
2. Copy bundled YAML templates from `~/.claude/skills/bs/bundle/`:
   - `.bootstrap.yaml`;
   - `.bootstrap/backlog.yaml`;
   - `.bootstrap/contract.sha256` containing only the local `contract.md` sha256.
3. Fill contract source fields from the installed skill release when available; otherwise leave explicit placeholders and stop with instructions.
4. Do not create markdown under `.bootstrap/`.
5. Inspect `.bootstrap/backlog.yaml` for task types. If any task has `type: code` and the binding lacks `verify.grade.code`, fail before task selection with the exact YAML block to add, derived from repo-detected defaults where possible:
   - Rust workspace: `cargo build --workspace`, `cargo fmt --all --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo nextest run --workspace`;
   - docs-only repo: keep `verify.grade.docs` mapped to `verify_command`;
   - unknown stack: print placeholders and stop; do not silently initialize a code backlog without per-round Grade commands.
6. Validate the generated binding and backlog.
7. Print next steps: edit real tasks, review red-line docs, commit the three files.
