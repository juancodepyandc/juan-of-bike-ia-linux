# AuroraIA-v2 — handoff snapshot

_Generated 2026-04-30T15:54:25Z by `python .claude/hooks/aurora_handoff.py` (`/aurora-handoff`)._

**Read this first** when picking up the project. Regenerate after every significant work session.

## HEAD

- branch: `main`
- HEAD:   `9be8a4f` — v80x: tour 5/6 — full 5-cat validation, all categories ≥ 90 ★
- date:   2026-04-30T17:43:08+02:00
- pushed to origin/main: yes

## Live ops snapshot

- tracker: `0` in-flight · `0` stale (>30 min) · OK
- dispatches: `67` total · global success `100.0%`
- rescue trend: `10/10` promoted (`100%`) · mean delta `+25.4` · axes lifted: `color_richness(9), silhouette_aspect(2)`

### Top runs by final score

- `cat3_meca_mesh` (generic): 79.5 → **99.5** (Δ +20.0, 6 events)
- `cat4_objet_mv_mesh` (generic): 62.3 → **99.4** (Δ +37.1, 8 events)
- `cat3_pipeline_motion_mesh` (generic): 79.4 → **99.4** (Δ +20.0, 4 events)
- `cat4_objet_mv_mesh_baked` (generic): 72.8 → **99.4** (Δ +26.6, 5 events)
- `cat5_jellopus_mesh` (creature): 78.8 → **98.8** (Δ +20.0, 8 events)
## Self-test snapshot

verdict: **PASS** (return code 0)

```
[aurora-self-test] running 33 gates...
  [ok ] validate_agents        OK � 38 agents, 11 leads, 32 commands, all model=claude-opus-4-7, state.json + KNOWN_AGENTS coherent.
  [ok ] test_hooks             OK
  [ok ] test_route_test        OK
  [ok ] bridge_doctor          [bridge-doctor] diagnose: {'bridge_pids': [4716], 'port_listeners': [4716], 'port_free': False, 'health_ok': True}
  [ok ] agents_list_endpoint   agent_count=38, leads=11
  [ok ] route_test_endpoint    dgPreferred=True (Cat 1 fix verified)
  [ok ] mesh_score_endpoint    overall=70.2, retry=True, failed_axes=['color_richness']
  [ok ] auto_validate_endpoint kind=pc_tower, next=dreamgaussian (Cat 1 fix loop closed)
  [ok ] color_diagnostic_endpoint stage_lost=hunyuan3d, loss=0.9991
  [ok ] bake_colors_endpoint   baked 46181 unique colors (Cat 1 rescue)
  [ok ] auto_rescue_endpoint   score_delta=+20.0, final=90.2, audit_stages=3
  [ok ] mesh_compare_endpoint  winner=right, overall_delta=20.0
  [ok ] viewer_html_endpoint   viewer html 4838 bytes
  [ok ] run_index_endpoint     runs=19, standalones=52
  [ok ] score_history_endpoint top runs returned: 5
  [ok ] tracker_health_endpoint in_flight=0, stale=0
  [ok ] tracker_health_unit    OK
  [ok ] watchdog_render        in_flight=0, recent=6, top=5
  [ok ] watchdog_endpoint      in_flight=0, recent=4, top=3
  [ok ] coverage_endpoint      declared=38, dispatched=2, coverage=5.3%
  [ok ] coverage_unit          OK
  [ok ] dispatches_endpoint    matches=3
  [ok ] dispatches_unit        OK
  [ok ] attribution_unit       OK
  [ok ] mesh_logic_unit        OK
  [ok ] ts_tests               tests 32
  [ok ] motion_baker_13_cases  SELF_TEST_OK: 13 test cases passed
  [ok ] motion_parser_17_cases PARSER_SELF_TEST_OK: 17 cases passed
  [ok ] motion_parity_fixtures PARITY_OK: 42 fixtures pass
  [ok ] metrics_derivation     total_dispatches=68, success=100%
  [ok ] changelog_in_sync      CHANGELOG.md matches git log
  [ok ] dashboard_render       30406 bytes (score+coverage+axis-lifts)
  [ok ] handoff_render         6,489 chars, 5 sections
[aurora-self-test] PASS — all 33 gates green.
```
## Agent tracker

- schema: `aurora.tracker.v1`
- last_commit: `9be8a4f`
- session_goal: Tour 3 — close the loop: cyber-lead + simulator-lead + Stop/SessionStart hooks + memory persistence
- tasks: 0 in-flight, 68 done, 0 blocked

### Recent done

- `t845e4296` **3d-quality-rescuer** — score 79.5->99.5 (delta +20.0); failed=[]
- `t6ea3c8ac` **3d-quality-rescuer** — score 79.4->99.4 (delta +20.0); failed=[]
- `t4338f92a` **3d-quality-rescuer** — score 78.8->98.8 (delta +20.0); failed=[]
- `t0ed6046c` **3d-quality-rescuer** — score 70.2->90.2 (delta +20.0); failed=[]
- `tdc127c47` **3d-quality-rescuer** — score 70.2->90.2 (delta +20.0); failed=[]
## 3D runs

- 19 grouped runs · 52 standalone files

