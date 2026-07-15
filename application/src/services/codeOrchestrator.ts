// ---------------------------------------------------------------------------
// Code Orchestrator — Multi-phase pipeline with model routing
// Equivalent of conversationOrchestrator.ts but specialized for code generation
// ---------------------------------------------------------------------------

import type { OllamaMessage } from '../types/app'
import {
  resilientOllamaChat,
  resilientOllamaChatStream,
  resilientOllamaGenerate,
  type RecoveryEvent,
} from './ollamaResilience'
import {
  type CodeIntent,
  type CodeIntentContext,
  buildArchitecturePlanningPrompt,
  classifyCodeIntent,
} from './codeIntent'
import {
  buildArchitecteSystemPrompt,
  buildCodeurSystemPrompt,
  buildAuditeurSystemPrompt,
} from './codeSystemPrompts'
import {
  buildAutonomousAssumptionNotes,
  buildCodeMissionDossier,
  buildDraftRegenerationPrompt,
  buildRescueRegenerationPrompt,
  reviewGeneratedCodeDraft,
  serializeCodeMissionDossier,
  type CodeMissionDossier,
} from './codeMissionControl'
import {
  type CorrectionStrategy,
  type CorrectionPass,
  type ErrorCategory,
  buildCorrectionStrategy,
  shouldContinueLoop,
  classifyErrors,
} from './codeAutoCorrection'
import { searchForSolution, researchBestPractices } from './codeResearch'
import { runCodeSandboxValidation, type CodeSandboxResult, type CodeSandboxStepResult } from './codeSandbox'
import { analyzeStuckCorrection, buildReasoningInstructions } from './codeReasoningEngine'
import {
  runCodePreflight,
  serializeCodePreflightReport,
  type CodePreflightReport,
} from './codePreflight'
import { withTimeout } from './llmTimebox'
import { isLLMRefusal } from './codeLLMRefusal.ts'
import { parseCodeFiles, serializeCodeFiles, extractNotes, detectNonCodePlanningNarrative } from './codeGeneratedFileParser.ts'
import {
  isVersionBelow,
  manifestUsesPackage,
  normalizeGeneratedCodeFilesForTest,
  readManifestDependencySpec,
  sanitizeGeneratedFiles,
  stripFormattingArtifacts,
  tryParseJson,
  upsertPackageDevDependency,
} from './codeGeneratedFileSanitizer.ts'
export { isLLMRefusal } from './codeLLMRefusal.ts'
export { parseCodeFiles, serializeCodeFiles, extractNotes } from './codeGeneratedFileParser.ts'
export { normalizeGeneratedCodeFilesForTest } from './codeGeneratedFileSanitizer.ts'
import {
  applySubjectImagePlaceholder,
  fetchBrandProfileFromBridge,
  fetchSubjectImages,
  mergeExistingWithUpdates,
} from './codeSubjectAssets.ts'
import { evaluateBrandFidelity, type BrandFidelityReport } from './codeFidelityGate'
import { compositeStaticCritic } from './codeStaticCritics'
import type { CritiqueReport } from './codeMultiPassCritique'
import {
  buildDesignRetryHint,
  checkGamePlayability,
  checkInteractive3DFidelity,
  checkWebPageIntegrity,
  computeContentQualityScore,
  computeDesignPolishReport,
  computeDesignPolishReportPublic,
  isVisualProjectType,
  type DesignPolishReport,
} from './codeQualityGates.ts'
export {
  buildDesignRetryHint,
  checkGamePlayability,
  checkInteractive3DFidelity,
  checkWebPageIntegrity,
  computeDesignPolishReportPublic,
} from './codeQualityGates.ts'
export type { DesignPolishReport } from './codeQualityGates.ts'
import {
  analyzeFollowUpIntent,
  type FollowUpAnalysis,
  type FollowUpKind,
} from './codeFollowUpAnalysis.ts'
export {
  analyzeFollowUpIntent,
  classifyClarificationSeverity,
  isVagueClarification,
} from './codeFollowUpAnalysis.ts'
export type {
  ClarificationSeverity,
  FollowUpAnalysis,
  FollowUpKind,
} from './codeFollowUpAnalysis.ts'

/**
 * Auto-generate a smart assumption instead of asking a vague question.
 * The code module should be autonomous and prefer assumptions over questions.
 */
