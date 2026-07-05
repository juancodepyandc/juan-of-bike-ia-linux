# Aurora git hooks

Portable git hooks for the AuroraIA-v2 multi-agent system. Project-tracked (unlike `.git/hooks/`) so every clone gets the same protection once enabled.

## Enable (one-time per clone)

```bash
git config core.hooksPath .claude/git-hooks
```

## Disable

```bash
git config --unset core.hooksPath
```

Or skip a single commit: `git commit --no-verify` (not recommended — the gate is light, ~2 seconds).

## Hooks

### `pre-commit`

Triggers when staged files include any of:
- `.claude/agents/`
- `.claude/agent-tracker/`
- `.claude/hooks/`
- `.claude/git-hooks/`
- `application/scripts/route_test.py`
- `application/scripts/test_route_test.py`
- `application/src/services/threeDIntent.ts`

Runs:
1. `python .claude/hooks/validate_agents.py` — frontmatter + tracker + KNOWN_AGENTS coherence
2. `python .claude/hooks/test_hooks.py` — 15 unit tests on the 6 hooks
3. `python application/scripts/test_route_test.py` — 13 routing tests (only if route_test files or threeDIntent touched)

Total runtime: ~1.5 seconds when triggered. Zero overhead on commits that don't touch the agent system.

## When the hook fires

```
[aurora pre-commit] agent system files staged — running checks:
  validate_agents ... ok
  test_hooks ... ok
  test_route_test ... ok
[aurora pre-commit] all checks green ✓
```

On failure, the commit is blocked with the captured stderr/stdout of the failing check. Fix and re-stage, or use `--no-verify` to bypass for an emergency.
