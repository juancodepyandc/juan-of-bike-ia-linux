// ---------------------------------------------------------------------------
// codeEscapedNewlines — un fichier entier sur UNE ligne, avec des `\n` litteraux.
//
// MESURE (run v130, capturee par le nouvel archivage d etats intermediaires —
// invisible avant lui):
//
//   Footer.tsx(1,107): error TS1127: Invalid character.
//   Footer.tsx(1,120): error TS1005: ';' expected.
//   Footer.tsx(1,149): error TS1127: Invalid character.
//
// Toutes les erreurs en LIGNE 1, a des colonnes croissantes. Le contenu livre:
//
//   import React from 'react'\n\nconst Footer: React.FC = () => {\n  return (
//
// Les `\n` sont deux caracteres — antislash puis n — pas des sauts de ligne.
// La sequence d echappement n a jamais ete decodee, le fichier tient donc sur
// une seule ligne et l antislash est un caractere invalide en TypeScript.
//
// Le modele n y peut rien: son texte etait juste. C est le transport qui a
// perdu le decodage. Une passe de modele sur ce fichier reecrirait du code
// correct... qui repasserait par le meme transport.
//
// Correction DETERMINISTE, et garde volontairement etroite: on ne decode que
// si le fichier n a AUCUN vrai saut de ligne alors qu il contient plusieurs
// `\n` litteraux. Un fichier normal contenant `join('\n')` a, lui, de vrais
// sauts de ligne — il n est jamais touche.
// ---------------------------------------------------------------------------

/** Fichiers dont les echappements sont LEGITIMES sur une seule ligne. */
const STRUCTURED = /\.(json|jsonc|lock|md|txt|csv|ya?ml)$/i

const LITERAL_NEWLINE = /\\r\\n|\\n/g

export function hasUndecodedNewlines(filename: string, content: string): boolean {
  if (STRUCTURED.test(filename)) return false
  if (content.length < 120) return false
  // Le fichier tient-il sur une seule ligne alors qu il devrait en avoir ?
  if (content.includes('\n')) return false
  const matches = content.match(LITERAL_NEWLINE)
  return (matches?.length ?? 0) >= 2
}

/**
 * Decode les sauts de ligne et tabulations echappes. N est appele que lorsque
 * `hasUndecodedNewlines` a etabli qu il n y a aucun vrai saut de ligne: le
 * risque de toucher une chaine legitime est donc nul par construction.
 */
export function decodeEscapedNewlines(content: string): string {
  return content
    .replace(/\\r\\n/g, '\n')
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '  ')
    .replace(/\\r/g, '')
}

export function repairEscapedNewlines(filename: string, content: string): { content: string; repaired: boolean } {
  if (!hasUndecodedNewlines(filename, content)) return { content, repaired: false }
  return { content: decodeEscapedNewlines(content), repaired: true }
}
