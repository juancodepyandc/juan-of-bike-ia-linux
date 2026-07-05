// ---------------------------------------------------------------------------
// useAbortableGeneration — centralise le pattern AbortController répété
// dans CodeView, ConversationView, ImageView, LearningView.
//
// Avant : chaque vue déclarait son propre abortRef + pattern try/finally.
// Après : ce hook expose start() / stop() / isRunning, et gère le cleanup.
// ---------------------------------------------------------------------------

import { useCallback, useRef, useState } from 'react'

export type AbortableGenerationHandle = {
  /** Démarre une génération. Annule automatiquement toute génération en cours. */
  start: <T>(fn: (signal: AbortSignal) => Promise<T>) => Promise<T | null>
  /** Annule la génération en cours (no-op si rien ne tourne). */
  stop: () => void
  /** Vrai pendant qu'une génération est active. */
  isRunning: boolean
  /** Signal de la génération active, null si aucune. */
  signal: AbortSignal | null
}

export function useAbortableGeneration(): AbortableGenerationHandle {
  const controllerRef = useRef<AbortController | null>(null)
  const [isRunning, setIsRunning] = useState(false)

  const stop = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort()
      controllerRef.current = null
    }
    setIsRunning(false)
  }, [])

  const start = useCallback(async <T>(fn: (signal: AbortSignal) => Promise<T>): Promise<T | null> => {
    // Annule toute génération précédente
    if (controllerRef.current) {
      controllerRef.current.abort()
    }

    const controller = new AbortController()
    controllerRef.current = controller
    setIsRunning(true)

    try {
      const result = await fn(controller.signal)
      return result
    } catch (err) {
      // AbortError est attendu — ne pas le propager
      if (err instanceof DOMException && err.name === 'AbortError') return null
      if (err instanceof Error && err.name === 'AbortError') return null
      throw err
    } finally {
      // Ne reset que si c'est bien CE controller qui est encore actif
      // (évite d'écraser l'état d'un start() lancé entretemps)
      if (controllerRef.current === controller) {
        controllerRef.current = null
        setIsRunning(false)
      }
    }
  }, [])

  const getSignal = () => controllerRef.current?.signal ?? null

  return {
    start,
    stop,
    isRunning,
    get signal() { return getSignal() },
  }
}
