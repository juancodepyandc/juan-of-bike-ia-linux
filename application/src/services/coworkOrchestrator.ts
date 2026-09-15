// ---------------------------------------------------------------------------
// coworkOrchestrator — pure orchestration loop. Zero browser/Tauri imports
// so it is fully unit-testable under Node with mocked deps.
//
// The production wrapper (coworkPipeline.runCoworkPrompt) injects the real
// planner / executor / confirmation handler; tests can pass canned mocks
// to assert behavior end-to-end.
// ---------------------------------------------------------------------------

// Use .ts extensions so Node ESM can resolve under --experimental-strip-types
// without --experimental-specifier-resolution. Vite tolerates both.
import {
  planSignature,
  stripFinishIfReadOnlyPlan,
  detectDualSignalNudgeContext,
  detectDualSignalAcceptanceInPlan,
  detectTrendNudgeContext,
  detectTrendAcceptanceInPlan,
  pickHostFromHistoryForDualSignal,
} from './coworkPlanParser.ts'
import { SAFETY_LIMITS, validateAction, approveExternalPath } from './coworkSafety.ts'
import { estimatePlan, LOCAL_OLLAMA_COST_MODEL } from './coworkPlanEstimator.ts'
import { auditActionSequence, planRequiresHumanReview } from './coworkActionSequenceAuditor.ts'
import type {
  CoworkAction,
  CoworkActionEvent,
  CoworkActionResult,
  CoworkCapability,
  CoworkConfirmation,
  CoworkPlan,
  CoworkRuntime,
} from './coworkTypes.ts'
import type { ModuleId } from '../types/app.ts'

// ---------------------------------------------------------------------------
// Plan/execute/confirm signatures the orchestrator expects.
// ---------------------------------------------------------------------------

// History entry — `under_extraction` is set by the orchestrator AFTER an
// `extract_structured(mode=card_iteration)` action whose
// `result.data.items.length < cards_processed * 0.5`. It surfaces a
// quality-of-extraction signal to the planner so the next iteration can
// decide to retry with includeImage:true (vision pass) without us
// auto-retrying. Absent on every other entry kind.
//
// v82m3 — `reason` carries an opaque marker describing WHY the
// `under_extraction` flag was set. Two known markers today :
//   - undefined / absent : flag set by yield ratio (items < cards*0.5)
//   - 'host_baseline_drift' : flag set by header-driven escalation when
//     the bridge's `X-Host-Yield-Delta-Pct` response header reports a
//     yield drop >= 15.0pp vs the host's own prior baseline
// The visualRetryNudge gate fires on either path (it only checks
// `under_extraction:true`), so the planner naturally escalates without
// having to inspect `reason`. The field is purely diagnostic — surfaces
// in audit logs and telemetry without changing planner behavior.
export type CoworkHistoryEntry = {
  action: CoworkAction
  result: CoworkActionResult
  under_extraction?: boolean
  reason?: string
}

export type PlannerFn = (ctx: {
  userPrompt: string
  runtime: CoworkRuntime
  capabilities: CoworkCapability[]
  workspaceRoot: string
  history: CoworkHistoryEntry[]
  signal?: AbortSignal
  module?: ModuleId
  voiceMode?: boolean
}) => Promise<CoworkPlan>

export type ExecuteFn = (
  action: CoworkAction,
  runtime: CoworkRuntime,
  workspaceRoot: string,
  signal?: AbortSignal,
) => Promise<CoworkActionResult>

export type ConfirmFn = (args: {
  action: CoworkAction
  reason: string
  destructive: boolean
}) => Promise<'approved' | 'skipped' | 'aborted'>

export type AuditFn = (entry: {
  action: CoworkAction
  decision: 'allow' | 'confirm' | 'block' | 'skipped' | 'aborted'
  result?: { ok: boolean; output?: string; error?: string; durationMs: number }
  reason?: string
  promptId?: string
  prompt?: string
}) => void

export type SettingsSnapshot = {
  trustMode: boolean
  dangerMode: boolean
  fullyUnlocked?: boolean
}

// v82m5 — optional dual-signal reporter. Pure observability — the production
// pipeline injects `reportDualSignalEvent` from coworkExecutor.ts (which
// POSTs to `/api/cowork/dual-signal-event`) so the orchestrator stays
// decoupled from the network layer. Tests pass a stub or omit entirely.
export type ReportDualSignalFn = (
  kind: 'emitted' | 'accepted',
  host: string,
) => Promise<void> | void

