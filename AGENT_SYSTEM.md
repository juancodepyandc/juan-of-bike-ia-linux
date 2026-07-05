# AuroraIA-v2 multi-agent system

A single-page architecture map. For full details see `.claude/agents/README.md` + `.claude/agents/EXAMPLES.md`.

## What this is

Claude Code project-local multi-agent layer for AuroraIA-v2. **37 agents** all pinned `model: claude-opus-4-7`, a 6-hook automatic tracker, and a bridge endpoint surface so the architecture is observable from inside the running app.

Built across 13 /loop tours (v78a → v78p, May 2026) on a single-prompt continuous improvement run.

## Hierarchy

```
aurora-orchestrator                  master, dispatches only
├── conversation-lead                 (delegates voice path -> voice-lead)
│   └── conversation-pipeline-tuner
├── image-lead
│   ├── image-flux-stylist
│   └── image-reference-researcher
├── code-lead
│   ├── code-fidelity-auditor
│   ├── code-sandbox-runner
│   └── code-design-architect
├── video-lead                        (consumes voice-lead)
│   ├── video-motion-director
│   └── video-talking-head
├── drawing-lead                      (consumes voice-lead)
│   └── drawing-sketch-interpreter
├── 3d-lead
│   ├── 3d-pipeline-router
│   ├── 3d-motion-rigger
│   └── 3d-mesh-postprocessor
├── learning-lead                     (consumes voice-lead, simulator-lead)
│   ├── learning-quiz-verifier
│   └── learning-bac-curator
├── cowork-lead                       (Aurora-Connect, 7628 LOC)
│   ├── cowork-orchestrator-tuner
│   ├── cowork-connector-keeper
│   └── cowork-safety-auditor
├── voice-lead                        (cross-module: 4 leads consume it)
│   ├── voice-tts-stt-tuner
│   └── voice-lipsync
├── cyber-lead                        (9 labs, defensive only)
│   ├── cyber-lab-builder
│   └── cyber-pyops-keeper
├── simulator-lead                    (pure compute, consumed by learning)
│   ├── simulator-physics-engine
│   └── simulator-scene-io
└── crosscut
    ├── tunnel-validator              E2E HTTP+UI gate before commit
    └── bridge-doctor                 respawn diagnosis
```

1 master + 11 leads + 23 sub-agents + 2 crosscut = **37 agents**.

## Hooks (`.claude/settings.json`)

| Event | Script | Purpose |
|---|---|---|
| UserPromptSubmit | `prompt_routing_hint.py` | Detect module keywords → suggest lead via additionalContext |
| PreToolUse on `Task` | `track_agent_dispatch.py` | Append `{id, lead, brief, status: in_progress}` |
| PostToolUse on `Task` | `track_agent_dispatch.py` | Transition → done/blocked + verdict + finished_at. Auto-rotates history at 50 tasks. |
| Stop | `record_last_commit.py` | HEAD short-SHA → tracker |
| SessionStart | `session_start_status.py` | Compact banner via additionalContext |
| PreCompact | `precompact_tracker_summary.py` | Inject in-flight + recent task summary |

All hooks: silent on success, fail-soft (warn stderr, exit 0), atomic `os.replace(tmp, dest)`.

## Slash commands

| Command | What it does |
|---|---|
| `/aurora-dispatch <goal>` | Invoke aurora-orchestrator with the user's goal |
| `/aurora-status` | Print compact tracker state |
| `/aurora-validate` | Lint frontmatter + tracker + KNOWN_AGENTS |
| `/aurora-test` | Run 15 hook unit tests (~0.7 s) |
| `/aurora-route-test <prompt>` | Local 3D routing decision (no full pipeline run) |
| `/aurora-route-test-tunnel <prompt>` | Same via bridge endpoint (HTTP) |
| `/aurora-dashboard` | Render `.claude/agent-tracker/dashboard.html` |
| `/aurora-precommit-install` | Enable the portable git pre-commit hook |
| `/aurora-agents-list` | Query `/api/agents/list` for the registry |
| `/aurora-self-test` | Run all 7 gates in one shot (~3-4 s, PASS/FAIL) |

## Bridge endpoints

| Endpoint | Method | Returns |
|---|---|---|
| `/api/agents/list` | GET | `{ok, schema_version, leads, crosscut, descriptions, agent_count}` |
| `/api/agents/<name>` | GET | `{ok, name, description, model, color, body}` |
| `/api/3d/route-test` | POST `{"prompt": "..."}` | `{ok, routing: {flags, dreamgaussianPreferred, probable_pipeline, ...}}` |
| `/api/3d/motion-self-test` | GET | 13/13 motion baker self-test |
| `/api/3d/motion-parser-self-test` | GET | 17/17 TS↔Python parity |
| `/api/3d/pipeline-status` | GET | 4-axes Meshy quality verdict |

## Verification

The architecture is engineered, not just configured:

