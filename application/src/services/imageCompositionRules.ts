// Analyseur de règles de composition pour évaluer la qualité d'un visuel
// (croquis, image générée) à partir de points focaux donnés.
//
// Règles supportées :
//   - Rule of Thirds : sujet sur l'intersection des lignes 1/3
//   - Golden Ratio : sujet sur la spirale dorée (φ = 1.618)
//   - Centred Symmetry : sujet centré
//   - Diagonals : sujet sur une des deux diagonales principales
//   - Lead Room (regard) : sujet humain regarde vers la zone vide
//
// Module pur. Input = points focaux normalisés [0..1].

export type FocalPoint = {
  x: number // normalisé [0..1]
  y: number
  /** Importance (visage > corps > arrière-plan). */
  weight: number
}

export type CompositionScore = {
  rule: 'rule-of-thirds' | 'golden-ratio' | 'centered' | 'diagonals' | 'lead-room'
  score: number // [0..1]
  /** Distance moyenne du sujet au "bon" point selon la règle. */
  avgDistance: number
  /** Verdict humain. */
  verdict: string
}

export type CompositionAnalysis = {
  scores: CompositionScore[]
  /** Meilleure règle qui s'applique. */
  bestRule: CompositionScore
  /** True si la composition est globalement bonne (best > 0.6). */
  isWellComposed: boolean
}

const THIRDS_POINTS = [
  { x: 1 / 3, y: 1 / 3 }, { x: 2 / 3, y: 1 / 3 },
  { x: 1 / 3, y: 2 / 3 }, { x: 2 / 3, y: 2 / 3 },
]

const PHI = 1.618
const GOLDEN_POINTS = [
  { x: 1 / PHI, y: 1 / PHI }, { x: 1 - 1 / PHI, y: 1 / PHI },
  { x: 1 / PHI, y: 1 - 1 / PHI }, { x: 1 - 1 / PHI, y: 1 - 1 / PHI },
]

function distToNearest(point: FocalPoint, targets: Array<{ x: number; y: number }>): number {
  let min = Infinity
  for (const t of targets) {
    const d = Math.hypot(point.x - t.x, point.y - t.y)
    if (d < min) min = d
  }
  return min
}

function scoreAgainstPoints(focals: FocalPoint[], targets: Array<{ x: number; y: number }>): number {
  if (focals.length === 0) return 0
  let weighted = 0
  let totalW = 0
  for (const f of focals) {
    const d = distToNearest(f, targets)
    // Distance normalisée : sur une diagonale 0..√2 ≈ 1.414. Score = 1 - d/0.2 (clamp).
    const s = Math.max(0, 1 - d / 0.2)
    weighted += s * f.weight
    totalW += f.weight
  }
  return totalW > 0 ? weighted / totalW : 0
}

function avgDistance(focals: FocalPoint[], targets: Array<{ x: number; y: number }>): number {
  if (focals.length === 0) return 0
  let total = 0
  for (const f of focals) total += distToNearest(f, targets)
  return total / focals.length
}

/**
 * Analyse complète : 5 règles évaluées + meilleure choisie.
 */
export function analyzeComposition(focals: FocalPoint[]): CompositionAnalysis {
  if (focals.length === 0) {
    const empty: CompositionScore = {
      rule: 'centered', score: 0, avgDistance: 0,
      verdict: 'Aucun point focal — composition indéterminée.',
    }
    return {
      scores: [empty],
      bestRule: empty,
      isWellComposed: false,
    }
  }

  const center = { x: 0.5, y: 0.5 }
  const diagonals = [
    { x: 0.25, y: 0.25 }, { x: 0.5, y: 0.5 }, { x: 0.75, y: 0.75 }, // diag descendante
    { x: 0.25, y: 0.75 }, { x: 0.75, y: 0.25 }, // diag montante
  ]

  const scores: CompositionScore[] = [
    {
      rule: 'rule-of-thirds',
      score: scoreAgainstPoints(focals, THIRDS_POINTS),
      avgDistance: avgDistance(focals, THIRDS_POINTS),
      verdict: '',
    },
    {
      rule: 'golden-ratio',
      score: scoreAgainstPoints(focals, GOLDEN_POINTS),
      avgDistance: avgDistance(focals, GOLDEN_POINTS),
      verdict: '',
    },
    {
      rule: 'centered',
      score: scoreAgainstPoints(focals, [center]),
      avgDistance: avgDistance(focals, [center]),
      verdict: '',
    },
    {
      rule: 'diagonals',
      score: scoreAgainstPoints(focals, diagonals),
      avgDistance: avgDistance(focals, diagonals),
      verdict: '',
    },
    {
      rule: 'lead-room',
      score: leadRoomScore(focals),
      avgDistance: 0,
      verdict: '',
    },
  ]

  // Verdict par règle.
  for (const s of scores) {
    if (s.score > 0.85) s.verdict = `Excellent ${s.rule}`
    else if (s.score > 0.6) s.verdict = `Bon ${s.rule}`
    else if (s.score > 0.3) s.verdict = `${s.rule} partiellement respectée`
    else s.verdict = `${s.rule} non respectée`
  }

  scores.sort((a, b) => b.score - a.score)
  const bestRule = scores[0]

  return {
    scores,
    bestRule,
    isWellComposed: bestRule.score > 0.6,
  }
}

/**
 * Lead room : un sujet humain (avec un facteur "direction") doit regarder
 * vers l'espace vide. Approximation : score haut si focal weight élevé +
 * pas trop près du bord d'opposition du regard.
 *
 * Sans direction de regard explicite, on retourne 0.5 (neutre).
 */
function leadRoomScore(focals: FocalPoint[]): number {
  if (focals.length === 0) return 0
  // Si le sujet principal est à 30-50% du bord vers le centre, OK.
  const top = focals.reduce((max, f) => (f.weight > max.weight ? f : max), focals[0])
  const distFromCenterX = Math.abs(top.x - 0.5)
  const distFromCenterY = Math.abs(top.y - 0.5)
  const maxOffset = Math.max(distFromCenterX, distFromCenterY)
  // Best ≈ 0.16 (= 1/3 - 0.5/2). Penalty si > 0.3 (trop au bord) ou < 0.1 (trop centré).
  if (maxOffset >= 0.1 && maxOffset <= 0.3) return 0.7
  return 0.3
}

/**
 * Recommandation de placement pour 1 sujet selon le style demandé.
 */
export function recommendPlacement(style: 'classic' | 'cinematic' | 'portrait' | 'landscape'): FocalPoint {
  switch (style) {
    case 'classic':
      return { x: 1 / 3, y: 1 / 3, weight: 1 } // rule of thirds top-left
    case 'cinematic':
      return { x: 0.4, y: 0.55, weight: 1 } // décalé vers le centre-bas
    case 'portrait':
      return { x: 0.5, y: 0.4, weight: 1 } // visage légèrement au-dessus du centre
    case 'landscape':
      return { x: 0.5, y: 2 / 3, weight: 1 } // horizon dans le tiers bas (ciel dominant)
  }
}
