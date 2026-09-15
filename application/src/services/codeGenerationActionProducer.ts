import type { OllamaMessage } from '../types/app.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import type { CodeIntent } from './codeIntent.ts'
import { buildExecutorQualityContract } from './codeExecutorQualityContract.ts'
import type {
  CodeGenerationActionProducer,
} from './codeGenerationExecutor.ts'
import {
  formatGenerationQueueForPrompt,
  type CodeGenerationQueue,
  type CodeGenerationQueueItem,
} from './codeGenerationQueue.ts'
import {
  buildCodeGenerationActionInstructions,
  parseCodeGenerationActions,
} from './codeGenerationActionProtocol.ts'
import { selectCodeProjectMemoryContext } from './codeProjectMemory.ts'
import { loadOrBuildCodeProjectMemory } from './codeProjectMemoryPersistence.ts'
import {
  buildCodeIncrementalPatchScope,
  formatCodeIncrementalPatchScope,
} from './codeIncrementalPatchScope.ts'

export type CodeGenerationActionModelClient = (
  model: string,
  messages: OllamaMessage[],
  options: { signal?: AbortSignal; num_ctx?: number; num_predict?: number; firstByteTimeoutMs?: number },
) => Promise<unknown>

export type CodeGenerationActionProducerOptions = {
  prompt: string
  model: string
  /** Intent du run: porte le verrouillage marque et le type de projet, sans
   *  lesquels l executor ne connait pas la barre de qualite exigee. */
  intent?: CodeIntent
  architecturePlan?: string | null
  contextImages?: string[]
  maxFileContextChars?: number
  signal?: AbortSignal
  numCtx?: number
  /** Plafond de tokens GENERES. Sans lui, certains presets Modelfile coupent a
   *  256-1024 tokens et le fichier arrive tronque. */
  numPredict?: number
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
    memory: loadOrBuildCodeProjectMemory(files),
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
  intent?: CodeIntent
  architecturePlan?: string | null
  contextImages?: string[]
  maxFileContextChars?: number
}): OllamaMessage[] {
  const maxContext = args.maxFileContextChars ?? 12_000
  const patchScope = args.files.length > 0
    ? formatCodeIncrementalPatchScope(buildCodeIncrementalPatchScope({
        prompt: args.prompt,
        files: args.files,
        maxTargetFiles: 8,
      }))
    : null
  const userMessage: OllamaMessage = {
    role: 'user',
    content: [
      '## DEMANDE UTILISATEUR',
      args.prompt,
      '',
      args.architecturePlan ? `## PLAN ARCHITECTE JSON\n${cap(args.architecturePlan, 8_000)}` : '',
      '',
      '## MANIFESTE COMPLET DU PROJET',
      formatGenerationQueueForPrompt(args.queue),
      '',
      '## FENETRE DE QUEUE',
      formatQueueWindow(args.queue, args.item),
      '',
      patchScope ? `## PORTEE PATCH INCREMENTAL WS5\n${patchScope}` : '',
      '',
      '## CONTEXTE FICHIERS CIBLE',
      formatRelevantFiles(args.files, args.item, args.prompt, maxContext),
      '',
      '## CONTRAT DE SORTIE',
      buildCodeGenerationActionInstructions(args.item),
    ].filter(Boolean).join('\n\n'),
  }
  if (args.contextImages?.length) userMessage.images = args.contextImages
  // Le contrat qualite (verrouillage marque, contrat de livraison, barre
  // visuelle, archetype, interactivite) est CIBLE sur le fichier en cours et
  // borne en taille: WS3 appelle le modele une fois par fichier, donc un prompt
  // systeme non borne se paierait en contexte a chaque appel.
  const qualityContract = args.intent
    ? buildExecutorQualityContract({
        intent: args.intent,
        prompt: args.prompt,
        target: { path: args.item.path, language: args.item.language, role: args.item.role },
      })
    : ''
  return [
    {
      role: 'system',
      content: [
        '# ROLE: EXECUTOR WS3 A OUTILS',
        'Tu produis uniquement des actions outil JSON pour le VFS AuroraIA.',
        'Tu ne livres jamais un blob projet complet dans ce mode.',
        'Chaque action doit etre minimale, complete et directement executable par le runner.',
        'En modification de projet existant, privilegie apply_patch sur les fichiers cibles WS5 et ne reecris pas les fichiers proteges.',
        'N utilise write_file sur un fichier existant que si le prompt demande explicitement une reecriture complete de ce fichier.',
        'Pour un fichier required, l action finale doit rendre le fichier present et complet.',
        ...(qualityContract ? ['', qualityContract] : []),
      ].join('\n'),
    },
    userMessage,
  ]
}

async function defaultChatClient(
  model: string,
  messages: OllamaMessage[],
  options: { signal?: AbortSignal; num_ctx?: number; num_predict?: number; firstByteTimeoutMs?: number },
) {
  const { resilientOllamaChat } = await import('./ollamaResilience.ts')
  return resilientOllamaChat(model, messages, 0.2, {
    signal: options.signal,
    num_ctx: options.num_ctx,
    num_predict: options.num_predict,
    firstByteTimeoutMs: options.firstByteTimeoutMs,
    neverMemorySkip: true,
  })
}

