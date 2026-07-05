---
description: Lint the Aurora agent system — frontmatter, model pin, state.json coherence, KNOWN_AGENTS sync
allowed-tools: Bash
---

Run the agent system linter and report:

```bash
python .claude/hooks/validate_agents.py
```

The script verifies:
1. Every `.claude/agents/<name>.md` has valid YAML frontmatter with `name`, `description`, `model`
2. Frontmatter `name` matches filename
3. Every agent has `model: claude-opus-4-7`
4. `state.json` agents and `.md` files are 1:1
5. `KNOWN_AGENTS` in `track_agent_dispatch.py` matches the file set

Returns OK or a numbered list of issues.
