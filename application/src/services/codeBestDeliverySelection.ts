// Choix du MEILLEUR etat livrable entre l existant et une regeneration.
//
// Mesure reelle (run 960): apres 2 h de generation, l audit de rendu note la
// livraison 44/100, sous le seuil. Une passe esthetique repart alors du debut et
// son resultat REMPLACE le livrable — sans aucune comparaison. Le second etat
// etait mesure (`renderAndScoreAesthetics` etait rappele, le score journalise),
// puis la mesure etait jetee. Le run s est termine sur un livrable plus pauvre
// que celui qu il avait deja: mesurer sans decider, c est ne pas mesurer.
//
// Regle unique: on ne remplace un etat livrable que par un etat PROUVE meilleur.

import { inspectCodePatchRegression } from './codeRegressionGuard.ts'
import type { CodeFile } from './codeOrchestratorTypes.ts'

export type DeliveryCandidate = {
  files: CodeFile[]
  /** Score de rendu mesure (0..100), ou null si non mesurable ici. */
  visualScore: number | null
  /** Verdict de composition (chevauchements, vides, emoji), ou null. */
  compositionOk: boolean | null
  /** Le pipeline qui a produit cet etat s est-il termine en erreur ? */
  pipelineFailed: boolean
}

export type DeliverySelection = {
  adopt: boolean
  reason: string
}

function describeScore(score: number | null): string {
  return score === null ? 'non mesure' : `${score}/100`
}

/**
 * Faut-il adopter `candidate` a la place de `incumbent` ?
 *
 * Le doute profite TOUJOURS a l etat deja livrable: une regeneration qui n a pas
 * fait la preuve d etre meilleure est du travail jete, pas du progres.
 */
export function pickBestDelivery(
  incumbent: DeliveryCandidate,
  candidate: DeliveryCandidate,
): DeliverySelection {
  if (candidate.files.length === 0) {
    return { adopt: false, reason: 'regeneration vide — livrable precedent conserve' }
  }

  if (candidate.pipelineFailed && !incumbent.pipelineFailed) {
    return {
      adopt: false,
      reason: 'la regeneration s est terminee en erreur alors que le livrable precedent tenait — livrable precedent conserve',
    }
  }

  // Une regeneration qui fait disparaitre une capacite (page, route, script,
  // export, document HTML) n est pas une amelioration, meme mieux notee: le
  // brief demandait AUSSI ce qu elle vient de supprimer.
  const regression = inspectCodePatchRegression(incumbent.files, candidate.files)
  if (!regression.ok) {
    const kinds = [...new Set(regression.violations.map((violation) => violation.kind))].join(', ')
    return {
      adopt: false,
      reason: `la regeneration perd des capacites (${kinds}) — livrable precedent conserve`,
    }
  }

  if (incumbent.visualScore !== null && candidate.visualScore === null) {
    return {
      adopt: false,
      reason: `rendu de la regeneration non mesurable (precedent ${describeScore(incumbent.visualScore)}) — livrable precedent conserve`,
    }
  }

  if (incumbent.visualScore !== null && candidate.visualScore !== null) {
    // Run 1061: le livrable etait note 100/100 en style et ECHOUAIT la
    // composition (emoji en position d icone). Une passe qui repare exactement
    // ce defaut ne peut pas faire monter un score deja au plafond — elle etait
    // donc condamnee par la seule comparaison de score, quoi qu elle repare.
    // Reparer la porte qui echouait EST le progres; le score sert alors a
    // verifier qu on n a rien casse en chemin, pas a prouver une hausse.
    if (incumbent.compositionOk === false && candidate.compositionOk === true
      && candidate.visualScore >= incumbent.visualScore) {
      return {
        adopt: true,
        reason: `composition reparee sans perte de rendu (${describeScore(candidate.visualScore)} contre ${describeScore(incumbent.visualScore)} avant) — regeneration adoptee`,
      }
    }
    if (candidate.visualScore <= incumbent.visualScore) {
      return {
        adopt: false,
        reason: `rendu ${describeScore(candidate.visualScore)} contre ${describeScore(incumbent.visualScore)} avant — livrable precedent conserve`,
      }
    }
    if (incumbent.compositionOk === true && candidate.compositionOk === false) {
      return {
        adopt: false,
        reason: `rendu mieux note (${describeScore(candidate.visualScore)}) mais composition cassee — livrable precedent conserve`,
      }
    }
    return {
      adopt: true,
      reason: `rendu ${describeScore(candidate.visualScore)} contre ${describeScore(incumbent.visualScore)} avant — regeneration adoptee`,
    }
  }

  return {
    adopt: true,
    reason: `aucun rendu mesure sur le livrable precedent — regeneration adoptee (${describeScore(candidate.visualScore)})`,
  }
}
