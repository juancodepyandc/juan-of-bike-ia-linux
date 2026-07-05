/**
 * codeStreamStore — global zustand store driving the Aurora Code module.
 *
 * v85 — REBUILD. Until now this store ran a SINGLE `ollamaChatStream` call
 * with only the current draft as the user message : no conversation history,
 * no existing project files, a 6000-token cap, and `streamOutput` wiped on
 * every submit. The 3500-line `orchestrateCodeGeneration` pipeline (intent
 * → preflight → planning → generation → validation → auto-correction, AND
 * the follow-up continuity analyzer) was dead code for the Aurora skin —
 * only the legacy manga CodeView ever called it.
 *
 * That single gap explained both symptoms the user reported :
 *   - "trop simpliste / non optimisé"  → single-shot, no plan, no validation
 *   - "nouveau projet à chaque fois"   → no history, no existing files
 *
 * This rebuild turns the store into a real PROJECT SESSION :
 *   - `messages[]` keeps the running conversation
 *   - `files[]`    keeps the current project tree
 *   - submit() routes through `orchestrateCodeGeneration`, which runs the
 *     follow-up analyzer (increment / pivot / fresh) and merges changed
 *     files onto the existing set instead of restarting from scratch
 *   - a real ETA is derived from pipeline progress + token throughput
 *   - a work mode (online vs local repo) lets the user iterate either on an
 *     in-app project (download / open in editor) or directly on a real git
 *     repository on disk (scan as context, write changes back)
 *
 * The state lives here (not in the component) so an in-flight generation
 * survives module navigation.
 */
import { create } from 'zustand'
import { selectCodeModelForHardware } from '../config/models'
import { useAppStore } from './appStore'
import {
  readHistory, pushHistory, removeHistoryEntry,
  type PromptHistoryEntry,
} from '../utils/promptHistory'
import { classifyCodeIntent } from '../services/codeIntent'
import { isVisualProject } from '../services/codeDesignDirectives'
import {
  orchestrateCodeGeneration,
  type CodeFile,
  type FollowUpKind,
} from '../services/codeOrchestrator'
import type { OllamaMessage } from '../types/app'
import { getBridgeUrl } from '../utils/runtime'
import { speakAs, stopSpeaking, clearSpeakQueue } from '../services/auroraVoice'
import { useModuleHistoryStore } from './moduleHistoryStore'

export type CodeWorkMode = 'online' | 'repo'

const NARRATE_VOICE_KEY = 'aurora.code.narrateVoice'

function readNarrateVoice(): boolean {
  try { return localStorage.getItem(NARRATE_VOICE_KEY) === '1' } catch { return false }
}

/**
 * v85e : friendly FIRST-PERSON French narration of what the module is doing
 * right now — "je fais ceci, puis je vais m'attaquer à ça". This is what the
 * UI shows (and optionally speaks). Phase-based so it changes a handful of
 * times per run, not per token.
 */
function narrate(
  phase: CodeStreamState['phase'],
  detail: string,
  ctx: { followUp: FollowUpKind | null; repo: boolean; brand: string | null; correction: boolean },
): string {
  const where = ctx.repo ? 'ton dépôt' : 'le projet'
  // v85f : a CORRECTION ("corrige le bug / écran noir") is a surgical fix, not
  // an addition. The wording must say "je corrige", never "j'ajoute".
  if (ctx.correction) {
    switch (phase) {
      case 'research':
      case 'brand':
      case 'planning':
        return `Je relis ${where} pour localiser le problème, ensuite je le corrige.`
      case 'streaming':
        return 'Je corrige uniquement ce qui ne marche pas, sans toucher au reste.'
      case 'validation':
        return 'Je vérifie que la correction règle bien le souci et ne casse rien d’autre.'
      case 'done':
        return 'C’est corrigé — je viens de te livrer la version réparée.'
      case 'error':
        return 'Je n’ai pas pu corriger automatiquement, je t’explique pourquoi juste en dessous.'
      default:
        return detail || 'Je prépare la correction…'
    }
  }
  switch (phase) {
    case 'research':
      return 'Je cherche des références de design en ligne, ensuite je conçois l’architecture.'
    case 'brand':
      return `J’étudie l’identité de ${ctx.brand || 'la marque'} pour rester fidèle, ensuite je passe à la conception.`
    case 'planning':
      return ctx.followUp === 'increment'
        ? `Je relis ${where} existant pour bien comprendre, ensuite j’applique ta demande.`
        : 'Je conçois l’architecture du projet, ensuite j’écris le code.'
    case 'streaming':
      return ctx.followUp === 'increment'
        ? 'J’applique ta demande au code, puis je vérifierai que tout tient toujours.'
        : `J’écris le code de ${where} maintenant, puis je vérifierai qu’il fonctionne.`
    case 'validation':
      return 'Je teste et je corrige le code généré, puis je te livre le résultat.'
    case 'done':
      return 'C’est prêt — je viens de te livrer le projet.'
    case 'error':
      return 'J’ai rencontré un souci pendant la tâche, je te l’explique juste en dessous.'
    default:
      return detail || 'Je prépare la tâche…'
  }
}

