# bs-evolve loop harness

This directory contains reusable helper scripts for the `/bs-evolve` command.

The loop algorithm body is `commands/bs-evolve.md`. Target-specific config, runtime
state, corpus pointers, reviews, and closure ledgers live in the target repository under
`.bs-evolve/`.

`loop-prompt.md` is a legacy tombstone only; late wakes that read it should stop instead
of continuing the pre-migration project-specific loop.
