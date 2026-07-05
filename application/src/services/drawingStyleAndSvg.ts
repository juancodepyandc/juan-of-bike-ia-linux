// Drawing module — style intent classifier + SVG path builder.
//
// Demande du handoff :
//   - détection automatique du style intent : schéma technique vs croquis artistique
//   - pour schémas : ligne propre, labels typographiés, alignement grille
//   - pour croquis : aquarelle, ink, vector flat selon le ton
//   - ControlNet edge-detection : output respecte la composition exacte du croquis
//   - multi-pass refinement
//   - export SVG quand vectoriel possible
//
// Module pur : pas de DOM, pas de canvas — uniquement structures + serialiseur SVG.

export type DrawingIntentClass = 'schema-technique' | 'croquis-artistique' | 'diagramme-flow' | 'sketch-rapide' | 'graphique-data'

export type DrawingStyleClassification = {
  intent: DrawingIntentClass
  /** Confidence 0..1. */
  confidence: number
  /** ControlNet preset à utiliser côté SD (lineart / canny / softedge / scribble). */
  controlNetPreset: 'lineart' | 'canny' | 'softedge' | 'scribble' | 'mlsd' | 'depth'
  /** Output cible préférentielle. */
  preferredOutput: 'svg' | 'raster' | 'both'
  /** Top patterns matchés (pour le hint UI). */
  matchedPatterns: string[]
}

const INTENT_SIGNALS: Array<{
  intent: DrawingIntentClass
  patterns: Array<{ regex: RegExp; weight: number; tag: string }>
  controlNetPreset: DrawingStyleClassification['controlNetPreset']
  preferredOutput: DrawingStyleClassification['preferredOutput']
}> = [
  {
    intent: 'schema-technique',
    patterns: [
      { regex: /\bschema(s)?\b/i, weight: 3, tag: 'schema' },
      { regex: /\btechnique(s)?\b/i, weight: 2, tag: 'technique' },
      { regex: /\bblueprint\b/i, weight: 4, tag: 'blueprint' },
      { regex: /\bcoupe (transversale|longitudinale|technique)\b/i, weight: 3, tag: 'coupe' },
      { regex: /\bcircuit (electronique|imprime|electrique)\b/i, weight: 4, tag: 'circuit' },
      { regex: /\bplan (electrique|architectural|mecanique)\b/i, weight: 4, tag: 'plan' },
      { regex: /\b(labels?|legendes?|annotations?)\b/i, weight: 2, tag: 'annotations' },
    ],
    controlNetPreset: 'mlsd',
    preferredOutput: 'svg',
  },
  {
    intent: 'croquis-artistique',
    patterns: [
      { regex: /\bcroquis(?!\s+technique)\b/i, weight: 3, tag: 'croquis' },
      { regex: /\bink\b/i, weight: 3, tag: 'ink' },
      { regex: /\baquarelle\b/i, weight: 4, tag: 'aquarelle' },
      { regex: /\billustration\b/i, weight: 2, tag: 'illustration' },
      { regex: /\bartistique\b/i, weight: 3, tag: 'artistique' },
      { regex: /\bvecteur (flat|artistique)\b/i, weight: 3, tag: 'vector-flat' },
    ],
    controlNetPreset: 'scribble',
    preferredOutput: 'raster',
  },
  {
    intent: 'diagramme-flow',
    patterns: [
      { regex: /\bdiagramme\b/i, weight: 3, tag: 'diagramme' },
      { regex: /\borganigramme\b/i, weight: 4, tag: 'organigramme' },
      { regex: /\bflowchart\b/i, weight: 4, tag: 'flowchart' },
      { regex: /\bmind ?map\b/i, weight: 4, tag: 'mindmap' },
      { regex: /\b(arbre de decision|state ?diagram|sequence ?diagram)\b/i, weight: 4, tag: 'diagramme-uml' },
    ],
    controlNetPreset: 'mlsd',
    preferredOutput: 'svg',
  },
  {
    intent: 'sketch-rapide',
    patterns: [
      { regex: /\bsketch\b/i, weight: 3, tag: 'sketch' },
      { regex: /\bbrouillon\b/i, weight: 3, tag: 'brouillon' },
      { regex: /\bmaquette\b/i, weight: 2, tag: 'maquette' },
      { regex: /\bwireframe\b/i, weight: 4, tag: 'wireframe' },
    ],
    controlNetPreset: 'scribble',
    preferredOutput: 'both',
  },
  {
    intent: 'graphique-data',
    patterns: [
      { regex: /\bgraphe?\b/i, weight: 3, tag: 'graphe' },
      { regex: /\bdiagramme (barres|circulaire|en barres)\b/i, weight: 4, tag: 'chart' },
      { regex: /\bcourbe(s)?\b/i, weight: 3, tag: 'courbe' },
      { regex: /\bhistogramme\b/i, weight: 4, tag: 'histogramme' },
      { regex: /\b(barchart|piechart|scatter|line ?chart)\b/i, weight: 4, tag: 'chart-en' },
    ],
    controlNetPreset: 'lineart',
    preferredOutput: 'svg',
  },
]

