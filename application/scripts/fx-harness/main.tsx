// Banc de l'écran de génération (test visuel, jamais importé par l'application).
// Utilisé par scripts/test-fx-visual.mjs : scénarios réels du bus FX, vues de
// référence synthétiques dessinées ici et GLB exporté par three.js.
import { createRoot } from 'react-dom/client'
import { Fragment, useEffect } from 'react'
import * as THREE from 'three'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'
import GenerationFxHost from '../../src/components/generationFx/GenerationFxHost.tsx'
import AuroraMascot, { FX_AGENTS, type FxModule, type MascotState } from '../../src/components/generationFx/mascots.tsx'
import { emitGenerationFx } from '../../src/components/generationFx/fxBus.ts'
import { useAppStore } from '../../src/stores/appStore.ts'
import { recordCompletedRun } from '../../src/services/generationTiming.ts'

const q = new URLSearchParams(location.search)
const mode = q.get('mode') || 'gallery'
const seedHistory = q.get('history') !== '0'

function figure(view: 'face' | 'droite' | 'dos'): string {
  const c = document.createElement('canvas')
  c.width = 360
  c.height = 480
  const g = c.getContext('2d')!
  g.fillStyle = '#f7f7f5'
  g.fillRect(0, 0, 360, 480)
  const skin = '#f1c9a5', shirt = view === 'dos' ? '#2c4a8a' : '#d94b3a', pants = '#2b2f3a', hair = '#3a2414'
  const side = view === 'droite'
  const cx = 180
  g.fillStyle = pants
  if (side) g.fillRect(cx - 22, 300, 44, 150)
  else { g.fillRect(cx - 52, 300, 40, 150); g.fillRect(cx + 12, 300, 40, 150) }
  g.fillStyle = '#111'
  if (side) g.fillRect(cx - 22, 440, 62, 18)
  else { g.fillRect(cx - 56, 440, 46, 18); g.fillRect(cx + 10, 440, 46, 18) }
  g.fillStyle = shirt
  g.beginPath()
  if (side) g.roundRect(cx - 34, 150, 68, 160, 22)
  else g.roundRect(cx - 70, 150, 140, 160, 26)
  g.fill()
  if (!side) {
    g.beginPath(); g.roundRect(cx - 100, 160, 34, 130, 16); g.fill()
    g.beginPath(); g.roundRect(cx + 66, 160, 34, 130, 16); g.fill()
    g.fillStyle = skin
    g.beginPath(); g.arc(cx - 83, 300, 17, 0, 7); g.fill()
    g.beginPath(); g.arc(cx + 83, 300, 17, 0, 7); g.fill()
  } else {
    g.beginPath(); g.roundRect(cx - 16, 160, 32, 130, 16); g.fill()
  }
  g.fillStyle = skin
  g.beginPath(); g.ellipse(cx + (side ? 6 : 0), 100, side ? 44 : 50, 58, 0, 0, 7); g.fill()
  g.fillStyle = hair
  g.beginPath(); g.ellipse(cx - (side ? 10 : 0), 70, side ? 46 : 54, 34, 0, Math.PI, 0); g.fill()
  if (view === 'face') {
    g.fillStyle = '#222'
    g.beginPath(); g.arc(cx - 18, 100, 5, 0, 7); g.arc(cx + 18, 100, 5, 0, 7); g.fill()
    g.fillStyle = '#ffd34d'
    g.fillRect(cx - 20, 200, 40, 40)
  }
  return c.toDataURL('image/png')
}

async function makeGlb(): Promise<string> {
  const scene = new THREE.Scene()
  const add = (geo: THREE.BufferGeometry, color: string, x: number, y: number) => {
    const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color }))
    m.position.set(x, y, 0)
    scene.add(m)
  }
  add(new THREE.CapsuleGeometry(0.42, 0.9, 8, 24), '#d94b3a', 0, 1.35)
  add(new THREE.SphereGeometry(0.34, 32, 24), '#f1c9a5', 0, 2.25)
  add(new THREE.CapsuleGeometry(0.13, 0.75, 6, 16), '#d94b3a', -0.62, 1.4)
  add(new THREE.CapsuleGeometry(0.13, 0.75, 6, 16), '#d94b3a', 0.62, 1.4)
  add(new THREE.CapsuleGeometry(0.16, 0.95, 6, 16), '#2b2f3a', -0.2, 0.5)
  add(new THREE.CapsuleGeometry(0.16, 0.95, 6, 16), '#2b2f3a', 0.2, 0.5)
  const buf = (await new GLTFExporter().parseAsync(scene, { binary: true })) as ArrayBuffer
  return URL.createObjectURL(new Blob([buf], { type: 'model/gltf-binary' }))
}

