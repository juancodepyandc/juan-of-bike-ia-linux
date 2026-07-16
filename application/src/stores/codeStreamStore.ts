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
} from '../services/codeOrchestrator'
import type { OllamaMessage } from '../types/app'
import { getBridgeUrl } from '../utils/runtime'
import { speakAs, stopSpeaking, clearSpeakQueue } from '../services/auroraVoice'
import { useModuleHistoryStore } from './moduleHistoryStore'
import { narrate, readNarrateVoice, writeNarrateVoice } from './codeStreamNarration.ts'
import { checkCodeBridgeReady, checkCodeModelInstalled } from './codeStreamPreflight.ts'
import { captureSessionSnapshot, emptySessionSnapshot } from './codeStreamSessions.ts'
import { computeEta, phaseFromDetail, summariseDelivery } from './codeStreamProgress.ts'
import { isCorrectionRequest, routeCodeStreamModel } from './codeStreamRouting.ts'
import type { CodeStreamState, CodeStreamStore } from './codeStreamTypes.ts'
import {
  appendCodeStreamEvents,
  createCodeStreamEventMetaFactory,
  makeCodeStreamCorrectionEvent,
  makeCodeStreamDoneEvent,
  makeCodeStreamErrorEvent,
  makeCodeStreamFileEvents,
  makeCodeStreamPhaseEvent,
  makeCodeStreamValidationEvent,
  makeInitialCodeStreamPhaseEvent,
} from './codeStreamEventLog.ts'

export type { CodeWorkMode, RepoScanInfo } from './codeStreamTypes.ts'

