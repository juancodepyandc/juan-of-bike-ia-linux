import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useAppStore } from '../../stores/appStore.ts'
import { useCodeStreamStore } from '../../stores/codeStreamStore.ts'
import type { ModuleId } from '../../types/app.ts'
import { FX_EVENT, FX_PREF_EVENT, generationFxEnabled, type FxAsk, type FxCounters, type FxModule, type FxPatch, type FxRef, fxAnswer, markFxHostMounted } from './fxBus.ts'
import { watchComfyProgress } from './comfyProgress.ts'
import AuroraMascot, { FX_AGENTS } from './mascots.tsx'
import { FX_SCENES, type SceneDraw } from './scenes.ts'

const REVEAL_MS = 2600

type FxEntry = {
  phase?: string
  progress?: number
  startedAt: number
  reveal?: { url: string; kind: 'image' | 'video'; at: number }
  refs?: FxRef[]
  logLines?: string[]
  counters?: FxCounters
  meshUrl?: string
  meshInfo?: string
  ask?: FxAsk | null
}

function updateCounters(prev: FxCounters | undefined, line: string): FxCounters | undefined {
  const l = line.toLowerCase()
  const c: FxCounters = { ...(prev ?? {}) }
  let touched = false
  if (/photo .*(validee|valide)\b/.test(l)) { c.photosValidees = (c.photosValidees ?? 0) + 1; touched = true }
  if (/photo .*(rejetee|ignoree|ecartee)/.test(l)) { c.photosRejetees = (c.photosRejetees ?? 0) + 1; touched = true }
  const tent = l.match(/tentative[^0-9]*(\d+)/)
  if (tent) { c.meshTentatives = Math.max(c.meshTentatives ?? 0, parseInt(tent[1], 10)); touched = true }
  if (/nouvelle passe|regeneration|_r\d\b/.test(l)) { c.meshTentatives = (c.meshTentatives ?? 1) + 1; touched = true }
  if (/trellis|hunyuan|geometrie/.test(l) && (c.meshTentatives ?? 0) === 0) { c.meshTentatives = 1; touched = true }
  return touched ? c : prev
}

const CODE_PHASE_INDEX: Record<string, number> = {
  idle: 0, planning: 1, research: 2, brand: 2, streaming: 3, validation: 4, done: 6, error: 6,
}

const MODULE_PHASE_RANGES: Partial<Record<FxModule, [number, number][]>> = {
  '3d': [
    [0.00, 0.15], // 0: Analyse
    [0.15, 0.40], // 1: Référence photo
    [0.40, 0.70], // 2: Sculpture 3D
    [0.70, 0.85], // 3: Matériaux & zones
    [0.85, 0.95], // 4: Animation
    [0.95, 1.00], // 5: Finalisation
  ],
}

function phaseIndexFor(module: FxModule, entry: FxEntry, now: number): { idx: number; simProg: number } {
  const phases = FX_SCENES[module].phases
  const ranges = MODULE_PHASE_RANGES[module]
  let idx = 0

  if (entry.phase) {
    const needle = entry.phase.toLowerCase()
    const direct = phases.findIndex((p) => needle.includes(p.toLowerCase()) || p.toLowerCase().includes(needle))
    if (direct >= 0) {
      idx = direct
    } else if (module === 'code' && CODE_PHASE_INDEX[needle] !== undefined) {
      idx = CODE_PHASE_INDEX[needle]
    } else if (typeof entry.progress === 'number' && ranges) {
      const p = Math.max(0, Math.min(1, entry.progress))
      const matchedIdx = ranges.findIndex(([start, end]) => p >= start && p < end)
      if (matchedIdx >= 0) idx = matchedIdx
    }
  } else if (typeof entry.progress === 'number' && ranges) {
    const p = Math.max(0, Math.min(1, entry.progress))
    const matchedIdx = ranges.findIndex(([start, end]) => p >= start && p < end)
    if (matchedIdx >= 0) idx = matchedIdx
  } else {
    const elapsed = now - entry.startedAt
    const rawProg = Math.min(0.96, 1 - Math.exp(-elapsed / 45000))
    idx = Math.min(phases.length - 1, Math.floor(rawProg * phases.length))
  }

  idx = Math.max(0, Math.min(phases.length - 1, idx))

  let simProg = 0
  if (ranges && ranges[idx]) {
    const [phaseStart, phaseEnd] = ranges[idx]
    const phaseSpan = phaseEnd - phaseStart
    if (typeof entry.progress === 'number') {
      const p = Math.max(0, Math.min(1, entry.progress))
      if (p >= phaseStart && p <= phaseEnd) {
        simProg = p
      } else if (p <= 1) {
        simProg = phaseStart + p * phaseSpan
      } else {
        simProg = Math.max(phaseStart, Math.min(phaseEnd, p / 100))
      }
    } else {
      const elapsedInPhase = Math.max(0, now - entry.startedAt)
      const subProg = 1 - Math.exp(-elapsedInPhase / 20000)
      simProg = phaseStart + subProg * phaseSpan * 0.96
    }
  } else {
    const phaseSpan = 1 / phases.length
    const phaseStart = idx * phaseSpan
    if (typeof entry.progress === 'number') {
      simProg = Math.max(0, Math.min(1, entry.progress))
    } else {
      const elapsed = now - entry.startedAt
      simProg = Math.min(0.96, phaseStart + (1 - Math.exp(-elapsed / 25000)) * phaseSpan)
    }
  }

  return { idx, simProg: Math.max(0, Math.min(1, simProg)) }
}