function Gallery() {
  const states: MascotState[] = ['idle', 'thinking', 'working', 'checking', 'waiting', 'asking', 'success', 'error']
  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: `140px repeat(${states.length}, 104px)`, gap: 6, alignItems: 'center' }}>
        <div />
        {states.map((s) => <div key={s} style={{ fontSize: 11, textAlign: 'center', color: '#8B93A7' }}>{s}</div>)}
        {(Object.keys(FX_AGENTS) as FxModule[]).map((m) => (
          <Fragment key={m}>
            <div style={{ fontSize: 12 }}>
              <b style={{ color: FX_AGENTS[m].accent }}>{FX_AGENTS[m].name}</b><br />
              <span style={{ color: '#8B93A7' }}>{m} · {FX_AGENTS[m].role}</span>
            </div>
            {states.map((s) => <div key={s} style={{ display: 'grid', placeItems: 'center' }}><AuroraMascot module={m} size={96} state={s} /></div>)}
          </Fragment>
        ))}
      </div>
    </div>
  )
}

function Scenario() {
  useEffect(() => {
    const st = useAppStore.getState()
    const mod = (q.get('module') || '3d') as FxModule
    st.setActiveModule(mod as never)
    if (seedHistory) {
      for (let i = 0; i < 4; i++) {
        recordCompletedRun(mod, null, {
          id: `seed-${mod}-${i}`,
          totalMs: (90 + i * 12) * 1000,
          phaseMs: mod === '3d' ? [8e3, 20e3, 30e3, 18e3, 6e3, 6e3] : undefined,
          at: i,
        })
      }
    }
    const run = async () => {
      if (mode === '3d-refs' || mode === '3d-mesh' || mode === '3d-done') {
        emitGenerationFx('3d', { active: true, phase: 'Analyse de la demande 3D…', progress: 0.05 })
        await new Promise((r) => setTimeout(r, 400))
        emitGenerationFx('3d', {
          active: true,
          phase: 'Référence photo — multi-vues prêtes',
          refs: [{ url: figure('face'), role: 'face' }, { url: figure('droite'), role: 'droite' }, { url: figure('dos'), role: 'dos' }],
          logLine: 'photo validée (score 0.83)',
        })
        if (mode !== '3d-refs') {
          await new Promise((r) => setTimeout(r, 1200))
          const glb = await makeGlb()
          emitGenerationFx('3d', { active: true, phaseIndex: 3, phase: 'Matériaux & zones — textures et matériaux par zones…', meshUrl: glb, meshInfo: 'géométrie native posée', logLine: 'texture_run: peinture des zones' })
          if (mode === '3d-done') {
            await new Promise((r) => setTimeout(r, 1500))
            emitGenerationFx('3d', { active: false, resultUrl: glb, resultKind: 'mesh', outcome: 'success' })
          }
        }
      } else if (mode === 'image') {
        emitGenerationFx('image', { active: true, phase: 'Étape 3/5 · Diffusion FLUX — pas 12/28 (43%)', progress: 0.57, logLine: 'Diffusion neuronale FLUX : pas 12/28 (43%)' })
      } else if (mode === 'queued') {
        st.addGenerationJob({
          id: 'job-q', module: 'image', title: 'Portrait', detail: 'En attente sur le PC · position 2 · 1 projet(s) devant',
          progress: 0, phase: 'idle', status: 'queued', services: [], model: null, createdAt: Date.now() - 15000,
          startedAt: null, finishedAt: null, error: null, history: [],
          scheduling: { queue_position: 2, ahead_count: 1, elapsed_seconds: 0, wait_seconds: 40, estimated_duration_seconds: 95, remaining_seconds: null, estimate_sample_count: 4 },
        })
        emitGenerationFx('image', { active: true, phase: 'En attente du PC' })
      } else if (mode === 'business') {
        emitGenerationFx('business', { active: true, phaseIndex: 2 })
        emitGenerationFx('conversation', { active: true, phase: 'Plan', phaseIndex: 1 })
        emitGenerationFx('code', { active: true, phase: 'Génération des fichiers', phaseIndex: 3, progress: 0.4 })
      } else if (mode === 'chat') {
        emitGenerationFx('conversation', { active: true, phase: 'Vérification', phaseIndex: 3, logLine: 'sources croisées' })
        await new Promise((r) => setTimeout(r, 1200))
        emitGenerationFx('conversation', { active: true, phase: 'Brouillon', phaseIndex: 2, revealContent: true })
      } else if (mode === 'flash') {
        emitGenerationFx('cyber', { active: true })
        await new Promise((r) => setTimeout(r, 200))
        emitGenerationFx('cyber', { active: false, outcome: 'success' })
      }
    }
    void run()
  }, [])
  return <GenerationFxHost />
}

