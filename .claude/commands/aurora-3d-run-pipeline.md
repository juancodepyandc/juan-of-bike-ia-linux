---
description: End-to-end 3D pipeline via the bridge — prompt → FLUX → Hunyuan3D → rescue → optional motion bake
argument-hint: <prompt> <run_id> [motion_prompt]
allowed-tools: Bash
---

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"prompt\":\"$1\",\"run_id\":\"$2\"$([ -n \"$3\" ] && echo \",\\\"motion_prompt\\\":\\\"$3\\\"\")}" \
  --max-time 2400 \
  http://127.0.0.1:3001/api/3d/run-pipeline
```

Or via the TS client (`application/src/services/meshRescue.ts`):

```typescript
const client = createMeshRescueClient(bridgeBase)
const res = await client.runPipeline(prompt, runId, {
  motionPrompt: 'le perso marche',
  multiView: true,
  force: false,
})
```

Endpoint: `POST /api/3d/run-pipeline`. Body:
- `prompt` (required) — 3D prompt
- `run_id` (required) — unique id, used in filenames
- `motion_prompt` (optional) — bakes animation if provided
- `multi_view` (optional bool) — default auto based on extracted kind
- `force` (optional bool) — re-run even if intermediate files exist

Returns `aurora.pipeline.v1` audit JSON: extract_kind → flux_synth → hunyuan3d → auto_rescue → motion_bake. ~25 min for full cycle including Hunyuan3D inference. Bridge timeout: 40 min.

Live verdict on Cat 3 + motion (v79p):
```
score: 79.4 → 99.4 (+20.0)
final mesh:    rescue_cat3_pipeline_motion/cat3_pipeline_motion_mesh_baked.glb
rigged mesh:   cat3_pipeline_motion_RIGGED.glb (108 MB, gear_mesh_rotate baked)
total elapsed: 1556s
```

Schema: `aurora.pipeline.v1`.
