/**
 * useVideoViewLogic — editorial cinema state machine, full lifecycle.
 *
 * v82jy : ce hook expose maintenant le full lifecycle render natif
 * (no manga delegate). AuroraV1VideoView en mode "live" rend la salle
 * de projection editorial native qui consume directement ces APIs.
 *
 * APIs exposées :
 *   - prompt + aspect/length/style + history persistant
 *   - generateStoryboard() → POST /api/cinema/storyboard
 *   - runRender() → POST /api/cinema/generate + polling /api/cinema/job/:id
 *   - jobStatus, videoUrl, rendering, cancelRender()
 *   - reset / abort
 *
 * Polling toutes les 2s, cleanup auto à l'unmount via useEffect.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useGenerationFxEmitter, useGenerationFxResult } from '../components/generationFx/fxBus'
import {
  cinemaGenerateStoryboard,
  cinemaGenerateRun,
  cinemaJobStatus,
  cinemaCancelJob,
  cinemaPreviewKeyframes,
  cinemaSelftest,
  cinemaSelftestResultFromJob,
  cinemaBenchmark,
  auroraStorageStatus,
  videoGallery,
  localFileToBridgeUrl,
  type Storyboard,
  type StoryboardResponse,
  type CinemaJobStatus,
  type CinemaPreviewKeyframesResponse,
  type CinemaSelftestResponse,
  type CinemaBenchmarkResult,
  type AuroraStorageStatus,
  type VideoGalleryResponse,
} from '../services/cinemaApi'
import { RANDOM_VIDEO_PROMPTS, RANDOM_VIDEO_STYLES, pickRandom as pickRandomCreative } from '../utils/randomCreativePrompts'
import { readHistory, pushHistory, removeHistoryEntry, type PromptHistoryEntry } from '../utils/promptHistory'
import { analyzeVideoPrompt } from '../services/videoPromptComposer'
import { useModuleHistoryStore } from '../stores/moduleHistoryStore'

export type VideoAspect = '16:9' | '9:16' | '1:1' | '4:3'
export type VideoLength = 'short' | 'medium' | 'long'

export interface UseVideoViewLogic {
  prompt: string
  setPrompt: (s: string) => void
  aspect: VideoAspect
  setAspect: (a: VideoAspect) => void
  length: VideoLength
  setLength: (l: VideoLength) => void
  style: string
  setStyle: (s: string) => void

  generating: boolean
  storyboard: Storyboard | null
  clarification: string | null
  error: string | null

  // v82lf : option subtitles (build SRT + mux mov_text dans mp4 final)
  subtitlesEnabled: boolean
  setSubtitlesEnabled: (b: boolean) => void

  generateStoryboard: () => Promise<void>
  reset: () => void
  hasResult: boolean
  // v82ez : random preset (prompt + style)
  randomVideoPreset: () => void
  // v82gs : prompt history persistant
  history: PromptHistoryEntry[]
  recallPrompt: (entry: PromptHistoryEntry) => void
  removeHistory: (prompt: string) => void
  // v82jy : full render lifecycle (native aurora_v1, no manga delegate)
  rendering: boolean
  jobStatus: CinemaJobStatus | null
  videoUrl: string | null
  runRender: () => Promise<void>
  cancelRender: () => Promise<void>
  // v82lj : preview keyframes (FLUX-only, fast, before Wan2.2 long render)
  previewing: boolean
  previewResult: CinemaPreviewKeyframesResponse | null
  previewKeyframes: () => Promise<void>
  // v82lm : selftest pipeline
  selftesting: boolean
  selftestResult: CinemaSelftestResponse | null
  runSelftest: () => Promise<void>
  benchmarking: boolean
  benchmarkResult: CinemaBenchmarkResult | null
  runBenchmark: () => Promise<void>
  storageStatus: AuroraStorageStatus | null
  refreshStorageStatus: () => Promise<void>
  gallery: VideoGalleryResponse | null
  refreshGallery: () => Promise<void>
}

const LENGTH_HINTS: Record<VideoLength, string> = {
  short: '15s court',
  medium: '30s standard',
  long: '60s long',
}

export function useVideoViewLogic(): UseVideoViewLogic {
  const openPromptSession = useModuleHistoryStore((s) => s.openPromptSession)
  const pushMessage = useModuleHistoryStore((s) => s.pushMessage)
  const [prompt, setPrompt] = useState('')
  const [aspect, setAspect] = useState<VideoAspect>('16:9')
  const [length, setLength] = useState<VideoLength>('medium')
  const [style, setStyle] = useState('cinematic')
  // v82lf : subtitles option (default off — opt-in pour pas surprendre)
  const [subtitlesEnabled, setSubtitlesEnabled] = useState(false)

  const [generating, setGenerating] = useState(false)
  const [storyboard, setStoryboard] = useState<Storyboard | null>(null)
  const [clarification, setClarification] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // v82gs : prompt history persistant.
  const [history, setHistory] = useState<PromptHistoryEntry[]>(() => readHistory('video'))
  const recallPrompt = useCallback((entry: PromptHistoryEntry) => {
    const sessionId = typeof entry.meta?.sessionId === 'string' ? entry.meta.sessionId : null
    openPromptSession('video', entry.prompt, sessionId)
    setPrompt(entry.prompt)
    if (entry.meta?.style && typeof entry.meta.style === 'string') setStyle(entry.meta.style)
    setStoryboard(null)
    setClarification(null)
    setError(null)
    setJobStatus(null)
    setVideoUrl(null)
    setPreviewResult(null)
  }, [openPromptSession])
  const removeHistory = useCallback((p: string) => {
    setHistory(removeHistoryEntry('video', p))
  }, [])

  const generateStoryboard = useCallback(async () => {
    const text = prompt.trim()
    if (!text || generating) return
    setGenerating(true)
    setStoryboard(null)
    setClarification(null)
    setError(null)
    try {
      // v84 : grammaire cinema detectee dans le prompt FR (camera, plan,
      // lumiere, style, tempo) transmise au realisateur LLM comme contrainte
      // dure — les demandes explicites de l'utilisateur ne se perdent plus
      // dans la traduction du storyboard.
      const cine = analyzeVideoPrompt(text)
      const cineDirectives = [
        cine.shot,
        ...(cine.staticCamera ? ['static camera, locked shot'] : cine.camera),
        ...cine.lighting,
        cine.style,
        cine.tempo,
      ].filter(Boolean)
      // 2026-08-07 : profil actif `personal_quality_first` (cf.
      // `config/video_model_strategy.json`) — la livraison finale vise 1080p
      // via l'étage upscale (`video_upscale_chain.py`). Envoyer 720p en indice
      // au storyboard bridait toute la chaîne à HD, sous le profil actif.
      // La génération native reste dans la fenêtre native du modèle vidéo
      // (720×1280 / 832×480 pour Wan) — c'est l'upscale qui monte à 1080p.
      const resp: StoryboardResponse = await cinemaGenerateStoryboard(text, {
        aspect,
        resolution: '1080p',
        lengthHint: LENGTH_HINTS[length],
        style,
        ...(cineDirectives.length > 0 ? { cinematography: cineDirectives.join('; ') } : {}),
      })
      if (resp.storyboard) {
        setStoryboard(resp.storyboard)
        // v82gs/v86 : l'historique pointe vers une vraie session isolee,
        // pas seulement vers le texte du prompt.
        pushMessage('video', { role: 'user', content: text })
        const activeSession = useModuleHistoryStore.getState().getActiveSession('video')
        pushMessage('video', {
          role: 'assistant',
          content: `Storyboard "${resp.storyboard.title || 'video'}" pret: ${resp.storyboard.summary || `${resp.storyboard.shots?.length ?? 0} plans`}.`,
        })
        setHistory(pushHistory('video', text, { style, aspect, length, sessionId: activeSession.id }))
      } else if (resp.clarification) {
        setClarification(resp.clarification)
      } else if (resp.error) {
        setError(resp.error)
      } else {
        setError('Réponse vide du bridge cinema')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setGenerating(false)
    }
  }, [prompt, generating, aspect, length, style, pushMessage])

  // v82ez / v82fg : random storyboard depuis pool mutualisé.
  const randomVideoPreset = useCallback(() => {
    setPrompt(pickRandomCreative(RANDOM_VIDEO_PROMPTS))
    setStyle(pickRandomCreative(RANDOM_VIDEO_STYLES, style))
  }, [style])

  // v82jy : full render lifecycle native (no manga delegate).
  const [rendering, setRendering] = useState(false)
  const [jobStatus, setJobStatus] = useState<CinemaJobStatus | null>(null)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  // v82lj : preview keyframes state
  const [previewing, setPreviewing] = useState(false)
  const [previewResult, setPreviewResult] = useState<CinemaPreviewKeyframesResponse | null>(null)
  // v82lm : self-test state
  const [selftesting, setSelftesting] = useState(false)
  const [selftestResult, setSelftestResult] = useState<CinemaSelftestResponse | null>(null)
  const [benchmarking, setBenchmarking] = useState(false)
  const [benchmarkResult, setBenchmarkResult] = useState<CinemaBenchmarkResult | null>(null)
  const [storageStatus, setStorageStatus] = useState<AuroraStorageStatus | null>(null)
  const [gallery, setGallery] = useState<VideoGalleryResponse | null>(null)
  useGenerationFxEmitter(
    'video',
    generating || rendering || previewing || benchmarking,
    benchmarking
      ? 'Comparaison qualité Wan / LTX'
      : jobStatus?.status === 'running' ? 'Rendu cinéma en cours' : undefined,
  )
  useGenerationFxResult('video', rendering, videoUrl, 'video')
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const cancelledRef = useRef(false)
  const previewCancelledRef = useRef(false)
  const previewJobIdRef = useRef<string | null>(null)
  const selftestCancelledRef = useRef(false)
  const selftestJobIdRef = useRef<string | null>(null)
  const benchmarkCancelledRef = useRef(false)
  const benchmarkJobIdRef = useRef<string | null>(null)

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
  }, [])

  const refreshStorageStatus = useCallback(async () => {
    try {
      setStorageStatus(await auroraStorageStatus())
    } catch {
      setStorageStatus(null)
    }
  }, [])

  const refreshGallery = useCallback(async () => {
    try {
      setGallery(await videoGallery())
    } catch {
      setGallery(null)
    }
  }, [])

  useEffect(() => {
    void refreshStorageStatus()
    void refreshGallery()
  }, [refreshStorageStatus, refreshGallery])

  useEffect(() => () => stopPolling(), [stopPolling])

  const cancelRender = useCallback(async () => {
    cancelledRef.current = true
    stopPolling()
    setRendering(false)
    const activeJobId = jobStatus?.jobId
    if (!activeJobId || !['queued', 'running'].includes(jobStatus.status)) return
    try {
      await cinemaCancelJob(activeJobId)
      setJobStatus((current) => current
        ? { ...current, status: 'cancelled', error: 'Rendu annulé.' }
        : current)
    } catch (e) {
      setError(`Annulation impossible : ${e instanceof Error ? e.message : String(e)}`)
    }
  }, [jobStatus, stopPolling])

  // Vrai micro-rendu asynchrone : FLUX -> video -> voix -> mux -> ffprobe.
  const runSelftest = useCallback(async () => {
    if (selftesting) return
    selftestCancelledRef.current = false
    setSelftesting(true)
    setSelftestResult(null)
    try {
      const spawn = await cinemaSelftest()
      if (!spawn.jobId) {
        setSelftestResult(spawn)
        return
      }
      selftestJobIdRef.current = spawn.jobId
      setSelftestResult(spawn)
      while (!selftestCancelledRef.current) {
        const job = await cinemaJobStatus(spawn.jobId)
        if (job.status === 'done') {
          setSelftestResult(cinemaSelftestResultFromJob(job))
          return
        }
        if (job.status === 'cancelled') {
          setSelftestResult({
            ok: false,
            jobId: spawn.jobId,
            status: 'cancelled',
            overall_ok: false,
            stages: {},
            summary: 'Micro-rendu annulé.',
          })
          return
        }
        if (job.status === 'unknown') {
          throw new Error(job.error || 'Le micro-rendu est introuvable.')
        }
        if (job.status === 'failed') {
          throw new Error(job.error || 'Le micro-rendu a échoué.')
        }
        setSelftestResult((current) => current
          ? {
              ...current,
              // The other terminal states are handled above; this branch is
              // necessarily one of the two states accepted by self-test UI.
              status: job.status === 'queued' ? 'queued' : 'running',
              summary: job.status === 'queued'
                ? 'Micro-rendu en file GPU…'
                : 'Micro-rendu réel en cours…',
            }
          : current)
        await new Promise((resolve) => setTimeout(resolve, 2000))
      }
    } catch (e) {
      setSelftestResult({
        ok: false, overall_ok: false, stages: {},
        summary: e instanceof Error ? e.message : String(e),
      })
    } finally {
      selftestJobIdRef.current = null
      setSelftesting(false)
    }
  }, [selftesting])

  const runBenchmark = useCallback(async () => {
    if (!storyboard || benchmarking) return
    benchmarkCancelledRef.current = false
    setBenchmarking(true)
    setBenchmarkResult(null)
    try {
      const spawn = await cinemaBenchmark(storyboard)
      benchmarkJobIdRef.current = spawn.jobId
      while (!benchmarkCancelledRef.current) {
        const job = await cinemaJobStatus(spawn.jobId)
        if (job.status === 'done') {
          const result = job.result
          if (result?.kind !== 'video_ab_benchmark') {
            throw new Error(job.error || 'Benchmark terminé sans rapport A/B exploitable.')
          }
          setBenchmarkResult(result as CinemaBenchmarkResult)
          void refreshGallery()
          return
        }
        if (job.status === 'cancelled') {
          setBenchmarkResult({
            ok: false,
            kind: 'video_ab_benchmark',
            winner: null,
            selection_graded: false,
            variants: [],
            error: 'Benchmark annulé.',
          })
          return
        }
        if (job.status === 'unknown') {
          throw new Error(job.error || 'Benchmark A/B introuvable.')
        }
        await new Promise((resolve) => setTimeout(resolve, 2000))
      }
    } catch (e) {
      setBenchmarkResult({
        ok: false,
        kind: 'video_ab_benchmark',
        winner: null,
        selection_graded: false,
        variants: [],
        error: e instanceof Error ? e.message : String(e),
      })
    } finally {
      benchmarkJobIdRef.current = null
      setBenchmarking(false)
    }
  }, [storyboard, benchmarking, refreshGallery])

  // v82lj : preview character keyframes via FLUX before committing Wan2.2.
  const previewKeyframes = useCallback(async () => {
    if (!storyboard || previewing) return
    previewCancelledRef.current = false
    setPreviewing(true)
    setPreviewResult(null)
    try {
      const spawn = await cinemaPreviewKeyframes(storyboard)
      previewJobIdRef.current = spawn.jobId
      while (!previewCancelledRef.current) {
        const status = await cinemaJobStatus(spawn.jobId)
        if (status.status === 'done') {
          const result = status.result as CinemaPreviewKeyframesResponse | undefined
          setPreviewResult(result ?? {
            ok: false,
            error: status.error || 'Aperçu terminé sans résultat exploitable.',
          })
          break
        }
        if (status.status === 'cancelled') {
          setPreviewResult({ ok: false, error: 'Aperçu annulé.' })
          break
        }
        if (status.status === 'unknown') {
          setPreviewResult({ ok: false, error: status.error || 'Job aperçu introuvable.' })
          break
        }
        await new Promise((resolve) => setTimeout(resolve, 2000))
      }
    } catch (e) {
      setPreviewResult({ ok: false, error: e instanceof Error ? e.message : String(e) })
    } finally {
      previewJobIdRef.current = null
      setPreviewing(false)
    }
  }, [storyboard, previewing])

  const runRender = useCallback(async () => {
    if (!storyboard || rendering) return
    cancelledRef.current = false
    setRendering(true)
    setVideoUrl(null)
    setError(null)
    try {
      // v82lf : inject the subtitles flag into the storyboard before sending.
      // Storyboard schema has subtitles: { enabled, ... } so we override.
      const enrichedStoryboard = {
        ...storyboard,
        subtitles: { ...(storyboard.subtitles || {}), enabled: subtitlesEnabled },
      }
      const spawn = await cinemaGenerateRun(enrichedStoryboard)
      if (cancelledRef.current) return
      setJobStatus({ jobId: spawn.jobId, status: 'queued', outputPath: spawn.outputPath })
      pollIntervalRef.current = setInterval(async () => {
        if (cancelledRef.current) { stopPolling(); return }
        try {
          const st = await cinemaJobStatus(spawn.jobId)
          setJobStatus(st)
          if (st.status === 'done') {
            stopPolling()
            setRendering(false)
            void refreshStorageStatus()
            void refreshGallery()
            const file = st.result?.video || st.outputPath
            if (file) setVideoUrl(localFileToBridgeUrl(file))
            if (st.result?.error || st.error) setError(st.result?.error || st.error || null)
          } else if (st.status === 'cancelled') {
            stopPolling()
            setRendering(false)
            setError('Rendu annulé.')
          } else if (st.status === 'unknown' && st.error) {
            stopPolling()
            setRendering(false)
            setError(st.error)
          }
        } catch (e) {
          stopPolling()
          setRendering(false)
          setError(e instanceof Error ? e.message : String(e))
        }
      }, 2000)
    } catch (e) {
      setRendering(false)
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [storyboard, rendering, stopPolling, subtitlesEnabled, refreshStorageStatus, refreshGallery])

  const reset = useCallback(() => {
    void cancelRender()
    previewCancelledRef.current = true
    if (previewJobIdRef.current) {
      void cinemaCancelJob(previewJobIdRef.current).catch(() => undefined)
    }
    selftestCancelledRef.current = true
    if (selftestJobIdRef.current) {
      void cinemaCancelJob(selftestJobIdRef.current).catch(() => undefined)
    }
    benchmarkCancelledRef.current = true
    if (benchmarkJobIdRef.current) {
      void cinemaCancelJob(benchmarkJobIdRef.current).catch(() => undefined)
    }
    setPrompt('')
    setStoryboard(null)
    setClarification(null)
    setError(null)
    setGenerating(false)
    setJobStatus(null)
    setVideoUrl(null)
  }, [cancelRender])

  return {
    prompt, setPrompt,
    aspect, setAspect,
    length, setLength,
    style, setStyle,
    generating,
    storyboard,
    clarification,
    error,
    generateStoryboard,
    reset,
    randomVideoPreset,
    hasResult: storyboard !== null || clarification !== null || error !== null,
    // v82gs : prompt history
    history, recallPrompt, removeHistory,
    // v82jy : full render lifecycle native
    rendering,
    jobStatus,
    videoUrl,
    runRender,
    cancelRender,
    // v82lf : subtitles toggle
    subtitlesEnabled,
    setSubtitlesEnabled,
    // v82lj : preview keyframes
    previewing,
    previewResult,
    previewKeyframes,
    // v82lm : selftest
    selftesting,
    selftestResult,
    runSelftest,
    benchmarking,
    benchmarkResult,
    runBenchmark,
    storageStatus,
    refreshStorageStatus,
    gallery,
    refreshGallery,
  }
}
