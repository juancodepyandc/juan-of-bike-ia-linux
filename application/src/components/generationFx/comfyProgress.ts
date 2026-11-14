/**
 * Progression réelle de ComfyUI (WebSocket).
 *
 * Lit tous les événements utiles d'une exécution : file d'attente, nœud en cours
 * (chargement du modèle, encodage du texte, diffusion, décodage, super-résolution,
 * enregistrement), pas de diffusion k/N du nœud échantillonneur, fin et erreur.
 * Le module qui soumet un graphe l'enregistre (`registerComfyRun`) : les messages
 * d'une autre exécution sont ignorés et chaque nœud est classé d'après son vrai type.
 *
 * Les aperçus latents (trames binaires) sont conservés quand ComfyUI en envoie
 * (option `--preview-method` du serveur) : la scène image les montre tels quels.
 * Sans aperçu, rien n'est inventé à leur place.
 */
import {
  COMFY_STAGE_LABEL,
  interpretComfyMessage,
  nodeClassesOf,
  stageRank,
  type ComfyLiveEvent,
  type ComfyRunInfo,
  type ComfyStage,
} from './comfyStages.ts'

export type { ComfyLiveEvent, ComfyRunInfo, ComfyStage } from './comfyStages.ts'

/** Mesure transmise à l'écran (compatibilité : pas k/N et jalon de fin de nœud). */
export type ComfyMeasure = {
  step?: number
  max?: number
  phaseFraction?: number
  executedNode?: string
}

export type ComfyLiveState = {
  promptId: string | null
  module: string | null
  stage: ComfyStage
  label: string
  step: number
  max: number
  /** instants des pas reçus (vitesse réelle de diffusion) */
  stepTimes: number[]
  subStep: number
  subMax: number
  queueRemaining: number
  /** URL objet du dernier aperçu latent reçu (null si ComfyUI n'en envoie pas) */
  previewUrl: string | null
  previewAt: number
  previewCount: number
  stageAt: number
  /** instant (Date.now) de l'enregistrement du graphe suivi */
  runAt: number
  /** début et fin réels observés de chaque sous-étape du graphe suivi */
  stageTimes: Partial<Record<ComfyStage, { start: number; end?: number }>>
  updatedAt: number
  connected: boolean
  error: string | null
}

const live: ComfyLiveState = {
  promptId: null, module: null, stage: 'queued', label: COMFY_STAGE_LABEL.queued,
  step: 0, max: 0, stepTimes: [], subStep: 0, subMax: 0, queueRemaining: 0,
  previewUrl: null, previewAt: 0, previewCount: 0, stageAt: 0, runAt: 0, stageTimes: {}, updatedAt: 0, connected: false, error: null,
}

const runs = new Map<string, ComfyRunInfo>()
let activeRunId: string | null = null

/** État courant lu à chaque image par la scène (objet partagé, ne pas modifier). */
export function readComfyLive(): Readonly<ComfyLiveState> {
  return live
}

function resetLive(run: ComfyRunInfo | null) {
  if (live.previewUrl) {
    try { URL.revokeObjectURL(live.previewUrl) } catch { /* ignore */ }
  }
  const now = Date.now()
  Object.assign(live, {
    promptId: run?.promptId ?? null, module: run?.module ?? null, stage: 'queued' as ComfyStage,
    label: COMFY_STAGE_LABEL.queued, step: 0, max: 0, stepTimes: [], subStep: 0, subMax: 0,
    queueRemaining: 0, previewUrl: null, previewAt: 0, previewCount: 0, stageAt: now, runAt: run ? now : 0, stageTimes: run ? { queued: { start: now } } : {}, updatedAt: now, error: null,
  })
}

/**
 * Déclare le graphe qui vient d'être soumis à ComfyUI (avant le premier pas).
 * `phaseIndex` : étape de l'écran pendant sa diffusion (Diffusion FLUX ou Édition Kontext).
 */
export function registerComfyRun(input: { promptId: string; module: string; workflow: unknown; phaseIndex: number; batchLabel?: string }): void {
  if (!input.promptId) return
  const run: ComfyRunInfo = {
    promptId: input.promptId,
    module: input.module,
    phaseIndex: input.phaseIndex,
    nodeClass: nodeClassesOf(input.workflow),
    batchLabel: input.batchLabel,
  }
  runs.set(run.promptId, run)
  if (runs.size > 12) runs.delete(runs.keys().next().value as string)
  activeRunId = run.promptId
  resetLive(run)
  for (const l of runListeners) l(run)
}

export function activeComfyRun(): ComfyRunInfo | null {
  return activeRunId ? runs.get(activeRunId) ?? null : null
}

const runListeners = new Set<(run: ComfyRunInfo) => void>()
export function onComfyRunRegistered(cb: (run: ComfyRunInfo) => void): () => void {
  runListeners.add(cb)
  return () => { runListeners.delete(cb) }
}