// v82m7 — symmetric reporter for the tier-2 DUAL_SIGNAL_TREND nudge. Same
// fire-and-forget contract as ReportDualSignalFn ; the production pipeline
// injects `reportTrendSignalEvent` from coworkExecutor.ts (POSTs to
// `/api/cowork/trend-signal-event`). Tests pass a stub or omit entirely.
export type ReportTrendSignalFn = (
  kind: 'emitted' | 'accepted',
  host: string,
) => Promise<void> | void

export type OrchestratorDeps = {
  plan: PlannerFn
  execute: ExecuteFn
  confirm: ConfirmFn
  audit?: AuditFn
  getSettings: () => SettingsSnapshot
  reportDualSignal?: ReportDualSignalFn
  reportTrendSignal?: ReportTrendSignalFn
}

export type OrchestratorOptions = {
  signal?: AbortSignal
  onEvent: (ev: CoworkActionEvent) => void
  module?: ModuleId
  voiceMode?: boolean
  promptId: string
}

// ---------------------------------------------------------------------------
// Public entry — runs the agentic loop with injected deps.
// ---------------------------------------------------------------------------

export async function orchestrateCoworkRun(
  prompt: string,
  runtime: CoworkRuntime,
  capabilities: CoworkCapability[],
  workspaceRoot: string,
  deps: OrchestratorDeps,
  opts: OrchestratorOptions,
): Promise<{ finished: boolean; iterations: number }> {
  const trimmed = prompt.trim()
  if (!trimmed) {
    emit(opts, { kind: 'warn', message: 'Demande vide.', at: Date.now() })
    return { finished: false, iterations: 0 }
  }

  const history: CoworkHistoryEntry[] = []
  emit(opts, { kind: 'info', message: 'Planification…', at: Date.now() })

  let iteration = 0
  let finished = false
  let lastPlanSig: string | null = null
  let duplicatePlanRecoveries = 0

  while (!finished && iteration < SAFETY_LIMITS.maxPlanIterations) {
    iteration += 1
    if (opts.signal?.aborted) {
      emit(opts, { kind: 'warn', message: 'Annule par l utilisateur.', at: Date.now() })
      return { finished, iterations: iteration }
    }

    let plan: CoworkPlan
    try {
      plan = await deps.plan({
        userPrompt: trimmed,
        runtime,
        capabilities,
        workspaceRoot,
        history,
        signal: opts.signal,
        module: opts.module,
        voiceMode: opts.voiceMode,
      })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      if (opts.signal?.aborted || /abort/i.test(msg)) {
        emit(opts, { kind: 'warn', message: 'Annule pendant la planification.', at: Date.now() })
        return { finished, iterations: iteration }
      }
      emit(opts, { kind: 'error', message: 'Echec planification', detail: msg, at: Date.now() })
      return { finished, iterations: iteration }
    }

    // Defense in depth : even if a planner forgot to apply the strip rule,
    // the orchestrator removes a trailing `finish` from a read-only-no-reply
    // plan so we ALWAYS get a synthesis pass. This is what the user sees as
    // "Plan #1 read -> Plan #2 reply". We do NOT auto-append a finish here
    // (that is the planner's job; auto-finishing prevents multi-iter chains).
    plan = stripFinishIfReadOnlyPlan(plan)

    // v82m5 — dual-signal escalation acceptance metric. Pure observability :
    // when the previous iteration's history contained the conditions that
    // triggered the `[HINT] DUAL_SIGNAL` nudge in the planner's system
    // prompt (yield-ratio AND host_baseline_drift both fired on the same
    // extract), we POST kind=emitted. Then if the resulting plan accepted
    // the stronger hint (browser.screenshot followed by extract_structured
    // with includeImage:true), we POST kind=accepted. Closes the loop on
    // hint efficacy without changing the plan loop's flow.
    //
    // Best-effort fire-and-forget (the reporter swallows network errors so
    // the plan loop never depends on telemetry succeeding).
    if (deps.reportDualSignal) {
      try {
        if (detectDualSignalNudgeContext(history)) {
          const host = pickHostFromHistoryForDualSignal(history)
          void Promise.resolve(deps.reportDualSignal('emitted', host)).catch(() => {})
          if (detectDualSignalAcceptanceInPlan(plan)) {
            void Promise.resolve(deps.reportDualSignal('accepted', host)).catch(() => {})
          }
        }
      } catch {
        // Pure observability — never break the loop on a reporter error.
      }
    }

    // v82m7 — tier-2 trend acceptance metric. Symmetric to dual-signal :
    // when the under_extraction entry's `delta_history` confirms a
    // sustained downward trajectory (last - first <= -5pp), the planner
    // sees the `[HINT] DUAL_SIGNAL_TREND` nudge in its system prompt and
    // we fire kind=emitted. If the resulting plan accepted the suggestion
    // (extract_structured(mode=spread) preceded by think/think_long as
    // the pause-proxy), we fire kind=accepted. Both reporters fire
    // independently — a TREND nudge can supersede DUAL_SIGNAL on the
    // same iteration, but each metric tracks its own acceptance rate.
    if (deps.reportTrendSignal) {
      try {
        if (detectTrendNudgeContext(history)) {
          const host = pickHostFromHistoryForDualSignal(history)
          void Promise.resolve(deps.reportTrendSignal('emitted', host)).catch(() => {})
          if (detectTrendAcceptanceInPlan(plan)) {
            void Promise.resolve(deps.reportTrendSignal('accepted', host)).catch(() => {})
          }
        }
      } catch {
        // Pure observability — never break the loop on a reporter error.
      }
    }

    const currentSig = planSignature(plan)
    if (currentSig === lastPlanSig) {
      if (hasRecoverableFailure(history) && duplicatePlanRecoveries < 2) {
        duplicatePlanRecoveries += 1
        const recoveryNote = `Plan repete (${currentSig.slice(0, 160)}). Choisis une strategie differente, un fallback plus simple, ou produis une synthese partielle avec les donnees deja collectees. Ne reexecute pas exactement les memes actions.`
        history.push({
          action: { kind: 'think', topic: 'anti-boucle recuperation', thought: recoveryNote },
          result: { ok: true, output: recoveryNote, durationMs: 0 },
        })
        emit(opts, {
          kind: 'warn',
          message: 'Plan identique detecte — je force une replannification alternative au lieu de relancer la meme action.',
          detail: recoveryNote,
          at: Date.now(),
        })
        continue
      }
      emit(opts, {
        kind: 'warn',
        message: 'Plan identique au precedent — boucle detectee, arret.',
        detail: `Signature: ${currentSig.slice(0, 200)}`,
        at: Date.now(),
      })
      return { finished, iterations: iteration }
    }
    duplicatePlanRecoveries = 0
    lastPlanSig = currentSig

    emit(opts, {
      kind: 'info',
      message: `Plan #${iteration} — ${plan.actions.length} action(s)`,
      detail: `${plan.reasoning}\n\nObjectif: ${plan.expectedOutcome}`,
      at: Date.now(),
    })

    // Pre-flight estimate — gives Juan a quick read on cost/duration/risk
    // before the actions actually fire. Uses local Ollama cost model (0$
    // tokens) since Aurora is offline-first; durations + risk still
    // computed normally. Pure observability — never blocks execution.
    try {
      const est = estimatePlan(plan, { costModel: LOCAL_OLLAMA_COST_MODEL })
      const secs = (est.totalDurationMs / 1000).toFixed(1)
      const riskPct = (est.worstRiskScore * 100).toFixed(0)
      const catSummary = Object.entries(est.byCategory)
        .filter(([, n]) => n > 0)
        .map(([k, n]) => `${k}×${n}`)
        .join(' · ')
      emit(opts, {
        kind: est.needsConfirmation ? 'warn' : 'info',
        message: `Estimation : ~${secs}s, risque max ${riskPct}%${est.needsConfirmation ? ' (confirmation recommandée)' : ''}`,
        detail: `${catSummary}${est.riskyActions.length > 0 ? ' • Actions risquées : ' + est.riskyActions.map((r) => `${r.kind}(${(r.risk * 100).toFixed(0)}%)`).join(', ') : ''}`,
        at: Date.now(),
      })
    } catch {
      // Pure observability — never break the loop on an estimator error.
    }

    try {
      const alerts = auditActionSequence(plan)
      if (alerts.length > 0) {
        const needsReview = planRequiresHumanReview(alerts)
        emit(opts, {
          kind: needsReview ? 'warn' : 'info',
          message: `Audit sequence : ${alerts.length} alerte(s) (${needsReview ? 'revue humaine recommandee' : 'surveillance'})`,
          detail: alerts
            .map((alert) => `${alert.severity.toUpperCase()} ${alert.pattern}: ${alert.message} -> ${alert.recommendation}`)
            .join('\n'),
          at: Date.now(),
        })
      }
    } catch {
      // Pure observability - never break execution on a sequence-audit error.
    }

    for (const action of plan.actions) {
      if (opts.signal?.aborted) {
        emit(opts, { kind: 'warn', message: 'Annule pendant l execution.', at: Date.now() })
        return { finished, iterations: iteration }
      }
      const stepOutcome = await executeStep(action, runtime, workspaceRoot, history, opts, deps)
      if (stepOutcome === 'aborted') return { finished: false, iterations: iteration }
      if (stepOutcome === 'replan') break
      if (stepOutcome === 'finished') {
        finished = true
        break
      }
    }
  }

  if (!finished) {
    emit(opts, {
      kind: 'warn',
      message: `Plafond d iterations atteint (${SAFETY_LIMITS.maxPlanIterations}). Aurora s arrete.`,
      at: Date.now(),
    })
  }

  emit(opts, {
    kind: finished ? 'success' : 'warn',
    message: finished
      ? `Termine — ${countOk(history)} action(s) reussie(s), ${countKo(history)} echouee(s).`
      : `Arret apres ${iteration} iteration(s) — ${countOk(history)} action(s) reussie(s).`,
    detail: buildSessionSummary(history),
    at: Date.now(),
  })

  return { finished, iterations: iteration }
}