export function buildAutonomousAssumption(prompt: string, intent: CodeIntent): string {
  return buildAutonomousAssumptionNotes(prompt, intent)
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CodeFile = {
  name: string
  language: string
  content: string
}

export type CodeOrchestrationPhase =
  | 'intent'
  | 'preflight'
  | 'planning'
  | 'generation'
  | 'validation'
  | 'correction'
  | 'research'
  | 'dev_server'
  | 'done'
  | 'error'

export type CodeOrchestrationResult = {
  files: CodeFile[]
  notes: string
  sandboxResult: CodeSandboxResult | null
  intent: CodeIntent
  preflightReport: CodePreflightReport | null
  correctionLog: CorrectionPass[]
  phase: CodeOrchestrationPhase
  architecturePlan: string | null
  totalAttempts: number
  finalScore: number
  recoveryEvents: RecoveryEvent[]
  /** Follow-up analysis — null when no conversation context was available. */
  followUp: FollowUpAnalysis | null
  /**
   * v73: design polish report attached when the project produced visual
   * output. Lets the UI surface a badge ("Design 82/100 — manque clamp(),
   * @keyframes") instead of leaving the score buried in retry logs.
   */
  designReport?: DesignPolishReport | null
}

export type PhaseCallback = (detail: string, progress: number) => void

// ---------------------------------------------------------------------------
// Model routing
// ---------------------------------------------------------------------------

/**
 * Expert-model architecture: un modele code dominant pour TOUT le pipeline.
 * Plus de swap VRAM, plus de fallback vers un petit modele.
 * Les differents comportements sont obtenus via les System Prompts
 * (Architecte, Codeur, Auditeur) — pas en changeant de modele.
 */
function selectModel(
  _phase: 'planning' | 'generation' | 'review' | 'correction',
  _intent: CodeIntent,
  _escalationLevel: number,
  configuredCodeModel: string,
): string {
  return configuredCodeModel
}

// ---------------------------------------------------------------------------
// Shared constants — declared early so all functions can reference them
// ---------------------------------------------------------------------------

const PREFLIGHT_PHASE_TIMEOUT_MS = 55_000
const RESEARCH_PHASE_TIMEOUT_MS = 25_000
const STREAM_GENERATION_TOTAL_TIMEOUT_MS = 2_700_000
const PLANNING_TIMEOUT_MS = 900_000
const CORRECTION_TIMEOUT_MS = 1_200_000
const PLANNING_FIRST_BYTE_TIMEOUT_MS = 720_000
const GENERATION_FIRST_BYTE_TIMEOUT_MS = 900_000
const CORRECTION_FIRST_BYTE_TIMEOUT_MS = 900_000
const DOCUMENTATION_EXTENSIONS_EARLY = new Set(['md', 'txt', 'doc', 'docx', 'pdf', 'rtf'])
const CODE_PLANNING_CONTEXT_TOKENS = 16_384
const CODE_EXPERT_CONTEXT_TOKENS = 24_576
const CODE_EXPERT_OUTPUT_TOKENS = 16_000

const INTERACTIVE_3D_FIDELITY_MAX_PASSES = 4



function clipText(text: string, maxLength = 2400) {
  const normalized = text.trim()
  return normalized.length <= maxLength
    ? normalized
    : `${normalized.slice(0, maxLength)}\n...[sortie tronquee]`
}

function buildEmptyGenerationDiagnostic(content: string, intent: CodeIntent, outputRetryCount: number) {
  const trimmed = content.trim()

  if (!trimmed) {
    return [
      `Le modele n a retourne aucun contenu exploitable pour le projet ${intent.projectType}.`,
      `Tentatives de regeneration effectuees: ${outputRetryCount}.`,
    ].join(' ')
  }

  if (isLLMRefusal(trimmed)) {
    return [
      'Le modele a repondu par un refus ou une excuse au lieu de livrer des fichiers de code.',
      `Apercu: ${clipText(trimmed, 500)}`,
    ].join(' ')
  }

  const planningIssue = detectNonCodePlanningNarrative(trimmed)
  if (planningIssue) {
    return [
      'Le modele est reste bloque en mode analyse/preflight au lieu de livrer des fichiers executables.',
      planningIssue,
      `Apercu brut: ${clipText(trimmed, 700)}`,
    ].join(' ')
  }

  return [
    'Le modele a bien produit du texte, mais pas dans un format de fichiers parseable par Aurora.',
    'Le contrat de sortie a donc ete juge invalide.',
    `Apercu brut: ${clipText(trimmed, 700)}`,
  ].join(' ')
}

function getModelShortName(model: string) {
  const tail = model.split('/').pop() || model
  return tail.split(':')[0]
}

function detectEnvironmentBlocker(
  sandboxResult: CodeSandboxResult,
  errorCategories: ErrorCategory[],
): string | null {
  if (sandboxResult.ok) return null

  if (errorCategories.includes('runtime_unavailable')) {
    const autoInstallFailure = sandboxResult.steps.find((step) => step.command.startsWith('auto-install:') && !step.ok)
    if (autoInstallFailure) {
      return `${autoInstallFailure.command.replace('auto-install:', '')} n a pas pu etre prepare automatiquement`
    }

    const missingCommand = sandboxResult.steps
      .filter((step) => !step.ok)
      .map((step) => step.output.match(/Failed to spawn command\s+([^\s:]+)/i)?.[1])
      .find(Boolean)

    if (missingCommand) {
      return `commande ${missingCommand} absente du poste local`
    }

    return 'runtime ou toolchain absente'
  }

  if (/reste indisponible apres preparation automatique/i.test(sandboxResult.summary)) {
    return sandboxResult.summary
  }

  return null
}

function isArchitecturePlanUsable(plan: string | null) {
  if (!plan) return false

  const sectionHits = [
    /###\s*comprehension/i.test(plan),
    /###\s*stack/i.test(plan),
    /###\s*fichiers a generer/i.test(plan),
    /###\s*commandes/i.test(plan) || /###\s*commandes d installation/i.test(plan),
  ].filter(Boolean).length
  const listedFiles = (plan.match(/`[^`\n]+\.[a-z0-9]+`/gi) || []).length

  return sectionHits >= 2 && listedFiles >= 2 && plan.trim().length > 180
}

// ---------------------------------------------------------------------------
// Pipeline phases
// ---------------------------------------------------------------------------

/** Phase 1: Classify intent (deterministic, no LLM) */
function runIntentPhase(
  prompt: string,
  setPhase: PhaseCallback,
  context?: CodeIntentContext,
): CodeIntent {
  setPhase('Classification du projet...', 5)
  return classifyCodeIntent(prompt, context)
}

/** Phase 1.5: Local preflight — inspect machine, workspace and current project before coding */
async function runPreflightPhase(
  prompt: string,
  intent: CodeIntent,
  existingFiles: CodeFile[],
  configuredCodeModel: string,
  setPhase: PhaseCallback,
): Promise<CodePreflightReport | null> {
  try {
    setPhase('Preflight local: analyse machine, outils et fichiers existants...', 8)
    return await withTimeout(runCodePreflight({
      prompt,
      intent,
      existingFiles,
      model: selectModel('planning', intent, 0, configuredCodeModel),
      setPhase: (detail, progress) => setPhase(detail, Math.max(8, Math.min(18, progress))),
    }), {
      label: 'Code preflight',
      timeoutMs: PREFLIGHT_PHASE_TIMEOUT_MS,
    })
  } catch (error) {
    setPhase('Preflight local indisponible — poursuite avec les informations connues...', 12)
    return null
  }
}

/** Phase 2: Deep reasoning + architecture planning (LLM — ALWAYS runs) */
async function runPlanningPhase(
  prompt: string,
  intent: CodeIntent,
  preflightReport: CodePreflightReport | null,
  configuredCodeModel: string,
  setPhase: PhaseCallback,
  onRecovery?: (event: RecoveryEvent) => void,
): Promise<string | null> {
  const model = selectModel('planning', intent, 0, configuredCodeModel)
  setPhase(`Architecte en reflexion (${getModelShortName(model)})...`, 10)
  // Injecter le system prompt ARCHITECTE dans le prompt
  const planPrompt = [
    buildArchitecteSystemPrompt(intent),
    '',
    '---',
    '',
    buildArchitecturePlanningPrompt(prompt, intent),
    preflightReport
      ? [
          '### PREFLIGHT LOCAL OBLIGATOIRE',
          'Le plan doit s appuyer sur ce diagnostic local avant toute decision de stack ou de configuration.',
          serializeCodePreflightReport(preflightReport),
        ].join('\n')
      : '',
  ].filter(Boolean).join('\n\n')

  // Le planning a un vrai budget pour les apps complexes. Si le modele echoue
  // malgre tout, les contrats deterministes prennent le relais.
  try {
    const response = await resilientOllamaGenerate(model, planPrompt, {
      timeoutMs: PLANNING_TIMEOUT_MS,
      firstByteTimeoutMs: PLANNING_FIRST_BYTE_TIMEOUT_MS,
      // v85c : architecte prompt is several thousand tokens; 8192 holds it
      // without risking the VRAM OOM that 16384 flirted with on a 16 GB card.
      num_ctx: CODE_PLANNING_CONTEXT_TOKENS,
      neverMemorySkip: true, // v85c : never refuse to plan on transient RAM pressure
      onRecoveryAttempt: (ev) => {
        // Ne log que les events critiques, pas les retries normaux
        if (ev.action !== 'retry') {
          setPhase(`Architecte — ${ev.action}...`, 16)
          onRecovery?.(ev)
        }
      },
    })
    const plan = response?.response?.trim()
    if (plan && isArchitecturePlanUsable(plan)) {
      setPhase('Plan d architecture pret — lancement de la generation...', 25)
      return plan
    }
    if (plan?.length) {
      setPhase('Plan insuffisant — le Codeur operera en autonomie...', 22)
    }
    return null
  } catch (planError) {
    // Planning echoue — ce n'est PAS un echec critique, le Codeur peut operer seul
    const msg = planError instanceof Error ? planError.message : String(planError)
    console.warn('[CodeOrchestrator] Planning skipped:', msg)
    setPhase('Architecte indisponible — generation directe par le Codeur...', 25)
    return null
  }
}

/** Context forwarded to the Codeur when the orchestrator has resolved a pivot. */
export type GenerationPivotContext = {
  kind: FollowUpKind
  migrationSummary: string | null
}

/** Phase 3: Code generation (streaming) */
async function runGenerationPhase(
  prompt: string,
  intent: CodeIntent,
  preflightReport: CodePreflightReport | null,
  architecturePlan: string | null,
  missionDossier: CodeMissionDossier | null,
  conversationHistory: OllamaMessage[],
  existingFiles: CodeFile[],
  contextImages: string[],
  configuredCodeModel: string,
  escalationLevel: number,
  setPhase: PhaseCallback,
  onToken: (token: string) => void,
  onRecovery?: (event: RecoveryEvent) => void,
  signal?: AbortSignal,
  pivotContext?: GenerationPivotContext,
): Promise<string> {
  setPhase('Generation du code en direct...', 35)
  const model = selectModel('generation', intent, escalationLevel, configuredCodeModel)

  // System prompt CODEUR pour la phase de generation.
  // v68: passer le prompt au builder pour activer la variante starter la plus
  // pertinente (saas/portfolio/ecommerce/dashboard/landing) detectee depuis
  // les mots-cles du prompt user.
  const messages: OllamaMessage[] = [
    { role: 'system', content: buildCodeurSystemPrompt(intent, prompt) },
  ]

  if (preflightReport) {
    messages.push({
      role: 'system',
      content: [
        '## PREFLIGHT LOCAL DU MODULE CODE',
        '',
        serializeCodePreflightReport(preflightReport),
        '',
        'Tu dois t appuyer sur ce preflight avant de fixer les versions, la stack, les scripts et les fichiers de configuration.',
        'Ne code jamais a l aveugle si le preflight indique quoi inspecter ou reutiliser.',
      ].join('\n'),
    })
  }

  // Add architecture plan as detailed implementation guide (capped to protect context window)
  if (architecturePlan) {
    // v85c : 12000 -> 7000. On a 16 GB / 16384-ctx budget the plan competes
    // with the system prompt + existing files for input room; 7000 chars
    // (~1750 tokens) is enough to guide generation without starving output.
    const cappedPlan = architecturePlan.length > 7000
      ? `${architecturePlan.slice(0, 7000)}\n...[plan tronque]`
      : architecturePlan
    messages.push({
      role: 'system',
      content: [
        '## PLAN D IMPLEMENTATION DETAILLE (cree par l architecte — SUIS-LE STRICTEMENT)',
        '',
        cappedPlan,
        '',
        'INSTRUCTIONS:',
        '- Genere TOUS les fichiers listes dans le plan, dans l ordre indique',
        '- Respecte les dependances et versions specifiees',
        '- Inclus un fichier README.md avec les commandes d installation et de lancement',
        '- Le design DOIT correspondre aux specs UX du plan',
        '- Chaque fichier doit etre COMPLET et fonctionnel',
      ].join('\n'),
    })
  } else {
    // No plan available — add minimal README instruction
    messages.push({
      role: 'system',
      content: [
        'INSTRUCTION SUPPLEMENTAIRE:',
        '- Genere un fichier README.md qui explique comment installer et lancer le projet',
        '- Le README doit contenir: description, pre-requis, installation, lancement, structure du projet',
      ].join('\n'),
    })
  }

  if (missionDossier) {
    messages.push({
      role: 'system',
      content: [
        '## DOSSIER EXECUTIF DU MODULE CODE',
        '',
        serializeCodeMissionDossier(missionDossier),
        '',
        'Respecte ce dossier avant toute optimisation locale ou toute improvisation.',
      ].join('\n'),
    })
  }

  // Add conversation history (capped to avoid context overflow)
  const recentHistory = conversationHistory.length > 8
    ? conversationHistory.slice(-8)
    : conversationHistory
  messages.push(...recentHistory)

  // Pivot-aware context: when the user asked for a platform pivot we do NOT
  // show the old code (that is exactly what made the model keep generating
  // HTML when the user asked for Python). Instead we inject a MIGRATION
  // block describing the business concept to carry over, and leave the
  // Codeur free to produce the new stack from scratch.
  if (pivotContext && pivotContext.kind === 'pivot_platform') {
    messages.push({
      role: 'user',
      content: [
        '## MIGRATION DE PROJET — PIVOT DE STACK DEMANDE',
        'L utilisateur a demande de REFAIRE LE MEME CONCEPT sur une autre stack / un autre langage.',
        'Ne reutilise PAS la stack precedente. Reimplemente le concept AU PROPRE, idiomatique, dans la nouvelle stack.',
        pivotContext.migrationSummary
          ? `\n### Concept metier a conserver\n${pivotContext.migrationSummary}`
          : '',
        '',
        '### REGLES',
        '- Genere un projet neuf, complet, idiomatique dans la nouvelle stack.',
        '- NE PRODUIS PAS de fichiers HTML/CSS/JS si la nouvelle stack est Python / Go / Rust / Java / etc.',
        '- NE PRODUIS PAS de fichier Python si la nouvelle stack est web pure. Suis RIGOUREUSEMENT le projet detecte.',
        '- Respecte le format de sortie `--- FICHIER: chemin ---` pour chaque fichier complet.',
        '- Inclure un README.md decrivant comment installer et lancer le nouveau projet.',
      ].filter(Boolean).join('\n'),
    })
  } else if (existingFiles.length > 0) {
    // Classic follow-up (increment / pivot_feature / no pivot): we show the
    // existing files so the Codeur patches them surgically.
    // v85c : budget-based inclusion. The old fixed 4000-char/file cap meant a
    // real project (a 12k-char index.html) was only shown up to char 4000 —
    // so the model "preserved" by REGENERATING a leaner file (a live test
    // showed index.html shrink 17.5k -> 10.7k on a simple modification). We
    // show each file in full until a ~13000-char pool is exhausted — enough to
    // show typical files verbatim (so modifications preserve them) while
    // keeping the follow-up prompt within the 12288 generation window so the
    // output still has room. Overflow files are truncated with a keep-note.
    let fileBudget = 13000
    const fileBlocks: string[] = []
    let shownCount = 0
    for (const f of existingFiles) {
      if (fileBudget <= 400) break
      const perCap = Math.min(f.content.length, Math.max(2000, fileBudget))
      const body = f.content.length > perCap
        ? `${f.content.slice(0, perCap)}\n...[fichier tronque: ${f.content.length} chars — le reste est conserve, NE le supprime pas]`
        : f.content
      fileBlocks.push(`--- FICHIER: ${f.name} ---\n\`\`\`${f.language}\n${body}\n\`\`\``)
      fileBudget -= body.length
      shownCount += 1
    }
    const omitted = existingFiles.length - shownCount
    messages.push({
      role: 'user',
      content: [
        '## CONTEXTE DU PROJET EXISTANT (tu es en mode "suite de conversation")',
        'Ce projet a deja ete genere. La nouvelle instruction utilisateur est une modification / ajout / retrait, PAS une demande de reconstruction.',
        pivotContext?.kind === 'pivot_feature'
          ? 'Mode: evolution majeure d une feature existante. Garde la meme stack, mais autorise des reecritures consequentes des fichiers concernes.'
          : '',
        '',
        '### REGLES DE MODIFICATION',
        '- Analyse l intention: ajout (nouvelle section/feature), retrait (section a enlever), changement (couleur/texte/comportement), refactor (structure interne).',
        '- Ne touche QUE ce qui est demande. Ne refactore rien qui fonctionne deja. Ne regenere pas les fichiers inchanges.',
        '- REGLE: quand tu retournes un fichier modifie, REPRENDS tout son contenu d origine et n applique QUE le changement demande. Ne resume pas, ne supprime aucune section existante qui n est pas explicitement visee par la demande.',
        '- Pour CHAQUE fichier que tu RETOURNES, il doit etre COMPLET (pas de diff, pas de ...).',
        '- Si un fichier ne change pas, NE le retourne PAS — il sera conserve automatiquement.',
        '- Si un fichier est renomme, fais-le proprement (retourner l ancien fichier vide n a aucun effet, retourner le nouveau nom suffit — l orchestrateur gere le delta).',
        '- Conserve imperativement: palette, typographie, structure globale, conventions de nommage, style des animations, ET tout le contenu existant non vise par la demande.',
        '- Si la modification demande une section ou un asset qui n existe pas encore, cree-le en respectant le style deja etabli (meme font, meme vocabulaire d animations, meme espacement).',
        '',
        '### FICHIERS DEJA EN PLACE (a reprendre INTEGRALEMENT quand tu les modifies):',
        ...fileBlocks,
        omitted > 0
          ? `...et ${omitted} autre(s) fichier(s) non montre(s) ici — ils restent en place, NE les supprime pas.`
          : '',
        'IMPORTANT: Chaque fichier que tu retournes doit etre COMPLET et reprendre tout l existant + la modification. Les fichiers non retournes sont conserves intacts.',
        'IMPORTANT: Tu es en mode SUITE, pas en mode creation from scratch — reutilise ce qui est deja construit.',
      ].filter(Boolean).join('\n\n'),
    })
  }

  // Add user prompt
  // v62: pour les projets visuels, on prefixe le user prompt avec un rappel
  // EXPLICITE du design contract afin que le LLM ne l ecrase pas avec ses
  // habitudes "tutoriel". Le system prompt contient deja le contract complet
  // mais les LLMs locaux (qwen3-coder, llama4:scout) tendent a se concentrer
  // sur la derniere consigne — donc on remet le coup de marteau juste avant
  // la demande effective.
  const designReminder = isVisualProjectType(intent.projectType)
    ? [
        '',
        '═══════════════════════════════════════════════════════════════',
        'RAPPEL DESIGN POUSSE — NON NEGOCIABLE',
        '═══════════════════════════════════════════════════════════════',
        '- Hero full-height (min-height:100vh) avec headline clamp(2.8rem, 6vw, 5.5rem) bold + visuel a droite (SVG inline / canvas / mesh gradient).',
        '- Mesh gradient en arriere-plan hero (2-3 blobs filter:blur(120px) absolute, animes via @keyframes).',
        '- Police Google Fonts premium (Inter / Manrope / Satoshi / DM Sans / Space Grotesk / Plus Jakarta) avec preconnect.',
        '- 7+ sections distinctes: nav fixed (backdrop-blur au scroll), hero, features grid 3 cols, showcase/gallery, testimonials/numbers, CTA final, footer 4 cols.',
        '- 7+ micro-interactions parmi: scroll reveal IntersectionObserver, nav qui change au scroll, parallax hero, hover cards (scale 1.02 + zoom image + overlay), counters anime, magnetic buttons, blob mousemove, stagger fade-in, gradient mesh anime, marquee carousel.',
        '- Mode sombre/clair avec data-theme + localStorage + prefers-color-scheme.',
        '- CSS variables completes (--color-*, --space-*, --radius-*, --shadow-*, --duration-*, --ease-*).',
        '- Glassmorphism (backdrop-filter:blur 14px) et shadows composites multi-layer.',
        '',
        'INTERDICTIONS qui declenchent un REJET et regeneration:',
        '- <h1>Bienvenue</h1> sans style. background:blue uni. boutons sans radius/transition.',
        '- font-family Arial/Times/sans-serif default.',
        '- table comme layout. zero animation. <img> casse.',
        '═══════════════════════════════════════════════════════════════',
        '',
        'DEMANDE UTILISATEUR (a traiter avec design pousse):',
      ].join('\n')
    : ''
  // Anti-skeleton clause. With a plan + dossier in context, local models can
  // emit a SKELETON that just mirrors the plan headings
  // (the live test dropped from ~13k chars solo to ~3.8k in the pipeline). This
  // forces complete, fleshed-out code for every file/section.
  const completenessDirective = [
    '═══════════════════════════════════════════════════════════════',
    'COMPLÉTUDE — NON NÉGOCIABLE',
    '- Génère le code COMPLET et INTÉGRAL de CHAQUE fichier. Pas de squelette,',
    '  pas de résumé du plan, pas de commentaire "<!-- section ici -->" ou "// à compléter".',
    '- CHAQUE section/fonctionnalité demandée est ENTIÈREMENT implémentée : vrai',
    '  contenu (textes réels, pas "lorem"), styles complets, et le JS qui la fait fonctionner.',
    '- Toute interactivité demandée (toggle, accordéon, onglets, carrousel, panier…)',
    '  DOIT avoir son JavaScript complet et fonctionnel (addEventListener, handlers).',
    '- Si tu références un fichier local (style.css, script.js), tu DOIS le générer aussi,',
    '  COMPLET. Ne laisse jamais un <link>/<script> pointer vers un fichier absent.',
    '- Si tu utilises des classes utilitaires Tailwind, inclus <script src="https://cdn.tailwindcss.com"></script>',
    '  dans le <head> ; sinon écris du vrai CSS qui style réellement la page (jamais d\'écran nu).',
    '- Vise un résultat RICHE : pour une page/app complète, plusieurs centaines de lignes.',
    '═══════════════════════════════════════════════════════════════',
    '',
  ].join('\n')
  const userMessage: OllamaMessage = {
    role: 'user',
    content: `${completenessDirective}${designReminder ? `${designReminder}\n` : ''}${prompt}`,
  }
  if (contextImages.length > 0) {
    userMessage.images = contextImages
  }
  messages.push(userMessage)

  // Use array chunks instead of string concatenation to avoid O(n²) memory usage
  // String concatenation creates a new string for every token → can crash on large outputs
  const contentChunks: string[] = []
  const generationSignal = signal
    ? AbortSignal.any([signal, AbortSignal.timeout(STREAM_GENERATION_TOTAL_TIMEOUT_MS)])
    : AbortSignal.timeout(STREAM_GENERATION_TOTAL_TIMEOUT_MS)
  try {
  // v85c : explicit context + output budget, TUNED FOR 16 GB VRAM. The old
  // code passed nothing → Ollama's ~4096 default truncated the stacked CODEUR
  // prompt + plan + existing files, giving simplistic, cut-off projects. The
  // first oversized attempt went too far and OOM'd on the SECOND
  // pipeline run (VRAM tighter) → the resilience layer learned a high memory
  // floor → memory_guard then skipped the model on every retry (storm). 12288
  // expert context starts high and is reduced by resilience if memory is tight.
  // headroom, so it never OOMs → no learned-floor cascade. Big projects are
  // built iteratively across turns, not crammed into one window. Resilience
  // still degrades to 4096/2048 on any OOM and shrinks num_predict with it.
  await resilientOllamaChatStream(
    model,
    messages,
    (token) => {
      contentChunks.push(token)
      onToken(token)
    },
    () => { /* done — resolved by the promise wrapper inside resilient */ },
    {
      signal: generationSignal,
      // Preset officiel Qwen3-Coder (temp 0.7 / top_p 0.8 / top_k 20 / repeat 1.05),
      // abaisse a 0.3 pour du code plus deterministe sans etrangler l'echantillonnage.
      // NB: l'ancien top_p 0.1 etait a la fois trop etroit (boucles de repetition sur
      // un MoE) ET jamais transmis par la couche de resilience — donc sans effet.
      temperature: 0.3,
      top_p: 0.8,
      top_k: 20,
      repeat_penalty: 1.05,
      // Large enough for the system prompt + plan + existing files + a real
      // multi-file output; resilience reduces it if the local runtime OOMs.
      num_ctx: CODE_EXPERT_CONTEXT_TOKENS,
      num_predict: CODE_EXPERT_OUTPUT_TOKENS,
      firstByteTimeoutMs: GENERATION_FIRST_BYTE_TIMEOUT_MS,
      neverMemorySkip: true, // v85c : the routed code model must always run
      onRecoveryAttempt: (ev) => {
        setPhase(`Generation — auto-reparation: ${ev.action}...`, 38)
        onRecovery?.(ev)
      },
    },
  )
  } catch (error) {
    const timedOut = error instanceof DOMException && error.name === 'AbortError' && !signal?.aborted
    if (timedOut) {
      setPhase('Generation time-boxee — poursuite avec le draft partiel...', 44)
      const partialContent = contentChunks.join('')
      // Detect truncation: if the last file section has an unclosed code block, it was cut mid-generation
      const lastFileMarker = partialContent.lastIndexOf('--- FICHIER:')
      if (lastFileMarker > 0) {
        const afterMarker = partialContent.slice(lastFileMarker)
        const openBlocks = (afterMarker.match(/```\w+/g) || []).length
        const closeBlocks = (afterMarker.match(/\n```\s*$/gm) || []).length
        if (openBlocks > closeBlocks) {
          // Truncated file — close it so at least the complete files are parseable
          return partialContent + '\n```\n'
        }
      }
      return partialContent
    }
    throw error
  }

  return contentChunks.join('')
}

