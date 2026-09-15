// ---------------------------------------------------------------------------
// coworkPlanParser — pure JSON parser for the Cowork planner. Extracted from
// coworkPlanner.ts so unit tests can import it without pulling in the
// LLM-driven planner (which requires browser/Tauri APIs).
// ---------------------------------------------------------------------------

import type { CoworkAction, CoworkPlan } from './coworkTypes.ts'

export type ParseResult =
  | { ok: true; plan: CoworkPlan }
  | { ok: false; error: string }

export function parsePlan(raw: string): ParseResult {
  if (!raw || !raw.trim()) return { ok: false, error: 'reponse vide' }
  const json = extractJsonObject(raw)
  if (!json) return { ok: false, error: 'aucun objet JSON detecte dans la reponse' }
  let parsed: unknown
  try {
    parsed = JSON.parse(json)
  } catch (e) {
    return { ok: false, error: `JSON.parse: ${(e as Error).message}` }
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { ok: false, error: 'racine n est pas un objet' }
  }
  const obj = parsed as Record<string, unknown>
  if (typeof obj.reasoning !== 'string') return { ok: false, error: 'reasoning manquant ou non-string' }
  if (typeof obj.expectedOutcome !== 'string') return { ok: false, error: 'expectedOutcome manquant ou non-string' }
  if (!Array.isArray(obj.actions) || obj.actions.length === 0) {
    return { ok: false, error: 'actions doit etre un tableau non vide' }
  }
  const actions: CoworkAction[] = []
  for (let i = 0; i < obj.actions.length; i++) {
    const item = obj.actions[i]
    const valid = validateAction(item)
    if (!valid.ok) return { ok: false, error: `actions[${i}] invalide: ${valid.error}` }
    actions.push(valid.action)
  }
  return {
    ok: true,
    plan: {
      reasoning: obj.reasoning,
      actions,
      expectedOutcome: obj.expectedOutcome,
    },
  }
}

export function extractJsonObject(raw: string): string | null {
  const trimmed = raw.trim()
  const fence = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i)
  if (fence) {
    const inside = fence[1].trim()
    if (inside.startsWith('{') && inside.endsWith('}')) return inside
  }
  const first = trimmed.indexOf('{')
  const last = trimmed.lastIndexOf('}')
  if (first !== -1 && last !== -1 && last > first) {
    return trimmed.slice(first, last + 1)
  }
  return null
}

export type ValidationResult =
  | { ok: true; action: CoworkAction }
  | { ok: false; error: string }

export function validateAction(item: unknown): ValidationResult {
  if (!item || typeof item !== 'object' || Array.isArray(item)) {
    return { ok: false, error: 'item n est pas un objet' }
  }
  const obj = item as Record<string, unknown>
  const kind = obj.kind
  if (typeof kind !== 'string') return { ok: false, error: 'kind manquant' }
  switch (kind) {
    case 'reply':
      return typeof obj.message === 'string'
        ? { ok: true, action: { kind: 'reply', message: obj.message } }
        : { ok: false, error: 'reply.message manquant' }

    case 'finish':
      return typeof obj.summary === 'string'
        ? { ok: true, action: { kind: 'finish', summary: obj.summary } }
        : { ok: false, error: 'finish.summary manquant' }

    case 'read_file':
      return typeof obj.path === 'string'
        ? { ok: true, action: { kind: 'read_file', path: obj.path } }
        : { ok: false, error: 'read_file.path manquant' }

    case 'list_dir':
      if (typeof obj.path !== 'string') return { ok: false, error: 'list_dir.path manquant' }
      return {
        ok: true,
        action: {
          kind: 'list_dir',
          path: obj.path,
          depth: typeof obj.depth === 'number' ? obj.depth : undefined,
        },
      }

    case 'write_file':
      if (typeof obj.path !== 'string') return { ok: false, error: 'write_file.path manquant' }
      if (typeof obj.content !== 'string') return { ok: false, error: 'write_file.content manquant' }
      return { ok: true, action: { kind: 'write_file', path: obj.path, content: obj.content } }

    case 'edit_file':
      if (typeof obj.path !== 'string') return { ok: false, error: 'edit_file.path manquant' }
      if (typeof obj.oldText !== 'string') return { ok: false, error: 'edit_file.oldText manquant' }
      if (typeof obj.newText !== 'string') return { ok: false, error: 'edit_file.newText manquant' }
      return {
        ok: true,
        action: { kind: 'edit_file', path: obj.path, oldText: obj.oldText, newText: obj.newText },
      }

    case 'delete_file':
      return typeof obj.path === 'string'
        ? { ok: true, action: { kind: 'delete_file', path: obj.path } }
        : { ok: false, error: 'delete_file.path manquant' }

    case 'shell': {
      if (typeof obj.command !== 'string') return { ok: false, error: 'shell.command manquant' }
      const args = Array.isArray(obj.args) ? obj.args.filter((a) => typeof a === 'string') as string[] : []
      return {
        ok: true,
        action: {
          kind: 'shell',
          command: obj.command,
          args,
          cwd: typeof obj.cwd === 'string' ? obj.cwd : undefined,
          timeoutMs: typeof obj.timeoutMs === 'number' ? obj.timeoutMs : undefined,
        },
      }
    }

    case 'web_search': {
      if (typeof obj.query !== 'string' || !obj.query.trim()) {
        return { ok: false, error: 'web_search.query manquant' }
      }
      const limit = typeof obj.limit === 'number' && Number.isFinite(obj.limit)
        ? Math.max(1, Math.min(10, Math.round(obj.limit)))
        : undefined
      return {
        ok: true,
        action: {
          kind: 'web_search',
          query: obj.query.trim(),
          limit,
        },
      }
    }

    case 'fetch': {
      if (typeof obj.url !== 'string') return { ok: false, error: 'fetch.url manquant' }
      const method = typeof obj.method === 'string' ? obj.method.toUpperCase() : undefined
      const allowedMethods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'] as const
      if (method && !allowedMethods.includes(method as (typeof allowedMethods)[number])) {
        return { ok: false, error: `fetch.method "${method}" non supportee` }
      }
      return {
        ok: true,
        action: {
          kind: 'fetch',
          url: obj.url,
          method: method as 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH' | undefined,
          headers: obj.headers && typeof obj.headers === 'object' && !Array.isArray(obj.headers)
            ? (obj.headers as Record<string, string>)
            : undefined,
          body: typeof obj.body === 'string' ? obj.body : undefined,
        },
      }
    }

    case 'open_url':
      return typeof obj.url === 'string'
        ? { ok: true, action: { kind: 'open_url', url: obj.url } }
        : { ok: false, error: 'open_url.url manquant' }

    case 'clipboard_read':
      return { ok: true, action: { kind: 'clipboard_read' } }

    case 'clipboard_write':
      return typeof obj.text === 'string'
        ? { ok: true, action: { kind: 'clipboard_write', text: obj.text } }
        : { ok: false, error: 'clipboard_write.text manquant' }

    case 'voice_speak':
      return typeof obj.text === 'string'
        ? { ok: true, action: { kind: 'voice_speak', text: obj.text } }
        : { ok: false, error: 'voice_speak.text manquant' }

    case 'dom_query':
      if (typeof obj.selector !== 'string') return { ok: false, error: 'dom_query.selector manquant' }
      return {
        ok: true,
        action: {
          kind: 'dom_query',
          selector: obj.selector,
          attribute: typeof obj.attribute === 'string' ? obj.attribute : undefined,
        },
      }

    case 'think':
      if (typeof obj.topic !== 'string') return { ok: false, error: 'think.topic manquant' }
      if (typeof obj.thought !== 'string') return { ok: false, error: 'think.thought manquant' }
      return { ok: true, action: { kind: 'think', topic: obj.topic, thought: obj.thought } }

    case 'think_long':
      if (typeof obj.topic !== 'string') return { ok: false, error: 'think_long.topic manquant' }
      if (typeof obj.prompt !== 'string') return { ok: false, error: 'think_long.prompt manquant' }
      return {
        ok: true,
        action: {
          kind: 'think_long',
          topic: obj.topic,
          prompt: obj.prompt,
          durationHintMs: typeof obj.durationHintMs === 'number' ? obj.durationHintMs : undefined,
        },
      }

    case 'remember_fact':
      if (typeof obj.fact !== 'string' || !obj.fact.trim()) {
        return { ok: false, error: 'remember_fact.fact manquant ou vide' }
      }
      return {
        ok: true,
        action: {
          kind: 'remember_fact',
          fact: obj.fact,
          tags: Array.isArray(obj.tags) ? obj.tags.filter((t) => typeof t === 'string') as string[] : undefined,
        },
      }

    case 'forget_fact':
      if (typeof obj.id !== 'string' && typeof obj.matching !== 'string') {
        return { ok: false, error: 'forget_fact requiert id OU matching' }
      }
      return {
        ok: true,
        action: {
          kind: 'forget_fact',
          id: typeof obj.id === 'string' ? obj.id : undefined,
          matching: typeof obj.matching === 'string' ? obj.matching : undefined,
        },
      }

    case 'vision_describe':
      if (typeof obj.imageDataUrl !== 'string') return { ok: false, error: 'vision_describe.imageDataUrl manquant' }
      return {
        ok: true,
        action: {
          kind: 'vision_describe',
          imageDataUrl: obj.imageDataUrl,
          question: typeof obj.question === 'string' ? obj.question : undefined,
        },
      }

    case 'connector':
      if (typeof obj.connector !== 'string') return { ok: false, error: 'connector.connector manquant' }
      if (typeof obj.action !== 'string') return { ok: false, error: 'connector.action manquant' }
      return {
        ok: true,
        action: {
          kind: 'connector',
          connector: obj.connector,
          action: obj.action,
          params: obj.params && typeof obj.params === 'object' && !Array.isArray(obj.params)
            ? (obj.params as Record<string, unknown>)
            : {},
        },
      }

    case 'browser': {
      const op = typeof obj.operation === 'string' ? obj.operation : ''
      // v82l7 — extract_structured added (comprehension-based extraction via
      // Ollama). The type union in coworkTypes.ts already declares it ; we
      // align the parser allowlist so plans containing it pass validation.
      const allowedOps = ['list_tabs', 'get_active_tab', 'read_dom', 'read_html', 'click', 'fill', 'eval', 'screenshot', 'navigate', 'analyze_page', 'extract_structured']
      if (!allowedOps.includes(op)) {
        return { ok: false, error: `browser.operation invalide: ${op}` }
      }
      return {
        ok: true,
        action: {
          kind: 'browser',
          operation: op as 'list_tabs' | 'get_active_tab' | 'read_dom' | 'read_html' | 'click' | 'fill' | 'eval' | 'screenshot' | 'navigate' | 'analyze_page' | 'extract_structured',
          payload: obj.payload && typeof obj.payload === 'object' && !Array.isArray(obj.payload)
            ? (obj.payload as Record<string, unknown>)
            : {},
          extId: typeof obj.extId === 'string' ? obj.extId : undefined,
        },
      }
    }

    default:
      return { ok: false, error: `kind inconnu: ${kind}` }
  }
}

