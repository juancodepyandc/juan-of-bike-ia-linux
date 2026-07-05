---
description: Index all 3D runs in application/output/3d/ — grouped by run id with mesh + reference + variants
allowed-tools: Bash
---

```bash
python application/python-services/mesh_run_index.py --pretty
```

Or scored:

```bash
python application/python-services/mesh_run_index.py --score --kind pc_tower --pretty
```

Or via bridge:

```bash
curl -sS http://127.0.0.1:3001/api/3d/run-index | python -m json.tool
curl -sS "http://127.0.0.1:3001/api/3d/run-index?score=1&kind=pc_tower" | python -m json.tool
```

Groups files by run id (naming convention `<id>_mesh.glb`, `<id>_reference.png`, `<id>_front_synthetic.png`). Returns:
- `runs[]`: each with files + latest_mtime + total_size + has_mesh / has_reference
- `standalones[]`: baked variants, viewers, previews — anything not part of a run group

Schema: `aurora.run_index.v1`. Used by `/aurora-self-test` gate 14.

Live verdict for the current state:
```
2 runs, 22 standalone files
[2026-04-30] juan_bike_1777509822533  (4 files: front_synth_seed, front_synthetic, reference, mesh)
[2026-04-30] juan_bike_1777508583733  (2 files: front_synth_seed, front_synthetic)
```