function FxCanvas({ module, entry }: { module: FxModule; entry: FxEntry }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const entryRef = useRef(entry)
  entryRef.current = entry
  useEffect(() => {
    const cv = canvasRef.current
    if (!cv) return
    const ctx = cv.getContext('2d')
    if (!ctx) return
    const accent = FX_AGENTS[module].accent
    const draw: SceneDraw = FX_SCENES[module].create()
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let W = 0
    let H = 0
    const size = () => {
      W = cv.clientWidth
      H = cv.clientHeight
      cv.width = Math.max(1, W * dpr)
      cv.height = Math.max(1, H * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    size()
    const ro = new ResizeObserver(size)
    ro.observe(cv)
    let alive = true
    const stars: { x: number; y: number; r: number; p: number; s: number }[] = []
    for (let i = 0; i < 55; i++) stars.push({ x: Math.random(), y: Math.random(), r: Math.random() * 1.2 + 0.3, p: Math.random() * 6.28, s: 0.5 + Math.random() * 1.5 })
    const hex = (a: string) => accent + a
    const frame = (now: number) => {
      if (!alive || !cv.isConnected) { ro.disconnect(); return }
      const e = entryRef.current
      const { simProg } = phaseIndexFor(module, e, performance.now() + e.startedAt - e.startedAt + Date.now() - Date.now())
      ctx.clearRect(0, 0, W, H)
      const g1 = ctx.createRadialGradient(W * 0.25, H * 0.2, 0, W * 0.25, H * 0.2, W * 0.6)
      g1.addColorStop(0, hex('16'))
      g1.addColorStop(1, hex('00'))
      ctx.fillStyle = g1
      ctx.fillRect(0, 0, W, H)
      const g2 = ctx.createRadialGradient(W * 0.8, H * 0.75, 0, W * 0.8, H * 0.75, W * 0.55)
      g2.addColorStop(0, hex('0E'))
      g2.addColorStop(1, hex('00'))
      ctx.fillStyle = g2
      ctx.fillRect(0, 0, W, H)
      for (const st of stars) {
        ctx.globalAlpha = 0.22 + 0.5 * (0.5 + 0.5 * Math.sin(now * 0.001 * st.s + st.p))
        ctx.fillStyle = '#CFE3FF'
        ctx.beginPath()
        ctx.arc(st.x * W, st.y * H, st.r, 0, 6.2832)
        ctx.fill()
      }
      ctx.globalAlpha = 1
      try { draw(ctx, W, H, now, simProg, accent) } catch { /* scène isolée */ }
      const vg = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.35, W / 2, H / 2, Math.max(W, H) * 0.75)
      vg.addColorStop(0, 'rgba(0,0,0,0)')
      vg.addColorStop(1, 'rgba(0,0,0,.4)')
      ctx.fillStyle = vg
      ctx.fillRect(0, 0, W, H)
      requestAnimationFrame(frame)
    }
    const raf = requestAnimationFrame(frame)
    return () => { alive = false; cancelAnimationFrame(raf); ro.disconnect() }
  }, [module])
  return <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
}

const ROLE_LABELS: Record<string, string> = {
  face: 'FACE', trois_quarts: '3/4', dos: 'DOS', gauche: 'GAUCHE', droite: 'DROITE',
  haut: 'HAUT', bas: 'BAS', extra: 'VUE +', inconnu: 'VUE',
}

function RefsPanel({ refs, accent }: { refs: FxRef[]; accent: string }) {
  return (
    <div style={{
      position: 'absolute', left: 48, top: 72, bottom: 170, width: 200,
      display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto',
      pointerEvents: 'none',
    }}>
      <span style={{ fontSize: 10, letterSpacing: '.28em', color: '#8B93A7', fontFamily: "'Cascadia Code',Consolas,monospace" }}>
        RÉFÉRENCES{refs.length > 1 ? ` · MULTI-VUES (${refs.length})` : ''}
      </span>
      {refs.map((r, i) => (
        <div key={`${r.url}-${i}`} style={{ position: 'relative', borderRadius: 12, overflow: 'hidden', border: `1px solid ${accent}44`, background: 'rgba(255,255,255,.03)' }}>
          <img src={r.url} alt={r.role} style={{ width: '100%', display: 'block', objectFit: 'contain', maxHeight: 150 }} />
          <span style={{
            position: 'absolute', left: 8, top: 8, fontSize: 10, fontWeight: 700,
            padding: '3px 8px', borderRadius: 999, letterSpacing: '.14em',
            background: 'rgba(4,6,11,.8)', border: `1px solid ${accent}88`, color: '#fff',
            fontFamily: "'Cascadia Code',Consolas,monospace",
          }}>{ROLE_LABELS[r.role] ?? r.role.toUpperCase()}</span>
        </div>
      ))}
    </div>
  )
}

function MeshForming({ url, accent }: { url: string; accent: string }) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    let disposed = false
    let raf = 0
    let renderer: import('three').WebGLRenderer | null = null
    void (async () => {
      const THREE = await import('three')
      const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js')
      if (disposed || !hostRef.current) return
      const W = host.clientWidth || 600
      const H = host.clientHeight || 420
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
      renderer.setSize(W, H)
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
      host.appendChild(renderer.domElement)
      const scene = new THREE.Scene()
      const camera = new THREE.PerspectiveCamera(45, W / H, 0.001, 5000)
      const group = new THREE.Group()
      scene.add(group)
      new GLTFLoader().load(url, (g) => {
        if (disposed) return
        const wire = new THREE.MeshBasicMaterial({ color: new THREE.Color(accent), wireframe: true, transparent: true, opacity: 0.55 })
        g.scene.traverse((o) => {
          const mesh = o as import('three').Mesh
          if (mesh.isMesh) mesh.material = wire
        })
        group.add(g.scene)
        const box = new THREE.Box3().setFromObject(g.scene)
        const size = box.getSize(new THREE.Vector3()).length() || 1
        const center = box.getCenter(new THREE.Vector3())
        g.scene.position.sub(center)
        camera.position.set(size * 0.55, size * 0.3, size * 0.55)
        camera.lookAt(0, 0, 0)
      }, undefined, () => { /* fichier encore en cours d'ecriture — retentera au prochain montage */ })
      const tick = () => {
        if (disposed || !renderer) return
        group.rotation.y += 0.004
        renderer.render(scene, camera)
        raf = requestAnimationFrame(tick)
      }
      tick()
    })()
    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      if (renderer) {
        renderer.dispose()
        renderer.domElement.remove()
      }
    }
  }, [url, accent])
  return <div ref={hostRef} style={{ position: 'absolute', inset: 0 }} />
}

