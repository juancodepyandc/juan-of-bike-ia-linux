import type { ErrorCategory } from './codeAutoCorrection.ts'

// ---------------------------------------------------------------------------
// Instruction builders per level
// ---------------------------------------------------------------------------

export function buildQuickFixInstructions(categories: ErrorCategory[]): string {
  const lines: string[] = ['Correction rapide des erreurs detectees:']

  if (categories.includes('syntax')) {
    lines.push('- Corrige les erreurs de syntaxe (parentheses, accolades, points-virgules)')
  }
  if (categories.includes('import_missing')) {
    lines.push('- Corrige les imports manquants ou mal orthographies')
    lines.push('- Verifie que tous les modules importes existent dans le projet')
  }
  if (categories.includes('type_error')) {
    lines.push('- Corrige les erreurs de type (types manquants, incompatibles)')
    lines.push('- Ajoute les declarations de type necessaires')
  }

  return lines.join('\n')
}

export function buildTargetedRepairInstructions(categories: ErrorCategory[]): string {
  const lines: string[] = ['Reparation ciblee des erreurs:']

  if (categories.includes('dependency_missing')) {
    lines.push('- Verifie que package.json / requirements.txt contient toutes les dependances')
    lines.push('- Ajoute les dependances manquantes avec les versions correctes')
  }
  if (categories.includes('config_error')) {
    lines.push('- Corrige les fichiers de configuration invalides, surtout package.json, tsconfig.json et les manifests JSON')
    lines.push('- Les fichiers JSON doivent etre du JSON pur: aucun backtick markdown, aucun commentaire, aucune explication autour')
  }
  if (categories.includes('runtime_unavailable')) {
    lines.push('- Le probleme principal est un runtime ou binaire absent: ne refactorise pas le code pour masquer ce symptome')
    lines.push('- Corrige seulement les scripts ou commandes declares si une incoherence evidente existe')
  }
  if (categories.includes('config_error')) {
    lines.push('- Verifie la configuration (tsconfig, vite.config, webpack, etc.)')
    lines.push('- Corrige les options incompatibles')
  }
  if (categories.includes('runtime_crash')) {
    lines.push('- Corrige les erreurs de reference (variables non definies)')
    lines.push('- Ajoute les verifications null/undefined necessaires')
  }

  lines.push('- Ne touche PAS aux fichiers qui fonctionnent deja')

  return lines.join('\n')
}

export function buildPartialRewriteInstructions(categories: ErrorCategory[]): string {
  const lines: string[] = [
    'Les corrections simples n\'ont pas suffi.',
    'Reecris les fichiers problematiques en profondeur:',
  ]

  if (categories.includes('build_failure')) {
    lines.push('- Revois completement la configuration de build')
    lines.push('- Verifie la compatibilite des versions de dependances')
  }
  if (categories.includes('test_failure')) {
    lines.push('- Corrige la logique metier pour faire passer les tests')
    lines.push('- Ne modifie les tests que pour une erreur de syntaxe ou fixture manifestement incoherente, jamais pour abaisser le contrat')
  }
  if (categories.includes('runtime_crash')) {
    lines.push('- Refactorise la logique qui crash')
    lines.push('- Utilise des patterns plus defensifs')
  }

  lines.push('- Utilise les solutions trouvees en ligne si disponibles')

  return lines.join('\n')
}
