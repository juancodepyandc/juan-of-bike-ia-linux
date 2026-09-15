import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile, PhaseCallback } from './codeOrchestrator.ts'
import type { CodeModelRoutingContext } from './codePipelineRuntime.ts'
import {
  CODE_EXPERT_CONTEXT_TOKENS,
  CODE_EXPERT_OUTPUT_TOKENS,
  GENERATION_FIRST_BYTE_TIMEOUT_MS,
  STREAM_GENERATION_TOTAL_TIMEOUT_MS,
  selectModel,
} from './codePipelineRuntime.ts'
import { withTimeout } from './llmTimebox.ts'
import { serializeProjectTreeEmission } from './codeProjectEmission.ts'
import { buildGenerationQueueWithFallback } from './codeGenerationQueue.ts'
import { describeBinaryAssetSkip } from './codeBinaryAssetPaths.ts'
import {
  buildCompletionQueueItems,
  describeMissingModules,
  findUnresolvedLocalImports,
} from './codeMissingModuleCompletion.ts'

/** Deux tours: un module cree peut a son tour en importer un autre. Pas plus:
 * chaque tour est un appel modele par fichier, et le budget VRAM est fini. */
const MISSING_MODULE_ROUNDS = 2
import { executeCodeGenerationQueue } from './codeGenerationExecutor.ts'
import {
  createCodeGenerationLLMActionProducer,
  type CodeGenerationActionModelClient,
} from './codeGenerationActionProducer.ts'
import { createCodeGenerationSandboxRunner } from './codeGenerationCommandRunner.ts'

export type AgenticGenerationPhaseResult = {
  ok: boolean
  content: string
  files: CodeFile[]
  error?: string
}

function createMetaFactory() {
  const runId = Date.now()
  let sequence = 0
  return () => ({ runId, sequence: ++sequence, timestamp: Date.now() })
}

function serializeFiles(files: CodeFile[]) {
  return serializeProjectTreeEmission(files.map((file) => ({
    path: file.name,
    content: file.content,
    language: file.language,
  })))
}

