/**
 * entEvalDetector — détecte si un devoir est une évaluation (DST, DM noté,
 * interrogation, contrôle…) à partir du title/description scraped.
 *
 * v82jj Pass 6/9 — Phase 2 P2.5.
 *
 * Approche 2 niveaux :
 *   1. fastClassify(item) — regex/keyword sur title+description (instant,
 *      pas de LLM call, marche pour 80%+ des cas évidents).
 *   2. llmClassify(item) — fallback Ollama si fast doute (kind='unknown'
 *      ou confidence basse).
 *
 * L'objectif : permettre au notif scheduler (Pass 7) de target uniquement
 * les évals à venir, et au parcours builder (Pass 8) de prioriser le
 * chapitre concerné.
 */
import { ollamaChat } from '../hooks/useTauri.ts'
import { useAppStore } from '../stores/appStore.ts'
import type { HarvestDevoirItem } from './entHarvestService.ts'

export type EvalKind =
  | 'eval'           // contrôle, DST, DS, interro, éval certifiante
  | 'dm'             // DM noté
  | 'devoir'         // travail à rendre non noté
  | 'lecon'          // apprendre/réviser leçon
  | 'lecture'        // lire un texte/livre
  | 'autre'

export type EvalDetection = {
  kind: EvalKind
  /** 0-1, niveau de confiance dans la classification. */
  confidence: number
  /** True si à traiter comme éval (notif scheduler use). */
  isEval: boolean
  /** Source : 'fast' (regex) ou 'llm' (Ollama fallback). */
  source: 'fast' | 'llm'
  /** Mots-clés détectés (debug + UI hint). */
  keywords?: string[]
}