/**
 * Normalise un brief FR pour que les patterns regex matchent indépendamment
 * des accents (schéma == schema). Lower-case + NFD strip-diacritics + un
 * espace normalisé. Sans cette étape, les regex `\b` ne s'alignent pas avec
 * les caractères accentués (é, à, ê sont non-word en JS).
 */
function normaliseBriefForMatching(brief: string): string {
  return brief
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/\s+/g, ' ')
}

export function classifyDrawingIntent(brief: string): DrawingStyleClassification {
  const normalised = normaliseBriefForMatching(brief)
  const matched = new Map<DrawingIntentClass, { score: number; tags: string[] }>()
  for (const set of INTENT_SIGNALS) {
    let s = 0
    const tags: string[] = []
    for (const pat of set.patterns) {
      if (pat.regex.test(normalised)) { s += pat.weight; tags.push(pat.tag) }
    }
    if (s > 0) matched.set(set.intent, { score: s, tags })
  }
  if (matched.size === 0) {
    return {
      intent: 'sketch-rapide',
      confidence: 0.2,
      controlNetPreset: 'scribble',
      preferredOutput: 'both',
      matchedPatterns: [],
    }
  }
  const sorted = [...matched.entries()].sort((a, b) => b[1].score - a[1].score)
  const [topIntent, top] = sorted[0]
  const totalScore = sorted.reduce((acc, [, v]) => acc + v.score, 0)
  const preset = INTENT_SIGNALS.find((s) => s.intent === topIntent)!
  return {
    intent: topIntent,
    confidence: top.score / totalScore,
    controlNetPreset: preset.controlNetPreset,
    preferredOutput: preset.preferredOutput,
    matchedPatterns: top.tags,
  }
}

// --- SVG path builder -------------------------------------------------------
//
// Minimal mais bien typé : on construit des éléments primitifs (rect, circle,
// line, path, text), avec une "feuille de style" globale (palette Aurora) et
// un serialiseur stable. Sortie : string XML valide.

export type Color = string
export type SvgViewBox = { x: number; y: number; w: number; h: number }

export type SvgElement =
  | { kind: 'rect'; x: number; y: number; w: number; h: number; fill?: Color; stroke?: Color; strokeWidth?: number; rx?: number }
  | { kind: 'circle'; cx: number; cy: number; r: number; fill?: Color; stroke?: Color; strokeWidth?: number }
  | { kind: 'line'; x1: number; y1: number; x2: number; y2: number; stroke: Color; strokeWidth?: number; dash?: number[] }
  | { kind: 'path'; d: string; fill?: Color; stroke?: Color; strokeWidth?: number }
  | { kind: 'text'; x: number; y: number; text: string; fill?: Color; fontSize?: number; fontFamily?: string; anchor?: 'start' | 'middle' | 'end' }
  | { kind: 'group'; transform?: string; children: SvgElement[] }

