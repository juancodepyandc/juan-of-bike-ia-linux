// ---------------------------------------------------------------------------
// codeCorrectionPromptBudget — laisser au modele la place de REPONDRE.
//
// Run 1141, mesure sur le prompt de correction reellement construit a partir des
// 35 fichiers livres:
//
//   system        5 665 caracteres  (~1 416 jetons)
//   user         92 501 caracteres  (~23 125 jetons)
//   TOTAL        98 166 caracteres  (~24 542 jetons)
//   num_ctx                          24 576 jetons
//   place restante pour la REPONSE        34 jetons
//
// Trente-quatre jetons. On demandait a un modele de reecrire des fichiers dans
// une fenetre ou il ne pouvait litteralement rien ecrire. D ou les appels qui ne
// finissent jamais: la passe 4 a consomme ses vingt minutes entieres, la passe 2
// onze minutes — ce n etait pas une panne reseau, c etait un prompt qui ne
// laissait aucune place a la sortie.
//
// La cause est la meme que partout ailleurs dans cette serie, sous une autre
// forme: on envoyait TOUT le projet a chaque passe, sans jamais mesurer ce que
// cela laissait au modele.
//
// Regle: le contexte se partage. On reserve d abord la sortie, on remplit
// ensuite — en commencant par les fichiers que les erreurs DESIGNENT.
// ---------------------------------------------------------------------------

import type { CodeFile } from './codeOrchestratorTypes.ts'

/** ~4 caracteres par jeton: suffisant pour budgeter, jamais pour facturer. */
export const CHARS_PER_TOKEN = 4

/**
 * Jetons reserves a la REPONSE. Une passe de correction doit pouvoir reecrire
 * plusieurs fichiers complets; en dessous de ce seuil elle est condamnee a
 * produire du tronque, donc a echouer et a relancer une passe.
 */
export const RESERVED_OUTPUT_TOKENS = 8_000

/** Budget de caracteres pour la section fichiers, une fois la sortie reservee. */
export function correctionFileBudgetChars(args: {
  contextTokens: number
  otherPromptChars: number
}): number {
  const promptTokens = Math.max(0, args.contextTokens - RESERVED_OUTPUT_TOKENS)
  return Math.max(4_000, promptTokens * CHARS_PER_TOKEN - args.otherPromptChars)
}

function normalize(path: string) {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '').toLowerCase()
}

/** Fichiers NOMMES par les sorties d erreur: la priorite absolue. */
export function filesNamedByFailures(files: CodeFile[], failingOutputs: readonly string[]): Set<string> {
  const named = new Set<string>()
  const text = failingOutputs.join('\n')
  for (const file of files) {
    const base = normalize(file.name)
    const leaf = base.split('/').pop() ?? base
    if (text.toLowerCase().includes(base) || (leaf.length > 4 && text.toLowerCase().includes(leaf))) {
      named.add(base)
    }
  }
  return named
}

export type CorrectionFileSelection = {
  included: CodeFile[]
  omitted: string[]
}

/**
 * Choisit les fichiers a joindre au prompt. Les fichiers designes par les
 * erreurs passent devant; le reste complete tant qu il y a de la place. On ne
 * tronque JAMAIS un fichier a moitie: un fichier coupe est un fichier que le
 * modele reecrira faux.
 */
export function selectFilesForCorrectionPrompt(args: {
  files: CodeFile[]
  failingOutputs: readonly string[]
  budgetChars: number
}): CorrectionFileSelection {
  const named = filesNamedByFailures(args.files, args.failingOutputs)
  const ranked = [...args.files].sort((a, b) => {
    const byNamed = Number(named.has(normalize(b.name))) - Number(named.has(normalize(a.name)))
    if (byNamed !== 0) return byNamed
    return a.content.length - b.content.length
  })

  const included: CodeFile[] = []
  const omitted: string[] = []
  let used = 0
  for (const file of ranked) {
    const cost = file.content.length + file.name.length + 40
    if (used + cost > args.budgetChars && included.length > 0) {
      omitted.push(file.name)
      continue
    }
    included.push(file)
    used += cost
  }
  return { included, omitted }
}

/**
 * Les fichiers omis doivent etre NOMMES: sans cela le modele croit qu ils n
 * existent pas et les recree — c est-a-dire qu il ecrase le projet. C est
 * exactement la regression que le garde anti-regression passait son temps a
 * refuser.
 */
export function describeOmittedFiles(omitted: readonly string[]): string {
  if (omitted.length === 0) return ''
  return [
    '',
    `## ${omitted.length} FICHIER(S) DU PROJET NON JOINTS (place insuffisante)`,
    'Ils EXISTENT et sont corrects. Ne les recree pas, ne les reecris pas, ne les supprime pas:',
    omitted.slice(0, 40).map((path) => `- ${path}`).join('\n'),
    omitted.length > 40 ? `- ... et ${omitted.length - 40} autre(s)` : '',
  ].filter(Boolean).join('\n')
}