let abortCtrl: AbortController | null = null

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
  events: [],

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
    writeNarrateVoice(on)
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
      events: [],
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
      events: [],
      genStartedAt: null, etaSecondsRemaining: null, etaTotalSeconds: null,
    })
  },

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

    let intent
    try { intent = classifyCodeIntent(text) } catch { intent = null }
    const isVisual = intent ? isVisualProject(intent) : true
    const routedModel = routeCodeStreamModel({ baseModel, installed, isVisual, text })
    const model = baseModel
    const brandHint = routedModel.brandHint
    if (routedModel.model !== baseModel) {
      console.log(`[code] route suggestion: "${baseModel}" → "${routedModel.model}" (${routedModel.routeReason}); generation keeps coder role "${baseModel}"`)
    }

    // Capture the conversation BEFORE this turn so the follow-up analyzer
    // sees genuine prior context (not the message we are about to add).
    const priorMessages = get().messages.slice(-8)
    const existingFiles = get().files

    useModuleHistoryStore.getState().pushMessage('code', { role: 'user', content: text })
    const activeCodeSession = useModuleHistoryStore.getState().getActiveSession('code')
    const nextRunId = get().runId + 1
    const nextEventMeta = createCodeStreamEventMetaFactory(nextRunId)
    const initialPhaseMessage = priorMessages.length > 0 || existingFiles.length > 0
      ? '🔁 Analyse du contexte de la conversation…'
      : '🔍 Démarrage du pipeline expert…'

    set({
      history: pushHistory('code', text, { model, sessionId: activeCodeSession.id }),
      runId: nextRunId,
      streaming: true,
      streamOutput: '',
      error: null,
      phase: 'planning',
      phaseMessage: initialPhaseMessage,
      modelUsed: model,
      brandPrimary: null,
      followUpKind: null,
      finalScore: 0,
      totalAttempts: 0,
      events: [makeInitialCodeStreamPhaseEvent(nextEventMeta, initialPhaseMessage)],
      progressPct: 1,
      genStartedAt: Date.now(),
      etaSecondsRemaining: null,
      etaTotalSeconds: null,
      narration: '',
      narrationLog: [],
      messages: [...get().messages, { role: 'user', content: text }],
    })

    const isCorrection = isCorrectionRequest(text)

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

    const bridgeIssue = await checkCodeBridgeReady()
    if (bridgeIssue) {
      set((prev) => ({
        streaming: false, phase: 'error', phaseMessage: '',
        events: appendCodeStreamEvents(prev.events, [makeCodeStreamErrorEvent(nextEventMeta, bridgeIssue.message)]),
        errorDialog: bridgeIssue,
      }))
      return
    }

    const modelIssue = await checkCodeModelInstalled(model)
    if (modelIssue) {
      set((prev) => ({
        streaming: false, phase: 'error', phaseMessage: '',
        events: appendCodeStreamEvents(prev.events, [makeCodeStreamErrorEvent(nextEventMeta, modelIssue.message)]),
        errorDialog: modelIssue,
      }))
      return
    }

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
        modelRouting: {
          configuredCodeModel: baseModel,
          installedModels: installed,
          hardware: app.hardware,
        },
        setPhase: (detail, prog) => {
          if (abortCtrl !== ctrl) return
          const prev = get()
          const nextProg = Math.max(prev.progressPct, Math.min(99, Math.round(prog)))
          const { remaining, total } = computeEta(prev.genStartedAt, nextProg, prev.etaSecondsRemaining)
          const nextPhase = phaseFromDetail(detail, nextProg)
          set((current) => ({
            phaseMessage: detail,
            progressPct: nextProg,
            phase: nextPhase,
            etaSecondsRemaining: remaining,
            etaTotalSeconds: total,
            events: appendCodeStreamEvents(current.events, [
              makeCodeStreamPhaseEvent(nextEventMeta, detail, nextProg),
            ]),
          }))
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
          const previousFiles = get().files
          const fileEvents = makeCodeStreamFileEvents(nextEventMeta, files, previousFiles)
          set((prev) => ({
            files,
            notes,
            events: appendCodeStreamEvents(prev.events, fileEvents),
          }))
        },
        onValidationUpdate: (result) => {
          if (abortCtrl !== ctrl) return
          set((prev) => ({
            events: appendCodeStreamEvents(prev.events, [
              makeCodeStreamValidationEvent(nextEventMeta, result),
            ]),
          }))
        },
        onCorrectionLogUpdate: (_log, attempt, score) => {
          if (abortCtrl !== ctrl) return
          set((prev) => ({
            totalAttempts: attempt,
            finalScore: score,
            events: appendCodeStreamEvents(prev.events, [
              makeCodeStreamCorrectionEvent(nextEventMeta, _log, attempt, score),
            ]),
          }))
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
        const message = result.notes?.slice(0, 600) || 'Le pipeline n\'a produit aucun fichier exploitable.'
        set((prev) => ({
          streaming: false, phase: 'error', phaseMessage: '',
          notes: result.notes,
          events: appendCodeStreamEvents(prev.events, [
            makeCodeStreamErrorEvent(nextEventMeta, message),
          ]),
          errorDialog: {
            title: 'Aucun fichier livré',
            message,
            suggestion: 'Reformule ou précise la demande puis clique OK pour réessayer.',
          },
        }))
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

      set((prev) => ({
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
        events: appendCodeStreamEvents(prev.events, [
          makeCodeStreamDoneEvent(
            nextEventMeta,
            result.files,
            result.finalScore,
            result.totalAttempts,
            result.notes,
          ),
        ]),
      }))
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
      set((prev) => ({
        error: errMsg, streaming: false, phase: 'error', phaseMessage: '',
        events: appendCodeStreamEvents(prev.events, [
          makeCodeStreamErrorEvent(nextEventMeta, errMsg),
        ]),
        errorDialog: { title, message: errMsg, suggestion },
      }))
      applyNarration('error')
    }
  },
}))

export const selectCodeStreaming = (s: CodeStreamStore) => s.streaming
export const selectCodeOutput = (s: CodeStreamStore) => s.streamOutput
export const selectCodeError = (s: CodeStreamStore) => s.error
