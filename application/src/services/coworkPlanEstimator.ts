// Plan estimator — pre-flight pour l'orchestrateur Cowork.
//
// Demandé par le handoff "expert uplift" :
//   - confirmation user pour chaînes > 6 steps
//   - estimation de coût (tokens externes, durée) avant exécution
//   - persistence des plans favoris ("voici ma routine matinale")
//   - dry-run mode
//
// Module pur : zéro I/O, le caller persiste où il veut (localStorage, Tauri
// store, fichier). Le planner LLM passe le `CoworkPlan` ici avant exécution
// pour produire le panneau "voici ce que je vais faire et combien ça coûte".

import type { CoworkAction, CoworkPlan } from './coworkTypes.ts'

export type CostModel = {
  /** $/1M input tokens (planner LLM). */
  inputPricePerMillion: number
  /** $/1M output tokens (planner LLM). */
  outputPricePerMillion: number
  /** Estimated tokens consumed per orchestrator round-trip (planner+history). */
  tokensPerPlannerCycle: number
  /** Network egress $/GB (for fetch actions). */
  egressPricePerGb: number
}

/** Tarifs Anthropic API Opus 4.7 (1M context) — au cas où, sinon c'est local. */
export const DEFAULT_COST_MODEL: CostModel = {
  inputPricePerMillion: 15,
  outputPricePerMillion: 75,
  tokensPerPlannerCycle: 8000,
  egressPricePerGb: 0.09,
}

/** Coût local Ollama : 0$ token, mais on garde du temps machine pour info. */
export const LOCAL_OLLAMA_COST_MODEL: CostModel = {
  inputPricePerMillion: 0,
  outputPricePerMillion: 0,
  tokensPerPlannerCycle: 8000,
  egressPricePerGb: 0,
}

export type ActionCost = {
  /** Coût USD estimé (tokens + egress). */
  usd: number
  /** Durée prévue en ms. */
  durationMs: number
  /** Risque ∈ [0..1]. */
  riskScore: number
  /** Notes humaines pour le récap. */
  notes: string[]
}

export type PlanEstimate = {
  totalUsd: number
  totalDurationMs: number
  /** Risque agrégé (max des actions, pas la moyenne — on cap au pire). */
  worstRiskScore: number
  actionCount: number
  /** Actions par catégorie (read/write/network/shell/llm/other). */
  byCategory: Record<ActionCategory, number>
  /** Actions susceptibles d'échouer (>0.5). */
  riskyActions: Array<{ index: number; kind: string; risk: number; reason: string }>
  /** Le plan dépasse le seuil "confirm gate". */
  needsConfirmation: boolean
  /** Plan vide ou trivial. */
  trivial: boolean
}

export type ActionCategory = 'read' | 'write' | 'network' | 'shell' | 'llm' | 'voice' | 'memory' | 'other'