- **cat5_jellopus** (2026-04-30T11:10:35) — 2 files, roles: mesh, reference
- **cat5_jellopus_right** (2026-04-30T10:43:50) — 1 files, roles: reference
- **cat5_jellopus_left** (2026-04-30T10:43:23) — 1 files, roles: reference
- **cat5_jellopus_back** (2026-04-30T10:42:59) — 1 files, roles: reference
- **cat3_pipeline_motion** (2026-04-30T09:57:47) — 2 files, roles: mesh, reference

_Rescued meshes (6):_ `cat1_baked_selftest.glb`, `cat1_baked_sharp.glb`, `cat1_baked_mz.glb`, `cat1_reshaped.glb`, `cat1_baked_preview.png` …
## Recent commits

- `9be8a4f` _2026-04-30_ **v80x** — tour 5/6 — full 5-cat validation, all categories ≥ 90 ★
- `3b75efb` _2026-04-30_ **v80w** — tour 4/6 — Cat 2 humanoid silhouette: 84.4 → 93.4 (kind-aware reshape)
- `c53bda3` _2026-04-30_ **v80v** — tour 3/6 — 4 nouveaux presets articulés (climb/spin/roar/vibrate)
- `3e34796` _2026-04-30_ **v80u** — tour 2/6 — motion vocabulary 22 → 34 fixtures, +85 synonyms
- `d08398a` _2026-04-30_ **v80t** — tour 1/6 — Cat 4 manifold rescue stage + alien-artifact kind fix
- `29baf94` _2026-04-30_ **v80s** — gate_handoff_render + recursion guard via AURORA_HANDOFF_SKIP_SELFTEST
- `f64196c` _2026-04-30_ **v80r** — 32nd gate runs mesh-decision unit tests (40 tests, ~8s)
- `696177b` _2026-04-30_ **v80q** — 31st gate runs python-services attribution tests (closes pre-commit gap)
- `39abec3` _2026-04-30_ **v80p** — 30th selftest gate runs the TS suite (closes pre-commit-only gap)
- `e6f5f86` _2026-04-30_ **v80o** — TS client closes parity for /api/agents/{list,<name>,metrics}
- `06a19b3` _2026-04-30_ **v80n** — env_check verifies v80 core scripts present (10 of them)
- `02ac0bd` _2026-04-30_ **v80m** — refresh handoff known_state to match v80 reality
## Useful commands

```bash
/aurora-self-test          # 17 gates, ~9s
/aurora-ship-it            # 4 gates: selftest + TS + tree clean + pushed
/aurora-validate           # frontmatter + tracker + KNOWN_AGENTS
/aurora-test               # 15 hook unit tests, ~0.7s
/aurora-dashboard          # render dashboard.html
/aurora-handoff            # regenerate this file
/aurora-route-test "<3D prompt>"  # which pipeline?
/aurora-mesh-validate "<glb>" "<prompt>"  # autonomous validate
/aurora-mesh-rescue ...    # full rescue chain
python bridge_doctor.py --check-only   # is the bridge alive?
python bridge_doctor.py    # respawn local bridge
```

## What's reliably true today

- **5 OOD categories at Meshy-grade**: Cat 1 91.3 · Cat 2 93.4 · Cat 3 99.5 · Cat 4 99.4 · Cat 5 98.8 — average **96.5/100** all watertight, files under `application/output/3d/v80x_*/`. Achieved via the 6-tour closure: manifold rescue stage, kind-aware reshape (max_distortion 0.55 for organic kinds), 4 articulated motion presets, motion vocab 22 → 42 fixtures.
- **38 agents** Opus 4.7 (1 master + 11 leads + 24 sub + 2 crosscut), see `AGENT_SYSTEM.md`.
- **6 hooks** auto-track every Agent dispatch in `.claude/agent-tracker/state.json`.
- **Python tooling writes tracker entries** via `tracker_helper.record_dispatch()`
  with `metadata` (run_id, kind, score_delta, final_mesh) — auto_rescue → `3d-quality-rescuer`, full pipeline → `3d-lead`.
- **33-gate self-test** + **4-gate ship-it**, **32 TS tests**, ~140 Python tests.
- **19 bridge endpoints** for 3D toolchain (`/api/3d/*` × 14) + agents introspection.
- **32 slash commands** with a script-resolution linter.
- **TS client** `application/src/services/meshRescue.ts` at full parity.
- **Detect → surface → self-heal watchdog**: `tracker_health` flags stale work, `aurora_watchdog` consolidates the four signals, `/aurora-archive-stale` auto-archives.
- **Rescue chain stages** (in order, each opt-in based on failed_axes):
  1. bake_vertex_colors — color richness (every Cat needed it: +20)
  2. mesh_postprocess --auto-fix — manifold (Cat 4: 40→100, +9.4)
  3. mesh_reshape (kind-aware) — silhouette aspect (Cat 2: 50→80, +9)
- **42 motion fixtures** parity TS↔Python (was 22). 45 motion presets including v80v additions: character.climb, character.spin, creature.roar, mechanism.vibrate.
- **Score history** (`application/output/3d/score_history.jsonl`) feeds dashboard sparklines + trend banner + per-axis effectiveness bars + watchdog top-runs.
- **Coverage report** (`/aurora-coverage`) surfaces dead agents.
- **Tracker query** (`/aurora-tracker-query` + `GET /api/agents/dispatches`) closes the audit chain.
- **Pre-commit gate** active when `git config core.hooksPath .claude/git-hooks` set.
- **CI template** at `.claude/ci/validate-agents.yml.template` covers all of the above.

