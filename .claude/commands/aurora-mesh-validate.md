---
description: Autonomous mesh validation — prompt + GLB → kind extracted, score, retry decision (no human classification needed)
argument-hint: <mesh_path> <prompt>
allowed-tools: Bash
---

```bash
python application/python-services/auto_validate_mesh.py \
  --mesh "$1" --prompt "$2" --pipeline hunyuan3d --pretty
```

Or via bridge endpoint:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"mesh_path\":\"$1\",\"prompt\":\"$2\",\"pipeline\":\"hunyuan3d\"}" \
  http://127.0.0.1:3001/api/3d/auto-validate
```

Output:
- `extraction`: `{kind, confidence, matched_pattern, alternatives}` — derived from prompt
- `score`: 5-axis breakdown + `retry_recommended` + `failed_axes`
- `next_action`: `{action: "retry_pipeline" | "accept", next_pipeline: "dreamgaussian" | "procedural_or_multiview" | "mesh_postprocess" | null, reason: "..."}`

Pipeline rotation graph:
- hunyuan3d color/aspect fail → dreamgaussian
- hunyuan3d manifold fail     → mesh_postprocess
- dreamgaussian color/aspect  → procedural_or_multiview
- mesh_postprocess manifold   → accept (last resort)

Live verdict on Cat 1 (boitier PC):
```
kind=pc_tower (confidence 1.0, matched 'boitier')
overall=70.2, retry=True, failed_axes=['color_richness']
DECISION: retry with dreamgaussian
```

Schema: `aurora.auto_validate.v1`. Designed to plug into the post-Hunyuan3D step in ModelView orchestration so the system retries autonomously without human intervention.
