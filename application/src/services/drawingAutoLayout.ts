// SVG auto-layout pour les flowcharts.
//
// Au lieu d'exiger que l'appelant fournisse des (x, y) pour chaque node,
// on prend juste un graphe (nodes + edges) et on calcule un placement
// raisonnable :
//   - tri topologique (DAG)
//   - placement par niveaux (couche horizontale ou verticale)
//   - centrage automatique
//   - répartition uniforme par couche
//
// Inspiré de la couche de placement de Graphviz "dot" (longest path
// layering), mais simplifié pour un usage temps réel côté navigateur.

import { AURORA_PALETTE, flowChartDoc, type SvgDocument } from './drawingStyleAndSvg.ts'

export type LayoutNode = {
  id: string
  label: string
  /** Optionnel : si fourni, déplacé pour respecter la dimension. */
  width?: number
  height?: number
}

export type LayoutEdge = {
  from: string
  to: string
  label?: string
}

export type LayoutOptions = {
  direction?: 'TB' | 'LR'
  nodeWidth?: number
  nodeHeight?: number
  hGap?: number
  vGap?: number
  marginX?: number
  marginY?: number
}

const DEFAULTS: Required<LayoutOptions> = {
  direction: 'TB',
  nodeWidth: 140,
  nodeHeight: 60,
  hGap: 40,
  vGap: 60,
  marginX: 60,
  marginY: 60,
}

export type LaidOutNode = LayoutNode & { x: number; y: number; w: number; h: number }
export type LayoutResult = {
  nodes: LaidOutNode[]
  edges: LayoutEdge[]
  viewBox: { x: number; y: number; w: number; h: number }
  /** Indique si le graphe contenait un cycle (le tri topo a quand même produit un layout par BFS). */
  hasCycle: boolean
}

/** Tri topologique stable ; renvoie l'ordre de visite et un flag de cycle. */
function topologicalLayers(nodes: LayoutNode[], edges: LayoutEdge[]): { layers: string[][]; hasCycle: boolean } {
  const adj = new Map<string, string[]>()
  const inDeg = new Map<string, number>()
  for (const n of nodes) {
    adj.set(n.id, [])
    inDeg.set(n.id, 0)
  }
  for (const e of edges) {
    if (!adj.has(e.from) || !adj.has(e.to)) continue
    adj.get(e.from)!.push(e.to)
    inDeg.set(e.to, (inDeg.get(e.to) ?? 0) + 1)
  }

  const layers: string[][] = []
  const remaining = new Map(inDeg)
  let cycleBroken = false
  let safety = nodes.length * 2 + 1
  while (remaining.size > 0 && safety > 0) {
    safety -= 1
    const layer: string[] = []
    for (const [id, deg] of remaining) {
      if (deg === 0) layer.push(id)
    }
    if (layer.length === 0) {
      // Cycle restant : on prend le min in-degree pour casser.
      let minId = ''
      let minDeg = Infinity
      for (const [id, deg] of remaining) {
        if (deg < minDeg) { minDeg = deg; minId = id }
      }
      if (minId) {
        layer.push(minId)
        // On a forcé un placement avec in-degree > 0 → présence d'un cycle.
        cycleBroken = true
      }
    }
    layer.sort()
    layers.push(layer)
    for (const id of layer) {
      remaining.delete(id)
      for (const next of adj.get(id) ?? []) {
        if (remaining.has(next)) remaining.set(next, (remaining.get(next) ?? 0) - 1)
      }
    }
  }
  const hasCycle = cycleBroken || remaining.size > 0 || safety <= 0
  return { layers, hasCycle }
}

/**
 * Calcule un placement des nodes selon un direction TB ou LR.
 * Toutes les nodes d'une couche partagent une coordonnée (y si TB, x si LR).
 */
