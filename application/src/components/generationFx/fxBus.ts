import { useEffect, useRef } from 'react'

export type FxModule =
  | 'conversation' | 'image' | 'code' | 'video' | 'drawing'
  | '3d' | 'learning' | 'cyber' | 'business' | 'voice' | 'cowork'

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
  /** index d'étape réellement atteint (prioritaire sur l'analyse du texte de phase) */
  phaseIndex?: number
  /** nouvelle tentative explicite : l'étape 3D peut revenir en arrière (sinon elle ne recule pas) */
  phaseReset?: boolean
  /** progression globale 0..1 fournie par le producteur */
  progress?: number
  /**
   * 'fine' : mesure continue réelle (pas k/N, pourcentage calculé par le pipeline) ;
   * 'stage' (défaut) : jalon d'étape. Seule une mesure fine nourrit la vitesse
   * utilisée par l'estimation du temps restant.
   */
  progressKind?: 'fine' | 'stage'
  /** avancement mesuré à l'intérieur de l'étape en cours (0..1), ex. pas de diffusion */
  phaseFraction?: number
  /** le module affiche déjà son contenu (flux de texte) : l'écran plein se réduit en pastille */
  revealContent?: boolean
  /** issue explicite pour un module sans job géré : seul 'success' alimente l'historique */
  outcome?: 'success' | 'error' | 'cancelled'
  resultUrl?: string
  /** 'mesh' : maillage 3D final, verrouillé dans l'hologramme avant de passer au viewer */
  resultKind?: 'image' | 'video' | 'mesh'
  refs?: FxRef[]
  /** type de sujet demandé (character, creature, product…) : règles de profil propres aux personnages */
  subjectKind?: string
  logLine?: string
  meshUrl?: string
  meshInfo?: string
  ask?: FxAsk | null
}

export type FxEmitterOptions = Pick<FxPatch, 'phaseIndex' | 'progressKind' | 'revealContent' | 'outcome'>

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

export function useGenerationFxEmitter(
  module: FxModule,
  active: boolean,
  phase?: string,
  progress?: number,
  options?: FxEmitterOptions,
): void {
  const was = useRef(false)
  const phaseIndex = options?.phaseIndex
  const progressKind = options?.progressKind
  const revealContent = options?.revealContent
  const outcome = options?.outcome
  // l'issue est lue au moment de la fin, sans relancer d'émission à chaque rendu
  const outcomeRef = useRef(outcome)
  outcomeRef.current = outcome
  useEffect(() => {
    if (active) {
      was.current = true
      emitGenerationFx(module, { active: true, phase, progress, phaseIndex, progressKind, revealContent })
    } else if (was.current) {
      was.current = false
      emitGenerationFx(module, { active: false, outcome: outcomeRef.current })
    }
  }, [module, active, phase, progress, phaseIndex, progressKind, revealContent])
  useEffect(() => () => {
    if (was.current) emitGenerationFx(module, { active: false, outcome: 'cancelled' })
  }, [module])
}
