#!/usr/bin/env python
"""Aurora 3D HTML viewer — generates a self-contained `viewer.html` that
loads any GLB and renders it with real PBR (Three.js + GLTFLoader +
OrbitControls), so the user can actually see colors that the matplotlib
preview can't display.

Reads a GLB path, copies it next to the HTML output (or references it via
the bridge URL), and writes a single .html file with Three.js inlined via
CDN. No build step, no server needed — open in any browser.

Usage:
    python aurora_3d_viewer.py --mesh out.glb --output viewer.html
    python aurora_3d_viewer.py --mesh out.glb --output viewer.html \\
        --title "Cat 1 baked PC" --bridge-url http://127.0.0.1:3001
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path


# Importmap pinned to recent stable. Use unpkg for ESM.
THREE_VERSION = "0.169.0"


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;
       background:#0d1117;color:#e6edf3;height:100vh;overflow:hidden;
       display:flex;flex-direction:column}}
  header{{padding:10px 16px;background:#161b22;border-bottom:1px solid #30363d;
         display:flex;justify-content:space-between;align-items:center;
         font-size:13px}}
  header h1{{font-size:14px;color:#7ee787}}
  header .meta{{color:#8b949e;font-size:11px}}
  header code{{background:#0d1117;padding:2px 6px;border-radius:3px}}
  #canvas-wrap{{flex:1;position:relative;background:#0d1117}}
  #canvas-wrap canvas{{display:block;width:100%;height:100%}}
  #status{{position:absolute;top:10px;left:10px;background:#161b22cc;
           padding:6px 10px;border-radius:4px;font-size:11px;color:#79c0ff}}
  #stats{{position:absolute;bottom:10px;right:10px;background:#161b22cc;
          padding:6px 10px;border-radius:4px;font-size:11px;color:#8b949e}}
  .err{{color:#ff7b72}}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="meta">mesh <code>{mesh_basename}</code></div>
</header>
<div id="canvas-wrap">
  <div id="status">loading…</div>
  <div id="stats"></div>
</div>
<script type="importmap">
{{
  "imports": {{
    "three": "https://unpkg.com/three@{three_version}/build/three.module.js",
    "three/addons/": "https://unpkg.com/three@{three_version}/examples/jsm/"
  }}
}}
</script>
<script type="module">
import * as THREE from 'three'
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js'
import {{ GLTFLoader }} from 'three/addons/loaders/GLTFLoader.js'
// iter11.C: DRACOLoader wires KHR_draco_mesh_compression so the standalone
// viewer can read the new compressed bake outputs (8-15× smaller).
import {{ DRACOLoader }} from 'three/addons/loaders/DRACOLoader.js'

const wrap = document.getElementById('canvas-wrap')
const status = document.getElementById('status')
const stats = document.getElementById('stats')

const scene = new THREE.Scene()
scene.background = new THREE.Color(0x0d1117)

const camera = new THREE.PerspectiveCamera(40, wrap.clientWidth / wrap.clientHeight, 0.001, 1000)
// iter17.C: closer side-angle framing. The Strimer / cable bundle runs along
// X axis (length 0.5m post-fit), so we drop the camera down (smaller Y),
// pull it back along +Z, and slightly off-axis on +X to reveal the entire
// length plus per-strand detail. Distance ≈ length × 1.5 = 0.75 keeps the
// cable filling ~80% of the viewport with its individual wires legible. The
// turntable update in the render loop rotates this around the world Y axis
// so the user sees every angle in a slow loop without manual orbit.
camera.position.set(0.15, 0.55, 0.72)

const renderer = new THREE.WebGLRenderer({{ antialias: true }})
renderer.setSize(wrap.clientWidth, wrap.clientHeight)
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
// iter27.fix3: revert to ACES + standard exposure as the default — iter17.E
// dimmed-and-linear was tuned for one specific case (Strimer LED chase), and
// crushed every non-emissive procedural mesh (motherboard PCB, belt rubber)
// to near-black. ACESFilmicToneMapping with exposure 1.0 renders both
// emissive and matte materials legibly.
renderer.toneMapping = THREE.ACESFilmicToneMapping
renderer.toneMappingExposure = 1.0
wrap.appendChild(renderer.domElement)

const controls = new OrbitControls(camera, renderer.domElement)
controls.enableDamping = true
controls.dampingFactor = 0.06
controls.target.set(0, 0, 0)

// iter28.fix2: brighter 3-light + back rim so dark rubber/chrome materials
// (V-belt, chrome heatsinks) render with definition. ACES rolls off the
// brightness so pure-emissive LEDs still pop without washing.
scene.add(new THREE.HemisphereLight(0xffffff, 0x222233, 1.4))
const key = new THREE.DirectionalLight(0xffffff, 2.2)
key.position.set(5, 5, 5)
scene.add(key)
const fill = new THREE.DirectionalLight(0xa9c8ff, 1.0)
fill.position.set(-3, 2, -2)
scene.add(fill)
const rim = new THREE.DirectionalLight(0xfff0d0, 0.7)
rim.position.set(0, 4, -6)
scene.add(rim)

const loader = new GLTFLoader()
// iter11.C / iter18.B / iter27.fix3: attach DRACOLoader so Draco-compressed
// bake GLBs decode. The earlier "/draco/-when-http(s)" rule broke the viewer
// when served from arbitrary http servers (test rigs, file shares) that
// don't proxy /draco/ to the bridge. Use the gstatic CDN by default — it
// works offline-cached after the first load and from any host. Only override
// to /draco/ when explicitly served from bridge:3001 (which DOES serve the
// local Draco WASM via the iter18.B route).
const dracoLoader = new DRACOLoader()
const _dracoCdn = 'https://www.gstatic.com/draco/v1/decoders/'
const _dracoLocal = '/draco/'
const _isBridge = (typeof window !== 'undefined') &&
                  window.location && window.location.port === '3001'
dracoLoader.setDecoderPath(_isBridge ? _dracoLocal : _dracoCdn)
loader.setDRACOLoader(dracoLoader)
let animationMixer = null
const animationClock = new THREE.Clock()
loader.load(
  {mesh_url_js!s},
  (gltf) => {{
    const obj = gltf.scene || gltf.scenes[0]
    // Center + scale so the mesh fits the viewport regardless of source units.
    const box = new THREE.Box3().setFromObject(obj)
    const size = new THREE.Vector3()
    box.getSize(size)
    const center = new THREE.Vector3()
    box.getCenter(center)
    const longest = Math.max(size.x, size.y, size.z) || 1
    const targetDim = 0.5
    const scale = targetDim / longest
    obj.scale.setScalar(scale)
    obj.position.sub(center.multiplyScalar(scale))

    // iter17.C/E: detect "thin elongated" meshes (cables, strips) where the
    // smallest dim is < 1/8 the longest. Auto-fit on `longest` makes such
    // meshes pixel-thin, so we zoom the camera in along that thin axis to
    // re-frame on the cross-section. Cable reads as 24 distinct wires
    // instead of a 16-px-tall blur.
    const sx = size.x * scale, sy = size.y * scale, sz = size.z * scale
    const dimsSorted = [sx, sy, sz].sort((a, b) => a - b)
    const minDim = dimsSorted[0], midDim = dimsSorted[1], maxDim = dimsSorted[2]
    // iter28.fix: distinguish TRUE tubes (cable/strip with max >> mid >> min)
    // from FLAT plates (motherboard with max ≈ mid >> min). Both used to hit
    // the "elongated" path because of min/max ratio, sending the motherboard
    // camera to a 30deg side angle that only showed a corner.
    const isThinTube = maxDim > 0 && midDim / maxDim < 0.30 && minDim / maxDim < 0.125
    const isFlatPlate = minDim / maxDim < 0.125 && midDim / maxDim >= 0.30
    if (isThinTube) {{
      // Cable / LED strip — angle shot to see length + cross-section
      const dist = maxDim * 0.55
      camera.position.set(dist * 0.20, dist * 0.30, dist * 0.95)
      camera.lookAt(0, 0, 0)
      controls.target.set(0, 0, 0)
      controls.update()
      window._iter17_camRadius = Math.hypot(camera.position.x, camera.position.z)
      window._iter17_camY = camera.position.y
    }} else if (isFlatPlate) {{
      // Motherboard / flat panel — top-down 3/4 view so the user sees the
      // whole component layout, not just a corner.
      const dist = maxDim * 0.95
      camera.position.set(0, dist * 0.85, dist * 0.50)
      camera.lookAt(0, 0, 0)
      controls.target.set(0, 0, 0)
      controls.update()
      window._iter17_camRadius = Math.hypot(camera.position.x, camera.position.z)
      window._iter17_camY = camera.position.y
    }}

    let triCount = 0
    // iter7.B: collect aurora.oled-atlas.v1 bindings so the standalone viewer
    // animates OLED screens just like Aurora's ModelView.tsx does. The Blender
    // baker writes a custom property on the screen material; the glTF exporter
    // mirrors it into material.userData / material.userData.gltfExtras.
    const oledBindings = []
    const ledBindings = []
    const beltBindings = []
    function hexToRgb(hex) {{
      const h = hex.startsWith('#') ? hex.slice(1) : hex
      if (h.length !== 6) return {{r: 1, g: 0, b: 0.2}}
      return {{
        r: parseInt(h.slice(0, 2), 16) / 255,
        g: parseInt(h.slice(2, 4), 16) / 255,
        b: parseInt(h.slice(4, 6), 16) / 255,
      }}
    }}
    // iter17.E: KHR_lights_punctual point lights baked in at 190 candela
    // (Blender's 3.5W → glTF candela conversion). At that intensity, four
    // white point lights inside a 5cm bundle radius wash the per-strand
    // emissive material to white. We dim them by 0.05 (≈9 candela each) so
    // they still tint the air with a faint glow but don't dominate the
    // emissive material. We also color-tint each one (Blender's exporter
    // strips per-light color → all white in glTF) by sampling from the
    // material palette.
    obj.traverse((node) => {{
      if (node.isLight) {{
        node.intensity = node.intensity * 0.05
      }}
    }})
    obj.traverse((node) => {{
      if (node.isMesh) {{
        triCount += node.geometry.index ? node.geometry.index.count / 3
                                        : node.geometry.attributes.position.count / 3
        // Use vertex colors if the GLB has COLOR_0 attribute.
        if (node.geometry.attributes.color) {{
          if (node.material) {{
            node.material.vertexColors = true
            node.material.needsUpdate = true
          }}
        }}
        // OLED flipbook atlas binding
        const mats = Array.isArray(node.material) ? node.material : [node.material]
        mats.forEach((mat) => {{
          if (!mat) return
          const ud = mat.userData || {{}}
          const extras = ud.gltfExtras || ud.extras || null
          const candidate = (extras && extras.aurora_oled_atlas) || ud.aurora_oled_atlas
          if (candidate && typeof candidate === 'object') {{
            const fc = Number(candidate.frame_count)
            const fr = Number(candidate.frame_rate)
            if (Number.isFinite(fc) && fc >= 2 && Number.isFinite(fr) && fr > 0) {{
              const tex = mat.map
              if (tex) {{
                tex.magFilter = THREE.NearestFilter
                tex.minFilter = THREE.NearestFilter
                tex.wrapS = THREE.RepeatWrapping
                tex.wrapT = THREE.RepeatWrapping
                tex.generateMipmaps = false
                const dir = candidate.direction === 'v' ? 'v' : 'h'
                if (dir === 'v') tex.repeat.set(1, 1 / fc)
                else tex.repeat.set(1 / fc, 1)
                tex.offset.set(0, 0)
                tex.needsUpdate = true
                oledBindings.push({{
                  texture: tex,
                  frame_count: Math.max(2, Math.round(fc)),
                  frame_rate: fr,
                  direction: dir,
                }})
              }}
            }}
          }}
          // iter9.D: aurora.led-emission.v1 binding (parity with ModelView.tsx).
          // The Blender glTF exporter doesn't export shader-node-socket
          // animation, so the baker tags the material with extras carrying
          // the LED pattern; we re-drive material.emissive + intensity here.
          const ledCand = (extras && extras.aurora_led_emission) || ud.aurora_led_emission
          if (ledCand && typeof ledCand === 'object') {{
            const speedHz = Number(ledCand.speed_hz)
            const strength = Number(ledCand.emission_strength)
            const colors = Array.isArray(ledCand.colors) ? ledCand.colors.filter(s => typeof s === 'string') : []
            if (Number.isFinite(speedHz) && speedHz > 0
                && Number.isFinite(strength) && strength >= 0) {{
              if (colors.length === 0) colors.push('#ff0033')
              const allowed = ['static_color','breathing','pulse','chase','rainbow']
              const pattern = allowed.indexOf(ledCand.pattern) >= 0 ? ledCand.pattern : 'rainbow'
              // iter16.A: phase_offset is optional, default 0 (back-compat
              // with iter15). Clamp to [0,1] period fraction.
              const _po = Number(ledCand.phase_offset)
              const phaseOffset = Number.isFinite(_po) ? Math.max(0, Math.min(1, _po)) : 0
              // Pre-set first frame so we don't flash black on load.
              const first = hexToRgb(ledCand.base_color || colors[0])
              if (mat.emissive) mat.emissive.setRGB(first.r, first.g, first.b)
              mat.emissiveIntensity = strength
              mat.needsUpdate = true
              ledBindings.push({{
                material: mat,
                pattern,
                speed_hz: speedHz,
                colors,
                emission_strength: strength,
                phase_offset: phaseOffset,
              }})
            }}
          }}
          // iter24.B: aurora.belt-scroll.v1 binding (parity with ModelView.tsx).
          // Procedural belt-pulley meshes ship a stripe texture on the belt;
          // we scroll material.map.offset.x by speed_uv_per_sec each frame so
          // the user SEES the belt sliding along its path while the pulleys
          // rotate at the kinematic ratio.
          const beltCand = (extras && extras.aurora_belt_scroll) || ud.aurora_belt_scroll
          if (beltCand && typeof beltCand === 'object') {{
            const speedUv = Number(beltCand.speed_uv_per_sec)
            if (Number.isFinite(speedUv)) {{
              const beltDir = beltCand.direction === 'v' ? 'v' : 'h'
              const tex = mat.map
              if (tex) {{
                tex.magFilter = THREE.NearestFilter
                tex.minFilter = THREE.NearestFilter
                tex.wrapS = THREE.RepeatWrapping
                tex.wrapT = THREE.RepeatWrapping
                tex.generateMipmaps = false
                tex.offset.set(0, 0)
                tex.needsUpdate = true
                beltBindings.push({{
                  texture: tex,
                  speed_uv_per_sec: speedUv,
                  direction: beltDir,
                }})
              }}
            }}
          }}
        }})
      }}
    }})
    scene.add(obj)
    if (Array.isArray(gltf.animations) && gltf.animations.length > 0) {{
      animationMixer = new THREE.AnimationMixer(obj)
      for (const clip of gltf.animations) {{
        const action = animationMixer.clipAction(clip)
        action.reset()
        action.play()
      }}
      window._gltfAnimation = {{
        clip_count: gltf.animations.length,
        clip_names: gltf.animations.map(c => c.name || 'unnamed'),
      }}
    }}
    // Expose for the render loop
    window._oledBindings = oledBindings
    window._ledBindings = ledBindings
    window._beltBindings = beltBindings

    status.textContent = 'OK'
    stats.textContent = `${{triCount.toLocaleString()}} triangles`
    setTimeout(() => {{ status.style.opacity = '0' }}, 1500)
  }},
  (xhr) => {{
    if (xhr.lengthComputable) {{
      const pct = Math.round((xhr.loaded / xhr.total) * 100)
      status.textContent = `loading ${{pct}}%`
    }}
  }},
  (err) => {{
    console.error(err)
    status.textContent = 'load failed: ' + err.message
    status.classList.add('err')
  }}
)

function onResize() {{
  camera.aspect = wrap.clientWidth / wrap.clientHeight
  camera.updateProjectionMatrix()
  renderer.setSize(wrap.clientWidth, wrap.clientHeight)
}}
window.addEventListener('resize', onResize)

// iter7.B: clock for OLED flipbook stepping. Use a virtual time so that
// pause-on-tab-hidden naturally freezes the animation (visibility API).
let oledStartTime = performance.now()
let oledPausedAccum = 0
let oledPauseStart = null
document.addEventListener('visibilitychange', () => {{
  if (document.visibilityState === 'hidden') {{
    oledPauseStart = performance.now()
  }} else if (oledPauseStart != null) {{
    oledPausedAccum += performance.now() - oledPauseStart
    oledPauseStart = null
  }}
}})
// iter9.C: deterministic frame override for headless screenshot capture.
// `?t=0.5` freezes the OLED + LED virtual clock at 0.5s — the render loop
// uses that fixed value instead of performance.now()-based wall time. This
// is what the iter9 proof harness uses to capture three reproducible frames
// of the rainbow chase at 0s / 0.5s / 1.0s.
const _frozenTimeParam = new URLSearchParams(location.search).get('t')
const _frozenTime = _frozenTimeParam != null && Number.isFinite(parseFloat(_frozenTimeParam))
  ? parseFloat(_frozenTimeParam) : null

// iter17.C: optional turntable rotation. `?turntable=1` (default off so
// existing tests stay deterministic) orbits the camera slowly around the Y
// axis at 0.08 rev/s = 12.5s per full turn so the user sees the cable
// from every angle without touching the mouse. Disabled when `?t=` is set
// (frozen time + frozen camera = reproducible screenshots).
const _turntableParam = new URLSearchParams(location.search).get('turntable')
const _turntable = _turntableParam != null && _turntableParam !== '0' && _frozenTime == null
const _camRadius = Math.hypot(camera.position.x, camera.position.z)
const _camY = camera.position.y
const _camStartTime = performance.now()

function loop() {{
  requestAnimationFrame(loop)
  // iter17.C: turntable orbit (off unless ?turntable=1). Slow 0.08 rev/s so
  // the user perceives the cable's full silhouette without motion sickness.
  if (_turntable) {{
    const dt = (performance.now() - _camStartTime) / 1000.0
    const ang = dt * 2 * Math.PI * 0.08
    // iter17.E: prefer the post-fit thin-mesh radius if it was set during
    // load — otherwise fall back to the initial camera ring.
    const radius = window._iter17_camRadius != null ? window._iter17_camRadius : _camRadius
    const camY = window._iter17_camY != null ? window._iter17_camY : _camY
    camera.position.set(
      Math.sin(ang) * radius,
      camY,
      Math.cos(ang) * radius,
    )
    camera.lookAt(0, 0, 0)
  }}
  controls.update()
  if (animationMixer) {{
    if (_frozenTime != null) animationMixer.setTime(_frozenTime)
    else animationMixer.update(animationClock.getDelta())
  }}
  // iter7.B: step OLED atlases at draw-time. Same logic as ModelView.tsx —
  // floor(t * frame_rate) % frame_count gives the frame index, divided by
  // frame_count gives the UV offset.
  const bindings = window._oledBindings
  if (bindings && bindings.length > 0 && oledPauseStart == null) {{
    const t = _frozenTime != null ? _frozenTime
            : (performance.now() - oledStartTime - oledPausedAccum) / 1000.0
    for (const b of bindings) {{
      const step = Math.floor(t * b.frame_rate) % b.frame_count
      const u = step / b.frame_count
      if (b.direction === 'v') b.texture.offset.set(0, u)
      else b.texture.offset.set(u, 0)
    }}
  }}
  // iter9.D: drive aurora.led-emission.v1 bindings — same math as
  // motion_intent_bpy_runner.bake_led_emission so what you see in this
  // standalone viewer is what the baker authored.
  const ledBs = window._ledBindings
  if (ledBs && ledBs.length > 0 && oledPauseStart == null) {{
    const t = _frozenTime != null ? _frozenTime
            : (performance.now() - oledStartTime - oledPausedAccum) / 1000.0
    for (const b of ledBs) {{
      const period = 1 / b.speed_hz
      // iter16.C: shift t by phase_offset * period so chase/rainbow propagates
      // ALONG the cable (per-strand offset) instead of pulsing globally. Same
      // formula as ModelView.tsx _evalLedPattern (TS<->Python parity).
      const tEffective = t + (b.phase_offset || 0) * period
      const phaseT = (tEffective / period) % 1
      let r = 0, g = 0, bl = 0, intensity = b.emission_strength
      function hexRgb(hex) {{
        const h = hex.startsWith('#') ? hex.slice(1) : hex
        return {{
          r: parseInt(h.slice(0, 2), 16) / 255,
          g: parseInt(h.slice(2, 4), 16) / 255,
          b: parseInt(h.slice(4, 6), 16) / 255,
        }}
      }}
      if (b.pattern === 'static_color') {{
        const c = hexRgb(b.colors[0]); r = c.r; g = c.g; bl = c.b
      }} else if (b.pattern === 'breathing') {{
        const phase = (Math.sin(2 * Math.PI * phaseT) + 1) * 0.5
        const c = hexRgb(b.colors[0]); r = c.r; g = c.g; bl = c.b
        intensity = b.emission_strength * phase
      }} else if (b.pattern === 'pulse') {{
        const phase = phaseT < 0.5 ? 1 : 0
        const c = hexRgb(b.colors[0]); r = c.r; g = c.g; bl = c.b
        intensity = b.emission_strength * phase
      }} else if (b.pattern === 'chase') {{
        const idx = Math.floor(phaseT * b.colors.length) % b.colors.length
        const c = hexRgb(b.colors[idx]); r = c.r; g = c.g; bl = c.b
      }} else {{
        // rainbow
        const hue = (tEffective * b.speed_hz * 0.5) % 1
        const iH = Math.floor(hue * 6)
        const fH = hue * 6 - iH
        const q = 1 - fH
        switch (iH % 6) {{
          case 0: r = 1;  g = fH; bl = 0; break
          case 1: r = q;  g = 1;  bl = 0; break
          case 2: r = 0;  g = 1;  bl = fH; break
          case 3: r = 0;  g = q;  bl = 1; break
          case 4: r = fH; g = 0;  bl = 1; break
          default: r = 1; g = 0;  bl = q
        }}
      }}
      if (b.material.emissive) b.material.emissive.setRGB(r, g, bl)
      b.material.emissiveIntensity = intensity
    }}
  }}
  // iter24.B: drive aurora.belt-scroll.v1 bindings — scroll the belt
  // material's UV offset along U (or V) at speed_uv_per_sec. Same parity
  // as ModelView.tsx so what you see in this standalone viewer matches
  // what the React UI shows.
  const beltBs = window._beltBindings
  if (beltBs && beltBs.length > 0 && oledPauseStart == null) {{
    const t = _frozenTime != null ? _frozenTime
            : (performance.now() - oledStartTime - oledPausedAccum) / 1000.0
    for (const b of beltBs) {{
      const u = t * b.speed_uv_per_sec
      const wrapped = ((u % 1) + 1) % 1
      if (b.direction === 'v') b.texture.offset.set(0, wrapped)
      else b.texture.offset.set(wrapped, 0)
    }}
  }}
  renderer.render(scene, camera)
}}
loop()
</script>
</body>
</html>
"""