/** Calculate a granular score from sandbox results AND content quality */
function computeSandboxScore(sandboxResult: CodeSandboxResult, files: CodeFile[], intent: CodeIntent): number {
  // Content quality gate — if the content itself is garbage, sandbox pass is irrelevant
  const contentScore = computeContentQualityScore(files, intent)
  if (contentScore === 0) return 0   // Refusal or empty → 0% no matter what
  if (contentScore <= 10) return contentScore // Generic/docs-only → cap at 10%

  if (sandboxResult.ok) {
    // Sandbox passed, but cap by content quality
    return Math.min(100, contentScore)
  }

  const totalSteps = sandboxResult.steps.length
  if (totalSteps === 0) return Math.min(contentScore, 50)
  const passingSteps = sandboxResult.steps.filter((s) => s.ok).length
  // Base score from passing ratio (0-80 range)
  const passRatio = passingSteps / totalSteps
  const baseScore = Math.round(passRatio * 80)
  // Bonus points for partial success indicators in failing steps
  const failingOutputs = sandboxResult.steps.filter((s) => !s.ok).map((s) => s.output).join('\n')
  let bonus = 0
  if (/warning/i.test(failingOutputs) && !/error/i.test(failingOutputs)) bonus += 10
  if (/compiled/i.test(failingOutputs) || /built/i.test(failingOutputs)) bonus += 5
  return Math.min(99, baseScore + bonus)
}

function isStaticCritiqueBlocking(report: CritiqueReport): boolean {
  if (report.hasBlocker) return true
  if (report.issues.some((issue) => issue.severity === 'error')) return true
  if (report.scores.compile < 1) return true
  if (report.scores.security < 0.85) return true
  if (report.scores.lint < 0.65) return true
  return false
}

function formatStaticCritiqueReport(report: CritiqueReport): string {
  const scoreLine = [
    `overall=${Math.round(report.overallScore * 100)}%`,
    `compile=${Math.round(report.scores.compile * 100)}%`,
    `lint=${Math.round(report.scores.lint * 100)}%`,
    `security=${Math.round(report.scores.security * 100)}%`,
    `accessibility=${Math.round(report.scores.accessibility * 100)}%`,
  ].join(' | ')

  const issues = report.issues.slice(0, 20).map((issue) => {
    const where = issue.location
      ? `${issue.location.file}${issue.location.line ? `:${issue.location.line}` : ''}`
      : 'projet'
    const suggestion = issue.suggestion ? ` Suggestion: ${issue.suggestion}` : ''
    return `[${issue.severity}] ${where} - ${issue.message}.${suggestion}`
  })

  return [
    scoreLine,
    report.hasBlocker ? 'blocker=true' : 'blocker=false',
    issues.length > 0 ? issues.join('\n') : 'Aucun probleme statique bloquant detecte.',
  ].join('\n')
}

function withStaticCritiqueStep(
  sandboxResult: CodeSandboxResult,
  report: CritiqueReport,
): CodeSandboxResult {
  const blocking = isStaticCritiqueBlocking(report)
  const output = formatStaticCritiqueReport(report)
  const staticStep: CodeSandboxStepResult = {
    label: 'Critique statique Aurora',
    command: 'internal:static-critique',
    ok: !blocking,
    output,
  }

  if (!blocking) {
    return {
      ...sandboxResult,
      steps: [...sandboxResult.steps, staticStep],
    }
  }

  const staticSummary = 'La critique statique a detecte des erreurs de syntaxe, structure, securite ou complexite.'
  return {
    ...sandboxResult,
    ok: false,
    summary: sandboxResult.ok
      ? staticSummary
      : `${sandboxResult.summary}\n${staticSummary}`,
    steps: [...sandboxResult.steps, staticStep],
  }
}

/** Phase 4 + 5: Validation + Auto-correction loop */
async function runValidationAndCorrectionLoop(
  prompt: string,
  initialFiles: CodeFile[],
  intent: CodeIntent,
  preflightReport: CodePreflightReport | null,
  missionDossier: CodeMissionDossier,
  architecturePlan: string | null,
  configuredCodeModel: string,
  setPhase: PhaseCallback,
  onFilesUpdate: (files: CodeFile[], notes: string) => void,
  onValidationUpdate: (result: CodeSandboxResult) => void,
  onCorrectionLogUpdate: (log: CorrectionPass[], attempt: number, score: number) => void,
  signal?: AbortSignal,
): Promise<{
  files: CodeFile[]
  notes: string
  sandboxResult: CodeSandboxResult | null
  correctionLog: CorrectionPass[]
  totalAttempts: number
  finalScore: number
}> {
  let currentFiles = initialFiles
  let currentNotes = ''
  let sandboxResult: CodeSandboxResult | null = null
  const correctionLog: CorrectionPass[] = []
  let attempt = 0
  let lastScore = 0
  let rescueRegenerationUsed = false

  while (true) {
    attempt += 1

    // Check abort
    if (signal?.aborted) break

    // Validate in sandbox
    setPhase(`Sandbox passe ${attempt} — validation en cours...`, Math.min(85, 60 + attempt * 4))
    sandboxResult = await runCodeSandboxValidation({
      files: currentFiles,
      prompt,
      setPhase,
      setProgress: (detail) => setPhase(detail, Math.min(90, 65 + attempt * 4)),
    })

    if (sandboxResult.normalizedFiles && sandboxResult.normalizedFiles.length > 0) {
      const normalizedChanged = sandboxResult.normalizedFiles.length !== currentFiles.length
        || sandboxResult.normalizedFiles.some((file, index) =>
          file.name !== currentFiles[index]?.name || file.content !== currentFiles[index]?.content,
        )
      if (normalizedChanged) {
        currentFiles = sandboxResult.normalizedFiles
        onFilesUpdate(currentFiles, currentNotes)
      }
    }

    setPhase(`Sandbox passe ${attempt} - critique statique du code...`, Math.min(90, 66 + attempt * 4))
    const staticReport = await compositeStaticCritic({
      generationId: `validation-${attempt}`,
      files: currentFiles,
    }, intent)
    sandboxResult = withStaticCritiqueStep(sandboxResult, staticReport)

    const interactive3D = checkInteractive3DFidelity(currentFiles, prompt, intent)
    if (!interactive3D.ok && attempt <= INTERACTIVE_3D_FIDELITY_MAX_PASSES) {
      const fidelitySummary = 'La fidelite 3D interactive demandee est incomplete.'
      sandboxResult = {
        ...sandboxResult,
        ok: false,
        summary: sandboxResult.ok
          ? fidelitySummary
          : `${sandboxResult.summary}\n${fidelitySummary}`,
        steps: [
          ...sandboxResult.steps,
          {
            label: 'Fidelite 3D interactive',
            command: 'interactive-3d-fidelity-gate',
            ok: false,
            output: interactive3D.hint,
          },
        ],
      }
      setPhase(
        `Passe ${attempt} - fidelite 3D incomplete (${interactive3D.missing.join(', ')})...`,
        Math.min(90, 68 + attempt * 4),
      )
    }

    // Deterministic visual gates: a sandbox can say "ok" while a web page is a
    // non-functional shell or a game has no input/game loop. These gates must
    // run before score/strategy calculation so the correction pass can fix them.
    const gamePlay =
      intent.projectType === 'game_web'
        ? checkGamePlayability(currentFiles, prompt)
        : { ok: true, missing: [] as string[], hint: '' }
    if (!gamePlay.ok) {
      const playabilitySummary = `Jeu incomplet: ${gamePlay.missing.join(', ')}.`
      sandboxResult = {
        ...sandboxResult,
        ok: false,
        summary: sandboxResult.ok
          ? playabilitySummary
          : `${sandboxResult.summary}\n${playabilitySummary}`,
        steps: [
          ...sandboxResult.steps,
          {
            label: 'Jouabilité',
            command: 'playability-gate',
            ok: false,
            output: gamePlay.hint,
          },
        ],
      }
      setPhase(
        `Passe ${attempt} - jeu incomplet (${gamePlay.missing.join(', ')}) - correction ciblee...`,
        Math.min(90, 70 + attempt * 4),
      )
    }

    const webIntegrity =
      intent.projectType === 'static_web'
        ? checkWebPageIntegrity(currentFiles, prompt)
        : { ok: true, missing: [] as string[], hint: '' }
    if (!webIntegrity.ok) {
      const integritySummary = `Page non fonctionnelle: ${webIntegrity.missing.join(', ')}.`
      sandboxResult = {
        ...sandboxResult,
        ok: false,
        summary: sandboxResult.ok
          ? integritySummary
          : `${sandboxResult.summary}\n${integritySummary}`,
        steps: [
          ...sandboxResult.steps,
          {
            label: 'Intégrité page',
            command: 'web-integrity-gate',
            ok: false,
            output: webIntegrity.hint,
          },
        ],
      }
      setPhase(
        `Passe ${attempt} - page non fonctionnelle (${webIntegrity.missing.join(', ')}) - correction ciblee...`,
        Math.min(90, 70 + attempt * 4),
      )
    }

    onValidationUpdate(sandboxResult)

    // Calculate score using granular formula + content quality gate
    const currentScore = computeSandboxScore(sandboxResult, currentFiles, intent)

    const errorCategories = sandboxResult.ok ? [] : classifyErrors(sandboxResult)
    const strategy = sandboxResult.ok
      ? null
      : buildCorrectionStrategy(errorCategories, attempt, correctionLog)

    // Trim agressif : on garde max 1.5KB par erreur pour la passe courante
    // (la passe courante est celle que le LLM va lire, donc on a besoin de
    // details). On tronque plus serre que 5KB pour proteger la RAM sur les
    // longues boucles.
    const truncatedErrors = sandboxResult.steps
      .filter((s) => !s.ok)
      .map((s) => s.output.length > 1500
        ? `${s.output.slice(0, 1000)}\n...[tronque: ${s.output.length} chars total]...\n${s.output.slice(-400)}`
        : s.output)

    const pass: CorrectionPass = {
      attempt,
      score: currentScore,
      errors: truncatedErrors,
      strategy: attempt === 1 ? 'initial' : (strategy?.level ?? 'initial'),
      modelUsed: configuredCodeModel,
      resolved: sandboxResult.ok,
    }
    correctionLog.push(pass)

    // Memory release : resume les passes > 4 en arriere en une ligne. Sans ca
    // un long run de 10 passes accumule 10 × 3-5KB d erreurs + retries +
    // metadata qui finit par saturer la RAM (cause #2 de crash PC).
    if (correctionLog.length > 4) {
      for (let i = 0; i < correctionLog.length - 4; i++) {
        const old = correctionLog[i]
        if (old.errors.length > 1 || (old.errors[0] && old.errors[0].length > 200)) {
          correctionLog[i] = {
            ...old,
            errors: [`[passe archivee: ${old.errors.length} erreurs, score ${old.score}%]`],
          }
        }
      }
    }

    // Push real-time update to UI
    onCorrectionLogUpdate([...correctionLog], attempt, currentScore)

    if (sandboxResult.ok) {
      lastScore = 100
      break
    }

    // Environment blocker detection: the sandbox reports that a runtime or
    // toolchain is missing. The user rule is "JAMAIS arreter tant qu il n
    // atteint pas son but" — so we DO NOT break here anymore. Instead we
    // surface the blocker as a warning note on the pass and keep iterating;
    // the Auditeur / web research can still rewrite the project to use a
    // different stack that does not require the missing tool.
    const environmentBlocker = detectEnvironmentBlocker(sandboxResult, errorCategories)
    if (environmentBlocker) {
      pass.errors = [
        `[Blocage environnement detecte - ${environmentBlocker}]`,
        ...pass.errors,
      ]
      setPhase(`Passe ${attempt} - ${environmentBlocker} (le module essaie une stack alternative)...`, Math.min(92, 70 + attempt * 3))
    }

    const localRepair = attemptLocalFileRepair(currentFiles, sandboxResult)
    if (localRepair) {
      currentFiles = localRepair.files
      currentNotes = `${currentNotes ? `${currentNotes}\n\n` : ''}Auto-reparation locale: ${localRepair.reason}`
      onFilesUpdate(currentFiles, currentNotes)
      setPhase(`Passe ${attempt} - auto-reparation locale appliquee.`, Math.min(93, 71 + attempt * 3))
      lastScore = currentScore
      continue
    }

    // Check if we should continue — only exits on score=100 or true infinite
    // loop (same exact error 8+ times). No "plateau" cutoff anymore.
    if (!shouldContinueLoop(correctionLog, attempt, errorCategories)) {
      lastScore = currentScore
      const reason = currentScore >= 100
        ? 'livraison validee a 100%'
        : `boucle infinie detectee sur la meme erreur apres ${attempt} passes`
      setPhase(`Arret de la boucle : ${reason}.`, 92)
      break
    }

    // Auto-correction attempt with clear status
    const correctionModel = selectModel('correction', intent, strategy!.escalation, configuredCodeModel)
    pass.modelUsed = correctionModel
    pass.strategy = strategy!.level
    // Update UI with mutated pass
    onCorrectionLogUpdate([...correctionLog], attempt, currentScore)

    const strategyLabel = strategy!.level.replace(/_/g, ' ')
    const modelShort = getModelShortName(correctionModel)
    setPhase(`Passe ${attempt} — ${strategyLabel} via ${modelShort}...`, Math.min(92, 70 + attempt * 3))

    // At high escalation, search the web for solutions
    let researchContext = ''
    if (strategy!.searchWeb) {
      setPhase(`Passe ${attempt} — recherche de solutions en ligne...`, Math.min(93, 72 + attempt * 3))
      const failingErrors = sandboxResult.steps
        .filter((s) => !s.ok)
        .map((s) => s.output)
        .join('\n')
      try {
        researchContext = await withTimeout(searchForSolution(failingErrors, intent, configuredCodeModel), {
          label: 'Code correction research',
          timeoutMs: RESEARCH_PHASE_TIMEOUT_MS,
        })
      } catch {
        researchContext = ''
      }
    }

    // Analyse de cause racine — activee DES la passe 2 pour comprendre
    // chaque erreur en profondeur, pas seulement quand on est bloque
    let reasoningContext = ''
    const recentScores = correctionLog.slice(-3).map((pass) => pass.score)
    const isFlatlining = recentScores.length >= 3 && Math.max(...recentScores) - Math.min(...recentScores) <= 4
    if (attempt >= 2 || isFlatlining) {
      setPhase(`Passe ${attempt} — analyse de la cause racine...`, Math.min(93, 73 + attempt * 3))
      const currentErrors = sandboxResult.steps
        .filter((s) => !s.ok)
        .map((s) => s.output)
      const reasoning = await analyzeStuckCorrection(
        prompt,
        correctionLog,
        intent,
        currentErrors,
        configuredCodeModel,
      )
      if (reasoning) {
        reasoningContext = buildReasoningInstructions(reasoning)
        setPhase(`Passe ${attempt} — cause identifiee: ${reasoning.rootCause.slice(0, 80)}...`, Math.min(93, 74 + attempt * 3))
      }
    }

    // Regeneration de secours: repart de zero quand strategy_change ou rewrite
    // Autorisee toutes les 4 passes pour ne pas boucler mais donner plusieurs chances
    const rescueEligible = (strategy!.level === 'rewrite' || strategy!.level === 'strategy_change')
      && (!rescueRegenerationUsed || attempt % 4 === 0)
    if (rescueEligible) {
      rescueRegenerationUsed = true
      const failingErrors = sandboxResult.steps
        .filter((step) => !step.ok)
        .map((step) => step.output)
      const rescuePrompt = buildRescueRegenerationPrompt({
        originalPrompt: prompt,
        missionDossier,
        architecturePlan,
        failingSummary: sandboxResult.summary,
        failingErrors,
        reasoningContext,
      })

      setPhase(`Passe ${attempt} â€” regeneration de secours complete...`, Math.min(94, 75 + attempt * 3))
      const rescueResponse = await resilientOllamaGenerate(correctionModel, rescuePrompt, {
        timeoutMs: CORRECTION_TIMEOUT_MS,
        firstByteTimeoutMs: CORRECTION_FIRST_BYTE_TIMEOUT_MS,
        signal,
        num_ctx: CODE_EXPERT_CONTEXT_TOKENS,
        neverMemorySkip: true,
        onRecoveryAttempt: (ev) => {
          setPhase(`Passe ${attempt} â€” sauvetage Ollama: ${ev.action}...`, Math.min(94, 76 + attempt * 3))
        },
      })

      const rescueContent = rescueResponse?.response?.trim() || ''
      const rescueFiles = parseCodeFiles(rescueContent)
      if (rescueFiles.length > 0 && !validateOutputMatchesIntent(rescueFiles, intent)) {
        currentFiles = rescueFiles
        currentNotes = extractNotes(rescueContent)
        onFilesUpdate(currentFiles, currentNotes)
        lastScore = currentScore
        continue
      }
    }

    // Build correction messages
    const correctionMessages = buildCorrectionMessages({
      prompt,
      files: currentFiles,
      validationResult: sandboxResult,
      strategy: strategy!,
      researchContext,
      reasoningContext,
      missionDossier,
      architecturePlan,
      preflightReport,
      intent,
    })

    setPhase(`Passe ${attempt} — ${modelShort} corrige le code...`, Math.min(94, 74 + attempt * 3))
    const repairResponse = await resilientOllamaChat(correctionModel, correctionMessages, 0.05, {
      timeoutMs: CORRECTION_TIMEOUT_MS,
      firstByteTimeoutMs: CORRECTION_FIRST_BYTE_TIMEOUT_MS,
      signal,
      num_ctx: CODE_EXPERT_CONTEXT_TOKENS,
      neverMemorySkip: true,
      onRecoveryAttempt: (ev) => {
        setPhase(`Passe ${attempt} — auto-reparation Ollama: ${ev.action}...`, Math.min(94, 75 + attempt * 3))
      },
    })
    const repairedContent = repairResponse?.message?.content?.trim() || ''
    const repairedFiles = parseCodeFiles(repairedContent)

    if (repairedFiles.length === 0) {
      // Correction produced nothing usable — continue to next strategy
      setPhase(`Passe ${attempt} — correction vide, tentative suivante...`, Math.min(94, 75 + attempt * 3))
      continue
    }

    // Validate the MERGED result, not the correction payload alone. v89b: a
    // legitimate single-file fix (e.g. the model returns only the repaired
    // script.js) used to be rejected here for "index.html absent" — index.html
    // already exists in currentFiles and is preserved by the merge, so the fix
    // was thrown away and the broken/truncated file kept. Validate what we'd
    // actually ship.
    const mergedCandidate = mergeExistingWithUpdates(currentFiles, repairedFiles)
    const correctionIssue = validateOutputMatchesIntent(mergedCandidate, intent)
    if (correctionIssue) {
      setPhase(`Passe ${attempt} — correction invalide (${correctionIssue.slice(0, 50)}...), on garde les fichiers actuels...`, Math.min(94, 76 + attempt * 3))
      continue
    }

    currentFiles = mergedCandidate
    currentNotes = extractNotes(repairedContent)
    onFilesUpdate(currentFiles, currentNotes)
    lastScore = currentScore
  }

  return {
    files: currentFiles,
    notes: currentNotes,
    sandboxResult,
    correctionLog,
    totalAttempts: attempt,
    finalScore: lastScore,
  }
}

