// Retour d experience du harnais anti-regression vers le CORRECTEUR.
//
// Mesure reelle (run 960, brief "Brulerie Nomade"): cinq passes de correction
// consecutives refusees par le garde anti-regression, rollback a chaque fois,
// et le modele n en a JAMAIS rien su. `buildCorrectionMessages` ne recevait que
// la sortie du sandbox — le verdict du garde partait dans le journal de l UI,
// jamais dans le prompt. Le modele reproposait donc exactement le meme patch,
// refuse a l identique, jusqu a la detection de boucle infinie.
//
// Ce module transforme le verdict du garde en CONSIGNE, et resserre la portee
// de la correction quand le refus se repete: un patch qui ne touche que les
// fichiers fautifs ne peut structurellement pas supprimer une capacite ailleurs.

import type { CodeFile } from './codeOrchestratorTypes.ts'

/** Nombre de refus consecutifs a partir duquel on resserre la portee. */
export const NARROW_SCOPE_AFTER_REJECTIONS = 2

function normalize(path: string): string {
  return path.replace(/\\/g, '/').trim()
}

/**
 * Fichiers explicitement nommes par les sorties d echec.
 *
 * On ne devine pas: un fichier n est retenu que si son chemin (ou son nom de
 * base, quand il est discriminant) apparait litteralement dans une sortie en
 * echec. Sert a resserrer la portee d une correction sur les seuls fautifs.
 */
export function filesImplicatedByFailures(files: CodeFile[], failingOutputs: string[]): string[] {
  const haystack = failingOutputs.join('\n')
  if (!haystack.trim()) return []

  const implicated: string[] = []
  for (const file of files) {
    const path = normalize(file.name)
    if (!path) continue
    if (haystack.includes(path)) {
      implicated.push(file.name)
      continue
    }
    const base = path.split('/').pop() ?? ''
    // Un nom de base ne compte que s il est unique dans le projet, sinon
    // "index.ts" impliquerait dix fichiers pour une seule erreur.
    if (base.length >= 5 && haystack.includes(base)) {
      const sameBase = files.filter((other) => (normalize(other.name).split('/').pop() ?? '') === base)
      if (sameBase.length === 1) implicated.push(file.name)
    }
  }
  return [...new Set(implicated)]
}

/**
 * Bloc de consigne injecte dans le prompt de correction suivant.
 *
 * Retourne une chaine vide quand aucun refus n a eu lieu: on ne bruite pas un
 * prompt qui n a rien a apprendre.
 */
export function buildRegressionFeedbackBlock({
  guardReport,
  consecutiveRejections,
  implicatedFiles,
}: {
  guardReport: string | null
  consecutiveRejections: number
  implicatedFiles: string[]
}): string {
  if (!guardReport || consecutiveRejections <= 0) return ''

  const lines = [
    '## TA CORRECTION PRECEDENTE A ETE REFUSEE ET ANNULEE',
    '',
    `Refus consecutifs: ${consecutiveRejections}. Le harnais anti-regression a rejete ta`,
    'derniere proposition parce qu elle FAISAIT DISPARAITRE des capacites deja livrees.',
    'Le projet a ete restaure a son etat precedent: repartir sur la meme idee la fera',
    'refuser une nouvelle fois.',
    '',
    'Verdict exact du garde:',
    guardReport.trim(),
    '',
    'Regles pour cette passe:',
    '- Reprends TOUT ce que le garde liste ci-dessus: chaque fichier, export, script,',
    '  endpoint ou test cite doit exister a l identique dans ta reponse.',
    '- Ne renomme rien, ne fusionne rien, ne "simplifie" rien pour faire passer la',
    '  validation. La validation ne mesure pas la taille du projet.',
  ]

  if (consecutiveRejections >= NARROW_SCOPE_AFTER_REJECTIONS) {
    lines.push(
      '',
      '## PORTEE RESSERREE (obligatoire a partir de ce refus)',
      '',
      'Repondre avec le projet entier a echoue plusieurs fois de suite. Cette fois:',
    )
    if (implicatedFiles.length > 0) {
      lines.push(
        `- Ne renvoie QUE ces fichiers, complets, rien d autre: ${implicatedFiles.map((name) => `\`${name}\``).join(', ')}.`,
      )
    } else {
      lines.push(
        '- Ne renvoie QUE les fichiers cites par les erreurs ci-dessus, complets, rien d autre.',
      )
    }
    lines.push(
      '- Les fichiers absents de ta reponse seront CONSERVES tels quels: ne les recopie pas,',
      '  ne les resume pas, ne les remplace pas par un commentaire.',
      '- Un fichier que tu renvoies doit etre integral et compilable seul: pas d ellipse,',
      '  pas de "... reste inchange ...".',
    )
  }

  return lines.join('\n')
}
