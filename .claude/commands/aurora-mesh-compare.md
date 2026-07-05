---
description: Compare two GLBs side-by-side on the 5-axis quality scorer
argument-hint: <left_glb> <right_glb> [kind]
allowed-tools: Bash
---

```bash
python application/python-services/mesh_compare.py \
  --left "$1" --right "$2" --kind "${3:-generic}" --pretty
```

Or via bridge:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"left\":\"$1\",\"right\":\"$2\",\"kind\":\"${3:-generic}\"}" \
  http://127.0.0.1:3001/api/3d/mesh-compare
```

Outputs:
- per-axis breakdown (left score / right score / delta)
- overall delta
- winner (`left` / `right` / `tie`)

Live verdict on Cat 1 (orig vs baked):
```
overall: 70.2 -> 90.2 (+20)
color_richness:    0 ->  100  (+100)  ← rescue worked
silhouette_aspect: 69 ->  69  (0)     ← unchanged (only color baked)
WINNER: right
```

Schema: `aurora.mesh_compare.v1`. Used by `/aurora-self-test` gate 12.
