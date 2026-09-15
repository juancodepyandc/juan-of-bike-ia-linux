/**
 * entNotesAnalysis — analyse trend des notes par matière, identification
 * des matières à remonter, ranking pour proposer parcours révision.
 *
 * v82ji Pass 5/9 — Phase 2 P2.4.
 *
 * Algorithmes :
 *   - normalizeGrade(grade, scale) → ratio 0-1 (compense /20 vs /10 vs %).
 *   - groupBySubject(notes[]) → { [subject]: HarvestNoteItem[] sorted }.
 *   - subjectTrend(notes[]) → { current, classAvg, slope, direction }.
 *   - prioritize(allNotes) → list rankée des matières à remonter.
 */
import type { HarvestNoteItem } from './entHarvestService.ts'

export type SubjectTrend = {
  subject: string
  noteCount: number
  /** Moyenne de l'élève sur la période (toutes notes du subject), 0-20. */
  studentAvg: number
  /** Moyenne classe agrégée (si disponible), 0-20. */
  classAvg: number | null
  /** Différence student - class. Négatif = sous-moyenne classe. */
  gapVsClass: number | null
  /** Slope linéaire des dernières notes (positive = en progrès). */
  slope: number
  direction: 'up' | 'down' | 'flat' | 'unknown'
  /** Last 6 notes normalisées 0-1 pour mini sparkline. */
  recentNormalized: number[]
  /** Score 0-100 = priorité de révision (plus haut = plus urgent). */
  priority: number
}

/** Normalise une note vers /20 (échelle scolaire FR standard). */
export function normalizeGrade(grade: number | null, scale?: number): number | null {
  if (grade === null || Number.isNaN(grade)) return null
  const sc = (scale && scale > 0) ? scale : 20
  // Si scale absent, on suppose /20 si grade <= 20, sinon % (scale 100).
  if (!scale) {
    if (grade <= 20) return grade
    if (grade <= 100) return (grade / 100) * 20
    return null
  }
  return (grade / sc) * 20
}

/** Group notes par matière, tri chronologique ascendant. */
export function groupBySubject(notes: HarvestNoteItem[]): Record<string, HarvestNoteItem[]> {
  const groups: Record<string, HarvestNoteItem[]> = {}
  for (const n of notes) {
    if (!n.subject) continue
    const key = n.subject.trim()
    if (!groups[key]) groups[key] = []
    groups[key].push(n)
  }
  for (const k of Object.keys(groups)) {
    groups[k].sort((a, b) => {
      const da = a.date ? new Date(a.date).getTime() : 0
      const db = b.date ? new Date(b.date).getTime() : 0
      return da - db
    })
  }
  return groups
}

/** Linear regression slope sur les notes normalisées d'une matière. */
function computeSlope(values: number[]): number {
  const n = values.length
  if (n < 2) return 0
  const xs = values.map((_, i) => i)
  const xMean = xs.reduce((a, b) => a + b, 0) / n
  const yMean = values.reduce((a, b) => a + b, 0) / n
  let num = 0, den = 0
  for (let i = 0; i < n; i++) {
    num += (xs[i] - xMean) * (values[i] - yMean)
    den += (xs[i] - xMean) ** 2
  }
  return den === 0 ? 0 : num / den
}

/** Compute trend par matière. */
export function subjectTrend(subject: string, notes: HarvestNoteItem[]): SubjectTrend {
  const valid = notes
    .map((n) => ({ note: normalizeGrade(n.grade, n.scale), classAvg: n.classAverage ?? null }))
    .filter((v) => v.note !== null) as Array<{ note: number; classAvg: number | null }>
  const noteCount = valid.length
  if (noteCount === 0) {
    return {
      subject, noteCount, studentAvg: 0, classAvg: null, gapVsClass: null,
      slope: 0, direction: 'unknown', recentNormalized: [], priority: 0,
    }
  }
  const studentAvg = valid.reduce((sum, v) => sum + v.note, 0) / noteCount
  const validClassAvgs = valid.map((v) => v.classAvg).filter((c): c is number => c !== null && !Number.isNaN(c))
  const classAvg = validClassAvgs.length > 0
    ? validClassAvgs.reduce((a, b) => a + b, 0) / validClassAvgs.length
    : null
  const gapVsClass = classAvg !== null ? studentAvg - classAvg : null
  const slope = computeSlope(valid.map((v) => v.note))
  const direction: SubjectTrend['direction'] =
    Math.abs(slope) < 0.1 ? 'flat'
      : slope > 0 ? 'up'
      : 'down'
  const recent = valid.slice(-6).map((v) => v.note / 20)
  // Priority : plus la note est basse (vs classe ou en absolu) et plus
  // elle baisse, plus on push haut. Score 0-100.
  let priority = 0
  // 0-50 : score basé sur niveau absolu (sous 10 = +50)
  priority += Math.max(0, (12 - studentAvg) * 5)
  // 0-30 : sous-classe (gap < -2 = +30)
  if (gapVsClass !== null && gapVsClass < 0) {
    priority += Math.min(30, Math.abs(gapVsClass) * 10)
  }
  // 0-20 : trend down
  if (direction === 'down') priority += Math.min(20, Math.abs(slope) * 30)
  priority = Math.min(100, Math.round(priority))
  return {
    subject, noteCount, studentAvg, classAvg, gapVsClass,
    slope, direction, recentNormalized: recent, priority,
  }
}

/** Trends pour toutes les matières, triés priority desc. */
export function analyzeAllSubjects(notes: HarvestNoteItem[]): SubjectTrend[] {
  const groups = groupBySubject(notes)
  const trends = Object.entries(groups).map(([subject, items]) => subjectTrend(subject, items))
  return trends.sort((a, b) => b.priority - a.priority)
}

/** Format human-readable d'une SubjectTrend. */
export function formatTrend(t: SubjectTrend): string {
  const arrow = t.direction === 'up' ? '▲' : t.direction === 'down' ? '▼' : '→'
  const gap = t.gapVsClass === null
    ? ''
    : t.gapVsClass >= 0
      ? ` (+${t.gapVsClass.toFixed(1)} vs classe)`
      : ` (${t.gapVsClass.toFixed(1)} vs classe)`
  return `${t.subject}: ${t.studentAvg.toFixed(1)}/20 ${arrow}${gap}`
}
