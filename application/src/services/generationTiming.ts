/**
 * Temps d'attente mesuré des générations, commun à tous les modules.
 *
 * Natif (Tauri) et web/tunnel partagent ce frontend : la même règle s'applique
 * aux deux. Le CLI possède ses propres estimations serveur (`scheduling`).
 *
 * Contrat : aucune durée n'est inventée. Une estimation ne provient que de :
 *  1. la vitesse mesurée d'un producteur fin (pas de diffusion k/N, pourcentage
 *     réellement calculé par un pipeline) ;
 *  2. l'historique local des runs comparables terminés (au moins
 *     MIN_COMPARABLE_RUNS, même module, même modèle si possible), avec la durée
 *     de chaque étape observée par l'écran de génération ;
 *  3. la médiane serveur des runs comparables du PC (`/api/projects/*`).
 * Sans ces mesures, l'état est « estimation en préparation » : jamais un
 * compte à rebours fabriqué. Une estimation reste indicative (complexité
 * variable des demandes, charge du PC) ; l'intervalle affiché le rappelle.
 */

export const MIN_COMPARABLE_RUNS = 3
export const TIMING_STORAGE_KEY = 'aurora.generation-timing.v1'
const MAX_RUNS_PER_KEY = 24
const MAX_KEYS = 80
const RECENT_RUNS = 12
const MIN_RUN_MS = 800
const MAX_RUN_MS = 36 * 3600 * 1000

export type TimingRun = {
  /** identifiant du job (déduplication) */
  id?: string
  totalMs: number
  /** durée observée de chaque étape de l'écran de génération (index = étape) */
  phaseMs?: number[]
  at: number
}

type TimingStore = { v: 1; runs: Record<string, TimingRun[]> }

export type StorageLike = Pick<Storage, 'getItem' | 'setItem'>

function defaultStorage(): StorageLike | null {
  try {
    return typeof window !== 'undefined' && window.localStorage ? window.localStorage : null
  } catch {
    return null
  }
}

function readStore(storage: StorageLike | null): TimingStore {
  if (!storage) return { v: 1, runs: {} }
  try {
    const raw = storage.getItem(TIMING_STORAGE_KEY)
    if (!raw) return { v: 1, runs: {} }
    const parsed = JSON.parse(raw) as TimingStore
    if (!parsed || parsed.v !== 1 || !parsed.runs || typeof parsed.runs !== 'object') return { v: 1, runs: {} }
    return parsed
  } catch {
    return { v: 1, runs: {} }
  }
}

function writeStore(storage: StorageLike | null, store: TimingStore): void {
  try {
    storage?.setItem(TIMING_STORAGE_KEY, JSON.stringify(store))
  } catch {
    // quota ou navigation privée : l'estimation reste « en préparation »
  }
}

export function timingKey(module: string, model?: string | null): string {
  const m = (model || '').trim().toLowerCase()
  return `${module}|${m || '*'}`
}

function validDuration(ms: unknown): ms is number {
  return typeof ms === 'number' && Number.isFinite(ms) && ms >= MIN_RUN_MS && ms <= MAX_RUN_MS
}

/** Enregistre un run terminé avec succès. Retourne false si rejeté ou déjà connu. */
export function recordCompletedRun(
  module: string,
  model: string | null | undefined,
  run: TimingRun,
  storage: StorageLike | null = defaultStorage(),
): boolean {
  if (!validDuration(run.totalMs)) return false
  const store = readStore(storage)
  if (run.id && Object.values(store.runs).some((list) => list.some((r) => r.id === run.id))) return false
  const phaseMs =
    Array.isArray(run.phaseMs) && run.phaseMs.length > 0 && run.phaseMs.every((v) => Number.isFinite(v) && v >= 0)
      ? run.phaseMs.map((v) => Math.round(v))
      : undefined
  const key = timingKey(module, model)
  const list = store.runs[key] ?? []
  list.push({ id: run.id, totalMs: Math.round(run.totalMs), phaseMs, at: Number.isFinite(run.at) ? run.at : Date.now() })
  store.runs[key] = list.slice(-MAX_RUNS_PER_KEY)
  const keys = Object.keys(store.runs)
  if (keys.length > MAX_KEYS) {
    const lastAt = (k: string) => {
      const rs = store.runs[k]
      return rs.length ? rs[rs.length - 1].at : 0
    }
    keys.sort((a, b) => lastAt(a) - lastAt(b))
    for (const k of keys.slice(0, keys.length - MAX_KEYS)) delete store.runs[k]
  }
  writeStore(storage, store)
  return true
}