// ---------------------------------------------------------------------------
// Auto-finish heuristic — if the LLM forgets to terminate the plan with a
// `finish` action, append one. Otherwise the orchestrator would call the
// planner again, which usually produces the same plan (because the LLM is
// stateless re. previous calls), wasting tokens and time.
// ---------------------------------------------------------------------------

export function ensureFinishAction(plan: CoworkPlan): CoworkPlan {
  if (plan.actions.length === 0) return plan
  const last = plan.actions[plan.actions.length - 1]
  if (last.kind === 'finish') return plan
  return {
    ...plan,
    actions: [
      ...plan.actions,
      { kind: 'finish', summary: plan.expectedOutcome || 'Plan termine.' },
    ],
  }
}

// Read-only kinds : actions that PRODUCE INFO without rendering an answer to
// the user. If a plan has only these + a finish (no reply), it means the LLM
// thinks the work is done after just reading — but the user still expects a
// SYNTHESIS. We strip the finish so the orchestrator re-plans with the read
// results in history, allowing the LLM to synthesise on iteration #2.
const READ_ONLY_KINDS = new Set<string>([
  'read_file', 'list_dir', 'browser', 'fetch', 'web_search', 'dom_query',
  'clipboard_read', 'think', 'think_long', 'vision_describe',
  // remember_fact and forget_fact mutate localStorage but the user wants
  // them to be a side step ; the synthesis pass should still happen, so we
  // classify them as read-only for the strip-finish heuristic.
  'remember_fact', 'forget_fact',
])

export function stripFinishIfReadOnlyPlan(plan: CoworkPlan): CoworkPlan {
  if (plan.actions.length < 2) return plan
  const last = plan.actions[plan.actions.length - 1]
  if (last.kind !== 'finish') return plan
  const before = plan.actions.slice(0, -1)
  // If the plan already has a reply, the LLM did synthesize → keep the finish.
  if (before.some((a) => a.kind === 'reply')) return plan
  // If every preceding action is read-only, the LLM forgot the synthesis pass.
  if (!before.every((a) => READ_ONLY_KINDS.has(a.kind))) return plan
  return { ...plan, actions: before }
}

// Combined post-processor : strip if read-only-no-reply, otherwise ensure finish.
export function postProcessPlan(plan: CoworkPlan): CoworkPlan {
  const stripped = stripFinishIfReadOnlyPlan(plan)
  if (stripped !== plan) return stripped     // keep without finish to force re-plan
  return ensureFinishAction(plan)            // otherwise normalise as usual
}

export function repairMetaOnlyReplyPlan(
  plan: CoworkPlan,
  ctx?: { userPrompt?: string },
): CoworkPlan {
  if (!isMetaOnlyReplyPlan(plan)) return plan
  const reply = plan.actions.find((action): action is CoworkAction & { kind: 'reply' } => action.kind === 'reply')
  const userPrompt = ctx?.userPrompt?.trim()
  const thought = [
    'Le plan proposait une meta-analyse au lieu d accomplir la mission.',
    reply?.message ? `Meta-analyse detectee: ${reply.message}` : '',
    userPrompt ? `Objectif utilisateur a traiter maintenant: ${userPrompt}` : '',
    'Prochain pas: choisir les outils utiles, rechercher/lire/creer/verifier, puis seulement finaliser avec une vraie reponse.',
  ].filter(Boolean).join('\n')
  return {
    reasoning: 'Meta-reponse finale bloquee et transformee en reflexion interne.',
    actions: [
      {
        kind: 'think',
        topic: 'Meta-analyse a convertir en action',
        thought,
      },
    ],
    expectedOutcome: 'Aurora continue la mission au lieu de repondre par une intention.',
  }
}

export function repairExtensionBlockedWebResearchPlan(
  plan: CoworkPlan,
  ctx?: { userPrompt?: string },
): CoworkPlan {
  if (!isExtensionBlockedWebResearchPlan(plan, ctx?.userPrompt)) return plan
  const prompt = ctx?.userPrompt?.trim() || 'recherche web publique'
  return {
    reasoning: 'Demande Aurora-Connect bloquee : conversion en recherche web native.',
    actions: [
      {
        kind: 'think',
        topic: 'fallback recherche web native',
        thought: 'Aurora-Connect sert a controler un onglet utilisateur. Pour une recherche internet publique, je bascule vers web_search puis fetch sans demander d extension.',
      },
      {
        kind: 'web_search',
        query: buildNativeWebSearchQuery(prompt),
        limit: 5,
      },
    ],
    expectedOutcome: 'Cowork obtient des resultats web publics sans exiger Aurora-Connect.',
  }
}

