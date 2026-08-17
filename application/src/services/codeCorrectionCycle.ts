// ---------------------------------------------------------------------------
// codeCorrectionCycle — distinguer un defaut qui PERSISTE d un defaut qui
// REVIENT. Le second n est pas de la stagnation, c est un cycle.
// ---------------------------------------------------------------------------

import type { CorrectionPass } from './codeAutoCorrection.ts'

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