function CenterStage({ entry, accent }: { entry: FxEntry; accent: string }) {
  const c = entry.counters ?? {}
  const started = Boolean(entry.logLines?.length)
  const silhouette = entry.refs?.[0]?.url
  const feed = (entry.logLines ?? []).slice(-7)
  const lastReject = [...(entry.logLines ?? [])].reverse().find((l) => /rejet|ecart|ignor/i.test(l))
  return (
    <div style={{
      position: 'absolute', left: 280, right: 200, top: 60, bottom: 170,
      display: 'flex', flexDirection: 'column', pointerEvents: 'none',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 10, letterSpacing: '.28em', color: '#8B93A7', fontFamily: "'Cascadia Code',Consolas,monospace" }}>
          {entry.meshUrl ? 'FABRICATION — GÉOMÉTRIE RÉELLE' : started ? 'LA FORME SE PRÉPARE' : 'EN ATTENTE'}
        </span>
        <span style={{ display: 'flex', gap: 8 }}>
          {[
            { lab: 'photos ✓', val: c.photosValidees ?? 0, col: '#4ADE80' },
            { lab: 'photos ✗', val: c.photosRejetees ?? 0, col: '#F87171' },
            // "1 mesh" laissait croire qu'un GLB existait alors que ce compteur
            // ne compte que les ESSAIS (deduit des lignes de log). Le GLB n'est
            // affiche que quand le fichier est reellement apparu sur le disque.
            { lab: 'essai mesh', val: c.meshTentatives ?? 0, col: accent },
            { lab: 'GLB', val: entry.meshUrl ? 1 : 0, col: entry.meshUrl ? '#4ADE80' : '#8B93A7' },
          ].map((k) => (
            <span key={k.lab} style={{
              fontSize: 10, padding: '4px 10px', borderRadius: 999,
              border: `1px solid ${k.col}55`, color: '#E6EAF5', background: 'rgba(4,6,11,.6)',
              fontFamily: "'Cascadia Code',Consolas,monospace",
            }}><b style={{ color: k.col, fontSize: 12 }}>{k.val}</b> {k.lab}</span>
          ))}
        </span>
      </div>
      <div style={{ position: 'relative', flex: 1 }}>
        {entry.meshUrl ? (
          <MeshForming url={entry.meshUrl} accent={accent} />
        ) : silhouette && started ? (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
            <img src={silhouette} alt="silhouette" style={{
              maxWidth: '72%', maxHeight: '92%', objectFit: 'contain',
              filter: 'brightness(0.18) sepia(1) hue-rotate(190deg) saturate(3.2) opacity(0.8)',
            }} />
            <div style={{
              position: 'absolute', left: '12%', right: '12%', height: 2,
              background: `linear-gradient(90deg, transparent, ${accent}, transparent)`,
              boxShadow: `0 0 18px ${accent}`, animation: 'aurora-fx-scan 2.8s ease-in-out infinite',
            }} />
          </div>
        ) : (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            color: accent, fontSize: 12, letterSpacing: '.2em',
            fontFamily: "'Cascadia Code',Consolas,monospace",
            textShadow: `0 0 12px ${accent}66`,
          }}>
            <span style={{ animation: 'aurora-fx-wait 2s ease-in-out infinite' }}>SCULPTURE 3D EN DIRECT · FORMATION DU MAILLAGE…</span>
          </div>
        )}
      </div>
      {lastReject && (
        <div style={{
          marginTop: 6, fontSize: 10, color: '#F87171', whiteSpace: 'nowrap', overflow: 'hidden',
          textOverflow: 'ellipsis', fontFamily: "'Cascadia Code',Consolas,monospace",
        }}>dernier rejet : {lastReject.replace(/^PROGRESS:[a-z_]*:?/i, '')}</div>
      )}
      <div style={{
        marginTop: 6, height: 128, overflow: 'hidden', borderRadius: 10,
        border: '1px solid rgba(255,255,255,.07)', background: 'rgba(0,0,0,.32)',
        padding: '8px 12px', fontFamily: "'Cascadia Code',Consolas,monospace", fontSize: 10.5,
        lineHeight: 1.65, color: '#9AA5BC', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
      }}>
        {feed.length === 0 && <div style={{ color: '#5A6377' }}>le detail de chaque decision du pipeline s'affichera ici…</div>}
        {feed.map((l, i) => (
          <div key={i} style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: i === feed.length - 1 ? '#E6EAF5' : undefined }}>
            <span style={{ color: accent }}>›</span> {l.replace(/^PROGRESS:[a-z_]*:?/i, '')}
          </div>
        ))}
      </div>
    </div>
  )
}