// ---------------------------------------------------------------------------
// One step = validate -> [confirm] -> execute -> audit -> emit
// ---------------------------------------------------------------------------

type StepOutcome = 'continue' | 'finished' | 'aborted' | 'replan'

async function executeStep(
  action: CoworkAction,
  runtime: CoworkRuntime,
  workspaceRoot: string,
  history: CoworkHistoryEntry[],
  opts: OrchestratorOptions,
  deps: OrchestratorDeps,
): Promise<StepOutcome> {
  const settings = deps.getSettings()
  // v115 — Le planner emet souvent vision_describe avec un placeholder
  // "<dataUrl du screenshot precedent>". On le resout ici en cherchant la
  // derniere dataUrl reelle dans l historique (screenshot_desktop ou
  // browser.screenshot). Sans ca le safety bloque l action.
  const resolved = resolveDataUrlReferences(action, history)
  const verdict = validateAction(resolved, runtime, workspaceRoot, {
    trustMode: settings.trustMode,
    dangerMode: settings.dangerMode,
    fullyUnlocked: settings.fullyUnlocked,
  })

  if (verdict.decision === 'block') {
    emit(opts, {
      kind: 'error',
      message: `Action bloquee: ${verdict.reason}`,
      detail: stringifyAction(action),
      actionKind: action.kind,
      at: Date.now(),
    })
    deps.audit?.({ action, decision: 'block', reason: verdict.reason, promptId: opts.promptId })
    history.push({ action, result: { ok: false, error: verdict.reason, durationMs: 0 } })
    appendRecoveryDirective(history, action, verdict.reason, runtime)
    emit(opts, {
      kind: 'warn',
      message: 'Je replannifie avec une alternative au lieu de finaliser apres cette action bloquee.',
      detail: buildRecoveryThought(action, verdict.reason, runtime),
      actionKind: action.kind,
      at: Date.now(),
    })
    return 'replan'
  }

  if (verdict.decision === 'confirm') {
    // Auto-approve non-destructive confirmations so the agent runs
    // autonomously for benign actions. Only destructive confirms trigger
    // an explicit user popup via deps.confirm().
    if (!verdict.destructive) {
      emit(opts, { kind: 'info', message: `Auto-approval (non-destructif): ${describeAction(verdict.normalized)}`, at: Date.now() })
      deps.audit?.({ action: verdict.normalized, decision: 'confirm', reason: verdict.reason, promptId: opts.promptId })
      if ('path' in verdict.normalized && typeof verdict.normalized.path === 'string') {
        approveExternalPath(verdict.normalized.path)
      }
    } else {
      const approval = await deps.confirm({
        action: verdict.normalized,
        reason: verdict.reason,
        destructive: verdict.destructive,
      })
      if (approval === 'aborted') {
        emit(opts, { kind: 'warn', message: 'User a interrompu l execution.', at: Date.now() })
        deps.audit?.({ action, decision: 'aborted', reason: verdict.reason, promptId: opts.promptId })
        return 'aborted'
      }
      if (approval === 'skipped') {
        emit(opts, {
          kind: 'warn',
          message: `Saute: ${describeAction(action)}`,
          actionKind: action.kind,
          at: Date.now(),
        })
        deps.audit?.({ action, decision: 'skipped', reason: verdict.reason, promptId: opts.promptId })
        history.push({ action, result: { ok: false, error: 'skipped by user', durationMs: 0 } })
        appendRecoveryDirective(history, action, 'skipped by user', runtime)
        return 'replan'
      }
      if ('path' in verdict.normalized && typeof verdict.normalized.path === 'string') {
        approveExternalPath(verdict.normalized.path)
      }
    }
  }

  if (shouldWarnAcceptedRisk(verdict, settings)) {
    emit(opts, {
      kind: 'warn',
      message: `Avertissement risque accepte: ${describeAction(verdict.normalized)}`,
      detail: `Cowork va executer cette action car le profil actuel l'autorise. Raison: ${verdict.reason}\n${stringifyAction(verdict.normalized)}`,
      actionKind: verdict.normalized.kind,
      at: Date.now(),
    })
  }

  emit(opts, {
    kind: 'info',
    message: describeAction(verdict.normalized),
    detail: stringifyAction(verdict.normalized),
    actionKind: verdict.normalized.kind,
    at: Date.now(),
  })

  const result = await deps.execute(verdict.normalized, runtime, workspaceRoot, opts.signal)
  const entry: CoworkHistoryEntry = { action: verdict.normalized, result }
  // v82m0 — annotate under_extraction telemetry on a successful card_iteration
  // extract. Closes the per-card observability loop opened in pass 29 by
  // letting the planner SEE the under-extraction signal in its history
  // summary (so it can naturally decide to retry with includeImage:true on
  // the next iteration). No auto-retry — the flag is purely advisory.
  // Threshold : items.length < cards_processed * 0.5 with cards_processed >= 5.
  // Edge cases (cards_processed missing, items missing, items=null) leave
  // under_extraction unset (the planner only reacts when the flag is true).
  annotateUnderExtraction(entry)
  // v82m3 — header-driven escalation. When the bridge forwards an
  // X-Host-Yield-Delta-Pct <= -15.0 we flip `under_extraction:true` with
  // `reason='host_baseline_drift'`. The visualRetryNudge gate fires on
  // either path, so the planner naturally retries with vision next turn.
  // No-op when headers are absent / malformed / above threshold.
  annotateHostBaselineDrift(entry)
  history.push(entry)

  deps.audit?.({
    action: verdict.normalized,
    decision: verdict.decision === 'allow' ? 'allow' : 'confirm',
    reason: verdict.reason,
    result: { ok: result.ok, output: result.output?.slice(0, 1000), error: result.error?.slice(0, 1000), durationMs: result.durationMs },
    promptId: opts.promptId,
  })

  if (result.ok) {
    emit(opts, {
      kind: 'success',
      message: `${describeAction(verdict.normalized)} → OK (${result.durationMs}ms)`,
      detail: truncate(result.output ?? '', 800),
      actionKind: verdict.normalized.kind,
      at: Date.now(),
    })
  } else {
    emit(opts, {
      kind: 'error',
      message: `${describeAction(verdict.normalized)} → ECHEC`,
      detail: result.error,
      actionKind: verdict.normalized.kind,
      at: Date.now(),
    })
    if (shouldReplanAfterFailure(verdict.normalized)) {
      const reason = result.error || 'action failed'
      appendRecoveryDirective(history, verdict.normalized, reason, runtime)
      emit(opts, {
        kind: 'warn',
        message: 'Echec detecte - je change de strategie avant de continuer.',
        detail: buildRecoveryThought(verdict.normalized, reason, runtime),
        actionKind: verdict.normalized.kind,
        at: Date.now(),
      })
      return 'replan'
    }
  }

  if (verdict.normalized.kind === 'finish') {
    return 'finished'
  }
  // If the planner emitted a `reply` that really asks for missing details,
  // treat it as terminal so we do not keep asking follow-up questions. Keep
  // this narrow : final reports also contain bullets/colons and must still
  // continue to voice_speak/finish.
  if (verdict.normalized.kind === 'reply') {
    const msg = (verdict.normalized as any).message || ''
    const trimmed = String(msg).trim()
    const asksForMissingInfo = /Veuillez préciser|Veuillez preciser|Veuillez fournir|Veuillez indiquer|Merci de préciser|Merci de preciser|Peux-tu préciser|Peux tu preciser|J'ai besoin de|Il me manque|Pour rédiger|Pour rediger/i.test(trimmed)
    const hasQuestionShape = /\?\s*$/.test(trimmed)
      || /\n\s*[-•*]\s+/.test(trimmed)
      || /:\s*$/.test(trimmed)
    const looksLikePromptForInfo = asksForMissingInfo && hasQuestionShape
    if (looksLikePromptForInfo) return 'finished'
  }
  return 'continue'
}

