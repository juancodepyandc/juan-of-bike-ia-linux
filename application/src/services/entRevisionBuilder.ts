/**
 * entRevisionBuilder — génère un parcours de révision complet pour une
 * éval donnée à partir des cours/exos harvested.
 *
 * v82jl Pass 8/9 — Phase 2 P2.7.
 *
 * Output structure :
 *   - 3-5 fiches de révision (résumé chapitre + définitions clés).
 *   - 5-10 flashcards Q/A.
 *   - 3 exos type avec correction étape par étape.
 *   - Mind-map textuelle du chapitre.
 *
 * Inputs :
 *   - eval target : HarvestDevoirItem (avec subject + chapter idéalement).
 *   - context cours : DocStructured[] (depuis entDocParser pass 4).
 *   - notes trend : SubjectTrend (pour calibrer difficulté).
 */
import { ollamaChat } from '../hooks/useTauri.ts'
import { useAppStore } from '../stores/appStore.ts'
import type { HarvestDevoirItem } from './entHarvestService.ts'
import type { DocStructured } from './entDocParser.ts'
import type { SubjectTrend } from './entNotesAnalysis.ts'

export type RevisionFiche = {
  title: string
  summary: string
  definitions: Array<{ term: string; def: string }>
}

export type RevisionFlashcard = {
  question: string
  answer: string
  hint?: string
}

export type RevisionExo = {
  question: string
  steps: string[]              // résolution pas-à-pas
  finalAnswer?: string
  difficulty: 'facile' | 'moyen' | 'difficile'
}

export type RevisionMindmap = {
  root: string                 // titre du chapitre
  branches: Array<{ label: string; sub?: string[] }>
}

export type RevisionParcours = {
  meta: {
    subject: string
    chapter: string
    level: string
    targetEval?: { title: string; date?: string }
    generatedAt: number
    calibratedFor: 'rattrapage' | 'consolidation' | 'expert'
  }
  fiches: RevisionFiche[]
  flashcards: RevisionFlashcard[]
  exercises: RevisionExo[]
  mindmap: RevisionMindmap
}

const SYSTEM_REVISION = `Tu es Aurora, copilote pédagogique français. Tu reçois :
- une éval cible (matière + chapitre + date)
- du contexte cours (résumé chapitre, key points)
- le niveau actuel de l'élève (avg/20, trend)

Tu génères un parcours de révision complet en JSON pur (pas de markdown fence) :
{
  "fiches": [
    { "title": "string", "summary": "2-3 phrases", "definitions": [{ "term": "X", "def": "Y" }, ...] }
  ],   // 3 à 5 fiches
  "flashcards": [
    { "question": "Q?", "answer": "A.", "hint": "optionnel" }
  ],   // 5 à 10 flashcards
  "exercises": [
    { "question": "Énoncé.", "steps": ["étape 1", "étape 2", ...], "finalAnswer": "réponse", "difficulty": "facile|moyen|difficile" }
  ],   // 3 exos
  "mindmap": {
    "root": "Nom du chapitre",
    "branches": [{ "label": "concept", "sub": ["sous-point 1", "sous-point 2"] }]
  }   // 4-7 branches
}

Calibrage :
- 'rattrapage' (avg < 10) : fiches très simples, flashcards courtes, exos de niveau facile.
- 'consolidation' (10-14) : équilibré, exos moyens.
- 'expert' (>14) : aller loin, exos difficile, défis bonus.

Réponds en français. JSON pur strict.`

function pickCalibration(trend?: SubjectTrend | null): 'rattrapage' | 'consolidation' | 'expert' {
  if (!trend) return 'consolidation'
  if (trend.studentAvg < 10) return 'rattrapage'
  if (trend.studentAvg > 14) return 'expert'
  return 'consolidation'
}