export type SvgDocument = {
  viewBox: SvgViewBox
  width?: number
  height?: number
  /** Stylesheet appliqué à tout le document. */
  cssVariables: Record<string, string>
  elements: SvgElement[]
}

/** Aurora palette par défaut (cohérence avec l'app). */
export const AURORA_PALETTE = {
  primary: '#3aa4ff',
  secondary: '#ff5a1f',
  accent: '#ffd166',
  surface: '#0b1220',
  surfaceLight: '#1b2230',
  textPrimary: '#ffffff',
  textSecondary: '#9aa4ff',
  good: '#4dd5a4',
  warn: '#ffd166',
  bad: '#ff6a3d',
} as const

export function emptyDoc(viewBox: SvgViewBox = { x: 0, y: 0, w: 1000, h: 1000 }): SvgDocument {
  return {
    viewBox,
    cssVariables: { ...AURORA_PALETTE },
    elements: [],
  }
}

// --- Serialiseur ------------------------------------------------------------
export function serialise(doc: SvgDocument): string {
  const vb = `${doc.viewBox.x} ${doc.viewBox.y} ${doc.viewBox.w} ${doc.viewBox.h}`
  const w = doc.width != null ? ` width="${doc.width}"` : ''
  const h = doc.height != null ? ` height="${doc.height}"` : ''
  const css = Object.entries(doc.cssVariables).map(([k, v]) => `--${k}: ${v}`).join('; ')
  const inner = doc.elements.map(renderEl).join('\n  ')
  return `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}"${w}${h} style="${css}">\n  ${inner}\n</svg>`
}

function renderEl(el: SvgElement): string {
  switch (el.kind) {
    case 'rect':
      return `<rect x="${el.x}" y="${el.y}" width="${el.w}" height="${el.h}"${attr('rx', el.rx)}${attr('fill', el.fill)}${attr('stroke', el.stroke)}${attr('stroke-width', el.strokeWidth)} />`
    case 'circle':
      return `<circle cx="${el.cx}" cy="${el.cy}" r="${el.r}"${attr('fill', el.fill)}${attr('stroke', el.stroke)}${attr('stroke-width', el.strokeWidth)} />`
    case 'line':
      return `<line x1="${el.x1}" y1="${el.y1}" x2="${el.x2}" y2="${el.y2}" stroke="${el.stroke}"${attr('stroke-width', el.strokeWidth)}${el.dash ? ` stroke-dasharray="${el.dash.join(' ')}"` : ''} />`
    case 'path':
      return `<path d="${el.d}"${attr('fill', el.fill)}${attr('stroke', el.stroke)}${attr('stroke-width', el.strokeWidth)} />`
    case 'text':
      return `<text x="${el.x}" y="${el.y}"${attr('font-size', el.fontSize)}${attr('font-family', el.fontFamily)}${attr('text-anchor', el.anchor)}${attr('fill', el.fill)}>${escapeXml(el.text)}</text>`
    case 'group':
      return `<g${el.transform ? ` transform="${el.transform}"` : ''}>${el.children.map(renderEl).join('')}</g>`
  }
}

function attr(name: string, value: string | number | undefined): string {
  if (value == null || value === '') return ''
  return ` ${name}="${value}"`
}