// ---------------------------------------------------------------------------
// Helpers (pure)
// ---------------------------------------------------------------------------

function shouldReplanAfterFailure(action: CoworkAction): boolean {
  // Some actions are presentation-only. A failed TTS should not prevent a
  // useful text reply from finishing. For real observation/mutation/network
  // actions, a failure means the mission needs a new strategy before finish.
  return !['reply', 'finish', 'voice_speak', 'think'].includes(action.kind)
}

function shouldWarnAcceptedRisk(
  verdict: { decision: 'allow' | 'confirm' | 'block'; destructive: boolean; reason: string },
  settings: SettingsSnapshot,
): boolean {
  if (verdict.decision !== 'allow' || !verdict.destructive) return false
  if (settings.fullyUnlocked) return true
  if (!settings.trustMode) return false
  return /trust mode|zero garde fou|deverrouille|danger\+trust/i.test(verdict.reason)
}

function appendRecoveryDirective(
  history: CoworkHistoryEntry[],
  action: CoworkAction,
  reason: string,
  runtime: CoworkRuntime,
): void {
  const thought = buildRecoveryThought(action, reason, runtime)
  history.push({
    action: { kind: 'think', topic: 'recuperation apres echec', thought },
    result: {
      ok: true,
      output: thought,
      data: { actionKind: action.kind, reason },
      durationMs: 0,
    },
  })
}

