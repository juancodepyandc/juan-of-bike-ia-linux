# Cyber Python ops — owned by `cyber-pyops-keeper`

When editing files in this directory, `cyber-pyops-keeper`'s rules apply. Be paranoid.

## Hard rules

- `_safety.py` is the **single gate**. Every public op imports it and calls `validate(...)` BEFORE any read/write/network. No exceptions.
- **Path allow-list**: workspace `application/` only. Adding a new path = written justification in the diff.
- **Time caps**: ops MUST exit cleanly when their timeout expires — no infinite loops.
- **Size caps**: file reads/writes have a max-bytes cap in `_safety.py`. Bumping requires proving the cap is still safe.
- **No active exploitation.** Defensive/educational only — network ops to user's own targets, password ops to user's own hashes.
- **No silent fallback** if `_safety.validate` fails — raise a clear exception that the lab UI surfaces.

See `.claude/agents/cyber-lead.md` and `.claude/agents/cyber-pyops-keeper.md` for the full lead spec.