// ── Fidélité mesurée sur un vrai modèle : vues rendues → reconstruction de
// production → comparaison à la surface réelle du maillage. ─────────────────
type Pt = [number, number, number]

function nearestDistances(from: Pt[], to: Pt[], cell = 0.03): number[] {
  const grid = new Map<string, Pt[]>()
  const key = (x: number, y: number, z: number) => `${x},${y},${z}`
  for (const p of to) {
    const k = key(Math.floor(p[0] / cell), Math.floor(p[1] / cell), Math.floor(p[2] / cell))
    const list = grid.get(k)
    if (list) list.push(p)
    else grid.set(k, [p])
  }
  return from.map((p) => {
    const cx = Math.floor(p[0] / cell), cy = Math.floor(p[1] / cell), cz = Math.floor(p[2] / cell)
    let best = Infinity
    for (let r = 1; r <= 12 && best === Infinity; r++) {
      for (let dx = -r; dx <= r; dx++) for (let dy = -r; dy <= r; dy++) for (let dz = -r; dz <= r; dz++) {
        const list = grid.get(key(cx + dx, cy + dy, cz + dz))
        if (!list) continue
        for (const q of list) {
          const d = Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2])
          if (d < best) best = d
        }
      }
    }
    return best
  })
}

const quantile = (values: number[], q: number) => {
  const s = values.filter(Number.isFinite).sort((a, b) => a - b)
  return s.length ? s[Math.min(s.length - 1, Math.floor(q * (s.length - 1)))] : NaN
}

