<!-- runtime tombstone: legacy bs-evolve loop prompt migrated to /bs-evolve -->
# Legacy bs-evolve-loop prompt tombstone

This legacy harness prompt is intentionally no longer the algorithm body.

Use the registered command instead:

```text
/bs-evolve --config <target>/.bs-evolve/config.yaml
```

If an old scheduled wake reads this file, do not continue the legacy loop. End without
arming a new wake. This tombstone absorbs late pre-migration wakes while keeping the loop
algorithm single-sourced in `commands/bs-evolve.md`.
