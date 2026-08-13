// ---------------------------------------------------------------------------
// codeTargetedRepairPass — reparer UN defaut constate a l ecran, en editant les
// fichiers qui le portent. Pas une regeneration, pas un nouveau plan
// d architecture, pas une nouvelle classification d intention.
//
// Ce que remplace ce module (run 1061): la passe dite « ciblee » appelait
// `orchestrateCodeGeneration` en entier. Elle repartait donc d une page blanche
// avec, pour tout heritage, les fichiers passes en contexte — et rendait un
// projet AUTRE, amputé de fichiers, de scripts et d exports. Corriger des emoji
// coutait alors un projet.
//
// Ici la passe PROPOSE un patch sur une portee bornee, et la fusion
// (applyTargetedRepair) est structurellement incapable de supprimer un fichier.
// La verification de rendu qui suit reste seule juge de l adoption.
// ---------------------------------------------------------------------------

import type { OllamaMessage } from '../types/app.ts'
import { parseCodeFiles } from './codeGeneratedFileParser.ts'
import { buildStructuredEmissionInstructions } from './codeProjectEmission.ts'
import {
  applyTargetedRepair,
  buildTargetedRepairScope,
  type TargetedRepairApplication,
  type TargetedRepairScope,
} from './codeTargetedRepairScope.ts'
import {
  CODE_EXPERT_CONTEXT_TOKENS,
  CORRECTION_FIRST_BYTE_TIMEOUT_MS,
  CORRECTION_TIMEOUT_MS,
} from './codePipelineRuntime.ts'
import type { CodeFile } from './codeOrchestratorTypes.ts'

/** Deux tentatives au plus: meme modele deja resident, aucun echange de VRAM. */
export const MAX_TARGETED_REPAIR_ATTEMPTS = 2

export type TargetedRepairResult = {
  files: CodeFile[]
  changed: boolean
  attempts: number
  patched: string[]
  added: string[]
  rejected: Array<{ path: string; reason: string }>
  summary: string
}

export function buildTargetedRepairMessages(args: {
  prompt: string
  critique: string
  scope: TargetedRepairScope
  previousRejection?: string
}): OllamaMessage[] {
  const targetList = args.scope.targets
    .map((file) => `- ${file.name} (motif: ${args.scope.reasonsByPath[file.name]?.join(', ') || 'portee'})`)
    .join('\n')

  const system = [
    'Tu es un ingenieur de maintenance. Tu recois un projet DEJA LIVRABLE et un',
    'defaut precis constate a l ecran. Tu corriges CE defaut, rien d autre.',
    '',
    'REGLES ABSOLUES:',
    '1. Tu ne rends QUE les fichiers de la liste ci-dessous, entiers, corriges.',
    '2. Tu ne supprimes aucun fichier, aucune route, aucun export, aucun script.',
    '3. Tu ne changes ni la stack, ni l architecture, ni les noms de composants.',
    '4. Tout fichier absent de ta reponse est conserve tel quel: ne le reecris pas',
    '   « pour la coherence », ce serait une regeneration deguisee.',
    '5. Tu ne renommes rien: le chemin que tu rends doit etre IDENTIQUE a l original.',
    '',
    buildStructuredEmissionInstructions(),
  ].join('\n')

  const user = [
    `## DEMANDE D ORIGINE (contexte, deja satisfaite)\n${args.prompt.slice(0, 1200)}`,
    '',
    `## DEFAUT A CORRIGER\n${args.critique}`,
    '',
    `## FICHIERS QUE TU AS LE DROIT DE REECRIRE (${args.scope.targets.length})\n${targetList}`,
    '',
    args.scope.protectedPaths.length > 0
      ? `## FICHIERS INTOUCHABLES (${args.scope.protectedPaths.length}) — toute version que tu en rendrais sera JETEE\n${args.scope.protectedPaths.slice(0, 40).map((p) => `- ${p}`).join('\n')}`
      : '',
    '',
    args.previousRejection ? `## TA TENTATIVE PRECEDENTE A ETE REFUSEE\n${args.previousRejection}` : '',
    '',
    '## CONTENU ACTUEL DES FICHIERS A CORRIGER',
    ...args.scope.targets.map((file) => `\n### ${file.name}\n${file.content}`),
  ].filter(Boolean).join('\n')

  return [
    { role: 'system', content: system },
    { role: 'user', content: user },
  ]
}

