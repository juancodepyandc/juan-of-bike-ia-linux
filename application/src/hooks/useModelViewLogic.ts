/**
 * useModelViewLogic — minimal editorial 3D intent state machine.
 *
 * Skeleton hook (v82bf), same pattern as useCodeViewLogic /
 * useVideoViewLogic. The full ModelView (3617 LOC) ships the
 * Hunyuan3D + DreamGaussian + Blender procedural + Meshroom router
 * with rescue, bones display, HDRI, and post-process.
 *
 * For now this hook offers the synchronous intent preview only :
 *   - prompt + style/aspect hints
 *   - previewIntent() → calls threeDIntent.previewThreeDIntent (sync,
 *     deterministic, no bridge call) so the editorial preview can
 *     show the user which pipeline (Hunyuan3D / DreamGaussian /
 *     Blender procedural / Meshroom) would handle their prompt
 *     BEFORE they commit to the full generation.
 *   - reset
 *
 * It does NOT spawn the actual 3D generation. That requires Hunyuan3D
 * / DreamGaussian / etc. which take minutes and need polling — the
 * "ENTRER DANS L'ATELIER 3D" button still mounts the full ModelView
 * for that.
 *
 * Future iters can grow this : add an /api/3d/preview endpoint that
 * runs a fast Blender procedural pass, call it from this hook, and
 * stream the GLB back to a small Three.js viewer in the editorial
 * preview, so the user sees a working low-res mesh without leaving
 * the editorial.
 */
import { useCallback, useState } from 'react'
import { previewThreeDIntent, type ThreeDIntent } from '../services/threeDIntent'
import { RANDOM_3D_PROMPTS, pickRandom as pickRandomCreative } from '../utils/randomCreativePrompts'
import { readHistory, pushHistory, removeHistoryEntry, type PromptHistoryEntry } from '../utils/promptHistory'
import { useModuleHistoryStore } from '../stores/moduleHistoryStore'

export interface UseModelViewLogic {
  prompt: string
  setPrompt: (s: string) => void
  intent: ThreeDIntent | null
  analyzing: boolean
  error: string | null
  previewIntent: () => void
  reset: () => void
  hasResult: boolean
  // v82fb : preset surprise (random 3D prompt)
  randomThreeDPreset: () => void
  // v82gt : prompt history persistant
  history: PromptHistoryEntry[]
  recallPrompt: (entry: PromptHistoryEntry) => void
  removeHistory: (prompt: string) => void
}

export function useModelViewLogic(): UseModelViewLogic {
  const openPromptSession = useModuleHistoryStore((s) => s.openPromptSession)
  const pushMessage = useModuleHistoryStore((s) => s.pushMessage)
  const [prompt, setPrompt] = useState('')
  const [intent, setIntent] = useState<ThreeDIntent | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // v82gt : prompt history persistant.
  const [history, setHistory] = useState<PromptHistoryEntry[]>(() => readHistory('3d'))
  const recallPrompt = useCallback((entry: PromptHistoryEntry) => {
    const sessionId = typeof entry.meta?.sessionId === 'string' ? entry.meta.sessionId : null
    openPromptSession('3d', entry.prompt, sessionId)
    setPrompt(entry.prompt)
    setIntent(null)
    setError(null)
  }, [openPromptSession])
  const removeHistory = useCallback((p: string) => {
    setHistory(removeHistoryEntry('3d', p))
  }, [])

  const previewIntent = useCallback(() => {
    const text = prompt.trim()
    if (!text) return
    setAnalyzing(true)
    setIntent(null)
    setError(null)
    try {
      // previewThreeDIntent is synchronous (deterministic fallback —
      // no LLM, no bridge call, no async). Wrap in setTimeout 0 to
      // give the UI a paint cycle for the analyzing state.
      window.setTimeout(() => {
        try {
          const result = previewThreeDIntent(text, [])
          setIntent(result)
          // v82gt/v86 : historique lie a la session, pas seulement au texte.
          pushMessage('3d', { role: 'user', content: text })
          const activeSession = useModuleHistoryStore.getState().getActiveSession('3d')
          pushMessage('3d', {
            role: 'assistant',
            content: `Intent 3D: ${result.summary}. Pipeline: ${result?.pipelineRouting?.pipeline ?? 'unknown'}.`,
          })
          setHistory(pushHistory('3d', text, { pipeline: result?.pipelineRouting?.pipeline ?? 'unknown', sessionId: activeSession.id }))
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e))
        } finally {
          setAnalyzing(false)
        }
      }, 0)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setAnalyzing(false)
    }
  }, [prompt, pushMessage])

  const reset = useCallback(() => {
    setPrompt('')
    setIntent(null)
    setError(null)
    setAnalyzing(false)
  }, [])

  // v82fb / v82fg : random 3D prompt depuis pool mutualisé.
  const randomThreeDPreset = useCallback(() => {
    setPrompt(pickRandomCreative(RANDOM_3D_PROMPTS))
  }, [])

  return {
    prompt, setPrompt,
    intent,
    analyzing,
    error,
    previewIntent,
    reset,
    hasResult: intent !== null || error !== null,
    randomThreeDPreset,
    // v82gt : prompt history
    history, recallPrompt, removeHistory,
  }
}