/** Build user prompt structured. */
function buildUserPrompt(args: {
  eval: HarvestDevoirItem
  cours: DocStructured[]
  trend?: SubjectTrend | null
  calibration: 'rattrapage' | 'consolidation' | 'expert'
}): string {
  const { eval: ev, cours, trend, calibration } = args
  const lines: string[] = []
  lines.push(`Éval cible :`)
  lines.push(`  Matière : ${ev.subject || 'inconnu'}`)
  lines.push(`  Titre : ${ev.title}`)
  if (ev.date) lines.push(`  Date : ${ev.date}`)
  if (ev.description) lines.push(`  Description : ${ev.description.slice(0, 500)}`)
  lines.push(``)
  if (cours.length > 0) {
    lines.push(`Contexte cours (${cours.length} document${cours.length > 1 ? 's' : ''}) :`)
    cours.slice(0, 3).forEach((c, i) => {
      lines.push(`  [Doc ${i + 1}] ${c.kind} · ${c.subject || '?'} · chapitre ${c.chapter || '?'}`)
      if (c.abstract) lines.push(`    Abstract : ${c.abstract}`)
      if (c.keyPoints?.length) lines.push(`    Key points : ${c.keyPoints.join('; ')}`)
    })
    lines.push(``)
  }
  if (trend) {
    lines.push(`Niveau actuel élève :`)
    lines.push(`  Moyenne ${trend.subject} : ${trend.studentAvg.toFixed(1)}/20 (trend ${trend.direction})`)
    if (trend.classAvg !== null) lines.push(`  Moyenne classe : ${trend.classAvg.toFixed(1)}/20`)
    if (trend.gapVsClass !== null) lines.push(`  Gap vs classe : ${trend.gapVsClass.toFixed(1)}`)
    lines.push(``)
  }
  lines.push(`Calibrage requis : ${calibration}.`)
  lines.push(`Génère le parcours révision en JSON strict.`)
  return lines.join('\n')
}

/** Pipeline complet. Génère un parcours révision pour cette éval. */
export async function buildRevisionParcours(args: {
  eval: HarvestDevoirItem
  cours?: DocStructured[]
  trend?: SubjectTrend | null
}): Promise<RevisionParcours | null> {
  const calibration = pickCalibration(args.trend)
  const userPrompt = buildUserPrompt({
    eval: args.eval,
    cours: args.cours ?? [],
    trend: args.trend ?? null,
    calibration,
  })
  try {
    const model = useAppStore.getState().mainModel
    const result = await ollamaChat(
      model,
      [{ role: 'system', content: SYSTEM_REVISION }, { role: 'user', content: userPrompt }],
      0.5,
    ) as { message?: { content?: string } } | null
    const response = result?.message?.content
    if (!response) return null
    const match = response.match(/\{[\s\S]*\}/)
    if (!match) return null
    const json = JSON.parse(match[0]) as Record<string, unknown>
    const fiches = Array.isArray(json.fiches) ? json.fiches as RevisionFiche[] : []
    const flashcards = Array.isArray(json.flashcards) ? json.flashcards as RevisionFlashcard[] : []
    const exercises = Array.isArray(json.exercises) ? json.exercises as RevisionExo[] : []
    const mindmap = (json.mindmap as RevisionMindmap | undefined) || {
      root: args.eval.subject || 'Chapitre',
      branches: [],
    }
    if (fiches.length === 0 && flashcards.length === 0) return null
    return {
      meta: {
        subject: args.eval.subject || 'inconnu',
        chapter: args.cours?.[0]?.chapter || args.eval.title || 'inconnu',
        level: args.cours?.[0]?.level || 'inconnu',
        targetEval: { title: args.eval.title, date: args.eval.date },
        generatedAt: Date.now(),
        calibratedFor: calibration,
      },
      fiches,
      flashcards,
      exercises,
      mindmap,
    }
  } catch {
    return null
  }
}

/** Save parcours dans localStorage pour ré-affichage sans re-LLM. */
const PARCOURS_KEY = 'aurora-ent-revision-parcours-v1'

export function saveParcours(parcours: RevisionParcours): void {
  if (typeof window === 'undefined') return
  try {
    const all: RevisionParcours[] = JSON.parse(window.localStorage.getItem(PARCOURS_KEY) || '[]')
    // Prepend + cap 20 derniers parcours.
    const next = [parcours, ...all].slice(0, 20)
    window.localStorage.setItem(PARCOURS_KEY, JSON.stringify(next))
  } catch { /* ignore */ }
}

export function loadAllParcours(): RevisionParcours[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(PARCOURS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch { return [] }
}