// --- Per-action cost / duration models ---------------------------------------
//
// Numbers calibrated by hand against real cowork runs. Tune in
// `application/python-services/cowork/*` if you change the executor.
const ACTION_COST: Record<string, (a: CoworkAction, cm: CostModel) => ActionCost> = {
  reply: (a, cm) => {
    const msg = (a as { message: string }).message
    const tokens = estimateTokens(msg)
    return {
      usd: (tokens / 1e6) * cm.outputPricePerMillion,
      durationMs: 50,
      riskScore: 0,
      notes: [`message ${tokens} tokens`],
    }
  },
  read_file: () => ({ usd: 0, durationMs: 30, riskScore: 0.05, notes: ['lecture locale'] }),
  list_dir: () => ({ usd: 0, durationMs: 40, riskScore: 0.05, notes: ['listing local'] }),
  write_file: (a) => ({
    usd: 0,
    durationMs: 80,
    riskScore: pathIsOutsideWorkspace((a as { path: string }).path) ? 0.85 : 0.4,
    notes: ['écriture disque', ((a as { content: string }).content?.length ?? 0) + ' octets'],
  }),
  edit_file: (a) => ({
    usd: 0,
    durationMs: 100,
    riskScore: pathIsOutsideWorkspace((a as { path: string }).path) ? 0.8 : 0.45,
    notes: ['edit ciblée'],
  }),
  delete_file: (a) => ({
    usd: 0,
    durationMs: 50,
    riskScore: pathIsOutsideWorkspace((a as { path: string }).path) ? 0.95 : 0.7,
    notes: ['suppression — destructif'],
  }),
  shell: (a) => {
    const cmd = (a as { command: string }).command
    const dangerous = /(?:rm\s+-rf|format|dd\s+if=|shutdown|reboot|del\s+\/[sf])/i.test(cmd)
    const timeoutMs = (a as { timeoutMs?: number }).timeoutMs ?? 30000
    return {
      usd: 0,
      durationMs: Math.min(timeoutMs, 5000),
      riskScore: dangerous ? 0.95 : 0.5,
      notes: dangerous ? ['commande dangereuse !'] : ['shell exec'],
    }
  },
  fetch: (a, cm) => {
    const url = (a as { url: string }).url
    const isLocal = /^(?:https?:\/\/)?(?:localhost|127\.|192\.168\.|10\.|172\.(?:1[6-9]|2\d|3[01])\.|0\.0\.0\.0)/.test(url)
    const sizeGb = 0.0001 // 100 KB par défaut
    return {
      usd: isLocal ? 0 : sizeGb * cm.egressPricePerGb,
      durationMs: isLocal ? 100 : 800,
      riskScore: isLocal ? 0.1 : 0.4,
      notes: [isLocal ? 'requête locale' : `fetch externe (${url.split('/')[2] ?? url})`],
    }
  },
  web_search: (a, cm) => {
    const query = (a as { query: string }).query
    return {
      usd: 0.0001 * cm.egressPricePerGb,
      durationMs: 900,
      riskScore: 0.2,
      notes: [`recherche web native (${query.slice(0, 48)})`],
    }
  },
  open_url: () => ({ usd: 0, durationMs: 200, riskScore: 0.2, notes: ['ouverture navigateur'] }),
  clipboard_read: () => ({ usd: 0, durationMs: 20, riskScore: 0.1, notes: ['lecture presse-papier'] }),
  clipboard_write: () => ({ usd: 0, durationMs: 20, riskScore: 0.2, notes: ['écriture presse-papier'] }),
  voice_speak: (a) => {
    const text = (a as { text: string }).text
    const durationMs = (text.length / 15) * 1000 // ~15 chars/s
    return { usd: 0, durationMs, riskScore: 0.05, notes: [`TTS ~${(durationMs / 1000).toFixed(1)}s`] }
  },
  dom_query: () => ({ usd: 0, durationMs: 50, riskScore: 0.05, notes: ['lecture DOM'] }),
  think: () => ({ usd: 0, durationMs: 30, riskScore: 0, notes: ['trace de raisonnement'] }),
  think_long: (a, cm) => {
    const prompt = (a as { prompt: string }).prompt
    const hint = (a as { durationHintMs?: number }).durationHintMs ?? 60_000
    const inTok = estimateTokens(prompt) + cm.tokensPerPlannerCycle
    const outTok = 1500
    return {
      usd: (inTok / 1e6) * cm.inputPricePerMillion + (outTok / 1e6) * cm.outputPricePerMillion,
      durationMs: hint,
      riskScore: 0.1,
      notes: [`mini-LLM ~${(hint / 1000).toFixed(0)}s, ~${inTok}↑/${outTok}↓ tokens`],
    }
  },
  remember_fact: () => ({ usd: 0, durationMs: 10, riskScore: 0.05, notes: ['mémoire +1'] }),
  forget_fact: () => ({ usd: 0, durationMs: 10, riskScore: 0.05, notes: ['mémoire -1'] }),
  vision_describe: (_a, cm) => ({
    usd: (2000 / 1e6) * cm.inputPricePerMillion + (500 / 1e6) * cm.outputPricePerMillion,
    durationMs: 3000,
    riskScore: 0.1,
    notes: ['analyse image qwen3-vl'],
  }),
  browser: (a) => {
    const op = (a as { operation: string }).operation
    const destructive = op === 'click' || op === 'fill' || op === 'eval' || op === 'navigate'
    return {
      usd: 0,
      durationMs: op === 'screenshot' || op === 'analyze_page' ? 1200 : 400,
      riskScore: destructive ? 0.35 : 0.1,
      notes: [`browser.${op}`],
    }
  },
  finish: () => ({ usd: 0, durationMs: 10, riskScore: 0, notes: ['fin de plan'] }),
  connector_action: (a, cm) => {
    const connectorId = (a as { id?: string }).id ?? 'unknown'
    return {
      usd: (500 / 1e6) * cm.outputPricePerMillion,
      durationMs: 1500,
      riskScore: 0.3,
      notes: [`connecteur ${connectorId}`],
    }
  },
}