// Tolerance modeles locaux: qwen3-coder & co emettent tres souvent le CODE BRUT
// (fence ```lang ... ``` ou HTML direct) SANS le marqueur de protocole d actions
// -> le WS3 echouait fatalement ("protocol_marker_missing") a CHAQUE generation.
// On recupere alors le contenu de fichier depuis la sortie brute pour le fichier
// cible de l etape, au lieu d avorter tout le pipeline.
function extractRawFileContent(raw: string): string | null {
  if (!raw) return null
  // Retire les blocs de raisonnement <think>...</think>.
  let text = raw.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
  // Si des blocs fences existent, prend le plus long (le fichier complet).
  const fences = [...text.matchAll(/```[a-zA-Z0-9_-]*\n?([\s\S]*?)```/g)].map((m) => m[1].trim()).filter(Boolean)
  if (fences.length > 0) {
    text = fences.sort((a, b) => b.length - a.length)[0]
  }
  text = text.trim()
  // Rejette une sortie manifestement non-code (refus, phrase courte).
  if (text.length < 20) return null
  // Ne JAMAIS ecrire un payload d actions JSON comme contenu de fichier (sinon la
  // page affiche {"actions":[{"kind":"write_file"...}]} en texte). Ce cas doit
  // etre parse comme des actions, pas traite en code brut.
  if (/"kind"\s*:\s*"(write_file|read_file|apply_patch|run_command)"/.test(text)) return null
  const looksLikeCode = /[<{};=]|function|const |import |export |def |class |<!doctype|<html|<div|=>/i.test(text)
  return looksLikeCode ? text : null
}

/**
 * Une reponse illisible n est pas une fatalite, c est une reponse a REDEMANDER.
 *
 * Mesure reelle (run 981): la toute premiere etape de l executor a recu une
 * reponse dont il ne restait RIEN d exploitable (`protocol_marker_missing`, et
 * le repli code-brut n avait pas 20 caracteres a se mettre sous la dent). Une
 * seule reponse ratee a tue un run entier — la boucle de correction sait
 * reparer du code, elle ne sait pas ressusciter un projet qui n a jamais ete
 * genere. Aucune tolerance d ANALYSE ne peut extraire du contenu du vide: la
 * seule reponse correcte est de redemander, autrement.
 */
const PRODUCER_MAX_ATTEMPTS = 3

function buildProducerRetryNudge(attempt: number, item: CodeGenerationQueueItem): OllamaMessage {
  if (attempt === 2) {
    return {
      role: 'user',
      content: [
        'Ta reponse precedente etait inexploitable (aucun contenu lisible).',
        `Reponds MAINTENANT uniquement avec le tableau JSON d actions pour \`${item.path}\`.`,
        'Pas de phrase avant, pas de phrase apres, pas de raisonnement: le JSON seul.',
      ].join('\n'),
    }
  }
  // Dernier recours: on abandonne le protocole et on demande le fichier nu.
  // `extractRawFileContent` sait le recuperer, et un fichier imparfait se
  // corrige — un run mort, non.
  return {
    role: 'user',
    content: [
      'Oublie le protocole d actions.',
      `Ecris simplement le contenu COMPLET du fichier \`${item.path}\`, dans un seul bloc \`\`\`.`,
      'Rien d autre: pas d explication, pas de JSON, pas de raisonnement.',
    ].join('\n'),
  }
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
      intent: options.intent,
      architecturePlan: options.architecturePlan,
      contextImages: options.contextImages,
      maxFileContextChars: options.maxFileContextChars,
    })
    // Anti-crash: decharge tout autre gros modele code avant de charger le
    // codeur (transition agent -> codeur). Un seul gros modele resident.
    const { ensureExclusiveCodeModel } = await import('./codeModelResidency.ts')
    await ensureExclusiveCodeModel(options.model)

    let lastErrors = 'aucune reponse exploitable'
    for (let attempt = 1; attempt <= PRODUCER_MAX_ATTEMPTS; attempt += 1) {
      const attemptMessages = attempt === 1
        ? messages
        : [...messages, buildProducerRetryNudge(attempt, item)]
      const response = await chatClient(options.model, attemptMessages, {
        signal: options.signal,
        num_ctx: options.numCtx,
        num_predict: options.numPredict,
        firstByteTimeoutMs: options.firstByteTimeoutMs,
      })
      const raw = extractAssistantContent(response)
      options.onRawResponse?.({ item, raw })

      const parsed = parseCodeGenerationActions(raw)
      if (parsed.ok) return parsed.actions

      // Repli tolerant: le modele a rendu du code brut sans le protocole
      // d actions. On l ecrit dans le fichier cible de l etape.
      const rawContent = extractRawFileContent(raw)
      if (rawContent) {
        options.onRawResponse?.({ item, raw: `[repli code-brut -> write_file ${item.path}]` })
        return [{ kind: 'write_file', path: item.path, language: item.language ?? undefined, content: rawContent }]
      }

      lastErrors = parsed.errors.join(',') || lastErrors
      options.onRawResponse?.({
        item,
        raw: `[tentative ${attempt}/${PRODUCER_MAX_ATTEMPTS} inexploitable: ${lastErrors} — ${raw.trim().length} caractere(s) recus]`,
      })
    }

    throw new Error(`action_protocol_invalid:${lastErrors}`)
  }
}
