---
description: Diagnose where colors collapse in the 3D pipeline (FLUX ref → Hunyuan3D mesh → post-process)
argument-hint: <reference_png> <mesh_glb> [post_mesh_glb]
allowed-tools: Bash
---

```bash
python application/python-services/mesh_color_diagnostic.py \
  --reference "$1" --mesh "$2" --pretty
```

Or via bridge:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"reference\":\"$1\",\"mesh\":\"$2\"}" \
  http://127.0.0.1:3001/api/3d/color-diagnostic
```

Output:
- `reference.unique_colors` — palette richness of the FLUX reference image
- `mesh.unique_colors` — palette richness of the GLB vertex colors
- `color_loss_ratio_ref_to_mesh` — 0.0 = perfect preservation, 1.0 = total collapse
- `stage_lost` — `hunyuan3d` | `post_process` | `none`
- `suggestions` — actionable next steps (switch pipeline, bake vertex colors, multi-view ref…)

Live verdict on Cat 1 (boitier PC):
```
stage_lost: hunyuan3d
color_loss_ratio: 0.9991
reference.unique_colors: 1066
mesh.unique_colors: 1
DECISION: switch to DreamGaussian (per v78j routing fix)
```

Schema: `aurora.color_diagnostic.v1`. Used by /aurora-self-test gate 9.
