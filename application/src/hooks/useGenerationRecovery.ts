import { useCallback, useEffect, useRef, useState } from 'react'
import { useGenerationTrackerStore, type TrackedGeneration } from '../stores/generationTrackerStore'
import { comfyuiGetHistory, comfyuiGetImage, toAssetUrl } from './useTauri'
import { extractComfyImageOutput, waitForComfyResult } from '../utils/comfyui'
import { scanOutputFiles } from '../utils/outputScanner'
import type { ModuleId } from '../types/app'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RecoveredResult {
  generation: TrackedGeneration
  /** URL affichable (blob ou asset) */
  url?: string
  /** Blob du fichier recupere */
  blob?: Blob
  /** Chemin du fichier sur disque */
  path?: string
}

export interface GenerationRecoveryState {
  /** True pendant la tentative de recovery */
  recovering: boolean
  /** Generations en attente de decision utilisateur (ollama_stream interrupted) */
  pendingRecoveries: TrackedGeneration[]
  /** Resultats recuperes automatiquement */
  recoveredResults: RecoveredResult[]
  /** Dismiss une generation (l'utilisateur ne veut pas relancer) */
  dismissRecovery: (id: string) => void
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

const PYTHON_POLL_INTERVAL_MS = 5_000
const PYTHON_MAX_WAIT_MS = 20 * 60 * 1000 // 20 min

async function recoverComfyUI(gen: TrackedGeneration): Promise<RecoveredResult | null> {
  if (!gen.comfyPromptId) return null

  try {
    const history = await comfyuiGetHistory(gen.comfyPromptId)
    const entry = history?.[gen.comfyPromptId]

    if (!entry) {
      // Prompt non trouve — ComfyUI a ete redemarre, generation perdue
      return null
    }

    if (entry.status?.status_str === 'error') {
      return null // Erreur pendant le rendu, pas recuperable
    }

    if (entry.status?.completed) {
      // Generation terminee ! Recuperer l'image
      const output = extractComfyImageOutput(entry)
      const blob = await comfyuiGetImage(output.filename, output.subfolder)
      const url = URL.createObjectURL(blob)
      return { generation: gen, url, blob, path: output.filename }
    }

    // Encore en cours — attendre via le systeme normal
    const result = await waitForComfyResult(gen.comfyPromptId, {
      getHistory: comfyuiGetHistory,
      timeoutMs: 300_000,
    })
    const blob = await comfyuiGetImage(result.filename, result.subfolder)
    const url = URL.createObjectURL(blob)
    return { generation: gen, url, blob, path: result.filename }
  } catch {
    return null
  }
}

async function recoverPythonScript(gen: TrackedGeneration): Promise<RecoveredResult | null> {
  if (!gen.expectedOutputDir) return null

  const pattern = gen.expectedOutputPattern || undefined
  const deadline = gen.startedAt + PYTHON_MAX_WAIT_MS

  // Tenter de trouver le fichier immediatement
  const files = await scanOutputFiles(gen.expectedOutputDir, gen.startedAt, pattern)
  if (files.length > 0) {
    const f = files[0]
    return { generation: gen, url: toAssetUrl(f.path), path: f.path }
  }

  // Si le process pourrait encore tourner, poll
  if (Date.now() < deadline) {
    return new Promise<RecoveredResult | null>((resolve) => {
      const interval = setInterval(async () => {
        const found = await scanOutputFiles(gen.expectedOutputDir!, gen.startedAt, pattern)
        if (found.length > 0) {
          clearInterval(interval)
          const f = found[0]
          resolve({ generation: gen, url: toAssetUrl(f.path), path: f.path })
        } else if (Date.now() >= deadline) {
          clearInterval(interval)
          resolve(null)
        }
      }, PYTHON_POLL_INTERVAL_MS)
    })
  }

  return null
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useGenerationRecovery(module: ModuleId): GenerationRecoveryState {
  const [recovering, setRecovering] = useState(false)
  const [pendingRecoveries, setPendingRecoveries] = useState<TrackedGeneration[]>([])
  const [recoveredResults, setRecoveredResults] = useState<RecoveredResult[]>([])
  const ranRef = useRef(false)

  const { getPendingGenerations, completeGeneration, failGeneration, markInterrupted, dismissGeneration } = useGenerationTrackerStore()

  const dismissRecovery = useCallback((id: string) => {
    dismissGeneration(id)
    setPendingRecoveries(prev => prev.filter(g => g.id !== id))
    setRecoveredResults(prev => prev.filter(r => r.generation.id !== id))
  }, [dismissGeneration])

  useEffect(() => {
    if (ranRef.current) return
    ranRef.current = true

    const pending = getPendingGenerations(module)
    if (pending.length === 0) return

    setRecovering(true)

    const run = async () => {
      const interrupted: TrackedGeneration[] = []
      const results: RecoveredResult[] = []

      for (const gen of pending) {
        try {
          if (gen.type === 'comfyui') {
            const result = await recoverComfyUI(gen)
            if (result) {
              completeGeneration(gen.id, {
                resultPath: result.path,
                resultFilename: result.path,
              })
              results.push(result)
            } else {
              failGeneration(gen.id, 'Generation non recuperable apres rafraichissement.')
            }
          } else if (gen.type === 'python_script') {
            const result = await recoverPythonScript(gen)
            if (result) {
              completeGeneration(gen.id, { resultPath: result.path })
              results.push(result)
            } else if (Date.now() - gen.startedAt > PYTHON_MAX_WAIT_MS) {
              failGeneration(gen.id, 'Generation Python non trouvee (timeout).')
            }
            // Si < 20min, on laisse en pending — le polling continue en background
          } else if (gen.type === 'ollama_stream') {
            // Stream non recuperable — proposer de relancer
            markInterrupted(gen.id)
            interrupted.push({ ...gen, status: 'interrupted' })
          }
        } catch {
          failGeneration(gen.id, 'Erreur pendant la tentative de recovery.')
        }
      }

      setPendingRecoveries(interrupted)
      setRecoveredResults(results)
      setRecovering(false)
    }

    void run()
  }, [module]) // eslint-disable-line react-hooks/exhaustive-deps

  return { recovering, pendingRecoveries, recoveredResults, dismissRecovery }
}
