import type { CodeFile } from './codeOrchestrator.ts'
import { normalizeProjectPath } from './codeProjectTree.ts'
import {
  type CodeGenerationQueue,
  type CodeGenerationQueueItem,
} from './codeGenerationQueue.ts'
import {
  type CodeGenerationToolAction,
  type CodeGenerationToolResult,
  type CodeGenerationToolRunner,
  executeCodeGenerationTool,
} from './codeGenerationTools.ts'
import {
  buildCodeStreamDoneEvent,
  buildCodeStreamErrorEvent,
  buildCodeStreamFileWrittenEvents,
  buildCodeStreamPhaseEvent,
  type CodeStreamEvent,
  type CodeStreamEventMeta,
} from './codeStreamEvents.ts'

export type CodeGenerationActionProducer = (args: {
  item: CodeGenerationQueueItem
  itemIndex: number
  queue: CodeGenerationQueue
  files: CodeFile[]
}) => Promise<CodeGenerationToolAction[]>

export type CodeGenerationExecutorToolResult = {
  item: CodeGenerationQueueItem
  result: CodeGenerationToolResult
}

export type CodeGenerationExecutorOptions = {
  queue: CodeGenerationQueue
  initialFiles?: CodeFile[]
  produceActions: CodeGenerationActionProducer
  nextMeta: () => CodeStreamEventMeta
  runner?: CodeGenerationToolRunner
  onEvent?: (event: CodeStreamEvent) => void
  onFilesUpdate?: (files: CodeFile[], item: CodeGenerationQueueItem, result: CodeGenerationToolResult) => void
  includeFileContentInEvents?: boolean
  stopOnOptionalFailure?: boolean
}

export type CodeGenerationExecutorResult = {
  ok: boolean
  files: CodeFile[]
  events: CodeStreamEvent[]
  toolResults: CodeGenerationExecutorToolResult[]
  completedItems: number
  error?: string
  failedItem?: CodeGenerationQueueItem
}

function normalizeComparablePath(path: string) {
  return normalizeProjectPath(path)?.toLowerCase() ?? ''
}

function hasGeneratedFile(files: CodeFile[], item: CodeGenerationQueueItem) {
  const expected = normalizeComparablePath(item.path)
  if (!expected) return false
  return files.some((file) => normalizeComparablePath(file.name) === expected && file.content.length > 0)
}

function progressForItem(itemIndex: number, total: number) {
  if (total <= 0) return 35
  return Math.max(35, Math.min(75, 35 + Math.round(((itemIndex + 1) / total) * 40)))
}

