// Compare deux prompts SDXL/FLUX et identifie quels qualifiers changent.
// Utile quand on génère plusieurs variations : Aurora peut dire "j'ai ajouté
// 'cinematic lighting' et retiré 'flat colors'" plutôt que "le prompt a
// changé".
//
// Approche :
//   - tokenize chaque prompt en segments (split sur virgules + nettoyage)
//   - calcule set-difference : added, removed, common
//   - identifie les segments "reformulés" (similarité Levenshtein ≥ 0.8) plutôt
//     que purement ajoutés/retirés
//   - classe par catégorie sémantique (style/lighting/composition/mood) en
//     croisant avec les listes du imagePromptBuilder
//
// Pure compute. Pas de LLM.

export type PromptSegment = {
  raw: string
  /** Tokens normalisés (lower + strip diacritics). */
  tokens: string[]
}

export type PromptDiff = {
  added: PromptSegment[]
  removed: PromptSegment[]
  /** Segments présents dans les 2 avec sim ≥ similarThreshold. */
  reformulated: Array<{ before: PromptSegment; after: PromptSegment; similarity: number }>
  /** Segments présents tels quels dans les 2 (sim = 1). */
  identical: PromptSegment[]
  /** Score global de changement [0..1] : 0 = identique, 1 = totalement différent. */
  changeRatio: number
  /** Phrase FR résumant le changement. */
  summary: string
}

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length > 0)
}

function splitSegments(prompt: string): PromptSegment[] {
  return prompt
    .split(/,(?![^()]*\))/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((raw) => ({ raw, tokens: tokenize(raw) }))
}

function jaccard(a: string[], b: string[]): number {
  if (a.length === 0 && b.length === 0) return 1
  if (a.length === 0 || b.length === 0) return 0
  const setA = new Set(a)
  const setB = new Set(b)
  let inter = 0
  for (const x of setA) if (setB.has(x)) inter += 1
  const union = new Set<string>()
  for (const x of setA) union.add(x)
  for (const x of setB) union.add(x)
  return inter / union.size
}

export function diffPrompts(before: string, after: string, similarThreshold = 0.5): PromptDiff {
  const segB = splitSegments(before)
  const segA = splitSegments(after)
  const usedAfter = new Set<number>()
  const identical: PromptSegment[] = []
  const reformulated: PromptDiff['reformulated'] = []
  const removed: PromptSegment[] = []

  for (const b of segB) {
    // Cherche le meilleur match dans segA non encore utilisé.
    let bestIdx = -1
    let bestSim = 0
    for (let i = 0; i < segA.length; i += 1) {
      if (usedAfter.has(i)) continue
      const sim = jaccard(b.tokens, segA[i].tokens)
      if (sim > bestSim) {
        bestSim = sim
        bestIdx = i
      }
    }
    if (bestIdx === -1) {
      removed.push(b)
      continue
    }
    if (bestSim === 1) {
      identical.push(b)
      usedAfter.add(bestIdx)
    } else if (bestSim >= similarThreshold) {
      reformulated.push({ before: b, after: segA[bestIdx], similarity: bestSim })
      usedAfter.add(bestIdx)
    } else {
      removed.push(b)
    }
  }
  const added = segA.filter((_, i) => !usedAfter.has(i))

  const totalChanges = added.length + removed.length + reformulated.length
  const totalSegments = Math.max(segB.length, segA.length)
  const changeRatio = totalSegments === 0 ? 0 : Math.min(1, totalChanges / totalSegments)

  const parts: string[] = []
  if (added.length > 0) parts.push(`+${added.length} ajout(s) : ${added.slice(0, 2).map((s) => `"${s.raw}"`).join(', ')}${added.length > 2 ? '…' : ''}`)
  if (removed.length > 0) parts.push(`-${removed.length} retrait(s) : ${removed.slice(0, 2).map((s) => `"${s.raw}"`).join(', ')}${removed.length > 2 ? '…' : ''}`)
  if (reformulated.length > 0) parts.push(`${reformulated.length} reformulation(s)`)
  if (identical.length > 0 && parts.length === 0) parts.push(`identique (${identical.length} segments)`)
  const summary = parts.length > 0 ? parts.join(' ; ') : 'aucun changement détecté'

  return { added, removed, reformulated, identical, changeRatio, summary }
}

/** Détermine si un segment porte un qualifier de style (cinematic, anime…). */
const STYLE_TOKENS = new Set([
  'cinematic', 'photorealistic', 'anime', 'manga', 'aquarelle', 'watercolor',
  'oil', 'painting', 'isometric', 'pixel', 'art', 'flat', 'illustration',
  'concept', 'technical', 'comic', 'sketch', 'realistic', 'hyperrealistic',
])

/** Détermine si un segment parle de lumière. */
const LIGHT_TOKENS = new Set([
  'golden', 'hour', 'blue', 'overcast', 'noon', 'studio', 'rim', 'light',
  'rembrandt', 'volumetric', 'fog', 'neon', 'cyberpunk', 'lighting',
])

/** Détermine si un segment parle de composition. */
const COMPOSITION_TOKENS = new Set([
  'centered', 'thirds', 'symmetrical', 'dutch', 'angle', 'overhead', 'wide',
  'shot', 'close', 'up', 'frame', 'composition',
])

export type SegmentCategory = 'style' | 'lighting' | 'composition' | 'subject' | 'other'

export function categorize(segment: PromptSegment): SegmentCategory {
  for (const tok of segment.tokens) {
    if (STYLE_TOKENS.has(tok)) return 'style'
    if (LIGHT_TOKENS.has(tok)) return 'lighting'
    if (COMPOSITION_TOKENS.has(tok)) return 'composition'
  }
  // Heuristic : 1er segment = sujet en général.
  return 'other'
}

/**
 * Diff catégorisé : groupe les ajouts/retraits par catégorie sémantique.
 * Utile pour rendre l'UI "tu as changé le style + la lumière".
 */
export type CategorizedDiff = {
  byCategory: Record<SegmentCategory, { added: PromptSegment[]; removed: PromptSegment[] }>
  changeRatio: number
  summary: string
}

export function diffPromptsByCategory(before: string, after: string): CategorizedDiff {
  const diff = diffPrompts(before, after)
  const byCategory: CategorizedDiff['byCategory'] = {
    style: { added: [], removed: [] },
    lighting: { added: [], removed: [] },
    composition: { added: [], removed: [] },
    subject: { added: [], removed: [] },
    other: { added: [], removed: [] },
  }
  for (const a of diff.added) byCategory[categorize(a)].added.push(a)
  for (const r of diff.removed) byCategory[categorize(r)].removed.push(r)
  const summary = (['style', 'lighting', 'composition'] as SegmentCategory[])
    .filter((c) => byCategory[c].added.length + byCategory[c].removed.length > 0)
    .map((c) => `${c}: ${byCategory[c].added.length} ajouts, ${byCategory[c].removed.length} retraits`)
    .join(' • ')
  return {
    byCategory,
    changeRatio: diff.changeRatio,
    summary: summary || diff.summary,
  }
}
