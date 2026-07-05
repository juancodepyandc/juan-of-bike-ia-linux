---
description: Dispatch a goal across AuroraIA-v2 modules via the multi-agent orchestrator
argument-hint: <goal description>
allowed-tools: Agent, Read, Write, Bash, Grep
---

Invoke `aurora-orchestrator` with the user's goal. The orchestrator will:
1. Parse intent → identify modules touched
2. Write the dispatch plan to `.claude/agent-tracker/state.json`
3. Launch the relevant `*-lead` agents in parallel
4. Aggregate their reports
5. Run `tunnel-validator` (mandatory before any commit)
6. Update the tracker with verdicts

Use the Agent tool with `subagent_type: "aurora-orchestrator"` and pass the goal verbatim:

```
$ARGUMENTS
```

Return a single concise summary covering: modules touched, lead verdicts, tunnel status, tracker state.