function describe(application: TargetedRepairApplication): string {
  const parts: string[] = []
  if (application.patched.length > 0) parts.push(`${application.patched.length} fichier(s) corrige(s): ${application.patched.join(', ')}`)
  if (application.added.length > 0) parts.push(`${application.added.length} ajout(s): ${application.added.join(', ')}`)
  if (application.rejected.length > 0) {
    parts.push(`${application.rejected.length} propositions refusees (${[...new Set(application.rejected.map((r) => r.reason))].join('; ')})`)
  }
  return parts.join(' — ') || 'aucune modification'
}

/**
 * Execute la passe ciblee. Ne leve jamais: une reparation impossible rend les
 * fichiers d origine, inchanges (`changed: false`). Le doute profite au
 * livrable, comme partout ailleurs dans ce module.
 */
export async function runTargetedRepairPass(args: {
  prompt: string
  files: CodeFile[]
  failedChecks: string[]
  critique: string
  model: string
  /** Chemins designes par une preuve (trace runtime resolue). */
  evidencePaths?: string[]
  setPhase?: (detail: string, progress: number) => void
  signal?: AbortSignal
  maxAttempts?: number
  /** Injectable pour les tests: renvoie la reponse brute du modele. */
  generate?: (messages: OllamaMessage[]) => Promise<string>
}): Promise<TargetedRepairResult> {
  const maxAttempts = args.maxAttempts ?? MAX_TARGETED_REPAIR_ATTEMPTS
  const scope = buildTargetedRepairScope({
    files: args.files,
    failedChecks: args.failedChecks,
    evidencePaths: args.evidencePaths,
  })

  if (scope.targets.length === 0) {
    return {
      files: args.files, changed: false, attempts: 0, patched: [], added: [], rejected: [],
      summary: `aucun fichier ne porte le defaut (${args.failedChecks.join(', ')}) — rien a patcher`,
    }
  }

  const generate = args.generate ?? (async (messages: OllamaMessage[]) => {
    const { resilientOllamaChat } = await import('./ollamaResilience.ts')
    const response = await resilientOllamaChat(args.model, messages, 0.05, {
      timeoutMs: CORRECTION_TIMEOUT_MS,
      firstByteTimeoutMs: CORRECTION_FIRST_BYTE_TIMEOUT_MS,
      signal: args.signal,
      num_ctx: CODE_EXPERT_CONTEXT_TOKENS,
      neverMemorySkip: true,
    })
    return response?.message?.content?.trim() || ''
  })

  let previousRejection: string | undefined
  let lastSummary = 'le modele n a produit aucun patch exploitable'

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    args.setPhase?.(`Passe ciblee ${attempt}/${maxAttempts} — ${scope.targets.length} fichier(s) sur ${args.files.length}...`, 96)
    const raw = await generate(buildTargetedRepairMessages({
      prompt: args.prompt, critique: args.critique, scope, previousRejection,
    }))
    const produced = parseCodeFiles(raw)
    if (produced.length === 0) {
      previousRejection = 'Aucun fichier lisible dans ta reponse. Respecte le format structure a la lettre.'
      lastSummary = 'reponse illisible'
      continue
    }

    const application = applyTargetedRepair({ before: args.files, scope, produced })
    const summary = describe(application)
    if (application.patched.length === 0 && application.added.length === 0) {
      previousRejection = `Rien n a pu etre applique: ${summary}. Rends UNIQUEMENT les chemins autorises, a l identique.`
      lastSummary = summary
      continue
    }

    return {
      files: application.files,
      changed: true,
      attempts: attempt,
      patched: application.patched,
      added: application.added,
      rejected: application.rejected,
      summary,
    }
  }

  return {
    files: args.files, changed: false, attempts: maxAttempts, patched: [], added: [], rejected: [],
    summary: lastSummary,
  }
}
