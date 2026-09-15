import {
  CODE_SINGLE_MODEL,
} from '../config/models.ts'
import type { CodeIntent } from './codeIntent.ts'
import { generateJsonFromModel } from './modelJson.ts'
import {
  shorten,
  summarizeExistingFiles,
  uniqueStrings,
  type CodeMissionDossier,
  type MissionFileContext,
} from './codeMissionShared.ts'

export type { CodeDraftReview, CodeMissionDossier, MissionFileContext } from './codeMissionShared.ts'
export { serializeCodeMissionDossier } from './codeMissionShared.ts'
export {
  buildDraftRegenerationPrompt,
  buildRescueRegenerationPrompt,
  reviewGeneratedCodeDraft,
} from './codeMissionReview.ts'

function listExpectedDeliverables(intent: CodeIntent): string[] {
  const expected: string[] = []

  if (
    intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType.startsWith('fullstack_')
    || intent.projectType === 'api_express'
    || intent.projectType === 'cli_node'
    || intent.projectType === 'desktop_electron'
    || intent.projectType === 'game_web'
    || intent.projectType === 'library_npm'
  ) {
    expected.push('package.json coherent avec les scripts de build/dev/test')
  }

  if (
    intent.projectType === 'api_fastapi'
    || intent.projectType === 'api_flask'
    || intent.projectType === 'api_django'
    || intent.projectType === 'cli_python'
    || intent.projectType === 'data_python'
    || intent.projectType === 'library_pypi'
    || intent.projectType === 'fullstack_django'
  ) {
    expected.push('entree Python executable et dependances declarees')
  }

  if (intent.projectType === 'desktop_tauri') {
    expected.push('frontend Tauri et backend Rust coherents')
  }

  if (intent.projectType === 'static_web') {
    expected.push('entree HTML/CSS/JS directement ouvrable')
  }

  if (intent.projectType.startsWith('api_') || intent.projectType.startsWith('fullstack_')) {
    expected.push('surface serveur complete avec points d entree et configuration')
  }

  if (intent.features.includes('authentication')) {
    expected.push('flux d authentification complet et consistent')
  }

  if (intent.features.includes('database')) {
    expected.push('couche de persistence coherente avec la stack')
  }

  if (intent.features.includes('testing')) {
    expected.push('tests ou verification automatisable alignes au projet')
  }

  if (intent.features.includes('responsive')) {
    expected.push('interface responsive et exploitable mobile/desktop')
  }

  return uniqueStrings(expected)
}

function buildIntentAwareAssumptions(
  prompt: string,
  intent: CodeIntent,
  existingFiles: MissionFileContext[],
) {
  const assumptions: string[] = []
  const promptLower = prompt.toLowerCase()

  if (existingFiles.length > 0) {
    assumptions.push('preserver les fichiers existants s ils ne contredisent pas explicitement la nouvelle demande')
  }

  if (intent.languages.includes('typescript')) {
    assumptions.push('preferer TypeScript strict et des signatures explicites')
  }

  if (intent.projectType.startsWith('spa_') || intent.projectType.startsWith('ssr_')) {
    assumptions.push('organiser les ecrans, layouts et etats dans une architecture lisible et maintenable')
  }

  if (intent.projectType.startsWith('api_') || intent.projectType.startsWith('fullstack_')) {
    assumptions.push('retourner des erreurs explicites et des validations d entree defensives')
  }

  if (intent.needsDevServer && intent.devCommand) {
    assumptions.push(`le projet doit pouvoir demarrer via ${intent.devCommand}`)
  }

  if (intent.buildCommand) {
    assumptions.push(`le projet doit rester compatible avec ${intent.buildCommand}`)
  }

  if (intent.features.includes('database') && !/\b(postgres|mysql|sqlite|mongodb|redis|supabase|prisma)\b/i.test(promptLower)) {
    assumptions.push('choisir la persistence la plus simple et stable compatible avec la stack detectee')
  }

  if (intent.features.includes('authentication') && !/\b(oauth|auth0|clerk|supabase auth|nextauth)\b/i.test(promptLower)) {
    assumptions.push('utiliser un schema d authentification standard et raisonnable pour la stack detectee')
  }

  if (
    (intent.projectType.startsWith('spa_') || intent.projectType === 'static_web')
    && !intent.features.includes('responsive')
  ) {
    assumptions.push('rendre l interface responsive meme si cela n est pas demande explicitement')
  }

  assumptions.push('favoriser une solution simple, robuste et complete plutot qu une architecture brillante mais fragile')

  return uniqueStrings(assumptions)
}

