import { useEffect, useMemo, useRef, useState } from 'react'
import {
  computeLiveMissionTiming,
  computeSubAgentsForProgress,
  generateHolographicSplats,
  readPersistedThreeDMission,
  subscribeThreeDMission,
  synthesizeThreeDMasterPrompt,
  type PersistedThreeDMissionState,
} from '../services/threeDSubAgentsOrchestrator.ts'

export interface HolographicSplatLoaderProps {
  prompt: string
  active: boolean
  mode?: 'mesh_3d' | 'engineering_cad'
  phaseLabel?: string
  phasePercent?: number
  startedAtMs?: number
  serverElapsedSeconds?: number | null
  serverRemainingSeconds?: number | null
  stlCount?: number
  verifiedCriteriaCount?: number
  totalCriteriaCount?: number
  referenceImageUrl?: string | null
  compact?: boolean
  onApplyMasterPrompt?: (formattedPrompt: string, inferredConstraints: string) => void
  onStop?: () => void
}

type HoloDisplayMode = 'splats' | 'kinematics' | 'laser_cad'

export default function HolographicSplatLoader({
  prompt,
  active,
  mode = 'mesh_3d',
  phaseLabel = '',
  phasePercent = 0,
  startedAtMs,
  serverElapsedSeconds = null,
  serverRemainingSeconds = null,
  stlCount = 0,
  verifiedCriteriaCount = 0,
  totalCriteriaCount = 0,
  referenceImageUrl = null,
  compact = false,
  onApplyMasterPrompt,
  onStop,
}: HolographicSplatLoaderProps) {
  const [persistedMission, setPersistedMission] = useState<PersistedThreeDMissionState | null>(() =>
    readPersistedThreeDMission(),
  )
  const [nowMs, setNowMs] = useState(() => Date.now())
  const [holoMode, setHoloMode] = useState<HoloDisplayMode>('splats')
  const [showMasterPrompt, setShowMasterPrompt] = useState(false)
  const [copiedMaster, setCopiedMaster] = useState(false)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const dragRef = useRef<{ dragging: boolean; lastX: number; lastY: number; rotY: number; rotX: number }>({
    dragging: false,
    lastX: 0,
    lastY: 0,
    rotY: 0.45,
    rotX: 0.18,
  })

  useEffect(() => {
    return subscribeThreeDMission((state) => {
      setPersistedMission(state)
    })
  }, [])

  // Horloge murale infigeable (1 tick / seconde basé sur Date.now())
  useEffect(() => {
    if (!active && !persistedMission?.active) return
    setNowMs(Date.now())
    const timer = window.setInterval(() => {
      setNowMs(Date.now())
    }, 1000)
    const onVis = () => {
      if (!document.hidden) setNowMs(Date.now())
    }
    document.addEventListener('visibilitychange', onVis)
    window.addEventListener('focus', onVis)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVis)
      window.removeEventListener('focus', onVis)
    }
  }, [active, persistedMission?.active])

  const effectivePrompt = (prompt || persistedMission?.rawPrompt || 'Système 3D articulé').trim()
  const blueprint = useMemo(
    () => synthesizeThreeDMasterPrompt(effectivePrompt),
    [effectivePrompt],
  )

  const effectivePct = useMemo(() => {
    const raw = typeof phasePercent === 'number' && phasePercent > 0 ? phasePercent : persistedMission?.phasePercent || 8
    return Math.max(4, Math.min(99, Math.round(raw)))
  }, [phasePercent, persistedMission?.phasePercent])

  const effectivePhaseLabel =
    phaseLabel.trim() ||
    persistedMission?.phaseLabel ||
    'Orchestration des sous-agents 3D & construction volumétrique en cours…'

  const effectiveStlCount = stlCount || persistedMission?.stlCount || 0
  const effectiveVerified = verifiedCriteriaCount || persistedMission?.verifiedCriteriaCount || 0
  const effectiveTotalCriteria = totalCriteriaCount || persistedMission?.totalCriteriaCount || 0

  const subAgents = useMemo(
    () =>
      computeSubAgentsForProgress(blueprint, effectivePct, effectivePhaseLabel, {
        stlCount: effectiveStlCount,
        verifiedCriteriaCount: effectiveVerified,
        totalCriteriaCount: effectiveTotalCriteria,
      }),
    [blueprint, effectivePct, effectivePhaseLabel, effectiveStlCount, effectiveVerified, effectiveTotalCriteria],
  )

  const activeAgent = useMemo(
    () => subAgents.find((a) => a.status === 'working') || subAgents[subAgents.length - 1],
    [subAgents],
  )

  const timing = useMemo(() => {
    const syntheticMission: PersistedThreeDMissionState = persistedMission ?? {
      missionKey: 'live',
      rawPrompt: effectivePrompt,
      mode,
      active: true,
      startedAtMs: startedAtMs || Date.now(),
      lastHeartbeatMs: Date.now(),
      phaseLabel: effectivePhaseLabel,
      phasePercent: effectivePct,
      estimatedTotalSeconds: mode === 'engineering_cad' ? 240 : 360,
      stlCount: effectiveStlCount,
      verifiedCriteriaCount: effectiveVerified,
      totalCriteriaCount: effectiveTotalCriteria,
      masterBlueprint: blueprint,
      subAgents,
    }
    return computeLiveMissionTiming(
      syntheticMission,
      nowMs,
      serverElapsedSeconds,
      serverRemainingSeconds,
    )
  }, [
    persistedMission,
    effectivePrompt,
    mode,
    startedAtMs,
    effectivePhaseLabel,
    effectivePct,
    effectiveStlCount,
    effectiveVerified,
    effectiveTotalCriteria,
    blueprint,
    subAgents,
    nowMs,
    serverElapsedSeconds,
    serverRemainingSeconds,
  ])

  const splats = useMemo(
    () => generateHolographicSplats(blueprint.archetype, compact ? 1100 : 1750),
    [blueprint.archetype, compact],
  )

  // Rendu 60 FPS du champ 3D de Gaussian Splats Holographiques
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let disposed = false
    let rafId = 0
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let width = 0
    let height = 0

    const resize = () => {
      width = canvas.clientWidth || 640
      height = canvas.clientHeight || 380
      canvas.width = Math.max(1, Math.floor(width * dpr))
      canvas.height = Math.max(1, Math.floor(height * dpr))
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)

    const renderFrame = (timeMs: number) => {
      if (disposed) return
      const t = timeMs * 0.001
      const prog = Math.max(0.08, Math.min(1, effectivePct / 100))

      if (!dragRef.current.dragging) {
        dragRef.current.rotY += 0.0065
      }
      const rotY = dragRef.current.rotY
      const rotX = dragRef.current.rotX

      ctx.clearRect(0, 0, width, height)

      // Fond holographique profond
      const bgGrad = ctx.createRadialGradient(
        width * 0.5,
        height * 0.52,
        10,
        width * 0.5,
        height * 0.52,
        Math.max(width, height) * 0.65,
      )
      bgGrad.addColorStop(0, 'rgba(14, 30, 56, 0.92)')
      bgGrad.addColorStop(0.55, 'rgba(7, 13, 25, 0.96)')
      bgGrad.addColorStop(1, 'rgba(4, 7, 15, 0.99)')
      ctx.fillStyle = bgGrad
      ctx.fillRect(0, 0, width, height)

      // Grille de référence CAO en perspective au sol
      const cx = width * 0.5
      const cy = height * 0.54
      const scale = Math.min(width, height) * 0.44

      ctx.save()
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.12)'
      ctx.lineWidth = 1
      for (let g = -4; g <= 4; g++) {
        const gx = g * 0.22
        ctx.beginPath()
        ctx.moveTo(cx + gx * scale * 0.9, cy + 0.72 * scale)
        ctx.lineTo(cx + gx * scale * 1.45, cy + 0.95 * scale)
        ctx.stroke()
      }
      // Anneau radar de base
      ctx.beginPath()
      ctx.ellipse(cx, cy + 0.76 * scale, scale * 0.78, scale * 0.18, 0, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.28)'
      ctx.stroke()
      ctx.restore()

      // Plan laser de balayage vertical
      const scanY = Math.sin(t * 1.35) * 0.85
      const cosY = Math.cos(rotY)
      const sinY = Math.sin(rotY)
      const cosX = Math.cos(rotX)
      const sinX = Math.sin(rotX)

      // Projection et tri en profondeur des Gaussian Splats
      const projected: Array<{
        sx: number
        sy: number
        sz: number
        r: number
        color: string
        alpha: number
        isJoint?: boolean
      }> = []

      const jointScreenNodes: Array<{ sx: number; sy: number; fingerIdx?: number; phalangeIdx?: number }> = []

      for (let i = 0; i < splats.length; i++) {
        const sp = splats[i]
        let px = sp.x
        let py = sp.y
        let pz = sp.z

        // Animation cinématique temps réel des doigts si main robotisée
        if (blueprint.archetype === 'robotic_hand' && sp.fingerIdx !== undefined && sp.phalangeIdx !== undefined) {
          const flexWave =
            0.28 *
            (0.5 + 0.5 * Math.sin(t * 2.1 - sp.fingerIdx * 0.45 - sp.phalangeIdx * 0.35)) *
            (holoMode === 'kinematics' ? 1.35 : 0.85)
          const curlZ = flexWave * (sp.phalangeIdx + 1) * 0.12
          const curlY = -Math.abs(flexWave) * (sp.phalangeIdx + 1) * 0.055
          pz += curlZ
          py += curlY
        }

        // Dispersion quantique initiale qui converge au fil de la progression `prog`
        const isSolid = prog >= sp.solidifyThreshold
        const scatter = isSolid ? 0.0 : (sp.solidifyThreshold - prog) * 0.38
        if (scatter > 0) {
          const orbitAngle = t * 1.6 + i * 0.13
          px += Math.cos(orbitAngle) * scatter
          pz += Math.sin(orbitAngle) * scatter
          py += Math.sin(t * 2.0 + i) * scatter * 0.4
        }

        // Rotation 3D Y puis X
        const rx = px * cosY - pz * sinY
        const rz1 = px * sinY + pz * cosY
        const ry = py * cosX - rz1 * sinX
        const rz = py * sinX + rz1 * cosX

        const fov = 2.6
        const depth = fov / (fov + rz + 1.25)
        const sx = cx + rx * scale * depth
        const sy = cy - ry * scale * depth

        const distToScan = Math.abs(py - scanY)
        const scanBoost = distToScan < 0.09 ? (1 - distToScan / 0.09) * 0.55 : 0

        let alpha = isSolid ? 0.78 : 0.26
        if (holoMode === 'kinematics' && !sp.isJoint) {
          alpha *= 0.38
        }
        alpha = Math.min(1, alpha + scanBoost)

        const r = sp.radius * depth * (sp.isJoint && holoMode === 'kinematics' ? 1.55 : 1.0)
        projected.push({
          sx,
          sy,
          sz: rz,
          r,
          color: distToScan < 0.045 && holoMode === 'laser_cad' ? '#ffffff' : sp.color,
          alpha,
          isJoint: sp.isJoint,
        })

        if (sp.isJoint && i % 7 === 0) {
          jointScreenNodes.push({
            sx,
            sy,
            fingerIdx: sp.fingerIdx,
            phalangeIdx: sp.phalangeIdx,
          })
        }
      }

      projected.sort((a, b) => b.sz - a.sz)

      // Lignes cinématiques / vecteurs d'articulation
      if (holoMode === 'kinematics' || holoMode === 'laser_cad') {
        ctx.save()
        ctx.strokeStyle =
          holoMode === 'kinematics' ? 'rgba(245, 158, 11, 0.38)' : 'rgba(52, 211, 153, 0.25)'
        ctx.lineWidth = 1.1
        for (let j = 1; j < jointScreenNodes.length; j++) {
          const prev = jointScreenNodes[j - 1]
          const curr = jointScreenNodes[j]
          if (prev.fingerIdx === curr.fingerIdx) {
            ctx.beginPath()
            ctx.moveTo(prev.sx, prev.sy)
            ctx.lineTo(curr.sx, curr.sy)
            ctx.stroke()
          }
        }
        ctx.restore()
      }

      // Dessin des Gaussian Splats (noyau + halo anisotrope)
      for (let i = 0; i < projected.length; i++) {
        const pt = projected[i]
        ctx.globalAlpha = pt.alpha
        ctx.fillStyle = pt.color
        ctx.beginPath()
        ctx.ellipse(
          pt.sx,
          pt.sy,
          pt.r * 1.35,
          pt.r * 0.88,
          (i % 5) * 0.3,
          0,
          Math.PI * 2,
        )
        ctx.fill()

        if (pt.isJoint || pt.alpha > 0.85) {
          ctx.globalAlpha = pt.alpha * 0.28
          ctx.beginPath()
          ctx.arc(pt.sx, pt.sy, pt.r * 2.4, 0, Math.PI * 2)
          ctx.fill()
        }
      }
      ctx.globalAlpha = 1

      // Faisceau laser horizontal de reconstruction
      const laserScreenY = cy - scanY * scale * 0.72
      const laserGrad = ctx.createLinearGradient(cx - scale * 0.9, laserScreenY, cx + scale * 0.9, laserScreenY)
      laserGrad.addColorStop(0, 'rgba(56, 189, 248, 0)')
      laserGrad.addColorStop(0.2, 'rgba(56, 189, 248, 0.45)')
      laserGrad.addColorStop(0.5, 'rgba(52, 211, 153, 0.9)')
      laserGrad.addColorStop(0.8, 'rgba(56, 189, 248, 0.45)')
      laserGrad.addColorStop(1, 'rgba(56, 189, 248, 0)')
      ctx.fillStyle = laserGrad
      ctx.fillRect(cx - scale * 0.9, laserScreenY - 1.2, scale * 1.8, 2.4)

      // Annotations HUD d'ingénierie dans les coins du canvas
      ctx.font = '600 10px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
      ctx.fillStyle = 'rgba(125, 211, 252, 0.85)'
      ctx.fillText(
        `ARCHÉTYPE: ${blueprint.archetype.toUpperCase()} · ${blueprint.degreesOfFreedom} DDL`,
        14,
        22,
      )
      ctx.fillStyle = 'rgba(167, 139, 250, 0.85)'
      ctx.fillText(
        `ENVELOPPE: ${blueprint.dimensionalEnvelopeMm.join(' × ')} mm · SPLATS: ${splats.length}`,
        14,
        38,
      )
      ctx.fillStyle = 'rgba(52, 211, 153, 0.9)'
      ctx.fillText(
        `SOLIDIFICATION: ${effectivePct}% · ${activeAgent?.codeName || 'AGENT ACTIF'}`,
        14,
        height - 14,
      )

      rafId = window.requestAnimationFrame(renderFrame)
    }

    rafId = window.requestAnimationFrame(renderFrame)
    return () => {
      disposed = true
      window.cancelAnimationFrame(rafId)
      ro.disconnect()
    }
  }, [splats, blueprint, effectivePct, holoMode, activeAgent])

  const handleCopyMasterPrompt = async () => {
    try {
      await navigator.clipboard.writeText(blueprint.formattedMasterPrompt)
      setCopiedMaster(true)
      window.setTimeout(() => setCopiedMaster(false), 2200)
    } catch {
      /* ignore clipboard restrictions */
    }
  }

  return (
    <section
      aria-label="Prévisualisation Holographique Gaussian Splats et Escouade de Sous-Agents 3D"
      className="relative overflow-hidden rounded-[1.6rem] border border-cyan-400/30 bg-[#050b14] text-slate-100 shadow-2xl"
    >
      {/* Barre supérieure : Statut Live + Timer Infigeable + ETA + Contrôles */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-cyan-500/20 bg-slate-900/80 px-4 py-3 backdrop-blur-md">
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-3 w-3">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-400" />
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-[0.16em] text-emerald-300">
                Projet en route · Calcul actif sur le PC
              </span>
              <span className="rounded-full border border-cyan-400/35 bg-cyan-500/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-cyan-200">
                Étape {activeAgent.index} / {subAgents.length}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-slate-300 line-clamp-1" title={effectivePhaseLabel}>
              {effectivePhaseLabel}
            </p>
          </div>
        </div>

        {/* Compteurs temps réel : Écoulé, Restant (ETA), Pourcentage */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="rounded-xl border border-slate-700/80 bg-slate-950/90 px-3 py-1.5 text-right">
            <span className="block text-[9px] uppercase tracking-wider text-slate-400">Temps écoulé</span>
            <span className="font-mono text-sm font-bold text-cyan-300" data-testid="holo-elapsed-timer">
              {timing.formattedElapsed}
            </span>
          </div>
          <div className="rounded-xl border border-slate-700/80 bg-slate-950/90 px-3 py-1.5 text-right">
            <span className="block text-[9px] uppercase tracking-wider text-slate-400">Temps restant estimé</span>
            <span className="font-mono text-sm font-bold text-amber-300" data-testid="holo-eta-timer">
              {timing.formattedRemaining}
            </span>
          </div>
          <div className="rounded-xl border border-cyan-500/40 bg-cyan-500/15 px-3 py-1.5 text-right">
            <span className="block text-[9px] uppercase tracking-wider text-cyan-200">Avancement</span>
            <span className="font-mono text-sm font-extrabold text-white" data-testid="holo-progress-pct">
              {effectivePct}%
            </span>
          </div>
          {onStop && (
            <button
              type="button"
              onClick={onStop}
              className="rounded-xl border border-red-500/45 bg-red-500/15 px-3 py-2 text-xs font-semibold text-red-200 transition hover:bg-red-500/25"
            >
              ■ Arrêter
            </button>
          )}
        </div>
      </div>

      {/* Barre de progression globale continue */}
      <div className="h-1.5 w-full bg-slate-900">
        <div
          className="h-full bg-gradient-to-r from-cyan-400 via-indigo-400 to-emerald-400 transition-all duration-300"
          style={{ width: `${effectivePct}%` }}
        />
      </div>

      {/* Grille centrale : Canvas Gaussian Splats 3D + Escouade de 5 Sous-Agents */}
      <div className={`grid gap-4 p-4 ${compact ? 'lg:grid-cols-1' : 'xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]'}`}>
        {/* Colonne Gauche : Viewport Holographique Gaussian Splats */}
        <div className="flex flex-col justify-between rounded-2xl border border-cyan-500/25 bg-[#040811] overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 px-3.5 py-2.5">
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300">
                Prévisualisation Holographique · Gaussian Splats 3D
              </span>
              <h4 className="text-sm font-semibold text-white">{blueprint.subjectTitle}</h4>
            </div>
            <div className="flex flex-wrap gap-1" role="group" aria-label="Mode de prévisualisation holographique">
              {(
                [
                  ['splats', 'Nuage Splats 3D'],
                  ['kinematics', 'Squelette & DDL'],
                  ['laser_cad', 'Scan CAO & Cotes'],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setHoloMode(id)}
                  className={`rounded-lg border px-2.5 py-1 text-[11px] font-medium transition ${
                    holoMode === id
                      ? 'border-cyan-400 bg-cyan-500/20 text-cyan-200'
                      : 'border-slate-700/70 bg-slate-900/60 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Zone Canvas Interactive (rotation 3D à la souris / au doigt sur tunnel mobile) */}
          <div className={`relative w-full ${compact ? 'h-[250px]' : 'h-[340px] sm:h-[390px]'} select-none`}>
            <canvas
              ref={canvasRef}
              onPointerDown={(e) => {
                dragRef.current.dragging = true
                dragRef.current.lastX = e.clientX
                dragRef.current.lastY = e.clientY
              }}
              onPointerMove={(e) => {
                if (!dragRef.current.dragging) return
                const dx = e.clientX - dragRef.current.lastX
                const dy = e.clientY - dragRef.current.lastY
                dragRef.current.lastX = e.clientX
                dragRef.current.lastY = e.clientY
                dragRef.current.rotY += dx * 0.008
                dragRef.current.rotX = Math.max(-0.85, Math.min(0.85, dragRef.current.rotX + dy * 0.006))
              }}
              onPointerUp={() => {
                dragRef.current.dragging = false
              }}
              onPointerLeave={() => {
                dragRef.current.dragging = false
              }}
              className="h-full w-full cursor-grab active:cursor-grabbing"
            />

            {/* Vignette image de référence si déjà générée */}
            {referenceImageUrl && (
              <div className="pointer-events-none absolute right-3 top-3 w-24 overflow-hidden rounded-xl border border-cyan-400/40 bg-slate-950/85 p-1 shadow-lg">
                <img
                  src={referenceImageUrl}
                  alt="Référence validée"
                  className="h-20 w-full rounded-lg object-contain"
                />
                <span className="mt-0.5 block text-center font-mono text-[9px] text-cyan-200">
                  Réf. active
                </span>
              </div>
            )}

            <div className="pointer-events-none absolute bottom-2.5 right-3 rounded-lg border border-slate-700/70 bg-slate-950/80 px-2.5 py-1 text-[10px] text-slate-300">
              Glisser pour tourner l’hologramme 3D · Reprise auto si vous quittez la page
            </div>
          </div>

          {/* Bandeau métriques d'ingénierie sous le canvas */}
          <div className="grid grid-cols-2 gap-2 border-t border-slate-800/80 bg-slate-950/70 px-3.5 py-2.5 text-[11px] sm:grid-cols-4">
            <div>
              <span className="text-slate-400">Chaîne cinématique :</span>
              <p className="font-semibold text-cyan-200 truncate" title={blueprint.kinematicChainSummary}>
                {blueprint.degreesOfFreedom} DDL (degrés de liberté)
              </p>
            </div>
            <div>
              <span className="text-slate-400">Enveloppe cible :</span>
              <p className="font-mono font-semibold text-slate-200">
                {blueprint.dimensionalEnvelopeMm.join(' × ')} mm
              </p>
            </div>
            <div>
              <span className="text-slate-400">Solides générés :</span>
              <p className="font-mono font-semibold text-emerald-300">
                {effectiveStlCount > 0 ? `${effectiveStlCount} STL/GLB sur disque` : 'Synthèse volumétrique…'}
              </p>
            </div>
            <div>
              <span className="text-slate-400">Continuité session :</span>
              <p className="font-semibold text-amber-300">
                Persistant (Tunnel / Mobile / PC)
              </p>
            </div>
          </div>
        </div>

        {/* Colonne Droite : Division du travail en 5 Sous-Agents Indépendants */}
        <div className="flex flex-col justify-between space-y-3">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/65 p-3.5">
            <div className="flex items-center justify-between gap-2 mb-2.5">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-indigo-300">
                  Intelligence Collective · Division par Tâche
                </span>
                <h4 className="text-sm font-semibold text-white">
                  Escouade de 5 Sous-Agents 3D & Ingénierie
                </h4>
              </div>
              <span className="rounded-full border border-emerald-400/35 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
                {subAgents.filter((a) => a.status === 'done').length} / {subAgents.length} terminés
              </span>
            </div>

            <div className="space-y-2">
              {subAgents.map((agent) => {
                const isWorking = agent.status === 'working'
                const isDone = agent.status === 'done'
                return (
                  <div
                    key={agent.id}
                    className={`rounded-xl border p-2.5 transition-all ${
                      isWorking
                        ? 'border-cyan-400/60 bg-cyan-500/10 shadow-md'
                        : isDone
                          ? 'border-emerald-500/35 bg-emerald-500/5'
                          : 'border-slate-800 bg-slate-950/50 opacity-75'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-slate-950"
                          style={{ backgroundColor: isDone ? '#34d399' : isWorking ? agent.accentColor : '#475569' }}
                        >
                          {isDone ? '✓' : agent.index}
                        </span>
                        <div className="min-w-0">
                          <p className="text-xs font-semibold text-white truncate">{agent.role}</p>
                          <p className="font-mono text-[10px] text-slate-400 truncate">{agent.codeName}</p>
                        </div>
                      </div>
                      <span
                        className={`shrink-0 rounded-full px-2 py-0.5 font-mono text-[10px] font-bold ${
                          isDone
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : isWorking
                              ? 'bg-cyan-500/25 text-cyan-200'
                              : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {isDone ? '100% · OK' : isWorking ? `${agent.progressPct}% · ACTIF` : 'EN FILE'}
                      </span>
                    </div>

                    <p className="mt-1.5 text-[11px] leading-snug text-slate-300">{agent.currentTask}</p>

                    <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                      <div
                        className="h-full transition-all duration-300"
                        style={{
                          width: `${agent.progressPct}%`,
                          backgroundColor: isDone ? '#34d399' : agent.accentColor,
                        }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Carte du Prompt Maître Auto-Organisé */}
          <div className="rounded-2xl border border-indigo-500/30 bg-indigo-950/20 p-3.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-indigo-300">
                  Prompt Maître Auto-Structuré
                </span>
                <p className="text-xs text-slate-300">
                  Contraintes mécatroniques, jeux et topologie déduits automatiquement même sans contrainte fournie.
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => setShowMasterPrompt((v) => !v)}
                  className="rounded-lg border border-indigo-400/40 bg-indigo-500/15 px-2.5 py-1 text-xs font-medium text-indigo-200 hover:bg-indigo-500/25"
                >
                  {showMasterPrompt ? 'Masquer le Prompt Maître' : 'Voir le Prompt Maître'}
                </button>
                <button
                  type="button"
                  onClick={() => void handleCopyMasterPrompt()}
                  className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-medium text-slate-200 hover:border-cyan-400/50"
                >
                  {copiedMaster ? '✓ Copié !' : 'Copier'}
                </button>
                {onApplyMasterPrompt && (
                  <button
                    type="button"
                    onClick={() =>
                      onApplyMasterPrompt(
                        blueprint.formattedMasterPrompt,
                        blueprint.inferredConstraints.map((c) => `• ${c}`).join('\n'),
                      )
                    }
                    className="rounded-lg bg-cyan-500 px-2.5 py-1 text-xs font-semibold text-slate-950 hover:bg-cyan-400"
                  >
                    Injecter dans le projet
                  </button>
                )}
              </div>
            </div>

            {showMasterPrompt && (
              <pre className="mt-2.5 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-xl border border-slate-800 bg-slate-950/90 p-3 font-mono text-[11px] leading-relaxed text-slate-200">
                {blueprint.formattedMasterPrompt}
              </pre>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

export { HolographicSplatLoader }
