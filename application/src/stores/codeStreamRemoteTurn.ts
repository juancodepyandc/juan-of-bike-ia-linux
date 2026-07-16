import { streamCodeGenerationFromBridge } from '../services/codeBridgeStreamClient.ts'
import type { CodeStreamEvent } from '../services/codeStreamEvents.ts'
import type { OllamaMessage } from '../types/app.ts'
import { useModuleHistoryStore } from './moduleHistoryStore.ts'
import { summariseDelivery } from './codeStreamProgress.ts'
import { applyRemoteCodeStreamEvent, phaseFromRemoteCodeStreamEvent } from './codeStreamRemoteState.ts'
import type { CodeStreamState, CodeStreamStore, CodeWorkMode } from './codeStreamTypes.ts'

type SetCodeStreamState = (
  next: Partial<CodeStreamStore> | ((state: CodeStreamStore) => Partial<CodeStreamStore>),
) => void

export type CodeBridgeStreamTurnArgs = {
  prompt: string
  model: string
  signal: AbortSignal
  workMode: CodeWorkMode
  isCorrection: boolean
  priorMessagesCount: number
  existingFilesCount: number
  isCurrent: () => boolean
  get: () => CodeStreamStore
  set: SetCodeStreamState
  applyNarration: (phase: CodeStreamState['phase']) => void
}

export function shouldUseCodeBridgeStream(args: {
  workMode: CodeWorkMode
  isCorrection: boolean
  priorMessagesCount: number
  existingFilesCount: number
}) {
  const configured = import.meta.env?.VITE_CODE_STREAM_ENGINE
  if (configured === 'local') return false
  if (configured === 'bridge') return true
  return false
}

function appendAssistantDelivery(set: SetCodeStreamState, filesCount: number, score: number) {
  set((prev) => {
    const deliverySummary = summariseDelivery(prev.files, score)
    const assistantTurn: OllamaMessage = { role: 'assistant', content: deliverySummary }
    useModuleHistoryStore.getState().pushMessage('code', { role: 'assistant', content: deliverySummary })
    return {
      messages: [...prev.messages, assistantTurn],
      errorDialog: filesCount > 0 ? prev.errorDialog : {
        title: 'Aucun fichier livré',
        message: 'Le flux /api/code/generate/stream s’est terminé sans fichier exploitable.',
        suggestion: 'Précise la demande puis relance la génération.',
      },
      phase: filesCount > 0 ? prev.phase : 'error',
      streaming: filesCount > 0 ? prev.streaming : false,
    }
  })
}

export async function runCodeBridgeStreamTurn(args: CodeBridgeStreamTurnArgs) {
  if (!shouldUseCodeBridgeStream(args)) return false

  let receivedEvent = false
  await streamCodeGenerationFromBridge({
    prompt: args.prompt,
    model: args.model,
    signal: args.signal,
    onEvent: async (event: CodeStreamEvent) => {
      receivedEvent = true
      if (!args.isCurrent()) return
      args.set((prev) => applyRemoteCodeStreamEvent(prev, event))
      args.applyNarration(phaseFromRemoteCodeStreamEvent(event))
      if (event.kind === 'done') appendAssistantDelivery(args.set, event.filesCount, event.finalScore)
    },
  }).catch((error) => {
    if (receivedEvent || args.signal.aborted) throw error
    args.set((prev) => ({
      phaseMessage: `Route /api/code/generate/stream indisponible, bascule orchestrateur local: ${error instanceof Error ? error.message : String(error)}`,
      events: prev.events,
    }))
  })

  return receivedEvent
}