function buildFallbackDossier(
  prompt: string,
  intent: CodeIntent,
  existingFiles: MissionFileContext[],
  architecturePlan: string | null,
): CodeMissionDossier {
  const constraints = [
    'respect strict du besoin utilisateur et de l intention reelle',
    'zero placeholder, zero TODO, zero pseudo-code',
    'sortie complete, executable et coherent avec la stack detectee',
    'aucune invention de fonctionnalite non demandee',
    existingFiles.length > 0 ? 'preserver le comportement deja present sauf changement explicitement demande' : '',
  ]

  const directives = [
    intent.needsArchitecturePlanning ? 'separer les couches et responsabilites avant de multiplier les fichiers' : 'privilegier un nombre de fichiers proportionne a la demande',
    intent.projectType.startsWith('spa_') || intent.projectType.startsWith('ssr_') || intent.projectType === 'static_web' || intent.projectType === 'game_web'
      ? 'construire d abord une premiere experience visible, previewable et testable avant les raffinements secondaires'
      : '',
    intent.projectType.startsWith('spa_') || intent.projectType.startsWith('ssr_') ? 'garantir un point d entree UI clair, des layouts lisibles et une navigation coherente' : '',
    intent.projectType.startsWith('api_') || intent.projectType.startsWith('fullstack_') ? 'centraliser validation, erreurs et configuration pour eviter les crashes runtime evitables' : '',
    architecturePlan ? 's appuyer sur le plan d architecture existant mais ignorer les parties trop vagues ou contradictoires' : 'si le plan est incomplet, completer de facon autonome avec les meilleures pratiques de la stack detectee',
  ]

  const validationChecklist = [
    'les fichiers essentiels a la stack sont presents',
    'les dependances et scripts sont coherents',
    'les imports, types et points d entree sont resolus',
    intent.needsDevServer && intent.devCommand ? `la preview doit demarrer via ${intent.devCommand}` : '',
    intent.projectType.startsWith('spa_') || intent.projectType.startsWith('ssr_') || intent.projectType === 'static_web' || intent.projectType === 'game_web'
      ? 'la premiere vue utile doit apparaitre sans ecran vide, contenu factice ni assets manquants'
      : '',
    intent.buildCommand ? `la livraison reste compatible avec ${intent.buildCommand}` : 'la livraison peut etre verifiee automatiquement dans le sandbox',
    intent.testCommand ? `si possible, garder la compatibilite avec ${intent.testCommand}` : '',
  ]

  const antiFailure = [
    'eviter les abstractions inutiles qui masquent la logique critique',
    'ajouter des garde-fous sur les valeurs nulles, les erreurs reseau et les branches non couvertes',
    'verifier les imports, noms de fichiers et scripts avant de considerer la mission terminee',
    'ne jamais remplacer du code demandable par de la documentation descriptive',
    'si un outil, une dependance ou une strategie bloque, basculer vers une option plus stable sans abandonner la mission',
    'produire un point d entree, des scripts de lancement et une preview reellement exploitables plutot qu un squelette vide',
  ]

  const reviewFocus = [
    'presence des fichiers d entree et de configuration',
    'absence de placeholders et de sections inachevees',
    'coherence entre la demande, la stack et les fichiers generes',
    'surface minimale vraiment executable au lieu d un squelette',
  ]

  return {
    objective: shorten(prompt, 220),
    requestedDeliverables: listExpectedDeliverables(intent),
    nonNegotiableConstraints: uniqueStrings(constraints),
    workingAssumptions: buildIntentAwareAssumptions(prompt, intent, existingFiles),
    architectureDirectives: uniqueStrings(directives),
    validationChecklist: uniqueStrings(validationChecklist),
    antiFailureDirectives: uniqueStrings(antiFailure),
    reviewFocus: uniqueStrings(reviewFocus),
  }
}