// ---------------------------------------------------------------------------
// Correction message builder
// ---------------------------------------------------------------------------

function buildCorrectionMessages({
  prompt,
  files,
  validationResult,
  strategy,
  researchContext,
  reasoningContext,
  missionDossier,
  architecturePlan,
  preflightReport,
  intent,
}: {
  prompt: string
  files: CodeFile[]
  validationResult: CodeSandboxResult
  strategy: CorrectionStrategy
  researchContext: string
  reasoningContext?: string
  missionDossier: CodeMissionDossier
  architecturePlan: string | null
  preflightReport: CodePreflightReport | null
  /** v72: required to evaluate the brand fidelity gate inside the correction prompt. */
  intent: CodeIntent
}): OllamaMessage[] {
  const failingSteps = validationResult.steps
    .filter((step) => !step.ok)
    .slice(0, 5)
    .map((step) => [
      `Step: ${step.label}`,
      `Command: ${step.command}`,
      `Output: ${clipText(step.output || 'aucune sortie exploitable')}`,
    ].join('\n'))
    .join('\n\n')

  // Injecter le system prompt AUDITEUR IMPITOYABLE
  const systemLines = [
    buildAuditeurSystemPrompt(),
    '',
    '---',
    '',
    `Strategie: ${strategy.level} (escalation ${strategy.escalation})`,
    `Instructions: ${strategy.instructions}`,
    '',
    'Avant de toucher au code applicatif, determine si l echec vient du code, d une config locale manquante, d un script faux, d une incompatibilite de version, d un type moderne ou d un runtime absent.',
    'Si le projet utilise TypeScript, verifie d abord tsconfig.json, la version de typescript, les options du compilateur et les types installes.',
    'Ajoute ou corrige les fichiers de configuration locaux obligatoires quand ils manquent, au lieu d heriter implicitement d un dossier parent.',
    'Conserve les fichiers qui n ont pas besoin de changer.',
  ]

  if (/package\.json|json valide|actual JSON|EJSONPARSE|JSONParseError/i.test(validationResult.summary + '\n' + failingSteps)) {
    systemLines.push(
      '',
      'PRIORITE ABSOLUE:',
      '- Corrige les fichiers JSON machine avant toute autre chose.',
      '- package.json doit etre un JSON strict, sans ```json, sans commentaires, sans explication autour.',
    )
  }

  if (isTypeScriptCompatibilityFailure(validationResult.summary + '\n' + failingSteps)) {
    systemLines.push(
      '',
      'PRIORITE COMPATIBILITE TYPESCRIPT:',
      '- Cherche une incompatibilite entre la version de typescript, tsconfig.json et les declarations .d.ts installees.',
      '- Si typescript est trop ancien pour les types/config actuels, monte la version du compilateur a un niveau compatible.',
      '- Si tsconfig.json manque, cree une configuration locale explicite au lieu de laisser tsc remonter dans les dossiers parents.',
    )
  }

  if (strategy.level === 'rewrite' || strategy.level === 'strategy_change') {
    systemLines.push(
      '',
      'ATTENTION: Les corrections precedentes ont echoue.',
      strategy.level === 'strategy_change'
        ? 'Change completement d approche: simplifie l architecture, utilise des patterns differents, change de librairies si necessaire.'
        : 'Reecris les fichiers problematiques completement. Ne te contente pas de patcher.',
    )
  }

  const userLines = [
    `Mission originale:\n${prompt}`,
    `Le sandbox a echoue:\n${validationResult.summary}`,
    failingSteps ? `Erreurs:\n${failingSteps}` : '',
    `Dossier executif:\n${serializeCodeMissionDossier(missionDossier)}`,
    architecturePlan ? `Plan d architecture de reference:\n${clipText(architecturePlan, 2200)}` : '',
    preflightReport ? `Preflight local:\n${serializeCodePreflightReport(preflightReport)}` : '',
  ]

  if (researchContext) {
    userLines.push(`\nSolutions trouvees en ligne:\n${researchContext}`)
  }

  if (reasoningContext) {
    userLines.push(`\n${reasoningContext}`)
  }

  // v67: si le projet est visuel (web/UI) ET le design polish est faible,
  // injecter le retry hint cible AVANT la consigne de correction. Le LLM
  // verra alors clairement quels patterns design il a oublies, en plus
  // des erreurs sandbox.
  const isVisual = files.length > 0 && files.some((f) => /\.(html?|css|s?css|tsx?|jsx?|vue|svelte)$/i.test(f.name))
  if (isVisual) {
    const designReport = computeDesignPolishReport(files)
    if (designReport.score < 70) {
      userLines.push('', buildDesignRetryHint(designReport))
    }
  }

  // v72: brand fidelity retry hint — quand le sujet est une marque connue
  // ET la gate de fidelite signale `shouldRetry`, injecter le hint cible
  // avec les regles violees pour que la correction ne se contente pas de
  // patcher la sandbox mais aussi reverrouille le sujet/palette/markers.
  const brandSubject = intent.assetPlan?.subject
  if (brandSubject?.source === 'brand' && brandSubject.brandProfile) {
    const brandReport = evaluateBrandFidelity(intent, files)
    if (brandReport.shouldRetry || brandReport.scorePenalty >= 15 || brandReport.scoreCap !== null) {
      const hintBlock = [
        '## RAPPEL VERROUILLAGE SUJET (FIDELITE BRAND ECHOUEE)',
        '',
        `Le sujet de cette page est ${brandSubject.canonical}. La gate de fidelite a detecte ces violations:`,
        brandReport.retryHint || '(pas de detail)',
        '',
        'A appliquer dans cette passe de correction:',
        `- Le mot "${brandSubject.canonical}" doit apparaitre dans <title>, <h1> du hero, et au moins 3 sections.`,
        brandSubject.brandProfile.primaryColor ? `- La couleur ${brandSubject.brandProfile.primaryColor} doit etre presente dans les CSS variables et utilisee pour les CTAs/accents.` : '',
        brandSubject.brandProfile.productKeywords.length ? `- Au moins 2 mots-cles produit (${brandSubject.brandProfile.productKeywords.slice(0, 4).join(', ')}) doivent apparaitre dans les titres ou paragraphes.` : '',
        '- Les markers PLACEHOLDER_SUBJECT_IMG / _1 / _2 doivent etre utilises dans les balises <img>.',
        '- Pas de derive vers un sujet adjacent (restaurant generique, blog editorial, SaaS abstrait).',
      ].filter(Boolean).join('\n')
      userLines.push('', hintBlock)
    }
  }

  userLines.push(
    '',
    'Corrige le projet complet. Modifie seulement ce qui est necessaire.',
    `\nFichiers actuels:\n${serializeCodeFiles(files)}`,
  )

  return [
    { role: 'system', content: systemLines.join('\n') },
    { role: 'user', content: userLines.filter(Boolean).join('\n\n') },
  ]
}

// ---------------------------------------------------------------------------
// Output validation — detect when LLM produced docs instead of code
// ---------------------------------------------------------------------------

const DOCUMENTATION_EXTENSIONS = new Set(['md', 'txt', 'doc', 'docx', 'pdf', 'rtf'])
const WEB_CODE_EXTENSIONS = new Set(['html', 'htm', 'css', 'scss', 'less', 'js', 'jsx', 'ts', 'tsx', 'vue', 'svelte', 'astro'])
const API_CODE_EXTENSIONS = new Set(['py', 'js', 'ts', 'go', 'rs', 'java', 'rb', 'php', 'cs', 'ex', 'kt'])
const WEB_RUNTIME_MANIFESTS = new Set([
  'go.mod',
  'go.sum',
  'pom.xml',
  'build.gradle',
  'build.gradle.kts',
  'composer.json',
  'gemfile',
  'requirements.txt',
  'manage.py',
])

function validateStructuredFiles(files: CodeFile[]): string | null {
  for (const file of files) {
    const normalized = file.name.replace(/\\/g, '/').toLowerCase()
    if (!normalized.endsWith('.json')) continue

    const parsed = tryParseJson(stripFormattingArtifacts(file.content))
    if (!parsed) {
      return `${file.name} n est pas un JSON valide. Les fichiers machine comme package.json doivent etre du JSON pur, sans backticks markdown ni texte parasite.`
    }

    if (normalized === 'package.json') {
      const packageName = parsed.name
      if (typeof packageName !== 'string' || packageName.trim().length === 0) {
        return 'package.json est present mais son champ "name" est invalide ou vide.'
      }
    }
  }

  return null
}

type LocalNodeManifest = {
  dependencies?: Record<string, string>
  devDependencies?: Record<string, string>
  optionalDependencies?: Record<string, string>
  peerDependencies?: Record<string, string>
  [key: string]: unknown
}

function upsertGeneratedFile(files: CodeFile[], nextFile: CodeFile) {
  const normalizedTarget = nextFile.name.replace(/\\/g, '/').toLowerCase()
  const existingIndex = files.findIndex((file) => file.name.replace(/\\/g, '/').toLowerCase() === normalizedTarget)
  if (existingIndex < 0) {
    return [...files, nextFile]
  }

  return files.map((file, index) => (index === existingIndex ? nextFile : file))
}

function isTypeScriptCompatibilityFailure(rawOutput: string) {
  return /ReferenceNode\.d\.ts|PropertyNode\.d\.ts|@types\/three|type parameter declaration expected|error TS1139|error TS6046|Unknown compiler option 'allowImportingTsExtensions'|moduleResolution' option must be/i.test(rawOutput)
}

