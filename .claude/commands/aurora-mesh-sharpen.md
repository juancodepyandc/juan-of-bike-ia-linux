---
description: Sharpen a mesh — Laplacian smoothing + feature re-sharpening + vertex color smoothing
argument-hint: <mesh_glb> <output_glb> [kind] [smooth_iters]
allowed-tools: Bash
---

```bash
python application/python-services/mesh_sharpen.py \
  --mesh "$1" --output "$2" \
  --kind "${3:-generic}" --smooth-iters "${4:-4}" --smooth-lambda 0.5 \
  --pretty
```

Or via bridge endpoint:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"mesh\":\"$1\",\"output\":\"$2\",\"kind\":\"${3:-generic}\",\"smooth_iters\":${4:-4}}" \
  http://127.0.0.1:3001/api/3d/mesh-sharpen
```

Three passes (each opt-out via flag):

1. **Laplacian smoothing** — N iterations (default 4) at λ (default 0.5). Removes vertex-level noise but preserves the global shape.
2. **Feature re-sharpening** — pushes vertex *away* from neighborhood mean where curvature is high (factor 0.3, conservative). Restores edges Laplacian blurred. Skip with `--no-features`.
3. **Vertex color smoothing** — 1 iteration at λ=0.25. Avoids pixel-grain colors after baking. Skip with `--no-color-smooth`.

TS client method:
```typescript
await client.sharpenMesh(mesh, output, kind, {
  smoothIters: 4, smoothLambda: 0.5,
  noFeatures: false, noColorSmooth: false,
})
```

Schema: `aurora.mesh_sharpen.v1`. Live verdict on Cat 1 baked: 46181 → 51229 unique colors after sharpening (smoothing diffuses palette).
