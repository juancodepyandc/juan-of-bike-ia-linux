---
description: End-to-end 3D pipeline — prompt → FLUX → Hunyuan3D → auto_rescue → audit JSON (single command)
argument-hint: <prompt> <run_id>
allowed-tools: Bash
---

```bash
python application/python-services/aurora_3d_pipeline.py \
  --prompt "$1" --run-id "$2" --pretty
```

Force multi-view FLUX (recommended for humanoid / character / vehicle):

```bash
python application/python-services/aurora_3d_pipeline.py \
  --prompt "..." --run-id X --multi-view --pretty
```

Force single-view (faster, fine for products / abstract objects):

```bash
python application/python-services/aurora_3d_pipeline.py \
  --prompt "..." --run-id X --single-view --pretty
```

Auto mode (default): subject_kind extracted from prompt → multi-view if kind in {character, humanoid, quadruped, creature, vehicle, pc_tower, case, computer}, else single-view.

Idempotent: re-runs reuse `<run_id>_reference.png` and `<run_id>_mesh.glb` if present. Pass `--force` to regenerate.

Stages:
1. `extract_kind` — subject_kind_extractor regex on prompt
2. `multi_view_decision` — auto / forced based on kind
3. `flux_synth` — single or multi-view, ~30-170s
4. `hunyuan3d` — mesh generation, 5-20 min depending on multi-view + GPU
5. `auto_rescue` — score → bake (if color failure) → reshape (if aspect failure) → re-score, ~30-60s

Schema: `aurora.pipeline.v1`. Returns audit JSON with every stage's path + score + delta.

Live verdict on Cat 2 multi-view (cyborg-shark humanoid):
```
kind: humanoid
multi_view: True
score: 53.9 → 84.4 (+30.5)
final mesh: application/output/3d/rescue_cat2_perso_mv/cat2_perso_mv_mesh_reshaped.glb
chain: bake (112361 colors) + reshape ([1.0, 0.7, 0.7])
```

Notable finding: multi-view doesn't materially lift humanoid overall score (84.7 single vs 84.4 multi — within margin) but produces 60% more unique vertex colors (112361 vs 70102) — richer 360° coverage even when the Hunyuan3D backbone caps the silhouette accuracy.