function buildRecoveryThought(action: CoworkAction, reason: string, runtime: CoworkRuntime): string {
  const base = [
    `L action ${action.kind} a echoue: ${reason}.`,
    'Ne termine pas la mission sur cet echec.',
    'Relis l objectif utilisateur, conserve les donnees deja collectees, puis choisis une strategie differente.',
  ]
  switch (action.kind) {
    case 'browser':
      base.push('Si l erreur vient d Aurora-Connect et que la demande n est pas un onglet ouvert, bascule vers web_search/fetch/shell au lieu de demander l extension.')
      base.push('Si la demande porte vraiment sur l onglet ouvert, propose une configuration courte ou tente list_tabs/analyze_page selon le contexte.')
      break
    case 'web_search':
      base.push('Essaie une requete plus courte, plus officielle, ou fetch une URL connue si elle est deja dans l historique.')
      break
    case 'fetch':
      base.push('Essaie une autre URL des resultats, une recherche web plus ciblee, ou une synthese partielle en citant la page inaccessible.')
      break
    case 'shell':
      base.push(runtime === 'tauri-desktop'
        ? 'Essaie une commande equivalente disponible, une variante PowerShell/Node/Python, ou installe une dependance raisonnable puis verifie.'
        : 'Le shell est limite dans ce runtime: utilise fetch/browser/connector ou explique la limite exacte.')
      break
    case 'read_file':
    case 'list_dir':
      base.push('Verifie le chemin, liste le dossier parent, utilise un chemin utilisateur connu, ou demande une seule precision si le fichier est introuvable.')
      break
    case 'write_file':
    case 'edit_file':
    case 'delete_file':
      base.push('Verifie les droits et le chemin, essaie un fichier de secours dans le meme dossier, ou demande confirmation si la cible est externe/sensible.')
      break
    case 'connector':
      base.push('Si le connecteur manque de cle/config, utilise un fallback natif quand possible; sinon demande uniquement le secret ou le parametre introuvable.')
      break
    case 'screenshot_desktop':
    case 'vision_describe':
      base.push('Essaie une capture/browser screenshot alternative, une question vision plus precise, ou bascule vers shell/fichiers si l information n est pas visuelle.')
      break
    default:
      base.push('Choisis le meilleur outil restant dans le catalogue et verifie le resultat avant finish.')
  }
  return base.join(' ')
}