function repairLocalTypeScriptCompatibility(files: CodeFile[], failingOutput: string) {
  if (!isTypeScriptCompatibilityFailure(failingOutput)) {
    return null
  }

  const packageFile = files.find((file) => file.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  if (!packageFile) {
    return null
  }

  const manifest = tryParseJson(stripFormattingArtifacts(packageFile.content)) as LocalNodeManifest | null
  if (!manifest) {
    return null
  }

  const currentTypeScriptSpec = readManifestDependencySpec(manifest, 'typescript')
  if (currentTypeScriptSpec && !isVersionBelow(currentTypeScriptSpec, 5, 2)) {
    return null
  }

  const nextManifest: LocalNodeManifest = {
    ...manifest,
    devDependencies: {
      ...((manifest.devDependencies && typeof manifest.devDependencies === 'object')
        ? manifest.devDependencies
        : {}),
      typescript: '^5.2.0',
    },
  }

  const nextFiles = upsertGeneratedFile(files, {
    ...packageFile,
    content: `${JSON.stringify(nextManifest, null, 2)}\n`,
  })

  return {
    files: nextFiles,
    reason: currentTypeScriptSpec
      ? `mise a niveau automatique de TypeScript (${currentTypeScriptSpec} -> ^5.2.0) pour resoudre une incompatibilite compilateur/types`
      : 'ajout automatique de TypeScript ^5.2.0 pour resoudre une incompatibilite compilateur/types',
  }
}

function attemptLocalFileRepair(files: CodeFile[], sandboxResult: CodeSandboxResult) {
  const failingOutput = sandboxResult.steps
    .filter((step) => !step.ok)
    .map((step) => step.output)
    .join('\n')

  const sanitizedFiles = sanitizeGeneratedFiles(files)
  const changed = sanitizedFiles.some((file, index) =>
    file.name !== files[index]?.name || file.content !== files[index]?.content,
  )

  if (changed) {
    const structuredIssue = validateStructuredFiles(sanitizedFiles)
    if (!structuredIssue) {
      return {
        files: sanitizedFiles,
        reason: 'normalisation locale des fichiers machine et dependances declarees',
      }
    }
  }

  return repairLocalTypeScriptCompatibility(sanitizedFiles, failingOutput)
}

function validateOutputMatchesIntent(files: CodeFile[], intent: CodeIntent): string | null {
  if (files.length === 0) return 'Aucun fichier genere.'

  // Check for LLM refusal in any file content
  const refusalFile = files.find((f) => isLLMRefusal(f.content))
  if (refusalFile) {
    return `Le fichier "${refusalFile.name}" contient un refus du modele au lieu de code source. Le modele doit GENERER du code, pas s excuser.`
  }

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())

  // Check if ALL files are documentation (no code files at all)
  const allDocs = files.every((f) => {
    const ext = f.name.split('.').pop()?.toLowerCase() || ''
    return DOCUMENTATION_EXTENSIONS.has(ext)
  })
  if (allDocs) {
    return 'Tous les fichiers sont des documents (md, txt) — aucun code source. Le module doit produire des FICHIERS DE CODE, pas de documentation.'
  }

  // Check if files have generic fallback names (bloc-1, module-2, script-3)
  // — means the model did not follow the required file header contract.
  const allGeneric = files.every((f) => isSyntheticFallbackFile(f.name))
  if (allGeneric) {
    return 'Les fichiers ont des noms generiques (bloc-1, module-2, script-3) — le format --- FICHIER: nom.ext --- n a pas ete suivi. Regenere avec des chemins reels comme package.json, index.html, src/App.tsx.'
  }

  const structuredIssue = validateStructuredFiles(files)
  if (structuredIssue) {
    return structuredIssue
  }

  if (intent.projectType === 'desktop_tauri') {
    const hasTauriFolder = normalizedNames.some((name) => name.startsWith('src-tauri/'))
    const hasCargoManifest = normalizedNames.some((name) => name === 'src-tauri/cargo.toml')
    const hasTauriConfig = normalizedNames.some((name) => name === 'src-tauri/tauri.conf.json')
    const hasRustEntry = normalizedNames.some((name) => /^src-tauri\/src\/.+\.rs$/i.test(name))
    const hasFrontendEntry = normalizedNames.some((name) =>
      name === 'package.json'
      || name === 'index.html'
      || /^src\/.+\.(ts|tsx|js|jsx|html|css)$/i.test(name),
    )

    if (!hasTauriFolder || !hasCargoManifest || !hasTauriConfig || !hasRustEntry || !hasFrontendEntry) {
      return 'Projet desktop Tauri detecte mais la sortie ne contient pas une vraie structure applicative native complete (frontend + src-tauri + Rust + config Tauri).'
    }
  }

  if (intent.projectType === 'desktop_electron') {
    const hasPackageJson = normalizedNames.includes('package.json')
    const hasElectronMain = normalizedNames.some((name) =>
      /(^|\/)(main|electron\.main|background)\.(js|ts)$/i.test(name),
    )
    const hasRenderer = normalizedNames.some((name) =>
      name === 'index.html'
      || /^src\/.+\.(ts|tsx|js|jsx|html|css)$/i.test(name),
    )

    if (!hasPackageJson || !hasElectronMain || !hasRenderer) {
      return 'Projet desktop Electron detecte mais la sortie ne contient pas une vraie structure desktop complete (package.json + process principal Electron + renderer).'
    }
  }

  // Web project should have at least one HTML or framework file
  const isWebProject = intent.projectType.startsWith('spa_') ||
    intent.projectType.startsWith('ssr_') ||
    intent.projectType === 'static_web' ||
    intent.projectType === 'game_web'

  if (isWebProject) {
    const unexpectedRuntimeFiles = normalizedNames.filter((name) =>
      name.startsWith('src-tauri/')
      || WEB_RUNTIME_MANIFESTS.has(name)
      || name.endsWith('.go')
      || name.endsWith('.rs'),
    )

    if (!intent.projectType.startsWith('fullstack_') && unexpectedRuntimeFiles.length > 0) {
      return `Projet web detecte (${intent.projectType}) mais la sortie embarque des runtimes hors sujet (${unexpectedRuntimeFiles.slice(0, 3).join(', ')}). Regenerer un vrai projet web, pas du Go/Rust/backend parasite.`
    }

    const hasWebFile = files.some((f) => {
      const ext = f.name.split('.').pop()?.toLowerCase() || ''
      return WEB_CODE_EXTENSIONS.has(ext)
    })
    if (!hasWebFile) {
      return `Projet web detecte (${intent.projectType}) mais aucun fichier web (html, css, js, tsx...) trouve. Genere les vrais fichiers source du projet.`
    }

    if (intent.projectType === 'static_web') {
      const hasIndexHtml = normalizedNames.includes('index.html')
      // v85d : a static_web brief sometimes yields a richer framework project
      // (Astro / Vue / Svelte SFC). That is valid, more-complex web output — it
      // just needs a build step instead of a raw index.html. Accept it rather
      // than burning 3 retries (a 12B rarely downgrades to plain HTML on retry,
      // so rejecting just wastes time before the best-attempt fallback delivers
      // the same Astro project anyway).
      const hasFrameworkWebEntry = normalizedNames.some((name) =>
        /\.(astro|vue|svelte)$/i.test(name)
        || /^src\/pages\//i.test(name)
        || /astro\.config\.(mjs|js|ts)$/i.test(name))
      const hasRuntimeReadyJavascript = normalizedNames.some((name) => /\.(js|mjs|cjs)$/i.test(name))
      const hasRawTypeScriptOnly = normalizedNames.some((name) => /\.(ts|tsx)$/i.test(name)) && !hasRuntimeReadyJavascript

      if (!hasIndexHtml && !hasFrameworkWebEntry) {
        return 'Page web statique detectee mais `index.html` est absent. La preview et le lancement navigateur ont besoin d un vrai point d entree HTML.'
      }

      if (hasRawTypeScriptOnly && !hasFrameworkWebEntry) {
        return 'Page web statique detectee mais la sortie contient du TypeScript brut sans JavaScript transpile. Fournis une page HTML/CSS/JS directement executable.'
      }
    }

    if (intent.projectType.startsWith('spa_') || intent.projectType.startsWith('ssr_')) {
      const hasPackageManifest = normalizedNames.some((name) => name.endsWith('package.json'))
      if (!hasPackageManifest) {
        return `Projet ${intent.projectType} detecte mais aucun package.json n est present. Le dev server et la preview ne pourront pas demarrer correctement.`
      }
    }
  }

  // API project should have actual server code
  const isApiProject = intent.projectType.startsWith('api_') || intent.projectType.startsWith('fullstack_')
  if (isApiProject) {
    const hasCodeFile = files.some((f) => {
      const ext = f.name.split('.').pop()?.toLowerCase() || ''
      return API_CODE_EXTENSIONS.has(ext)
    })
    if (!hasCodeFile) {
      return `Projet API detecte (${intent.projectType}) mais aucun fichier code serveur trouve. Genere les vrais fichiers source.`
    }
  }

  // Check if files are too small (likely stubs or descriptions)
  const avgContentLength = files.reduce((sum, f) => sum + f.content.length, 0) / files.length
  if (avgContentLength < 50 && files.length <= 2) {
    return 'Les fichiers generes sont trop courts (< 50 caracteres en moyenne) — probablement des stubs. Genere du code complet et fonctionnel.'
  }

  return null // Output looks valid
}

type ProjectRunbook = {
  installSteps: string[]
  runSteps: string[]
}

function buildProjectRunbook(files: CodeFile[], intent: CodeIntent): ProjectRunbook {
  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasPackageJson = normalizedNames.some((name) => name.endsWith('package.json'))
  const hasRequirements = normalizedNames.includes('requirements.txt')
  const hasCargo = normalizedNames.some((name) => name.endsWith('cargo.toml'))
  const hasIndexHtml = normalizedNames.includes('index.html')
  const pythonEntry = files.find((file) => /(^|\/)(main|app)\.py$/i.test(file.name.replace(/\\/g, '/')))
  const runCommand = intent.devCommand || intent.buildCommand

  if (intent.projectType === 'static_web' || intent.projectType === 'game_web') {
    return {
      installSteps: ['Aucune installation requise.'],
      runSteps: [
        hasIndexHtml ? 'Ouvrir `index.html` dans un navigateur.' : 'Le projet doit fournir un `index.html` pour la preview.',
      ],
    }
  }

  if (
    intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType === 'fullstack_mern'
    || intent.projectType === 'fullstack_nextjs'
    || intent.projectType === 'desktop_electron'
    || intent.projectType === 'desktop_tauri'
    || intent.projectType === 'api_express'
    || intent.projectType === 'cli_node'
    || intent.projectType === 'library_npm'
    || hasPackageJson
  ) {
    const resolvedRunCommand = runCommand || (hasPackageJson ? 'npm start' : 'npm run dev')
    const installSteps = ['```bash', 'npm install', '```']
    if (intent.projectType === 'desktop_tauri' && hasCargo) {
      installSteps.push('', '```bash', 'cargo build', '```')
    }
    return {
      installSteps,
      runSteps: ['```bash', resolvedRunCommand, '```'],
    }
  }

  if (
    intent.projectType === 'api_fastapi'
    || intent.projectType === 'api_django'
    || intent.projectType === 'api_flask'
    || intent.projectType === 'fullstack_django'
    || intent.projectType === 'cli_python'
    || intent.projectType === 'data_python'
  ) {
    const resolvedRunCommand = runCommand || (pythonEntry ? `python ${pythonEntry.name}` : 'python main.py')
    return {
      installSteps: hasRequirements
        ? ['```bash', 'pip install -r requirements.txt', '```']
        : ['Installer Python 3.11+ puis les dependances du projet.'],
      runSteps: ['```bash', resolvedRunCommand, '```'],
    }
  }

  if (intent.projectType === 'api_actix' || intent.projectType === 'cli_rust' || intent.projectType === 'system_rust' || intent.projectType === 'library_crate') {
    const resolvedRunCommand = runCommand || 'cargo run'
    return {
      installSteps: ['```bash', 'cargo build', '```'],
      runSteps: ['```bash', resolvedRunCommand, '```'],
    }
  }

  if (intent.projectType === 'api_gin' || intent.projectType === 'cli_go') {
    const resolvedRunCommand = runCommand || 'go run .'
    return {
      installSteps: ['```bash', 'go mod tidy', '```'],
      runSteps: ['```bash', resolvedRunCommand, '```'],
    }
  }

  return {
    installSteps: ['Voir les fichiers de configuration du projet pour les dependances exactes.'],
    runSteps: ['Consulter le code livre et le README pour lancer manuellement le projet.'],
  }
}

function buildLinuxLaunchScriptLines(files: CodeFile[], intent: CodeIntent): string[] {
  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasPackageJson = normalizedNames.some((name) => name.endsWith('package.json'))
  const hasRequirements = normalizedNames.includes('requirements.txt')
  const hasCargo = normalizedNames.some((name) => name.endsWith('cargo.toml'))
  const pythonEntry = files.find((file) => /(^|\/)(main|app)\.py$/i.test(file.name.replace(/\\/g, '/')))
  const runCommand = intent.devCommand || intent.buildCommand

  if (intent.projectType === 'static_web') return []

  if (
    intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType === 'fullstack_mern'
    || intent.projectType === 'fullstack_nextjs'
    || intent.projectType === 'desktop_electron'
    || intent.projectType === 'desktop_tauri'
    || intent.projectType === 'api_express'
    || intent.projectType === 'cli_node'
    || intent.projectType === 'library_npm'
    || hasPackageJson
  ) {
    const resolvedRunCommand = runCommand || (hasPackageJson ? 'npm start' : 'npm run dev')
    const lines = [
      '#!/usr/bin/env bash',
      'set -euo pipefail',
      'cd "$(dirname "$0")"',
      'if ! command -v npm >/dev/null 2>&1; then echo "Node.js avec npm est requis." >&2; exit 1; fi',
      'if [ ! -d "node_modules" ]; then npm install; fi',
    ]
    if (intent.projectType === 'desktop_tauri' && hasCargo) {
      lines.push('if ! command -v cargo >/dev/null 2>&1; then echo "Rust/Cargo est requis pour Tauri." >&2; exit 1; fi')
    }
    lines.push(resolvedRunCommand)
    return lines
  }

  if (
    intent.projectType === 'api_fastapi'
    || intent.projectType === 'api_django'
    || intent.projectType === 'api_flask'
    || intent.projectType === 'fullstack_django'
    || intent.projectType === 'cli_python'
    || intent.projectType === 'data_python'
  ) {
    const resolvedRunCommand = runCommand || (pythonEntry ? `python ${pythonEntry.name}` : 'python main.py')
    const lines = [
      '#!/usr/bin/env bash',
      'set -euo pipefail',
      'cd "$(dirname "$0")"',
      'command -v python >/dev/null 2>&1 || { echo "Python est requis." >&2; exit 1; }',
    ]
    if (hasRequirements) lines.push('python -m pip install -r requirements.txt')
    lines.push(resolvedRunCommand)
    return lines
  }

  if (intent.projectType === 'api_actix' || intent.projectType === 'cli_rust' || intent.projectType === 'system_rust' || intent.projectType === 'library_crate') {
    return [
      '#!/usr/bin/env bash',
      'set -euo pipefail',
      'cd "$(dirname "$0")"',
      'command -v cargo >/dev/null 2>&1 || { echo "Rust/Cargo est requis." >&2; exit 1; }',
      runCommand || 'cargo run',
    ]
  }

  if (intent.projectType === 'api_gin' || intent.projectType === 'cli_go') {
    return [
      '#!/usr/bin/env bash',
      'set -euo pipefail',
      'cd "$(dirname "$0")"',
      'command -v go >/dev/null 2>&1 || { echo "Go est requis." >&2; exit 1; }',
      'go mod tidy',
      runCommand || 'go run .',
    ]
  }

  return []
}

function generateLinuxLaunchScript(files: CodeFile[], intent: CodeIntent): CodeFile | null {
  const hasLaunchScript = files.some((f) => /^(start|launch|lancement)\.(sh|bat)$/i.test(f.name.replace(/.*[/\\]/, '')))
  if (hasLaunchScript) return null

  const lines = buildLinuxLaunchScriptLines(files, intent)
  if (lines.length === 0) return null

  return {
    name: 'start.sh',
    language: 'bash',
    content: lines.join('\n'),
  }
}

/**
 * Some local models spray Tailwind utility
 * classes (flex, grid, text-5xl, bg-…) WITHOUT including Tailwind and without
 * generating the matching CSS → an unstyled BLACK page. If an HTML file uses
 * Tailwind utilities but ships no Tailwind, inject the Play CDN + a dark-mode
 * config so the page actually renders. No-op when the model wrote real CSS or
 * already included Tailwind.
 */
function ensureTailwindCDN(files: CodeFile[], projectType?: string): CodeFile[] {
  // A canvas game is self-styled (inline <style> + canvas draw calls) and never
  // needs Tailwind. The utility-class heuristic below false-positives on plain
  // class names like "container", injecting a ~2 KB marketing theme + an external
  // CDN script as dead weight. Skip it for games entirely.
  if (projectType === 'game_web') return files
  const TW_UTIL = /class="[^"]*\b(flex|grid|hidden|container|mx-auto|justify-\w+|items-\w+|text-(xs|sm|base|lg|xl|\dxl|center|fg|accent)|bg-[a-z]+(-\d{2,3})?|[pmgw][xytblr]?-\d|gap-\d|rounded(-\w+)?|shadow(-\w+)?|font-(bold|semibold|medium)|grid-cols-\d)\b/
  const HAS_TW = /cdn\.tailwindcss\.com|@tailwind\b/
  // v85g : local models spray SEMANTIC Tailwind tokens (bg-surface, text-fg,
  // text-fg-dim, bg-accent, shadow-2…) that need a config to be defined —
  // without it the classes resolve to NOTHING → unstyled/black page. We inject
  // the Play CDN + a CSS-variable theme + a Tailwind config that defines that
  // exact vocabulary, with light/dark wired to [data-theme="dark"]/.dark AND
  // prefers-color-scheme, so the page renders styled and the dark toggle works.
  const inject = [
    '<style data-aurora-theme>',
    ':root{--c-surface:255 255 255;--c-surface-elevated:248 247 245;--c-card:255 255 255;--c-fg:23 23 23;--c-fg-dim:90 92 100;--c-fg-mute:140 142 150;--c-line:230 230 234;--c-accent:124 92 255;--c-accent-soft:139 110 255}',
    '[data-theme="dark"],.dark{--c-surface:12 11 16;--c-surface-elevated:24 24 30;--c-card:22 22 28;--c-fg:240 240 245;--c-fg-dim:170 172 180;--c-fg-mute:120 122 130;--c-line:42 42 50;--c-accent:160 140 255;--c-accent-soft:175 155 255}',
    '@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--c-surface:12 11 16;--c-surface-elevated:24 24 30;--c-card:22 22 28;--c-fg:240 240 245;--c-fg-dim:170 172 180;--c-fg-mute:120 122 130;--c-line:42 42 50;--c-accent:160 140 255;--c-accent-soft:175 155 255}}',
    'body{background:rgb(var(--c-surface));color:rgb(var(--c-fg));transition:background .3s ease,color .3s ease}',
    '</style>',
    '<script src="https://cdn.tailwindcss.com"></script>',
    '<script>tailwind.config={darkMode:["selector",\'[data-theme="dark"]\'],theme:{extend:{colors:{'
    + 'surface:{DEFAULT:"rgb(var(--c-surface) / <alpha-value>)",elevated:"rgb(var(--c-surface-elevated) / <alpha-value>)"},'
    + 'card:"rgb(var(--c-card) / <alpha-value>)",line:"rgb(var(--c-line) / <alpha-value>)",'
    + 'fg:{DEFAULT:"rgb(var(--c-fg) / <alpha-value>)",dim:"rgb(var(--c-fg-dim) / <alpha-value>)",mute:"rgb(var(--c-fg-mute) / <alpha-value>)"},'
    + 'accent:{DEFAULT:"rgb(var(--c-accent) / <alpha-value>)",soft:"rgb(var(--c-accent-soft) / <alpha-value>)"}},'
    + 'boxShadow:{2:"0 4px 16px rgb(0 0 0 / 0.08)",3:"0 12px 32px rgb(0 0 0 / 0.14)"}}}};</script>',
  ].join('\n')
  return files.map((f) => {
    if (!/\.html?$/i.test(f.name)) return f
    const c = f.content
    if (!TW_UTIL.test(c) || HAS_TW.test(c)) return f
    let next = c
    if (/<\/head>/i.test(next)) next = next.replace(/<\/head>/i, `${inject}\n</head>`)
    else if (/<head[^>]*>/i.test(next)) next = next.replace(/<head[^>]*>/i, (m) => `${m}\n${inject}`)
    else next = `${inject}\n${next}`
    return { ...f, content: next }
  })
}

