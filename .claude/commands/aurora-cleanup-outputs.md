---
description: Prune stale 3D test artifacts from application/output/3d/ (dry-run by default)
allowed-tools: Bash
---

```bash
python application/python-services/aurora_cleanup_outputs.py --pretty
```

To actually delete (defaults to dry-run):

```bash
python application/python-services/aurora_cleanup_outputs.py --apply --pretty
```

Prunable patterns:
- `*_endpoint.glb`, `*_endpoint_baked.glb` — selftest gate output artifacts
- `*_selftest.glb`, `*_selftest_baked.glb` — selftest gate output
- `*_test.glb` — ad-hoc smoke test output
- `aurora_cleaned.glb` — leftover from `blender_bridge.py --mode cleanup`

Preserved:
- `{run_id}_mesh.glb` (Hunyuan3D raw)
- `{run_id}_reference.png` (FLUX ref) + multi-view siblings
- `{run_id}_front_synth_seed.png` + `_front_synthetic.png`
- `rescue_{run_id}/*.glb`
- `cat{N}_*.glb` Cat 1-N final variants
- Any non-matching file by default

Schema: `aurora.cleanup.v1`. Output: prune candidates with size totals + applied deletes when `--apply`.
