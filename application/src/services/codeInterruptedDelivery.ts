// Livrer le travail deja produit quand le pipeline meurt en route.
//
// Mesure reelle (run 1041): 32 fichiers ecrits, puis « Ollama: toutes les
// tentatives epuisees (3). Modeles testes: qwen3-coder:30b [...] Derniere
// erreur: fetch failed » — la machine etait a 0 octet de RAM libre. Le
// gestionnaire fatal renvoyait `files: []`: tout le travail detruit par une
// panne reseau, sans qu aucune porte de qualite n ait eu son mot a dire.
//
// C est la regle des portes de qualite, prise dans l autre sens: un juge qui ne
// peut pas mesurer ne condamne pas, donc un generateur qui perd son modele ne
// detruit pas ses fichiers. Une panne d infrastructure ne dit RIEN sur la
// valeur du travail deja produit — le jeter est une erreur de categorie, et
// c est la plus chere mesuree sur ce module.

import { isInfrastructureFailureMessage } from './codeInfrastructureFailure.ts'
import type { CodeFile, CodeOrchestrationResult } from './codeOrchestratorTypes.ts'
import type { CodeIntent } from './codeIntent.ts'
import type { RecoveryEvent } from './ollamaResilience'

export type InterruptedDelivery = {
  cause: string
  infrastructure: boolean
  notes: string
  phaseMessage: string
}

/**
 * Prepare la livraison d un travail interrompu. Le texte doit etre explicite
 * sur un point: l interruption n est pas un verdict de qualite.
 */
export function buildInterruptedDelivery(
  message: string,
  files: CodeFile[],
  previousNotes: string,
): InterruptedDelivery {
  const infrastructure = isInfrastructureFailureMessage(message)
  const cause = infrastructure ? 'panne d infrastructure' : 'erreur du pipeline'
  const notes = [
    previousNotes,
    '',
    `INTERROMPU — ${cause}: ${message}`,
    infrastructure
      ? 'Le travail ci-dessus a ete produit AVANT la panne et est livre tel quel. Il n a pas ete valide jusqu au bout: aucune conclusion sur sa qualite ne doit etre tiree de cette interruption.'
      : 'Le travail ci-dessus a ete produit avant l erreur et est livre tel quel, sans validation complete.',
  ].filter(Boolean).join('\n')
  return {
    cause,
    infrastructure,
    notes,
    phaseMessage: `Interrompu (${cause}) — ${files.length} fichier(s) preserves`,
  }
}

/** Le resultat complet a renvoyer quand on preserve un travail interrompu. */
export function buildInterruptedResult(
  delivery: InterruptedDelivery,
  files: CodeFile[],
  intent: CodeIntent,
  recoveryEvents: RecoveryEvent[],
): CodeOrchestrationResult {
  return {
    files,
    notes: delivery.notes,
    sandboxResult: null,
    intent,
    preflightReport: null,
    correctionLog: [],
    phase: 'interrupted',
    architecturePlan: null,
    totalAttempts: 0,
    finalScore: 0,
    recoveryEvents,
    followUp: null,
  }
}