async function fidelity() {
  const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js')
  const { MeshSurfaceSampler } = await import('three/examples/jsm/math/MeshSurfaceSampler.js')
  const { buildSilhouetteCloud, foregroundMask } = await import('../../src/components/generationFx/hologramSources.ts')
  const url = q.get('model') || '/aurora-avatar.vrm'
  const gltf = await new GLTFLoader().loadAsync(url)
  const obj = gltf.scene
  const box = new THREE.Box3().setFromObject(obj)
  const size = box.getSize(new THREE.Vector3())
  const center = box.getCenter(new THREE.Vector3())
  const s = 2 / size.y
  obj.scale.setScalar(s)
  obj.position.set(-center.x * s, -box.min.y * s - 1, -center.z * s)
  const scene = new THREE.Scene()
  scene.add(obj)
  scene.add(new THREE.AmbientLight(0xffffff, 1.4))
  const key = new THREE.DirectionalLight(0xffffff, 1.2)
  key.position.set(0, 1, 3)
  scene.add(key)
  obj.updateMatrixWorld(true)
  const PX = 168
  const half = 1.15
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false, preserveDrawingBuffer: true })
  renderer.setPixelRatio(1)
  renderer.setSize(PX, PX)
  renderer.setClearColor(0x000000, 0)
  const cam = new THREE.OrthographicCamera(-half, half, half, -half, 0.01, 20)
  const views: Record<string, { pos: [number, number, number] }> = {
    face: { pos: [0, 0, 5] },
    droite: { pos: [-5, 0, 0] },
    dos: { pos: [0, 0, -5] },
  }
  const shots: Record<string, { img: { width: number; height: number; data: Uint8ClampedArray }; png: string }> = {}
  const canvas = document.createElement('canvas')
  canvas.width = PX
  canvas.height = PX
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!
  for (const [name, v] of Object.entries(views)) {
    cam.position.set(...v.pos)
    cam.lookAt(0, 0, 0)
    renderer.render(scene, cam)
    ctx.clearRect(0, 0, PX, PX)
    ctx.drawImage(renderer.domElement, 0, 0)
    const id = ctx.getImageData(0, 0, PX, PX)
    shots[name] = { img: { width: PX, height: PX, data: id.data }, png: canvas.toDataURL('image/png') }
  }
  const view = (n: string) => {
    const res = foregroundMask(shots[n].img)
    if (!res) throw new Error(`no subject in ${n} view`)
    return { img: shots[n].img, mask: res.mask }
  }
  const front = view('face'), side = view('droite'), back = view('dos')
  // surface réelle (pose de repos), même repère que les rendus
  const truth: Pt[] = []
  const tmp = new THREE.Vector3()
  const meshes: THREE.Mesh[] = []
  obj.traverse((o) => { if ((o as THREE.Mesh).isMesh) meshes.push(o as THREE.Mesh) })
  const totalTris = meshes.reduce((a, m) => a + ((m.geometry.index?.count ?? m.geometry.attributes.position.count) / 3), 0)
  for (const m of meshes) {
    const n = Math.max(50, Math.round((24000 * ((m.geometry.index?.count ?? m.geometry.attributes.position.count) / 3)) / totalTris))
    const sampler = new MeshSurfaceSampler(m).build()
    for (let i = 0; i < n; i++) {
      sampler.sample(tmp)
      tmp.applyMatrix4(m.matrixWorld)
      truth.push([tmp.x, tmp.y, tmp.z])
    }
  }
  const px = (2 * half) / PX
  const evaluate = (label: string, cloud: ReturnType<typeof buildSilhouetteCloud>) => {
    if (!cloud) return { label, error: 'no cloud' }
    // la reconstruction est centrée sur la boîte du masque de face : même centrage pour la vérité
    let minX = Infinity, maxX = -Infinity
    for (const p of truth) { minX = Math.min(minX, p[0]); maxX = Math.max(maxX, p[0]) }
    const shiftX = (minX + maxX) / 2
    const surf: Pt[] = []
    for (let i = 0; i < cloud.count; i++) {
      if (cloud.kinds[i] === 1) continue
      surf.push([cloud.positions[i * 3] + shiftX, cloud.positions[i * 3 + 1], cloud.positions[i * 3 + 2]])
    }
    const toTruth = nearestDistances(surf, truth)
    const toCloud = nearestDistances(truth, surf)
    // silhouettes : projection orthographique du nuage contre les masques rendus
    const iou = (axis: 'front' | 'side', mask: { width: number; data: Uint8Array }, mirror: boolean, pts: Pt[] = surf) => {
      const W = mask.width
      const raw = new Uint8Array(W * W)
      for (const p of pts) {
        const h = axis === 'front' ? p[0] : (mirror ? -p[2] : p[2])
        const u = Math.floor((h + half) / px)
        const v = Math.floor((half - p[1]) / px)
        if (u >= 0 && v >= 0 && u < W && v < W) raw[v * W + u] = 1
      }
      // fermeture morphologique 3×3 : bouche les trous d'échantillonnage sans épaissir le contour
      const morph = (src: Uint8Array, dilate: boolean) => {
        const out = new Uint8Array(W * W)
        for (let y = 0; y < W; y++) for (let x = 0; x < W; x++) {
          let v = dilate ? 0 : 1
          for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
            const xx = x + dx, yy = y + dy
            const inside = xx >= 0 && yy >= 0 && xx < W && yy < W ? src[yy * W + xx] : 0
            if (dilate && inside) v = 1
            if (!dilate && !inside) v = 0
          }
          out[y * W + x] = v
        }
        return out
      }
      const grid = morph(morph(raw, true), false)
      let inter = 0, uni = 0
      for (let i = 0; i < W * W; i++) {
        const a = grid[i], b = mask.data[i]
        if (a && b) inter++
        if (a || b) uni++
      }
      return inter / Math.max(1, uni)
    }
    const pct = (d: number) => Math.round((d / 2) * 10000) / 100
    return {
      label,
      method: cloud.method,
      points: cloud.count,
      chamferCloudToModel: { p50: pct(quantile(toTruth, 0.5)), p90: pct(quantile(toTruth, 0.9)) },
      chamferModelToCloud: { p50: pct(quantile(toCloud, 0.5)), p90: pct(quantile(toCloud, 0.9)) },
      iouFront: Math.round(iou('front', front.mask, false) * 1000) / 1000,
      iouSide: Math.round(Math.max(iou('side', side.mask, false), iou('side', side.mask, true)) * 1000) / 1000,
      depth: Math.round(cloud.depth * 1000) / 1000,
      // plafond de la mesure : les vrais points de surface projetés de la même façon
      iouFrontOfTruthSamples: Math.round(iou('front', front.mask, false, truth) * 1000) / 1000,
      iouSideOfTruthSamples: Math.round(iou('side', side.mask, false, truth) * 1000) / 1000,
      profileSign: cloud.profileSign ?? null,
      profileVote: cloud.profileVote ?? null,
    }
  }
  const relief = evaluate('face seule (relief)', buildSilhouetteCloud(front, { maxPoints: 32000 }))
  const hull = evaluate('face + profil + dos (enveloppe)', buildSilhouetteCloud(front, { side, back, maxPoints: 32000 }))
  const modelDepth = (() => { let a = Infinity, b = -Infinity; for (const p of truth) { a = Math.min(a, p[2]); b = Math.max(b, p[2]) } return Math.round((b - a) * 1000) / 1000 })()
  const { silhouetteSimilarity } = await import('../../src/components/generationFx/hologramSources.ts')
  const result = { model: url, triangles: Math.round(totalTris), truthSamples: truth.length, modelDepth, unit: '% de la hauteur du modèle', relief, hull, sideVsFront: silhouetteSimilarity(front.mask, side.mask) }
  ;(window as unknown as { __fidelity: unknown; __views: unknown }).__fidelity = result
  ;(window as unknown as { __views: unknown }).__views = Object.fromEntries(Object.entries(shots).map(([k, v]) => [k, v.png]))
  renderer.dispose()
  return result
}