function escapeXml(text: string): string {
  return text.replace(/[<>&"']/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' }[c]!))
}

// --- Helpers haut-niveau ----------------------------------------------------

/** Génère un schéma "boîtes + flèches" pour un diagramme-flow. */
export function flowChartDoc(nodes: Array<{ id: string; label: string; x: number; y: number; w?: number; h?: number }>, edges: Array<{ from: string; to: string; label?: string }>): SvgDocument {
  const doc = emptyDoc({ x: 0, y: 0, w: 1000, h: 800 })
  const byId = new Map(nodes.map((n) => [n.id, n]))
  // Edges first (drawn under nodes).
  for (const edge of edges) {
    const a = byId.get(edge.from)
    const b = byId.get(edge.to)
    if (!a || !b) continue
    const aw = a.w ?? 120, ah = a.h ?? 60
    const bw = b.w ?? 120, bh = b.h ?? 60
    doc.elements.push({
      kind: 'line',
      x1: a.x + aw / 2, y1: a.y + ah,
      x2: b.x + bw / 2, y2: b.y,
      stroke: AURORA_PALETTE.textSecondary,
      strokeWidth: 2,
    })
    if (edge.label) {
      doc.elements.push({
        kind: 'text',
        x: (a.x + aw / 2 + b.x + bw / 2) / 2,
        y: (a.y + ah + b.y) / 2 - 4,
        text: edge.label,
        anchor: 'middle',
        fontSize: 12,
        fill: AURORA_PALETTE.textSecondary,
        fontFamily: 'system-ui, sans-serif',
      })
    }
  }
  for (const node of nodes) {
    const w = node.w ?? 120
    const h = node.h ?? 60
    doc.elements.push({ kind: 'rect', x: node.x, y: node.y, w, h, rx: 12, fill: AURORA_PALETTE.surfaceLight, stroke: AURORA_PALETTE.primary, strokeWidth: 2 })
    doc.elements.push({ kind: 'text', x: node.x + w / 2, y: node.y + h / 2 + 5, text: node.label, anchor: 'middle', fontSize: 16, fill: AURORA_PALETTE.textPrimary, fontFamily: 'system-ui, sans-serif' })
  }
  return doc
}

/** Génère une grille pour aligner les croquis techniques sur un fond quadrillé. */
export function gridOverlay(viewBox: SvgViewBox, spacing = 40): SvgElement[] {
  const out: SvgElement[] = []
  for (let x = viewBox.x; x <= viewBox.x + viewBox.w; x += spacing) {
    out.push({ kind: 'line', x1: x, y1: viewBox.y, x2: x, y2: viewBox.y + viewBox.h, stroke: 'rgba(154,164,255,0.15)', strokeWidth: 0.5 })
  }
  for (let y = viewBox.y; y <= viewBox.y + viewBox.h; y += spacing) {
    out.push({ kind: 'line', x1: viewBox.x, y1: y, x2: viewBox.x + viewBox.w, y2: y, stroke: 'rgba(154,164,255,0.15)', strokeWidth: 0.5 })
  }
  return out
}

/** Multi-pass refinement plan — utilisé par l'orchestrateur drawing. */
export type RefinementPass = {
  passNumber: number
  goal: 'composition' | 'cleanup' | 'detail' | 'polish' | 'labels'
  controlNetWeight: number
  denoisingStrength: number
  promptAddition: string
}

export function planRefinementPasses(classification: DrawingStyleClassification): RefinementPass[] {
  if (classification.intent === 'sketch-rapide') {
    return [{ passNumber: 1, goal: 'composition', controlNetWeight: 0.9, denoisingStrength: 0.75, promptAddition: 'rough sketch, expressive lines' }]
  }
  if (classification.intent === 'schema-technique' || classification.intent === 'diagramme-flow') {
    return [
      { passNumber: 1, goal: 'composition', controlNetWeight: 1.0, denoisingStrength: 0.6, promptAddition: 'clean technical lines, ruler-straight strokes' },
      { passNumber: 2, goal: 'labels', controlNetWeight: 0.8, denoisingStrength: 0.3, promptAddition: 'precise labels in monospace font, no smudging' },
      { passNumber: 3, goal: 'polish', controlNetWeight: 0.5, denoisingStrength: 0.2, promptAddition: 'final polish, ensure all annotations readable' },
    ]
  }
  // Artistic chain
  return [
    { passNumber: 1, goal: 'composition', controlNetWeight: 0.85, denoisingStrength: 0.7, promptAddition: 'compose the overall shape' },
    { passNumber: 2, goal: 'detail', controlNetWeight: 0.6, denoisingStrength: 0.5, promptAddition: 'add texture and shading' },
    { passNumber: 3, goal: 'polish', controlNetWeight: 0.3, denoisingStrength: 0.3, promptAddition: 'polish, harmonise colors' },
  ]
}