function pathIsOutsideWorkspace(path: string): boolean {
  if (!path) return true
  const normalized = path.replace(/\\/g, '/').toLowerCase()
  if (normalized.includes('..')) return true
  if (normalized.startsWith('/')) {
    // Absolute unix path : si pas sous le cwd (heuristique), considérer dehors.
    return !normalized.startsWith('/users/juan/desktop/ia/auroraia-v2')
  }
  if (/^[a-z]:\//.test(normalized)) {
    return !normalized.startsWith('c:/users/juan/desktop/ia/auroraia-v2')
  }
  return false
}

function estimateTokens(text: string): number {
  if (!text) return 0
  // Approximation rough — ~4 chars/token pour FR/EN.
  return Math.ceil(text.length / 4)
}

function categoryOf(action: CoworkAction): ActionCategory {
  switch (action.kind) {
    case 'read_file':
    case 'list_dir':
    case 'dom_query':
      return 'read'
    case 'write_file':
    case 'edit_file':
    case 'delete_file':
      return 'write'
    case 'fetch':
    case 'web_search':
    case 'open_url':
    case 'browser':
      return 'network'
    case 'shell':
      return 'shell'
    case 'think':
    case 'think_long':
    case 'vision_describe':
      return 'llm'
    case 'voice_speak':
      return 'voice'
    case 'remember_fact':
    case 'forget_fact':
      return 'memory'
    default:
      return 'other'
  }
}

/** Estimate one action — exposed for the UI to show inline cost badges. */
export function estimateAction(action: CoworkAction, model: CostModel = DEFAULT_COST_MODEL): ActionCost {
  const fn = ACTION_COST[action.kind] ?? ((): ActionCost => ({ usd: 0, durationMs: 50, riskScore: 0.2, notes: ['inconnu'] }))
  return fn(action, model)
}

export type EstimatePlanOptions = {
  /** Cost model to use (defaults to Anthropic API tarifs). */
  costModel?: CostModel
  /** Trigger user confirmation when actions ≥ this count. Default 6. */
  confirmThreshold?: number
  /** Risk fraction that also triggers confirmation. */
  riskConfirmThreshold?: number
}

export function estimatePlan(plan: CoworkPlan, opts: EstimatePlanOptions = {}): PlanEstimate {
  const model = opts.costModel ?? DEFAULT_COST_MODEL
  const threshold = opts.confirmThreshold ?? 6
  const riskThreshold = opts.riskConfirmThreshold ?? 0.7

  let totalUsd = 0
  let totalDurationMs = 0
  let worstRisk = 0
  const byCategory: Record<ActionCategory, number> = {
    read: 0, write: 0, network: 0, shell: 0, llm: 0, voice: 0, memory: 0, other: 0,
  }
  const risky: Array<{ index: number; kind: string; risk: number; reason: string }> = []

  plan.actions.forEach((action, index) => {
    const cost = estimateAction(action, model)
    totalUsd += cost.usd
    totalDurationMs += cost.durationMs
    if (cost.riskScore > worstRisk) worstRisk = cost.riskScore
    byCategory[categoryOf(action)] += 1
    if (cost.riskScore >= 0.5) {
      risky.push({ index, kind: action.kind, risk: cost.riskScore, reason: cost.notes.join(' / ') })
    }
  })

  // Account for the planner round-trip itself (token cost in/out).
  const plannerInUsd = (model.tokensPerPlannerCycle / 1e6) * model.inputPricePerMillion
  const plannerOutUsd = (1500 / 1e6) * model.outputPricePerMillion
  totalUsd += plannerInUsd + plannerOutUsd

  return {
    totalUsd,
    totalDurationMs,
    worstRiskScore: worstRisk,
    actionCount: plan.actions.length,
    byCategory,
    riskyActions: risky,
    needsConfirmation: plan.actions.length >= threshold || worstRisk >= riskThreshold,
    trivial: plan.actions.length <= 1 && worstRisk < 0.3,
  }
}

// --- Plan favorites store ---------------------------------------------------
//
// Pure structure : la persistance est à la charge du caller (localStorage côté
// web, Tauri store côté desktop). Permet à Juan d'enregistrer "ma routine
// matinale", "build + push + deploy", etc.
export type SavedPlan = {
  id: string
  name: string
  description: string
  createdAt: string
  /** Tags pour la recherche. */
  tags: string[]
  /** Le plan source — peut être ré-exécuté tel quel. */
  plan: CoworkPlan
  /** Compteur d'utilisations. */
  runCount: number
  /** Dernière utilisation. */
  lastRunAt: string | null
  /** Estimation cachée — re-calculer si le costModel change. */
  estimateSnapshot?: PlanEstimate
}