export type HistoryBasis = 'model' | 'module' | 'none'
export type ComparableRuns = { runs: TimingRun[]; basis: HistoryBasis }

/**
 * Runs comparables : même module et même modèle si au moins
 * MIN_COMPARABLE_RUNS existent, sinon même module (modèles confondus).
 */
export function comparableRuns(
  module: string,
  model?: string | null,
  storage: StorageLike | null = defaultStorage(),
): ComparableRuns {
  const store = readStore(storage)
  const own = model ? store.runs[timingKey(module, model)] ?? [] : []
  if (own.length >= MIN_COMPARABLE_RUNS) return { runs: own.slice(), basis: 'model' }
  const prefix = `${module}|`
  const all = Object.entries(store.runs)
    .filter(([k]) => k.startsWith(prefix))
    .flatMap(([, rs]) => rs)
    .sort((a, b) => a.at - b.at)
    .slice(-MAX_RUNS_PER_KEY)
  if (all.length >= MIN_COMPARABLE_RUNS) return { runs: all, basis: 'module' }
  return { runs: all, basis: 'none' }
}

export type Summary = { n: number; median: number; q1: number; q3: number; min: number; max: number }

export function quantile(sorted: number[], q: number): number {
  if (!sorted.length) return Number.NaN
  const pos = (sorted.length - 1) * Math.max(0, Math.min(1, q))
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo)
}

export function summarize(values: number[]): Summary | null {
  const v = values.filter((x) => Number.isFinite(x)).sort((a, b) => a - b)
  if (!v.length) return null
  return { n: v.length, median: quantile(v, 0.5), q1: quantile(v, 0.25), q3: quantile(v, 0.75), min: v[0], max: v[v.length - 1] }
}

/** Échantillon de progression mesurée : f est une fraction 0..1 de l'unité mesurée. */
export type LiveSample = { t: number; f: number }

export type MeasuredRate = {
  /** fraction par milliseconde */
  rate: number
  fLast: number
  tLast: number
  spanMs: number
  n: number
}

/**
 * Vitesse mesurée par moindres carrés sur les échantillons récents.
 * Exige au moins deux mesures, 3 s d'écart et 2 % d'avancement réel.
 */
export function measuredRate(samples: LiveSample[] | undefined, now: number): MeasuredRate | null {
  if (!samples || samples.length < 2) return null
  const recent = samples
    .filter((s) => Number.isFinite(s.t) && Number.isFinite(s.f) && s.t <= now + 1000 && now - s.t <= 240_000)
    .slice(-24)
  if (recent.length < 2) return null
  const first = recent[0]
  const last = recent[recent.length - 1]
  const spanMs = last.t - first.t
  if (spanMs < 3000 || last.f - first.f < 0.02) return null
  const n = recent.length
  let st = 0
  let sf = 0
  let stt = 0
  let stf = 0
  for (const s of recent) {
    const t = s.t - first.t
    st += t
    sf += s.f
    stt += t * t
    stf += t * s.f
  }
  const denom = n * stt - st * st
  let rate = denom > 0 ? (n * stf - st * sf) / denom : (last.f - first.f) / spanMs
  // les moindres carrés peuvent sous-estimer après un palier ; la vitesse
  // moyenne entre extrémités reste une mesure réelle
  const meanRate = (last.f - first.f) / spanMs
  if (!(rate > 0)) rate = meanRate
  rate = Math.max(rate, meanRate * 0.5)
  if (!(rate > 0)) return null
  return { rate, fLast: Math.min(1, Math.max(0, last.f)), tLast: last.t, spanMs, n }
}

/** Temps restant pour finir l'unité mesurée, décompté depuis le dernier échantillon. */
export function remainingFromRate(r: MeasuredRate, now: number): number {
  return Math.max(0, (1 - r.fLast) / r.rate - Math.max(0, now - r.tLast))
}

export type ServerEstimate = {
  medianTotalSec: number | null
  remainingSec?: number | null
  sampleCount: number
}

export type QueueInfo = { position: number; aheadCount: number; waitSec: number | null }