export interface RepoScanInfo {
  files: number
  bytes: number
  branch: string | null
  truncated: boolean
}

interface CodeStreamState {
  draft: string
  streaming: boolean
  streamOutput: string
  error: string | null
  history: PromptHistoryEntry[]
  lastCompletedAt: number | null
  runId: number
  // Coarse phase used by the View for banner colours. The detailed,
  // human-readable status lives in `phaseMessage`, and the numeric 0..100
  // pipeline progress in `progressPct`.
  phase: 'idle' | 'research' | 'brand' | 'planning' | 'streaming' | 'validation' | 'done' | 'error'
  phaseMessage: string
  errorDialog: {
    title: string
    message: string
    suggestion?: string
  } | null
  modelUsed: string | null
  brandPrimary: string | null

  // --- v85 : project session (conversation continuity) ---
  /** Current project files — passed as existingFiles so follow-ups iterate. */
  files: CodeFile[]
  notes: string
  /** Running conversation. Drives the follow-up analyzer. */
  messages: OllamaMessage[]
  /** What the follow-up analyzer decided for the latest turn. */
  followUpKind: FollowUpKind | null
  finalScore: number
  totalAttempts: number

  // --- v85 : real-time progress + ETA ---
  progressPct: number
  genStartedAt: number | null
  etaSecondsRemaining: number | null
  etaTotalSeconds: number | null

  // --- v85e : live first-person narration of the current task ---
  /** Current "je fais X…" sentence (French, first person). */
  narration: string
  /** History of narration lines for this run (capped). */
  narrationLog: string[]
  /** When true, the narration is spoken aloud (TTS). OFF by default. */
  narrateVoice: boolean

  // --- v85 : online vs local repo work mode ---
  workMode: CodeWorkMode
  repoPath: string | null
  repoLabel: string | null
  repoLoaded: boolean
  repoScan: RepoScanInfo | null
  repoBusy: boolean
  repoMessage: string | null
  repoWriteResult: { written: string[]; path: string; ts: number } | null

  // --- v86 : conversation-scoped code workspaces ---
  activeSessionId: string | null
  sessionSnapshots: Record<string, CodeSessionSnapshot>
}

interface CodeStreamActions {
  setDraft: (s: string) => void
  submit: (modelOverride?: string) => Promise<void>
  abort: () => void
  /** Soft reset of the live stream (keeps the project + conversation). */
  reset: () => void
  /** Hard reset — start a brand new project (clears files + conversation). */
  newProject: () => void
  recallPrompt: (entry: PromptHistoryEntry) => void
  removeHistory: (prompt: string) => void
  dismissErrorDialog: () => void
  retryAfterError: () => Promise<void>
  /** Toggle spoken narration (TTS). Persisted; OFF by default. */
  setNarrateVoice: (on: boolean) => void

  // --- v85 : work mode + repo ---
  setWorkMode: (mode: CodeWorkMode) => void
  setRepoPath: (path: string) => void
  pickRepo: () => Promise<void>
  scanRepo: (path?: string) => Promise<void>
  writeRepo: () => Promise<void>
  /** v85f : detect + install the project's deps (detached) so it runs on the PC. */
  installRepoDeps: () => Promise<void>
  clearRepoWriteResult: () => void
  activateSession: (sessionId: string) => void
}

type CodeStreamStore = CodeStreamState & CodeStreamActions

type CodeSessionSnapshot = {
  draft: string
  streamOutput: string
  error: string | null
  lastCompletedAt: number | null
  phase: CodeStreamState['phase']
  phaseMessage: string
  modelUsed: string | null
  brandPrimary: string | null
  files: CodeFile[]
  notes: string
  messages: OllamaMessage[]
  followUpKind: FollowUpKind | null
  finalScore: number
  totalAttempts: number
  progressPct: number
  genStartedAt: number | null
  etaSecondsRemaining: number | null
  etaTotalSeconds: number | null
  narration: string
  narrationLog: string[]
  workMode: CodeWorkMode
  repoPath: string | null
  repoLabel: string | null
  repoLoaded: boolean
  repoScan: RepoScanInfo | null
  repoMessage: string | null
  repoWriteResult: { written: string[]; path: string; ts: number } | null
}