export function layoutFlowchart(nodes: LayoutNode[], edges: LayoutEdge[], opts: LayoutOptions = {}): LayoutResult {
  const cfg = { ...DEFAULTS, ...opts }
  const { layers, hasCycle } = topologicalLayers(nodes, edges)

  const widthByLayer = layers.map((l) => l.length)
  const maxLayerSize = Math.max(1, ...widthByLayer)
  const nodeWidth = cfg.nodeWidth
  const nodeHeight = cfg.nodeHeight
  const out: LaidOutNode[] = []

  let totalW = 0
  let totalH = 0

  if (cfg.direction === 'TB') {
    for (let li = 0; li < layers.length; li += 1) {
      const layer = layers[li]
      const layerW = layer.length * nodeWidth + (layer.length - 1) * cfg.hGap
      const fullW = maxLayerSize * nodeWidth + (maxLayerSize - 1) * cfg.hGap
      const xStart = cfg.marginX + (fullW - layerW) / 2
      const y = cfg.marginY + li * (nodeHeight + cfg.vGap)
      for (let i = 0; i < layer.length; i += 1) {
        const id = layer[i]
        const def = nodes.find((n) => n.id === id)
        if (!def) continue
        out.push({
          ...def,
          x: xStart + i * (nodeWidth + cfg.hGap),
          y,
          w: def.width ?? nodeWidth,
          h: def.height ?? nodeHeight,
        })
      }
    }
    totalW = cfg.marginX * 2 + maxLayerSize * nodeWidth + (maxLayerSize - 1) * cfg.hGap
    totalH = cfg.marginY * 2 + layers.length * nodeHeight + (layers.length - 1) * cfg.vGap
  } else {
    // LR : layers deviennent des colonnes.
    for (let li = 0; li < layers.length; li += 1) {
      const layer = layers[li]
      const layerH = layer.length * nodeHeight + (layer.length - 1) * cfg.vGap
      const fullH = maxLayerSize * nodeHeight + (maxLayerSize - 1) * cfg.vGap
      const yStart = cfg.marginY + (fullH - layerH) / 2
      const x = cfg.marginX + li * (nodeWidth + cfg.hGap)
      for (let i = 0; i < layer.length; i += 1) {
        const id = layer[i]
        const def = nodes.find((n) => n.id === id)
        if (!def) continue
        out.push({
          ...def,
          x,
          y: yStart + i * (nodeHeight + cfg.vGap),
          w: def.width ?? nodeWidth,
          h: def.height ?? nodeHeight,
        })
      }
    }
    totalW = cfg.marginX * 2 + layers.length * nodeWidth + (layers.length - 1) * cfg.hGap
    totalH = cfg.marginY * 2 + maxLayerSize * nodeHeight + (maxLayerSize - 1) * cfg.vGap
  }

  return {
    nodes: out,
    edges,
    viewBox: { x: 0, y: 0, w: totalW, h: totalH },
    hasCycle,
  }
}

/**
 * Construit le SvgDocument à partir d'un layout calculé. Choisit
 * automatiquement la couleur des nodes (palette Aurora) + dessine les
 * edges avec petite flèche.
 */
export function layoutToSvg(layout: LayoutResult): SvgDocument {
  const doc = flowChartDoc(
    layout.nodes.map((n) => ({ id: n.id, label: n.label, x: n.x, y: n.y, w: n.w, h: n.h })),
    layout.edges,
  )
  doc.viewBox = layout.viewBox
  doc.cssVariables = { ...AURORA_PALETTE }
  return doc
}

// --- Radial layout ---------------------------------------------------------
// Pour les structures "1 centre + N feuilles" (mind map, cas d'usage).
// Place le root au centre et distribue les enfants sur un cercle. Plusieurs
// niveaux supportés via rayons concentriques.

export type RadialOptions = {
  /** ID du nœud racine. */
  rootId: string
  /** Rayon du premier cercle. */
  baseRadius?: number
  /** Espacement angulaire min entre 2 feuilles (rad). */
  minAngleRad?: number
  /** Largeur/hauteur par nœud. */
  nodeWidth?: number
  nodeHeight?: number
  /** Centre du diagramme. */
  centerX?: number
  centerY?: number
}

const RADIAL_DEFAULTS: Required<Omit<RadialOptions, 'rootId'>> = {
  baseRadius: 160,
  minAngleRad: Math.PI / 18, // 10°
  nodeWidth: 140,
  nodeHeight: 60,
  centerX: 400,
  centerY: 400,
}

/**
 * Place les nodes en arbre radial.
 *   - root au centre
 *   - enfants directs sur le 1er cercle (rayon = baseRadius)
 *   - petits-enfants sur le 2e cercle (rayon = 2 × baseRadius)
 *   - …
 *
 * Si un nœud n'est pas dans l'arbre du root, il est placé "hors" — orbite
 * détachée plus loin.
 */
