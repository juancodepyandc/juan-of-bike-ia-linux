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
  cinemaPreviewKeyframes,
  cinemaSelftest,
  localFileToBridgeUrl,
  type Storyboard,
  type StoryboardResponse,
  type CinemaJobStatus,
  type CinemaPreviewKeyframesResponse,
  type CinemaSelftestResponse,
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
  cancelRender: () => void
  // v82lj : preview keyframes (FLUX-only, fast, before Wan2.2 long render)
  previewing: boolean
  previewResult: CinemaPreviewKeyframesResponse | null
  previewKeyframes: () => Promise<void>
  // v82lm : selftest pipeline
  selftesting: boolean
  selftestResult: CinemaSelftestResponse | null
  runSelftest: () => Promise<void>
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
      const resp: StoryboardResponse = await cinemaGenerateStoryboard(text, {
        aspect,
        resolution: '720p',
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
  useGenerationFxEmitter(
    'video',
    generating || rendering || previewing,
    jobStatus?.status === 'running' ? 'Rendu cinéma en cours' : undefined,
  )
  useGenerationFxResult('video', rendering, videoUrl, 'video')
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const cancelledRef = useRef(false)

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
  }, [])

  useEffect(() => () => stopPolling(), [stopPolling])

  const cancelRender = useCallback(() => {
    cancelledRef.current = true
    stopPolling()
    setRendering(false)
  }, [stopPolling])

  // v82lm : selftest pipeline (vérifie ComfyUI / Ollama / Wan2 / voice / ffmpeg).
  const runSelftest = useCallback(async () => {
    if (selftesting) return
    setSelftesting(true)
    setSelftestResult(null)
    try {
      const r = await cinemaSelftest()
      setSelftestResult(r)
    } catch (e) {
      setSelftestResult({
        ok: false, overall_ok: false, stages: {},
        summary: e instanceof Error ? e.message : String(e),
      })
    } finally {
      setSelftesting(false)
    }
  }, [selftesting])

  // v82lj : preview character keyframes via FLUX before committing Wan2.2.
  const previewKeyframes = useCallback(async () => {
    if (!storyboard || previewing) return
    setPreviewing(true)
    setPreviewResult(null)
    try {
      const r = await cinemaPreviewKeyframes(storyboard)
      setPreviewResult(r)
    } catch (e) {
      setPreviewResult({ ok: false, error: e instanceof Error ? e.message : String(e) })
    } finally {
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
            const file = st.result?.video || st.outputPath
            if (file) setVideoUrl(localFileToBridgeUrl(file))
            if (st.result?.error || st.error) setError(st.result?.error || st.error || null)
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
  }, [storyboard, rendering, stopPolling, subtitlesEnabled])

  const reset = useCallback(() => {
    cancelRender()
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
  }
}
