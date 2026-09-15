import type { RecoveryEvent } from './ollamaResilience.ts'
import {
  type CodeIntent,
  type CodeIntentContext,
  buildArchitecturePlanningPrompt,
  classifyCodeIntent,
} from './codeIntent.ts'
import type { CodeFile, PhaseCallback } from './codeOrchestrator.ts'
import { buildArchitecteSystemPrompt } from './codeSystemPrompts.ts'
import { buildProjectTypeStackContract } from './codeProjectTypeStackContract.ts'
import { buildProjectGeneratorPromptBlock } from './codeProjectGeneratorRegistry.ts'
import { detectDesignArchetype } from './codeDesignDirectives.ts'
import { buildCodeDesignSpec, formatCodeDesignSpecPrompt } from './codeDesignSpec.ts'
import type { CodePreflightReport } from './codePreflight.ts'
import { withTimeout } from './llmTimebox.ts'
import { parseArchitecturePlanJson } from './codeArchitecturePlan.ts'
import {
  getArchitecturePlanCandidateCount,
  selectBestArchitecturePlan,
} from './codeArchitecturePlanSelection.ts'
import {
  CODE_PLANNING_CONTEXT_TOKENS,
  PLANNING_FIRST_BYTE_TIMEOUT_MS,
  PLANNING_TIMEOUT_MS,
  PREFLIGHT_PHASE_TIMEOUT_MS,
  getModelShortName,
  selectModel,
  type CodeModelRoutingContext,
} from './codePipelineRuntime.ts'

export function isArchitecturePlanUsable(plan: string | null) {
  return parseArchitecturePlanJson(plan).ok
}

const INTENT_SEMANTIC_TIMEOUT_MS = 45000
const INTENT_SEMANTIC_FIRST_BYTE_MS = 30000

/**
 * Phase 1: classify intent. Utilise le classifieur semantique LLM (WS6) pour
 * couvrir la taxonomie etendue (compiler, os_kernel, distributed_system,
 * mobile natif, embedded...) que les regex ne reperent pas, avec repli
 * DETERMINISTE garanti sur le classifieur heuristique (pas de modele, echec
 * LLM, JSON invalide, confiance < seuil, ou timeout).
 */
export async function runIntentPhase(
  prompt: string,
  setPhase: PhaseCallback,
  context?: CodeIntentContext,
  options?: { configuredCodeModel?: string; signal?: AbortSignal },
): Promise<CodeIntent> {
  setPhase('Classification du projet...', 5)
  const heuristic = classifyCodeIntent(prompt, context)
  const model = options?.configuredCodeModel
  if (!model) return heuristic

  try {
    const [{ classifyCodeIntentWithSemanticModel }, { resilientOllamaChat }] = await Promise.all([
      import('./codeSemanticIntentClassifier.ts'),
      import('./ollamaResilience.ts'),
    ])
    const result = await withTimeout(
      classifyCodeIntentWithSemanticModel({
        prompt,
        signal: options?.signal,
        minConfidence: 0.65,
        modelClient: (messages, opts) =>
          resilientOllamaChat(model, messages, 0.1, {
            signal: opts?.signal ?? options?.signal,
            firstByteTimeoutMs: INTENT_SEMANTIC_FIRST_BYTE_MS,
            num_ctx: 4096,
          }),
      }),
      { label: 'Code intent classification', timeoutMs: INTENT_SEMANTIC_TIMEOUT_MS },
    )
    if (result.source === 'semantic_model') {
      // Le modele ne peut pas renverser une heuristique confiante sans le
      // moindre indice lexical: un run reel a classe une landing page de marque
      // en `ide`, ce qui change l archetype, le contrat de livraison et les
      // commandes. Et c est non deterministe — meme prompt, verdict different
      // d un run a l autre.
      const { decideSemanticIntentOverride } = await import('./codeSemanticIntentGuard.ts')
      const decision = decideSemanticIntentOverride({
        prompt,
        heuristic,
        semantic: result.intent,
      })
      if (decision.accept) {
        setPhase(`Classification semantique: ${result.intent.projectType} (LLM)`, 6)
        return result.intent
      }
      setPhase(
        `Classification semantique ecartee (${result.intent.projectType} non corrobore) -> ${heuristic.projectType}`,
        6,
      )
      return heuristic
    }
  } catch {
    // Repli silencieux et sur sur l heuristique context-aware.
  }
  return heuristic
}

