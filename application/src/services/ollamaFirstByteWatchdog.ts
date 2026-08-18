// ---------------------------------------------------------------------------
// ollamaFirstByteWatchdog — le chien de garde qui coupait sans dire quoi.
//
// MESURE (run v125, 39 min, 41 fichiers produits, journal Ollama a l appui):
//
//   [CodeOrchestrator] Pipeline fatal error (app NOT crashed): This operation
//   was aborted
//
// Trois mesures faites AVANT de toucher une ligne:
//
//   1. `AbortSignal.timeout()` ne peut PAS produire ce message. Sous Node
//      v24.18 il produit `TimeoutError: The operation was aborted due to
//      timeout`, y compris compose par `AbortSignal.any`. Le message
//      « This operation was aborted » est celui d un `AbortController.abort()`
//      SANS raison. La piste `codeInterModuleAssets.combineSignals` est donc
//      exclue par la mesure, pas par l opinion.
//   2. Un flux tronque en cours de route (proxy qui lache) produit
//      `TypeError: terminated`, pas un AbortError. Egalement exclu.
//   3. Sur les 195 modules atteignables depuis `codeOrchestrator.ts`, le SEUL
//      `new AbortController()` suivi d un `.abort()` nu vit dans `useTauri.ts`:
//      le chien de garde de premier octet. Par elimination exhaustive, c est
//      lui.
//
// Journal Ollama du meme run:
//   02:01:43 « aborting completion request due to client closing the
//              connection » -> 500, 3m0s, POST /api/chat
//   02:02:39 « client connection closed before llama-server finished loading »
//              -> 499, 3m30s, POST /api/generate
//
// Le bridge relaie Ollama avec `requests(..., timeout=180)`. Le budget de
// premier octet, lui, valait 480 s pour la CASCADE ENTIERE de trois points
// d entree. Deux points d entree condamnes d avance pouvaient donc consommer
// 360 s des 480 s avant que le seul appel capable d aboutir soit meme tente.
//
// C est, pour la seizieme fois sur ce module, une porte qui condamne quelque
// chose qu elle n a jamais mesure: elle se nomme et se documente comme un
// budget « time-to-first-byte » d UN appel, et elle chronometre en realite le
// temps passe sur des appels DEJA morts. Puis elle coupe sans raison, si bien
// que l erreur ne nomme ni le modele, ni le point d entree, ni le budget, ni
// meme le fait qu il s agissait d un delai.
//
// Ce module corrige les deux moities:
//   - le budget est REARME a chaque tentative (il mesure ce qu il pretend);
//   - l abandon porte une raison nommee, distincte selon qu il vient du delai
//     ou d une annulation demandee par l appelant.
// ---------------------------------------------------------------------------

/** Signature stable du delai de premier octet, reconnue par le classifieur. */
export const FIRST_BYTE_TIMEOUT_MARK = 'premier octet absent'

/** Signature stable d une annulation demandee par l appelant (bouton Stop). */
export const CALLER_CANCEL_MARK = 'annulation demandee par l appelant'

export function buildFirstByteTimeoutMessage(args: {
  endpoint: string
  model: string
  budgetMs: number
}): string {
  const seconds = Math.round(args.budgetMs / 1000)
  return `Ollama: ${FIRST_BYTE_TIMEOUT_MARK} apres ${seconds}s sur ${args.endpoint} (modele ${args.model}) — delai depasse, aucun octet recu`
}

export function buildCallerCancelMessage(): string {
  return `Generation interrompue: ${CALLER_CANCEL_MARK}`
}

/** Le delai de premier octet a-t-il expire (par opposition a une annulation) ? */
export function isFirstByteTimeout(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '')
  return message.includes(FIRST_BYTE_TIMEOUT_MARK)
}

/** L appelant a-t-il demande l arret (bouton Stop) ? */
export function isCallerCancellation(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '')
  return message.includes(CALLER_CANCEL_MARK)
}

export type FirstByteWatchdog = {
  /** Signal a passer a `fetch`. Unique pour tout l appel: le flux reste annulable. */
  readonly signal: AbortSignal
  /**
   * (Re)arme le budget pour LA tentative qui commence. Chaque point d entree
   * repart avec son budget entier — une tentative morte ne mange plus celui de
   * la suivante.
   */
  arm: (endpoint: string) => void
  /** Desarme des que les en-tetes arrivent: le budget ne borne QUE le premier octet. */
  disarm: () => void
  /** Detache l ecoute du signal appelant. */
  dispose: () => void
  /** Point d entree sur lequel le delai a expire, sinon null. */
  timedOutOn: () => string | null
}

export function createFirstByteWatchdog(args: {
  model: string
  budgetMs: number
  callerSignal?: AbortSignal
  /** Injectables pour les tests — jamais fournis en production. */
  setTimeoutImpl?: (fn: () => void, ms: number) => unknown
  clearTimeoutImpl?: (handle: unknown) => void
}): FirstByteWatchdog {
  const setTimer = args.setTimeoutImpl ?? ((fn, ms) => globalThis.setTimeout(fn, ms))
  const clearTimer = args.clearTimeoutImpl ?? ((handle) => globalThis.clearTimeout(handle as never))

  const controller = new AbortController()
  let handle: unknown = null
  let expiredOn: string | null = null

  const disarm = () => {
    if (handle !== null) {
      clearTimer(handle)
      handle = null
    }
  }

  const onCallerAbort = () => {
    disarm()
    // L annulation de l appelant n est PAS un delai: elle porte sa propre
    // signature pour que la livraison ne la classe pas en panne machine.
    controller.abort(new DOMException(buildCallerCancelMessage(), 'AbortError'))
  }

  if (args.callerSignal) {
    if (args.callerSignal.aborted) onCallerAbort()
    else args.callerSignal.addEventListener('abort', onCallerAbort, { once: true })
  }

  return {
    signal: controller.signal,
    arm(endpoint: string) {
      disarm()
      if (controller.signal.aborted) return
      if (!Number.isFinite(args.budgetMs) || args.budgetMs <= 0) return
      handle = setTimer(() => {
        handle = null
        expiredOn = endpoint
        controller.abort(
          new DOMException(
            buildFirstByteTimeoutMessage({ endpoint, model: args.model, budgetMs: args.budgetMs }),
            'TimeoutError',
          ),
        )
      }, args.budgetMs)
    },
    disarm,
    dispose() {
      disarm()
      args.callerSignal?.removeEventListener('abort', onCallerAbort)
    },
    timedOutOn: () => expiredOn,
  }
}