export type EtaInput = {
  now: number
  /** début réel du calcul (admission accordée) ; null si encore en file */
  runStartedAt: number | null
  phaseIdx?: number | null
  phaseCount?: number | null
  phaseStartedAt?: number | null
  /** progression fine de l'ensemble du run */
  overall?: LiveSample[]
  /** progression fine de l'étape en cours uniquement */
  phase?: LiveSample[]
  runs: TimingRun[]
  historyBasis: HistoryBasis
  server?: ServerEstimate | null
  queue?: QueueInfo | null
  done?: boolean
}

export type EtaState = 'done' | 'queued' | 'estimating' | 'partial' | 'live' | 'history' | 'blended' | 'overdue'

export type EtaEstimate = {
  state: EtaState
  remainingMs: number | null
  lowMs: number | null
  highMs: number | null
  /** durée totale habituelle (médiane) quand elle est connue */
  expectedTotalMs: number | null
  confidence: number
  /** nombre de runs comparables mesurés (local ou serveur) */
  sampleCount: number
  /** sur quoi repose l'estimation, en français */
  basis: string
}

type Range = { mid: number; lo: number; hi: number }

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))

function basisLabel(basis: HistoryBasis, n: number): string {
  if (basis === 'model') return `médiane de ${n} runs mesurés (même modèle)`
  if (basis === 'module') return `médiane de ${n} runs mesurés du module`
  return `${n} run(s) mesuré(s)`
}

/**
 * Estime le temps restant d'un run en cours.
 * Les durées par étape (si l'historique les contient) priment sur la durée
 * totale ; une vitesse mesurée affine l'étape en cours ou le run entier.
 */