export async function executeCodeGenerationQueue(
  options: CodeGenerationExecutorOptions,
): Promise<CodeGenerationExecutorResult> {
  let files = [...(options.initialFiles ?? [])]
  const events: CodeStreamEvent[] = []
  const toolResults: CodeGenerationExecutorToolResult[] = []
  let completedItems = 0

  const emit = (event: CodeStreamEvent) => {
    events.push(event)
    options.onEvent?.(event)
  }

  emit(buildCodeStreamPhaseEvent({
    ...options.nextMeta(),
    phase: 'generation',
    message: `Executor WS3: ${options.queue.items.length} fichier(s) a traiter.`,
    progress: 35,
  }))

  for (let itemIndex = 0; itemIndex < options.queue.items.length; itemIndex++) {
    const item = options.queue.items[itemIndex]
    emit(buildCodeStreamPhaseEvent({
      ...options.nextMeta(),
      phase: 'generation',
      message: `Executor WS3: fichier ${item.order}/${options.queue.items.length} — ${item.path}`,
      progress: progressForItem(itemIndex, options.queue.items.length),
    }))

    let actions: CodeGenerationToolAction[]
    try {
      actions = await options.produceActions({ item, itemIndex, queue: options.queue, files })
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      const code = `action_producer_failed:${message}`
      // Un fichier SECONDAIRE illisible ne vaut pas la perte du projet entier.
      // Le producteur a deja retente plusieurs fois avec des consignes
      // differentes; s il echoue encore sur un fichier non requis, on le note
      // et on continue. Un fichier requis, lui, reste bloquant: sans point
      // d entree il n y a pas de livrable.
      if (!item.required) {
        emit(buildCodeStreamErrorEvent({ ...options.nextMeta(), message: `${code}:${item.path}`, recoverable: true }))
        emit(buildCodeStreamPhaseEvent({
          ...options.nextMeta(),
          phase: 'generation',
          message: `Executor WS3: ${item.path} illisible apres plusieurs tentatives — fichier saute, generation poursuivie.`,
          progress: progressForItem(itemIndex, options.queue.items.length),
        }))
        continue
      }
      emit(buildCodeStreamErrorEvent({ ...options.nextMeta(), message: code, recoverable: item.required }))
      return { ok: false, files, events, toolResults, completedItems, error: code, failedItem: item }
    }

    if (actions.length === 0) {
      if (item.required && !hasGeneratedFile(files, item)) {
        const code = 'required_item_actions_empty'
        emit(buildCodeStreamErrorEvent({ ...options.nextMeta(), message: `${code}:${item.path}`, recoverable: true }))
        return { ok: false, files, events, toolResults, completedItems, error: code, failedItem: item }
      }
      completedItems += 1
      continue
    }

    for (const action of actions) {
      const previousFiles = files
      const result = await executeCodeGenerationTool(files, action, options.runner)
      toolResults.push({ item, result })

      if (!result.ok) {
        // Un patch qui ne retrouve pas sa cible sur un fichier DEJA ecrit et
        // non vide n est pas une raison de perdre tout le run. Mesure reelle:
        // apres 36 fichiers et 46 minutes, un seul `patch_search_not_found`
        // faisait remonter `agentic_retry_failed` jusqu a l erreur fatale. Le
        // fichier existe et reste valide: on trace et on continue, la boucle de
        // correction re-jugera le livrable.
        const targetExists = result.path
          ? (files.find((f) => f.name === result.path)?.content ?? '').trim().length > 0
          : false
        if (result.error === 'patch_search_not_found' && targetExists) {
          emit(buildCodeStreamErrorEvent({
            ...options.nextMeta(),
            message: `patch_ignore:${result.error}:${item.path}`,
            recoverable: true,
          }))
          continue
        }
        if (item.required || options.stopOnOptionalFailure) {
          emit(buildCodeStreamErrorEvent({
            ...options.nextMeta(),
            message: `${result.error ?? 'tool_failed'}:${item.path}`,
            recoverable: true,
          }))
          return {
            ok: false,
            files,
            events,
            toolResults,
            completedItems,
            error: result.error ?? 'tool_failed',
            failedItem: item,
          }
        }
        continue
      }

      files = result.files
      options.onFilesUpdate?.(files, item, result)
      for (const event of buildCodeStreamFileWrittenEvents({
        files,
        previousFiles,
        nextMeta: options.nextMeta,
        includeContent: options.includeFileContentInEvents,
      })) {
        emit(event)
      }
    }

    if (item.required && !hasGeneratedFile(files, item)) {
      const code = 'required_file_not_written'
      emit(buildCodeStreamErrorEvent({ ...options.nextMeta(), message: `${code}:${item.path}`, recoverable: true }))
      return { ok: false, files, events, toolResults, completedItems, error: code, failedItem: item }
    }
    completedItems += 1
  }

  const requiredDelivered = options.queue.items.filter((item) => !item.required || hasGeneratedFile(files, item)).length
  const coverage = options.queue.items.length > 0
    ? Math.round((requiredDelivered / options.queue.items.length) * 100)
    : 100
  emit(buildCodeStreamDoneEvent({
    ...options.nextMeta(),
    files,
    finalScore: coverage,
    totalAttempts: 1,
    notes: `Executor WS3 termine: ${completedItems}/${options.queue.items.length} entree(s) traitees. Validation WS7 separee.`,
  }))

  return { ok: true, files, events, toolResults, completedItems }
}
