# Aurora CI templates

GitHub Actions workflows kept here as templates. To activate, copy the file to `.github/workflows/` (this requires a token with the `workflow` scope, which Claude Code's OAuth app does not have — the user has to do it manually with their git credentials).

## validate-agents.yml.template

Lints the agent system on every PR or push touching `.claude/agents/`, `.claude/agent-tracker/`, or the relevant hooks. Runs:

1. `python .claude/hooks/validate_agents.py` — frontmatter + tracker coherence + KNOWN_AGENTS sync
2. `python -m py_compile` on all 5 hook scripts

To enable:

```bash
mkdir -p .github/workflows
cp .claude/ci/validate-agents.yml.template .github/workflows/validate-agents.yml
git add .github/workflows/validate-agents.yml
git commit -m "Enable Aurora agent system CI"
git push
```