function FullOverlay({ module, entry }: { module: FxModule; entry: FxEntry }) {
  const scene = FX_SCENES[module]
  const agent = FX_AGENTS[module]
  const [, force] = useState(0)
  const [page, setPage] = useState<'scene' | 'construction'>(module === '3d' ? 'construction' : 'scene')
  useEffect(() => {
    const iv = window.setInterval(() => force((n) => n + 1), 400)
    return () => window.clearInterval(iv)
  }, [])
  const now = Date.now()
  const { idx, simProg } = phaseIndexFor(module, entry, now)
  const sayIdx = Math.min(scene.says.length - 1, Math.floor(simProg * scene.says.length))
  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        width: '100%', height: '100%',
        zIndex: 99999, pointerEvents: 'auto',
        overflow: 'hidden',
        background: '#04060b',
        boxShadow: `inset 0 0 120px ${agent.accent}18`,
        animation: 'aurora-fx-in .5s cubic-bezier(.22,1,.36,1)',
      }}
    >
      {/* 31/07 (retour Juan): le bouton d'arret etait SOUS cet ecran opaque —
          invisible des que la generation tourne. Il vit desormais ICI, sur la
          couche du dessus, toujours cliquable. */}
      <button
        type="button"
        onClick={() => window.dispatchEvent(new CustomEvent('aurora-fx-stop', { detail: { module } }))}
        style={{
          position: 'absolute', top: 14, right: 16, zIndex: 5,
          pointerEvents: 'auto', cursor: 'pointer',
          padding: '7px 14px', borderRadius: 999,
          border: '1px solid rgba(248,113,113,.5)', background: 'rgba(127,29,29,.35)',
          color: '#fecaca', fontSize: 12, fontWeight: 650,
          fontFamily: "'Inter','Segoe UI',system-ui,sans-serif",
        }}
      >
        ■ Arreter la generation
      </button>
      <FxCanvas module={module} entry={entry} />
      {!entry.reveal && entry.refs && entry.refs.length > 0 && (
        <RefsPanel refs={entry.refs} accent={agent.accent} />
      )}
      {!entry.reveal && module === '3d' && page === 'construction' && (
        <CenterStage entry={entry} accent={agent.accent} />
      )}
      {!entry.reveal && module === '3d' && (
        <button
          type="button"
          onClick={() => setPage((p) => (p === 'scene' ? 'construction' : 'scene'))}
          title={page === 'scene' ? 'Voir la fabrication réelle' : 'Revenir à la scène animée'}
          style={{
            position: 'absolute', right: 48, top: '46%', zIndex: 2,
            width: 52, height: 52, borderRadius: '50%', cursor: 'pointer',
            border: `1px solid ${agent.accent}77`, background: 'rgba(8,12,22,.85)',
            color: agent.accent, fontSize: 20, fontWeight: 700,
            boxShadow: `0 0 24px ${agent.accent}33`, pointerEvents: 'auto',
          }}
        >{page === 'scene' ? '❯' : '❮'}</button>
      )}
      {!entry.reveal && entry.ask && (
        <FxAskPanel module={module} ask={entry.ask} accent={agent.accent} />
      )}
      {entry.reveal && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(4,6,11,.55)', backdropFilter: 'blur(6px)', animation: 'aurora-fx-reveal-bg .4s ease',
        }}>
          {entry.reveal.kind === 'video' ? (
            <video
              src={entry.reveal.url}
              muted
              autoPlay
              playsInline
              style={{
                maxWidth: '78%', maxHeight: '78%', borderRadius: 14,
                border: `1px solid ${agent.accent}88`, boxShadow: `0 20px 70px rgba(0,0,0,.6), 0 0 40px ${agent.accent}44`,
                animation: 'aurora-fx-reveal 1.1s cubic-bezier(.22,1,.36,1)',
              }}
            />
          ) : (
            <img
              src={entry.reveal.url}
              alt="Résultat généré"
              style={{
                maxWidth: '78%', maxHeight: '78%', borderRadius: 14, objectFit: 'contain',
                border: `1px solid ${agent.accent}88`, boxShadow: `0 20px 70px rgba(0,0,0,.6), 0 0 40px ${agent.accent}44`,
                animation: 'aurora-fx-reveal 1.1s cubic-bezier(.22,1,.36,1)',
              }}
            />
          )}
          <span style={{
            position: 'absolute', bottom: 84, fontFamily: "'Cascadia Code',Consolas,monospace",
            fontSize: 12, color: '#4ADE80', letterSpacing: '.2em',
          }}>✓ TERMINÉ</span>
        </div>
      )}
      {!entry.reveal && (
      <div style={{ position: 'absolute', right: 48, bottom: 150, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, animation: 'aurora-fx-float 3.6s ease-in-out infinite' }}>
        <AuroraMascot module={module} size={96} state="working" />
        <span style={{
          fontSize: 11, color: '#E6EAF5', padding: '7px 13px', borderRadius: 12, borderTopLeftRadius: 3,
          background: 'rgba(255,255,255,.07)', border: '1px solid rgba(255,255,255,.15)', maxWidth: 190, textAlign: 'center',
          fontFamily: "'Inter','Segoe UI',system-ui,sans-serif",
        }}>{scene.says[sayIdx]}</span>
      </div>
      )}
      <div style={{ position: 'absolute', left: 48, right: 48, bottom: 28, fontFamily: "'Cascadia Code',Consolas,monospace", pointerEvents: 'none' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
          <span style={{ fontSize: 10, letterSpacing: '.32em', color: '#8B93A7' }}>
            {module.toUpperCase()} · {agent.name.toUpperCase()} TRAVAILLE
          </span>
          <span style={{ fontSize: 22, fontWeight: 700, color: agent.accent, textShadow: `0 0 18px ${agent.accent}88` }}>
            {Math.floor(simProg * 100)}%
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${scene.phases.length}, minmax(0, 1fr))`, gap: 6, marginBottom: 10 }}>
          {scene.phases.map((p, i) => {
            const isDone = i < idx
            const isCurrent = i === idx
            let phaseFill = 0
            if (isDone) phaseFill = 100
            else if (isCurrent) {
              const ranges = MODULE_PHASE_RANGES[module]
              if (ranges && ranges[i]) {
                const [start, end] = ranges[i]
                phaseFill = Math.max(5, Math.min(100, Math.round(((simProg - start) / (end - start)) * 100)))
              } else {
                phaseFill = Math.max(10, Math.min(100, Math.round((simProg * scene.phases.length - i) * 100)))
              }
            }
            return (
              <div
                key={p}
                style={{
                  display: 'flex', flexDirection: 'column', gap: 3,
                  padding: '5px 8px', borderRadius: 8,
                  border: `1px solid ${isCurrent ? agent.accent : isDone ? 'rgba(74,222,128,.35)' : 'rgba(255,255,255,.08)'}`,
                  background: isCurrent ? `${agent.accent}18` : isDone ? 'rgba(74,222,128,.06)' : 'rgba(255,255,255,.02)',
                  boxShadow: isCurrent ? `0 0 16px ${agent.accent}44` : 'none',
                  transition: 'all .3s ease',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{
                    fontSize: 9.5, fontWeight: isCurrent ? 700 : 500,
                    color: isDone ? '#4ADE80' : isCurrent ? '#fff' : '#6B7280',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>
                    {isDone ? '✓ ' : ''}{p}
                  </span>
                  <span style={{ fontSize: 9, color: isDone ? '#4ADE80' : isCurrent ? agent.accent : '#4B5563', fontWeight: 600 }}>
                    {isDone ? '100%' : isCurrent ? `${phaseFill}%` : '0%'}
                  </span>
                </div>
                <div style={{ height: 3, borderRadius: 2, background: 'rgba(255,255,255,.08)', overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', width: `${phaseFill}%`,
                    background: isDone ? '#4ADE80' : `linear-gradient(90deg, ${agent.accent}, #fff)`,
                    boxShadow: isCurrent ? `0 0 8px ${agent.accent}` : 'none',
                    transition: 'width .25s ease',
                  }} />
                </div>
              </div>
            )
          })}
        </div>
        {entry.phase && (
          <div style={{ fontSize: 11, color: '#B7C0D4', marginBottom: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            <span style={{ color: agent.accent }}>›</span> {entry.phase}
          </div>
        )}
        <div style={{ height: 4, borderRadius: 4, background: 'rgba(255,255,255,.08)', overflow: 'hidden' }}>
          <i style={{
            display: 'block', height: '100%', width: `${simProg * 100}%`,
            background: `linear-gradient(90deg, ${agent.accent}, #fff8)`,
            boxShadow: `0 0 14px ${agent.accent}`,
            transition: 'width .35s linear',
          }} />
        </div>
      </div>
    </div>
  )
}

