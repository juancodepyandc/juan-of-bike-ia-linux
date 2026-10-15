import { useEffect, useRef, useState } from 'react'
import { bridgeFetch, readBridgeKey } from '../utils/bridgeAuth.ts'
import { duration } from './ProjectsPanel.tsx'
import { getBridgeUrl } from '../utils/runtime.ts'

type TelemetryMilestone = { id: string; label: string; done: boolean; active: boolean }
type TelemetryCriterion = { index: number; text: string; status: string }
type TelemetryAction = { index: number; kind: string; summary: string }
type TelemetryPart = {
  id: string
  name: string
  file: string
  source: string
  dimensions_mm: number[] | null
  volume_mm3: number | null
  watertight: boolean | null
  filament: string | null
  color_rgba: number[] | null
}
type TelemetryJoint = {
  id: string
  type: string
  parent: string
  child: string
  limits: [number, number] | null
}
type TelemetryBomItem = { name: string; quantity: number; specification: string }
type TelemetryDraftSummary = {
  title: string
  feasibility: string
  units: string
  part_count: number
  printable_count: number
  purchased_count: number
  joint_count: number
  dof: number | null
  parts: TelemetryPart[]
  joints: TelemetryJoint[]
  bom: TelemetryBomItem[]
  assembly_steps: string[]
  assumptions: string[]
  blockers: string[]
  simulations: Record<string, unknown>
}
type Telemetry = {
  phase: string
  progress_pct: number
  criteria: TelemetryCriterion[]
  criteria_count: number
  verified_count: number
  recent_actions: TelemetryAction[]
  workspace_files: string[]
  stl_count: number
  milestones: TelemetryMilestone[]
  draft_summary: TelemetryDraftSummary | null
  profile_summary: {
    name?: string
    process?: string
    bed_mm?: number[]
    clearance_mm?: number
    wall_mm?: number
  } | null
}

type Design = {
  scheduling?: {
    queue_position: number
    wait_seconds: number | null
    estimated_duration_seconds: number | null
    remaining_seconds: number | null
    elapsed_seconds: number
  }
  id: string
  mission_id: string
  state: string
  ready: boolean
  artifacts_available?: boolean
  partial?: boolean
  objective?: string
  constraints?: string
  request_id?: string
  result?: string
  error?: string
  steps?: number
  download_url?: string
  dossier_url?: string
  viewer_url?: string
  telemetry?: Telemetry
  report?: {
    title: string
    feasibility: string
    assumptions: string[]
    blockers: string[]
    bom: { name: string; quantity: number; specification: string }[]
  }
}

const STORAGE = 'aurora.engineering-objective.v1'
type SourceModel = { mission_id: string; file: string }
function sourceModel(): SourceModel | null {
  try {
    const s = JSON.parse(localStorage.getItem(STORAGE + '.source') || 'null')
    return s && /^mis_[a-f0-9]{16}$/.test(s.mission_id) && typeof s.file === 'string' ? s : null
  } catch {
    return null
  }
}
type RequestPayload = {
  source?: SourceModel
  objective: string
  constraints: string
  profile: unknown
  request_id: string
}
function savedRequest(): RequestPayload | null {
  try {
    const d = JSON.parse(localStorage.getItem(STORAGE + '.pending') || 'null')
    return d && typeof d.request_id === 'string' && typeof d.objective === 'string' && typeof d.constraints === 'string'
      ? d
      : null
  } catch {
    return null
  }
}
class RejectedRequest extends Error {}
function initial() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE) || '{}')
  } catch {
    return {}
  }
}

const QUICK_SPECS: { label: string; goalSnippet?: string; constraintSnippet: string }[] = [
  {
    label: '+ Mécanisme & cinématique',
    goalSnippet: 'Ensemble articulé fonctionnel avec pièces mobiles coordonnées, butées de fin de course et montage démontable.',
    constraintSnippet: 'Définir explicitement chaque liaison mécanique (revolute, prismatic, fixed), les axes, les limites de course et un jeu fonctionnel de 0,25 à 0,35 mm sur les articulations.',
  },
  {
    label: '+ Tolérances & ajustements précis',
    constraintSnippet: 'Jeu radial d’emboîtement 0,20 mm (ajustement serré/glissant selon fonction), chanfrein d’entrée 0,3 mm, paroi minimale 2,4 mm autour des logements et pions.',
  },
  {
    label: '+ Intégration moteur / capteurs',
    constraintSnippet: 'Prévoir logements cotés pour actionneurs/capteurs, passages de câbles internes de 4 mm min, pattes de fixation alignées et accès de maintenance par une face dégagée.',
  },
  {
    label: '+ Visserie & inserts métalliques',
    constraintSnippet: 'Assembler par visserie standard M3 (alésages passants Ø3,2 mm, lamages tête cylindrique Ø6 mm, ou avant-trous inserts thermofixés Ø4,0 × 5 mm) et nomenclature BOM complète.',
  },
  {
    label: '+ Grand format multi-pièces',
    constraintSnippet: 'Respecter strictement le volume utile du plateau imprimante : découper les grands sous-ensembles avec pions de centrage détrompés et numéroter l’ordre de montage pas à pas.',
  },
]