function emit(opts: OrchestratorOptions, ev: CoworkActionEvent) {
  try { opts.onEvent(ev) } catch { /* swallow listener errors */ }
}

function describeAction(action: CoworkAction): string {
  switch (action.kind) {
    case 'reply':           return 'Reponse Aurora'
    case 'finish':          return `Termine — ${action.summary.slice(0, 80)}`
    case 'read_file':       return `Lire ${action.path}`
    case 'list_dir':        return `Lister ${action.path}`
    case 'write_file':      return `Ecrire ${action.path}`
    case 'edit_file':       return `Modifier ${action.path}`
    case 'delete_file':     return `Supprimer ${action.path}`
    case 'shell':           return `Shell: ${action.command} ${(action.args ?? []).join(' ')}`.trim()
    case 'web_search':      return `Recherche web : ${action.query}`
    case 'fetch':           return `Fetch ${action.method ?? 'GET'} ${action.url}`
    case 'open_url':        return `Ouvrir ${action.url}`
    case 'clipboard_read':  return 'Lire presse-papiers'
    case 'clipboard_write': return 'Copier dans presse-papiers'
    case 'voice_speak':     return `Lire a voix haute (${action.text.length} caracteres)`
    case 'dom_query':       return `DOM ${action.selector}${action.attribute ? `[${action.attribute}]` : ''}`
    case 'think':           return `Reflexion : ${action.topic}`
    case 'think_long':      return `Reflexion longue : ${action.topic}`
    case 'remember_fact':   return `Memoriser : ${action.fact.slice(0, 60)}`
    case 'forget_fact':     return `Oublier : ${action.id ?? action.matching ?? '?'}`
    case 'vision_describe': return `Vision (qwen3-vl) : ${action.question?.slice(0, 60) ?? 'description image'}`
    case 'screenshot_desktop': return `Capture ecran systeme (Print Screen ${action.quality === 'hq' ? 'HQ' : 'fast'})`
    case 'connector':       return `Connecteur ${action.connector}.${action.action}`
    case 'browser':         return `Navigateur : ${action.operation}${action.payload?.selector ? ' ' + action.payload.selector : ''}`
    case 'ephemeral_tool':  return `Outil temporaire : ${action.toolName}`
    case 'file_bundle':     return `${action.files.length} fichier(s) pour ${action.moduleTarget}`
  }
}

