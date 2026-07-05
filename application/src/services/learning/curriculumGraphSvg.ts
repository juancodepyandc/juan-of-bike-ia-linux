// Branche `bacSti2dCurriculum` (qui contient les prérequis) sur l'auto-layout
// flowchart de `drawingAutoLayout`. Sortie : un SVG du programme STI2D/SIN
// où chaque nœud est un concept et les flèches partent du prérequis vers
// le concept qui en dépend.
//
// Utilisable depuis Dashboard.tsx pour afficher "voilà l'arbre du BO et où
// tu en es", ou comme export PDF pour un cours imprimé.

import {
  layoutFlowchart,
  layoutToSvg,
  type LayoutEdge,
  type LayoutNode,
} from '../drawingAutoLayout.ts'
import { serialise, type SvgDocument } from '../drawingStyleAndSvg.ts'
import { BAC_STI2D_CURRICULUM, nodesByTrack, nodesByYear, type CurriculumNode, type SchoolYear } from './bacSti2dCurriculum.ts'

export type CurriculumSvgOptions = {
  /** Filtrer par année (1ère / Tle). Default : toutes les années. */
  year?: SchoolYear
  /** Filtrer par discipline. Default : toutes. */
  track?: CurriculumNode['track']
  /** Direction de lecture du graphe. Default 'TB'. */
  direction?: 'TB' | 'LR'
  /** Si fourni, ces ids reçoivent un fond "complété" dans le SVG. */
  completedIds?: Set<string>
}

/**
 * Construit le SvgDocument pour un sous-ensemble de la taxonomie BO STI2D.
 * Renvoie aussi le rapport de cycles (le graphe ne devrait jamais en avoir,
 * mais on garde la sécurité au cas où la taxonomie évolue mal).
 */
export function buildCurriculumSvg(opts: CurriculumSvgOptions = {}): { doc: SvgDocument; nodeCount: number; edgeCount: number; hasCycle: boolean } {
  const direction = opts.direction ?? 'TB'
  let pool: readonly CurriculumNode[] = BAC_STI2D_CURRICULUM
  if (opts.year) pool = nodesByYear(opts.year)
  if (opts.track) pool = pool.filter((n) => n.track === opts.track)

  const poolIds = new Set(pool.map((n) => n.id))
  const layoutNodes: LayoutNode[] = pool.map((n) => ({
    id: n.id,
    label: shortLabel(n),
    width: 180,
    height: 64,
  }))

  const edges: LayoutEdge[] = []
  for (const node of pool) {
    for (const pre of node.prerequisites ?? []) {
      if (poolIds.has(pre)) edges.push({ from: pre, to: node.id })
    }
  }

  const layout = layoutFlowchart(layoutNodes, edges, { direction, nodeWidth: 180, nodeHeight: 64, hGap: 24, vGap: 70 })
  const doc = layoutToSvg(layout)

  // Highlight des nœuds complétés : remplace fill de la rect par une teinte verdâtre.
  if (opts.completedIds && opts.completedIds.size > 0) {
    for (const el of doc.elements) {
      if (el.kind === 'rect') {
        const matchedNode = layout.nodes.find((n) => Math.round(n.x) === Math.round(el.x) && Math.round(n.y) === Math.round(el.y))
        if (matchedNode && opts.completedIds.has(matchedNode.id)) {
          el.fill = doc.cssVariables.good ?? '#4dd5a4'
        }
      }
    }
  }

  return { doc, nodeCount: layoutNodes.length, edgeCount: edges.length, hasCycle: layout.hasCycle }
}

/** Sérialise directement le SVG d'un sous-ensemble du curriculum. */
export function curriculumSvgString(opts: CurriculumSvgOptions = {}): string {
  return serialise(buildCurriculumSvg(opts).doc)
}

function shortLabel(node: CurriculumNode): string {
  // Le label complet peut être trop long pour une boîte 180×64 ; on garde
  // les ~40 premiers caractères, à un mot-frontière près.
  const label = node.label
  if (label.length <= 40) return label
  const cut = label.slice(0, 40)
  const lastSpace = cut.lastIndexOf(' ')
  return (lastSpace > 20 ? cut.slice(0, lastSpace) : cut) + '…'
}
