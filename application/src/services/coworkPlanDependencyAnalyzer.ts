// Analyse de dépendances dans un CoworkPlan : identifie quelle action
// dépend de quelle autre (par data-flow heuristique) et calcule le chemin
// critique. Utile pour :
//
//   1. Paralléliser : actions indépendantes peuvent tourner en parallèle
//   2. Chemin critique : "ce plan prend X secondes, dont Y % sur la chaîne A→B→C"
//   3. Suggestions de réordonnancement : "lance read_file en premier, c'est
//      pas cher et ça débloque la suite"
//
// Heuristique de dépendance :
//   - write_file(path) dépend des read_file/fetch précédents
//   - shell(cmd) dépend de tout fichier mentionné dans le cmd
//   - fetch dépend de variables d'env / token précédemment écrits
//   - finish dépend implicitement de toutes les actions précédentes

import { estimateAction, type CostModel } from './coworkPlanEstimator.ts'
import type { CoworkAction, CoworkPlan } from './coworkTypes.ts'

export type DependencyEdge = {
  from: number // index source dans plan.actions
  to: number   // index dépendant
  reason: string
}

export type ActionNode = {
  index: number
  action: CoworkAction
  /** Index des actions dont celle-ci dépend (in-edges). */
  dependsOn: number[]
  /** Index des actions qui dépendent de celle-ci (out-edges). */
  dependents: number[]
  /** Durée estimée (ms). */
  durationMs: number
}

export type DependencyAnalysis = {
  nodes: ActionNode[]
  edges: DependencyEdge[]
  /** Indices des actions exécutables immédiatement (in-degree = 0). */
  initialFront: number[]
  /** Chemin critique (séquence d'indices avec durées). */
  criticalPath: number[]
  /** Durée totale du chemin critique (ms). */
  criticalPathMs: number
  /** Durée minimum si toutes les indépendances tournent en parallèle. */
  minDurationMs: number
  /** Durée séquentielle (sans parallélisation). */
  sequentialDurationMs: number
}

function actionPaths(action: CoworkAction): string[] {
  switch (action.kind) {
    case 'read_file':
    case 'write_file':
    case 'edit_file':
    case 'delete_file':
    case 'list_dir':
      return [action.path]
    case 'shell':
      // Extract tokens that ressemble à des paths (segments avec / ou .ts/.py/...)
      return [action.command, ...action.args].filter((s) => /[\/.]\w+/.test(s))
    default:
      return []
  }
}

function actionConsumes(a: CoworkAction): 'reads' | 'writes' | 'both' | 'none' {
  switch (a.kind) {
    case 'read_file':
    case 'list_dir':
    case 'fetch':
    case 'web_search':
    case 'dom_query':
    case 'clipboard_read':
      return 'reads'
    case 'write_file':
    case 'delete_file':
    case 'clipboard_write':
      return 'writes'
    case 'edit_file':
    case 'shell':
      return 'both'
    default:
      return 'none'
  }
}

/**
 * Build dependency graph. Heuristiques :
 *   - écriture sur P dépend de toute lecture précédente sur P (read-then-write)
 *   - lecture sur P dépend de toute écriture précédente sur P (write-then-read)
 *   - shell dépend de toute écriture précédente sur les paths mentionnés
 *   - finish dépend de tout (sauf 'think')
 *   - vision_describe dépend de l'image_data_url (peut venir d'une screenshot
 *     précédente)
 *   - think_long dépend d'aucune action précédente (peut tourner en parallèle)
 */