function stringifyAction(action: CoworkAction): string {
  try { return JSON.stringify(action, null, 2) } catch { return String(action) }
}

// v115 — Resoudre les references dataUrl dans les actions du planner.
// Quand le LLM ecrit `imageDataUrl: "<dataUrl du screenshot precedent>"`,
// on cherche la derniere dataUrl reelle dans l historique et on la substitue
// pour eviter le block du safety. Pure (ne mute pas action si rien a faire).
function resolveDataUrlReferences(action: CoworkAction, history: CoworkHistoryEntry[]): CoworkAction {
  if (action.kind !== 'vision_describe') return action
  if (action.imageDataUrl?.startsWith('data:')) return action

  // Walk history backwards : derniere capture screenshot avec dataUrl
  for (let i = history.length - 1; i >= 0; i--) {
    const entry = history[i]
    if (!entry.result.ok || !entry.result.data) continue
    const data = entry.result.data as { dataUrl?: string }
    if (data.dataUrl && data.dataUrl.startsWith('data:')) {
      const isScreenshot = (entry.action.kind === 'screenshot_desktop')
        || (entry.action.kind === 'browser' && entry.action.operation === 'screenshot')
      if (isScreenshot) {
        return { ...action, imageDataUrl: data.dataUrl }
      }
    }
  }
  return action
}

function truncate(s: string, max: number): string {
  if (!s) return ''
  if (s.length <= max) return s
  return s.slice(0, max) + `\n…[tronque · ${s.length - max} octets]`
}

function countOk(history: CoworkHistoryEntry[]): number {
  return history.filter((h) => h.result.ok).length
}
function countKo(history: CoworkHistoryEntry[]): number {
  return history.filter((h) => !h.result.ok).length
}

function hasRecoverableFailure(history: CoworkHistoryEntry[]): boolean {
  return history.some((h) => (
    !h.result.ok
    && h.result.error !== 'skipped by user'
    && h.action.kind !== 'finish'
  ))
}

// v82m0 — under_extraction telemetry. Mutates the entry IN-PLACE when the
// action is a successful `extract_structured(mode=card_iteration)` whose
// returned item count fell below half the per-card pre-cut count surfaced
// by the bridge. Pure read of `result.data.cards_processed` and
// `result.data.items.length` ; no side effects beyond the entry mutation.
//
// Edge cases :
//   - action kind != browser, op != extract_structured, mode != card_iteration → noop
//   - !result.ok → noop (failure already surfaced as KO)
//   - cards_processed missing / non-finite / < 5 → noop (no quality signal)
//   - items missing / null / not an array → noop
//   - items.length >= cards_processed * 0.5 → noop (extraction is healthy)
//
// Exported for unit testing — the orchestrator unit tests assert the same
// matrix we describe here without spinning up the full executor.
export function annotateUnderExtraction(entry: CoworkHistoryEntry): void {
  const a = entry.action
  if (a.kind !== 'browser') return
  if (a.operation !== 'extract_structured') return
  const payload = (a.payload && typeof a.payload === 'object') ? a.payload as Record<string, unknown> : {}
  if (payload.mode !== 'card_iteration') return
  if (!entry.result.ok) return
  const data = entry.result.data
  if (!data || typeof data !== 'object') return
  const d = data as { cards_processed?: unknown; items?: unknown }
  const cardsProcessed = typeof d.cards_processed === 'number' ? d.cards_processed : NaN
  if (!Number.isFinite(cardsProcessed) || cardsProcessed < 5) return
  if (!Array.isArray(d.items)) return
  const itemsLen = d.items.length
  if (itemsLen >= cardsProcessed * 0.5) return
  entry.under_extraction = true
}

