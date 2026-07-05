import {
  CODE_SINGLE_MODEL,
} from '../config/models'
import type { CodeIntent } from './codeIntent'
import { generateJsonFromModel } from './modelJson'

type MissionFileContext = {
  name: string
  language: string
  content: string
}

export type CodeMissionDossier = {
  objective: string
  requestedDeliverables: string[]
  nonNegotiableConstraints: string[]
  workingAssumptions: string[]
  architectureDirectives: string[]
  validationChecklist: string[]
  antiFailureDirectives: string[]
  reviewFocus: string[]
}

export type CodeDraftReview = {
  score: number
  verdict: 'accept' | 'repair' | 'regenerate'
  summary: string
  strengths: string[]
  criticalIssues: string[]
  missingFiles: string[]
  mustFixBeforeSandbox: string[]
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)))
}

function shorten(text: string, maxLength = 420) {
  const normalized = text.replace(/\s+/g, ' ').trim()
  if (normalized.length <= maxLength) {
    return normalized
  }

  return `${normalized.slice(0, maxLength)}...`
}

function summarizeExistingFiles(files: MissionFileContext[]) {
  if (files.length === 0) {
    return 'Aucun fichier existant a conserver.'
  }

  return files
    .slice(0, 10)
    .map((file) => {
      const preview = shorten(file.content, 180)
      return `- ${file.name} (${file.language}) :: ${preview}`
    })
    .join('\n')
}

function hasFile(files: MissionFileContext[], matcher: RegExp | string) {
  return files.some((file) => {
    const normalized = file.name.replace(/\\/g, '/').toLowerCase()
    if (typeof matcher === 'string') {
      return normalized === matcher.toLowerCase()
    }
    return matcher.test(normalized)
  })
}

function isDocumentationFile(name: string) {
  return /\.(md|txt|doc|docx|pdf|rtf)$/i.test(name)
}

function stripFormattingArtifacts(content: string) {
  let current = content
    .replace(/^\uFEFF/, '')
    .replace(/<think>[\s\S]*?<\/think>/gi, '')
    .trim()

  for (let index = 0; index < 3; index += 1) {
    const next = current
      .replace(/^```[\w.-]*\s*\r?\n/, '')
      .replace(/\r?\n```$/, '')
      .trim()
    if (next === current) break
    current = next
  }

  return current
}

function parseJsonSafely(content: string) {
  try {
    return JSON.parse(stripFormattingArtifacts(content)) as Record<string, unknown>
  } catch {
    return null
  }
}

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

export function serializeCodeMissionDossier(dossier: CodeMissionDossier) {
  return [
    `OBJECTIF_EXECUTIF: ${dossier.objective}`,
    dossier.requestedDeliverables.length > 0
      ? `LIVRABLES_ATTENDUS:\n${dossier.requestedDeliverables.map((item) => `- ${item}`).join('\n')}`
      : '',
    dossier.nonNegotiableConstraints.length > 0
      ? `CONTRAINTES_DURES:\n${dossier.nonNegotiableConstraints.map((item) => `- ${item}`).join('\n')}`
      : '',
    dossier.workingAssumptions.length > 0
      ? `HYPOTHESES_AUTONOMES:\n${dossier.workingAssumptions.map((item) => `- ${item}`).join('\n')}`
      : '',
    dossier.architectureDirectives.length > 0
      ? `DIRECTIVES_ARCHITECTURE:\n${dossier.architectureDirectives.map((item) => `- ${item}`).join('\n')}`
      : '',
    dossier.validationChecklist.length > 0
      ? `CHECKLIST_VALIDATION:\n${dossier.validationChecklist.map((item) => `- ${item}`).join('\n')}`
      : '',
    dossier.antiFailureDirectives.length > 0
      ? `GARDE_FOUS_ANTI_ECHEC:\n${dossier.antiFailureDirectives.map((item) => `- ${item}`).join('\n')}`
      : '',
    dossier.reviewFocus.length > 0
      ? `FOCUS_AUDIT_INTERNE:\n${dossier.reviewFocus.map((item) => `- ${item}`).join('\n')}`
      : '',
  ].filter(Boolean).join('\n\n')
}

