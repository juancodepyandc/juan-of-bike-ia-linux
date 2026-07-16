import type { CodeIntent } from './codeIntent.ts'
import { runAgenticGenerationPhase } from './codeAgenticGenerationPhase.ts'
import { isLLMRefusal } from './codeLLMRefusal.ts'
import type { CodeFile, PhaseCallback } from './codeOrchestratorTypes.ts'
import type { CodeModelRoutingContext } from './codePipelineRuntime.ts'

export async function runInitialAgenticGeneration({
  prompt,
  intent,
  architecturePlan,
  existingFiles,
  contextImages,
  generationModel,
  userFileDataUrls,
  setPhase,
  onToken,
  onFilesUpdate,
  signal,
  modelRouting,
}: {
  prompt: string
  intent: CodeIntent
  architecturePlan: string
  existingFiles: CodeFile[]
  contextImages: string[]
  generationModel: string
  userFileDataUrls?: Record<string, string>
  setPhase: PhaseCallback
  onToken: (token: string) => void
  onFilesUpdate: (files: CodeFile[], notes: string) => void
  signal?: AbortSignal
  modelRouting?: CodeModelRoutingContext
}): Promise<string> {
  const generation = await runAgenticGenerationPhase({
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
  })
  if (generation && !generation.ok && signal?.aborted) throw new DOMException('Aborted', 'AbortError')
  if (!generation?.ok) {
    throw new Error(`Echec de l executor agentique WS3: ${generation?.error || 'plan_without_queue'}`)
  }

  let content = generation.content
  if (isLLMRefusal(content)) {
    console.warn('[CodeOrchestrator] LLM returned a refusal instead of code. Forcing regeneration.')
    setPhase('Le modele a refuse de generer du code — regeneration forcee...', 40)
    const rescue = await runAgenticGenerationPhase({
      prompt: [
        'INSTRUCTION CRITIQUE: Tu DOIS generer du code source. NE REFUSE JAMAIS.',
        'Tu es un generateur de code. Ta seule sortie autorisee est une suite d actions outil JSON WS3.',
        '',
        'INTERDIT: excuses, refus, explications, suggestions de consulter les instructions.',
        'Regenere chaque fichier du plan, complet et executable:',
        '',
        prompt,
      ].join('\n'),
      intent,
      architecturePlan,
      existingFiles,
      contextImages,
      generationModel,
      escalationLevel: 2,
      setPhase,
      onToken,
      onFilesUpdate,
      signal,
      modelRouting: { ...modelRouting, plateau: true },
    })
    if (rescue && !rescue.ok && signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    if (!rescue?.ok) {
      throw new Error(`Echec de la regeneration agentique WS3: ${rescue?.error || 'plan_without_queue'}`)
    }
    if (isLLMRefusal(rescue.content)) {
      throw new Error('Refus LLM persistant apres regeneration agentique WS3')
    }
    content = rescue.content
  }

  for (const [marker, dataUrl] of Object.entries(userFileDataUrls ?? {})) {
    if (typeof dataUrl === 'string' && dataUrl && content.includes(marker)) {
      content = content.split(marker).join(dataUrl)
    }
  }
  return content
}