function Fidelity() {
  useEffect(() => {
    void fidelity().then((r) => {
      const pre = document.createElement('pre')
      pre.id = 'fidelity'
      pre.textContent = JSON.stringify(r, null, 2)
      document.body.appendChild(pre)
    }).catch((e) => {
      const pre = document.createElement('pre')
      pre.id = 'fidelity-error'
      pre.textContent = String(e)
      document.body.appendChild(pre)
    })
  }, [])
  return null
}

function RealData() {
  // Vraies données du dépôt : référence de personnage détourée et modèle VRM riggé.
  useEffect(() => {
    useAppStore.getState().setActiveModule('3d' as never)
    emitGenerationFx('3d', { active: true, phase: 'Analyse de la demande 3D…' })
    window.setTimeout(() => {
      if (mode === 'real-ref') {
        emitGenerationFx('3d', { active: true, phase: 'Référence photo — référence visuelle retenue', refs: [{ url: q.get('ref') || '/fairy/natsu.png', role: 'face' }], logLine: 'photo validée' })
      } else {
        emitGenerationFx('3d', { active: true, phaseIndex: 3, phase: 'Matériaux & zones — textures et matériaux par zones…', meshUrl: q.get('model') || '/aurora-avatar.vrm', meshInfo: 'modèle réel du dépôt' })
      }
    }, 300)
  }, [])
  return <GenerationFxHost />
}

// ── Mode « live » : l'écran est piloté par de vraies générations
// (scripts/real-gen/run-live.mjs relaie les événements du générateur). ──────
async function imageFromUrl(url: string, maxDim = 168) {
  const blob = await (await fetch(url)).blob()
  const bmp = await createImageBitmap(blob)
  const scale = Math.min(1, maxDim / Math.max(bmp.width, bmp.height))
  const w = Math.max(8, Math.round(bmp.width * scale))
  const h = Math.max(8, Math.round(bmp.height * scale))
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const ctx = c.getContext('2d', { willReadFrequently: true })!
  ctx.drawImage(bmp, 0, 0, w, h)
  const id = ctx.getImageData(0, 0, w, h)
  return { width: w, height: h, data: id.data }
}