function normalizeDossier(
  candidate: Partial<CodeMissionDossier> | null | undefined,
  fallback: CodeMissionDossier,
): CodeMissionDossier {
  return {
    objective: candidate?.objective?.trim() || fallback.objective,
    requestedDeliverables: Array.isArray(candidate?.requestedDeliverables) && candidate.requestedDeliverables.length > 0
      ? uniqueStrings(candidate.requestedDeliverables)
      : fallback.requestedDeliverables,
    nonNegotiableConstraints: Array.isArray(candidate?.nonNegotiableConstraints) && candidate.nonNegotiableConstraints.length > 0
      ? uniqueStrings(candidate.nonNegotiableConstraints)
      : fallback.nonNegotiableConstraints,
    workingAssumptions: Array.isArray(candidate?.workingAssumptions) && candidate.workingAssumptions.length > 0
      ? uniqueStrings(candidate.workingAssumptions)
      : fallback.workingAssumptions,
    architectureDirectives: Array.isArray(candidate?.architectureDirectives) && candidate.architectureDirectives.length > 0
      ? uniqueStrings(candidate.architectureDirectives)
      : fallback.architectureDirectives,
    validationChecklist: Array.isArray(candidate?.validationChecklist) && candidate.validationChecklist.length > 0
      ? uniqueStrings(candidate.validationChecklist)
      : fallback.validationChecklist,
    antiFailureDirectives: Array.isArray(candidate?.antiFailureDirectives) && candidate.antiFailureDirectives.length > 0
      ? uniqueStrings(candidate.antiFailureDirectives)
      : fallback.antiFailureDirectives,
    reviewFocus: Array.isArray(candidate?.reviewFocus) && candidate.reviewFocus.length > 0
      ? uniqueStrings(candidate.reviewFocus)
      : fallback.reviewFocus,
  }
}