def render(mesh_path: Path, output_path: Path, title: str | None = None,
           bridge_url: str | None = None, copy_mesh: bool = True) -> dict:
    if not mesh_path.is_file():
        return {"ok": False, "error": f"mesh not found: {mesh_path}"}

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Decide how the HTML references the mesh:
    #   - if bridge_url given, build /api/download/<rel> URL
    #   - else copy the mesh next to the HTML and reference by relative path
    if bridge_url:
        rel = mesh_path.resolve().as_posix()
        # Strip the application/ prefix if present (bridge serves from there).
        marker = "/application/"
        idx = rel.find(marker)
        rel_for_bridge = rel[idx + len(marker):] if idx >= 0 else mesh_path.name
        mesh_url = f"{bridge_url.rstrip('/')}/api/download/{rel_for_bridge}"
    elif copy_mesh:
        target = output_path.parent / mesh_path.name
        if target.resolve() != mesh_path.resolve():
            shutil.copy2(mesh_path, target)
        mesh_url = mesh_path.name
    else:
        mesh_url = str(mesh_path)

    title_text = title or f"Aurora 3D — {mesh_path.name}"
    html_text = HTML_TEMPLATE.format(
        title=html.escape(title_text),
        mesh_basename=html.escape(mesh_path.name),
        three_version=THREE_VERSION,
        mesh_url_js=json.dumps(mesh_url),
    )
    output_path.write_text(html_text, encoding="utf-8")
    return {
        "ok": True,
        "schema": "aurora.viewer.v1",
        "mesh": str(mesh_path),
        "output_html": str(output_path),
        "mesh_url": mesh_url,
        "size_bytes": output_path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aurora 3D viewer HTML generator")
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", default=None)
    parser.add_argument("--bridge-url", default=None,
                        help="If set, mesh is loaded via /api/download/<rel>")
    parser.add_argument("--no-copy", action="store_true",
                        help="Don't copy the mesh next to the HTML")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    result = render(
        Path(args.mesh), Path(args.output),
        args.title, args.bridge_url, copy_mesh=not args.no_copy,
    )
    if args.pretty and result.get("ok"):
        sys.stdout.write(
            f"viewer -> {result['output_html']}\n"
            f"  mesh url: {result['mesh_url']}\n"
            f"  size:     {result['size_bytes']} bytes\n"
        )
    else:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=True) + "\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
