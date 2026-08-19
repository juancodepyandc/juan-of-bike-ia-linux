import { useEffect, useRef } from 'react'

export type FxModule =
  | 'conversation' | 'image' | 'code' | 'video' | 'drawing'
  | '3d' | 'learning' | 'cyber' | 'voice' | 'cowork'

export const FX_EVENT = 'aurora:generation-fx'
export const FX_PREF_EVENT = 'aurora:generation-fx-pref'
const FX_PREF_KEY = 'aurora-fx-enabled'

export type FxRef = { url: string; role: string }
export type FxCounters = { photosValidees?: number; photosRejetees?: number; meshTentatives?: number }

// Question posee PAR l'ecran de generation lui-meme. Lecon payee deux fois:
// empiler une modale translucide PAR-DESSUS l'ecran anime est illisible, et
// les clics traversent vers l'interface en dessous (un clic aveugle a ouvert
// un selecteur de fichiers). La question doit etre une PARTIE de l'ecran —
// une seule surface, opaque — et l'ecran bloque tout clic vers le dessous
// tant qu'une reponse est attendue.
export type FxAsk = {
  id: string
  // question       -> texte + options
  // confirm_images -> accepter / refuser (+ peut-etre si allowMaybe)
  // pick_image     -> galerie: cliquer UNE image puis valider
  kind: 'question' | 'confirm_images' | 'pick_image'
  question: string
  categoryLabel?: string
  options?: string[]
  images?: string[]
  allowText?: boolean
  allowMaybe?: boolean
  /** lot: tri image par image (clic = garder/jeter); l'index 0 (reference) est fixe */
  allowPickEach?: boolean
  /** la question attend une PHOTO en reponse (2e vue reelle) */
  allowPhoto?: boolean
}

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
  ask?: FxAsk | null
}

// Registre des reponses en attente + presence du host. Si le host n'est pas
// monte (FX desactive), fxAsk rend null et l'appelant retombe sur sa modale
// classique — jamais une promesse qui ne se resout pas.
const askResolvers = new Map<string, (value: unknown) => void>()
let fxHostMounted = 0

export function markFxHostMounted(on: boolean): void {
  fxHostMounted += on ? 1 : -1
}

export function isFxHostAlive(): boolean {
  return fxHostMounted > 0 && generationFxEnabled()
}

export function fxAsk<T>(module: FxModule, ask: FxAsk): Promise<T> | null {
  if (!isFxHostAlive()) return null
  return new Promise<T>((resolve) => {
    askResolvers.set(ask.id, resolve as (value: unknown) => void)
    emitGenerationFx(module, { active: true, ask })
  })
}

export function fxAnswer(module: FxModule, id: string, value: unknown): void {
  const r = askResolvers.get(id)
  askResolvers.delete(id)
  emitGenerationFx(module, { active: true, ask: null })
  r?.(value)
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
