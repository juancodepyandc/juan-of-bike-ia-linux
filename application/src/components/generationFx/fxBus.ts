import { useEffect, useRef } from 'react'

export type FxModule =
  | 'conversation' | 'image' | 'code' | 'video' | 'drawing'
  | '3d' | 'learning' | 'cyber' | 'voice' | 'cowork'

export const FX_EVENT = 'aurora:generation-fx'
export const FX_PREF_EVENT = 'aurora:generation-fx-pref'
const FX_PREF_KEY = 'aurora-fx-enabled'

export type FxRef = { url: string; role: string }
export type FxCounters = { photosValidees?: number; photosRejetees?: number; meshTentatives?: number }
export type FxPatch = {
  active: boolean
  phase?: string
  progress?: number
  resultUrl?: string
  resultKind?: 'image' | 'video'
  refs?: FxRef[]
  logLine?: string
  meshUrl?: string
  meshInfo?: string
}

export function generationFxEnabled(): boolean {
  try { return window.localStorage.getItem(FX_PREF_KEY) !== '0' } catch { return true }
}

export function setGenerationFxEnabled(on: boolean): void {
  try { window.localStorage.setItem(FX_PREF_KEY, on ? '1' : '0') } catch { /* ignore */ }
  try { window.dispatchEvent(new CustomEvent(FX_PREF_EVENT)) } catch { /* ignore */ }
}

export function emitGenerationFx(module: FxModule, patch: FxPatch): void {
  if (typeof window === 'undefined') return
  try {
    window.dispatchEvent(new CustomEvent(FX_EVENT, { detail: { module, ...patch } }))
  } catch { /* ignore */ }
}

export function useGenerationFxResult(module: FxModule, active: boolean, url: string | null | undefined, kind: 'image' | 'video' = 'image'): void {
  const prev = useRef(false)
  useEffect(() => {
    if (prev.current && !active && url) {
      emitGenerationFx(module, { active: false, resultUrl: url, resultKind: kind })
    }
    prev.current = active
  }, [module, active, url, kind])
}

export function useGenerationFxEmitter(module: FxModule, active: boolean, phase?: string, progress?: number): void {
  const was = useRef(false)
  useEffect(() => {
    if (active) {
      was.current = true
      emitGenerationFx(module, { active: true, phase, progress })
    } else if (was.current) {
      was.current = false
      emitGenerationFx(module, { active: false })
    }
  }, [module, active, phase, progress])
  useEffect(() => () => {
    if (was.current) emitGenerationFx(module, { active: false })
  }, [module])
}
