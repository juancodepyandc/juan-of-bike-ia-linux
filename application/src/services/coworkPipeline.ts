// ---------------------------------------------------------------------------
// coworkPipeline — production wrapper around the pure orchestrator.
//
// Detects runtime + capabilities, wires the real planner / executor /
// confirmation / audit / settings, and calls orchestrateCoworkRun. All the
// loop logic (validate → confirm → execute → audit → emit) lives in
// coworkOrchestrator.ts where it can be unit-tested with mocks.
// ---------------------------------------------------------------------------

import { useCoworkStore } from '../stores/coworkStore'
import { isTauriRuntime } from '../utils/runtime'
import { getWorkspacePath } from '../hooks/useTauri'
import { appendAuditEntry, makePromptId } from './coworkAudit'
import { readPinnedConnectors } from './coworkConnectorPin'
import { runAction, reportDualSignalEvent, reportTrendSignalEvent } from './coworkExecutor'
import { orchestrateCoworkRun } from './coworkOrchestrator'
import { planNextStep } from './coworkPlanner'
import {
  enrichPlannerContextWithBridgeSignals,
  _clearPlannerCtxCachesForTesting as _clearCacheForTestingImpl,
} from './coworkPlannerCtxEnricher'
import { loadSettings } from './coworkSettings'
import type {
  CoworkAction,
  CoworkActionEvent,
  CoworkCapability,
  CoworkPlan,
  CoworkRuntime,
} from './coworkTypes'
import type { CoworkProjectThread } from './coworkProjectThread.ts'
import type { ModuleId } from '../types/app'

// ---------------------------------------------------------------------------
// Re-exports for existing UI imports.
// ---------------------------------------------------------------------------

export type {
  CoworkAction,
  CoworkActionEvent,
  CoworkCapability,
  CoworkPlan,
  CoworkRuntime,
} from './coworkTypes'

// ---------------------------------------------------------------------------
// Runtime detection
// ---------------------------------------------------------------------------

export function detectCoworkRuntime(): CoworkRuntime {
  if (isTauriRuntime()) return 'tauri-desktop'
  if (typeof navigator !== 'undefined') {
    const ua = navigator.userAgent.toLowerCase()
    const isMobile = /iphone|ipad|ipod|android|windows phone|mobile/.test(ua)
    return isMobile ? 'web-mobile' : 'web-desktop'
  }
  return 'web-desktop'
}

export function getCoworkCapabilities(runtime: CoworkRuntime): CoworkCapability[] {
  return [
    {
      id: 'filesystem',
      label: 'Filesystem (lire/ecrire)',
      description: 'Lire et modifier les fichiers du workspace local.',
      enabled: runtime === 'tauri-desktop',
      destructive: true,
    },
    {
      id: 'shell',
      label: 'Commandes shell',
      description: 'Executer des commandes systeme (git, npm, python, etc.).',
      enabled: runtime === 'tauri-desktop',
      destructive: true,
    },
    {
      id: 'fetch',
      label: 'Appels reseau',
      description: 'Appeler des APIs publiques (REST, GraphQL).',
      enabled: runtime !== 'web-mobile',
      destructive: false,
    },
    {
      id: 'clipboard',
      label: 'Presse-papiers',
      description: 'Lire et ecrire dans le presse-papiers (avec permission).',
      enabled: runtime !== 'web-mobile',
      destructive: false,
    },
    {
      id: 'voice',
      label: 'Voix (dictee + TTS)',
      description: 'Capturer la voix au micro et lire les reponses.',
      enabled: true,
      destructive: false,
    },
    {
      id: 'dom',
      label: 'DOM (page courante)',
      description: 'Lire et modifier la page web courante.',
      enabled: runtime !== 'tauri-desktop',
      destructive: false,
    },
    {
      id: 'mobile-bridge',
      label: 'Pont mobile (Shortcuts/Tasker)',
      description: 'Declencher des actions iOS Shortcuts ou Android Tasker via webhook.',
      enabled: false,
      destructive: true,
    },
  ]
}

// v82m7 — re-export the cache-clearing helper so callers (tests, UI dev
// tooling) can import it from the pipeline module without knowing about
// the internal split between coworkPipeline and coworkPlannerCtxEnricher.
export const _clearPlannerCtxCachesForTesting = _clearCacheForTestingImpl

// ---------------------------------------------------------------------------
// Public entry point — production wiring
// ---------------------------------------------------------------------------