export function layoutRadial(nodes: LayoutNode[], edges: LayoutEdge[], opts: RadialOptions): LayoutResult {
  const cfg = { ...RADIAL_DEFAULTS, ...opts }
  if (!nodes.some((n) => n.id === opts.rootId)) {
    // root inexistant — fallback layoutFlowchart TB
    return layoutFlowchart(nodes, edges, { direction: 'TB' })
  }

  // Construit l'arbre BFS depuis root via edges (from→to).
  const adj = new Map<string, string[]>()
  for (const n of nodes) adj.set(n.id, [])
  for (const e of edges) {
    if (adj.has(e.from)) adj.get(e.from)!.push(e.to)
  }

  const depth = new Map<string, number>()
  depth.set(opts.rootId, 0)
  const queue = [opts.rootId]
  while (queue.length > 0) {
    const cur = queue.shift()!
    const d = depth.get(cur)!
    for (const child of adj.get(cur) ?? []) {
      if (!depth.has(child)) {
        depth.set(child, d + 1)
        queue.push(child)
      }
    }
  }

  // Group nodes par depth.
  const byDepth = new Map<number, string[]>()
  for (const [id, d] of depth) {
    if (!byDepth.has(d)) byDepth.set(d, [])
    byDepth.get(d)!.push(id)
  }

  const out: LaidOutNode[] = []
  const rootNode = nodes.find((n) => n.id === opts.rootId)!
  out.push({
    ...rootNode,
    x: cfg.centerX - cfg.nodeWidth / 2,
    y: cfg.centerY - cfg.nodeHeight / 2,
    w: rootNode.width ?? cfg.nodeWidth,
    h: rootNode.height ?? cfg.nodeHeight,
  })

  let maxDepthSeen = 0
  for (const [d, ids] of byDepth) {
    if (d === 0) continue
    maxDepthSeen = Math.max(maxDepthSeen, d)
    const radius = cfg.baseRadius * d
    const angleStep = Math.max(cfg.minAngleRad, (2 * Math.PI) / Math.max(1, ids.length))
    ids.sort()
    for (let i = 0; i < ids.length; i += 1) {
      const id = ids[i]
      const def = nodes.find((n) => n.id === id)
      if (!def) continue
      const angle = i * angleStep
      const cx = cfg.centerX + radius * Math.cos(angle)
      const cy = cfg.centerY + radius * Math.sin(angle)
      out.push({
        ...def,
        x: cx - cfg.nodeWidth / 2,
        y: cy - cfg.nodeHeight / 2,
        w: def.width ?? cfg.nodeWidth,
        h: def.height ?? cfg.nodeHeight,
      })
    }
  }

  // Disconnected nodes : orbite plus loin.
  const placed = new Set(out.map((n) => n.id))
  const orphans = nodes.filter((n) => !placed.has(n.id))
  if (orphans.length > 0) {
    const orbitR = cfg.baseRadius * (maxDepthSeen + 2)
    for (let i = 0; i < orphans.length; i += 1) {
      const angle = (i / Math.max(1, orphans.length)) * 2 * Math.PI
      out.push({
        ...orphans[i],
        x: cfg.centerX + orbitR * Math.cos(angle) - cfg.nodeWidth / 2,
        y: cfg.centerY + orbitR * Math.sin(angle) - cfg.nodeHeight / 2,
        w: orphans[i].width ?? cfg.nodeWidth,
        h: orphans[i].height ?? cfg.nodeHeight,
      })
    }
  }

  // ViewBox : englobe tous les centres + padding.
  const padding = 80
  const xs = out.map((n) => n.x)
  const ys = out.map((n) => n.y)
  const minX = Math.min(...xs, cfg.centerX) - padding
  const minY = Math.min(...ys, cfg.centerY) - padding
  const maxX = Math.max(...xs.map((x, i) => x + (out[i]?.w ?? cfg.nodeWidth)), cfg.centerX) + padding
  const maxY = Math.max(...ys.map((y, i) => y + (out[i]?.h ?? cfg.nodeHeight)), cfg.centerY) + padding

  return {
    nodes: out,
    edges,
    viewBox: { x: minX, y: minY, w: maxX - minX, h: maxY - minY },
    hasCycle: false, // par construction, BFS
  }
}
