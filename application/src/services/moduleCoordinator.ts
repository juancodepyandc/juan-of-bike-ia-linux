import { AUXILIARY_ANALYSIS_MODEL } from '../config/models'
import { ollamaGenerate } from '../hooks/useTauri'
import { sharedMemory } from './sharedMemory'

interface HelpRequest {
  fromModule: string
  problem: string
  context: string
  timestamp: number
}

interface HelpResult {
  suggestion: string
  webContext?: string
  fromModule: string
}

const helpLog: HelpRequest[] = []

export const moduleCoordinator = {
  async requestCrossModuleHelp(
    fromModule: string,
    problem: string,
    context: string,
    model = AUXILIARY_ANALYSIS_MODEL,
  ): Promise<HelpResult> {
    const request: HelpRequest = { fromModule, problem, context, timestamp: Date.now() }
    helpLog.push(request)

    try {
      const resp = await ollamaGenerate(model, `/no_think
Module "${fromModule}" is stuck with this problem: ${problem}
Context: ${context}
Suggest a concrete fix or improvement in 2-3 sentences.`)

      const suggestion = resp?.response || 'Essaie de reformuler le prompt avec plus de details specifiques.'
      return { suggestion, fromModule }
    } catch {
      return { suggestion: 'Reformule le prompt avec plus de details.', fromModule }
    }
  },

  notifyGenerationComplete(module: string, promptHash: string, result: unknown): void {
    sharedMemory.setModuleResult(module, promptHash, result)
  },

  getExistingResult<T = unknown>(module: string, promptHash: string): T | undefined {
    return sharedMemory.getModuleResult<T>(module, promptHash)
  },

  getHelpLog(): HelpRequest[] {
    return [...helpLog]
  },
}