export function analyzeDependencies(plan: CoworkPlan, costModel?: CostModel): DependencyAnalysis {
  const actions = plan.actions
  const nodes: ActionNode[] = actions.map((action, index) => {
    const dur = estimateAction(action, costModel).durationMs
    return { index, action, dependsOn: [], dependents: [], durationMs: dur }
  })
  const edges: DependencyEdge[] = []

  // Pour chaque action, regarde les actions précédentes pour des conflits.
  for (let i = 0; i < actions.length; i += 1) {
    const a = actions[i]
    const pathsA = actionPaths(a)
    const consumesA = actionConsumes(a)

    if (a.kind === 'finish') {
      // finish dépend de toutes les actions non-think précédentes.
      for (let j = 0; j < i; j += 1) {
        if (actions[j].kind === 'think') continue
        nodes[i].dependsOn.push(j)
        nodes[j].dependents.push(i)
        edges.push({ from: j, to: i, reason: 'finish dépend de toutes les actions précédentes' })
      }
      continue
    }

    if (a.kind === 'vision_describe') {
      // Vision dépend de la screenshot ou edit précédent. Heuristique :
      // si une action précédente est browser.screenshot, on lie.
      for (let j = 0; j < i; j += 1) {
        if (actions[j].kind === 'browser' && (actions[j] as { operation: string }).operation === 'screenshot') {
          nodes[i].dependsOn.push(j)
          nodes[j].dependents.push(i)
          edges.push({ from: j, to: i, reason: 'vision_describe consomme la screenshot' })
          break
        }
      }
      continue
    }

    for (let j = 0; j < i; j += 1) {
      const b = actions[j]
      const pathsB = actionPaths(b)
      const consumesB = actionConsumes(b)
      const sharedPath = pathsA.find((p) => pathsB.includes(p))
      if (!sharedPath) continue

      const aReads = consumesA === 'reads' || consumesA === 'both'
      const aWrites = consumesA === 'writes' || consumesA === 'both'
      const bWrites = consumesB === 'writes' || consumesB === 'both'
      const bReads = consumesB === 'reads' || consumesB === 'both'

      let reason: string | null = null
      if (aWrites && bReads) reason = `write-after-read sur ${sharedPath}`
      else if (aReads && bWrites) reason = `read-after-write sur ${sharedPath}`
      else if (aWrites && bWrites) reason = `write-after-write sur ${sharedPath}`

      if (reason) {
        nodes[i].dependsOn.push(j)
        nodes[j].dependents.push(i)
        edges.push({ from: j, to: i, reason })
      }
    }
  }

  // initialFront : actions sans dépendance.
  const initialFront = nodes.filter((n) => n.dependsOn.length === 0).map((n) => n.index)

  // Sequential = somme des durées.
  const sequentialDurationMs = nodes.reduce((s, n) => s + n.durationMs, 0)

  // CriticalPath par DP : longestPath(i) = duration(i) + max(longestPath(j) pour j dans dependsOn(i)).
  const longest = new Array<number>(nodes.length).fill(0)
  const predecessor = new Array<number>(nodes.length).fill(-1)
  // Tri topologique implicite via les index (le plan est déjà ordonné).
  for (let i = 0; i < nodes.length; i += 1) {
    let maxPred = 0
    for (const dep of nodes[i].dependsOn) {
      if (longest[dep] > maxPred) {
        maxPred = longest[dep]
        predecessor[i] = dep
      }
    }
    longest[i] = maxPred + nodes[i].durationMs
  }
  // Trouve l'action terminale du chemin critique = celle qui maximise longest.
  // Cas particulier : nodes vide ↦ aucun chemin critique, on évite la boucle
  // ci-dessous (sinon `predecessor[0]` est undefined et `undefined !== -1` =>
  // boucle infinie).
  const criticalPath: number[] = []
  let criticalPathMs = 0
  if (nodes.length > 0) {
    let endIdx = 0
    for (let i = 1; i < longest.length; i += 1) {
      if (longest[i] > longest[endIdx]) endIdx = i
    }
    let cur: number = endIdx
    let guard = 0
    while (cur !== -1 && guard < nodes.length + 1) {
      criticalPath.unshift(cur)
      const pred = predecessor[cur]
      // Garde-fou : undefined ou pointeur hors range ↦ on stoppe.
      if (pred == null || pred < 0 || pred >= nodes.length) break
      cur = pred
      guard += 1
    }
    criticalPathMs = longest[endIdx]
  }

  return {
    nodes,
    edges,
    initialFront,
    criticalPath,
    criticalPathMs,
    minDurationMs: criticalPathMs,
    sequentialDurationMs,
  }
}

/**
 * Suggestion de réordonnancement : si on respecte les dépendances mais
 * qu'on peut paralléliser, retourne les "vagues" d'exécution. Chaque vague
 * = actions à in-degree=0 dans le DAG restant.
 */
export function executionWaves(analysis: DependencyAnalysis): number[][] {
  const inDeg = new Map<number, number>()
  for (const node of analysis.nodes) inDeg.set(node.index, node.dependsOn.length)
  const dependents = new Map<number, number[]>()
  for (const node of analysis.nodes) dependents.set(node.index, node.dependents)

  const waves: number[][] = []
  while (inDeg.size > 0) {
    const wave: number[] = []
    for (const [idx, deg] of inDeg) {
      if (deg === 0) wave.push(idx)
    }
    if (wave.length === 0) break // graphe restant a un cycle (ne devrait pas)
    wave.sort()
    waves.push(wave)
    for (const idx of wave) {
      inDeg.delete(idx)
      for (const dep of dependents.get(idx) ?? []) {
        const v = inDeg.get(dep)
        if (v != null) inDeg.set(dep, v - 1)
      }
    }
  }
  return waves
}
