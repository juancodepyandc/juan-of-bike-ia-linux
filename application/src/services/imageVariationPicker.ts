// Variation picker — quand le pipeline d'image génère 4 candidats SDXL/FLUX,
// on doit choisir le meilleur sans afficher les 4 et demander à Juan de
// cliquer. Le handoff demande "picker visuel automatique via qwen3-vl"
// mais l'appel vision peut être absent ; on a alors besoin d'un score
// purement statique en fallback.
//
// 4 axes :
//   - prompt fidelity (texte du prompt présent dans la description vision)
//   - composition (rule-of-thirds, symétrie via détection bordures)
//   - sharpness (variance Laplacian heuristic via histogram cues)
//   - palette match (couleurs dominantes vs paletteHints du brief)
//
// La fonction principale `pickBestVariation(candidates)` ne dépend ni de
// vision LLM ni de canvas : elle prend des "features" déjà calculées.
// L'appelant (côté Python ou côté ouvert Tauri) extrait les features.

export type VariationFeatures = {
  /** ID du candidat (sha256 du PNG, ou index). */
  id: string
  /** [0..1] : combien le prompt initial est verbalement présent dans la description vision. */
  promptFidelity: number
  /** [0..1] : 1 = sujet placé sur tier rule, symétrie/balance OK. */
  compositionScore: number
  /** [0..1] : 1 = très net (haut variance bord). */
  sharpnessScore: number
  /** [0..1] : ressemblance entre couleurs dominantes et paletteHints. */
  paletteMatch: number
  /** [0..1] : pénalité (visages déformés, artefacts JPEG, censure). */
  artefactPenalty: number
  /** Coloris dominants détectés (hex), pour la fiche. */
  dominantColors?: string[]
  /** Texte vision (qwen3-vl description) si dispo. */
  visionDescription?: string
}

export type VariationScore = {
  features: VariationFeatures
  /** Score global [0..1] = mix pondéré. */
  overall: number
  /** Détail axes pour debug. */
  axes: {
    fidelity: number
    composition: number
    sharpness: number
    palette: number
    artefacts: number
  }
  /** Raison condensée pour la fiche UI ("net + bon cadrage, palette correcte"). */
  rationale: string
}

const WEIGHTS = {
  fidelity: 2.5,
  composition: 1.5,
  sharpness: 1.2,
  palette: 1.0,
  artefacts: 1.5, // pénalité, donc soustraite
}

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

export function scoreVariation(features: VariationFeatures): VariationScore {
  const fidelity = clamp01(features.promptFidelity)
  const composition = clamp01(features.compositionScore)
  const sharpness = clamp01(features.sharpnessScore)
  const palette = clamp01(features.paletteMatch)
  const artefacts = clamp01(features.artefactPenalty)
  const totalWeight = WEIGHTS.fidelity + WEIGHTS.composition + WEIGHTS.sharpness + WEIGHTS.palette
  const positive = (fidelity * WEIGHTS.fidelity + composition * WEIGHTS.composition + sharpness * WEIGHTS.sharpness + palette * WEIGHTS.palette) / totalWeight
  const overall = clamp01(positive - artefacts * (WEIGHTS.artefacts / (totalWeight + WEIGHTS.artefacts)))
  return {
    features,
    overall,
    axes: { fidelity, composition, sharpness, palette, artefacts },
    rationale: buildRationale({ fidelity, composition, sharpness, palette, artefacts }),
  }
}

function buildRationale(a: { fidelity: number; composition: number; sharpness: number; palette: number; artefacts: number }): string {
  const parts: string[] = []
  if (a.fidelity > 0.85) parts.push('fidèle au prompt')
  else if (a.fidelity < 0.5) parts.push('s\'éloigne du prompt')
  if (a.composition > 0.8) parts.push('bon cadrage')
  if (a.sharpness > 0.85) parts.push('très net')
  else if (a.sharpness < 0.5) parts.push('flou')
  if (a.palette > 0.85) parts.push('palette respectée')
  else if (a.palette < 0.4) parts.push('palette hors brief')
  if (a.artefacts > 0.4) parts.push('artefacts visibles')
  if (parts.length === 0) return 'qualité moyenne'
  return parts.join(', ')
}