export function estimateRemaining(input: EtaInput): EtaEstimate {
  const now = input.now
  const recent = input.runs.slice(-RECENT_RUNS)
  const localTotals = recent.length >= MIN_COMPARABLE_RUNS ? summarize(recent.map((r) => r.totalMs)) : null
  const server =
    input.server && input.server.medianTotalSec != null && Number.isFinite(input.server.medianTotalSec) &&
    input.server.sampleCount >= MIN_COMPARABLE_RUNS
      ? input.server
      : null
  const sampleCount = Math.max(recent.length, server?.sampleCount ?? 0)
  const expectedTotalMs = localTotals ? localTotals.median : server ? (server.medianTotalSec as number) * 1000 : null

  if (input.done) {
    return { state: 'done', remainingMs: 0, lowMs: 0, highMs: 0, expectedTotalMs, confidence: 1, sampleCount, basis: 'Terminé' }
  }

  if (input.runStartedAt == null) {
    const waitMs = input.queue?.waitSec != null && Number.isFinite(input.queue.waitSec) ? input.queue.waitSec * 1000 : null
    return {
      state: 'queued',
      remainingMs: waitMs,
      lowMs: null,
      highMs: null,
      expectedTotalMs,
      confidence: waitMs != null ? 0.4 : 0,
      sampleCount,
      basis: waitMs != null
        ? 'attente calculée par le PC d’après les projets devant'
        : input.queue
          ? 'attente non estimée : durées des projets devant pas encore mesurées'
          : 'en attente du démarrage',
    }
  }

  const elapsed = Math.max(0, now - input.runStartedAt)

  // 1) Historique par étape
  let phaseRange: (Range & { n: number; overdue: boolean }) | null = null
  const phaseCount = input.phaseCount ?? 0
  const phaseIdx = input.phaseIdx ?? null
  const phaseLive = measuredRate(input.phase, now)
  if (phaseCount > 0 && phaseIdx != null && input.phaseStartedAt != null) {
    const withPhases = recent.filter((r) => Array.isArray(r.phaseMs) && r.phaseMs.length === phaseCount)
    if (withPhases.length >= MIN_COMPARABLE_RUNS) {
      const stats = Array.from({ length: phaseCount }, (_, j) => summarize(withPhases.map((r) => (r.phaseMs as number[])[j])))
      const inPhase = Math.max(0, now - input.phaseStartedAt)
      const cur = stats[phaseIdx]
      let curMid = 0
      let curLo = 0
      let curHi = 0
      let overdue = false
      if (cur) {
        const histMid = Math.max(0, cur.median - inPhase)
        const histLo = Math.max(0, cur.q1 - inPhase)
        const histHi = Math.max(histMid, cur.q3 - inPhase)
        if (phaseLive) {
          const live = remainingFromRate(phaseLive, now)
          const w = clamp(phaseLive.fLast * 1.2, 0.3, 0.9)
          curMid = w * live + (1 - w) * histMid
          curLo = w * live * 0.8 + (1 - w) * histLo
          curHi = w * live * 1.3 + (1 - w) * histHi
        } else {
          curMid = histMid
          curLo = histLo
          curHi = histHi
          overdue = inPhase > cur.q3 * 1.5 + 5000
        }
      }
      let mid = curMid
      let lo = curLo
      let hi = curHi
      for (let j = phaseIdx + 1; j < phaseCount; j++) {
        const s = stats[j]
        if (!s) continue
        mid += s.median
        lo += s.q1
        hi += s.q3
      }
      phaseRange = { mid, lo, hi, n: withPhases.length, overdue }
    }
  }

  // 2) Historique de la durée totale (local, sinon serveur)
  let totalRange: (Range & { n: number }) | null = null
  if (localTotals) {
    totalRange = { mid: localTotals.median - elapsed, lo: localTotals.q1 - elapsed, hi: localTotals.q3 - elapsed, n: localTotals.n }
  } else if (server) {
    const total = (server.medianTotalSec as number) * 1000
    const serverRemaining =
      server.remainingSec != null && Number.isFinite(server.remainingSec) ? server.remainingSec * 1000 : total - elapsed
    totalRange = { mid: serverRemaining, lo: serverRemaining - total * 0.25, hi: serverRemaining + total * 0.3, n: server.sampleCount }
  }

  // 3) Vitesse mesurée du run entier
  const overallLive = measuredRate(input.overall, now)
  let liveRange: Range | null = null
  if (overallLive && overallLive.fLast >= 0.04) {
    const rem = remainingFromRate(overallLive, now)
    const spread = 0.15 + 0.45 * (1 - overallLive.fLast)
    liveRange = { mid: rem, lo: rem * (1 - spread * 0.6), hi: rem * (1 + spread) }
  }

  // L'étape en cours mesurée borne par le bas une estimation fondée sur la
  // seule durée totale : il reste au moins la fin de cette étape.
  if (!phaseRange && totalRange && phaseLive) {
    const floor = remainingFromRate(phaseLive, now)
    totalRange = { ...totalRange, mid: Math.max(totalRange.mid, floor), lo: Math.max(totalRange.lo, floor), hi: Math.max(totalRange.hi, floor) }
  }

  const base = phaseRange ?? totalRange
  const histBasis = phaseRange
    ? `${basisLabel(input.historyBasis, phaseRange.n)}, par étape`
    : localTotals
      ? basisLabel(input.historyBasis, localTotals.n)
      : server
        ? `médiane de ${server.sampleCount} runs comparables mesurés par le PC`
        : ''
  const histConfidence = base
    ? clamp(0.3 + 0.05 * (phaseRange?.n ?? totalRange?.n ?? 0), 0.3, 0.8) * (input.historyBasis === 'module' && !server ? 0.8 : 1)
    : 0

  const finish = (state: EtaState, r: Range, confidence: number, basis: string): EtaEstimate => {
    const mid = Math.max(0, r.mid)
    const lo = clamp(r.lo, 0, mid)
    const hi = Math.max(mid, r.hi)
    return { state, remainingMs: mid, lowMs: lo, highMs: hi, expectedTotalMs, confidence: clamp(confidence, 0, 0.95), sampleCount, basis }
  }

  if (liveRange && base) {
    const f = overallLive ? overallLive.fLast : 0
    const w = clamp((f - 0.05) / 0.6, 0.15, 0.85)
    const r: Range = {
      mid: w * liveRange.mid + (1 - w) * Math.max(0, base.mid),
      lo: w * liveRange.lo + (1 - w) * Math.max(0, base.lo),
      hi: w * liveRange.hi + (1 - w) * Math.max(0, base.hi),
    }
    if (liveRange.mid <= 0 && base.hi <= 0) {
      return { state: 'overdue', remainingMs: null, lowMs: null, highMs: null, expectedTotalMs, confidence: 0.2, sampleCount, basis: 'au-delà de la vitesse mesurée et de l’historique' }
    }
    return finish('blended', r, Math.max(histConfidence, 0.4 + 0.5 * f), `vitesse mesurée + ${histBasis}`)
  }
  if (liveRange) {
    if (liveRange.mid <= 0) {
      return { state: 'overdue', remainingMs: null, lowMs: null, highMs: null, expectedTotalMs, confidence: 0.2, sampleCount, basis: 'dernières opérations au-delà de la vitesse mesurée' }
    }
    const f = overallLive ? overallLive.fLast : 0
    return finish('live', liveRange, 0.35 + 0.5 * f, 'vitesse réelle mesurée pendant ce run')
  }
  if (base) {
    const phaseOverdue = phaseRange?.overdue ?? false
    if (base.hi <= 0 || phaseOverdue) {
      return { state: 'overdue', remainingMs: null, lowMs: null, highMs: null, expectedTotalMs, confidence: 0.15, sampleCount, basis: `plus long que d’habitude (${histBasis})` }
    }
    if (base.mid <= 0) {
      // entre la médiane et le 3e quartile : borne haute seulement
      return finish('history', { mid: base.hi, lo: 0, hi: base.hi }, histConfidence * 0.7, `${histBasis} · au-delà de la médiane`)
    }
    return finish('history', base, histConfidence, histBasis)
  }
  if (phaseLive) {
    // étape en cours mesurée, étapes suivantes inconnues : borne basse seulement
    const rem = remainingFromRate(phaseLive, now)
    return { state: 'partial', remainingMs: rem, lowMs: rem, highMs: null, expectedTotalMs, confidence: 0.25, sampleCount, basis: 'étape en cours mesurée ; étapes suivantes pas encore mesurées' }
  }
  return {
    state: 'estimating',
    remainingMs: null,
    lowMs: null,
    highMs: null,
    expectedTotalMs,
    confidence: 0,
    sampleCount,
    basis: `estimation en préparation (${Math.min(sampleCount, MIN_COMPARABLE_RUNS)}/${MIN_COMPARABLE_RUNS} runs comparables mesurés)`,
  }
}

