# Aurora Agents — Index

Agent hierarchy for AuroraIA-v2. All agents pinned to `model: claude-opus-4-7`.

## Hierarchy (38 agents)

```
aurora-orchestrator                  ← master, dispatches only
│
├── conversation-lead                         (delegates voice → voice-lead)
│   └── conversation-pipeline-tuner
│
├── image-lead
│   ├── image-flux-stylist
│   └── image-reference-researcher
│
├── code-lead
│   ├── code-fidelity-auditor
│   ├── code-sandbox-runner
│   └── code-design-architect
│
├── video-lead                                (consumes voice-lead)
│   ├── video-motion-director
│   └── video-talking-head
│
├── drawing-lead                              (consumes voice-lead)
│   └── drawing-sketch-interpreter
│
├── 3d-lead
│   ├── 3d-pipeline-router
│   ├── 3d-motion-rigger
│   ├── 3d-mesh-postprocessor
│   └── 3d-quality-rescuer       (autonomy chain: score → bake → reshape → re-validate)
│
├── learning-lead                             (consumes voice-lead, simulator-lead)
│   ├── learning-quiz-verifier
│   └── learning-bac-curator
│
├── cowork-lead                               (Aurora-Connect, 7628 LOC)
│   ├── cowork-orchestrator-tuner
│   ├── cowork-connector-keeper
│   └── cowork-safety-auditor
│
├── voice-lead                                (cross-module: conversation, video, drawing, learning)
│   ├── voice-tts-stt-tuner
│   └── voice-lipsync
│
├── cyber-lead                                (9 labs, defensive/educational)
│   ├── cyber-lab-builder
│   └── cyber-pyops-keeper
│
├── simulator-lead                            (pure compute, consumed by learning)
│   ├── simulator-physics-engine
│   └── simulator-scene-io
│
└── crosscut
    ├── tunnel-validator                      ← E2E HTTP+UI gate before commit
    └── bridge-doctor                         ← respawn diagnosis
```

**Counts**: 1 master + 11 leads + 24 sub-agents + 2 crosscut = **38 agents**, all `model: claude-opus-4-7`. Verified by `python .claude/hooks/validate_agents.py` (or `/aurora-validate`).

## Auto-tracker (6 hooks)

`.claude/settings.json` (committed, portable to clones) registers 6 hooks that wrap the tracker (`.claude/agent-tracker/state.json`, schema `aurora.tracker.v1`). User-local permissions stay in `.claude/settings.local.json`.

| Event | Script | What it does |
|-------|--------|--------------|
| UserPromptSubmit | `prompt_routing_hint.py` | Detects module keywords in user prompt → injects `[Aurora hint] likely lead(s): …` via additionalContext |
| PreToolUse on `Task` | `track_agent_dispatch.py` | Append `{id, lead, brief, status:in_progress, started_at}` |
| PostToolUse on `Task` | `track_agent_dispatch.py` | Find the matching in-flight task, set `finished_at` + `status:done\|blocked` + `verdict`. Auto-rotates to history when tasks > 50. |
| Stop | `record_last_commit.py` | Record HEAD short-SHA in `last_commit` + `last_commit_at` |
| SessionStart | `session_start_status.py` | Print compact banner via `additionalContext` (leads count, last_commit, in-flight tasks) |
| PreCompact | `precompact_tracker_summary.py` | Inject tracker summary (in-flight + recent done/blocked) so the post-compact session keeps situational awareness |

All hooks are silent on success, fail-soft (warn to stderr, exit 0), atomic (`os.replace(tmp, dest)`). Self-test commands:

```bash
python .claude/hooks/validate_agents.py     # lint frontmatter + tracker coherence
python .claude/hooks/test_hooks.py          # 15 unit tests, stdlib-only, ~0.7s
```

Or via slash: `/aurora-validate` and `/aurora-test`.

## How dispatch works

1. User asks something (or `/loop` fires).
2. `aurora-orchestrator` parses intent → identifies modules touched.
3. Updates `session_goal` in tracker.
4. Launches the relevant `*-lead` sub-agents **in parallel** via `Agent` tool. The PreToolUse hook auto-records each launch.
5. Each lead reads its briefs, fans out to its own sub-agents in parallel when both/all are needed.
6. Sub-agents return → leads aggregate → orchestrator aggregates. PostToolUse hook closes each task.
7. `tunnel-validator` runs (mandatory before any commit).
8. On Stop, `record_last_commit.py` writes the new HEAD SHA to the tracker.
9. Next session: SessionStart prints the banner with what was last done.

## Hard rules baked into every lead

- llama4:scout = Meta → no `/no_think` tokens
- Memory streaming = `chunks: string[]` + `.join('')`, never `+= token`
- Sandbox/correctionLog truncation caps preserved (8 KB / 2 KB)
- VRAM model swaps = #1 crash cause → single model per pipeline by default
- Tunnel-first commit policy — `tunnel-validator` must say OK
- Bridge respawn requires evidence (per `feedback_bridge_respawn.md`)
- Voice path goes through `voice-lead`
- Simulator engine = pure compute, no DOM/Three.js
- Cyber `_safety.py` is the single Python gate

## Per-module CLAUDE.md fragments

The architecture also surfaces from inside the code via `CLAUDE.md` files in module sub-directories. When Claude reads files in those paths, the local `CLAUDE.md` provides the lead's hard rules without requiring agent dispatch:

- `application/src/services/cyber/CLAUDE.md` — `cyber-lab-builder` rules
- `application/src/services/simulator/CLAUDE.md` — `simulator-*` rules (no DOM/Three.js, determinism, fixed dt)
- `application/src/services/learning/CLAUDE.md` — `learning-lead` rules
- `application/python-services/cyber/CLAUDE.md` — `cyber-pyops-keeper` rules (`_safety.py` is the single gate)
- `extension_chrome/CLAUDE.md` — `cowork-connector-keeper` rules (MV3, handshake format)

These are durable: even when an editor session has no agents loaded, the rules surface naturally as the file is read.

## Adding a new agent

1. Create `.claude/agents/<name>.md` with frontmatter `name`, `description` (auto-trigger friendly), `model: claude-opus-4-7`, optional `color`.
2. Body: scope to one concern. List "files you own" + "hard rules" + "workflow".
3. Register under its lead in `.claude/agent-tracker/state.json` `leads.<lead>.sub_agents`.
4. Add the agent name to `KNOWN_AGENTS` in `.claude/hooks/track_agent_dispatch.py`.
5. Update this README.
6. Run `/aurora-validate` (or `python .claude/hooks/validate_agents.py`) to confirm coherence.
7. If you also touched a hook script, run `/aurora-test` (or `python .claude/hooks/test_hooks.py`).
