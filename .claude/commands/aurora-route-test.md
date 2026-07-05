---
description: Self-test the 3D pipeline routing decision for a prompt without running the full pipeline
argument-hint: <3D prompt>
allowed-tools: Bash
---

Run the routing self-test on the given prompt:

```bash
python application/scripts/route_test.py "$ARGUMENTS"
```

Returns JSON with:
- `flags`: photogrammetry / mechanism / stylized / luxury_material
- `dreamgaussianPreferred`: bool — true if DreamGaussian (MIT, EU-safe) wins over Hunyuan3D default
- `probable_pipeline`: human-readable verdict

The Python regexes mirror those in `application/src/services/threeDIntent.ts` `routePipeline()`. When you change one side, change both — `python application/scripts/test_route_test.py` (13 unit tests) guards against drift.

This was added in v78j after Cat 1 of the 3D /loop run produced a sub-par PC boitier mesh routed to default Hunyuan3D. The luxury-material detector now flips dreamgaussianPreferred for prompts mentioning quartz fumé, obsidienne, acajou, or rose, marbre, etc.
