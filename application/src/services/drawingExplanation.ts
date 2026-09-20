import { layoutFlowchart, layoutToSvg, type LayoutEdge, type LayoutNode } from './drawingAutoLayout.ts'
import { AURORA_PALETTE, classifyDrawingIntent, serialise } from './drawingStyleAndSvg.ts'

/** Route explanatory relations to editable typography rather than diffusion-generated text. */
export function isExplanatoryDrawing(prompt: string): boolean {
  const intent = classifyDrawingIntent(prompt).intent
  if (intent === 'graphique-data' || intent === 'croquis-artistique') return false
  return intent === 'diagramme-flow' || intent === 'schema-technique'
    || /\b(explique|expliquer|explication|explanatory)\b/i.test(prompt)
}

export function explanationInstruction(prompt: string): string {
  return [
    'Produis un schéma explicatif sous forme de graphe JSON, sans Markdown ni SVG.',
    'Format : {"nodes":[{"id":"a","label":"Étape"}],"edges":[{"from":"a","to":"b","label":"relation"}]}',
    'De 1 à 16 nœuds, au plus 32 relations. Identifiants uniques. Chaque relation relie deux nœuds existants.',
    'Les flèches indiquent le sens des relations. Aucun nœud isolé si plusieurs nœuds sont présents.',
    'Libellés français précis : au plus 32 caractères par nœud et 24 par relation.',
    'Respecte les éléments, valeurs et relations demandés. Ne remplace pas une explication par une décoration.',
    'Si un croquis est fourni, conserve ses éléments identifiables et le sens de ses relations.',
    `Demande : ${prompt}`,
  ].join('\n')
}

function label(value: unknown, limit: number): string {
  if (typeof value !== 'string' || !value.trim() || value.trim().length > limit
      || /[\u0000-\u0008\u000B\u000C\u000E-\u001F\uFFFE\uFFFF]/.test(value)) {
    throw new Error(`Schéma : libellé manquant ou dépassant ${limit} caractères.`)
  }
  return value.trim()
}