function MiniPill({ module, entry, onClick }: { module: FxModule; entry: FxEntry; onClick: () => void }) {
  const agent = FX_AGENTS[module]
  const { simProg } = phaseIndexFor(module, entry, Date.now())
  return (
    <button
      type="button"
      onClick={onClick}
      title={`${agent.name} travaille sur ${module} — cliquer pour voir`}
      style={{
        display: 'flex', alignItems: 'center', gap: 9, padding: '7px 14px 7px 8px', borderRadius: 999,
        border: `1px solid ${agent.accent}66`, background: 'rgba(8,12,22,.92)', cursor: 'pointer',
        boxShadow: `0 10px 30px rgba(0,0,0,.5), 0 0 18px ${agent.accent}22`,
        color: '#E6EAF5', fontFamily: "'Inter','Segoe UI',system-ui,sans-serif",
      }}
    >
      <AuroraMascot module={module} size={30} state="working" />
      <span style={{ fontSize: 12, fontWeight: 650 }}>{agent.name}</span>
      {entry.ask ? (
        // 31/07 (audit): une question du pipeline restait INVISIBLE quand
        // l'utilisateur etait sur un autre module — la pastille affichait un
        // % serein pendant que tout attendait une reponse (jusqu'a 2 h).
        <span style={{ fontSize: 11, fontWeight: 700, color: '#ffb44d',
                       animation: 'pulse 1.2s ease-in-out infinite' }}>
          QUESTION EN ATTENTE — cliquer
        </span>
      ) : (
        <span style={{ fontSize: 11, fontFamily: "'Cascadia Code',Consolas,monospace", color: agent.accent }}>
          {Math.floor(simProg * 100)}%
        </span>
      )}
    </button>
  )
}


