import type { OllamaMessage } from '../types/app'
import type { CodeFile } from './codeOrchestrator.ts'
import type {
  CodeGenerationActionProducer,
} from './codeGenerationExecutor.ts'
import type {
  CodeGenerationQueue,
  CodeGenerationQueueItem,
} from './codeGenerationQueue.ts'
import {
  buildCodeGenerationActionInstructions,
  parseCodeGenerationActions,
} from './codeGenerationActionProtocol.ts'
import { buildCodeProjectMemory, selectCodeProjectMemoryContext } from './codeProjectMemory.ts'

export type CodeGenerationActionModelClient = (
  model: string,
  messages: OllamaMessage[],
  options: { signal?: AbortSignal; num_ctx?: number; firstByteTimeoutMs?: number },
) => Promise<unknown>

export type CodeGenerationActionProducerOptions = {
  prompt: string
  model: string
  architecturePlan?: string | null
  contextImages?: string[]
  maxFileContextChars?: number
  signal?: AbortSignal
  numCtx?: number
  firstByteTimeoutMs?: number
  chatClient?: CodeGenerationActionModelClient
  onRawResponse?: (args: { item: CodeGenerationQueueItem; raw: string }) => void
}

function extractAssistantContent(response: unknown) {
  if (typeof response === 'string') return response
  if (!response || typeof response !== 'object') return ''
  const record = response as Record<string, unknown>
  if (typeof record.response === 'string') return record.response
  const message = record.message && typeof record.message === 'object'
    ? record.message as Record<string, unknown>
    : null
  return typeof message?.content === 'string' ? message.content : ''
}

function cap(text: string, max: number) {
  if (text.length <= max) return text
  const head = Math.max(0, Math.floor(max * 0.65))
  const tail = Math.max(0, max - head - 80)
  return `${text.slice(0, head)}\n...[tronque ${text.length - max} chars]...\n${text.slice(-tail)}`
}

function formatRelevantFiles(files: CodeFile[], item: CodeGenerationQueueItem, prompt: string, maxChars: number) {
  const byPath = new Map(files.map((file) => [file.name.replace(/\\/g, '/').toLowerCase(), file]))
  const selected = selectCodeProjectMemoryContext({
    memory: buildCodeProjectMemory(files),
    item,
    prompt,
    maxFiles: 8,
  })
  if (selected.length === 0) return 'Aucun fichier existant pertinent dans le contexte cible.'

  let remaining = maxChars
  const blocks: string[] = []
  for (const selection of selected) {
    const file = byPath.get(selection.file.path.replace(/\\/g, '/').toLowerCase())
    if (!file) continue
    if (remaining <= 200) break
    const header = `--- EXISTING ${file.name} (${file.language || 'text'}; raisons=${selection.reasons.join(',')}) ---`
    const body = cap(file.content, Math.max(200, remaining - header.length - 12))
    blocks.push(`${header}\n${body}`)
    remaining -= header.length + body.length + 2
  }
  return blocks.join('\n\n')
}

function formatQueueWindow(queue: CodeGenerationQueue, item: CodeGenerationQueueItem) {
  const index = queue.items.findIndex((entry) => entry.path === item.path)
  const start = Math.max(0, index - 3)
  const end = Math.min(queue.items.length, index + 4)
  return queue.items.slice(start, end).map((entry) => [
    entry.order === item.order ? '->' : '  ',
    `${entry.order}. ${entry.path}`,
    entry.required ? 'required' : 'optional',
    entry.language || 'lang?',
    entry.role,
  ].filter(Boolean).join(' | ')).join('\n')
}

export function buildCodeGenerationActionMessages(args: {
  item: CodeGenerationQueueItem
  itemIndex: number
  queue: CodeGenerationQueue
  files: CodeFile[]
  prompt: string
  architecturePlan?: string | null
  contextImages?: string[]
  maxFileContextChars?: number
}): OllamaMessage[] {
  const maxContext = args.maxFileContextChars ?? 12_000
  const userMessage: OllamaMessage = {
    role: 'user',
    content: [
      '## DEMANDE UTILISATEUR',
      args.prompt,
      '',
      args.architecturePlan ? `## PLAN ARCHITECTE JSON\n${cap(args.architecturePlan, 8_000)}` : '',
      '',
      '## FENETRE DE QUEUE',
      formatQueueWindow(args.queue, args.item),
      '',
      '## CONTEXTE FICHIERS CIBLE',
      formatRelevantFiles(args.files, args.item, args.prompt, maxContext),
      '',
      '## CONTRAT DE SORTIE',
      buildCodeGenerationActionInstructions(args.item),
    ].filter(Boolean).join('\n\n'),
  }
  if (args.contextImages?.length) userMessage.images = args.contextImages
  return [
    {
      role: 'system',
      content: [
        '# ROLE: EXECUTOR WS3 A OUTILS',
        'Tu produis uniquement des actions outil JSON pour le VFS AuroraIA.',
        'Tu ne livres jamais un blob projet complet dans ce mode.',
        'Chaque action doit etre minimale, complete et directement executable par le runner.',
        'Pour un fichier required, l action finale doit rendre le fichier present et complet.',
      ].join('\n'),
    },
    userMessage,
  ]
}

async function defaultChatClient(
  model: string,
  messages: OllamaMessage[],
  options: { signal?: AbortSignal; num_ctx?: number; firstByteTimeoutMs?: number },
) {
  const { resilientOllamaChat } = await import('./ollamaResilience.ts')
  return resilientOllamaChat(model, messages, 0.2, {
    signal: options.signal,
    num_ctx: options.num_ctx,
    firstByteTimeoutMs: options.firstByteTimeoutMs,
    neverMemorySkip: true,
  })
}

export function createCodeGenerationLLMActionProducer(
  options: CodeGenerationActionProducerOptions,
): CodeGenerationActionProducer {
  const chatClient = options.chatClient ?? defaultChatClient
  return async ({ item, itemIndex, queue, files }) => {
    const messages = buildCodeGenerationActionMessages({
      item,
      itemIndex,
      queue,
      files,
      prompt: options.prompt,
      architecturePlan: options.architecturePlan,
      contextImages: options.contextImages,
      maxFileContextChars: options.maxFileContextChars,
    })
    const response = await chatClient(options.model, messages, {
      signal: options.signal,
      num_ctx: options.numCtx,
      firstByteTimeoutMs: options.firstByteTimeoutMs,
    })
    const raw = extractAssistantContent(response)
    options.onRawResponse?.({ item, raw })
    const parsed = parseCodeGenerationActions(raw)
    if (!parsed.ok) {
      throw new Error(`action_protocol_invalid:${parsed.errors.join(',')}`)
    }
    return parsed.actions
  }
}