function ensureSpaIndexHtml(files: CodeFile[], intent: CodeIntent): CodeFile[] {
  if (!intent.projectType.startsWith('spa_')) return files

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  if (normalizedNames.includes('index.html')) return files

  const entry = [
    'src/main.tsx',
    'src/main.jsx',
    'src/main.ts',
    'src/main.js',
    'src/index.tsx',
    'src/index.jsx',
    'src/index.ts',
    'src/index.js',
    'main.tsx',
    'main.jsx',
    'main.ts',
    'main.js',
    'index.tsx',
    'index.jsx',
    'index.ts',
    'index.js',
  ].find((candidate) => normalizedNames.includes(candidate))

  if (!entry) return files

  const title = intent.projectType.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
  const html = [
    '<!doctype html>',
    '<html lang="en">',
    '  <head>',
    '    <meta charset="UTF-8" />',
    '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />',
    `    <title>${title}</title>`,
    '  </head>',
    '  <body>',
    '    <div id="root"></div>',
    `    <script type="module" src="/${entry}"></script>`,
    '  </body>',
    '</html>',
    '',
  ].join('\n')

  return [
    ...files,
    {
      name: 'index.html',
      language: 'html',
      content: html,
    },
  ]
}

function ensureSpaViteConfig(files: CodeFile[], intent: CodeIntent): CodeFile[] {
  if (!intent.projectType.startsWith('spa_')) return files

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  if (normalizedNames.some((name) => /^vite\.config\.(?:ts|js|mjs|mts)$/.test(name))) return files

  return [
    ...files,
    {
      name: 'vite.config.ts',
      language: 'typescript',
      content: [
        "import { defineConfig } from 'vite'",
        "import react from '@vitejs/plugin-react'",
        '',
        'export default defineConfig({',
        '  plugins: [react()],',
        '  server: {',
        "    host: '127.0.0.1',",
        '    port: 5173,',
        '  },',
        '})',
        '',
      ].join('\n'),
    },
  ]
}

function fileSet(files: CodeFile[]) {
  return new Set(files.map((file) => file.name.replace(/\\/g, '/').toLowerCase()))
}