// La question est une PARTIE de l'ecran de generation — pas une modale
// empilee par-dessus. Fond PLEIN (aucune transparence sous le texte),
// lisibilite d'abord; la generation reste visible autour, en pause implicite.
function FxAskPanel({ module, ask, accent }: { module: FxModule; ask: FxAsk; accent: string }) {
  const [text, setText] = useState('')
  const [choix, setChoix] = useState<number | null>(null)
  // 31/07 (demande Juan): sur un LOT, pouvoir trier IMAGE PAR IMAGE (garder /
  // jeter) au lieu du tout-ou-rien oui/non.
  const [jetees, setJetees] = useState<Set<number>>(new Set())
  const confirm = ask.kind === 'confirm_images'
  const pick = ask.kind === 'pick_image'
  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 3, display: 'grid',
      placeItems: 'center', pointerEvents: 'auto',
      background: 'rgba(4,6,11,.95)',
    }}>
      <div style={{
        width: 'min(820px, 94vw)', maxHeight: '88vh', overflowY: 'auto',
        background: '#0B0F16', borderRadius: 20, padding: '26px 30px',
        border: `1px solid ${accent}66`,
        boxShadow: `0 30px 90px rgba(0,0,0,.65), 0 0 40px ${accent}22`,
      }}>
        <div style={{
          fontSize: 11, letterSpacing: '.3em', color: accent, fontWeight: 700,
          fontFamily: "'Cascadia Code',Consolas,monospace", marginBottom: 12,
        }}>
          {ask.categoryLabel?.toUpperCase() ?? (confirm ? 'VALIDATION — VOTRE AVIS EST ATTENDU' : 'QUESTION — LA GÉNÉRATION ATTEND VOTRE RÉPONSE')}
        </div>
        <div style={{ fontSize: 20, lineHeight: 1.5, color: '#EEF2FB', fontWeight: 600 }}>
          {ask.question}
        </div>
        {(confirm || pick) && ask.images && ask.images.length > 0 && (
          <div style={{
            marginTop: 18, display: 'grid', gap: 12,
            gridTemplateColumns: ask.images.length > 1 ? 'repeat(auto-fit, minmax(180px, 1fr))' : '1fr',
          }}>
            {ask.images.map((u, i) => (
              <div key={i} style={{ position: 'relative' }}>
                <img src={u} alt={`Proposition ${i + 1}`}
                  onClick={pick ? () => setChoix(i)
                    : confirm && ask.allowPickEach && i > 0
                      ? () => setJetees((prev) => { const n = new Set(prev); if (n.has(i)) n.delete(i); else n.add(i); return n })
                      : undefined}
                  style={{
                    width: '100%', maxHeight: '38vh', objectFit: 'contain',
                    borderRadius: 12, background: '#091116',
                    cursor: pick || (confirm && ask.allowPickEach && i > 0) ? 'pointer' : 'default',
                    opacity: jetees.has(i) ? 0.35 : 1,
                    border: pick && choix === i
                      ? `3px solid ${accent}`
                      : jetees.has(i)
                        ? '3px solid rgba(248,113,113,.8)'
                        : '1px solid rgba(255,255,255,.08)',
                    boxShadow: pick && choix === i ? `0 0 24px ${accent}55` : 'none',
                  }} />
                {confirm && ask.allowPickEach && i > 0 && (
                  <span style={{ position: 'absolute', top: 6, left: 8, fontSize: 11, fontWeight: 700,
                                 color: jetees.has(i) ? '#FCA5A5' : '#86EFAC' }}>
                    {jetees.has(i) ? '✕ jetee — cliquer pour garder' : '✓ gardee — cliquer pour jeter'}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
        {!confirm && ask.options && ask.options.length > 0 && (
          <div style={{ marginTop: 18, display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {ask.options.map((opt) => (
              <button key={opt} type="button"
                onClick={() => fxAnswer(module, ask.id, opt)}
                style={{
                  padding: '12px 18px', borderRadius: 12, cursor: 'pointer',
                  border: `1px solid ${accent}55`, background: `${accent}14`,
                  color: '#EDF2FC', fontSize: 15, fontWeight: 600,
                }}>{opt}</button>
            ))}
          </div>
        )}
        {confirm && ask.allowPhoto && (
          <label style={{
            marginTop: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: 8, padding: '12px', borderRadius: 12, cursor: 'pointer',
            border: `1px dashed ${accent}66`, background: `${accent}0d`,
            color: '#BFDBFE', fontSize: 14, fontWeight: 600,
          }}>
            Joindre la 2e photo (vraie vue sous un autre angle)
            <input type="file" accept="image/*,.png,.jpg,.jpeg,.webp,.avif,.heic,.heif" style={{ display: 'none' }}
              onChange={async (e) => {
                const f = e.target.files?.[0]
                if (!f) return
                const fd = new FormData()
                fd.append('file', f, f.name)
                try {
                  const base = window.location.port === '1420' ? 'http://127.0.0.1:3001' : ''
                  const r = await fetch(`${base}/api/upload`, { method: 'POST', body: fd })
                  const d = await r.json()
                  if (d?.path) fxAnswer(module, ask.id, { accepted: true, verdict: 'photo', photo: d.path, reason: '' })
                } catch { /* l'utilisateur peut cliquer Accepter pour mono-vue */ }
                e.currentTarget.value = ''
              }} />
          </label>
        )}
        {(confirm || ask.allowText) && (
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2}
            placeholder={confirm ? 'Optionnel (si vous refusez) : ce qui ne va pas' : 'Votre réponse...'}
            style={{
              marginTop: 16, width: '100%', borderRadius: 12, padding: 12,
              background: '#101623', color: '#EDF2FC', fontSize: 15,
              border: '1px solid rgba(255,255,255,.14)', resize: 'vertical',
            }} />
        )}
        <div style={{ marginTop: 18, display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
          {pick ? (
            <button type="button" disabled={choix === null}
              onClick={() => choix !== null && fxAnswer(module, ask.id, { choix })}
              style={{
                padding: '12px 26px', borderRadius: 12,
                cursor: choix === null ? 'not-allowed' : 'pointer',
                opacity: choix === null ? 0.45 : 1,
                border: `1px solid ${accent}88`, background: `${accent}22`,
                color: '#EDF2FC', fontSize: 15, fontWeight: 700,
              }}>Valider la proposition {choix !== null ? choix + 1 : ''}</button>
          ) : confirm ? (
            <>
              <button type="button"
                onClick={() => fxAnswer(module, ask.id, { accepted: false, reason: text.trim(), verdict: 'non' })}
                style={{
                  padding: '12px 20px', borderRadius: 12, cursor: 'pointer',
                  border: '1px solid rgba(248,113,113,.6)', background: 'rgba(248,113,113,.14)',
                  color: '#FCA5A5', fontSize: 15, fontWeight: 700,
                }}>✕ Non — supprimer</button>
              {ask.allowMaybe && (
                <button type="button"
                  onClick={() => fxAnswer(module, ask.id, { accepted: false, reason: text.trim(), verdict: 'peutetre' })}
                  style={{
                    padding: '12px 20px', borderRadius: 12, cursor: 'pointer',
                    border: '1px solid rgba(251,191,36,.55)', background: 'rgba(251,191,36,.12)',
                    color: '#FCD34D', fontSize: 15, fontWeight: 700,
                  }}>~ Peut-être — garder et proposer autre chose</button>
              )}
              {ask.allowPickEach && jetees.size > 0 && (
                <button type="button"
                  onClick={() => fxAnswer(module, ask.id, { accepted: true, reason: text.trim(), verdict: 'selection', jetees: Array.from(jetees) })}
                  style={{
                    padding: '12px 20px', borderRadius: 12, cursor: 'pointer',
                    border: '1px solid rgba(96,165,250,.6)', background: 'rgba(96,165,250,.14)',
                    color: '#93C5FD', fontSize: 15, fontWeight: 700,
                  }}>Garder ma selection ({(ask.images?.length || 1) - 1 - jetees.size} vue(s))</button>
              )}
              <button type="button"
                onClick={() => fxAnswer(module, ask.id, { accepted: true, reason: '', verdict: 'oui' })}
                style={{
                  padding: '12px 24px', borderRadius: 12, cursor: 'pointer',
                  border: '1px solid rgba(74,222,128,.6)', background: 'rgba(74,222,128,.16)',
                  color: '#86EFAC', fontSize: 15, fontWeight: 700,
                }}>✓ Accepter</button>
            </>
          ) : (
            <>
              <button type="button" onClick={() => fxAnswer(module, ask.id, null)}
                style={{
                  padding: '12px 18px', borderRadius: 12, cursor: 'pointer',
                  border: '1px solid rgba(255,255,255,.18)', background: 'transparent',
                  color: '#9AA3B8', fontSize: 14,
                }}>Passer</button>
              {ask.allowText && (
                <button type="button"
                  onClick={() => fxAnswer(module, ask.id, text.trim() || null)}
                  style={{
                    padding: '12px 24px', borderRadius: 12, cursor: 'pointer',
                    border: `1px solid ${accent}88`, background: `${accent}22`,
                    color: '#EDF2FC', fontSize: 15, fontWeight: 700,
                  }}>Envoyer</button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function GenerationFxHost() {
  const [entries, setEntries] = useState<Partial<Record<FxModule, FxEntry>>>({})
  useEffect(() => {
    markFxHostMounted(true)
    return () => markFxHostMounted(false)
  }, [])
  const [enabled, setEnabled] = useState(generationFxEnabled)
  const activeModule = useAppStore((s) => s.activeModule)
  const setActiveModule = useAppStore((s) => s.setActiveModule)

  const apply = useCallback((module: FxModule, patch: FxPatch) => {
    setEntries((prev) => {
      const next = { ...prev }
      if (!patch.active) {
        if (!(module in next) && !patch.resultUrl) return prev
        if (patch.resultUrl) {
          const cur0 = next[module] ?? { startedAt: Date.now() - 1 }
          next[module] = {
            ...cur0,
            progress: 1,
            reveal: { url: patch.resultUrl, kind: patch.resultKind ?? 'image', at: Date.now() },
          }
          window.setTimeout(() => {
            setEntries((p2) => {
              if (!p2[module]?.reveal) return p2
              const n2 = { ...p2 }
              delete n2[module]
              return n2
            })
          }, REVEAL_MS)
          return next
        }
        delete next[module]
        return next
      }
      const cur = next[module]
      const logLines = patch.logLine
        ? [...(cur?.logLines ?? []), patch.logLine].slice(-300)
        : cur?.logLines
      next[module] = {
        startedAt: cur?.startedAt ?? Date.now(),
        phase: patch.phase ?? cur?.phase,
        progress: patch.progress ?? cur?.progress,
        refs: patch.refs ?? cur?.refs,
        logLines,
        counters: patch.logLine ? updateCounters(cur?.counters, patch.logLine) : cur?.counters,
        meshUrl: patch.meshUrl ?? cur?.meshUrl,
        meshInfo: patch.meshInfo ?? cur?.meshInfo,
        // undefined = inchange; null = question retiree (repondue)
        ask: patch.ask === undefined ? cur?.ask : patch.ask,
      }
      return next
    })
  }, [])

  useEffect(() => {
    const onFx = (ev: Event) => {
      const d = (ev as CustomEvent<{ module: FxModule } & FxPatch>).detail
      if (!d?.module) return
      apply(d.module, d)
    }
    const onPref = () => setEnabled(generationFxEnabled())
    window.addEventListener(FX_EVENT, onFx)
    window.addEventListener(FX_PREF_EVENT, onPref)
    return () => {
      window.removeEventListener(FX_EVENT, onFx)
      window.removeEventListener(FX_PREF_EVENT, onPref)
    }
  }, [apply])

  const comfyActive = Boolean(entries.image && !entries.image.reveal) || Boolean(entries.drawing && !entries.drawing.reveal)
  useEffect(() => {
    if (!comfyActive) return
    const stop = watchComfyProgress((frac, label) => {
      setEntries((prev) => {
        const next = { ...prev }
        let touched = false
        for (const m of ['image', 'drawing'] as FxModule[]) {
          if (next[m] && !next[m]!.reveal) {
            next[m] = { ...next[m]!, progress: frac, phase: label ?? next[m]!.phase }
            touched = true
          }
        }
        return touched ? next : prev
      })
    })
    return stop
  }, [comfyActive])

  const codeStreaming = useCodeStreamStore((s) => s.streaming)
  const codePhase = useCodeStreamStore((s) => s.phase)
  const codeMessage = useCodeStreamStore((s) => s.phaseMessage)
  const codeProgress = useCodeStreamStore((s) => s.progressPct)
  useEffect(() => {
    const running = codeStreaming || (codePhase !== 'idle' && codePhase !== 'done' && codePhase !== 'error')
    if (running) {
      apply('code', {
        active: true,
        phase: codeMessage || codePhase,
        progress: typeof codeProgress === 'number' && codeProgress > 0 ? codeProgress / 100 : undefined,
      })
    } else {
      apply('code', { active: false })
    }
  }, [codeStreaming, codePhase, codeMessage, codeProgress, apply])

  const activeFx = useMemo(() => Object.entries(entries) as [FxModule, FxEntry][], [entries])
  if (!enabled || activeFx.length === 0) return null

  const fxForCurrent = activeFx.find(([m]) => (m as string) === (activeModule as string))
  const others = activeFx.filter(([m]) => (m as string) !== (activeModule as string))

  return (
    <>
      <style>{`
        @keyframes aurora-fx-in { from { opacity: 0; transform: translate(-50%, -46%) scale(.97) } to { opacity: 1; transform: translate(-50%, -50%) scale(1) } }
        @keyframes aurora-fx-float { 0%,100% { transform: translateY(0) } 50% { transform: translateY(-7px) } }
        @keyframes aurora-fx-reveal { from { opacity: 0; clip-path: inset(0 100% 0 0); transform: scale(.96) } to { opacity: 1; clip-path: inset(0 0 0 0); transform: scale(1) } }
        @keyframes aurora-fx-reveal-bg { from { opacity: 0 } to { opacity: 1 } }
        @keyframes aurora-fx-scan { 0%,100% { top: 6% } 50% { top: 92% } }
        @keyframes aurora-fx-wait { 0%,100% { opacity: .35 } 50% { opacity: 1 } }
      `}</style>
      {fxForCurrent && <FullOverlay module={fxForCurrent[0]} entry={fxForCurrent[1]} />}
      {others.length > 0 && (
        <div style={{ position: 'fixed', right: 18, bottom: 18, zIndex: 119, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
          {others.map(([m, e]) => (
            <MiniPill key={m} module={m} entry={e} onClick={() => setActiveModule(m as ModuleId)} />
          ))}
        </div>
      )}
    </>
  )
}