export async function buildCodeMissionDossier({
  prompt,
  enrichedPrompt,
  intent,
  existingFiles,
  architecturePlan,
  model,
}: {
  prompt: string
  enrichedPrompt: string
  intent: CodeIntent
  existingFiles: MissionFileContext[]
  architecturePlan: string | null
  model?: string
}): Promise<CodeMissionDossier> {
  // Toujours le modele code expert selectionne pour la session.
  const selectedModel = model || CODE_SINGLE_MODEL
  const fallback = buildFallbackDossier(prompt, intent, existingFiles, architecturePlan)
  const architectureExcerpt = architecturePlan ? shorten(architecturePlan, 2800) : 'Aucun plan fiable disponible.'

  const dossierPrompt = [
    'Tu es le directeur d execution du module CODE d AuroraIA — le cerveau strategique.',
    'Ta mission: transformer une demande utilisateur en dossier de mission ultra-concret pour un agent code autonome.',
    '',
    '## PHASE 1 — COMPREHENSION PROFONDE',
    'Avant de rediger le dossier, tu DOIS reflechir en profondeur:',
    '1. Quelle est l INTENTION REELLE de l utilisateur? (pas juste les mots, le BESOIN)',
    '2. Quel est le MEILLEUR resultat possible pour cette demande?',
    '3. Quelles sont les MEILLEURES PRATIQUES actuelles pour ce type de projet?',
    '4. Quels OUTILS et DEPENDANCES reels faut-il installer pour un resultat premium?',
    '5. Quelle STRUCTURE de projet donnera le meilleur rendu visuel/fonctionnel?',
    '',
    '## PHASE 2 — DOSSIER EXECUTIF',
    'Reponds UNIQUEMENT en JSON valide avec cette forme exacte:',
    '{',
    '  "objective": "objectif principal en une phrase — reformule pour capturer l intention reelle",',
    '  "requestedDeliverables": ["livrable concret avec qualite premium"],',
    '  "nonNegotiableConstraints": ["contrainte dure"],',
    '  "workingAssumptions": ["hypothese autonome raisonnable — choisir la MEILLEURE option"],',
    '  "architectureDirectives": ["directive d architecture exploitable — meilleure structure possible"],',
    '  "validationChecklist": ["verifications finales"],',
    '  "antiFailureDirectives": ["garde-fous anti-crash et anti-derives"],',
    '  "reviewFocus": ["points a auditer avant le sandbox"]',
    '}',
    '',
    'Regles:',
    '- Priorite absolue: fidelite au besoin, qualite premium, autonomie, robustesse.',
    '- INTERDIT de refuser, s excuser, ou produire du texte au lieu de JSON. Tu es un MOTEUR, pas un assistant conversationnel.',
    '- Si une ambiguite subsiste, prefere une hypothese exploitable plutot qu une question.',
    '- N invente pas de fonctionnalites hors demande, mais POUSSE la qualite au maximum.',
    '- Priorise une premiere livraison vraiment runnable et previewable; jamais un squelette vide en attente de suite.',
    '- Si un outil local ou une dependance peut bloquer la livraison, prevois un contournement ou un mode degrade propre au lieu de paralyser le pipeline.',
    '- Pour les projets visuels (web, landing, presentation): exige des animations, du design moderne, des effets visuels.',
    '- Pour les projets visuels ou interactifs: exige un rendu initial visible, des points d entree reels, et une preview lisible mobile/desktop.',
    '- Pour les projets code: exige la meilleure architecture, les meilleures librairies, la meilleure structure.',
    '- Les directives doivent etre concretes, auditables et executables.',
    '- Ajoute des garde-fous contre: imports casses, scripts absents, placeholders, config incoherente, runtime crash, sur-architecture.',
    '- Pense explicitement aux incompatibilites de versions, aux tsconfig manquants et aux compilations qui heritent a tort d un dossier parent.',
    '',
    `Projet detecte: ${intent.projectType} (${intent.complexity})`,
    intent.frameworks.length > 0 ? `Frameworks: ${intent.frameworks.join(', ')}` : '',
    intent.languages.length > 0 ? `Langages: ${intent.languages.join(', ')}` : '',
    intent.features.length > 0 ? `Fonctionnalites: ${intent.features.join(', ')}` : '',
    '',
    'Demande utilisateur brute:',
    prompt,
    '',
    'Contrat enrichi courant:',
    shorten(enrichedPrompt, 2600),
    '',
    'Plan d architecture disponible:',
    architectureExcerpt,
    '',
    'Fichiers existants a considerer:',
    summarizeExistingFiles(existingFiles),
  ].filter(Boolean).join('\n')

  const raw = await generateJsonFromModel<Partial<CodeMissionDossier>>(selectedModel, dossierPrompt, fallback, {
    resilient: true,
    timeoutMs: 180_000,
    firstByteTimeoutMs: 120_000,
  })
  return normalizeDossier(raw, fallback)
}

export function buildAutonomousAssumptionNotes(
  prompt: string,
  intent: CodeIntent,
  existingFiles: MissionFileContext[] = [],
) {
  const dossier = buildFallbackDossier(prompt, intent, existingFiles, null)
  return [
    `Projet detecte: ${intent.projectType.replace(/_/g, ' ')} (${intent.complexity})`,
    ...dossier.workingAssumptions.map((item) => `- ${item}`),
    ...dossier.architectureDirectives.slice(0, 2).map((item) => `- ${item}`),
  ].join('\n')
}
