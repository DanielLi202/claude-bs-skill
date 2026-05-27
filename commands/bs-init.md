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
5. Validate the generated binding and backlog.
6. Print next steps: edit real tasks, review red-line docs, commit the three files.