/** Durée lisible pour une attente : arrondie, jamais faussement précise. */
export function formatWait(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 10) return 'quelques secondes'
  if (s < 60) return `${Math.max(10, Math.round(s / 5) * 5)} s`
  if (s < 600) {
    const m = Math.floor(s / 60)
    const r = Math.round((s % 60) / 10) * 10
    if (r === 60) return `${m + 1} min`
    return r ? `${m} min ${r} s` : `${m} min`
  }
  if (s < 3600) return `${Math.round(s / 60)} min`
  const h = Math.floor(s / 3600)
  const m = Math.round((s % 3600) / 60)
  if (m === 60) return `${h + 1} h`
  return `${h} h ${String(m).padStart(2, '0')}`
}

/** Chronomètre exact (secondes visibles). */
export function formatClock(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  if (s < 60) return `${s} s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m} min ${String(s % 60).padStart(2, '0')} s`
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')} min`
}

/** Libellé court du temps restant pour un HUD. */
export function etaHeadline(est: EtaEstimate, shownRemainingMs?: number | null, queue?: QueueInfo | null): string {
  const rem = shownRemainingMs ?? est.remainingMs
  switch (est.state) {
    case 'done':
      return 'Terminé'
    case 'queued': {
      const pos = queue ? `En file · position ${queue.position}` : 'En attente de démarrage'
      return rem != null ? `${pos} · attente ≈ ${formatWait(rem)}` : pos
    }
    case 'estimating':
      return `Estimation en préparation (${Math.min(est.sampleCount, MIN_COMPARABLE_RUNS)}/${MIN_COMPARABLE_RUNS} runs mesurés)`
    case 'partial':
      return rem != null ? `≥ ${formatWait(rem)} (étape en cours mesurée)` : 'Étape en cours mesurée'
    case 'overdue':
      return est.expectedTotalMs != null
        ? `Plus long que d’habitude (médiane ${formatWait(est.expectedTotalMs)})`
        : 'Dernières opérations en cours'
    default:
      return rem != null ? `≈ ${formatWait(rem)}` : 'Estimation en préparation'
  }
}

/** Intervalle lisible (« entre 1 min 40 s et 2 min 50 s »), ou null. */
export function etaInterval(est: EtaEstimate): string | null {
  if (est.lowMs == null || est.highMs == null) return null
  if (!['history', 'blended', 'live'].includes(est.state)) return null
  const lo = formatWait(est.lowMs)
  const hi = formatWait(est.highMs)
  return lo === hi ? null : `${lo} – ${hi}`
}

/**
 * Compte à rebours lissé : décompte une seconde par seconde et ne se recale que
 * si l'estimation change nettement — évite un affichage qui saute à chaque mesure.
 */
export class EtaCountdown {
  private anchorMs: number | null = null
  private anchorAt = 0

