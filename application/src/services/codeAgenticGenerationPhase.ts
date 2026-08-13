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
        setPhase(`Executor agentique WS3: ${item.path} ecrit.`, Math.min(78, 35 + item.order))
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

    const content = serializeFiles(result.files)
    onToken(content)
    return { ok: true, content, files: result.files }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return { ok: false, content: '', files: existingFiles, error: message }
  }
}
