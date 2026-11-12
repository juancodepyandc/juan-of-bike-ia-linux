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

createRoot(document.getElementById('root')!).render(mode === 'gallery' ? <Gallery /> : <Scenario />)