export default function EngineeringDesignPanel({ profile, objectiveHint = '' }: { profile: unknown; objectiveHint?: string }) {
  const [goal, setGoal] = useState<string>(() => initial().goal || objectiveHint)
  const [source, setSource] = useState<SourceModel | null>(sourceModel)
  const [constraints, setConstraints] = useState<string>(() => initial().constraints || '')
  const [projects, setProjects] = useState<Design[]>([])
  const [current, setCurrent] = useState<Design | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [deviceConnected, setDeviceConnected] = useState(true)
  const [showEmbeddedViewer, setShowEmbeddedViewer] = useState(true)
  const [viewerExploded, setViewerExploded] = useState(false)
  const [activeStepIndex, setActiveStepIndex] = useState<number>(-1)
  const [inspectedPartId, setInspectedPartId] = useState<string>('')
  const viewerIframeRef = useRef<HTMLIFrameElement | null>(null)
  const mounted = useRef(true)
  const preferred = useRef<string>((() => {
    try {
      return localStorage.getItem(STORAGE + '.selected') || ''
    } catch {
      return ''
    }
  })())

  useEffect(() => {
    if (current) {
      preferred.current = current.id
      try {
        localStorage.setItem(STORAGE + '.selected', current.id)
      } catch {
        /* ignore storage restrictions */
      }
    }
  }, [current])

  const pending = useRef<RequestPayload | null>(savedRequest())
  const [unconfirmed, setUnconfirmed] = useState(Boolean(pending.current))

  useEffect(() => {
    const navigate = (event: Event) => {
      const d = (event as CustomEvent).detail
      if (d?.module === '3d' && !pending.current && typeof d.draft?.goal === 'string') {
        setGoal(d.draft.goal)
        setConstraints(d.draft.constraints || '')
        setSource(sourceModel())
      }
      try {
        preferred.current = localStorage.getItem(STORAGE + '.selected') || preferred.current
      } catch {
        /* ignore */
      }
    }
    window.addEventListener('aurora:navigate', navigate)
    return () => window.removeEventListener('aurora:navigate', navigate)
  }, [])

  function remember(data: RequestPayload | null) {
    const previous = pending.current?.request_id
    pending.current = data
    setUnconfirmed(Boolean(data))
    try {
      if (data) localStorage.setItem(STORAGE + '.pending', JSON.stringify(data))
      else if (savedRequest()?.request_id === previous) localStorage.removeItem(STORAGE + '.pending')
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE, JSON.stringify({ goal, constraints }))
    } catch {
      /* ignore */
    }
  }, [goal, constraints])

  async function api(path = '', data?: unknown) {
    const r = await bridgeFetch(`${getBridgeUrl()}/api/3d/design${path}`, {
      method: data === undefined ? 'GET' : 'POST',
      headers: data === undefined ? {} : { 'Content-Type': 'application/json' },
      body: data === undefined ? undefined : JSON.stringify(data),
    })
    const result = await r.json()
    if (!r.ok) {
      throw r.status >= 400 && r.status < 500
        ? new RejectedRequest(result.error || 'Demande refusée.')
        : Error(result.error || 'Projet indisponible.')
    }
    return result
  }

  useEffect(() => {
    mounted.current = true
    let running = false
    const poll = async () => {
      if (running || document.hidden) return
      running = true
      try {
        const d = await api()
        if (mounted.current) {
          setDeviceConnected(true)
          setProjects(d.projects)
          if (pending.current && d.projects.some((p: Design) => p.request_id === pending.current?.request_id)) {
            remember(null)
          }
          setCurrent((c) =>
            d.projects.find((p: Design) => p.id === c?.id) ||
            d.projects.find((p: Design) => p.id === preferred.current) ||
            d.projects.find((p: Design) => ['running', 'queued'].includes(p.state)) ||
            d.projects[0] ||
            null,
          )
        }
      } catch {
        /* Show authentication only on an explicit user action. */
      } finally {
        running = false
      }
    }
    // Ordinary polling must not open a connection dialog before user intent.
    const session = async () => {
      try {
        const key = readBridgeKey()
        const r = await fetch(`${getBridgeUrl()}/api/devices/session`, {
          headers: key ? { Authorization: `Bearer ${key}` } : {},
        })
        const info = await r.json()
        if (mounted.current) setDeviceConnected(Boolean(info.connected))
        if (info.connected) await poll()
      } catch {
        /* ignore background poll network error */
      }
    }
    void session()
    const timer = setInterval(() => {
      void session()
    }, 4000)
    return () => {
      mounted.current = false
      clearInterval(timer)
    }
  }, [])

  async function connectAndSync() {
    setBusy(true)
    setError('')
    try {
      const d = await api()
      setDeviceConnected(true)
      setProjects(d.projects)
      setCurrent((c) =>
        d.projects.find((p: Design) => p.id === c?.id) ||
        d.projects.find((p: Design) => p.id === preferred.current) ||
        d.projects.find((p: Design) => ['running', 'queued'].includes(p.state)) ||
        d.projects[0] ||
        null,
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Connexion à l’atelier interrompue.')
    } finally {
      setBusy(false)
    }
  }

  async function start() {
    setBusy(true)
    setError('')
    const data = pending.current || {
      objective: goal.trim(),
      constraints,
      profile,
      ...(source ? { source } : {}),
      request_id: crypto.randomUUID(),
    }
    remember(data)
    try {
      const d = await api('', data)
      setDeviceConnected(true)
      setCurrent(d)
      setProjects((p) => [d, ...p.filter((x) => x.id !== d.id)])
      remember(null)
    } catch (e) {
      if (e instanceof RejectedRequest) remember(null)
      setError(e instanceof Error ? e.message : 'Connexion interrompue.')
    } finally {
      setBusy(false)
    }
  }

  async function resume() {
    if (!current) return
    setBusy(true)
    setError('')
    try {
      setCurrent(await api('/' + current.id + '/resume', {}))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reprise interrompue.')
    } finally {
      setBusy(false)
    }
  }

  async function stopProject() {
    if (!current) return
    setBusy(true)
    setError('')
    try {
      await api('/' + current.id + '/stop', {})
      setCurrent({ ...current, state: 'stopping' })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Arrêt refusé.')
    } finally {
      setBusy(false)
    }
  }

  async function deleteProject() {
    if (!current) return
    setBusy(true)
    setError('')
    try {
      await api('/' + current.id + '/delete', {})
      setProjects((p) => p.filter((x) => x.id !== current.id))
      setCurrent(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Suppression refusée.')
    } finally {
      setBusy(false)
    }
  }

  async function download() {
    if (!current?.download_url) return
    try {
      const r = await bridgeFetch(getBridgeUrl() + current.download_url)
      if (!r.ok) throw Error('Dossier indisponible.')
      const url = URL.createObjectURL(await r.blob())
      const a = document.createElement('a')
      a.href = url
      a.download = 'projet-aurora.zip'
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 30000)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Téléchargement interrompu.')
    }
  }

  function postToViewer(payload: Record<string, unknown>) {
    const win = viewerIframeRef.current?.contentWindow
    if (!win) return
    const targetOrigin = viewerIframeRef.current?.src
      ? new URL(viewerIframeRef.current.src, window.location.href).origin
      : window.location.origin
    win.postMessage(payload, targetOrigin)
  }

  function handleToggleExploded(nextExploded: boolean) {
    setViewerExploded(nextExploded)
    setShowEmbeddedViewer(true)
    postToViewer({ type: 'aurora-assembly-view', exploded: nextExploded })
  }

  function handleInspectPart(partId: string) {
    setInspectedPartId(partId)
    setShowEmbeddedViewer(true)
    setTimeout(() => postToViewer({ type: 'aurora-assembly-inspect', part_id: partId }), 60)
  }

  function handleSelectStep(stepIndex: number) {
    setActiveStepIndex(stepIndex)
    setShowEmbeddedViewer(true)
    setTimeout(() => postToViewer({ type: 'aurora-assembly-step', step_index: stepIndex }), 60)
  }

  function appendQuickSpec(spec: { goalSnippet?: string; constraintSnippet: string }) {
    if (spec.goalSnippet && !goal.trim()) {
      setGoal(spec.goalSnippet)
    }
    setConstraints((prev) => {
      const clean = prev.trim()
      if (clean.includes(spec.constraintSnippet)) return prev
      return clean ? `${clean}\n• ${spec.constraintSnippet}` : `• ${spec.constraintSnippet}`
    })
  }

  const status: Record<string, string> = {
    queued: 'Projet dans la file d’attente',
    planning: 'L’IA prépare son plan',
    running: 'Conception, recherche et tests en cours',
    stopping: 'Arrêt en cours sur le PC',
    completed: 'Dossier livré',
    blocked: 'Une contrainte reste à résoudre',
    failed: 'La mission a rencontré une erreur',
    interrupted: 'Mission interrompue · reprise disponible',
    stopped: 'Mission arrêtée',
    incomplete: 'Dossier incomplet · consulter le résultat',
  }
  const field = 'mt-2 w-full rounded-xl border border-aurora-border bg-aurora-surface-2 p-3 text-base text-aurora-text'
  const telemetry = current?.telemetry
  const draft = telemetry?.draft_summary
  const bomList = draft?.bom?.length ? draft.bom : current?.report?.bom || []
  const assumptionsList = draft?.assumptions?.length ? draft.assumptions : current?.report?.assumptions || []
  const blockersList = draft?.blockers?.length ? draft.blockers : current?.report?.blockers || []

  return (
    <section className="mb-5 rounded-2xl border border-aurora-border bg-aurora-surface/80 p-4 text-aurora-text" aria-label="Conception par objectif">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold">Concevoir un projet avec l’IA</h3>
          <p className="mt-1 text-sm text-aurora-text-muted">
            Décrivez le résultat souhaité. Aurora choisit les structures et éléments nécessaires, recherche leurs contraintes, génère les solides CAO (`design.py` + `STL`), vérifie l’assemblage et teste ses propositions sur le PC.
          </p>
        </div>
        {!deviceConnected && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void connectAndSync()}
            className="min-h-11 rounded-xl border border-amber-400/60 bg-amber-500/15 px-3 py-2 text-xs font-semibold text-amber-200"
          >
            Connecter cet appareil au PC (Tunnel / Mobile)
          </button>
        )}
      </div>

      {source && (
        <p className="mt-2 rounded-xl border border-aurora-accent/40 bg-aurora-accent/10 px-3 py-2 text-sm">
          Modèle source : <strong>{source.file}</strong>
          <button
            type="button"
            disabled={busy || unconfirmed}
            className="ml-3 min-h-11 text-aurora-accent underline"
            onClick={() => {
              setSource(null)
              try {
                localStorage.removeItem(STORAGE + '.source')
              } catch {
                /* ignore */
              }
            }}
          >
            Retirer la référence
          </button>
        </p>
      )}

      <label className="mt-3 block text-sm font-medium">
        Objectif
        <textarea
          aria-label="Objectif du projet"
          disabled={busy || unconfirmed}
          rows={3}
          className={field}
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="Ce que le projet doit accomplir, ses dimensions, ses mécanismes (engrenages, charnières, boîtier, support articulé) et son usage…"
        />
      </label>

      <details className="mt-3" open={Boolean(constraints.trim())}>
        <summary className="min-h-11 cursor-pointer text-sm font-medium">
          Contraintes, tolérances ou composants imposés (facultatif)
        </summary>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {QUICK_SPECS.map((spec) => (
            <button
              key={spec.label}
              type="button"
              disabled={busy || unconfirmed}
              onClick={() => appendQuickSpec(spec)}
              className="rounded-lg border border-aurora-border/70 bg-aurora-surface-2 px-2.5 py-1.5 text-xs text-aurora-text-muted hover:border-aurora-accent hover:text-aurora-text"
            >
              {spec.label}
            </button>
          ))}
        </div>
        <textarea
          aria-label="Contraintes du projet"
          disabled={busy || unconfirmed}
          rows={3}
          className={field}
          value={constraints}
          onChange={(e) => setConstraints(e.target.value)}
          placeholder="Pièces à utiliser, visserie M3, jeux d’assemblage en mm, moteurs/capteurs, budget, forces, matière, environnement…"
        />
      </details>

      <button
        type="button"
        disabled={busy || (!goal.trim() && !unconfirmed)}
        className="mt-3 min-h-12 w-full rounded-xl bg-aurora-accent p-3 font-semibold text-white disabled:opacity-40"
        onClick={() => void start()}
      >
        {busy
          ? 'Connexion et démarrage…'
          : unconfirmed
            ? 'Vérifier ou reprendre cette demande'
            : 'Concevoir, tester et préparer le dossier'}
      </button>
      <p className="mt-2 text-xs text-aurora-text-dim">
        L’IA travaille dans un dossier dédié et poursuit côté PC lorsque vous quittez cette page (y compris depuis un téléphone ou le tunnel). Ses hypothèses, cotes et preuves géométriques sont suivies en direct ci-dessous.
      </p>

      {unconfirmed && (
        <p className="mt-2 text-sm text-amber-300">
          Demande non confirmée : ce bouton reprend la même demande et son profil, sans créer un second travail.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </p>
      )}

      {projects.length > 1 && (
        <label className="mt-3 block text-sm">
          Retrouver un projet ({projects.length})
          <select
            className={field}
            value={current?.id || ''}
            onChange={(e) => {
              setCurrent(projects.find((p) => p.id === e.target.value) || null)
              setActiveStepIndex(-1)
              setInspectedPartId('')
            }}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.report?.title || p.telemetry?.draft_summary?.title || p.objective?.slice(0, 80) || p.id.slice(-8)} · {status[p.state] || p.state}
              </option>
            ))}
          </select>
        </label>
      )}

      {current && (
        <div className="mt-4 rounded-xl border border-aurora-border/80 bg-aurora-surface-2/60 p-3.5 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p role="status" className="font-semibold text-aurora-text">
              {status[current.state] || current.state} · {current.steps || 0} étape(s)
            </p>
            {telemetry && (
              <span className="rounded-full border border-aurora-accent/40 bg-aurora-accent/15 px-2.5 py-0.5 text-xs font-medium text-aurora-accent">
                Avancement : {telemetry.progress_pct}%
              </span>
            )}
          </div>

          {telemetry && (
            <div className="mt-3 space-y-3">
              {/* Progress Bar */}
              <div className="h-2 w-full overflow-hidden rounded-full bg-aurora-border/40">
                <div
                  className="h-full bg-aurora-accent transition-all duration-300"
                  style={{ width: `${Math.max(4, Math.min(100, telemetry.progress_pct))}%` }}
                />
              </div>

              {/* Phase explanation */}
              <p className="text-xs text-aurora-text-muted">{telemetry.phase}</p>

              {/* 6-Stage Engineering Pipeline */}
              {telemetry.milestones?.length > 0 && (
                <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-6" aria-label="Étapes de conception">
                  {telemetry.milestones.map((m) => (
                    <div
                      key={m.id}
                      className={`rounded-lg border px-2.5 py-1.5 text-xs ${
                        m.done
                          ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200'
                          : m.active
                            ? 'border-aurora-accent bg-aurora-accent/15 font-semibold text-aurora-accent'
                            : 'border-aurora-border/40 bg-aurora-surface/40 text-aurora-text-dim'
                      }`}
                    >
                      <span>{m.done ? '✓ ' : m.active ? '● ' : '○ '}</span>
                      {m.label}
                    </div>
                  ))}
                </div>
              )}

              {/* Active Printer Profile & Workspace Files */}
              <div className="flex flex-wrap gap-2 text-xs text-aurora-text-muted">
                {telemetry.profile_summary?.bed_mm && (
                  <span className="rounded-lg border border-aurora-border/50 px-2 py-1">
                    Imprimante : {telemetry.profile_summary.name || telemetry.profile_summary.process || 'FDM'} (
                    {telemetry.profile_summary.bed_mm.join(' × ')} mm · jeu {telemetry.profile_summary.clearance_mm ?? 0.2} mm)
                  </span>
                )}
                <span className="rounded-lg border border-aurora-border/50 px-2 py-1">
                  Solides STL générés : {telemetry.stl_count}
                </span>
                {telemetry.criteria_count > 0 && (
                  <span className="rounded-lg border border-aurora-border/50 px-2 py-1">
                    Critères vérifiés : {telemetry.verified_count} / {telemetry.criteria_count}
                  </span>
                )}
              </div>

              {/* Live Engineering Criteria & Recent Actions */}
              {(telemetry.criteria.length > 0 || telemetry.recent_actions.length > 0 || telemetry.workspace_files.length > 0) && (
                <details className="rounded-xl border border-aurora-border/50 bg-aurora-surface/50 p-2.5 text-xs" open={['queued', 'planning', 'running'].includes(current.state)}>
                  <summary className="min-h-9 cursor-pointer font-medium text-aurora-text">
                    Suivi technique en direct (critères, opérations CAO et fichiers sur le PC)
                  </summary>
                  <div className="mt-2 space-y-2">
                    {telemetry.criteria.length > 0 && (
                      <div>
                        <p className="font-semibold text-aurora-text-muted">Critères de vérification :</p>
                        <ul className="mt-1 space-y-1">
                          {telemetry.criteria.map((c) => (
                            <li key={c.index} className={c.status === 'verified' ? 'text-emerald-300' : 'text-aurora-text-muted'}>
                              {c.status === 'verified' ? '✓' : '⋯'} {c.text}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {telemetry.recent_actions.length > 0 && (
                      <div>
                        <p className="font-semibold text-aurora-text-muted">Dernières opérations exécutées :</p>
                        <ul className="mt-1 space-y-1 font-mono text-[11px] text-aurora-text-muted">
                          {telemetry.recent_actions.map((a) => (
                            <li key={a.index} className="truncate">
                              [{a.kind}] {a.summary}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {telemetry.workspace_files.length > 0 && (
                      <p className="text-[11px] text-aurora-text-dim">
                        Fichiers dans le dossier : {telemetry.workspace_files.join(', ')}
                      </p>
                    )}
                  </div>
                </details>
              )}
            </div>
          )}

          {current.scheduling && ['queued', 'running'].includes(current.state) && (
            <p className="mt-2 text-aurora-text-muted">
              {current.state === 'queued'
                ? `Position ${current.scheduling.queue_position} · attente ${duration(current.scheduling.wait_seconds)} · durée indicative ${duration(current.scheduling.estimated_duration_seconds)}`
                : `Écoulé ${duration(current.scheduling.elapsed_seconds)} · restant ${duration(current.scheduling.remaining_seconds)}`}
            </p>
          )}

          {current.error && <p className="mt-2 text-red-400">{current.error}</p>}

          {/* Structured Engineering Inspector: Parts, Joints/DOF, BOM, Assembly Steps */}
          {draft && (
            <div className="mt-3 space-y-3 rounded-xl border border-aurora-border/60 bg-aurora-surface/60 p-3 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h4 className="text-sm font-semibold text-aurora-text">{draft.title || 'Architecture du projet'}</h4>
                  <p className="text-aurora-text-muted">
                    {draft.part_count} pièce(s) ({draft.printable_count} imprimable(s)
                    {draft.purchased_count > 0 ? `, ${draft.purchased_count} standard/achetée(s)` : ''}) ·{' '}
                    {draft.joint_count} liaison(s) mécanique(s)
                    {draft.dof !== null ? ` · ${draft.dof} degré(s) de liberté (DDL)` : ''}
                  </p>
                </div>
                {draft.feasibility && (
                  <span className="rounded-lg border border-aurora-border px-2.5 py-1 text-[11px] uppercase tracking-wider text-aurora-text-muted">
                    Faisabilité : {draft.feasibility}
                  </span>
                )}
              </div>

              {/* Parts table */}
              {draft.parts.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead>
                      <tr className="border-b border-aurora-border/50 text-aurora-text-muted">
                        <th className="py-1.5 pr-2">Pièce</th>
                        <th className="py-1.5 pr-2">Type / Matière</th>
                        <th className="py-1.5 pr-2">Dimensions (mm)</th>
                        <th className="py-1.5 pr-2">Volume</th>
                        <th className="py-1.5">Inspection</th>
                      </tr>
                    </thead>
                    <tbody>
                      {draft.parts.map((part) => (
                        <tr
                          key={part.id}
                          className={`border-b border-aurora-border/25 ${inspectedPartId === part.id ? 'bg-aurora-accent/15' : ''}`}
                        >
                          <td className="py-1.5 pr-2 font-medium text-aurora-text">
                            {part.id}
                            {part.name && part.name !== part.id ? ` — ${part.name}` : ''}
                          </td>
                          <td className="py-1.5 pr-2 text-aurora-text-muted">
                            {part.source === 'purchased' ? 'Composant standard' : part.filament || 'Impression 3D'}
                          </td>
                          <td className="py-1.5 pr-2 font-mono text-aurora-text">
                            {part.dimensions_mm ? part.dimensions_mm.map((v) => Number(v).toFixed(1)).join(' × ') : '—'}
                          </td>
                          <td className="py-1.5 pr-2 font-mono text-aurora-text-muted">
                            {part.volume_mm3 ? `${(part.volume_mm3 / 1000).toFixed(2)} cm³` : '—'}
                            {part.watertight === true ? ' ✓' : part.watertight === false ? ' ⚠' : ''}
                          </td>
                          <td className="py-1.5">
                            {current.viewer_url && (
                              <button
                                type="button"
                                onClick={() => handleInspectPart(part.id)}
                                className="rounded-lg border border-aurora-border px-2 py-1 text-[11px] text-aurora-accent hover:border-aurora-accent"
                              >
                                Inspecter en 3D
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Mechanical Joints */}
              {draft.joints.length > 0 && (
                <div>
                  <p className="font-semibold text-aurora-text">Liaisons cinématiques ({draft.joints.length}) :</p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {draft.joints.map((j) => (
                      <span key={j.id} className="rounded-lg border border-aurora-border/60 bg-aurora-surface-2 px-2 py-1 text-[11px]">
                        <strong>{j.id}</strong> ({j.type}) : {j.parent} → {j.child}
                        {j.limits ? ` [${j.limits[0]}..${j.limits[1]}]` : ''}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* BOM */}
              {bomList.length > 0 && (
                <div>
                  <p className="font-semibold text-aurora-text">Nomenclature & visserie / matériel (BOM) :</p>
                  <ul className="mt-1 space-y-1 text-aurora-text-muted">
                    {bomList.map((item, idx) => (
                      <li key={idx}>
                        • <strong>{item.quantity}× {item.name}</strong>
                        {item.specification ? ` — ${item.specification}` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Step-by-step Assembly Sequence */}
              {draft.assembly_steps.length > 0 && (
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold text-aurora-text">Séquence d’assemblage pas à pas :</p>
                    {current.viewer_url && activeStepIndex >= 0 && (
                      <button
                        type="button"
                        onClick={() => handleSelectStep(-1)}
                        className="rounded-lg border border-aurora-border px-2 py-1 text-[11px] text-aurora-accent"
                      >
                        Réafficher toutes les pièces
                      </button>
                    )}
                  </div>
                  <ol className="mt-1.5 space-y-1.5">
                    {draft.assembly_steps.map((stepText, idx) => (
                      <li
                        key={idx}
                        className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border px-2.5 py-1.5 ${
                          activeStepIndex === idx
                            ? 'border-aurora-accent bg-aurora-accent/15 text-aurora-text'
                            : 'border-aurora-border/40 bg-aurora-surface-2/50 text-aurora-text-muted'
                        }`}
                      >
                        <span>
                          <strong>Étape {idx + 1} :</strong> {stepText}
                        </span>
                        {current.viewer_url && (
                          <button
                            type="button"
                            onClick={() => handleSelectStep(idx)}
                            className="rounded-lg border border-aurora-border px-2 py-1 text-[11px] text-aurora-accent hover:border-aurora-accent"
                          >
                            Isoler l’étape en 3D
                          </button>
                        )}
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {/* Assumptions */}
              {assumptionsList.length > 0 && (
                <details className="text-aurora-text-muted">
                  <summary className="cursor-pointer font-medium">Hypothèses de calcul et tolérances ({assumptionsList.length})</summary>
                  <ul className="mt-1 space-y-1 pl-3">
                    {assumptionsList.map((a, i) => (
                      <li key={i}>• {a}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}

          {current.result && (
            <details className="mt-2">
              <summary className="min-h-11 cursor-pointer font-medium">Décisions et résultat de l’IA</summary>
              <pre className="mt-1 whitespace-pre-wrap break-words rounded-xl border border-aurora-border/40 bg-aurora-surface p-3 text-xs">
                {current.result}
              </pre>
            </details>
          )}

          <div className="mt-3 flex flex-wrap gap-2">
            {['interrupted', 'blocked', 'failed', 'stopped'].includes(current.state) && (
              <button
                type="button"
                className="min-h-11 rounded-lg border border-aurora-border px-3 py-2"
                onClick={() => void resume()}
                disabled={busy}
              >
                Reprendre ce projet et ses preuves
              </button>
            )}
            {['running', 'queued'].includes(current.state) && (
              <button
                type="button"
                className="min-h-11 rounded-lg border border-aurora-border px-3 py-2"
                onClick={() => void stopProject()}
                disabled={busy}
              >
                Suspendre / Arrêter
              </button>
            )}
            {['completed', 'failed', 'stopped', 'interrupted', 'blocked'].includes(current.state) && (
              <button
                type="button"
                className="min-h-11 rounded-lg border border-red-500/50 px-3 py-2 text-red-400"
                onClick={() => void deleteProject()}
                disabled={busy}
              >
                Supprimer ce projet
              </button>
            )}
          </div>

          {(current.ready || current.artifacts_available) && (
            <div className="mt-3 space-y-2 border-t border-aurora-border/50 pt-3">
              {current.partial && (
                <p className="text-amber-300">
                  Fichiers provisoires disponibles : la validation finale de la mission reste incomplète.
                </p>
              )}
              <button
                type="button"
                className="min-h-11 w-full rounded-xl border border-aurora-accent bg-aurora-accent/15 p-3 font-semibold text-aurora-accent"
                onClick={() => void download()}
              >
                {current.partial ? 'Télécharger les fichiers provisoires' : 'Télécharger les pièces et le dossier de montage'}
              </button>
              <div className="flex flex-wrap gap-3">
                {current.dossier_url && (
                  <a
                    className="flex min-h-11 items-center rounded-xl border border-aurora-border px-3 text-aurora-accent"
                    href={getBridgeUrl() + current.dossier_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Lire le dossier / enregistrer en PDF
                  </a>
                )}
                {current.viewer_url && (
                  <a
                    className="flex min-h-11 items-center rounded-xl border border-aurora-border px-3 text-aurora-accent"
                    href={getBridgeUrl() + current.viewer_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Ouvrir l’assemblage sur cet appareil
                  </a>
                )}
                {current.viewer_url && (
                  <button
                    type="button"
                    onClick={() => setShowEmbeddedViewer((v) => !v)}
                    className="min-h-11 rounded-xl border border-aurora-border px-3 text-xs text-aurora-text"
                  >
                    {showEmbeddedViewer ? 'Masquer l’aperçu 3D intégré' : 'Afficher l’aperçu 3D intégré'}
                  </button>
                )}
              </div>

              {current.viewer_url && showEmbeddedViewer && (
                <div className="mt-3 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      aria-pressed={!viewerExploded}
                      onClick={() => handleToggleExploded(false)}
                      className={`min-h-10 rounded-lg border px-3 text-xs ${
                        !viewerExploded
                          ? 'border-aurora-accent bg-aurora-accent/15 font-semibold text-aurora-accent'
                          : 'border-aurora-border text-aurora-text-muted'
                      }`}
                    >
                      Vue assemblée
                    </button>
                    <button
                      type="button"
                      aria-pressed={viewerExploded}
                      onClick={() => handleToggleExploded(true)}
                      className={`min-h-10 rounded-lg border px-3 text-xs ${
                        viewerExploded
                          ? 'border-aurora-accent bg-aurora-accent/15 font-semibold text-aurora-accent'
                          : 'border-aurora-border text-aurora-text-muted'
                      }`}
                    >
                      Vue éclatée
                    </button>
                    <button
                      type="button"
                      onClick={() => handleSelectStep(-1)}
                      className="min-h-10 rounded-lg border border-aurora-border px-3 text-xs text-aurora-text-muted hover:text-aurora-text"
                    >
                      Afficher toutes les pièces
                    </button>
                  </div>
                  <iframe
                    title="Viewer d’assemblage du projet"
                    ref={viewerIframeRef}
                    onLoad={() => {
                      postToViewer({ type: 'aurora-assembly-view', exploded: viewerExploded })
                      if (inspectedPartId) postToViewer({ type: 'aurora-assembly-inspect', part_id: inspectedPartId })
                      if (activeStepIndex >= 0) postToViewer({ type: 'aurora-assembly-step', step_index: activeStepIndex })
                    }}
                    className="h-[68dvh] min-h-[380px] w-full rounded-xl border border-aurora-border bg-black/40"
                    src={getBridgeUrl() + current.viewer_url}
                  />
                </div>
              )}

              {blockersList.map((b, i) => (
                <p key={i} className="mt-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-2 text-amber-300">
                  {b}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