/** Accord de l'hologramme avec les vues réellement générées (IoU face et profil). */
async function holoCheck(frontUrl: string, sideUrl: string, backUrl?: string, subjectKind?: string | null) {
  const { buildSilhouetteCloud, foregroundMask, maskBounds, silhouetteSimilarity } = await import('../../src/components/generationFx/hologramSources.ts')
  const load = async (u: string) => {
    const img = await imageFromUrl(u)
    const m = foregroundMask(img)
    return m ? { img, mask: m.mask } : null
  }
  const front = await load(frontUrl)
  const side = await load(sideUrl)
  const back = backUrl ? await load(backUrl) : null
  if (!front) return { error: 'vue de face sans sujet séparable' }
  const fb = maskBounds(front.mask)!
  const Hf = fb.y1 - fb.y0 + 1
  const Wf = fb.x1 - fb.x0 + 1
  const s = 2 / Math.max(Hf, Wf)
  const cx = (fb.x0 + fb.x1) / 2
  const raster = (W: number, H: number, pts: [number, number][]) => {
    const raw = new Uint8Array(W * H)
    for (const [u, v] of pts) {
      const uu = Math.floor(u), vv = Math.floor(v)
      if (uu >= 0 && vv >= 0 && uu < W && vv < H) raw[vv * W + uu] = 1
    }
    const morph = (src: Uint8Array, dilate: boolean) => {
      const out = new Uint8Array(W * H)
      for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
        let v = dilate ? 0 : 1
        for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
          const xx = x + dx, yy = y + dy
          const inside = xx >= 0 && yy >= 0 && xx < W && yy < H ? src[yy * W + xx] : 0
          if (dilate && inside) v = 1
          if (!dilate && !inside) v = 0
        }
        out[y * W + x] = v
      }
      return out
    }
    return morph(morph(raw, true), false)
  }
  const iouOf = (grid: Uint8Array, mask: Uint8Array) => {
    let inter = 0, uni = 0
    for (let i = 0; i < grid.length; i++) {
      if (grid[i] && mask[i]) inter++
      if (grid[i] || mask[i]) uni++
    }
    return Math.round((inter / Math.max(1, uni)) * 1000) / 1000
  }
  const evaluate = (cloud: NonNullable<ReturnType<typeof buildSilhouetteCloud>>) => {
    const frontPts: [number, number][] = []
    const sidePts: [number, number][] = []
    const sideA: [number, number][] = []
    const sb = side ? maskBounds(side.mask) : null
    const Hs = sb ? sb.y1 - sb.y0 + 1 : 1
    const sideWorldPerPx = (Hf * s) / Hs
    const sideCenter = sb ? (sb.x0 + sb.x1) / 2 : 0
    for (let i = 0; i < cloud.count; i++) {
      if (cloud.kinds[i] === 1) continue
      const x = cloud.positions[i * 3], y = cloud.positions[i * 3 + 1], z = cloud.positions[i * 3 + 2]
      const fy = fb.y1 - (y + 1) / s
      frontPts.push([x / s + cx, fy])
      if (sb) {
        const t = Hf > 1 ? (fy - fb.y0) / (Hf - 1) : 0
        const sv = sb.y0 + t * (Hs - 1)
        sidePts.push([sideCenter + z / sideWorldPerPx, sv])
        sideA.push([sideCenter - z / sideWorldPerPx, sv])
      }
    }
    const iouFront = iouOf(raster(front.mask.width, front.mask.height, frontPts), front.mask.data)
    const iouSide = side
      ? Math.max(
        iouOf(raster(side.mask.width, side.mask.height, sidePts), side.mask.data),
        iouOf(raster(side.mask.width, side.mask.height, sideA), side.mask.data),
      )
      : null
    return { method: cloud.method, points: cloud.count, iouFront, iouSide, profileSign: cloud.profileSign ?? null, profileAmbiguous: cloud.profileAmbiguous ?? false, depth: Math.round(cloud.depth * 1000) / 1000 }
  }
  const relief = buildSilhouetteCloud(front, { maxPoints: 32000, subjectKind })
  const hull = side ? buildSilhouetteCloud(front, { side, back, maxPoints: 32000, subjectKind }) : null
  return {
    relief: relief ? evaluate(relief) : null,
    hull: hull ? evaluate(hull) : null,
    sideSeparable: Boolean(side),
    backSeparable: Boolean(back),
    sideVsFront: side ? silhouetteSimilarity(front.mask, side.mask) : null,
  }
}

function Live() {
  useEffect(() => {
    useAppStore.getState().setActiveModule('3d' as never)
    const w = window as unknown as Record<string, unknown>
    w.__fx = (patch: Parameters<typeof emitGenerationFx>[1]) => emitGenerationFx('3d', patch)
    w.__accuracy = async () => (await import('../../src/services/generationTiming.ts')).etaAccuracy('3d')
    w.__holoCheck = holoCheck
    w.__liveReady = true
  }, [])
  return <GenerationFxHost />
}

createRoot(document.getElementById('root')!).render(
  mode === 'gallery' ? <Gallery />
    : mode === 'fidelity' ? <Fidelity />
      : mode === 'real-ref' || mode === 'real-mesh' ? <RealData />
        : mode === 'live' ? <Live />
          : <Scenario />,
)
