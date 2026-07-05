---
description: Auto-rescue every grouped 3D run in a directory (mesh + reference) using auto_rescue chain
argument-hint: <output_dir> [source_dir] [fallback_prompt]
allowed-tools: Bash
---

```bash
python application/python-services/mesh_batch_rescue.py \
  --dir "${2:-application/output/3d}" \
  --output-dir "$1" \
  --fallback-prompt "${3:-generic 3D object}" \
  --pretty
```

For each grouped run found by `mesh_run_index`:
1. Locate `<id>_mesh.glb` + `<id>_reference.png`
2. Read prompt from sidecar `<id>_prompt.txt` (or use fallback)
3. Run `auto_rescue_mesh` (extract kind → score → bake if color → reshape if aspect → re-score)
4. Write rescued GLB to `<output_dir>/<run_id>/`

Output: per-run audit + global avg score delta. Skipped runs (missing mesh or reference) listed separately.

Live verdict (current repo state):
```
rescued: 1, failed: 0, skipped: 1
avg score delta: +20.0
[OK] juan_bike_1777509822533     kind=pc_tower  score 70.2 -> 90.2
[SKIP] juan_bike_1777508583733     missing mesh or reference
```

Schema: `aurora.batch_rescue.v1`. Ideal for processing the Cat 2/3/4
backlog when the UI generates a wave of meshes.