// v82m3 — host-baseline-drift telemetry. Mutates the entry IN-PLACE when the
// successful `extract_structured(mode=card_iteration)` response carried a
// `X-Host-Yield-Delta-Pct` header (forwarded by the bridge via
// `result.data.headers`) whose value is <= -15.0pp (a sharp drop vs the
// host's own moving baseline). Sets `under_extraction:true` and tags the
// `reason` with `host_baseline_drift` so the planner naturally fires the
// existing visual-retry nudge on the NEXT iteration WITHOUT us having to
// touch /api/cowork/extraction-stats. The header is self-contained, no
// extra round-trip needed.
//
// "Host knows itself" — the bridge already computed the per-host moving
// baseline (last N=10 yields) ; we just consume the result.
//
// Edge cases (graceful no-op for ALL of these — never throws) :
//   - action kind != browser, op != extract_structured, mode != card_iteration
//   - !result.ok
//   - data missing / not an object
//   - headers field absent
//   - X-Host-Yield-Delta-Pct header absent
//   - header value not a parseable signed float (NaN / Infinity / "abc")
//   - delta > -15.0 (healthy or only mild drift)
//
// Threshold is `delta < -15.0` (strict less-than). The agenda specifies
// `delta >= -15.0 → no flag`, i.e. only sharper-than-15-pp drops escalate.
// Header comes back as `-20.0` / `+5.0` formatted floats from the bridge.
//
// Exported for unit testing — the orchestrator tests assert this matrix
// without spinning up Flask.
export const HOST_BASELINE_DRIFT_THRESHOLD_PP = -15.0
export const HOST_BASELINE_DRIFT_REASON = 'host_baseline_drift'

export function annotateHostBaselineDrift(entry: CoworkHistoryEntry): void {
  try {
    const a = entry.action
    if (a.kind !== 'browser') return
    if (a.operation !== 'extract_structured') return
    const payload = (a.payload && typeof a.payload === 'object') ? a.payload as Record<string, unknown> : {}
    if (payload.mode !== 'card_iteration') return
    if (!entry.result.ok) return
    const data = entry.result.data
    if (!data || typeof data !== 'object') return
    const d = data as { headers?: unknown }
    const h = d.headers
    if (!h || typeof h !== 'object') return
    const headers = h as Record<string, unknown>
    // Header key matched case-insensitively : the bridge sends
    // 'X-Host-Yield-Delta-Pct' but a HTTP intermediary may lowercase it.
    let raw: unknown = headers['X-Host-Yield-Delta-Pct']
    if (raw === undefined) raw = headers['x-host-yield-delta-pct']
    if (raw === undefined) return
    const str = typeof raw === 'string' ? raw : String(raw)
    const parsed = Number.parseFloat(str)
    if (!Number.isFinite(parsed)) return
    if (parsed >= HOST_BASELINE_DRIFT_THRESHOLD_PP) return
    // Drift confirmed — flag for the planner. We DO NOT clobber a yield-
    // ratio-based reason if it's already set (yield ratio fires first in
    // executeStep), but we still flip `under_extraction` to true if the
    // yield path didn't trip it ; the visualRetryNudge gate only cares
    // about the boolean.
    entry.under_extraction = true
    if (!entry.reason) entry.reason = HOST_BASELINE_DRIFT_REASON
  } catch {
    // Defensive : a malformed header must NEVER break the orchestrator
    // run. The flag stays unset and the planner runs as if no drift
    // signal existed.
  }
}

function buildSessionSummary(
  history: CoworkHistoryEntry[],
): string {
  if (history.length === 0) return '(aucune action executee)'
  const lines = history.map((h, i) => {
    const tag = h.result.ok ? 'OK ' : 'KO '
    const dur = `${h.result.durationMs}ms`
    return `${(i + 1).toString().padStart(2, ' ')}. ${tag} ${describeAction(h.action)} (${dur})`
  })
  return lines.join('\n')
}

// Re-export so the production wrapper has a single import path.
export type { CoworkConfirmation }
