/**
 * Reading of the professor autopilot status (GET /api/professor/autopilot) for the interface.
 *
 * Pure functions: no fetch, no React. The bridge returns what
 * `python -m auto_rl.professor.autopilot status` prints; this module turns it into French labels and the
 * buttons that make sense. A number that was not measured is shown as « non mesuré », never as 0.
 */

export type ProfessorPhase =
  | 'new' | 'ready' | 'diagnosing' | 'diagnosed' | 'training' | 'trained' | 'examining'
  | 'waiting_quota' | 'stalled'

export interface ProfessorHistoryEntry {
  cycle: number
  at?: number
  verdict?: string | null
  problems?: string[]
  macro_gain?: number | null
  installed?: boolean
  activated?: boolean
  deployment?: string | null
}

export interface ProfessorStudent {
  phase: ProfessorPhase | string
  cycle: number | null
  best_cycle: number | null
  installed_cycle: number | null
  kernel: string | null
  until: number | null
  why: string | null
  deliveries?: number[]
  rejected_in_a_row?: number
  last?: ProfessorHistoryEntry | null
}

export interface ProfessorEvent { at: number; student: string | null; message: string }

export interface ProfessorStatus {
  supported?: boolean
  error?: string
  enabled: boolean
  running: boolean
  busy?: string | null
  activate?: boolean
  quota?: { remaining_seconds?: number; refresh_at?: number | null; read_at?: number } | null
  students: Record<string, ProfessorStudent>
  events: ProfessorEvent[]
  updated_at?: number | null
  last_result?: string | null
}

export interface StudentView {
  tag: string
  phase: string
  detail: string
  best: string
  installed: string
  active: boolean
  warning: boolean
}

export interface StatusView {
  supported: boolean
  headline: string
  tone: 'idle' | 'running' | 'warning' | 'error'
  canStart: boolean
  canStop: boolean
  quota: string
  students: StudentView[]
  events: { when: string; text: string }[]
}

const PHASES: Record<string, string> = {
  new: 'état à relire sur Kaggle et sur ce PC',
  ready: 'prêt pour le prochain cycle',
  diagnosing: 'diagnostic en cours sur Kaggle',
  diagnosed: 'diagnostic terminé, entraînement à lancer',
  training: 'entraînement en cours sur Kaggle',
  trained: 'entraînement terminé, examen à lancer',
  examining: 'examen en cours sur Kaggle (base, modèle en place et candidat)',
  waiting_quota: 'en attente du quota Kaggle',
  stalled: 'en pause',
}

export function formatDate(seconds: number | null | undefined): string {
  if (!seconds || !Number.isFinite(seconds)) return 'non mesuré'
  return new Date(seconds * 1000).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return 'non mesuré'
  const minutes = Math.round(seconds / 60)
  return minutes >= 60 ? `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')}` : `${minutes} min`
}

function cycleLabel(cycle: number | null | undefined): string {
  return cycle === null || cycle === undefined ? 'aucun' : `cycle ${cycle}`
}

export function describeStudent(tag: string, student: ProfessorStudent): StudentView {
  const phase = PHASES[student.phase] ?? student.phase
  const parts: string[] = []
  if (student.cycle !== null && student.cycle !== undefined && ['diagnosing', 'training', 'trained', 'examining'].includes(student.phase)) {
    parts.push(`cycle ${student.cycle}`)
  }
  if (student.phase === 'waiting_quota') parts.push(`reprise vers ${formatDate(student.until)}`)
  if (student.phase === 'stalled' && student.why) parts.push(student.why)
  if (student.deliveries && student.deliveries.length) {
    parts.push(`livraison du cycle ${student.deliveries[student.deliveries.length - 1]} en attente sur ce PC`
      + (student.why && student.phase !== 'stalled' ? ` (${student.why})` : ''))
  }
  const last = student.last
  if (last && last.verdict !== undefined && last.installed === undefined) {
    const gain = typeof last.macro_gain === 'number' ? ` (${(last.macro_gain * 100).toFixed(1)} points)` : ''
    parts.push(last.problems && last.problems.length
      ? `dernier examen : cycle ${last.cycle} refusé`
      : `dernier examen : cycle ${last.cycle} vérifié${gain}`)
  } else if (last && last.installed) {
    parts.push(last.activated ? `cycle ${last.cycle} activé` : `cycle ${last.cycle} installé sans activation (${last.deployment ?? 'examen tel que servi non concluant'})`)
  }
  return {
    tag,
    phase,
    detail: parts.join(' · '),
    best: cycleLabel(student.best_cycle),
    installed: cycleLabel(student.installed_cycle),
    active: ['diagnosing', 'training', 'examining'].includes(student.phase),
    warning: student.phase === 'stalled',
  }
}

export function describeStatus(status: ProfessorStatus | null | undefined): StatusView {
  if (!status || status.supported === false) {
    return {
      supported: false,
      headline: status?.error || 'Autopilote indisponible sur ce PC.',
      tone: 'error', canStart: false, canStop: false, quota: 'non mesuré', students: [], events: [],
    }
  }
  const students = Object.entries(status.students || {}).map(([tag, student]) => describeStudent(tag, student))
  const running = Boolean(status.running)
  const stopping = Boolean(status.enabled) === false && running
  let headline: string
  let tone: StatusView['tone']
  if (running && status.busy) { headline = `En cours sur ce PC : ${status.busy}`; tone = 'running' }
  else if (running && !stopping) { headline = 'Autopilote actif : il avance tout seul, une étape à la fois.'; tone = 'running' }
  else if (stopping) { headline = 'Arrêt demandé : l’étape en cours se termine.'; tone = 'warning' }
  else if (status.enabled && !running) { headline = 'Autopilote interrompu (PC arrêté ou bridge relancé) : le relancer reprend où il en était.'; tone = 'warning' }
  else { headline = 'Autopilote arrêté.'; tone = 'idle' }
  if (students.some((s) => s.warning) && tone !== 'running') tone = 'warning'
  const quota = status.quota && typeof status.quota.remaining_seconds === 'number'
    ? `${formatDuration(status.quota.remaining_seconds)} de GPU Kaggle restantes cette semaine`
      + (status.quota.refresh_at ? `, renouvelées le ${formatDate(status.quota.refresh_at)}` : '')
    : 'quota Kaggle non mesuré'
  const events = (status.events || []).slice(-8).reverse().map((event) => ({
    when: formatDate(event.at),
    text: event.student ? `${event.student} : ${event.message}` : event.message,
  }))
  return { supported: true, headline, tone, canStart: !running, canStop: running && Boolean(status.enabled), quota, students, events }
}