// Patterns ordonnés par spécificité décroissante. Le premier qui match gagne.
const EVAL_PATTERNS: Array<{ kind: EvalKind; re: RegExp; weight: number; keyword: string }> = [
  // Évaluations explicites — confidence haute.
  { kind: 'eval', re: /\b(DST|D\.S\.T|devoir\s+sur\s+table)\b/i, weight: 0.95, keyword: 'DST' },
  { kind: 'eval', re: /\b(DS|D\.S|devoir\s+surveillé)\b/i, weight: 0.95, keyword: 'DS' },
  { kind: 'eval', re: /\b(contrôle|controle)\b/i, weight: 0.9, keyword: 'contrôle' },
  { kind: 'eval', re: /\b(évaluation|evaluation|évalué|evalué|eval)\b/i, weight: 0.9, keyword: 'évaluation' },
  { kind: 'eval', re: /\b(interrogation|interro)\b/i, weight: 0.9, keyword: 'interro' },
  { kind: 'eval', re: /\b(test\s+(de|sur|d['e]))\b/i, weight: 0.85, keyword: 'test' },
  { kind: 'eval', re: /\b(épreuve|epreuve|examen|partiel|baccalauréat|bac\b)\b/i, weight: 0.95, keyword: 'examen' },
  { kind: 'eval', re: /\b(grand[-\s]?oral|oral\s+(de|du|d['e]))\b/i, weight: 0.85, keyword: 'oral' },
  { kind: 'eval', re: /\b(qcm)\b/i, weight: 0.85, keyword: 'QCM' },

  // DM (Devoir Maison) noté.
  { kind: 'dm', re: /\bDM\s+(noté|note|à\s+rendre)/i, weight: 0.9, keyword: 'DM noté' },
  { kind: 'dm', re: /\b(DM|D\.M|devoir\s+(à\s+la\s+)?maison)\b/i, weight: 0.7, keyword: 'DM' },

  // Devoirs simples
  { kind: 'devoir', re: /\b(faire|terminer|compléter|completer|finir)\b.*\b(exo|exercice|fiche)/i, weight: 0.7, keyword: 'exo à faire' },
  { kind: 'devoir', re: /\b(à\s+rendre|a\s+rendre|à\s+remettre)\b/i, weight: 0.7, keyword: 'à rendre' },

  // Leçons / révisions.
  { kind: 'lecon', re: /\b(apprendre|réviser|reviser|relire)\b.*\b(leçon|lecon|cours|chapitre|fiche)/i, weight: 0.7, keyword: 'apprendre leçon' },
  { kind: 'lecon', re: /\b(leçon|lecon)\s+(à|a)\s+(savoir|apprendre)/i, weight: 0.8, keyword: 'leçon à savoir' },

  // Lectures.
  { kind: 'lecture', re: /\b(lire|lecture)\b/i, weight: 0.6, keyword: 'lecture' },
]

/** Détection rapide regex/keyword. Pas d'appel LLM. */
export function fastClassify(item: HarvestDevoirItem): EvalDetection {
  const text = `${item.title || ''} ${item.description || ''}`.toLowerCase()
  if (item.isEval === true) {
    return { kind: 'eval', confidence: 1.0, isEval: true, source: 'fast', keywords: ['flag explicit'] }
  }
  let best: { kind: EvalKind; confidence: number; keyword: string } | null = null
  const matchedKeywords: string[] = []
  for (const { kind, re, weight, keyword } of EVAL_PATTERNS) {
    if (re.test(text)) {
      matchedKeywords.push(keyword)
      if (!best || weight > best.confidence) {
        best = { kind, confidence: weight, keyword }
      }
    }
  }
  if (!best) {
    return { kind: 'autre', confidence: 0.3, isEval: false, source: 'fast', keywords: [] }
  }
  return {
    kind: best.kind,
    confidence: best.confidence,
    isEval: best.kind === 'eval' || (best.kind === 'dm' && best.confidence >= 0.85),
    source: 'fast',
    keywords: matchedKeywords,
  }
}

const SYSTEM_LLM = `Tu classes les devoirs scolaires. Réponds STRICTEMENT en JSON avec :
{ "kind": "eval"|"dm"|"devoir"|"lecon"|"lecture"|"autre", "confidence": 0-1 }
"eval" = DST/DS/contrôle/interro/QCM/oral/test (toute évaluation notée).
"dm" = devoir maison à rendre noté.
"devoir" = travail à faire non noté.
"lecon" = apprendre/réviser leçon.
"lecture" = lire un texte/livre.
Pas de markdown, JSON pur.`

/** Classification LLM si la fast est ambiguë. */
export async function llmClassify(item: HarvestDevoirItem): Promise<EvalDetection> {
  const text = `Titre: ${item.title || '(sans titre)'}\nDescription: ${item.description || '(vide)'}`
  try {
    const model = useAppStore.getState().mainModel
    const result = await ollamaChat(
      model,
      [{ role: 'system', content: SYSTEM_LLM }, { role: 'user', content: text }],
      0.1,
    ) as { message?: { content?: string } } | null
    const response = result?.message?.content
    if (!response) return { kind: 'autre', confidence: 0.2, isEval: false, source: 'llm' }
    const match = response.match(/\{[\s\S]*\}/)
    if (!match) return { kind: 'autre', confidence: 0.2, isEval: false, source: 'llm' }
    const json = JSON.parse(match[0]) as Record<string, unknown>
    const kind = typeof json.kind === 'string' ? (json.kind as EvalKind) : 'autre'
    const confidence = typeof json.confidence === 'number' ? json.confidence : 0.5
    return {
      kind, confidence,
      isEval: kind === 'eval' || (kind === 'dm' && confidence >= 0.7),
      source: 'llm',
    }
  } catch {
    return { kind: 'autre', confidence: 0.2, isEval: false, source: 'llm' }
  }
}

/** Pipeline : fast d'abord, escalade LLM si confidence < threshold. */
export async function classifyEval(
  item: HarvestDevoirItem,
  options?: { llmThreshold?: number },
): Promise<EvalDetection> {
  const fast = fastClassify(item)
  const threshold = options?.llmThreshold ?? 0.65
  if (fast.confidence >= threshold || fast.kind === 'autre') {
    // Si fast est confiant OU si c'est rejeté à 'autre' avec faible confidence
    // (contenu vide), pas la peine d'escalader LLM.
    return fast
  }
  return await llmClassify(item)
}

/** Bulk classification — fast pour tous, LLM seulement pour ambigus.
 *  Cap LLM calls à 10 par bulk pour éviter rate limit. */
export async function classifyAll(
  items: HarvestDevoirItem[],
  options?: { llmThreshold?: number; maxLlmCalls?: number },
): Promise<EvalDetection[]> {
  const threshold = options?.llmThreshold ?? 0.65
  const maxLlm = options?.maxLlmCalls ?? 10
  const fastResults = items.map((it) => ({ item: it, det: fastClassify(it) }))
  const ambiguous = fastResults.filter((r) => r.det.confidence < threshold && r.det.kind !== 'autre')
  // LLM seulement les ambigus, jusqu'à maxLlm
  const toEscalate = ambiguous.slice(0, maxLlm)
  const escalated = await Promise.all(toEscalate.map((r) => llmClassify(r.item)))
  const escalatedMap = new Map<HarvestDevoirItem, EvalDetection>()
  toEscalate.forEach((r, i) => escalatedMap.set(r.item, escalated[i]))
  return fastResults.map((r) => escalatedMap.get(r.item) ?? r.det)
}
