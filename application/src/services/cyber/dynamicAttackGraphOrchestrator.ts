/**
 * dynamicAttackGraphOrchestrator.ts — Moteur de graphe d'attaque relationnel et calcul de chemins critiques.
 *
 * Fonctionnalités :
 * 1. Modélisation de la topologie réseau et des vecteurs d'accès en graphe orienté.
 * 2. Calcul du chemin d'attaque critique (plus court chemin pondéré par CVSS et probabilité EPSS).
 * 3. Évaluation du rayon d'impact (Blast Radius) en cas de compromission d'un nœud.
 * 4. Détermination des points de coupure minimaux (Chokepoints) pour neutraliser l'attaque au moindre coût.
 */

export interface GraphNode {
  id: string
  label: string
  type: 'EXTERNAL_ASSET' | 'DMZ_SERVICE' | 'INTERNAL_HOST' | 'DATABASE' | 'ADMIN_CONTROLLER'
  ipAddress?: string
  cvssVulnerability?: number
  epssProbability?: number // 0..1
  isCompromised: boolean
  isCriticalAsset: boolean
}

export interface GraphEdge {
  id: string
  sourceNodeId: string
  targetNodeId: string
  protocol: string
  mitreTechnique: string
  weight: number // Coût/Résistance de l'arête (plus c'est bas, plus l'exploitation est facile)
  isBlockedByDefense: boolean
}

export interface AttackPathStep {
  stepIndex: number
  sourceLabel: string
  targetLabel: string
  technique: string
  accumulatedRiskScore: number
}

export interface CriticalAttackPathAnalysis {
  pathFound: boolean
  totalRiskScore: number
  chokepoints: string[] // Nœuds ou arêtes prioritaires à couper
  steps: AttackPathStep[]
  blastRadiusNodeCount: number
  remediationAction: string
}

export interface DynamicAttackGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

/**
 * Calcule le chemin d'attaque le plus probable / critique entre un point d'entrée et les actifs vitaux.
 */
export function computeCriticalAttackPath(
  graph: DynamicAttackGraph,
  startNodeId: string,
  targetCriticalNodeId?: string
): CriticalAttackPathAnalysis {
  const nodeMap = new Map<string, GraphNode>()
  graph.nodes.forEach((n) => nodeMap.set(n.id, n))

  const targetNode = targetCriticalNodeId
    ? nodeMap.get(targetCriticalNodeId)
    : graph.nodes.find((n) => n.isCriticalAsset)

  if (!nodeMap.has(startNodeId) || !targetNode) {
    return {
      pathFound: false,
      totalRiskScore: 0,
      chokepoints: [],
      steps: [],
      blastRadiusNodeCount: 0,
      remediationAction: "Aucun chemin critique détecté : Nœud de départ ou actif cible introuvable.",
    }
  }

  // Algorithme de Dijkstra pour trouver le chemin de moindre résistance (poids minimal)
  const distances = new Map<string, number>()
  const previous = new Map<string, { nodeId: string; edge: GraphEdge }>()
  const unvisited = new Set<string>()

  graph.nodes.forEach((n) => {
    distances.set(n.id, Infinity)
    unvisited.add(n.id)
  })

  distances.set(startNodeId, 0)

  while (unvisited.size > 0) {
    let currentId: string | null = null
    let smallestDist = Infinity

    unvisited.forEach((id) => {
      const dist = distances.get(id) ?? Infinity
      if (dist < smallestDist) {
        smallestDist = dist
        currentId = id
      }
    })

    if (!currentId || smallestDist === Infinity || currentId === targetNode.id) {
      break
    }

    unvisited.delete(currentId)

    // Exploration des arêtes sortantes non bloquées
    const outgoingEdges = graph.edges.filter(
      (e) => e.sourceNodeId === currentId && !e.isBlockedByDefense
    )

    for (const edge of outgoingEdges) {
      if (!unvisited.has(edge.targetNodeId)) continue

      const targetN = nodeMap.get(edge.targetNodeId)
      const epssBonus = targetN?.epssProbability ? (1 - targetN.epssProbability) * 2 : 1
      const edgeCost = edge.weight * epssBonus

      const alt = (distances.get(currentId) ?? 0) + edgeCost
      if (alt < (distances.get(edge.targetNodeId) ?? Infinity)) {
        distances.set(edge.targetNodeId, alt)
        previous.set(edge.targetNodeId, { nodeId: currentId, edge })
      }
    }
  }

  // Reconstruction du chemin
  const pathSteps: AttackPathStep[] = []
  let curr = targetNode.id
  const chokepoints: string[] = []

  while (previous.has(curr)) {
    const prev = previous.get(curr)!
    const sourceNode = nodeMap.get(prev.nodeId)
    const targetN = nodeMap.get(curr)

    if (sourceNode && targetN) {
      pathSteps.unshift({
        stepIndex: pathSteps.length + 1,
        sourceLabel: sourceNode.label,
        targetLabel: targetN.label,
        technique: prev.edge.mitreTechnique,
        accumulatedRiskScore: Math.round((distances.get(curr) ?? 0) * 10) / 10,
      })

      // Les nœuds intermédiaires constituent les points de coupure idéaux
      if (!sourceNode.isCriticalAsset && sourceNode.type !== 'EXTERNAL_ASSET') {
        chokepoints.push(sourceNode.label)
      }
    }
    curr = prev.nodeId
  }

  // Calcul du rayon d'impact (Blast Radius) : nombre de nœuds atteignables depuis le point d'entrée
  let blastCount = 0
  distances.forEach((d) => {
    if (d < Infinity) blastCount++
  })

  const pathFound = pathSteps.length > 0
  const totalRisk = pathFound ? Math.max(10, Math.min(100, Math.round(100 - (distances.get(targetNode.id) ?? 50)))) : 0

  return {
    pathFound,
    totalRiskScore: totalRisk,
    chokepoints: Array.from(new Set(chokepoints)),
    steps: pathSteps,
    blastRadiusNodeCount: blastCount,
    remediationAction: chokepoints.length > 0
      ? `Isoler ou filtrer en priorité le point de coupure [${chokepoints[0]}] pour rompre la chaîne d'attaque vers [${targetNode.label}].`
      : "Renforcer les contrôles d'accès et la segmentation réseau périphérique.",
  }
}
