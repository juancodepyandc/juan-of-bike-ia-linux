---
description: Restore vertex colors on a GLB by projecting the FLUX reference image (rescue Hunyuan3D monochrome output)
argument-hint: <mesh_glb> <reference_png> <output_glb> [kind]
allowed-tools: Bash
---

```bash
python application/python-services/bake_vertex_colors.py \
  --mesh "$1" --reference "$2" --output "$3" --kind "${4:-generic}" --pretty
```

Or via bridge:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"mesh\":\"$1\",\"reference\":\"$2\",\"output\":\"$3\",\"kind\":\"${4:-generic}\"}" \
  http://127.0.0.1:3001/api/3d/bake-colors
```

Subject kinds (per `subject_kind_extractor`): `character`, `humanoid`, `quadruped`, `creature`, `pc_tower`, `case`, `computer`, `vehicle`, `product`, `gadget`, `architecture`, `sphere`, `generic`. The kind picks the projection axes (e.g. quadrupeds project on Z-Y for the side view, PC towers on X-Y front).

Output: new GLB at `--output` with rich vertex colors. Score should rebound from `color_richness=0` (monochrome) to `color_richness=100` (rich palette).

Live verdict on Cat 1:
```
input  unique_colors: 1
output unique_colors: 46181
score  overall: 70.2 → 90.2
```

Schema: `aurora.color_bake.v1`. Used by `/aurora-self-test` gate 10.

Note: this is a planar projection — works best on subjects with a clear front face (PC tower, character, vehicle). For complex 3D color zoning you'd want multi-view projection (front + back + side), tracked as a follow-up.