/** Phase 1.5: inspect the machine and current project before planning. */
export async function runPreflightPhase(
  prompt: string,
  intent: CodeIntent,
  existingFiles: CodeFile[],
  configuredCodeModel: string,
  setPhase: PhaseCallback,
  modelRouting?: CodeModelRoutingContext,
): Promise<CodePreflightReport | null> {
  try {
    setPhase('Preflight local: analyse machine, outils et fichiers existants...', 8)
    const { runCodePreflight } = await import('./codePreflight.ts')
    return await withTimeout(runCodePreflight({
      prompt,
      intent,
      existingFiles,
      model: selectModel('planning', intent, 0, configuredCodeModel, modelRouting),
      setPhase: (detail, progress) => setPhase(detail, Math.max(8, Math.min(18, progress))),
    }), {
      label: 'Code preflight',
      timeoutMs: PREFLIGHT_PHASE_TIMEOUT_MS,
    })
  } catch {
    setPhase('Preflight local indisponible - poursuite avec les informations connues...', 12)
    return null
  }
}

/** Phase 2: produce the structured plan required by the WS3 executor. */
export async function runPlanningPhase(
  prompt: string,
  intent: CodeIntent,
  preflightReport: CodePreflightReport | null,
  configuredCodeModel: string,
  setPhase: PhaseCallback,
  onRecovery?: (event: RecoveryEvent) => void,
  modelRouting?: CodeModelRoutingContext,
): Promise<string> {
  const model = selectModel('planning', intent, 0, configuredCodeModel, modelRouting)
  setPhase(`Architecte en reflexion (${getModelShortName(model)})...`, 15)
  const preflightBlock = preflightReport
    ? [
        '### PREFLIGHT LOCAL OBLIGATOIRE',
        'Le plan doit s appuyer sur ce diagnostic local avant toute decision de stack ou de configuration.',
        (await import('./codePreflight.ts')).serializeCodePreflightReport(preflightReport),
      ].join('\n')
    : ''
  // WS6: pour les cibles etendues (compiler, os_kernel, distributed_system,
  // mobile natif, embedded, engine_3d, ide, desktop_app), injecte les fichiers
  // structurels attendus + la barre qualite du generateur specialise dans le
  // plan. Chaine vide (sans effet) pour les types web courants.
  const generatorBlock = buildProjectGeneratorPromptBlock(intent)
  // WS10: injecte la design-spec platform-aware (le meme contrat verifie ensuite
  // par le gate design-spec) pour que la plateforme correcte soit visee des le
  // plan — pas de contrat CSS web pour du mobile natif ou un jeu canvas.
  const designSpecBlock = formatCodeDesignSpecPrompt(
    buildCodeDesignSpec(prompt, intent, detectDesignArchetype(prompt, intent)),
  )
  // Le type de projet doit etre une CONTRAINTE, pas une information: sans ce
  // bloc, le prompt invite le modele a choisir "la stack la plus moderne" et il
  // repond Next.js sur une intention static_web.
  const projectTypeContract = buildProjectTypeStackContract(intent)
  const planPrompt = [
    buildArchitecteSystemPrompt(intent),
    '',
    '---',
    '',
    projectTypeContract,
    '',
    buildArchitecturePlanningPrompt(prompt, intent),
    generatorBlock,
    designSpecBlock,
    preflightBlock,
  ].filter(Boolean).join('\n\n')

  try {
    // Anti-crash residence: decharge tout autre gros modele code avant le
    // planificateur (devstral) — un seul gros modele resident a la fois.
    const { ensureExclusiveCodeModel } = await import('./codeModelResidency.ts')
    await ensureExclusiveCodeModel(model)
    const { resilientOllamaGenerate } = await import('./ollamaResilience.ts')
    const candidateCount = getArchitecturePlanCandidateCount(intent)
    const rawCandidates: string[] = []
    for (let candidateIndex = 0; candidateIndex < candidateCount; candidateIndex++) {
      if (candidateCount > 1) {
        setPhase(
          `Architecte best-of-${candidateCount} - candidat ${candidateIndex + 1}/${candidateCount}...`,
          16 + Math.round(((candidateIndex + 1) / candidateCount) * 8),
        )
      }
      const response = await resilientOllamaGenerate(
        model,
        candidateIndex === 0
          ? planPrompt
          : `${planPrompt}\n\nVARIANTE ${candidateIndex + 1}: produis une architecture alternative, toujours au meme schema JSON, avec une meilleure decomposition si possible.`,
        {
          timeoutMs: PLANNING_TIMEOUT_MS,
          firstByteTimeoutMs: PLANNING_FIRST_BYTE_TIMEOUT_MS,
          num_ctx: CODE_PLANNING_CONTEXT_TOKENS,
          neverMemorySkip: true,
          onRecoveryAttempt: (event) => {
            if (event.action !== 'retry') {
              setPhase(`Architecte - ${event.action}...`, 18)
              onRecovery?.(event)
            }
          },
        },
      )
      rawCandidates.push(response?.response?.trim() || '')
    }

    const selection = selectBestArchitecturePlan(rawCandidates, intent)
    if (selection.selected?.serialized) {
      const suffix = candidateCount > 1
        ? ` (best-of-${candidateCount}, candidat ${selection.selected.index + 1})`
        : ''
      // L executor ne peut ecrire QUE les fichiers de la file issue du plan.
      // Un plan sans porte d entree condamne donc le run: la porte de livraison
      // refuse, la boucle regenere le meme plan, et les passes s epuisent sur un
      // defaut que personne ne corrige. Reparation deterministe, sans appel
      // modele supplementaire (le budget VRAM ne supporte pas une replanification).
      const { ensureArchitecturePlanEntryFiles } = await import('./codeArchitecturePlanEntryContract.ts')
      const repaired = ensureArchitecturePlanEntryFiles(selection.selected.serialized, intent)
      if (repaired.added.length > 0) {
        setPhase(
          `Plan d architecture complete${suffix}: porte d entree ajoutee (${repaired.added.join(', ')}) - lancement de la generation agentique...`,
          25,
        )
        return repaired.plan
      }
      setPhase(`Plan d architecture pret${suffix} - lancement de la generation agentique...`, 25)
      return repaired.plan
    }

    const errors = selection.scored.flatMap((candidate) => candidate.errors).slice(0, 3)
    throw new Error(`architecture_plan_invalid:${errors.join(',') || 'empty_response'}`)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.warn('[CodeOrchestrator] Structured planning failed:', message)
    // Un architecte defaillant ne doit plus tuer le run. Le repli existait deja
    // un etage plus bas (buildGenerationQueueWithFallback derive une file depuis
    // l intent seul) mais n etait jamais atteint: ce `throw`, puis celui de
    // isArchitecturePlanUsable, se declenchaient avant. On synthetise donc un
    // plan deterministe depuis l intent, valide au meme schema, et le pipeline
    // continue. Zero appel modele supplementaire.
    const { buildFallbackArchitecturePlan } = await import('./codeArchitecturePlanFallback.ts')
    const fallback = buildFallbackArchitecturePlan(intent, prompt)
    if (isArchitecturePlanUsable(fallback)) {
      setPhase(
        `Plan d architecte inexploitable (${message.slice(0, 60)}) - repli deterministe derive de l intent, generation poursuivie...`,
        25,
      )
      return fallback
    }
    setPhase(`Plan d architecture inexploitable - generation bloquee (${message.slice(0, 80)})`, 22)
    throw new Error(`Echec du plan d architecture structure: ${message}`)
  }
}