export type SavedPlanIndex = {
  version: number
  plans: SavedPlan[]
}

export const SAVED_PLAN_VERSION = 1

export function createSavedPlanIndex(): SavedPlanIndex {
  return { version: SAVED_PLAN_VERSION, plans: [] }
}

export function addSavedPlan(index: SavedPlanIndex, draft: Omit<SavedPlan, 'id' | 'createdAt' | 'runCount' | 'lastRunAt'>): SavedPlanIndex {
  const id = `plan_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
  const saved: SavedPlan = {
    ...draft,
    id,
    createdAt: new Date().toISOString(),
    runCount: 0,
    lastRunAt: null,
  }
  return { ...index, plans: [...index.plans, saved] }
}

export function removeSavedPlan(index: SavedPlanIndex, id: string): SavedPlanIndex {
  return { ...index, plans: index.plans.filter((p) => p.id !== id) }
}

export function bumpSavedPlanUsage(index: SavedPlanIndex, id: string): SavedPlanIndex {
  return {
    ...index,
    plans: index.plans.map((p) => p.id === id ? { ...p, runCount: p.runCount + 1, lastRunAt: new Date().toISOString() } : p),
  }
}

export function searchSavedPlans(index: SavedPlanIndex, query: string): SavedPlan[] {
  const q = query.trim().toLowerCase()
  if (!q) return index.plans
  return index.plans.filter((p) =>
    p.name.toLowerCase().includes(q)
    || p.description.toLowerCase().includes(q)
    || p.tags.some((tag) => tag.toLowerCase().includes(q)))
}

// --- Dry-run helper ---------------------------------------------------------
//
// Convert a plan to a "what would have happened" trace without running it.
// Each entry says what the action would have done, its cost and risk, in a
// format the UI can render as a checklist before the user clicks "Lancer".
export type DryRunStep = {
  index: number
  kind: CoworkAction['kind']
  summary: string
  cost: ActionCost
  category: ActionCategory
}

export function dryRunPlan(plan: CoworkPlan, model: CostModel = DEFAULT_COST_MODEL): DryRunStep[] {
  return plan.actions.map((action, index) => ({
    index,
    kind: action.kind,
    summary: summarizeAction(action),
    cost: estimateAction(action, model),
    category: categoryOf(action),
  }))
}

function summarizeAction(action: CoworkAction): string {
  switch (action.kind) {
    case 'reply':
      return `Aurora répond : "${action.message.slice(0, 80)}${action.message.length > 80 ? '…' : ''}"`
    case 'read_file': return `Lire ${action.path}`
    case 'list_dir': return `Lister ${action.path}${action.depth ? ` (profondeur ${action.depth})` : ''}`
    case 'write_file': return `Écrire ${action.path} (${action.content.length} octets)`
    case 'edit_file': return `Éditer ${action.path}`
    case 'delete_file': return `Supprimer ${action.path}`
    case 'shell': return `Shell : ${action.command} ${action.args.slice(0, 2).join(' ')}${action.args.length > 2 ? ' …' : ''}`
    case 'web_search': return `Recherche web : ${action.query}`
    case 'fetch': return `${action.method ?? 'GET'} ${action.url}`
    case 'open_url': return `Ouvrir ${action.url}`
    case 'clipboard_read': return 'Lire le presse-papier'
    case 'clipboard_write': return `Copier "${action.text.slice(0, 40)}"`
    case 'voice_speak': return `Parler "${action.text.slice(0, 40)}"`
    case 'dom_query': return `DOM ${action.selector}`
    case 'think': return `Penser à : ${action.topic}`
    case 'think_long': return `Long think : ${action.topic}`
    case 'remember_fact': return `Retenir : ${action.fact}`
    case 'forget_fact': return `Oublier ${action.id ?? action.matching ?? '?'}`
    case 'vision_describe': return `Analyse visuelle qwen3-vl`
    case 'browser': return `Browser ${action.operation}${action.extId ? ` [${action.extId}]` : ''}`
    case 'finish': return `Terminer : ${action.summary.slice(0, 60)}`
    default: return (action as { kind: string }).kind
  }
}
