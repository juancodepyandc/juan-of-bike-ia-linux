import { CODE_SINGLE_MODEL } from '../config/models'
import type { CodeIntent } from './codeIntent'
import { generateJsonFromModel } from './modelJson'
import {
  hasFile,
  isDocumentationFile,
  parseJsonSafely,
  serializeCodeMissionDossier,
  shorten,
  uniqueStrings,
  type CodeDraftReview,
  type CodeMissionDossier,
  type MissionFileContext,
} from './codeMissionShared.ts'

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
