# Cyber TS services — owned by `cyber-lead` / `cyber-lab-builder`

When editing files in this directory, the `cyber-lab-builder` sub-agent rules apply.

## Hard rules

- `pythonClient.ts` is the **only** place that calls the Python ops in `application/python-services/cyber/`. Don't add raw `fetch('/api/cyber/...')` in lab views — go through this module.
- `ctfStore.ts` schema is versioned. Bumping = migration, not wipe (users have solves persisted locally).
- Long-running ops (hash brute, password analyze, network scan) MUST report progress to the lab UI — block freezes.
- **Defensive/educational only.** No active exploitation tooling.

See `.claude/agents/cyber-lead.md` and `.claude/agents/cyber-lab-builder.md` for the full lead spec.