function isMetaOnlyReplyPlan(plan: CoworkPlan): boolean {
  const nonFinishActions = plan.actions.filter((action) => action.kind !== 'finish')
  if (nonFinishActions.length !== 1 || nonFinishActions[0].kind !== 'reply') return false
  const message = normalizeGuardText(nonFinishActions[0].message)
  if (message.length < 40) return false
  const talksAboutUser = /\b(l[' ]?utilisateur|utilisateur|user|demande utilisateur|la demande)\b/.test(message)
  const defersWork = /(il est necessaire|il faut|devrait|doit consulter|besoin de consulter|necessite de|correspond probablement|probablement|pour identifier|avant de repondre|je dois d abord)/.test(message)
  const researchDiagnosis = /(recherches? precedentes?.{0,80}(echoue|echou|formulation)|formulation peu precise|il faut cibler|cibler directement|ressources officielles|requete plus ciblee|recherche plus ciblee)/.test(message)
  const noConcreteOutcome = !/(c est fait|j ai cree|j ai lu|j ai verifie|voici le resultat|fichier cree|sources consultees|verification)/.test(message)
  return ((talksAboutUser && defersWork) || researchDiagnosis) && noConcreteOutcome
}

function isExtensionBlockedWebResearchPlan(plan: CoworkPlan, userPrompt?: string): boolean {
  const nonFinishActions = plan.actions.filter((action) => action.kind !== 'finish')
  if (nonFinishActions.length !== 1 || nonFinishActions[0].kind !== 'reply') return false
  const message = normalizeGuardText(nonFinishActions[0].message)
  const prompt = normalizeGuardText(userPrompt || '')
  const asksForExtension = /(aurora[- ]?connect|extension|installer|settings|recharger la page)/.test(message)
  const publicResearch = /(recherch|internet|web|en ligne|site|officiel|telecharg|fichier|banque|sujet|annale|bac|tp|sti2d|sin|document|pdf)/.test(prompt)
  return asksForExtension && publicResearch
}

function buildNativeWebSearchQuery(prompt: string): string {
  const compact = prompt
    .replace(/\s+/g, ' ')
    .replace(/[{}[\]"'`<>]/g, '')
    .trim()
  return compact.length > 180 ? compact.slice(0, 180) : compact
}

function normalizeGuardText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}

// ---------------------------------------------------------------------------
// v82ly — auto-inject extract_structured(mode=card_iteration) when the
// PRECEDING plan iteration already analyzed the page AND the analyze_page
// result reports a social_feed pageType with strong topological signals.
//
// Rationale : when the LLM planner sees "social_feed=true" in its history it
// SHOULD chain extract_structured(card_iteration), but LLMs forget. We close
// the loop deterministically — pure DOM signals → planner intent → bridge
// LLM extraction per-card. ZERO hardcoded selectors here ; we just propagate
// the topological hints (repeating_card_count, has_avatars, has_timestamps).
//
// The function is a noop when :
//   - history doesn't contain a recent analyze_page result
//   - that result doesn't expose pageType.social_feed=true
//   - the topological gate (repeating_card_count >= 5) isn't met
//   - the plan already contains an extract_structured(card_iteration) action
//     (the LLM remembered — don't double-emit)
//   - the plan ends with a `reply` already addressing the cards (synthesis pass)
//
// When it fires, it inserts the extract_structured action BEFORE any reply/
// finish in the current plan. This keeps the synthesis pass (Plan #2) intact
// while ensuring per-card extraction happens before the LLM tries to reply.
// ---------------------------------------------------------------------------

type AnalyzePageResultLike = {
  pageType?: {
    social_feed?: boolean
    listing?: boolean
    article?: boolean
    // v82n0 — article quality verdict (rich/thin/paywall/unknown).
    article_quality?: 'rich' | 'thin' | 'paywall' | 'unknown'
  } & Record<string, unknown>
  signals?: {
    listLikeCount?: number
    repeatingCardCount?: number
    avatarHits?: number
    hasTimestamps?: boolean
    reactionButtons?: number
    // v82n0 — listing subtype heuristic.
    listingSubtype?: 'search_results' | 'product_listing' | 'news_listing' | 'generic'
    articleQuality?: 'rich' | 'thin' | 'paywall' | 'unknown'
  } & Record<string, unknown>
  // v82lz — analyze_page emits `url: location.href`. We use it to surface
  // a connector hint when the page is a known social host. ZERO selectors
  // hardcoded — only hostname → connector-id mapping (UX hint, not adapter
  // wiring : the action stays a generic extract_structured(card_iteration)).
  url?: string
}

// v82lz — Pure host→connector mapping. Each entry is a `(hostname suffix,
// connector-id)` pair. Suffix-match : we test endsWith on the registered
// suffix so subdomains (m.facebook.com, www.linkedin.com) all resolve. The
// mapping deliberately keeps only hosts where a real connector entry exists
// in `coworkConnectors.ts` AND that the user is likely to scrape from a feed
// view (LinkedIn, Reddit, GitHub discussions, etc.). For social hosts that
// don't have a 1:1 connector match (Twitter/X, Mastodon, Bluesky, Threads),
// we map them to a generic 'extension_only' marker so the reasoning can say
// "no dedicated connector, use the topological scrape".
//
// Never selectors-based — only hostname lookups. This is metadata about the
// site identity, not its DOM.
const SOCIAL_HOST_TO_CONNECTOR: Array<{ suffix: string; connectorId: string | null; label: string }> = [
  { suffix: 'linkedin.com',     connectorId: null,        label: 'LinkedIn' },
  { suffix: 'twitter.com',      connectorId: null,        label: 'Twitter/X' },
  { suffix: 'x.com',            connectorId: null,        label: 'Twitter/X' },
  { suffix: 'reddit.com',       connectorId: 'reddit',    label: 'Reddit' },
  { suffix: 'github.com',       connectorId: 'github',    label: 'GitHub' },
  { suffix: 'mastodon.social',  connectorId: null,        label: 'Mastodon' },
  { suffix: 'bsky.app',         connectorId: null,        label: 'Bluesky' },
  { suffix: 'threads.net',      connectorId: null,        label: 'Threads' },
  { suffix: 'facebook.com',     connectorId: null,        label: 'Facebook' },
  { suffix: 'instagram.com',    connectorId: null,        label: 'Instagram' },
  { suffix: 'youtube.com',      connectorId: 'youtube',   label: 'YouTube' },
  { suffix: 'news.ycombinator.com', connectorId: 'hackernews', label: 'Hacker News' },
  { suffix: 'discord.com',      connectorId: 'discord',   label: 'Discord' },
  { suffix: 'slack.com',        connectorId: 'slack',     label: 'Slack' },
]

/**
 * Pure helper : extract the hostname from a URL string and look it up in
 * SOCIAL_HOST_TO_CONNECTOR. Returns the matching entry or null when the host
 * isn't a known social site. Defensive against malformed URLs (returns null
 * instead of throwing). Used by buildCardIterationAction to surface a
 * connector hint in the action payload without changing executor wiring.
 */
export function pickConnectorHintForHost(url: string | undefined | null): { connectorId: string | null; label: string } | null {
  if (!url || typeof url !== 'string') return null
  let host = ''
  try {
    host = new URL(url).hostname.toLowerCase()
  } catch {
    return null
  }
  if (!host) return null
  for (const entry of SOCIAL_HOST_TO_CONNECTOR) {
    if (host === entry.suffix || host.endsWith('.' + entry.suffix)) {
      return { connectorId: entry.connectorId, label: entry.label }
    }
  }
  return null
}

/**
 * Pure helper : compose a one-line reasoning hint to embed in the
 * extract_structured(card_iteration) payload. Three branches :
 *   - known social host with a dedicated connector → "opt-in to <id>" hint
 *   - known social host without a dedicated connector → "extension-only" hint
 *   - unknown / generic feed → "topological card_iteration" hint
 * The action stays the same shape ; only the payload.connector_hint string
 * carries the recommendation. Caller (executor / UI) is free to ignore it.
 */
export function buildConnectorHintReasoning(url: string | undefined | null): string {
  const picked = pickConnectorHintForHost(url)
  if (!picked) {
    return 'Detected social_feed page (generic) — using topological card_iteration extraction'
  }
  if (picked.connectorId) {
    return `Detected social_feed page on ${picked.label} — opt-in to ${picked.connectorId} connector for richer adapter, or fallback to topological scrape (current default)`
  }
  return `Detected social_feed page on ${picked.label} — no dedicated connector available, using topological card_iteration extraction (current default)`
}

/**
 * Scan the most recent action history for the latest analyze_page result.
 * Returns the analyze_page data shape (pageType+signals) when found, or null.
 * Pure : does not touch DOM, network, or any global state.
 */
export function findLatestAnalyzePageResult(
  history: ReadonlyArray<{ action: CoworkAction; result: { ok: boolean; data?: unknown } }>,
): AnalyzePageResultLike | null {
  for (let i = history.length - 1; i >= 0; i--) {
    const h = history[i]
    if (!h.result.ok) continue
    if (h.action.kind !== 'browser') continue
    if (h.action.operation !== 'analyze_page') continue
    const d = h.result.data
    if (d && typeof d === 'object') return d as AnalyzePageResultLike
  }
  return null
}

/**
 * Decide whether the plan should auto-emit a card_iteration extract_structured
 * follow-up based on the analyze_page topology in history.
 * Pure predicate : same input → same output, no side effects.
 */
export function shouldAutoEmitCardIteration(
  plan: CoworkPlan,
  history: ReadonlyArray<{ action: CoworkAction; result: { ok: boolean; data?: unknown } }>,
): boolean {
  const analyze = findLatestAnalyzePageResult(history)
  if (!analyze) return false
  if (!analyze.pageType?.social_feed) return false
  // Topological gate : a feed must have at least 5 repeating card-shaped
  // children. listLikeCount is the cross-source field name (background.js
  // analyze_page emits both `listLikeCount` and `repeatingCardCount`).
  const sig = analyze.signals || {}
  const cardCount = Number(sig.repeatingCardCount ?? sig.listLikeCount ?? 0)
  if (cardCount < 5) return false
  // Already chained ? Don't double-emit. We match on operation+mode so a plain
  // extract_structured (free intent) doesn't suppress the auto-injection.
  for (const a of plan.actions) {
    if (a.kind !== 'browser') continue
    if (a.operation !== 'extract_structured') continue
    const mode = (a.payload && typeof a.payload === 'object'
      ? (a.payload as Record<string, unknown>).mode
      : undefined)
    if (mode === 'card_iteration') return false
  }
  return true
}

/**
 * Build the synthetic extract_structured action with card_signals propagated
 * from the analyze_page snapshot. Pure factory.
 *
 * v82lz — embeds a `connector_hint` reasoning string in the payload when the
 * analyze_page url maps to a known social host. The string is purely UX :
 * it surfaces a recommendation about which connector adapter would be
 * richer than the topological scrape, without changing the action's
 * runtime behaviour. The action stays a generic
 * `browser.extract_structured(mode=card_iteration)` ; the hint is metadata
 * the UI / planner can surface to the user.
 */
export function buildCardIterationAction(
  analyze: AnalyzePageResultLike,
): CoworkAction {
  const sig = analyze.signals || {}
  const repeatingCount = Number(sig.repeatingCardCount ?? sig.listLikeCount ?? 0)
  const hasAvatars = Number(sig.avatarHits ?? 0) >= 2
  const hasTimestamps = Boolean(sig.hasTimestamps)
  const hasReactions = Number(sig.reactionButtons ?? 0) >= 2
  const connectorHint = buildConnectorHintReasoning(analyze.url)
  return {
    kind: 'browser',
    operation: 'extract_structured',
    payload: {
      intent: 'extract recent posts from this social feed',
      mode: 'card_iteration',
      card_signals: {
        repeating_card_count: repeatingCount,
        has_avatars: hasAvatars,
        has_timestamps: hasTimestamps,
        has_reactions: hasReactions,
      },
      connector_hint: connectorHint,
    },
  }
}

/**
 * Inject the card_iteration follow-up action into a plan when the predicate
 * fires. The action is inserted BEFORE the first reply/finish so the planner's
 * synthesis pass still runs after extraction.
 * Returns the plan unchanged when the predicate is false.
 *
 * v82n0 — also injects a listing-subtype card_iteration action when the
 * predicate `shouldAutoEmitListingIteration` fires (pageType.listing=true
 * and signals.listingSubtype is one of search_results/product_listing/
 * news_listing). The two predicates are mutually exclusive : social_feed
 * subsumes listing in the typology check, so a page hits at most one branch.
 */
export function injectCardIterationFollowUp(
  plan: CoworkPlan,
  history: ReadonlyArray<{ action: CoworkAction; result: { ok: boolean; data?: unknown } }>,
): CoworkPlan {
  if (shouldAutoEmitCardIteration(plan, history)) {
    const analyze = findLatestAnalyzePageResult(history)
    if (!analyze) return plan
    const action = buildCardIterationAction(analyze)
    const idx = plan.actions.findIndex((a) => a.kind === 'reply' || a.kind === 'finish')
    const newActions = idx === -1
      ? [...plan.actions, action]
      : [...plan.actions.slice(0, idx), action, ...plan.actions.slice(idx)]
    return { ...plan, actions: newActions }
  }
  if (shouldAutoEmitListingIteration(plan, history)) {
    const analyze = findLatestAnalyzePageResult(history)
    if (!analyze) return plan
    const action = buildListingIterationAction(analyze)
    const idx = plan.actions.findIndex((a) => a.kind === 'reply' || a.kind === 'finish')
    const newActions = idx === -1
      ? [...plan.actions, action]
      : [...plan.actions.slice(0, idx), action, ...plan.actions.slice(idx)]
    return { ...plan, actions: newActions }
  }
  return plan
}

// ---------------------------------------------------------------------------
// v82n0 — listing-subtype auto-emit.
//
// Sister of shouldAutoEmitCardIteration / buildCardIterationAction tuned for
// generic listings (search results, product listings, news listings). The
// detector reads pageType.listing + signals.listingSubtype emitted by
// analyze_page (background.js) AND content-scrape (snapshot path). When the
// subtype is a known rich category, we inject an extract_structured action
// with a subtype-aware intent so the LLM can structure its output (e.g.
// {name,price,rating} per product, {title,date,author,url} per news).
//
// The action stays a generic extract_structured(mode=card_iteration) — same
// bridge route as social_feed. The DIFFERENCE is the payload :
//   - intent : subtype-tailored phrase
//   - card_signals : carries listing_subtype so the bridge can shape the
//     LLM system prompt accordingly
//
// ZERO hardcoded selectors. Pure topology → planner intent.
// ---------------------------------------------------------------------------

const LISTING_SUBTYPE_INTENTS: Record<string, string> = {
  search_results: 'extract search results from this page (per result: title, snippet, url)',
  product_listing: 'extract products from this listing (per item: name, price, currency, rating if any, url)',
  news_listing: 'extract news items from this listing (per item: title, date, author, url, summary)',
  generic: 'extract repeating items from this listing',
}

/**
 * Pure predicate — does the latest analyze_page report pageType.listing=true
 * with a non-generic listingSubtype ? Returns false otherwise so the caller
 * skips the injection. Mutually exclusive with shouldAutoEmitCardIteration
 * (social_feed subsumes listing in the typology decision).
 */
export function shouldAutoEmitListingIteration(
  plan: CoworkPlan,
  history: ReadonlyArray<{ action: CoworkAction; result: { ok: boolean; data?: unknown } }>,
): boolean {
  const analyze = findLatestAnalyzePageResult(history)
  if (!analyze) return false
  // social_feed branch wins — it has its own injector.
  if (analyze.pageType?.social_feed) return false
  if (!analyze.pageType?.listing) return false
  const sig = analyze.signals || {}
  const subtype = String(sig.listingSubtype ?? 'generic')
  // Only fire on rich subtypes — generic doesn't add value over the LLM's
  // free extraction.
  if (subtype !== 'search_results' && subtype !== 'product_listing' && subtype !== 'news_listing') {
    return false
  }
  // Topological gate : need at least 5 repeating items.
  const cardCount = Number(sig.repeatingCardCount ?? sig.listLikeCount ?? 0)
  if (cardCount < 5) return false
  // Already chained ? Don't double-emit. Match on operation+mode AND
  // listing_subtype propagation.
  for (const a of plan.actions) {
    if (a.kind !== 'browser') continue
    if (a.operation !== 'extract_structured') continue
    const mode = (a.payload && typeof a.payload === 'object'
      ? (a.payload as Record<string, unknown>).mode
      : undefined)
    if (mode === 'card_iteration') return false
  }
  return true
}

/**
 * Pure factory — build the extract_structured action for a listing page.
 * Mirrors buildCardIterationAction but :
 *   - intent is subtype-aware (LISTING_SUBTYPE_INTENTS table)
 *   - card_signals carries listing_subtype so the bridge / LLM can shape
 *     its output schema per category.
 */
export function buildListingIterationAction(
  analyze: AnalyzePageResultLike,
): CoworkAction {
  const sig = analyze.signals || {}
  const subtype = (String(sig.listingSubtype ?? 'generic') as keyof typeof LISTING_SUBTYPE_INTENTS)
  const intent = LISTING_SUBTYPE_INTENTS[subtype] || LISTING_SUBTYPE_INTENTS.generic
  const repeatingCount = Number(sig.repeatingCardCount ?? sig.listLikeCount ?? 0)
  return {
    kind: 'browser',
    operation: 'extract_structured',
    payload: {
      intent,
      mode: 'card_iteration',
      card_signals: {
        repeating_card_count: repeatingCount,
        listing_subtype: subtype,
      },
    },
  }
}

// ---------------------------------------------------------------------------
// v82m1 — token-aware system-prompt nudge for under-extracted card iterations.
//
// When the most recent extract_structured(card_iteration) flagged
// `under_extraction:true` AND the prior analyze_page reported visual signals
// (avatars or reactions), inject a single-line educational hint into the
// system prompt so the planner can naturally pick the right retry strategy
// (browser.screenshot → extract_structured(includeImage:true)).
//
// Rules :
//   - PURE prompt nudge — no flow control, no auto-trigger, no executor wiring
//   - LLM is free to ignore the hint if its judgement says otherwise
//   - The hint string is emitted ONLY when the gate fires ; when off, the
//     function returns null and the caller appends nothing → ZERO token
//     overhead on the 99% no-under-extraction case
//   - Both signals must align : the under_extraction entry must come AFTER
//     a known-visual analyze_page (we look for the most recent analyze_page
//     in the history and check its signals)
// ---------------------------------------------------------------------------

/**
 * Pure predicate : decide whether the planner should append the visual-retry
 * nudge to its system prompt.
 *
 * Returns true when the most-recent under_extraction:true entry in history
 * is preceded by an analyze_page whose signals report has_avatars OR
 * has_reactions. Returns false otherwise (preserves zero-token-overhead
 * baseline for normal pages).
 */
export function shouldAppendVisualRetryNudge(
  history: ReadonlyArray<{ action: CoworkAction; result: { ok: boolean; data?: unknown }; under_extraction?: boolean }>,
): boolean {
  // Find most-recent under_extraction:true entry.
  let underExtractionIdx = -1
  for (let i = history.length - 1; i >= 0; i--) {
    if (history[i].under_extraction === true) {
      underExtractionIdx = i
      break
    }
  }
  if (underExtractionIdx < 0) return false
  // Find the analyze_page that PRECEDES that under_extraction entry. We scan
  // backward from underExtractionIdx-1 — analyze_page must exist before the
  // extract_structured ran so its signals are known to the planner.
  let analyze: AnalyzePageResultLike | null = null
  for (let i = underExtractionIdx - 1; i >= 0; i--) {
    const h = history[i]
    if (!h.result.ok) continue
    if (h.action.kind !== 'browser') continue
    if (h.action.operation !== 'analyze_page') continue
    const d = h.result.data
    if (d && typeof d === 'object') { analyze = d as AnalyzePageResultLike; break }
  }
  if (!analyze) return false
  const sig = analyze.signals || {}
  // Visual-signal gate : avatars hits OR reaction-button count signals a
  // media-heavy page where text scraping under-yields. We mirror the
  // booleans buildCardIterationAction emits (has_avatars/has_reactions
  // computed there from avatarHits>=2, reactionButtons>=2).
  const hasAvatars = Number(sig.avatarHits ?? 0) >= 2
  const hasReactions = Number(sig.reactionButtons ?? 0) >= 2
  return hasAvatars || hasReactions
}

// v82m4 — dual-signal escalation marker. Reused from coworkOrchestrator's
// `HOST_BASELINE_DRIFT_REASON` constant. We keep it duplicated here as a
// LOCAL constant so coworkPlanParser stays decoupled from coworkOrchestrator
// (no import cycle, parser is a leaf module). The value is identical and a
// unit test in coworkOrchestrator.test.ts already asserts equality with the
// orchestrator's exported constant — drift between the two is caught.
const HOST_BASELINE_DRIFT_REASON_PARSER = 'host_baseline_drift'

// v82m6 — tier-2 sparkline trend trip. Mirror the SPARKLINE_TREND_THRESHOLD_PP
// (=5pp) constant in coworkExtractionStats.ts so the parser stays a leaf
// module (no cycle with the network layer / store-driven module). The
// detector below operates on a `delta_history` annotation passed through
// the history entry by the orchestrator/pipeline ; we don't import the UI
// helper because the parser must be unit-testable without DOM/React.
const SPARKLINE_RED_THRESHOLD_PP_PARSER = 5.0

/**
 * v82m6 — pure detector : does the most-recent under_extraction:true entry
 * carry a `delta_history` array whose overall trajectory is RED (last - first
 * <= -5pp) ? Mirrors `sparklineToneForDeltaHistory` in coworkExtractionStats.
 *
 * Rationale : the existing yield-ratio + drift dual-signal fires on a SINGLE
 * extract entry (per-host blip vs baseline). The trend signal CONFIRMS the
 * blip is a sustained drift (not a one-off noise) by inspecting the host's
 * recent history of deltas. When both fire together, we emit the tier-2
 * `DUAL_SIGNAL_TREND` hint with the spread+pause escalation.
 *
 * Returns false when :
 *   - no under_extraction entry exists in history
 *   - the entry has no `delta_history` array (not annotated by the pipeline)
 *   - delta_history has < 2 finite numeric entries
 *   - last - first > -5pp (trajectory NOT confirmed red)
 */
export function didDeltaHistoryConfirmRedTrend(
  history: ReadonlyArray<{
    action: CoworkAction
    result: { ok: boolean; data?: unknown }
    under_extraction?: boolean
    delta_history?: number[]
  }>,
): boolean {
  if (!history || history.length === 0) return false
  let entry: { delta_history?: number[] } | null = null
  for (let i = history.length - 1; i >= 0; i--) {
    if (history[i].under_extraction === true) {
      entry = history[i]
      break
    }
  }
  if (!entry) return false
  const dh = entry.delta_history
  if (!dh || !Array.isArray(dh) || dh.length < 2) return false
  const cleaned: number[] = []
  for (const v of dh) {
    if (typeof v === 'number' && Number.isFinite(v)) cleaned.push(v)
  }
  if (cleaned.length < 2) return false
  const trend = cleaned[cleaned.length - 1] - cleaned[0]
  return trend <= -SPARKLINE_RED_THRESHOLD_PP_PARSER
}

/**
 * Pure detector : was the under_extraction flag triggered by the YIELD-RATIO
 * path (items < cards * 0.5 with cards >= 5) on the most-recent extract entry ?
 *
 * Returns false when :
 *   - no under_extraction entry exists in history
 *   - the under_extraction entry has no result.data shape we can inspect
 *   - cards_processed < 5 OR not finite
 *   - items not an array
 *   - items.length >= cards * 0.5 (yield healthy)
 *
 * Used by `buildVisualRetryNudge` to decide whether the yield-ratio path
 * fired — independent of the `reason` field. Both paths can fire together
 * (yield ratio AND host baseline drift) → dual-signal nudge.
 */
export function didUnderExtractionTripYieldRatio(
  history: ReadonlyArray<{ action: CoworkAction; result: { ok: boolean; data?: unknown }; under_extraction?: boolean }>,
): boolean {
  // Find most-recent under_extraction:true entry.
  let entry: { action: CoworkAction; result: { ok: boolean; data?: unknown }; under_extraction?: boolean } | null = null
  for (let i = history.length - 1; i >= 0; i--) {
    if (history[i].under_extraction === true) {
      entry = history[i]
      break
    }
  }
  if (!entry) return false
  const data = entry.result.data
  if (!data || typeof data !== 'object') return false
  const d = data as { cards_processed?: unknown; items?: unknown }
  const cards = typeof d.cards_processed === 'number' ? d.cards_processed : NaN
  if (!Number.isFinite(cards) || cards < 5) return false
  if (!Array.isArray(d.items)) return false
  return d.items.length < cards * 0.5
}

/**
 * Pure detector : was the under_extraction flag tagged with
 * `reason='host_baseline_drift'` ? Independent of the yield-ratio path —
 * both can fire on the same entry (dual-signal case) or only one (single).
 *
 * Returns false when no under_extraction entry exists OR its reason field
 * is absent / different. The marker mirrors the orchestrator's
 * `HOST_BASELINE_DRIFT_REASON` exported constant.
 */
export function didUnderExtractionTripHostBaselineDrift(
  history: ReadonlyArray<{ action: CoworkAction; result: { ok: boolean; data?: unknown }; under_extraction?: boolean; reason?: string }>,
): boolean {
  for (let i = history.length - 1; i >= 0; i--) {
    if (history[i].under_extraction === true) {
      return history[i].reason === HOST_BASELINE_DRIFT_REASON_PARSER
    }
  }
  return false
}

/**
 * Pure builder : compose the single-line system-prompt nudge string. Returns
 * null when the gate doesn't fire (caller appends nothing → no token overhead).
 *
 * The string is short (one line) and educational — the planner can ignore
 * it if its judgement points elsewhere. NO selectors, NO host-specific
 * logic ; pure topology + history coupling.
 *
 * v82m4 — dual-signal escalation. When BOTH paths fired (yield-ratio path
 * AND host_baseline_drift reason), we emit a STRONGER hint that mentions
 * `mode=spread` as an additional escalation option. Single-signal cases
 * keep the existing hint string verbatim — zero token-overhead change.
 *
 * Detection :
 *   - dual : `didUnderExtractionTripYieldRatio` && `reason === 'host_baseline_drift'`
 *   - single (yield only) : yield-ratio fires, reason is NOT host_baseline_drift
 *   - single (drift only) : reason is host_baseline_drift, yield-ratio false
 *
 * The visual-signal gate (`shouldAppendVisualRetryNudge`) still applies — we
 * never escalate without confirmed visual signals on the page (avatars or
 * reactions), so dual-signal on a non-visual page returns null like before.
 */
export function buildVisualRetryNudge(
  history: ReadonlyArray<{
    action: CoworkAction
    result: { ok: boolean; data?: unknown }
    under_extraction?: boolean
    reason?: string
    delta_history?: number[]
  }>,
): string | null {
  if (!shouldAppendVisualRetryNudge(history)) return null
  const yieldFired = didUnderExtractionTripYieldRatio(history)
  const driftFired = didUnderExtractionTripHostBaselineDrift(history)
  // v82m6 — tier-2 escalation. When the under_extraction entry's
  // delta_history trajectory is RED (sparkline tone red, last-first <= -5pp),
  // we emit the DUAL_SIGNAL_TREND hint suggesting `mode=spread` AND a 3-5s
  // pause. This distinguishes a sustained host degradation from a one-off
  // blip — the sparkline confirms the trajectory. Higher priority than the
  // existing dual-signal path so we check it FIRST.
  const trendConfirmed = didDeltaHistoryConfirmRedTrend(history)
  if (trendConfirmed) {
    return '[HINT] DUAL_SIGNAL_TREND — Persistent host degradation detected (sparkline trending down). Add `mode=spread` AND pause 3-5 seconds before next extract_structured to let the page settle. This is a sustained drift, not a one-off blip.'
  }
  if (yieldFired && driftFired) {
    // v82m4 — dual-signal stronger hint. Adds `mode=spread` to the suggested
    // escalation so the planner has an additional knob beyond the existing
    // screenshot+includeImage:true path. Single-line for prompt token economy.
    return '[HINT] DUAL_SIGNAL — under_extraction + host baseline drift detected. Next action SHOULD be `browser.screenshot` then `extract_structured` with `includeImage: true` AND consider `mode=spread`.'
  }
  return '[HINT] Last card_iteration was under_extraction (items < 50% of cards) on a page with visual signals. Next action SHOULD be `browser.screenshot` followed by `extract_structured` with `includeImage: true` to capture media-heavy posts.'
}

// ---------------------------------------------------------------------------
// v82m5 — pure detectors for the dual-signal escalation acceptance metric.
//
// These mirror the gate inside `buildVisualRetryNudge` so the orchestrator
// can decide :
//   1. "did the planner have the dual-signal nudge in its system prompt
//      this iteration ?" → `detectDualSignalNudgeContext(history)`
//   2. "did the next plan accept it ?" → `detectDualSignalAcceptanceInPlan(plan)`
//
// Pure : no React, no DOM, no fetch, no global state. The orchestrator
// invokes them ; the network reporter (`reportDualSignalEvent` in
// coworkExecutor.ts) is injected via the pipeline so tests can stub it.
// ---------------------------------------------------------------------------

// Marker re-exported from coworkOrchestrator's HOST_BASELINE_DRIFT_REASON.
// We keep the value local here to avoid a circular import (planParser must
// not depend on the orchestrator). Identity is enforced by a matching test.
const DUAL_SIGNAL_DRIFT_REASON_MARKER = 'host_baseline_drift'

type DualSignalHistoryEntry = {
  action: { kind: string; operation?: string; payload?: unknown }
  result: { ok: boolean; data?: unknown }
  under_extraction?: boolean
  reason?: string
}

/**
 * v82m5 — pure detector : does the most-recent under_extraction:true entry
 * in `history` carry BOTH the yield-ratio signal AND the host_baseline_drift
 * reason marker ? Mirrors the gate inside `buildVisualRetryNudge` so the
 * orchestrator can decide "did the planner have the dual-signal nudge in
 * its system prompt this iteration ?" without re-running the full
 * planner-prompt build.
 *
 * Returns false when :
 *   - no under_extraction entry exists in history
 *   - the entry doesn't have a parseable card_iteration data shape
 *   - cards_processed < 5 (yield-ratio path requires the same gate as the
 *     orchestrator's `annotateUnderExtraction`)
 *   - items.length >= cards_processed * 0.5 (yield-ratio path didn't fire)
 *   - reason !== 'host_baseline_drift' (drift path didn't fire)
 */
export function detectDualSignalNudgeContext(
  history: ReadonlyArray<DualSignalHistoryEntry>,
): boolean {
  if (!history || history.length === 0) return false
  let entry: DualSignalHistoryEntry | null = null
  for (let i = history.length - 1; i >= 0; i--) {
    if (history[i].under_extraction === true) {
      entry = history[i]
      break
    }
  }
  if (!entry) return false
  if (entry.reason !== DUAL_SIGNAL_DRIFT_REASON_MARKER) return false
  const data = entry.result.data
  if (!data || typeof data !== 'object') return false
  const d = data as { cards_processed?: unknown; items?: unknown }
  const cards = typeof d.cards_processed === 'number' ? d.cards_processed : NaN
  if (!Number.isFinite(cards) || cards < 5) return false
  if (!Array.isArray(d.items)) return false
  return d.items.length < cards * 0.5
}

/**
 * v82m5 — pure detector : does this plan contain the dual-signal acceptance
 * sequence — `browser.screenshot` followed (anywhere later in the actions
 * list) by `extract_structured` with `includeImage: true` in its payload ?
 *
 * The "followed by" gate is intentionally loose — the LLM may interleave a
 * `think` action between the screenshot and the extract, and that's still
 * an acceptance. We just need both actions to appear AND in that order.
 *
 * Returns false when :
 *   - plan.actions absent or empty
 *   - no browser.screenshot present
 *   - no extract_structured(includeImage:true) present
 *   - extract_structured comes BEFORE the screenshot (wrong order)
 */
export function detectDualSignalAcceptanceInPlan(plan: CoworkPlan | null | undefined): boolean {
  if (!plan || !Array.isArray(plan.actions) || plan.actions.length === 0) return false
  let screenshotIdx = -1
  for (let i = 0; i < plan.actions.length; i++) {
    const a = plan.actions[i]
    if (a.kind === 'browser' && (a as { operation?: string }).operation === 'screenshot') {
      screenshotIdx = i
      break
    }
  }
  if (screenshotIdx < 0) return false
  for (let i = screenshotIdx + 1; i < plan.actions.length; i++) {
    const a = plan.actions[i]
    if (a.kind !== 'browser') continue
    const op = (a as { operation?: string }).operation
    if (op !== 'extract_structured') continue
    const payload = (a as { payload?: unknown }).payload
    if (!payload || typeof payload !== 'object') continue
    const includeImage = (payload as { includeImage?: unknown }).includeImage
    if (includeImage === true) return true
  }
  return false
}

/**
 * v82m7 — pure detector : symmetric to `detectDualSignalAcceptanceInPlan`
 * but for the tier-2 DUAL_SIGNAL_TREND nudge. Looks for an
 * `extract_structured` action whose payload contains `mode: 'spread'`
 * AND a `think` (or `wait`) action sequenced BEFORE that extract — the
 * proxy for "pause 3-5 seconds" the trend nudge suggests.
 *
 * The "before" gate matches the loose ordering used elsewhere : the LLM
 * may interleave other actions, but the pause-action MUST come before
 * the spread-extract. If the order is wrong (extract first, then
 * think/wait) we count it as NOT accepted — the planner clearly missed
 * the "pause then extract" semantics.
 *
 * Returns false when :
 *   - plan.actions absent or empty
 *   - no extract_structured(mode=spread) present
 *   - no think (or future `wait`) present BEFORE that extract
 */
export function detectTrendAcceptanceInPlan(plan: CoworkPlan | null | undefined): boolean {
  if (!plan || !Array.isArray(plan.actions) || plan.actions.length === 0) return false
  // Find the FIRST extract_structured(mode=spread) — that's the action the
  // nudge asked for. We don't double-count later spread extracts.
  let spreadIdx = -1
  for (let i = 0; i < plan.actions.length; i++) {
    const a = plan.actions[i]
    if (a.kind !== 'browser') continue
    if ((a as { operation?: string }).operation !== 'extract_structured') continue
    const payload = (a as { payload?: unknown }).payload
    if (!payload || typeof payload !== 'object') continue
    const mode = (payload as { mode?: unknown }).mode
    if (mode === 'spread') {
      spreadIdx = i
      break
    }
  }
  if (spreadIdx < 0) return false
  // Look for a `think` action positioned BEFORE the spread extract. We
  // accept `think` (planner reasoning step) and `think_long` (longer
  // reflection) as the pause-proxy ; either signals "let the page settle"
  // semantics. A future `wait` action kind would be added here too.
  for (let i = 0; i < spreadIdx; i++) {
    const a = plan.actions[i]
    if (a.kind === 'think' || a.kind === 'think_long') return true
  }
  return false
}

/**
 * v82m7 — pure detector : did the most-recent under_extraction:true entry
 * in `history` have a `delta_history` array confirming a sustained red
 * trend (last - first <= -5pp) ? This mirrors the gate inside
 * `buildVisualRetryNudge` for the tier-2 TREND escalation. The
 * orchestrator uses it as the "did the planner have the TREND nudge in
 * its system prompt this iteration ?" predicate, symmetric with
 * `detectDualSignalNudgeContext` for tier-1.
 *
 * Returns false when no under_extraction entry exists, or when the entry
 * doesn't carry a `delta_history` array, or when the trajectory isn't
 * confirmed red. Identity to `didDeltaHistoryConfirmRedTrend` — exported
 * separately for symmetry / discoverability with the tier-1 detector.
 */
export function detectTrendNudgeContext(
  history: ReadonlyArray<{
    action: CoworkAction
    result: { ok: boolean; data?: unknown }
    under_extraction?: boolean
    delta_history?: number[]
  }>,
): boolean {
  return didDeltaHistoryConfirmRedTrend(history)
}

/**
 * v82m5 — pure helper : extract the host (lowercase, no leading "www.")
 * from the most-recent extract entry's payload URL. Returns "" when the
 * URL is missing or unparseable. The orchestrator passes this as the
 * `host` field of the dual-signal-event POST so the bridge can aggregate
 * by host top5.
 */
export function pickHostFromHistoryForDualSignal(
  history: ReadonlyArray<DualSignalHistoryEntry>,
): string {
  if (!history || history.length === 0) return ''
  for (let i = history.length - 1; i >= 0; i--) {
    const e = history[i]
    if (e.action.kind !== 'browser') continue
    if ((e.action as { operation?: string }).operation !== 'extract_structured') continue
    const payload = (e.action as { payload?: unknown }).payload
    if (!payload || typeof payload !== 'object') continue
    const rawUrl = (payload as { url?: unknown }).url
    if (typeof rawUrl !== 'string' || !rawUrl) continue
    try {
      const u = new URL(rawUrl)
      let h = (u.hostname || '').toLowerCase()
      if (h.startsWith('www.')) h = h.slice(4)
      return h
    } catch {
      return ''
    }
  }
  return ''
}

// ---------------------------------------------------------------------------
// v82m6 — pin propagation builder.
//
// Produces a single-line `[USER_PROMOTED]` hint when the user has pinned at
// least one connector. Returns "" otherwise → ZERO token overhead in the
// default case. Pure : no localStorage, no React, no DOM ; the caller
// (pipeline) reads `readPinnedConnectors()` and passes the ids through
// `PlannerContext.pinnedConnectorIds`.
//
// Cap on 8 ids matches `MAX_PINS` in coworkConnectorPin.ts so the hint
// always fits on a single line even when the user pinned the maximum.
// ---------------------------------------------------------------------------
export function buildPinnedConnectorsHint(
  pinnedConnectorIds: ReadonlyArray<string> | undefined,
): string {
  if (!pinnedConnectorIds || pinnedConnectorIds.length === 0) return ''
  // Defensive : trim whitespace, drop empties, dedupe (LRU order preserved
  // by the source store ; we just enforce our local invariants).
  const seen = new Set<string>()
  const cleaned: string[] = []
  for (const raw of pinnedConnectorIds) {
    if (typeof raw !== 'string') continue
    const id = raw.trim()
    if (!id) continue
    if (seen.has(id)) continue
    seen.add(id)
    cleaned.push(id)
  }
  if (cleaned.length === 0) return ''
  return `\n[USER_PROMOTED] User has pinned these connectors as preferred: ${cleaned.join(', ')}. When applicable, prefer their dedicated actions over generic open_url/extract_structured.`
}

// ---------------------------------------------------------------------------
// v82m6 — DUAL_SIGNAL_INEFFECTIVE fallback hint.
//
// Caller passes a list of hosts on which the bridge endpoint
// `dual-signal-effective` reported `effective:false` (>=5 emitted, 0
// accepted). When the most-recent extract entry's URL host matches one of
// those, we emit the DUAL_SIGNAL_INEFFECTIVE escalation suggesting a
// STRATEGY change (re-run analyze_page with a different focus_signal, or
// use a connector if available) instead of another screenshot retry.
//
// v82m8 — when BOTH tier-1 (DUAL_SIGNAL) AND tier-2 (DUAL_SIGNAL_TREND)
// have been ineffective on the host, we escalate to a TIER_3 nudge that
// recommends MANUAL review : check anti-bot, try opt-in connector, or
// involve the user. The LLM sees clearly "automatic escalation has been
// exhausted — STOP".
//
// Pure : no fetch, no localStorage. Empty / undefined → empty string →
// ZERO token overhead. Single-line to match the existing nudge contract.
// ---------------------------------------------------------------------------

// Pure helper — extract the most-recent extract_structured host (lowercase,
// no leading "www.") from a history slice. Returns "" when no extract entry
// has a parseable payload URL. Shared between buildIneffectiveHostHint and
// the tier-3 builder so the two stay in lock-step.
function _currentExtractHost(
  history: ReadonlyArray<{ action: CoworkAction; result: { ok: boolean; data?: unknown } }>,
): string {
  if (!history || history.length === 0) return ''
  for (let i = history.length - 1; i >= 0; i--) {
    const e = history[i]
    if (!e || !e.action) continue
    if (e.action.kind !== 'browser') continue
    const op = (e.action as { operation?: string }).operation
    if (op !== 'extract_structured') continue
    const payload = (e.action as { payload?: unknown }).payload
    if (!payload || typeof payload !== 'object') continue
    const u = (payload as { url?: unknown }).url
    if (typeof u !== 'string' || !u) continue
    try {
      const parsed = new URL(u)
      let h = (parsed.hostname || '').toLowerCase()
      if (h.startsWith('www.')) h = h.slice(4)
      return h
    } catch {
      continue
    }
  }
  return ''
}

// Pure helper — normalise a host list (lowercase, strip "www.", drop empties).
function _normaliseHostSet(hosts: ReadonlyArray<string> | undefined): Set<string> {
  const out = new Set<string>()
  if (!hosts) return out
  for (const raw of hosts) {
    if (typeof raw !== 'string') continue
    let h = raw.trim().toLowerCase()
    if (!h) continue
    if (h.startsWith('www.')) h = h.slice(4)
    out.add(h)
  }
  return out
}

export function buildIneffectiveHostHint(
  ineffectiveHosts: ReadonlyArray<string> | undefined,
  history: ReadonlyArray<{ action: CoworkAction; result: { ok: boolean; data?: unknown } }>,
  trendIneffectiveHosts?: ReadonlyArray<string> | undefined,
): string {
  if ((!ineffectiveHosts || ineffectiveHosts.length === 0) &&
      (!trendIneffectiveHosts || trendIneffectiveHosts.length === 0)) return ''
  const hostNorm = _currentExtractHost(history)
  if (!hostNorm) return ''
  const tier1Set = _normaliseHostSet(ineffectiveHosts)
  const tier2Set = _normaliseHostSet(trendIneffectiveHosts)
  const tier1 = tier1Set.has(hostNorm)
  const tier2 = tier2Set.has(hostNorm)
  // v82m8 — both tiers ineffective → tier-3 terminal escalation. The LLM
  // gets a single, unambiguous instruction to STOP automatic retries and
  // hand back to the human (or pivot to a connector if one exists).
  if (tier1 && tier2) {
    return `\n[HINT] TIER_3_NO_AUTO_ESCALATION — Both DUAL_SIGNAL and DUAL_SIGNAL_TREND escalations have failed on this host. STOP automatic escalation. Recommend manual review : (1) check if site has anti-bot detection, (2) try opt-in connector if available, (3) consider direct user assistance instead of auto-retry.`
  }
  if (tier1) {
    return `\n[HINT] DUAL_SIGNAL_INEFFECTIVE — Previous DUAL_SIGNAL escalations on this host did not change extraction quality. Try a different strategy: re-run analyze_page with a different focus_signal, or use connector if available, instead of repeating screenshot+includeImage.`
  }
  if (tier2) {
    // v82m8 — symmetric tier-2-only fallback. The trend nudge has been
    // accepted-but-zero-yield, so suggest the same kind of strategy pivot
    // we suggest for tier-1 — but tagged TREND so the LLM can disambiguate.
    return `\n[HINT] TREND_INEFFECTIVE — Previous DUAL_SIGNAL_TREND (mode=spread + pause) escalations on this host did not improve extraction. Consider a different strategy: re-run analyze_page with a different focus_signal, or use connector if available, instead of repeating spread+pause.`
  }
  return ''
}

// ---------------------------------------------------------------------------
// Loop detection — produces a stable signature of the plan's actions so the
// orchestrator can detect "the LLM is repeating itself" and bail out
// instead of burning the iteration budget.
// ---------------------------------------------------------------------------

export function planSignature(plan: CoworkPlan): string {
  return plan.actions.map((a) => actionSignature(a)).join('|')
}

function actionSignature(action: CoworkAction): string {
  switch (action.kind) {
    case 'reply':           return `reply:${hashString(action.message)}`
    case 'finish':          return `finish:${hashString(action.summary)}`
    case 'read_file':       return `read:${action.path}`
    case 'list_dir':        return `list:${action.path}`
    case 'write_file':      return `write:${action.path}:${hashString(action.content)}`
    case 'edit_file':       return `edit:${action.path}:${hashString(action.oldText)}:${hashString(action.newText)}`
    case 'delete_file':     return `delete:${action.path}`
    case 'shell':           return `shell:${action.command}:${(action.args ?? []).join(' ')}`
    case 'web_search':      return `web_search:${hashString(action.query)}:${action.limit ?? ''}`
    case 'fetch':           return `fetch:${action.method ?? 'GET'}:${action.url}`
    case 'open_url':        return `open:${action.url}`
    case 'clipboard_read':  return 'clip:read'
    case 'clipboard_write': return `clip:write:${hashString(action.text)}`
    case 'voice_speak':     return `tts:${hashString(action.text)}`
    case 'dom_query':       return `dom:${action.selector}:${action.attribute ?? ''}`
    case 'think':           return `think:${action.topic}:${hashString(action.thought)}`
    case 'think_long':      return `think_long:${action.topic}:${hashString(action.prompt)}`
    case 'remember_fact':   return `remember:${hashString(action.fact)}`
    case 'forget_fact':     return `forget:${action.id ?? action.matching ?? ''}`
    case 'vision_describe': return `vision:${hashString(action.imageDataUrl.slice(0, 200))}:${action.question ?? ''}`
    case 'screenshot_desktop': return `screenshot_desktop:${action.quality ?? 'fast'}:${action.display ?? 'primary'}`
    case 'connector':       return `conn:${action.connector}:${action.action}:${hashString(JSON.stringify(action.params ?? {}))}`
    case 'browser':         return `browser:${action.operation}:${hashString(JSON.stringify(action.payload ?? {}))}`
    case 'ephemeral_tool':  return `ephemeral_tool:${hashString(JSON.stringify(action))}`
    case 'file_bundle':     return `file_bundle:${hashString(JSON.stringify(action))}`
  }
}

function hashString(s: string): string {
  // Tiny non-crypto hash — enough to detect identical action payloads.
  let h = 5381
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h + s.charCodeAt(i)) | 0
  }
  return h.toString(36)
}
