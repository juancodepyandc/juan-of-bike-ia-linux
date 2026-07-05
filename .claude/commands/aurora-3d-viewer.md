---
description: Generate a self-contained Three.js HTML viewer for any GLB (real PBR, no server)
argument-hint: <mesh_glb> <output_html> [title]
allowed-tools: Bash
---

```bash
python application/python-services/aurora_3d_viewer.py \
  --mesh "$1" --output "$2" --title "${3:-Aurora 3D}" --pretty
```

Or via bridge endpoint:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"mesh\":\"$1\",\"output\":\"$2\",\"title\":\"${3:-Aurora 3D}\"}" \
  http://127.0.0.1:3001/api/3d/viewer-html
```

Produces a single `.html` file (~5 KB) loading Three.js via importmap (CDN), with:
- ACES filmic tone mapping
- Hemisphere + key + fill lights
- OrbitControls (drag = orbit, scroll = zoom, right-drag = pan)
- Auto-fit + center based on bbox
- Vertex colors enabled when COLOR_0 attribute present (so baked GLBs render properly — matplotlib previews can't show them)

The mesh is copied next to the HTML by default so opening the HTML in a browser just works (no server needed).

Schema: `aurora.viewer.v1`. Used by `/aurora-self-test` gate 13.