export function explanationSvg(response: string, options: { monochrome?: boolean } = {}): string {
  const text = response.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '')
  if (text.length > 20000) throw new Error('Schéma : réponse trop volumineuse.')
  const graph = JSON.parse(text)
  if (!graph || !Array.isArray(graph.nodes) || !Array.isArray(graph.edges)
      || graph.nodes.length < 1 || graph.nodes.length > 16 || graph.edges.length > 32) {
    throw new Error('Schéma : graphe absent ou hors limites.')
  }
  const ids = new Set<string>()
  const nodes: LayoutNode[] = graph.nodes.map((node: Record<string, unknown> | null) => {
    if (!node || typeof node.id !== 'string' || !/^[a-zA-Z0-9_-]{1,40}$/.test(node.id) || ids.has(node.id)) {
      throw new Error('Schéma : identifiant de nœud invalide ou dupliqué.')
    }
    ids.add(node.id)
    return { id: node.id, label: label(node.label, 32) }
  })
  const edges: LayoutEdge[] = graph.edges.map((edge: Record<string, unknown> | null) => {
    if (!edge || typeof edge.from !== 'string' || typeof edge.to !== 'string'
        || !ids.has(edge.from) || !ids.has(edge.to) || edge.from === edge.to) {
      throw new Error('Schéma : relation vers un nœud absent ou vers lui-même.')
    }
    return { from: edge.from, to: edge.to, label: edge.label === undefined ? undefined : label(edge.label, 24) }
  })
  if (nodes.length > 1 && nodes.some((node) => !edges.some((edge) => edge.from === node.id || edge.to === node.id))) {
    throw new Error('Schéma : un élément est isolé de l’explication.')
  }
  const nodeWidth = Math.max(340, ...nodes.map((node) => node.label.length * 16 + 40))
  const layout = layoutFlowchart(nodes, edges, { nodeWidth, nodeHeight: 72, vGap: 100, hGap: 80 })
  const doc = layoutToSvg({ ...layout, edges: [] })
  const nodeElements = doc.elements
  doc.elements = []
  doc.width = layout.viewBox.w
  doc.height = layout.viewBox.h
  let outsideLanes = 0
  for (const edge of edges) {
    const source = layout.nodes.find((node) => node.id === edge.from)!
    const target = layout.nodes.find((node) => node.id === edge.to)!
    let x = target.x + target.w / 2
    let y = target.y
    let angle: number
    let path: string
    let labelX: number
    let labelY: number
    const outside = target.y <= source.y || target.y - source.y > 172
    if (outside) {
      // Return and skip-level arrows run beside the boxes, preserving cycles visibly.
      const lane = layout.viewBox.w - 30 + outsideLanes++ * 28
      x = target.x + target.w
      y = target.y + target.h / 2
      const sourceX = source.x + source.w
      const sourceY = source.y + source.h / 2
      path = `M ${sourceX} ${sourceY} L ${lane} ${sourceY} L ${lane} ${y} L ${x} ${y}`
      angle = Math.PI
      labelX = lane + 8
      labelY = (sourceY + y) / 2
      doc.width = Math.max(doc.width, lane + 250)
    } else {
      const sourceX = source.x + source.w / 2
      const sourceY = source.y + source.h
      path = `M ${sourceX} ${sourceY} L ${x} ${y}`
      angle = Math.atan2(y - sourceY, x - sourceX)
      labelX = (sourceX + x) / 2 + 12
      labelY = (sourceY + y) / 2 - 8
    }
    doc.elements.push({ kind: 'path', d: path, fill: 'none', stroke: AURORA_PALETTE.textSecondary, strokeWidth: 2 })
    const a = [x - 12 * Math.cos(angle - 0.45), y - 12 * Math.sin(angle - 0.45)]
    const b = [x - 12 * Math.cos(angle + 0.45), y - 12 * Math.sin(angle + 0.45)]
    doc.elements.push({ kind: 'path', d: `M ${x} ${y} L ${a.join(' ')} L ${b.join(' ')} Z`, fill: AURORA_PALETTE.textSecondary })
    if (edge.label) doc.width = Math.max(doc.width, labelX + edge.label.length * 13 + 20)
    if (edge.label) doc.elements.push({
      kind: 'text', x: labelX, y: labelY, text: edge.label,
      anchor: 'start', fontSize: 13,
      fontFamily: 'system-ui, sans-serif', fill: AURORA_PALETTE.textSecondary,
    })
  }
  doc.viewBox = { ...layout.viewBox, w: doc.width }
  doc.elements.unshift({ kind: 'rect', x: 0, y: 0, w: doc.width, h: doc.height, fill: '#10131d' })
  doc.elements.push(...nodeElements)
  if (options.monochrome) {
    for (const element of doc.elements) {
      if (element.kind === 'rect') {
        element.fill = '#ffffff'
        if (element.stroke) element.stroke = '#111111'
      } else if (element.kind === 'text') {
        element.fill = '#111111'
      } else if (element.kind === 'path') {
        if (element.fill !== 'none') element.fill = '#111111'
        if (element.stroke) element.stroke = '#111111'
      }
    }
  }
  return serialise(doc)
}

/** Retry one invalid graph with validation feedback; transport failures remain explicit. */
export async function generateExplanationWithRepair(
  requestGraph: (correction?: string) => Promise<string>,
  signal: AbortSignal,
  options: { monochrome?: boolean } = {},
): Promise<string> {
  signal.throwIfAborted()
  const first = await requestGraph()
  signal.throwIfAborted()
  let correction: string
  try {
    return explanationSvg(first, options)
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error)
    correction = [
      'Le graphe précédent est invalide. Corrige-le en conservant la demande et ses relations.',
      `Erreur de validation : ${reason}`,
      `Réponse précédente : ${first.slice(0, 12000)}`,
      'Renvoie uniquement le graphe JSON corrigé dans le format demandé.',
    ].join('\n')
  }
  signal.throwIfAborted()
  const repaired = await requestGraph(correction)
  signal.throwIfAborted()
  try {
    return explanationSvg(repaired, options)
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error)
    throw new Error(`Schéma non validé après une correction automatique : ${reason}`)
  }
}

export async function sketchBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer())
  let binary = ''
  for (let start = 0; start < bytes.length; start += 8192) {
    binary += String.fromCharCode(...bytes.subarray(start, start + 8192))
  }
  return btoa(binary)
}