export async function runAgenticGenerationPhase({
  prompt,
  intent,
  architecturePlan,
  existingFiles,
  contextImages,
  generationModel,
  setPhase,
  onToken,
  onFilesUpdate,
  signal,
  modelRouting,
  chatClient,
  escalationLevel = 0,
}: {
  prompt: string
  intent: CodeIntent
  architecturePlan: string | null
  existingFiles: CodeFile[]
  contextImages: string[]
  generationModel: string
  setPhase: PhaseCallback
  onToken: (token: string) => void
  onFilesUpdate?: (files: CodeFile[], notes: string) => void
  signal?: AbortSignal
  modelRouting?: CodeModelRoutingContext
  chatClient?: CodeGenerationActionModelClient
  escalationLevel?: number
}): Promise<AgenticGenerationPhaseResult | null> {
  // Repli garanti: si le plan d architecture ne parse pas en file exploitable,
  // on synthetise une file par defaut depuis l intent au lieu d echouer a 0
  // fichier (cause reelle de "Erreur fatale du pipeline: plan_without_queue").
  const { queue, usedFallback } = buildGenerationQueueWithFallback(architecturePlan, intent)
  if (queue.items.length === 0) return null

  const model = selectModel('generation', intent, escalationLevel, generationModel, modelRouting)
  setPhase(
    usedFallback
      ? `Executor agentique WS3: plan non exploitable -> file de repli (${queue.items.length} fichier(s))...`
      : `Executor agentique WS3: ${queue.items.length} fichier(s) a produire...`,
    35,
  )
  // Un saut silencieux serait un echec silencieux de plus: on nomme ce que la
  // file ne demandera PAS au modele, et pourquoi.
  const binarySkip = describeBinaryAssetSkip(queue.binaryAssetPaths)
  if (binarySkip) setPhase(`Executor agentique WS3: ${binarySkip}`, 35)
  const producer = createCodeGenerationLLMActionProducer({
    prompt,
    model,
    // Sans l intent, l executor perd le verrouillage marque et la barre de
    // qualite: c est precisement ce qui rendait les generations "basiques".
    intent,
    architecturePlan,
    contextImages,
    signal,
    numCtx: CODE_EXPERT_CONTEXT_TOKENS,
    // Sans plafond explicite, certains presets Modelfile coupent la generation
    // a 256-1024 tokens: le fichier arrive tronque et la charge d actions JSON
    // devient invalide. La constante existait deja, elle n etait jamais passee.
    numPredict: CODE_EXPERT_OUTPUT_TOKENS,
    firstByteTimeoutMs: GENERATION_FIRST_BYTE_TIMEOUT_MS,
    chatClient,
  })

  try {
    // Plafond TOTAL de la generation. Seul un delai de premier octet etait
    // applique: un modele qui streame lentement sans jamais finir bloquait le
    // pipeline indefiniment, VRAM occupee. La constante existait, elle n etait
    // branchee nulle part.
    const result = await withTimeout(executeCodeGenerationQueue({
      queue,
      initialFiles: existingFiles,
      produceActions: producer,
      nextMeta: createMetaFactory(),
      runner: createCodeGenerationSandboxRunner(),
      onFilesUpdate: (files, item) => {
        const itemPct = 35 + Math.round((item.order / Math.max(1, queue.items.length)) * 30)
        setPhase(`Executor agentique WS3 (${item.order}/${queue.items.length}): ${item.path}`, Math.min(68, itemPct))
        onFilesUpdate?.(files, `Generation agentique WS3 en cours: ${item.order}/${queue.items.length}`)
      },
    }), { label: 'Generation agentique WS3', timeoutMs: STREAM_GENERATION_TOTAL_TIMEOUT_MS })

    if (!result.ok) {
      return {
        ok: false,
        content: '',
        files: result.files,
        error: result.error ?? 'agentic_generation_failed',
      }
    }

    // Un composant IMPORTE est un composant VOULU. Run 1121: le code livre
    // importait `src/components/Logo` et `src/components/StorySection`, que la
    // file ne demandait pas — d ou 234 erreurs TS2307 et huit passes a discuter
    // de typage pendant que des fichiers entiers manquaient. Le constat est
    // exact et mecanique, donc on ne le delegue pas: on complete la file.
    let finalFiles = result.files
    for (let round = 1; round <= MISSING_MODULE_ROUNDS; round += 1) {
      const missing = findUnresolvedLocalImports(finalFiles)
      if (missing.length === 0) break
      setPhase(`Executor agentique WS3: ${describeMissingModules(missing)} — completion ${round}/${MISSING_MODULE_ROUNDS}...`, 78)
      const completion = await withTimeout(executeCodeGenerationQueue({
        queue: { ...queue, items: buildCompletionQueueItems(missing, queue.items.length + 1) },
        initialFiles: finalFiles,
        produceActions: producer,
        nextMeta: createMetaFactory(),
        runner: createCodeGenerationSandboxRunner(),
        onFilesUpdate: (files, item) => {
          setPhase(`Executor agentique WS3: ${item.path} ecrit (module manquant).`, 79)
          onFilesUpdate?.(files, `Completion des modules manquants: ${item.path}`)
        },
      }), { label: 'Completion WS3 des modules manquants', timeoutMs: STREAM_GENERATION_TOTAL_TIMEOUT_MS })
      // Une completion qui echoue ne detruit rien: on garde ce qu elle a ecrit.
      if (completion.files.length > finalFiles.length) finalFiles = completion.files
      else break
    }

    const content = serializeFiles(finalFiles)
    onToken(content)
    return { ok: true, content, files: finalFiles }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return { ok: false, content: '', files: existingFiles, error: message }
  }
}