- **28 unit tests** — 15 hooks (`test_hooks.py`) + 13 routing (`test_route_test.py`)
- **`/aurora-self-test`** runs 7 gates: validate + tests + bridge_doctor + 2 endpoints + dashboard
- **Pre-commit hook** (`.claude/git-hooks/pre-commit`) gates commits touching the agent system
- **Lint** (`validate_agents.py`) — frontmatter + tracker + KNOWN_AGENTS coherence
- **CI template** — `.claude/ci/validate-agents.yml.template` (copy to `.github/workflows/` to activate)

Self-test live (current bridge PID 23644):
```
[aurora-self-test] running 7 gates...
  [ok] validate_agents        37 agents, 11 leads, model=claude-opus-4-7 coherent
  [ok] test_hooks             15 tests
  [ok] test_route_test        13 tests
  [ok] bridge_doctor          health_ok: True
  [ok] agents_list_endpoint   agent_count=37, leads=11
  [ok] route_test_endpoint    dgPreferred=True (Cat 1 fix verified)
  [ok] dashboard_render       11552 bytes
[aurora-self-test] PASS — all 7 gates green.
```

## How dispatch works

1. User asks something (or `/loop` fires).
2. UserPromptSubmit hook detects module keywords → suggests lead via additionalContext.
3. Aurora-orchestrator parses intent → identifies modules touched.
4. Updates `session_goal` in tracker.
5. Launches relevant `*-lead` sub-agents in parallel via `Agent` tool.
6. Each lead reads briefs, fans out to its sub-agents in parallel when needed.
7. Sub-agents return → leads aggregate → orchestrator aggregates.
8. PreToolUse + PostToolUse hooks auto-record every Agent dispatch in `state.json`.
9. `tunnel-validator` runs (mandatory before any commit).
10. On Stop hook, HEAD short-SHA written to `last_commit`.
11. SessionStart on next session: banner re-orients you with `last_commit` + in-flight tasks.

## Adding a new agent

1. Create `.claude/agents/<name>.md` with frontmatter `name`, `description`, `model: claude-opus-4-7`, optional `color`.
2. Body: scope to one concern. List "files you own" + "hard rules" + "workflow".
3. Register under its lead in `.claude/agent-tracker/state.json` `leads.<lead>.sub_agents`.
4. Add the agent name to `KNOWN_AGENTS` in `.claude/hooks/track_agent_dispatch.py`.
5. Update `.claude/agents/README.md` and `EXAMPLES.md`.
6. Run `/aurora-self-test` (or just `/aurora-validate`) to confirm coherence.

## Recovery

- Bridge unresponsive → `python bridge_doctor.py --check-only` to diagnose, then `python bridge_doctor.py` to respawn.
- Tunnel 502 → `python bridge_doctor.py --pull` (gated on clean tree, refuses if non-session paths are dirty).
- `update-aurora.bat` is a CRLF wrapper for `bridge_doctor.py --pull`.

## Persistence

- `.claude/agent-tracker/state.json` — current dispatch state (rotated at 50 tasks → `history/tasks-<UTC>.json`)
- `.claude/agent-tracker/dashboard.html` — generated HTML view (gitignored)
- User auto-memory `~/.claude/projects/.../memory/project_aurora_agents_v3.md` — load across sessions

## Files-of-interest

```
.claude/
├── agents/                      37 agent .md + README + EXAMPLES
├── agent-tracker/
│   ├── state.json               schema aurora.tracker.v1
│   ├── history/                 rotated archives
│   └── README.md
├── hooks/
│   ├── track_agent_dispatch.py  Pre+Post hook
│   ├── record_last_commit.py    Stop hook
│   ├── session_start_status.py  SessionStart hook
│   ├── precompact_tracker_summary.py  PreCompact hook
│   ├── prompt_routing_hint.py   UserPromptSubmit hook
│   ├── validate_agents.py       lint
│   ├── test_hooks.py            15 unit tests
│   ├── aurora_dashboard.py      HTML render
│   └── aurora_selftest.py       7-gate master test
├── git-hooks/
│   ├── pre-commit               portable hook
│   └── README.md
├── commands/                    10 slash commands
├── ci/                          GitHub Actions template
├── settings.json                hooks (committed)
└── settings.local.json          permissions only

application/
├── bridge_server.py             /api/agents/list, /api/agents/<name>, /api/3d/route-test
├── scripts/
│   ├── route_test.py            Python regex mirror of routePipeline()
│   ├── test_route_test.py       13 unit tests
│   └── route_test.mjs           Node placeholder (ESM .ts interop pending)
└── src/services/
    ├── threeDIntent.ts          routePipeline() with v78j luxury-material detection
    ├── cyber/CLAUDE.md          per-module rules
    ├── simulator/CLAUDE.md
    └── learning/CLAUDE.md

bridge_doctor.py                 cross-platform recovery (replaces broken .bat)
update-aurora.bat                CRLF thin wrapper for bridge_doctor.py --pull
.gitattributes                   pin .bat to CRLF
AGENT_SYSTEM.md                  this file
```
