import type { CodeFile, FollowUpKind } from './codeOrchestrator.ts'
import {
  buildCodeIncrementalPatchScope,
  formatCodeIncrementalPatchScope,
} from './codeIncrementalPatchScope.ts'

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '').toLowerCase()
}

function capContent(content: string, max: number) {
  if (content.length <= max) return content
  return `${content.slice(0, max)}\n...[fichier tronque: ${content.length} chars — le reste est conserve, NE le supprime pas]`
}

export function buildExistingProjectPatchContext(args: {
  prompt: string
  existingFiles: CodeFile[]
  pivotKind?: FollowUpKind
  maxChars?: number
}) {
  const scope = buildCodeIncrementalPatchScope({
    prompt: args.prompt,
    files: args.existingFiles,
    maxTargetFiles: 8,
  })
  const targetSet = new Set(scope.targetFiles.map(normalizePath))
  const selectedFiles = scope.targetFiles.length > 0
    ? args.existingFiles.filter((file) => targetSet.has(normalizePath(file.name)))
    : args.existingFiles.slice(0, 8)
  let fileBudget = args.maxChars ?? 13_000
  const shownTargets: string[] = []
  const fileBlocks: string[] = []
  for (const file of selectedFiles) {
    if (fileBudget <= 400) break
    const perCap = Math.min(file.content.length, Math.max(2000, fileBudget))
    const body = capContent(file.content, perCap)
    fileBlocks.push(`--- FICHIER CIBLE: ${file.name} ---\n\`\`\`${file.language}\n${body}\n\`\`\``)
    shownTargets.push(file.name)
    fileBudget -= body.length
  }
  const shownSet = new Set(shownTargets.map(normalizePath))
  const hiddenTargets = scope.targetFiles.filter((path) => !shownSet.has(normalizePath(path))).length

  return [
    '## CONTEXTE DU PROJET EXISTANT (mode suite de conversation)',
    'Ce projet a deja ete genere. La nouvelle instruction utilisateur est une modification / ajout / retrait, PAS une reconstruction.',
    args.pivotKind === 'pivot_feature'
      ? 'Mode: evolution majeure d une feature existante. Garde la meme stack, mais autorise des reecritures consequentes des fichiers concernes.'
      : '',
    '',
    '## PORTEE PATCH INCREMENTAL WS5',
    formatCodeIncrementalPatchScope(scope),
    '',
    '### REGLES DE MODIFICATION',
    '- Utilise prioritairement apply_patch sur les fichiers cibles.',
    '- Ne touche QUE ce qui est demande. Ne refactore rien qui fonctionne deja.',
    '- Si un fichier ne change pas, NE le retourne PAS — il sera conserve automatiquement.',
    '- Conserve palette, typographie, structure, conventions et tout contenu non vise par la demande.',
    '- Les fichiers proteges et les fichiers non montres restent en place et doivent rester identiques.',
    '',
    '### FICHIERS CIBLES A REPRENDRE INTEGRALEMENT QUAND TU LES MODIFIES',
    ...fileBlocks,
    hiddenTargets > 0 ? `... ${hiddenTargets} fichier(s) cible(s) supplementaire(s) non montre(s) faute de budget.` : '',
    scope.protectedFiles.length > 0
      ? `${scope.protectedFiles.length} fichier(s) protege(s) non inclus dans le contexte complet — NE les modifie pas.`
      : '',
    'IMPORTANT: Tu es en mode SUITE, pas en mode creation from scratch.',
  ].filter(Boolean).join('\n\n')
}