function buildDraftReviewFallback(
  prompt: string,
  intent: CodeIntent,
  files: MissionFileContext[],
): CodeDraftReview {
  const strengths: string[] = []
  const criticalIssues: string[] = []
  const missingFiles: string[] = []
  const mustFix: string[] = []
  let score = 92

  const codeFiles = files.filter((file) => !isDocumentationFile(file.name))
  const genericNames = files.filter((file) => /^bloc-\d+\./i.test(file.name) || /^reponse\./i.test(file.name))
  const placeholderFiles = files.filter((file) =>
    /\b(TODO|FIXME|placeholder|implement here|to be implemented|coming soon|lorem ipsum|stub)\b/i.test(file.content),
  )
  const tinyFiles = codeFiles.filter((file) => file.content.trim().length < 60)
  const docsOnly = files.length > 0 && files.every((file) => isDocumentationFile(file.name))
  const promptLower = prompt.toLowerCase()

  if (files.length === 0) {
    criticalIssues.push('aucun fichier de code exploitable n a ete genere')
    score = 0
  }

  if (!docsOnly && codeFiles.length > 0) {
    strengths.push('des fichiers de code exploitables ont bien ete produits')
  }

  if (docsOnly) {
    criticalIssues.push('la sortie contient uniquement de la documentation au lieu de code source')
    score -= 55
  }

  if (genericNames.length === files.length && files.length > 0) {
    criticalIssues.push('les noms de fichiers sont generiques et peu fiables pour un vrai projet')
    score -= 30
  }

  if (placeholderFiles.length > 0) {
    mustFix.push(`supprimer les placeholders/TODO dans ${placeholderFiles.map((file) => file.name).join(', ')}`)
    score -= 24
  }

  if (tinyFiles.length >= 2 || (codeFiles.length > 0 && tinyFiles.length === codeFiles.length)) {
    mustFix.push('les fichiers sont trop minces pour constituer une implementation complete')
    score -= 18
  }

  const nodeLikeProject =
    intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType.startsWith('fullstack_')
    || intent.projectType === 'api_express'
    || intent.projectType === 'cli_node'
    || intent.projectType === 'desktop_electron'
    || intent.projectType === 'game_web'
    || intent.projectType === 'library_npm'

  if (nodeLikeProject && !hasFile(files, 'package.json')) {
    missingFiles.push('package.json')
    score -= 18
  }

  const packageFile = files.find((file) => file.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  if (packageFile) {
    const parsedPackage = parseJsonSafely(packageFile.content)
    if (!parsedPackage) {
      criticalIssues.push('package.json est invalide ou contient du markdown parasite au lieu d un JSON pur')
      mustFix.push('reecrire package.json en JSON strict sans backticks ni texte libre')
      score -= 24
    }
  }

  if (intent.projectType === 'static_web' && !hasFile(files, /\.html?$/i)) {
    missingFiles.push('point d entree HTML')
    score -= 18
  }

  if (intent.projectType === 'desktop_tauri' && !hasFile(files, /(^|\/)src-tauri\/cargo\.toml$/i) && !hasFile(files, 'cargo.toml')) {
    missingFiles.push('src-tauri/Cargo.toml')
    score -= 18
  }

  if (
    (intent.projectType === 'api_fastapi'
      || intent.projectType === 'api_flask'
      || intent.projectType === 'api_django'
      || intent.projectType === 'cli_python'
      || intent.projectType === 'data_python'
      || intent.projectType === 'library_pypi'
      || intent.projectType === 'fullstack_django')
    && !hasFile(files, /\.py$/i)
  ) {
    missingFiles.push('entree Python')
    score -= 18
  }

  if (intent.needsArchitecturePlanning && codeFiles.length < 3) {
    mustFix.push('la structure du projet semble trop courte pour la complexite detectee')
    score -= 10
  }

  if (intent.features.includes('authentication') && !/\b(auth|login|jwt|session|token|middleware)\b/i.test(files.map((file) => file.content).join('\n'))) {
    mustFix.push('la surface d authentification demandee n apparait pas clairement dans le code genere')
    score -= 12
  }

  if (intent.features.includes('database') && !/\b(prisma|typeorm|mongoose|sequelize|drizzle|sql|sqlite|postgres|mysql|mongodb|redis)\b/i.test(files.map((file) => file.content).join('\n'))) {
    mustFix.push('aucune couche de persistence visible malgre une demande orientee donnees')
    score -= 10
  }

  const codeBlob = files.map((file) => file.content).join('\n')
  if (
    /\b(wasd|clavier|keyboard|key(?:down|up)|touches?|fleches?|shift|espace|space)\b/i.test(prompt)
    && !/\b(addEventListener\s*\(\s*['"]key(?:down|up)|onKeyDown|onKeyUp|KeyboardControls|useKeyboardControls)\b/i.test(codeBlob)
  ) {
    mustFix.push('les controles clavier demandes (WASD/shift/espace) ne sont pas cables dans le code')
    score -= 16
  }

  if (/\b(minimap|mini-map|radar)\b/i.test(prompt) && !/\b(minimap|mini-map|radar)\b/i.test(codeBlob)) {
    mustFix.push('la minimap/radar demandee n apparait pas comme fonctionnalite codee')
    score -= 12
  }

  if (
    /\b(collect|collecter|resource|ressource|minerai|mineral|dock|docking|scanner?|scan)\b/i.test(prompt)
    && !(
      /\b(collision|collid|intersect|distanceTo|raycaster|Math\.hypot|Vector3|Box3|Sphere)\b/i.test(codeBlob)
      && /\b(collect|dock|scan|scanner|resource|ressource|mineral|minerai|cargo|inventory|mission|objective)\b/i.test(codeBlob)
    )
  ) {
    mustFix.push('les mecaniques de collecte/scan/docking demandees doivent etre cablees avec des tests spatiaux reels, pas seulement decrites dans le HUD')
    score -= 14
  }

  if (/\btauri\b/i.test(promptLower) && !hasFile(files, /src-tauri/i)) {
    missingFiles.push('backend Tauri')
    score -= 16
  }

  if (missingFiles.length === 0 && mustFix.length === 0 && criticalIssues.length === 0) {
    strengths.push('le draft couvre les fondamentaux attendus avant sandbox')
  }

  score = Math.max(0, Math.min(100, score))
  const verdict = criticalIssues.length > 0 || score < 45
    ? 'regenerate'
    : (mustFix.length > 0 || missingFiles.length > 0 || score < 74 ? 'repair' : 'accept')

  const summary =
    verdict === 'accept'
      ? 'Draft coherent avant sandbox.'
      : verdict === 'repair'
        ? 'Draft utile mais incomplet ou fragile avant validation.'
        : 'Draft rejete avant sandbox car trop risqué ou insuffisant.'

  return {
    score,
    verdict,
    summary,
    strengths: uniqueStrings(strengths),
    criticalIssues: uniqueStrings(criticalIssues),
    missingFiles: uniqueStrings(missingFiles),
    mustFixBeforeSandbox: uniqueStrings(mustFix),
  }
}

function normalizeDraftReview(
  candidate: Partial<CodeDraftReview> | null | undefined,
  fallback: CodeDraftReview,
): CodeDraftReview {
  const score = Number.isFinite(candidate?.score) ? Math.max(0, Math.min(100, Number(candidate?.score))) : fallback.score
  const verdict = candidate?.verdict === 'accept' || candidate?.verdict === 'repair' || candidate?.verdict === 'regenerate'
    ? candidate.verdict
    : fallback.verdict

  return {
    score,
    verdict,
    summary: candidate?.summary?.trim() || fallback.summary,
    strengths: Array.isArray(candidate?.strengths) ? uniqueStrings(candidate.strengths) : fallback.strengths,
    criticalIssues: Array.isArray(candidate?.criticalIssues) ? uniqueStrings(candidate.criticalIssues) : fallback.criticalIssues,
    missingFiles: Array.isArray(candidate?.missingFiles) ? uniqueStrings(candidate.missingFiles) : fallback.missingFiles,
    mustFixBeforeSandbox: Array.isArray(candidate?.mustFixBeforeSandbox) ? uniqueStrings(candidate.mustFixBeforeSandbox) : fallback.mustFixBeforeSandbox,
  }
}

function summarizeFilesForReview(files: MissionFileContext[]) {
  return files
    .slice(0, 12)
    .map((file) => [
      `--- FILE: ${file.name} (${file.language}) ---`,
      shorten(file.content, 600),
    ].join('\n'))
    .join('\n\n')
}

export async function reviewGeneratedCodeDraft({
  prompt,
  intent,
  files,
  architecturePlan,
  missionDossier,
  model = CODE_SINGLE_MODEL,
}: {
  prompt: string
  intent: CodeIntent
  files: MissionFileContext[]
  architecturePlan: string | null
  missionDossier: CodeMissionDossier
  model?: string
}): Promise<CodeDraftReview> {
  const fallback = buildDraftReviewFallback(prompt, intent, files)

  if (files.length === 0) {
    return fallback
  }

  const reviewPrompt = [
    'Tu es le gardien qualite du module CODE d AuroraIA.',
    'Tu audites un draft de projet AVANT le sandbox.',
    '',
    'Reponds UNIQUEMENT en JSON valide avec cette forme:',
    '{',
    '  "score": 0,',
    '  "verdict": "accept|repair|regenerate",',
    '  "summary": "resume court",',
    '  "strengths": ["point fort"],',
    '  "criticalIssues": ["probleme bloquant"],',
    '  "missingFiles": ["fichier ou piece critique manquante"],',
    '  "mustFixBeforeSandbox": ["correction importante"]',
    '}',
    '',
    'Regles de jugement:',
    '- "regenerate" si la sortie ressemble a de la doc, des placeholders, des stubs, une architecture clairement hors-sujet, ou un REFUS/EXCUSE du modele.',
    '- "regenerate" IMMEDIATEMENT si un fichier contient "je suis desole", "I cannot", "I\'m sorry", des excuses ou un refus de generer.',
    '- "repair" si la base est bonne mais fragile, incomplete ou partiellement incoherente.',
    '- "accept" seulement si le draft semble vraiment sandbox-ready et REPOND FIDELEMENT a la demande.',
    '- Penalise fortement: TODO, fichiers vides, scripts absents, imports invraisemblables, stack incoherente, absence de point d entree.',
    '- Penalise SEVEREMENT: fichiers qui ne contiennent pas de code mais du texte explicatif, des excuses ou des redirections.',
    '- Priorite: fidelite a la demande, completude, executabilite, robustesse, qualite visuelle.',
    '',
    `Projet detecte: ${intent.projectType} (${intent.complexity})`,
    intent.frameworks.length > 0 ? `Frameworks: ${intent.frameworks.join(', ')}` : '',
    intent.languages.length > 0 ? `Langages: ${intent.languages.join(', ')}` : '',
    intent.features.length > 0 ? `Features: ${intent.features.join(', ')}` : '',
    '',
    `Demande utilisateur: ${shorten(prompt, 500)}`,
    '',
    'Dossier executif:',
    serializeCodeMissionDossier(missionDossier),
    '',
    architecturePlan ? `Plan d architecture (extrait):\n${shorten(architecturePlan, 1800)}` : 'Plan d architecture: indisponible',
    '',
    'Draft a auditer:',
    summarizeFilesForReview(files),
  ].filter(Boolean).join('\n')

  const raw = await generateJsonFromModel<Partial<CodeDraftReview>>(model, reviewPrompt, fallback, {
    resilient: true,
    timeoutMs: 120_000,
    firstByteTimeoutMs: 90_000,
  })
  return normalizeDraftReview(raw, fallback)
}

export function buildDraftRegenerationPrompt({
  originalPrompt,
  enrichedPrompt,
  missionDossier,
  draftReview,
  architecturePlan,
}: {
  originalPrompt: string
  enrichedPrompt: string
  missionDossier: CodeMissionDossier
  draftReview: CodeDraftReview
  architecturePlan: string | null
}) {
  const machineFileIssue = [
    ...draftReview.criticalIssues,
    ...draftReview.mustFixBeforeSandbox,
    ...draftReview.missingFiles,
  ].some((item) => /json|package\.json|tsconfig|manifest|config/i.test(item))

  return [
    'REGENERATION OBLIGATOIRE DU PROJET.',
    'Le draft precedent a ete audite puis rejete avant sandbox.',
    '',
    `Demande originale:\n${originalPrompt}`,
    '',
    `Contrat enrichi:\n${shorten(enrichedPrompt, 2600)}`,
    '',
    `Dossier executif:\n${serializeCodeMissionDossier(missionDossier)}`,
    '',
    architecturePlan ? `Plan d architecture a respecter:\n${shorten(architecturePlan, 2400)}` : '',
    '',
    `Diagnostic audit:\n- Score: ${draftReview.score}\n- Verdict: ${draftReview.verdict}\n- Resume: ${draftReview.summary}`,
    draftReview.criticalIssues.length > 0 ? `Problemes critiques:\n${draftReview.criticalIssues.map((item) => `- ${item}`).join('\n')}` : '',
    draftReview.missingFiles.length > 0 ? `Pieces manquantes:\n${draftReview.missingFiles.map((item) => `- ${item}`).join('\n')}` : '',
    draftReview.mustFixBeforeSandbox.length > 0 ? `Corrections indispensables:\n${draftReview.mustFixBeforeSandbox.map((item) => `- ${item}`).join('\n')}` : '',
    '',
    machineFileIssue
      ? [
          'Priorite absolue fichiers machine:',
          '- Reecris `package.json`, `tsconfig.json` et tout `.json` en JSON strict parseable par JSON.parse.',
          '- Aucun commentaire, aucune virgule finale, aucun bloc markdown, aucun texte autour du JSON.',
          '- Pour React Three Fiber, utilise uniquement les noms npm officiels: `@react-three/fiber`, `@react-three/drei`, `@react-three/postprocessing`.',
          '- Interdit: `react-three-fiber`, `react-three/drei`, `react-three/postprocessing` dans package.json.',
        ].join('\n')
      : '',
    '',
    'Instruction absolue:',
    '- Regenere les fichiers de code complets.',
    '- Ne produis ni documentation descriptive ni squelette incomplet.',
    '- Corrige specifiquement les problemes identifies par l audit.',
    '- Respecte le format --- FICHIER: ... --- pour chaque fichier.',
  ].filter(Boolean).join('\n\n')
}

export function buildRescueRegenerationPrompt({
  originalPrompt,
  missionDossier,
  architecturePlan,
  failingSummary,
  failingErrors,
  reasoningContext,
}: {
  originalPrompt: string
  missionDossier: CodeMissionDossier
  architecturePlan: string | null
  failingSummary: string
  failingErrors: string[]
  reasoningContext?: string
}) {
  return [
    'MODE SAUVETAGE EXECUTIF.',
    'Les corrections incrementales ont echoue ou stagnent. Il faut reconstruire une version plus simple, plus robuste et plus precise.',
    '',
    `Demande originale:\n${originalPrompt}`,
    '',
    `Dossier executif:\n${serializeCodeMissionDossier(missionDossier)}`,
    '',
    architecturePlan ? `Plan d architecture (a epurer si necessaire):\n${shorten(architecturePlan, 2200)}` : '',
    '',
    `Etat courant du sandbox:\n${failingSummary}`,
    failingErrors.length > 0 ? `Erreurs principales:\n${failingErrors.slice(0, 6).map((item) => `- ${shorten(item, 260)}`).join('\n')}` : '',
    reasoningContext ? `Analyse cause racine:\n${reasoningContext}` : '',
    '',
    'Instruction absolue:',
    '- Repars des exigences, pas du dernier patch.',
    '- Simplifie l architecture si elle provoque les echecs.',
    '- Garde uniquement les dependances et fichiers utiles.',
    '- Livre la plus petite version complete et stable qui satisfait la demande.',
  ].filter(Boolean).join('\n\n')
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