function emptySessionSnapshot(): CodeSessionSnapshot {
  return {
    draft: '',
    streamOutput: '',
    error: null,
    lastCompletedAt: null,
    phase: 'idle',
    phaseMessage: '',
    modelUsed: null,
    brandPrimary: null,
    files: [],
    notes: '',
    messages: [],
    followUpKind: null,
    finalScore: 0,
    totalAttempts: 0,
    progressPct: 0,
    genStartedAt: null,
    etaSecondsRemaining: null,
    etaTotalSeconds: null,
    narration: '',
    narrationLog: [],
    workMode: 'online',
    repoPath: null,
    repoLabel: null,
    repoLoaded: false,
    repoScan: null,
    repoMessage: null,
    repoWriteResult: null,
  }
}

function captureSessionSnapshot(state: CodeStreamState): CodeSessionSnapshot {
  const settledPhase: CodeStreamState['phase'] = state.streaming
    ? (state.files.length > 0 || state.streamOutput ? 'done' : 'idle')
    : state.phase
  return {
    draft: state.draft,
    streamOutput: state.streamOutput,
    error: state.error,
    lastCompletedAt: state.lastCompletedAt,
    phase: settledPhase,
    phaseMessage: state.streaming ? '' : state.phaseMessage,
    modelUsed: state.modelUsed,
    brandPrimary: state.brandPrimary,
    files: state.files,
    notes: state.notes,
    messages: state.messages,
    followUpKind: state.followUpKind,
    finalScore: state.finalScore,
    totalAttempts: state.totalAttempts,
    progressPct: state.streaming ? 0 : state.progressPct,
    genStartedAt: state.streaming ? null : state.genStartedAt,
    etaSecondsRemaining: state.streaming ? null : state.etaSecondsRemaining,
    etaTotalSeconds: state.etaTotalSeconds,
    narration: state.narration,
    narrationLog: state.narrationLog,
    workMode: state.workMode,
    repoPath: state.repoPath,
    repoLabel: state.repoLabel,
    repoLoaded: state.repoLoaded,
    repoScan: state.repoScan,
    repoMessage: state.repoMessage,
    repoWriteResult: state.repoWriteResult,
  }
}

let abortCtrl: AbortController | null = null

/**
 * ETA from pipeline progress. `progressPct` is a 0..100 figure the
 * orchestrator emits per phase. We project total runtime from the elapsed
 * fraction and damp the remaining estimate so it never jumps wildly up.
 */
function computeEta(
  startedAt: number | null,
  prog: number,
  prevRemaining: number | null,
): { remaining: number | null; total: number | null } {
  if (!startedAt || prog <= 2) return { remaining: prevRemaining, total: null }
  const elapsed = (Date.now() - startedAt) / 1000
  const frac = Math.min(0.98, prog / 100)
  const total = elapsed / frac
  let remaining = Math.max(0, total - elapsed)
  // Damp upward jitter : allow the estimate to fall freely but only creep up.
  if (prevRemaining !== null && remaining > prevRemaining + 8) {
    remaining = prevRemaining + 8
  }
  return { remaining: Math.round(remaining), total: Math.round(total) }
}

/** Coarse phase bucket for banner colours, derived from the detail string. */
function phaseFromDetail(detail: string, prog: number): CodeStreamState['phase'] {
  const d = detail.toLowerCase()
  if (/marque|brand/.test(d)) return 'brand'
  if (/recherche|research|reference|inspiration|meilleures pratiques/.test(d)) return 'research'
  if (/plan|architecture|preflight|dossier|contexte de la discussion|analyse/.test(d)) return 'planning'
  if (/validation|sandbox|correction|test|verif/.test(d)) return 'validation'
  if (prog >= 30 && prog < 90) return 'streaming'
  if (prog >= 90) return 'validation'
  return 'planning'
}

/** Short assistant turn summarising what was produced (keeps history light). */
function summariseDelivery(files: CodeFile[], score: number): string {
  const names = files.slice(0, 12).map((f) => f.name).join(', ')
  const extra = files.length > 12 ? ` (+${files.length - 12})` : ''
  return `Projet livré — ${files.length} fichier(s) : ${names}${extra}. Score ${score}%.`
}