export type PickResult = {
  winner: VariationScore
  ranked: VariationScore[]
  /** Si les 2 premiers sont très proches (< 0.05), on signale l'ambiguïté. */
  ambiguous: boolean
  /** Si le winner est sous 0.5, on conseille de re-générer. */
  regenerateAdvised: boolean
}

/**
 * Choisit la meilleure variation. Retourne aussi le classement complet
 * (pour afficher "ces 3 autres candidates étaient ainsi") et des flags
 * pour l'UI.
 */
export function pickBestVariation(candidates: VariationFeatures[]): PickResult {
  if (candidates.length === 0) throw new Error('pickBestVariation: aucun candidat')
  const scored = candidates.map(scoreVariation).sort((a, b) => b.overall - a.overall)
  const winner = scored[0]
  const second = scored[1]
  const ambiguous = Boolean(second && Math.abs(winner.overall - second.overall) < 0.05)
  const regenerateAdvised = winner.overall < 0.5
  return { winner, ranked: scored, ambiguous, regenerateAdvised }
}

// --- Helpers pour calculer la fidelity côté caller --------------------------

/**
 * Mesure verbale entre le prompt original et une description vision.
 * Approxime via tokenisation + recouvrement de bigrammes.
 */
export function measurePromptFidelity(prompt: string, visionDescription: string): number {
  const tokensP = tokenize(prompt)
  const tokensV = tokenize(visionDescription)
  if (tokensP.length === 0 || tokensV.length === 0) return 0
  const bigramsP = bigrams(tokensP)
  const bigramsV = bigrams(tokensV)
  const setV = new Set(bigramsV)
  let matches = 0
  for (const bg of bigramsP) if (setV.has(bg)) matches += 1
  // Bonus pour les uni-tokens importants présents.
  const setVu = new Set(tokensV)
  const importantP = tokensP.filter((t) => t.length >= 5) // mots "longs" = plus distinctifs
  let unimatches = 0
  for (const t of importantP) if (setVu.has(t)) unimatches += 1
  const bigramScore = bigramsP.length === 0 ? 0 : matches / bigramsP.length
  const uniScore = importantP.length === 0 ? 0 : unimatches / importantP.length
  return clamp01(0.7 * bigramScore + 0.3 * uniScore)
}

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length >= 2)
}

function bigrams(tokens: string[]): string[] {
  if (tokens.length < 2) return []
  const out: string[] = []
  for (let i = 0; i < tokens.length - 1; i += 1) {
    out.push(`${tokens[i]} ${tokens[i + 1]}`)
  }
  return out
}

/**
 * Calcule un score [0..1] de correspondance palette : compare hex dominants
 * détectés et les hex demandés dans le brief.
 *
 * Métriques :
 *   - Pour chaque hex demandé, on cherche le plus proche parmi dominants
 *     (distance euclidienne dans l'espace RGB).
 *   - On moyenne sur tous les hex demandés, normalisé sur 441 ≈ √(3·255²).
 */
export function measurePaletteMatch(dominantHex: string[], requestedHex: string[]): number {
  if (requestedHex.length === 0) return 1 // pas de contrainte palette → tout passe
  if (dominantHex.length === 0) return 0
  const reqRgb = requestedHex.map(hexToRgb).filter(Boolean) as Array<[number, number, number]>
  const domRgb = dominantHex.map(hexToRgb).filter(Boolean) as Array<[number, number, number]>
  if (reqRgb.length === 0 || domRgb.length === 0) return 0
  let total = 0
  for (const r of reqRgb) {
    let best = Infinity
    for (const d of domRgb) {
      const dist = Math.sqrt((r[0] - d[0]) ** 2 + (r[1] - d[1]) ** 2 + (r[2] - d[2]) ** 2)
      if (dist < best) best = dist
    }
    total += best
  }
  const avgDist = total / reqRgb.length
  // 441 = distance max théorique, mais en pratique on veut 0..100 = parfait, 200+ = mauvais.
  return clamp01(1 - avgDist / 200)
}

function hexToRgb(hex: string): [number, number, number] | null {
  const h = hex.replace(/^#/, '')
  if (h.length === 3) {
    return [parseInt(h[0] + h[0], 16), parseInt(h[1] + h[1], 16), parseInt(h[2] + h[2], 16)]
  }
  if (h.length === 6) {
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
  }
  return null
}
