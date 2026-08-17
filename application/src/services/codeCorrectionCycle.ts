// ---------------------------------------------------------------------------
// codeCorrectionCycle — distinguer un defaut qui PERSISTE d un defaut qui
// REVIENT. Le second n est pas de la stagnation, c est un cycle.
// ---------------------------------------------------------------------------

import type { CorrectionPass, CorrectionStrategy } from './codeAutoCorrection.ts'

/**
 * Signature stable d une erreur de compilation: fichier + code TS + symbole.
 * Les numeros de ligne bougent a chaque reecriture, pas le defaut.
 */
export function compilerSignatures(pass: CorrectionPass): Set<string> {
  const text = (pass.errors ?? []).join('\n')
  const found = new Set<string>()
  for (const m of text.matchAll(/(\S+?)\(\d+,\d+\): error (TS\d+): ([^\n]{0,70})/g)) {
    found.add(`${m[1]}|${m[2]}|${m[3].replace(/\s+/g, ' ').trim()}`)
  }
  return found
}

/**
 * La boucle TOURNE-T-ELLE EN ROND ?
 *
 * Run 1171, neuf passes, score 20 -> 65 -> 68 -> 72 -> 73. Le detecteur
 * existant cherche la MEME erreur six fois de suite; ici elle alternait:
 *
 *   passe 3  AdminPage.tsx TS2339 Property 'clearOrders' does not exist on
 *                                 type 'OrderState'   (score 68)
 *   passe 4  — absente
 *   passe 5  AdminPage.tsx TS2304 Cannot find name 'Order'   (score 68)
 *
 * Le modele alignait l usage sur le type, puis le type sur l usage. Comme le
 * score global montait, ni la stagnation ni la boucle infinie ne se declenchaient
 * — et le run est alle au plafond dur en payant quatre passes pour rien.
 *
 * Un defaut qui DISPARAIT puis REVIENT sans que le score ait progresse depuis sa
 * derniere apparition n est pas de la stagnation: c est un cycle. Le meme
 * traitement, retente, redonnera le meme aller-retour.
 */
export function detectCorrectionCycle(correctionLog: CorrectionPass[]): string | null {
  if (correctionLog.length < 4) return null
  const perPass = correctionLog.map(compilerSignatures)

  for (const signature of perPass[perPass.length - 1]) {
    const seen = perPass
      .map((set, index) => (set.has(signature) ? index : -1))
      .filter((index) => index >= 0)
    if (seen.length < 2) continue
    const previous = seen[seen.length - 2]
    const latest = seen[seen.length - 1]
    // Il faut un VRAI trou: revenue apres avoir disparu.
    if (latest - previous < 2) continue
    // …et aucun terrain gagne entre les deux apparitions.
    if (correctionLog[latest].score > correctionLog[previous].score) continue
    return signature
  }
  return null
}


/**
 * Un cycle detecte doit CHANGER LA NATURE de la strategie, pas seulement
 * arreter la boucle.
 *
 * L etat precedent s arretait net au premier cycle. C etait deja mieux que de
 * payer quatre passes d aller-retour, mais cela laissait le contrat incoherent
 * — le run se terminait sur le defaut qu il venait de nommer. Or la reponse
 * existe et elle est deterministe: donner a la passe la FERMETURE du contrat
 * (definition, declarations concurrentes, consommateurs) pour qu elle tranche
 * une fois au lieu d osciller.
 *
 * On accorde donc exactement UNE passe de plus apres la detection. Si le cycle
 * est toujours la ensuite, la fermeture n a pas suffi et s obstiner ne paiera
 * pas davantage: on arrete.
 */
export const CYCLE_CLOSURE_GRACE = 1

/** Index de la passe a laquelle le cycle devient detectable. */
export function cycleFirstDetectedIndex(correctionLog: CorrectionPass[]): number | null {
  for (let end = 4; end <= correctionLog.length; end += 1) {
    if (detectCorrectionCycle(correctionLog.slice(0, end))) return end - 1
  }
  return null
}

/**
 * Reste-t-il une passe de grace pour tenter la reparation de contrat ?
 *
 * `false` quand aucun cycle n est en cours (rien a accorder) ET quand la grace
 * est epuisee — l appelant distingue les deux via `detectCorrectionCycle`.
 */
export function cycleGraceRemaining(correctionLog: CorrectionPass[]): boolean {
  const first = cycleFirstDetectedIndex(correctionLog)
  if (first === null) return false
  return correctionLog.length - 1 - first < CYCLE_CLOSURE_GRACE
}

/**
 * Un cycle mesure CHANGE la consigne, il ne se contente pas d arreter la boucle.
 *
 * Sans cela, la passe de grace accordee apres detection repeterait exactement le
 * traitement qui vient d osciller — et redonnerait le meme aller-retour. La
 * consigne interdit donc explicitement le va-et-vient et impose de trancher
 * l ambiguite, ce qu aucune passe precedente n avait demande.
 */
export function withCycleDirective(strategy: CorrectionStrategy, correctionLog: CorrectionPass[]): CorrectionStrategy {
  const signature = detectCorrectionCycle(correctionLog)
  if (!signature) return strategy
  return {
    ...strategy,
    instructions: [
      strategy.instructions,
      '',
      '## CYCLE MESURE — NE REPETE PAS LE TRAITEMENT PRECEDENT',
      `Defaut qui disparait puis revient sans gain de score: ${signature}`,
      'Les passes precedentes ont aligne l usage sur le type, puis le type sur l usage.',
      'Corriger un seul cote RECREE le defaut de l autre.',
      'Traite la definition ET tous ses consommateurs comme UNE SEULE unite.',
      'Si un symbole est declare dans plusieurs modules, choisis UNE declaration',
      'faisant autorite, supprime les autres, redirige les consommateurs, et dis',
      'laquelle tu as retenue.',
    ].join('\n'),
  }
}
