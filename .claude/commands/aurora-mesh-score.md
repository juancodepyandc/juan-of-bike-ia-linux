---
description: Score a 3D mesh GLB on 5 axes (color, density, aspect, manifold, surface) — autonomous retry decision
argument-hint: <mesh_path> <kind>
allowed-tools: Bash
---

```bash
python application/python-services/mesh_quality_score.py --mesh "$1" --kind "$2" --pretty
```

Or HTTP via bridge:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"mesh_path\":\"$1\",\"kind\":\"$2\"}" \
  http://127.0.0.1:3001/api/3d/mesh-score
```

Subject kinds: `character`, `humanoid`, `quadruped`, `creature`, `pc_tower`, `case`, `computer`, `vehicle`, `product`, `gadget`, `architecture`, `sphere`, `generic`.

Output: 5-axis breakdown (each 0-100) + overall score + `retry_recommended` flag + `failed_axes` list.

Hard floors that force retry independent of overall score:
- color_richness < 25 (monochrome dealbreaker for Meshy-equivalent quality)
- silhouette_aspect < 40 (wrong shape — sphere classified as PC tower etc.)
- manifold_health < 30 (non-watertight or many broken faces)

Used in the autonomous /loop pipeline: post-Hunyuan3D, the orchestrator scores and decides whether to retry with DreamGaussian or accept. Cat 1 of the 3D /loop run validated this — its monochrome output (color_richness=0) correctly triggers retry.
