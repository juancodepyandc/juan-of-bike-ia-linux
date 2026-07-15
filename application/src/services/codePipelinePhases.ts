import type { OllamaMessage } from '../types/app'
import type { RecoveryEvent } from './ollamaResilience.ts'
import {
  type CodeIntent,
  type CodeIntentContext,
  buildArchitecturePlanningPrompt,
  classifyCodeIntent,
} from './codeIntent.ts'
import type { FollowUpKind } from './codeFollowUpAnalysis.ts'
import type { CodeFile, PhaseCallback } from './codeOrchestrator.ts'
import {
  buildArchitecteSystemPrompt,
  buildCodeurSystemPrompt,
} from './codeSystemPrompts.ts'
import type { CodeMissionDossier } from './codeMissionControl.ts'
import type { CodePreflightReport } from './codePreflight.ts'
import { withTimeout } from './llmTimebox.ts'
import { isVisualProjectType } from './codeQualityGates.ts'
import {
  CODE_EXPERT_CONTEXT_TOKENS,
  CODE_EXPERT_OUTPUT_TOKENS,
  CODE_PLANNING_CONTEXT_TOKENS,
  GENERATION_FIRST_BYTE_TIMEOUT_MS,
  PLANNING_FIRST_BYTE_TIMEOUT_MS,
  PLANNING_TIMEOUT_MS,
  PREFLIGHT_PHASE_TIMEOUT_MS,
  STREAM_GENERATION_TOTAL_TIMEOUT_MS,
  getModelShortName,
  selectModel,
} from './codePipelineRuntime.ts'

export function isArchitecturePlanUsable(plan: string | null) {
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

/** Phase 1: Classify intent (deterministic, no LLM) */
export function runIntentPhase(
  prompt: string,
  setPhase: PhaseCallback,
  context?: CodeIntentContext,
): CodeIntent {
  setPhase('Classification du projet...', 5)
  return classifyCodeIntent(prompt, context)
}

/** Phase 1.5: Local preflight — inspect machine, workspace and current project before coding */
export async function runPreflightPhase(
  prompt: string,
  intent: CodeIntent,
  existingFiles: CodeFile[],
  configuredCodeModel: string,
  setPhase: PhaseCallback,
): Promise<CodePreflightReport | null> {
  try {
    setPhase('Preflight local: analyse machine, outils et fichiers existants...', 8)
    const { runCodePreflight } = await import('./codePreflight.ts')
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
export async function runPlanningPhase(
  prompt: string,
  intent: CodeIntent,
  preflightReport: CodePreflightReport | null,
  configuredCodeModel: string,
  setPhase: PhaseCallback,
  onRecovery?: (event: RecoveryEvent) => void,
): Promise<string | null> {
  const model = selectModel('planning', intent, 0, configuredCodeModel)
  setPhase(`Architecte en reflexion (${getModelShortName(model)})...`, 10)
  const preflightBlock = preflightReport
    ? [
        '### PREFLIGHT LOCAL OBLIGATOIRE',
        'Le plan doit s appuyer sur ce diagnostic local avant toute decision de stack ou de configuration.',
        (await import('./codePreflight.ts')).serializeCodePreflightReport(preflightReport),
      ].join('\n')
    : ''
  const planPrompt = [
    buildArchitecteSystemPrompt(intent),
    '',
    '---',
    '',
    buildArchitecturePlanningPrompt(prompt, intent),
    preflightBlock,
  ].filter(Boolean).join('\n\n')

  try {
    const { resilientOllamaGenerate } = await import('./ollamaResilience.ts')
    const response = await resilientOllamaGenerate(model, planPrompt, {
      timeoutMs: PLANNING_TIMEOUT_MS,
      firstByteTimeoutMs: PLANNING_FIRST_BYTE_TIMEOUT_MS,
      num_ctx: CODE_PLANNING_CONTEXT_TOKENS,
      neverMemorySkip: true,
      onRecoveryAttempt: (ev) => {
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
export async function runGenerationPhase(
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

  const messages: OllamaMessage[] = [
    { role: 'system', content: buildCodeurSystemPrompt(intent, prompt) },
  ]

  if (preflightReport) {
    const { serializeCodePreflightReport } = await import('./codePreflight.ts')
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

  if (architecturePlan) {
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
    const { serializeCodeMissionDossier } = await import('./codeMissionControl.ts')
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

  const recentHistory = conversationHistory.length > 8
    ? conversationHistory.slice(-8)
    : conversationHistory
  messages.push(...recentHistory)

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
        '- Respecte le format de sortie structure `AURORA_CODE_VFS/1` avec longueur declaree pour chaque fichier complet.',
        '- Inclure un README.md decrivant comment installer et lancer le nouveau projet.',
      ].filter(Boolean).join('\n'),
    })
  } else if (existingFiles.length > 0) {
    let fileBudget = 13000
    const fileBlocks: string[] = []
    let shownCount = 0
    for (const file of existingFiles) {
      if (fileBudget <= 400) break
      const perCap = Math.min(file.content.length, Math.max(2000, fileBudget))
      const body = file.content.length > perCap
        ? `${file.content.slice(0, perCap)}\n...[fichier tronque: ${file.content.length} chars — le reste est conserve, NE le supprime pas]`
        : file.content
      fileBlocks.push(`--- FICHIER: ${file.name} ---\n\`\`\`${file.language}\n${body}\n\`\`\``)
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

  const contentChunks: string[] = []
  const generationSignal = signal
    ? AbortSignal.any([signal, AbortSignal.timeout(STREAM_GENERATION_TOTAL_TIMEOUT_MS)])
    : AbortSignal.timeout(STREAM_GENERATION_TOTAL_TIMEOUT_MS)
  try {
    const { resilientOllamaChatStream } = await import('./ollamaResilience.ts')
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
        temperature: 0.3,
        top_p: 0.8,
        top_k: 20,
        repeat_penalty: 1.05,
        num_ctx: CODE_EXPERT_CONTEXT_TOKENS,
        num_predict: CODE_EXPERT_OUTPUT_TOKENS,
        firstByteTimeoutMs: GENERATION_FIRST_BYTE_TIMEOUT_MS,
        neverMemorySkip: true,
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
      const lastFileMarker = partialContent.lastIndexOf('--- FICHIER:')
      if (lastFileMarker > 0) {
        const afterMarker = partialContent.slice(lastFileMarker)
        const openBlocks = (afterMarker.match(/```\w+/g) || []).length
        const closeBlocks = (afterMarker.match(/\n```\s*$/gm) || []).length
        if (openBlocks > closeBlocks) {
          return `${partialContent}\n\`\`\`\n`
        }
      }
      return partialContent
    }
    throw error
  }

  return contentChunks.join('')
}