export const useCodeStreamStore = create<CodeStreamStore>()((set, get) => ({
  draft: '',
  streaming: false,
  streamOutput: '',
  error: null,
  history: readHistory('code'),
  lastCompletedAt: null,
  runId: 0,
  phase: 'idle',
  phaseMessage: '',
  errorDialog: null,
  modelUsed: null,
  brandPrimary: null,

  files: [],
  notes: '',
  messages: [],
  followUpKind: null,
  finalScore: 0,
  totalAttempts: 0,

  progressPct: 0,
  genStartedAt: null,
  etaSecondsRemaining: null,
  etaTotalSeconds: null,

  narration: '',
  narrationLog: [],
  narrateVoice: readNarrateVoice(),

  workMode: 'online',
  repoPath: null,
  repoLabel: null,
  repoLoaded: false,
  repoScan: null,
  repoBusy: false,
  repoMessage: null,
  repoWriteResult: null,
  activeSessionId: null,
  sessionSnapshots: {},

  dismissErrorDialog() { set({ errorDialog: null }) },

  async retryAfterError() {
    set({ errorDialog: null })
    await get().submit()
  },

  setNarrateVoice(on) {
    try { localStorage.setItem(NARRATE_VOICE_KEY, on ? '1' : '0') } catch { /* ignore */ }
    if (!on) { stopSpeaking(); clearSpeakQueue() }
    set({ narrateVoice: on })
  },

  setDraft(s) { set({ draft: s }) },

  recallPrompt(entry) {
    const sessionId = typeof entry.meta?.sessionId === 'string' ? entry.meta.sessionId : null
    const session = useModuleHistoryStore.getState().openPromptSession('code', entry.prompt, sessionId)
    get().activateSession(session.id)
    set({ draft: entry.prompt })
  },

  removeHistory(p) { set({ history: removeHistoryEntry('code', p) }) },

  setWorkMode(mode) { set({ workMode: mode }) },

  setRepoPath(path) { set({ repoPath: path }) },

  clearRepoWriteResult() { set({ repoWriteResult: null }) },

  activateSession(sessionId) {
    const state = get()
    if (!sessionId || state.activeSessionId === sessionId) return

    if (state.streaming && abortCtrl) {
      abortCtrl.abort()
      abortCtrl = null
      stopSpeaking(); clearSpeakQueue()
    }

    const snapshots = { ...state.sessionSnapshots }
    if (state.activeSessionId) {
      snapshots[state.activeSessionId] = captureSessionSnapshot(state)
    }
    const next = snapshots[sessionId] ?? emptySessionSnapshot()

    set({
      ...next,
      streaming: false,
      errorDialog: null,
      repoBusy: false,
      activeSessionId: sessionId,
      sessionSnapshots: snapshots,
    })
  },

  newProject() {
    if (abortCtrl) abortCtrl.abort()
    stopSpeaking(); clearSpeakQueue()
    set({
      streaming: false, streamOutput: '', draft: '', error: null,
      files: [], notes: '', messages: [], followUpKind: null,
      finalScore: 0, totalAttempts: 0, phase: 'idle', phaseMessage: '',
      progressPct: 0, genStartedAt: null, etaSecondsRemaining: null,
      etaTotalSeconds: null, repoWriteResult: null,
      narration: '', narrationLog: [],
    })
  },

  abort() {
    if (abortCtrl) abortCtrl.abort()
    stopSpeaking(); clearSpeakQueue()
    set({ streaming: false, phase: get().streamOutput ? 'done' : 'idle' })
  },

  reset() {
    if (abortCtrl) abortCtrl.abort()
    set({
      streaming: false, streamOutput: '', draft: '', error: null,
      phase: 'idle', phaseMessage: '', progressPct: 0,
      genStartedAt: null, etaSecondsRemaining: null, etaTotalSeconds: null,
    })
  },

  // -------------------------------------------------------------------------
  // Repo mode — pick / scan / write back through the bridge
  // -------------------------------------------------------------------------

  async pickRepo() {
    set({ repoBusy: true, repoMessage: 'Sélection du dossier…' })
    try {
      const r = await fetch(`${getBridgeUrl()}/api/code/repo/pick`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
        signal: AbortSignal.timeout(120_000),
      })
      const j = await r.json() as { ok?: boolean; path?: string; error?: string }
      if (j?.ok && j.path) {
        set({ repoPath: j.path })
        await get().scanRepo(j.path)
      } else {
        set({ repoBusy: false, repoMessage: j?.error || 'Aucun dossier sélectionné.' })
      }
    } catch (e) {
      set({
        repoBusy: false,
        repoMessage: `Sélecteur indisponible : ${e instanceof Error ? e.message : String(e)}. Colle le chemin manuellement.`,
      })
    }
  },

  async scanRepo(path) {
    const target = (path ?? get().repoPath ?? '').trim()
    if (!target) { set({ repoMessage: 'Chemin du repo vide.' }); return }
    set({ repoBusy: true, repoMessage: 'Lecture du dépôt en cours…' })
    try {
      const r = await fetch(`${getBridgeUrl()}/api/code/repo/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: target, max_files: 120, max_bytes: 1_400_000 }),
        signal: AbortSignal.timeout(60_000),
      })
      const j = await r.json() as {
        ok?: boolean
        error?: string
        path?: string
        label?: string
        branch?: string | null
        truncated?: boolean
        total_files?: number
        total_bytes?: number
        files?: Array<{ path: string; content: string; language?: string }>
      }
      if (!j?.ok || !Array.isArray(j.files)) {
        set({ repoBusy: false, repoLoaded: false, repoMessage: j?.error || 'Lecture du dépôt échouée.' })
        return
      }
      const files: CodeFile[] = j.files.map((f) => ({
        name: f.path,
        language: f.language || 'text',
        content: f.content,
      }))
      set({
        repoPath: j.path || target,
        repoLabel: j.label || target.split(/[\\/]/).filter(Boolean).pop() || target,
        repoLoaded: true,
        repoBusy: false,
        repoScan: {
          files: j.total_files ?? files.length,
          bytes: j.total_bytes ?? 0,
          branch: j.branch ?? null,
          truncated: Boolean(j.truncated),
        },
        repoMessage: `${files.length} fichier(s) chargé(s) comme contexte${j.branch ? ` · branche ${j.branch}` : ''}.`,
        // Seed the project with the real repo files so the orchestrator
        // iterates on the actual codebase. Fresh conversation for this repo.
        files,
        messages: [],
        followUpKind: null,
        streamOutput: '',
        notes: '',
      })
    } catch (e) {
      set({
        repoBusy: false,
        repoLoaded: false,
        repoMessage: `Lecture échouée : ${e instanceof Error ? e.message : String(e)}`,
      })
    }
  },

  async writeRepo() {
    const path = (get().repoPath ?? '').trim()
    const files = get().files
    if (!path) { set({ repoMessage: 'Aucun repo sélectionné.' }); return }
    if (files.length === 0) { set({ repoMessage: 'Aucun fichier à écrire.' }); return }
    set({ repoBusy: true, repoMessage: 'Écriture des changements dans le dépôt…' })
    try {
      const r = await fetch(`${getBridgeUrl()}/api/code/repo/write`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path,
          files: files.map((f) => ({ path: f.name, content: f.content })),
          backup: true,
        }),
        signal: AbortSignal.timeout(30_000),
      })
      const j = await r.json() as { ok?: boolean; written?: string[]; error?: string }
      if (j?.ok) {
        set({
          repoBusy: false,
          repoWriteResult: { written: j.written ?? [], path, ts: Date.now() },
          repoMessage: `${(j.written ?? []).length} fichier(s) écrit(s) dans ${path}.`,
        })
      } else {
        set({ repoBusy: false, repoMessage: j?.error || 'Écriture échouée.' })
      }
    } catch (e) {
      set({
        repoBusy: false,
        repoMessage: `Écriture échouée : ${e instanceof Error ? e.message : String(e)}`,
      })
    }
  },

  async installRepoDeps() {
    const path = (get().repoPath ?? '').trim()
    if (!path) { set({ repoMessage: 'Aucun repo sélectionné.' }); return }
    set({ repoBusy: true, repoMessage: 'Détection + installation des dépendances…' })
    try {
      const r = await fetch(`${getBridgeUrl()}/api/code/repo/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
        signal: AbortSignal.timeout(15_000),
      })
      const j = await r.json() as { ok?: boolean; command?: string; manifest?: string; error?: string }
      set({
        repoBusy: false,
        repoMessage: j?.ok
          ? `Installation lancée : ${j.command} (suis la progression dans la console qui s'est ouverte).`
          : (j?.error || 'Installation échouée.'),
      })
    } catch (e) {
      set({
        repoBusy: false,
        repoMessage: `Installation échouée : ${e instanceof Error ? e.message : String(e)}`,
      })
    }
  },

  // -------------------------------------------------------------------------
  // submit — the real pipeline (continuity + quality)
  // -------------------------------------------------------------------------

  async submit(modelOverride) {
    const text = get().draft.trim()
    if (!text || get().streaming) return
    if (abortCtrl) abortCtrl.abort()
    const ctrl = new AbortController()
    abortCtrl = ctrl

    const app = useAppStore.getState()
    const installed = app.installedModels ?? []
    const baseModel = modelOverride
      ?? selectCodeModelForHardware(app.hardware, installed, app.codeModel)

    // Intent-aware model routing (unchanged logic — picks a general LLM for
    // visual/brand work and a coder model for pure code projects).
    let intent
    try { intent = classifyCodeIntent(text) } catch { intent = null }
    const isVisual = intent ? isVisualProject(intent) : true
    const isCoderModel = /coder|codellama|coding/i.test(baseModel)

    // Expert default: prefer the strongest installed local models for Code V1.
    // Smaller models remain late fallbacks for explicit fast smoke tests only.
    const PREFERRED_GENERAL_SPEED = [
      'qwen3:14b', 'gemma3:27b', 'mistral-small3.1:24b',
      'gemma3:12b', 'qwen3:32b', 'llama3.3',
      'qwen2.5:7b', 'qwen3-vl:30b', 'qwen3-vl:8b',
    ]
    const PREFERRED_GENERAL_QUALITY = [
      'qwen3:14b', 'gemma3:27b', 'mistral-small3.1:24b',
      'gemma3:12b', 'qwen3:32b', 'llama3.3',
      'qwen3-vl:30b', 'qwen2.5:7b', 'qwen3-vl:8b',
    ]
    const PREFERRED_CODER = [
      'qwen3-coder-next:q8_0', 'qwen3-coder-next:q4_K_M',
      'qwen3-coder:30b-a3b-q8_0', 'qwen3-coder:30b-a3b-q4_K_M', 'qwen3-coder:30b',
      'qwen2.5-coder:32b', 'qwen2.5-coder:14b', 'deepseek-coder-v2:16b',
      'qwen2.5-coder:7b', 'codellama:13b',
    ]
    const pickFirstInstalled = (candidates: string[], fallback: string) =>
      installed.length > 0
        ? candidates.find((m) => installed.some((x) => x === m || (!m.includes(':') && x.startsWith(`${m}:`)))) || fallback
        : fallback

    const BRAND_HINT_RE = /\b([A-Z][a-zA-Z]{2,}(?:[\s-][A-Z][a-zA-Z]{2,})?)\b/
    const STOP = new Set(['Page', 'App', 'Application', 'Site', 'Landing', 'Dashboard',
      'Pour', 'Avec', 'Sans', 'Sur', 'Faire', 'Crée', 'Le', 'La', 'Les', 'Un', 'Une', 'Des'])
    const brandHint = (() => {
      const m = text.match(BRAND_HINT_RE)
      return m && !STOP.has(m[1].split(/[\s-]/)[0]) ? m[1] : null
    })()

    let model = baseModel
    let routeReason = 'configured'
    if (isVisual && isCoderModel) {
      const list = brandHint ? PREFERRED_GENERAL_QUALITY : PREFERRED_GENERAL_SPEED
      model = pickFirstInstalled(list, 'qwen3:14b')
      routeReason = `visual${brandHint ? '+brand' : ''} needs general LLM`
    } else if (isVisual && brandHint) {
      const upgrade = pickFirstInstalled(PREFERRED_GENERAL_QUALITY, baseModel)
      if (upgrade && upgrade !== baseModel) { model = upgrade; routeReason = `brand ${brandHint}` }
    } else if (!isVisual && !isCoderModel) {
      const upgrade = pickFirstInstalled(PREFERRED_CODER, '')
      if (upgrade && upgrade !== baseModel) { model = upgrade; routeReason = 'code-heavy → coder model' }
    }
    if (model !== baseModel) console.log(`[code] route: "${baseModel}" → "${model}" (${routeReason})`)

    // Capture the conversation BEFORE this turn so the follow-up analyzer
    // sees genuine prior context (not the message we are about to add).
    const priorMessages = get().messages.slice(-8)
    const existingFiles = get().files

    useModuleHistoryStore.getState().pushMessage('code', { role: 'user', content: text })
    const activeCodeSession = useModuleHistoryStore.getState().getActiveSession('code')

    set({
      history: pushHistory('code', text, { model, sessionId: activeCodeSession.id }),
      runId: get().runId + 1,
      streaming: true,
      streamOutput: '',
      error: null,
      phase: 'planning',
      phaseMessage: priorMessages.length > 0 || existingFiles.length > 0
        ? '🔁 Analyse du contexte de la conversation…'
        : '🔍 Démarrage du pipeline expert…',
      modelUsed: model,
      brandPrimary: null,
      followUpKind: null,
      finalScore: 0,
      totalAttempts: 0,
      progressPct: 1,
      genStartedAt: Date.now(),
      etaSecondsRemaining: null,
      etaTotalSeconds: null,
      narration: '',
      narrationLog: [],
      messages: [...get().messages, { role: 'user', content: text }],
    })

    // v85f : detect a CORRECTION request so generation stays surgical and the
    // narration says "je corrige" (not "j'ajoute"). The user reported that a
    // "corrige X" was treated as "ajouter des modifications".
    const isCorrection = /\b(corrig|fix|r[ée]par|bug|erreur|[ée]cran\s*noir|plante|cass|d[ée]bogue|marche\s*pas|fonctionne\s*pas|r[ée]sou[ds]|ne\s*s'?affiche)\b/i.test(text)

    // v85e : compute + apply the first-person narration whenever the phase
    // changes (and speak it if the enunciate toggle is on). Deduped so the
    // streaming phase doesn't re-announce on every token.
    const applyNarration = (ph: CodeStreamState['phase']) => {
      const st = get()
      const line = narrate(ph, st.phaseMessage, {
        followUp: st.followUpKind,
        repo: st.workMode === 'repo',
        brand: brandHint,
        correction: isCorrection,
      })
      if (line && line !== st.narration) {
        set({ narration: line, narrationLog: [...st.narrationLog, line].slice(-40) })
        if (st.narrateVoice) void speakAs('code', line).catch(() => {})
      }
    }
    applyNarration('planning')

    // Pre-flight 1 — bridge alive.
    try {
      const probe = await fetch(`${getBridgeUrl()}/healthz`, { signal: AbortSignal.timeout(4_000) })
      if (!probe.ok) throw new Error('bridge_unhealthy')
    } catch {
      set({
        streaming: false, phase: 'error', phaseMessage: '',
        errorDialog: {
          title: 'Bridge AuroraIA non joignable',
          message: 'Le bridge Python (port 3001) ne répond pas. Aurora est peut-être fermé ou le tunnel a expiré.',
          suggestion: 'Relance Aurora (start-aurora.bat) ou exécute "python bridge_doctor.py" puis clique OK pour réessayer.',
        },
      })
      return
    }

    // Pre-flight 2 — model present.
    try {
      const tagsResp = await fetch(`${getBridgeUrl()}/proxy/ollama/api/tags`, { signal: AbortSignal.timeout(6_000) })
      if (tagsResp.ok) {
        const tags = await tagsResp.json() as { models?: Array<{ name?: string }> }
        const have = (tags.models ?? []).map((m) => m.name ?? '').filter(Boolean)
        if (have.length > 0 && !have.includes(model)) {
          set({
            streaming: false, phase: 'error', phaseMessage: '',
            errorDialog: {
              title: `Modèle "${model}" non installé`,
              message: `Le modèle ${model} n'est pas dans Ollama. Disponibles : ${have.slice(0, 6).join(', ')}${have.length > 6 ? '…' : ''}.`,
              suggestion: `Lance "ollama pull ${model}" puis clique OK pour réessayer.`,
            },
          })
          return
        }
      }
    } catch { /* best-effort */ }

    if (ctrl.signal.aborted || abortCtrl !== ctrl) {
      set({ phase: 'idle', phaseMessage: '', streaming: false })
      return
    }

    try {
      const result = await orchestrateCodeGeneration({
        prompt: text,
        // v85f : frame corrections as surgical fixes so the model doesn't
        // rewrite/add features when the user only asked to repair something.
        enrichedPrompt: isCorrection
          ? `${text}\n\n## INSTRUCTION — CORRECTION CIBLÉE\nC'est une CORRECTION, pas un ajout. Modifie UNIQUEMENT ce qui est nécessaire pour régler le problème décrit. Ne réécris pas les fichiers qui marchent, n'ajoute AUCUNE fonctionnalité non demandée, préserve tout le reste à l'identique (structure, style, contenu). Si le souci est un écran noir / une erreur runtime, corrige la cause (CSS manquant, JS cassé, import erroné, chemin relatif) et garde le projet exécutable.`
          : text,
        conversationHistory: priorMessages,
        existingFiles,
        contextImages: [],
        configuredCodeModel: model,
        visionModel: model,
        setPhase: (detail, prog) => {
          if (abortCtrl !== ctrl) return
          const prev = get()
          const nextProg = Math.max(prev.progressPct, Math.min(99, Math.round(prog)))
          const { remaining, total } = computeEta(prev.genStartedAt, nextProg, prev.etaSecondsRemaining)
          const nextPhase = phaseFromDetail(detail, nextProg)
          set({
            phaseMessage: detail,
            progressPct: nextProg,
            phase: nextPhase,
            etaSecondsRemaining: remaining,
            etaTotalSeconds: total,
          })
          applyNarration(nextPhase)
        },
        onToken: (token) => {
          if (abortCtrl !== ctrl) return
          const wasPre = ['planning', 'research', 'brand'].includes(get().phase)
          set((prev) => ({
            streamOutput: prev.streamOutput + token,
            phase: prev.phase === 'planning' || prev.phase === 'research' || prev.phase === 'brand'
              ? 'streaming' : prev.phase,
          }))
          if (wasPre) applyNarration('streaming')
        },
        onFilesUpdate: (files, notes) => {
          if (abortCtrl !== ctrl) return
          set({ files, notes })
        },
        onValidationUpdate: () => { /* validation surfaced via phase + score */ },
        onCorrectionLogUpdate: (_log, attempt, score) => {
          if (abortCtrl !== ctrl) return
          set({ totalAttempts: attempt, finalScore: score })
        },
        onFollowUpAnalysis: (analysis) => {
          if (abortCtrl !== ctrl) return
          set({ followUpKind: analysis.kind })
        },
        signal: ctrl.signal,
      })

      if (abortCtrl !== ctrl) return

      const brandColor =
        result.intent?.assetPlan?.subject?.brandProfile?.primaryColor ?? null

      if (result.files.length === 0) {
        set({
          streaming: false, phase: 'error', phaseMessage: '',
          notes: result.notes,
          errorDialog: {
            title: 'Aucun fichier livré',
            message: result.notes?.slice(0, 600) || 'Le pipeline n\'a produit aucun fichier exploitable.',
            suggestion: 'Reformule ou précise la demande puis clique OK pour réessayer.',
          },
        })
        return
      }

      // Append a light assistant turn so the next prompt is treated as a
      // follow-up on THIS project, not a fresh start.
      const deliverySummary = summariseDelivery(result.files, result.finalScore)
      const assistantTurn: OllamaMessage = {
        role: 'assistant',
        content: deliverySummary,
      }
      useModuleHistoryStore.getState().pushMessage('code', { role: 'assistant', content: deliverySummary })

      set({
        streaming: false,
        files: result.files,
        notes: result.notes,
        finalScore: result.finalScore,
        totalAttempts: result.totalAttempts,
        followUpKind: result.followUp?.kind ?? get().followUpKind,
        brandPrimary: brandColor,
        lastCompletedAt: Date.now(),
        phase: 'done',
        phaseMessage: '',
        progressPct: 100,
        etaSecondsRemaining: 0,
        etaTotalSeconds: get().etaTotalSeconds,
        messages: [...get().messages, assistantTurn],
      })
      applyNarration('done')
    } catch (e) {
      if (ctrl.signal.aborted) {
        if (abortCtrl === ctrl) set({ streaming: false, phase: get().streamOutput ? 'done' : 'idle', phaseMessage: '' })
        return
      }
      if (abortCtrl !== ctrl) return
      const errMsg = e instanceof Error ? e.message : String(e)
      let title = 'Échec de la génération'
      let suggestion = 'Clique OK pour réessayer.'
      if (/AbortError|aborted|timeout/i.test(errMsg)) {
        title = 'Timeout du modèle'
        suggestion = 'Le modèle n\'a pas répondu à temps. Vérifie qu\'Ollama tourne puis OK pour réessayer.'
      } else if (/404|not found|unknown model/i.test(errMsg)) {
        title = `Modèle ${model} introuvable`
        suggestion = `Lance "ollama pull ${model}" puis OK pour réessayer.`
      } else if (/connection|refused|fetch/i.test(errMsg)) {
        title = 'Bridge Aurora non joignable'
        suggestion = 'Relance Aurora ou bridge_doctor.py puis OK pour réessayer.'
      }
      set({
        error: errMsg, streaming: false, phase: 'error', phaseMessage: '',
        errorDialog: { title, message: errMsg, suggestion },
      })
      applyNarration('error')
    }
  },
}))

/**
 * Selector helpers — zustand pattern, lets a component subscribe to
 * just one slice without re-rendering on every state change.
 */
export const selectCodeStreaming = (s: CodeStreamStore) => s.streaming
export const selectCodeOutput = (s: CodeStreamStore) => s.streamOutput
export const selectCodeError = (s: CodeStreamStore) => s.error
