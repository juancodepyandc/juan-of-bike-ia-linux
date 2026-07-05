---
description: Full autonomous 3D mesh rescue chain — validate, bake colors if needed, reshape if needed, re-validate
argument-hint: <mesh_glb> <reference_png> <prompt> <output_dir>
allowed-tools: Bash
---

```bash
python application/python-services/auto_rescue_mesh.py \
  --mesh "$1" --reference "$2" --prompt "$3" --output-dir "$4" --pretty
```

Or via bridge:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"mesh\":\"$1\",\"reference\":\"$2\",\"prompt\":\"$3\",\"output_dir\":\"$4\"}" \
  http://127.0.0.1:3001/api/3d/auto-rescue
```

Pipeline:
1. Extract subject_kind from prompt (regex)
2. Score initial mesh
3. If `color_richness` fails → `bake_vertex_colors` (project FLUX ref onto vertices)
4. Re-score
5. If `silhouette_aspect` fails → `mesh_reshape` (non-uniform scale toward canonical aspect, max 30% distortion)
6. Re-score
7. Return audit trail with each stage's score

Live result on Cat 1 (boitier PC):
```
Initial: 70.2  failed=['color_richness']
+ bake:  90.2  failed=[]              ← color rescued
Final:   90.2  delta: +20.0
```

If aspect was also failing (below hard floor 40), reshape would chain in.

Schema: `aurora.auto_rescue.v1`. Used by `/aurora-self-test` gate 11.