function applyEvent(ev: ComfyLiveEvent, now: number) {
  if (ev.stage !== live.stage && (stageRank(ev.stage) >= stageRank(live.stage) || ev.stage === 'error')) {
    const prev = live.stageTimes[live.stage]
    if (prev && prev.end == null) prev.end = now
    if (!live.stageTimes[ev.stage]) live.stageTimes[ev.stage] = { start: now }
    live.stage = ev.stage
    live.stageAt = now
  }
  live.label = ev.label
  if (typeof ev.step === 'number' && typeof ev.max === 'number') {
    if (ev.step !== live.step) {
      live.stepTimes.push(now)
      if (live.stepTimes.length > 200) live.stepTimes.shift()
    }
    live.step = ev.step
    live.max = ev.max
  }
  if (typeof ev.subStep === 'number') { live.subStep = ev.subStep; live.subMax = ev.subMax ?? 0 }
  if (typeof ev.queueRemaining === 'number') live.queueRemaining = ev.queueRemaining
  if (ev.error) live.error = ev.error
  live.updatedAt = now
}

function handlePreview(buf: ArrayBuffer) {
  // trame binaire ComfyUI : uint32 type d'événement (1 = aperçu, 4 = aperçu + métadonnées), puis l'image
  if (buf.byteLength < 9) return
  const view = new DataView(buf)
  const event = view.getUint32(0)
  let offset = 8
  let mime = view.getUint32(4) === 2 ? 'image/png' : 'image/jpeg'
  if (event === 4) {
    const metaLen = view.getUint32(4)
    try {
      const meta = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 8, metaLen))) as { prompt_id?: string; image_type?: string }
      if (meta.prompt_id && activeRunId && meta.prompt_id !== activeRunId) return
      if (meta.image_type) mime = meta.image_type
    } catch { /* métadonnées illisibles : aperçu gardé */ }
    offset = 8 + metaLen
  } else if (event !== 1) {
    return
  }
  if (!activeRunId) return
  const blob = new Blob([new Uint8Array(buf, offset)], { type: mime })
  const prev = live.previewUrl
  live.previewUrl = URL.createObjectURL(blob)
  live.previewAt = Date.now()
  live.previewCount += 1
  live.updatedAt = live.previewAt
  if (prev) setTimeout(() => { try { URL.revokeObjectURL(prev) } catch { /* ignore */ } }, 1500)
}

function comfyWsCandidates(): string[] {
  const out: string[] = []
  try {
    const stored = window.localStorage.getItem('aurora-comfy-url')
    if (stored) out.push(stored.replace(/^http/, 'ws').replace(/\/$/, ''))
  } catch { /* ignore */ }
  out.push('ws://127.0.0.1:8188')
  // web / tunnel : le navigateur n'atteint pas 127.0.0.1 du PC ; le serveur de la page peut relayer /ws
  try {
    const host = window.location.host
    if (host && !/^(127\.0\.0\.1|localhost)(:|$)/.test(host)) {
      out.push(`${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${host}`)
    }
  } catch { /* ignore */ }
  return Array.from(new Set(out))
}

type LiveCb = (ev: ComfyLiveEvent, run: ComfyRunInfo | null, measure: ComfyMeasure) => void

export function watchComfyProgress(onEvent: LiveCb): () => void {
  if (typeof window === 'undefined' || typeof WebSocket === 'undefined') return () => {}
  let ws: WebSocket | null = null
  let closed = false
  let lastLoggedStep = -1
  let candidateIdx = 0
  let retry: ReturnType<typeof setTimeout> | null = null
  const candidates = comfyWsCandidates()

  const connect = () => {
    if (closed) return
    const base = candidates[candidateIdx % candidates.length]
    let opened = false
    try {
      ws = new WebSocket(`${base}/ws?clientId=aurora-fx-${Math.random().toString(36).slice(2, 10)}`)
      ws.binaryType = 'arraybuffer'
    } catch {
      ws = null
    }
    if (!ws) return
    ws.onopen = () => { opened = true; live.connected = true }
    ws.onmessage = (msgEv) => {
      if (closed) return
      if (msgEv.data instanceof ArrayBuffer) { handlePreview(msgEv.data); return }
      if (typeof msgEv.data !== 'string') return
      let msg: { type?: string; data?: Record<string, unknown> }
      try { msg = JSON.parse(msgEv.data) } catch { return }
      const run = activeComfyRun()
      if (msg.type === 'execution_start' && run && msg.data?.prompt_id === run.promptId) lastLoggedStep = -1
      const ev = interpretComfyMessage(msg, run, { stage: live.stage, lastLoggedStep })
      if (!ev) return
      if (ev.log && typeof ev.step === 'number') lastLoggedStep = ev.step
      applyEvent(ev, Date.now())
      const measure: ComfyMeasure = {
        step: ev.step,
        max: ev.max,
        phaseFraction: typeof ev.step === 'number' && ev.max ? ev.step / ev.max : undefined,
        executedNode: ev.stage === 'save' ? String(msg.data?.node ?? '') : undefined,
      }
      onEvent(ev, run, measure)
    }
    ws.onclose = () => {
      live.connected = false
      if (closed) return
      // candidat suivant si celui-ci n'a jamais ouvert ; reconnexion sinon
      if (!opened) candidateIdx += 1
      // un tour complet sans connexion : on attend avant de réessayer (ComfyUI pas encore lancé)
      const fullCycle = !opened && candidateIdx % candidates.length === 0
      retry = setTimeout(connect, opened ? 1500 : fullCycle ? 5000 : 400)
    }
    ws.onerror = () => { /* onclose suit : candidat suivant ou reconnexion */ }
  }
  connect()
  return () => {
    closed = true
    if (retry) clearTimeout(retry)
    try { ws?.close() } catch { /* ignore */ }
  }
}