  update(est: EtaEstimate, now: number): number | null {
    if (est.remainingMs == null) {
      this.anchorMs = null
      return null
    }
    const target = est.remainingMs
    const shown = this.anchorMs == null ? null : Math.max(0, this.anchorMs - (now - this.anchorAt))
    if (shown == null || Math.abs(target - shown) > Math.max(5000, target * 0.15) || (shown === 0 && target > 0)) {
      this.anchorMs = target
      this.anchorAt = now
      return target
    }
    return shown
  }
}

/**
 * Valeur lissée déterministe : fonction pure du temps entre deux mesures,
 * lue à l'identique par le HUD et par l'animation (même valeur au même instant).
 */
export class SmoothValue {
  private from = 0
  private target = 0
  private changedAt = 0
  private readonly tauMs: number

  constructor(initial = 0, tauMs = 650) {
    this.from = initial
    this.target = initial
    this.tauMs = tauMs
  }

  set(target: number, now: number): void {
    if (target === this.target) return
    this.from = this.valueAt(now)
    this.target = target
    this.changedAt = now
  }

  valueAt(now: number): number {
    const dt = Math.max(0, now - this.changedAt)
    return this.target - (this.target - this.from) * Math.exp(-dt / this.tauMs)
  }

  get goal(): number {
    return this.target
  }
}

/**
 * Chronologie d'une session de génération : étapes réellement observées,
 * progression mesurée, événements. Sert à la fois à l'estimation, à
 * l'enregistrement des durées par étape et à la synchronisation des animations.
 */
export class RunTimeline {
  readonly startedAt: number
  readonly phaseCount: number
  phaseIdx = 0
  phaseStartedAt: number
  private readonly phaseAccum: number[]
  readonly overall: LiveSample[] = []
  phase: LiveSample[] = []
  measured = false
  lastMeasured: number | null = null
  lastEventAt: number
  lastPhaseChangeAt: number
  eventCount = 0
  readonly display: SmoothValue

  constructor(startedAt: number, phaseCount: number) {
    this.startedAt = startedAt
    this.phaseCount = Math.max(1, phaseCount)
    this.phaseStartedAt = startedAt
    this.lastEventAt = startedAt
    this.lastPhaseChangeAt = startedAt
    this.phaseAccum = new Array(this.phaseCount).fill(0)
    this.display = new SmoothValue(0)
  }

  /** Change d'étape ; retourne true si l'étape a réellement changé. */
  notePhase(idx: number, now: number): boolean {
    const next = clamp(Math.round(idx), 0, this.phaseCount - 1)
    if (next === this.phaseIdx) return false
    this.phaseAccum[this.phaseIdx] += Math.max(0, now - this.phaseStartedAt)
    this.phaseIdx = next
    this.phaseStartedAt = now
    this.lastPhaseChangeAt = now
    this.phase = []
    return true
  }

  /**
   * Progression mesurée de l'ensemble (0..1). Une régression nette (nouvelle
   * passe) est acceptée ; un léger recul de mesure ne fait pas reculer l'affichage.
   */
  noteProgress(p: number, now: number, fine: boolean): void {
    if (!Number.isFinite(p)) return
    const v = clamp(p, 0, 1)
    this.measured = true
    const prev = this.lastMeasured
    this.lastMeasured = v
    const goal = prev != null && v < prev && prev - v < 0.2 ? Math.max(v, this.display.goal) : v
    this.display.set(goal, now)
    if (fine) {
      this.overall.push({ t: now, f: v })
      if (this.overall.length > 64) this.overall.splice(0, this.overall.length - 64)
    }
  }

  /** Progression fine à l'intérieur de l'étape en cours (ex. pas de diffusion). */
  notePhaseFraction(f: number, now: number): void {
    if (!Number.isFinite(f)) return
    this.phase.push({ t: now, f: clamp(f, 0, 1) })
    if (this.phase.length > 64) this.phase.splice(0, this.phase.length - 64)
  }

  noteEvent(now: number): void {
    this.lastEventAt = now
    this.eventCount += 1
  }

  /** Durées par étape, étape courante comprise jusqu'à `now`. */
  phaseDurations(now: number): number[] {
    const out = this.phaseAccum.slice()
    out[this.phaseIdx] += Math.max(0, now - this.phaseStartedAt)
    return out
  }

  progressAt(now: number): number {
    return clamp(this.display.valueAt(now), 0, 1)
  }
}