function projectUsesTailwindTooling(files: CodeFile[]) {
  const names = fileSet(files)
  if ([...names].some((name) => /(^|\/)tailwind\.config\.(?:js|cjs|mjs|ts)$/.test(name))) return true
  if (files.some((file) => /@tailwind\b|@apply\b/.test(file.content))) return true

  const packageFile = files.find((file) => file.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  if (!packageFile) return false
  const manifest = tryParseJson(stripFormattingArtifacts(packageFile.content))
  return Boolean(manifest && manifestUsesPackage(manifest, 'tailwindcss'))
}

function ensureTailwindTooling(files: CodeFile[]) {
  if (!projectUsesTailwindTooling(files)) return files
  const names = fileSet(files)
  let nextFiles = files

  const packageIndex = nextFiles.findIndex((file) => file.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  if (packageIndex >= 0) {
    const manifest = tryParseJson(stripFormattingArtifacts(nextFiles[packageIndex].content))
    if (manifest) {
      let nextManifest = upsertPackageDevDependency(manifest, 'tailwindcss', '^3.4.17', true)
      nextManifest = upsertPackageDevDependency(nextManifest, 'postcss', '^8.5.6', true)
      nextManifest = upsertPackageDevDependency(nextManifest, 'autoprefixer', '^10.4.21', true)
      nextFiles = nextFiles.map((file, index) => index === packageIndex
        ? { ...file, content: `${JSON.stringify(nextManifest, null, 2)}\n` }
        : file)
    }
  }

  if (names.has('postcss.config.js') || names.has('postcss.config.cjs') || names.has('postcss.config.mjs')) {
    return nextFiles
  }

  return [
    ...nextFiles,
    {
      name: 'postcss.config.js',
      language: 'javascript',
      content: [
        'export default {',
        '  plugins: {',
        '    tailwindcss: {},',
        '    autoprefixer: {},',
        '  },',
        '}',
        '',
      ].join('\n'),
    },
  ]
}

function isSyntheticFallbackFile(name: string): boolean {
  const normalized = name.replace(/\\/g, '/').toLowerCase()
  return /^(?:module|script|style|page|bloc)-\d+\.[a-z0-9]+$/.test(normalized)
    || /^output\.[a-z0-9]+$/.test(normalized)
    || /^reponse\.(?:txt|text|md)$/.test(normalized)
}

function stripSyntheticFallbackFiles(files: CodeFile[], intent: CodeIntent): CodeFile[] {
  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasStructuredProject =
    normalizedNames.includes('package.json')
    || normalizedNames.includes('index.html')
    || normalizedNames.some((name) => name.startsWith('src/'))

  if (!hasStructuredProject) return files

  const shouldStrip = intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType.startsWith('fullstack_')
    || intent.projectType.startsWith('api_')
    || intent.needsDevServer
    || intent.needsBundling

  if (!shouldStrip) return files
  return files.filter((file) => !isSyntheticFallbackFile(file.name))
}

function upsertProjectSupportFiles(
  files: CodeFile[],
  intent: CodeIntent,
  prompt: string,
  architecturePlan: string | null,
): CodeFile[] {
  const strippedFiles = ensureTailwindCDN(files, intent.projectType).filter((file) => {
    const name = file.name.replace(/\\/g, '/').toLowerCase()
    return name !== 'readme.md' && name !== 'start.sh' && !name.endsWith('.bat')
  })
  const baseFiles = ensureSpaViteConfig(
    ensureSpaIndexHtml(stripSyntheticFallbackFiles(strippedFiles, intent), intent),
    intent,
  )
  const supportedFiles = ensureTailwindTooling(baseFiles)

  const nextFiles = [...supportedFiles, generateReadme(supportedFiles, intent, prompt, architecturePlan)]
  const launchScript = generateLinuxLaunchScript(supportedFiles, intent)
  if (launchScript) nextFiles.push(launchScript)

  return nextFiles
}

export function upsertProjectSupportFilesForTest(
  files: CodeFile[],
  intent: CodeIntent,
  prompt = '',
  architecturePlan: string | null = null,
) {
  return upsertProjectSupportFiles(files, intent, prompt, architecturePlan)
}

// ---------------------------------------------------------------------------
// Main orchestration entry point
// ---------------------------------------------------------------------------

export async function orchestrateCodeGeneration({
  prompt,
  enrichedPrompt,
  conversationHistory,
  existingFiles,
  contextImages,
  userFileDataUrls,
  configuredCodeModel,
  visionModel,
  setPhase,
  onToken,
  onFilesUpdate,
  onValidationUpdate,
  onCorrectionLogUpdate,
  onRecoveryEvent,
  onFollowUpAnalysis,
  signal,
}: {
  prompt: string
  enrichedPrompt: string
  conversationHistory: OllamaMessage[]
  existingFiles: CodeFile[]
  contextImages: string[]
  /** Map of placeholder → data URL for user-attached files (USER_FILE_0 → data:image/jpeg;base64,...) */
  userFileDataUrls?: Record<string, string>
  configuredCodeModel: string
  visionModel: string
  setPhase: PhaseCallback
  onToken: (token: string) => void
  onFilesUpdate: (files: CodeFile[], notes: string) => void
  onValidationUpdate: (result: CodeSandboxResult) => void
  onCorrectionLogUpdate: (log: CorrectionPass[], attempt: number, score: number) => void
  onRecoveryEvent?: (event: RecoveryEvent) => void
  /** Fires as soon as the follow-up analyzer has decided the pivot kind. */
  onFollowUpAnalysis?: (analysis: FollowUpAnalysis) => void
  signal?: AbortSignal
}): Promise<CodeOrchestrationResult> {
  const generationModel = contextImages.length > 0 ? visionModel : configuredCodeModel
  const recoveryEvents: RecoveryEvent[] = []
  const trackRecovery = (ev: RecoveryEvent) => {
    recoveryEvents.push(ev)
    onRecoveryEvent?.(ev)
  }

  // Top-level crash guard — the pipeline NEVER crashes the app
  try {
    return await runFullPipeline({
      prompt,
      enrichedPrompt,
      conversationHistory,
      existingFiles,
      contextImages,
      userFileDataUrls,
      configuredCodeModel,
      generationModel,
      setPhase,
      onToken,
      onFilesUpdate,
      onValidationUpdate,
      onCorrectionLogUpdate,
      onFollowUpAnalysis,
      trackRecovery,
      recoveryEvents,
      signal,
    })
  } catch (fatalError) {
    // Absolute last resort — return error state instead of crashing
    const msg = fatalError instanceof Error ? fatalError.message : String(fatalError)
    console.error('[CodeOrchestrator] Pipeline fatal error (app NOT crashed):', msg)
    setPhase(`Erreur pipeline: ${msg.slice(0, 100)}`, 0)
    return {
      files: [],
      notes: `Erreur fatale du pipeline: ${msg}`,
      sandboxResult: null,
      intent: classifyCodeIntent(enrichedPrompt),
      preflightReport: null,
      correctionLog: [],
      phase: 'error',
      architecturePlan: null,
      totalAttempts: 0,
      finalScore: 0,
      recoveryEvents,
      followUp: null,
    }
  }
}

// ---------------------------------------------------------------------------
// Full pipeline implementation (isolated for crash-proof wrapping)
// ---------------------------------------------------------------------------

async function runFullPipeline({
  prompt,
  enrichedPrompt,
  conversationHistory,
  existingFiles,
  contextImages,
  userFileDataUrls,
  configuredCodeModel,
  generationModel,
  setPhase,
  onToken,
  onFilesUpdate,
  onValidationUpdate,
  onCorrectionLogUpdate,
  onFollowUpAnalysis,
  trackRecovery,
  recoveryEvents,
  signal,
}: {
  prompt: string
  enrichedPrompt: string
  conversationHistory: OllamaMessage[]
  existingFiles: CodeFile[]
  contextImages: string[]
  /** Map of placeholder → data URL for user-attached files (forwarded from orchestrateCodeGeneration) */
  userFileDataUrls?: Record<string, string>
  configuredCodeModel: string
  generationModel: string
  setPhase: PhaseCallback
  onToken: (token: string) => void
  onFilesUpdate: (files: CodeFile[], notes: string) => void
  onValidationUpdate: (result: CodeSandboxResult) => void
  onCorrectionLogUpdate: (log: CorrectionPass[], attempt: number, score: number) => void
  onFollowUpAnalysis?: (analysis: FollowUpAnalysis) => void
  trackRecovery: (event: RecoveryEvent) => void
  recoveryEvents: RecoveryEvent[]
  signal?: AbortSignal
}): Promise<CodeOrchestrationResult> {
  // Phase 0: Follow-up intent analysis — only runs when there is prior context.
  // Turns "la meme chose en python" into a reformulated prompt + pivotKind so
  // the rest of the pipeline does not accidentally carry a stale HTML project.
  const hasContext = conversationHistory.length > 0 || existingFiles.length > 0
  const followUp: FollowUpAnalysis | null = hasContext
    ? await (async () => {
        setPhase('Analyse du contexte de la discussion...', 3)
        try {
          return await analyzeFollowUpIntent({
            newPrompt: prompt,
            conversationHistory,
            existingFiles,
            model: configuredCodeModel,
            signal,
          })
        } catch (err) {
          console.warn('[CodeOrchestrator] follow-up analysis failed, continuing without:', err)
          return null
        }
      })()
    : null

  if (followUp) {
    onFollowUpAnalysis?.(followUp)
    setPhase(
      `Mode: ${followUp.kind}${followUp.pivotReason ? ` — ${followUp.pivotReason.slice(0, 60)}` : ''}`,
      5,
    )
  }

  // The prompt the remaining phases reason on is the reformulation when the
  // analyzer produced one. Keep the original `prompt`/`enrichedPrompt` for
  // places that need the raw user text.
  const reformulatedPrompt = followUp?.reformulatedPrompt?.trim() || prompt
  const reformulatedEnriched = followUp && followUp.reformulatedPrompt && followUp.reformulatedPrompt !== prompt
    ? `${enrichedPrompt}\n\n## REFORMULATION CONTEXTUELLE\n${followUp.reformulatedPrompt}`
    : enrichedPrompt

  // If the analyzer decided we are pivoting platforms or starting fresh,
  // drop the existing files so the Codeur does not see the old HTML while
  // the user actually asked for a Python backend. The migration summary
  // captures the business concept to carry over.
  const effectiveExistingFiles = followUp?.shouldResetFiles ? [] : existingFiles

  // Phase 1: Intent classification (deterministic) — enriched with follow-up context.
  const intentContext: CodeIntentContext | undefined = followUp
    ? {
        previousProjectType: followUp.previousProjectType ?? undefined,
        previousLanguages: followUp.previousLanguages,
        previousFrameworks: followUp.previousFrameworks,
        pivotKind: followUp.kind === 'clarify_only' ? 'increment' : followUp.kind,
      }
    : undefined
  const intent = runIntentPhase(reformulatedEnriched, setPhase, intentContext)

  // Phase 1.5: Deterministic + model-assisted preflight before any code generation
  const preflightReport = await runPreflightPhase(
    prompt,
    intent,
    existingFiles,
    configuredCodeModel,
    setPhase,
  )

  // Phase 1.75: Research best practices (non-blocking, enriches planning context)
  // Label is contextualized by the asset plan so the user understands WHY it takes time
  // ("recherche de references premium" >> "recherche generique").
  const ap = intent.assetPlan
  const researchPhaseLabel = ap?.researchQueries.length
    ? `Recherche de references visuelles en ligne (${ap.researchQueries.slice(0, 2).join(' | ')})... cela peut prendre jusqu a 30s`
    : ap?.wantsPremiumLook
      ? 'Recherche de tendances de design premium... cela peut prendre jusqu a 30s'
      : 'Recherche des meilleures pratiques pour ce type de projet...'
  setPhase(researchPhaseLabel, 14)
  let bestPracticesContext = ''
  try {
    bestPracticesContext = await withTimeout(researchBestPractices(prompt, intent, configuredCodeModel), {
      label: 'Code research best practices',
      timeoutMs: RESEARCH_PHASE_TIMEOUT_MS,
    })
    if (bestPracticesContext) {
      setPhase('Meilleures pratiques trouvees — integration dans la planification...', 16)
    }
  } catch {
    // Research is non-blocking — continue without it
  }

  // v77 — DYNAMIC BRAND ENRICHMENT. When the user prompt mentions a brand we
  // don't have in the in-memory dictionary (Lipton, Heineken, Audi, ...),
  // the codeIntent classifier marks the subject as `inferred_brand` with no
  // profile. We call the bridge `/api/brand/enrich` here to fetch a real
  // BrandProfile from Wikipedia + Ollama before the planning phase, so the
  // rest of the pipeline (image queries, productShape recipe, palette lock)
  // works the same way for ANY brand, not just our 47 cached ones.
  //
  // v84r FIX : on SKIP cette phase pour les prompts qui ressemblent à un brief
  // technique simple (mots "simple", "minimal", "page HTML", "bouton",
  // "fonction", "calcul" etc.) — un titre "Bonjour Aurora" ne devrait pas
  // déclencher 60s de Wikipedia + Ollama. Le brand enrich reste actif pour
  // les vrais briefs "fais-moi le site de Coca-Cola" etc.
  const promptLower = prompt.toLowerCase()
  const looksLikeSimpleTechBrief = (
    prompt.length < 300 &&
    /\b(simple|minimal|basique|petit|petite|un\s+bouton|une\s+page|index\.html|une\s+fonction|calcul|console|cli|script)\b/i.test(promptLower) &&
    !/\b(comme|pour|de la marque|site de|brand|logo de)\b/i.test(promptLower)
  )
  if (ap?.subject?.source === 'inferred_brand' && !ap.subject.brandProfile && ap.subject.canonical && !looksLikeSimpleTechBrief) {
    setPhase(`Enrichissement dynamique du profil de marque "${ap.subject.canonical}" (Wikipedia + Ollama)...`, 13)
    try {
      const enriched = await withTimeout(
        fetchBrandProfileFromBridge(ap.subject.canonical),
        // v84r : 55s → 20s. Si Wikipedia tarde, on n'a pas le luxe d'attendre.
        // Le code peut commencer à streamer avec la palette générique.
        { label: 'Brand enrich (bridge)', timeoutMs: 20_000 },
      )
      if (enriched) {
        // Mutate the subject in place — the rest of the pipeline now sees a
        // full BrandProfile and treats the page as a brand page.
        ap.subject.brandProfile = enriched
        ;(ap.subject as { source: string }).source = 'brand'
        // Also re-run the brand-aware research query injection that
        // classifyCodeAssetPlan does for cached brands, so the bridge
        // image fetch picks up the right queries from the new profile.
        if (enriched.imageQueries?.length && ap.researchQueries) {
          for (const q of enriched.imageQueries.slice(0, 3).reverse()) {
            ap.researchQueries.unshift(q)
          }
        }
        setPhase(`Profil "${ap.subject.canonical}" enrichi (palette ${enriched.primaryColor}, produit ${enriched.productShape ?? 'logo'}).`, 14)
      } else {
        setPhase(`Pas de profil enrichi trouve pour "${ap.subject.canonical}" — generic fallback.`, 14)
      }
    } catch (err) {
      console.warn('[CodeOrchestrator] brand enrich failed:', err)
    }
  }

  // Phase 1.8: Real image fetch for the detected subject — data URLs are inlined
  // in the prompt so the LLM reuses them as <img src="..."> directly.
  // This is how "il doit vraiment telecharger une image" happens, and it survives
  // the user saving the project anywhere since it is a data URL, not a remote link.
  // v71: multi-image — brand pages need 3-4 distinct shots (logo, product,
  // lifestyle, detail), not a single hero photo. The orchestrator queries the
  // Aurora-Connect extension first (real browser tab), then the Python bridge,
  // then a deterministic local SVG fallback.
  let subjectImageBlock = ''
  // v84r : skip pour les briefs simples — pas besoin d'aller chercher 4 images
  // si le user demande juste "page HTML avec un bouton qui calcule X".
  const wantsRealImage = ap && (ap.wantsImages || ap.subject?.source === 'brand' || (ap.objectMentions?.length ?? 0) > 0)
  if (wantsRealImage && !looksLikeSimpleTechBrief) {
    const isBrand = ap.subject?.source === 'brand'
    setPhase(
      isBrand
        ? 'Recuperation des images officielles de la marque (logo + produit + lifestyle)...'
        : 'Telechargement d images reelles du sujet (peut prendre 10-30s)...',
      17,
    )
    try {
      const images = await withTimeout(
        fetchSubjectImages(intent),
        { label: 'Subject images fetch (multi)', timeoutMs: 45_000 },
      )
      // Cap each data URL at ~280KB so we don't blow up the prompt — the Codeur
      // only needs the image to load at runtime, not to read its bytes during
      // planning. Anything longer is dropped silently.
      const acceptable = images.filter((img) => img.dataUrl.length <= 350_000)
      if (acceptable.length > 0) {
        const dataUrls = acceptable.map((img) => img.dataUrl)
        ;(intent as any).__subjectImageDataUrls = dataUrls
        // Keep the legacy single-marker field for any older prompt path.
        ;(intent as any).__subjectImageDataUrl = dataUrls[0]

        const sourcesLine = acceptable
          .map((img, idx) => `  ${idx + 1}. ${img.query || 'subject'} -> ${img.source || 'unknown'}`)
          .join('\n')
        subjectImageBlock = [
          `## IMAGES REELLES DU SUJET (telechargees pour toi en amont — ${acceptable.length})`,
          `- ${acceptable.length} photo(s) / illustration(s) du sujet ont ete trouvees et converties en data URLs.`,
          '- Tu DOIS les utiliser DIRECTEMENT dans la page avec ces markers literaux:',
          '  - `PLACEHOLDER_SUBJECT_IMG`     -> image principale (hero / produit central).',
          acceptable.length >= 2 ? '  - `PLACEHOLDER_SUBJECT_IMG_1`   -> image principale (alias du marker non numerote).' : '',
          acceptable.length >= 2 ? '  - `PLACEHOLDER_SUBJECT_IMG_2`   -> image secondaire (lifestyle / contexte).' : '',
          acceptable.length >= 3 ? '  - `PLACEHOLDER_SUBJECT_IMG_3`   -> image tertiaire (detail / texture / variante).' : '',
          acceptable.length >= 4 ? '  - `PLACEHOLDER_SUBJECT_IMG_4`   -> image complementaire (gallery).' : '',
          '- Au build final, chaque marker sera remplace par la data URL correspondante.',
          '- Tu peux reutiliser le meme marker plusieurs fois (hero + showcase + footer). Tout marker sans image associee sera neutralise.',
          '- Sources originales:',
          sourcesLine,
        ].filter(Boolean).join('\n')
        setPhase(
          isBrand
            ? `${acceptable.length} image(s) de la marque telechargees — injection dans le prompt...`
            : `${acceptable.length} image(s) du sujet telechargees — injection dans le prompt...`,
          19,
        )
      } else if (images.length > 0) {
        console.warn('[CodeOrchestrator] All fetched subject images exceed the 350KB inline budget — skipping.')
      }
    } catch (err) {
      // Non-blocking: we continue without a real image. The Codeur falls back to
      // its usual SVG-inline strategy thanks to the "PAS D IMAGES CASSEES" rules.
      console.warn('[CodeOrchestrator] Subject image fetch failed:', err)
    }
  }

  // Inject brand profile into planning context: colors, keywords, design vibe.
  let brandProfileBlock = ''
  const brandSubject = ap?.subject
  if (brandSubject?.source === 'brand' && brandSubject.brandProfile) {
    const profile = brandSubject.brandProfile
    const palette: string[] = []
    if (profile.primaryColor) palette.push(`primaire ${profile.primaryColor}`)
    if (profile.secondaryColor) palette.push(`secondaire ${profile.secondaryColor}`)
    if (profile.tertiaryColor) palette.push(`tertiaire ${profile.tertiaryColor}`)
    brandProfileBlock = [
      `## PROFIL DE MARQUE — ${brandSubject.canonical}`,
      `- Domaine: ${brandSubject.domain ?? 'inconnu'}.`,
      palette.length ? `- Palette canonique: ${palette.join(', ')}.` : '',
      profile.productKeywords.length ? `- Produits / mots-cles: ${profile.productKeywords.join(', ')}.` : '',
      profile.designVibe ? `- Vibe visuel: ${profile.designVibe}.` : '',
      profile.typoVibe ? `- Typo: ${profile.typoVibe}.` : '',
      `- Le plan d architecture et le code DOIVENT respecter cette identite. Les couleurs du starter generique ne s appliquent pas.`,
    ].filter(Boolean).join('\n')
  }

  // Phase 2: Deep reasoning + architecture planning via llama4.
  const planningExtras: string[] = []
  if (bestPracticesContext) planningExtras.push(`## MEILLEURES PRATIQUES TROUVEES (a integrer dans le plan):\n${bestPracticesContext}`)
  // Brand profile injected before image block so architect plan uses colors/keywords.
  if (brandProfileBlock) planningExtras.push(brandProfileBlock)
  if (subjectImageBlock) planningExtras.push(subjectImageBlock)
  if (followUp?.migrationSummary && followUp.kind === 'pivot_platform') {
    planningExtras.push(`## MIGRATION DE PROJET (conserve le concept, change la stack)\n${followUp.migrationSummary}`)
  }
  const planningPrompt = planningExtras.length
    ? `${reformulatedEnriched}\n\n${planningExtras.join('\n\n')}`
    : reformulatedEnriched
  // Skip planning only for genuinely small visual one-offs. Complex visual work
  // (multi-page, 3D, simulator, whole-product briefs) needs the architect pass:
  // the user's target is a real engineered project, not a pretty single screen.
  const skipPlanningForVisual =
    (intent.projectType === 'static_web' || intent.projectType === 'game_web') &&
    !intent.needsArchitecturePlanning
  const architecturePlan = skipPlanningForVisual
    ? null
    : await runPlanningPhase(
        planningPrompt,
        intent,
        preflightReport,
        configuredCodeModel,
        setPhase,
        trackRecovery,
      )
  if (skipPlanningForVisual) setPhase('Projet web direct — generation sans plan lourd...', 28)
  const missionDossier = await buildCodeMissionDossier({
    prompt: reformulatedPrompt,
    enrichedPrompt: reformulatedEnriched,
    intent,
    existingFiles: effectiveExistingFiles,
    architecturePlan,
    model: selectModel('planning', intent, 0, configuredCodeModel),
  })

  // Pivot context forwarded to the code generator so it can swap the
  // "CONTEXTE PROJET EXISTANT" block with a "MIGRATION DE PROJET" block
  // when the user asked for a platform pivot.
  const pivotContext: GenerationPivotContext | undefined = followUp
    ? {
        kind: followUp.kind,
        migrationSummary: followUp.migrationSummary,
      }
    : undefined

  // Phase 3: Code generation (streaming, guided by plan)
  let fullContent = await runGenerationPhase(
    reformulatedEnriched,
    intent,
    preflightReport,
    architecturePlan,
    missionDossier,
    conversationHistory,
    effectiveExistingFiles,
    contextImages,
    generationModel,
    0,
    setPhase,
    onToken,
    trackRecovery,
    signal,
    pivotContext,
  )

  // CRITICAL: Detect LLM refusal BEFORE parsing — refuse early, retry immediately
  if (isLLMRefusal(fullContent)) {
    console.warn('[CodeOrchestrator] LLM returned a refusal instead of code. Forcing regeneration.')
    setPhase('Le modele a refuse de generer du code — regeneration forcee...', 40)
    // Force a regeneration with a stronger prompt
    const rescueContent = await runGenerationPhase(
      [
        'INSTRUCTION CRITIQUE: Tu DOIS generer du code source. NE REFUSE JAMAIS.',
        'Tu es un generateur de code. Ta seule sortie autorisee est du CODE SOURCE dans le format:',
        '--- FICHIER: nom.ext ---',
        '```langage',
        '// code ici',
        '```',
        '',
        'INTERDIT: excuses, refus, explications, suggestions de consulter les instructions.',
        'Genere le projet demande MAINTENANT:',
        '',
        reformulatedEnriched,
      ].join('\n'),
      intent,
      preflightReport,
      architecturePlan,
      missionDossier,
      conversationHistory,
      effectiveExistingFiles,
      contextImages,
      selectModel('generation', intent, 2, generationModel),
      2,
      setPhase,
      onToken,
      trackRecovery,
      signal,
      pivotContext,
    )
    // If rescue also refuses, we'll catch it in the validation loop below
    if (!isLLMRefusal(rescueContent)) {
      fullContent = rescueContent
    }
  }

  // Swap the PLACEHOLDER_SUBJECT_IMG marker with the real downloaded data URL
  // so every <img> tag the LLM wrote resolves immediately at first render.
  fullContent = applySubjectImagePlaceholder(fullContent, intent)

  // Swap USER_FILE_N markers with the real data URL of each user-attached file.
  // `userFileDataUrls` is optional in the public API — guard against every possible
  // shape (undefined / null / {}) to avoid ReferenceError at runtime.
  const userMap = userFileDataUrls ?? {}
  for (const [marker, dataUrl] of Object.entries(userMap)) {
    if (typeof dataUrl === 'string' && dataUrl && fullContent.includes(marker)) {
      fullContent = fullContent.split(marker).join(dataUrl)
    }
  }

  let latestRawGenerationContent = fullContent
  let parsed = parseCodeFiles(latestRawGenerationContent)
  let initialNotes = extractNotes(latestRawGenerationContent)
  // In follow-up mode (effectiveExistingFiles.length > 0), files NOT returned
  // by the LLM are preserved — we merge the new/changed files on top of the
  // existing set. After a pivot_platform / fresh_start, `effectiveExistingFiles`
  // is empty so the old project is correctly wiped.
  let initialFiles = effectiveExistingFiles.length > 0 && parsed.length > 0
    ? mergeExistingWithUpdates(effectiveExistingFiles, parsed)
    : parsed

  // Validate output quality — retry loop to ensure LLM produced actual code.
  // Complex briefs get more attempts and never downgrade to a tiny skeleton:
  // time is secondary to a complete, runnable project.
  const isExpertComplexProject = intent.complexity === 'complex' || intent.complexity === 'enterprise'
  const MAX_OUTPUT_RETRIES = isExpertComplexProject ? 6 : 3
  const MAX_NETWORK_ERRORS = isExpertComplexProject ? 4 : 2
  let outputRetry = 0
  let networkErrors = 0
  // v71 — track the latest brand fidelity report so we can apply the score
  // penalty/cap at the end of the orchestration.
  let latestBrandFidelity: BrandFidelityReport | null = null
  // v85c : remember the best non-empty attempt across the retry loop so the
  // pipeline NEVER returns 0 files when the model actually produced usable
  // code that a quality gate merely flagged. "Imparfait mais livré" > "rien".
  let bestAttempt: { files: CodeFile[]; notes: string; score: number } | null = null

  while (outputRetry < MAX_OUTPUT_RETRIES) {
    const draftReview = await reviewGeneratedCodeDraft({
      prompt,
      intent,
      files: initialFiles,
      architecturePlan,
      missionDossier,
      // v85c : CRITICAL — without this, the draft critique defaulted to
      // CODE_SINGLE_MODEL (qwen3-coder:30b, 20 GB) mid-pipeline, evicting the
      // routed generation model and forcing a CPU-spill +
      // reload thrash on every run. Pin it to the same model the rest of the
      // pipeline uses → true single-model coherence, no swap, far faster.
      model: configuredCodeModel,
    })
    // v71 — brand fidelity gate. Catches the "Coca-Cola → restaurant" drift
    // BEFORE the sandbox/correction loop wastes minutes on a wrong-subject
    // build. Only fires when the prompt has a brand subject; no-op otherwise.
    const brandSubject = intent.assetPlan?.subject
    const brandFidelity = evaluateBrandFidelity(intent, initialFiles)
    latestBrandFidelity = brandFidelity
    const brandIssueLine = brandFidelity.shouldRetry && brandFidelity.retryHint
      ? `Fidelite sujet (BRAND): ${brandFidelity.retryHint}`
      : null

    const issueNarrative = detectNonCodePlanningNarrative(latestRawGenerationContent)
    const issueIntent = validateOutputMatchesIntent(initialFiles, intent)
    const issueDraft = draftReview.verdict === 'regenerate'
      ? [
          draftReview.summary,
          ...draftReview.criticalIssues,
          ...draftReview.missingFiles,
        ].filter(Boolean).join(' | ')
      : null
    // v85d : the draft critique runs on the generation model,
    // which the audit found false-flags 'regenerate' on perfectly valid projects.
    // Trust the DETERMINISTIC gates (narrative / intent / brand) as primary;
    // let the LLM-judge force a retry ONLY when the output is also thin
    // (< 2 real code files) — otherwise it just burns retries on good output.
    const realCodeFileCount = initialFiles.filter((f) => {
      const e = f.name.split('.').pop()?.toLowerCase() || ''
      return !DOCUMENTATION_EXTENSIONS_EARLY.has(e)
    }).length
    const draftBlocks = issueDraft && realCodeFileCount < 2 ? issueDraft : null
    const outputIssue = issueNarrative || issueIntent || brandIssueLine || draftBlocks

    // v85c : track the best non-empty attempt (most files, then content score).
    if (initialFiles.length > 0) {
      const q = computeContentQualityScore(initialFiles, intent)
      if (!bestAttempt
        || initialFiles.length > bestAttempt.files.length
        || (initialFiles.length === bestAttempt.files.length && q > bestAttempt.score)) {
        bestAttempt = { files: initialFiles, notes: initialNotes, score: q }
      }
    }
    if (outputIssue) {
      console.warn(
        `[CodeOrchestrator] outputIssue @retry ${outputRetry} | files=${initialFiles.length} | `
        + `narrative=${!!issueNarrative} intentMismatch=${issueIntent ? JSON.stringify(issueIntent.slice(0, 80)) : false} `
        + `brand=${!!brandIssueLine} draftRegenerate=${!!issueDraft}`,
      )
    }
    if (!outputIssue) break // Output is valid code

    outputRetry++
    const escalation = outputRetry + 1
    const retryModel = selectModel('generation', intent, escalation, generationModel)
    const modelShort = retryModel.split(':')[0]

    setPhase(
      `Sortie incorrecte (tentative ${outputRetry}/${MAX_OUTPUT_RETRIES}) — regeneration via ${modelShort}...`,
      48 + outputRetry * 4,
    )

    // On brand drift: lock subject + palette + keywords in retry prompt.
    const brandRetryBlock = (brandFidelity.shouldRetry && brandSubject?.source === 'brand' && brandSubject.brandProfile)
      ? [
          '## VERROUILLAGE SUJET — REGLE INVIOLABLE',
          `Le sujet de cette page EST ${brandSubject.canonical}. Pas un sujet adjacent.`,
          '',
          'Violations detectees au tour precedent:',
          brandFidelity.retryHint || '(pas de detail)',
          '',
          'Pour ce nouveau tour, applique strictement:',
          `- Le mot "${brandSubject.canonical}" doit apparaitre dans <title>, dans le <h1> du hero, et dans au moins 3 sections.`,
          brandSubject.brandProfile.primaryColor ? `- Couleur primaire OBLIGATOIRE: ${brandSubject.brandProfile.primaryColor}. Utilise-la pour le hero, les CTAs et les accents.` : '',
          brandSubject.brandProfile.secondaryColor ? `- Couleur secondaire: ${brandSubject.brandProfile.secondaryColor}.` : '',
          brandSubject.brandProfile.productKeywords.length ? `- Mots-cles produit: ${brandSubject.brandProfile.productKeywords.join(', ')}. Au moins 2 dans les titres de section.` : '',
          brandSubject.brandProfile.designVibe ? `- Vibe visuel cible: ${brandSubject.brandProfile.designVibe}.` : '',
          '- Markers d images REELLES deja telechargees: PLACEHOLDER_SUBJECT_IMG, PLACEHOLDER_SUBJECT_IMG_1..4. Place-en au moins 2 dans la page.',
          '- INTERDIT: restaurant, menu du jour, blog culinaire, SaaS abstrait. C est une marque/produit emblematique, traite-la comme telle.',
        ].filter(Boolean).join('\n')
      : ''

    const retryPrompt = [
      `ERREUR CRITIQUE (tentative ${outputRetry + 1}): La sortie precedente etait INCORRECTE.`,
      `Probleme: ${outputIssue}`,
      '',
      brandRetryBlock,
      '',
      `DOSSIER EXECUTIF:\n${serializeCodeMissionDossier(missionDossier)}`,
      '',
      'RAPPEL ABSOLU:',
      '- Tu es un DEVELOPPEUR. Tu produis du CODE SOURCE, JAMAIS de la documentation.',
      '- Chaque fichier DOIT etre un VRAI fichier de code (html, css, js, py, etc.)',
      '- INTERDIT: fichiers .md, .txt, texte descriptif, listes de fonctionnalites',
      detectNonCodePlanningNarrative(latestRawGenerationContent)
        ? '- TA SORTIE PRECEDENTE ETAIT UN PLAN/PREFLIGHT. N envoie plus jamais de diagnostic: convertis directement la solution en fichiers.'
        : '',
      outputRetry >= 2 && !isExpertComplexProject
        ? '- SIMPLIFIE: produis le MINIMUM de fichiers necessaires pour que ca fonctionne'
        : '',
      outputRetry >= 2 && isExpertComplexProject
        ? '- NE SIMPLIFIE PAS LES FONCTIONNALITES: preserve le scope demande, corrige la structure et livre tous les fichiers necessaires.'
        : '',
      '',
      detectNonCodePlanningNarrative(latestRawGenerationContent)
        ? `SORTIE INTERDITE A NE PAS REPRODUIRE:\n${clipText(latestRawGenerationContent, 1400)}\n`
        : '',
      buildDraftRegenerationPrompt({
        originalPrompt: prompt,
        enrichedPrompt,
        missionDossier,
        draftReview,
        architecturePlan,
      }),
      '',
      architecturePlan ? `PLAN A SUIVRE:\n${architecturePlan.slice(0, 6000)}\n` : '',
      'Voici la demande originale. Genere les VRAIS FICHIERS DE CODE:',
      '',
      enrichedPrompt,
      '',
      'FORMAT OBLIGATOIRE (ne JAMAIS devier):',
      '--- FICHIER: nom_du_fichier.ext ---',
      '```langage',
      '// code source complet ici',
      '```',
      '',
      intent.projectType === 'static_web'
        ? 'Pour une page web, genere AU MINIMUM: index.html, style.css, et optionnellement script.js + README.md'
        : intent.projectType === 'desktop_tauri'
          ? 'Pour une application desktop Tauri, genere AU MINIMUM: package.json, src/*, src-tauri/Cargo.toml, src-tauri/tauri.conf.json, src-tauri/src/main.rs + README.md'
          : intent.projectType === 'desktop_electron'
            ? 'Pour une application desktop Electron, genere AU MINIMUM: package.json, main.ts|main.js, preload si utile, renderer src/* + README.md'
        : intent.projectType.startsWith('api_')
          ? 'Pour une API, genere les fichiers serveur: routes, models, config, entry point + README.md'
          : 'Genere tous les fichiers source necessaires au projet + README.md',
    ].filter(Boolean).join('\n')

    let retryContent = ''
    try {
      retryContent = await runGenerationPhase(
        retryPrompt,
        intent,
        preflightReport,
        architecturePlan,
        missionDossier,
        conversationHistory,
        effectiveExistingFiles,
        contextImages,
        retryModel,
        escalation,
        setPhase,
        onToken,
        trackRecovery,
        signal,
        pivotContext,
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      if (/failed to fetch|network|TypeError|524|connection closed/i.test(msg)) {
        networkErrors += 1
        setPhase(`Erreur reseau (${networkErrors}/${MAX_NETWORK_ERRORS}) pendant la regeneration — tentative ${outputRetry}...`, 50 + outputRetry * 4)
        if (networkErrors >= MAX_NETWORK_ERRORS) {
          setPhase('Trop d erreurs reseau consecutives — arret propre du pipeline.', 96)
          break
        }
        // Short pause then let the outer loop retry once more.
        await new Promise((r) => setTimeout(r, 2000))
        continue
      }
      throw err
    }

    latestRawGenerationContent = retryContent
    const retryFiles = parseCodeFiles(retryContent)
    initialFiles = effectiveExistingFiles.length > 0 && retryFiles.length > 0
      ? mergeExistingWithUpdates(effectiveExistingFiles, retryFiles)
      : retryFiles
    initialNotes = extractNotes(retryContent)
  }

  // v85c : if the retry loop exhausted while flagging issues but an earlier
  // attempt DID produce usable files, deliver the best one (with a quality
  // note) instead of returning nothing. The quality gates become advisory,
  // not fatal — the user always gets a project they can iterate on.
  if (initialFiles.length === 0 && bestAttempt && bestAttempt.files.length > 0) {
    console.warn(`[CodeOrchestrator] retry loop exhausted — delivering best attempt (${bestAttempt.files.length} fichiers) instead of 0.`)
    initialFiles = bestAttempt.files
    initialNotes = bestAttempt.notes
      ? `${bestAttempt.notes}\n\n[Aurora] Livré malgré des réserves du contrôle qualité — un ajustement manuel peut être utile.`
      : '[Aurora] Livré malgré des réserves du contrôle qualité — un ajustement manuel peut être utile.'
  }

  if (initialFiles.length === 0) {
    const diagnostic = buildEmptyGenerationDiagnostic(latestRawGenerationContent, intent, outputRetry)
    return {
      files: [],
      notes: diagnostic,
      sandboxResult: null,
      intent,
      preflightReport,
      correctionLog: [],
      phase: 'error',
      architecturePlan,
      totalAttempts: 0,
      finalScore: 0,
      recoveryEvents,
      followUp,
    }
  }

  initialFiles = upsertProjectSupportFiles(initialFiles, intent, reformulatedEnriched, architecturePlan)

  onFilesUpdate(initialFiles, initialNotes)

  // Phase 4+5: Validation + auto-correction loop
  const validationResult = await runValidationAndCorrectionLoop(
    prompt,
    initialFiles,
    intent,
    preflightReport,
    missionDossier,
    architecturePlan,
    configuredCodeModel,
    setPhase,
    onFilesUpdate,
    onValidationUpdate,
    onCorrectionLogUpdate,
    signal,
  )

  const finalFiles = upsertProjectSupportFiles(validationResult.files, intent, reformulatedEnriched, architecturePlan)

  // v71 — re-evaluate the brand fidelity AFTER the validation loop has settled.
  // The auto-correction may have rewritten copy and undone an earlier brand
  // fix, so we score on the final files.
  const finalBrandFidelity = evaluateBrandFidelity(intent, finalFiles)
  let adjustedScore = validationResult.finalScore
  if (finalBrandFidelity.scoreCap !== null) {
    adjustedScore = Math.min(adjustedScore, finalBrandFidelity.scoreCap)
  }
  if (finalBrandFidelity.scorePenalty > 0) {
    adjustedScore = Math.max(0, adjustedScore - finalBrandFidelity.scorePenalty)
  }

  const augmentedNotes = finalBrandFidelity.retryHint
    ? `${validationResult.notes}\n\n## FIDELITE SUJET\n${finalBrandFidelity.retryHint}`
    : validationResult.notes

  // Suppress the latestBrandFidelity warning when no longer used after the
  // post-loop re-evaluation. (Keeps the linter quiet without losing state
  // we may want to surface in a future iteration.)
  void latestBrandFidelity

  // Compute design polish report for visual project types (badge for UI).
  const designReport = isVisualProjectType(intent.projectType)
    ? computeDesignPolishReport(finalFiles)
    : null

  return {
    files: finalFiles,
    notes: augmentedNotes,
    sandboxResult: validationResult.sandboxResult,
    intent,
    preflightReport,
    correctionLog: validationResult.correctionLog,
    // Expert delivery contract: files are not enough. A project is done only
    // when the sandbox and deterministic quality gates agree it is runnable.
    phase: validationResult.sandboxResult?.ok ? 'done' : 'error',
    architecturePlan,
    totalAttempts: validationResult.totalAttempts,
    finalScore: adjustedScore,
    recoveryEvents,
    followUp,
    designReport,
  }
}

// ---------------------------------------------------------------------------
// README auto-generation — ensures every project has install/run instructions
// ---------------------------------------------------------------------------

function generateReadme(
  files: CodeFile[],
  intent: CodeIntent,
  prompt: string,
  architecturePlan: string | null,
): CodeFile {
  const fileList = files
    .filter((f) => f.name.toLowerCase() !== 'readme.md')
    .map((f) => `- \`${f.name}\` — ${f.language}`)
    .join('\n')

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasPackageJson = normalizedNames.includes('package.json')
  const hasRequirements = normalizedNames.includes('requirements.txt')
  const hasCargo = normalizedNames.some((name) => name.endsWith('cargo.toml'))

  const installSteps: string[] = []
  if (hasPackageJson) {
    installSteps.push('```bash', 'npm install', '```')
  }
  if (hasRequirements) {
    installSteps.push('```bash', 'pip install -r requirements.txt', '```')
  }
  if (hasCargo) {
    installSteps.push('```bash', 'cargo build', '```')
  }
  if (installSteps.length === 0) {
    if (intent.projectType === 'static_web' || intent.projectType === 'game_web') {
      installSteps.push('Aucune installation requise — ouvrir `index.html` dans un navigateur.')
    } else {
      installSteps.push('Voir les dependances dans les fichiers de configuration du projet.')
    }
  }

  const runSteps: string[] = []
  if (intent.devCommand) {
    runSteps.push('```bash', intent.devCommand, '```')
  } else if (intent.projectType === 'static_web') {
    runSteps.push('Ouvrir `index.html` dans un navigateur web.')
  } else if (hasPackageJson) {
    runSteps.push('```bash', 'npm start', '```')
  } else if (files.some((f) => f.name === 'app.py' || f.name === 'main.py')) {
    const entry = files.find((f) => f.name === 'app.py') ? 'app.py' : 'main.py'
    runSteps.push('```bash', `python ${entry}`, '```')
  }

  const runbook = buildProjectRunbook(files, intent)

  // Extract dependencies from plan if available
  let depsSection = ''
  if (architecturePlan) {
    const depsMatch = architecturePlan.match(/###\s*DEPENDANCES[^\n]*\n([\s\S]*?)(?=###|$)/i)
    if (depsMatch?.[1]?.trim()) {
      depsSection = `## Dependances\n\n${depsMatch[1].trim()}\n\n`
    }
  }

  const content = [
    `# ${intent.projectType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}`,
    '',
    `> ${prompt.slice(0, 200)}${prompt.length > 200 ? '...' : ''}`,
    '',
    '## Structure du projet',
    '',
    fileList,
    '',
    depsSection,
    '## Installation',
    '',
    runbook.installSteps.join('\n'),
    '',
    '## Lancement',
    '',
    runbook.runSteps.join('\n'),
    '',
    '## Raccourci de lancement',
    '',
    'Le fichier `start.sh` est fourni quand un demarrage automatise est possible sur Linux/macOS.',
    '',
    '---',
    '*Genere par Aurora IA — Module Code*',
  ].join('\n')

  return {
    name: 'README.md',
    language: 'markdown',
    content,
  }
}
