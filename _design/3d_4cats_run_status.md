# 3D pipeline — 4 categories hors-base run status

Tracker for the `3D.txt` /loop directive: validate 4 categories outside any training distribution, fix on fail.

| Cat | Prompt | Pipeline status | Form verdict | Notes |
|-----|--------|-----------------|---------------|-------|
| 1 | boitier PC quartz fumé translucide, lotus or rose, obsidienne, acajou nordique | functional (run id `1777509822533`, retry 3, tunnel cooper) | sub-par — cubic 12×12×6 cm bbox, expected tower form | Hunyuan3D weak on architectural/hard-edge objects. Improvement candidates listed in `application/output/3d/CAT_RUN_STATUS.md`. |
| 2 | (TBD) perso fictif | not started | — | Hunyuan3D's strong suit, expected ≥85 fidelity. |
| 3 | (TBD) mécanique custom | not started | — | Should route to procedural Blender if intent matches. |
| 4 | (TBD) objet original | not started | — | Generic stylized — DreamGaussian preferred. |

## Cat 1 mesh integrity (verified locally)

```
GLB: application/output/3d/juan_bike_1777509822533_mesh.glb
verts=402644 faces=805304
bbox=[0.116, 0.120, 0.059] m
visual=ColorVisuals (vertex colors present)
```

Reference image (`*_reference.png`) is correct: PC tower with quartz translucent side panel, copper/rose-gold accent, dark interior, RGB fans. Hunyuan3D's mesh does not capture the tower silhouette nor the panel topology.

## Cat 1 follow-up (not blocking, tracked for next iteration)

- `application/src/services/threeDIntent.ts`: extend keyword list to route `boitier`, `PC`, `case`, `tower`, `computer`, `ordinateur` to DreamGaussian preferred (currently default → Hunyuan3D).
- Multi-view reference generation (front + back + side) before Hunyuan3D would improve silhouette.
- Tracked in `application/output/3d/CAT_RUN_STATUS.md` (local).

## Discipline

- Local bridge 200 ✓, tunnel cooper-inspection 200 ✓, motion self-test 13/13, parser 17/17.
- Per 3D.txt rule: never `update-aurora.bat` without commit+push first.
- Each cat run gets a tracker entry here when complete.