export type RunCoworkExtras = {
  module?: ModuleId
  voiceMode?: boolean
  // v21 — conversation continuity : the most recent N user/Aurora exchanges
  // (already in the chat overlay). Injected into the planner system prompt
  // so follow-up questions ("et la version mobile ?", "approfondis", etc.)
  // can resolve their references implicitly.
  conversationHistory?: Array<{ role: 'user' | 'aurora'; content: string }>
  // v29 — attached images : when user drags / pastes an image into the
  // composer, the overlay pre-runs vision_describe and passes the textual
  // descriptions here. The planner system prompt surfaces them so Aurora
  // has the visual context immediately, without re-running vision.
  // Cap to 3 descriptions per submit to keep the prompt compact.
  attachedImageDescriptions?: string[]
  // Project continuity: generated artifacts, active reference, versions and
  // previous multi-module steps extracted from the Cowork thread.
  projectThread?: CoworkProjectThread
}

export async function runCoworkPrompt(
  prompt: string,
  runtime: CoworkRuntime,
  onEvent: (ev: CoworkActionEvent) => void,
  signal?: AbortSignal,
  extras: RunCoworkExtras = {},
): Promise<void> {
  let workspaceRoot = ''
  try {
    workspaceRoot = await getWorkspacePath()
  } catch {
    workspaceRoot = ''
  }
  const capabilities = getCoworkCapabilities(runtime)
  const promptId = makePromptId()

  await orchestrateCoworkRun(
    prompt,
    runtime,
    capabilities,
    workspaceRoot,
    {
      plan: async (ctx) => {
        // v82m7 — enrich the orchestrator's raw ctx with bridge-driven
        // signals BEFORE handing it to the planner. ineffectiveHosts is
        // populated from /api/cowork/dual-signal-effective for the current
        // host ; history[*].delta_history is populated from
        // /api/cowork/extraction-stats per known host. Both fetches are
        // cached per-host with 60-second TTL so a multi-iter plan loop
        // doesn't thrash the bridge. Errors silently swallowed → empty
        // arrays, never break the planner.
        const enriched = await enrichPlannerContextWithBridgeSignals(ctx)
        // v82m8 — `enriched` carries `ineffectiveHosts` and
        // `trendIneffectiveHosts` (added by the enricher even if the
        // orchestrator ctx type doesn't declare them statically). We
        // spread enriched FIRST so both fields propagate to planNextStep,
        // then layer on the extras / pin list.
        return planNextStep({
          ...enriched,
          conversationHistory: extras.conversationHistory,
          attachedImageDescriptions: extras.attachedImageDescriptions,
          projectThread: extras.projectThread,
          // v82m6 — pin propagation : surface user-pinned connectors to the
          // planner so the LLM can prefer their dedicated actions over generic
          // open_url/extract_structured. Empty list → ZERO token overhead.
          pinnedConnectorIds: readPinnedConnectors().map((p) => p.id),
        })
      },
      execute: (action, rt, ws, sig) => runAction(action, rt, ws, sig),
      confirm: (args) => requestConfirmationViaStore(args),
      audit: (entry) => appendAuditEntry({
        ...entry,
        prompt: prompt.trim().slice(0, 200),
      }),
      getSettings: () => {
        const s = loadSettings()
        return { trustMode: s.trustMode, dangerMode: s.dangerMode, fullyUnlocked: s.fullyUnlocked }
      },
      // v82m5 — dual-signal escalation acceptance reporter. Fire-and-forget
      // POST to /api/cowork/dual-signal-event ; never throws (best-effort
      // observability — the reporter swallows network errors so the plan
      // loop can never break on telemetry hiccups).
      reportDualSignal: (kind, host) => reportDualSignalEvent(kind, host),
      // v82m7 — symmetric tier-2 reporter for the DUAL_SIGNAL_TREND nudge.
      // Same fire-and-forget contract as reportDualSignal ; targets
      // /api/cowork/trend-signal-event so tier-1 / tier-2 metrics stay
      // separate.
      reportTrendSignal: (kind, host) => reportTrendSignalEvent(kind, host),
    },
    {
      signal,
      onEvent,
      module: extras.module,
      voiceMode: extras.voiceMode,
      promptId,
    },
  )
}

// ---------------------------------------------------------------------------
// Confirmation bridge — uses the cowork store to wait for user input.
// ---------------------------------------------------------------------------

function requestConfirmationViaStore(args: {
  action: CoworkAction
  reason: string
  destructive: boolean
}): Promise<'approved' | 'skipped' | 'aborted'> {
  return new Promise((resolve) => {
    const id = `confirm-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    useCoworkStore.getState().requestConfirmation({
      id,
      action: args.action,
      reason: args.reason,
      destructive: args.destructive,
      approve: () => {
        useCoworkStore.getState().clearConfirmation()
        resolve('approved')
      },
      skip: () => {
        useCoworkStore.getState().clearConfirmation()
        resolve('skipped')
      },
      abort: () => {
        useCoworkStore.getState().clearConfirmation()
        resolve('aborted')
      },
    })
  })
}
