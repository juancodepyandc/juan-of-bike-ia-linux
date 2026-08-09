import type {
  CodeGenerationToolAction,
} from './codeGenerationTools.ts'
import type { CodeGenerationQueueItem } from './codeGenerationQueue.ts'
import {
  repairJsonControlCharacters,
  salvageTruncatedWriteFile,
} from './codeGenerationActionSalvage.ts'

export const CODE_GENERATION_ACTION_PROTOCOL_VERSION = 'AURORA_CODE_ACTIONS/1' as const

export type CodeGenerationActionParseResult =
  | { ok: true; actions: CodeGenerationToolAction[]; errors: [] }
  | { ok: false; actions: CodeGenerationToolAction[]; errors: string[] }

function stripThinkingAndFences(raw: string) {
  let text = raw.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/i)
  if (fence) text = fence[1].trim()
  return text
}

function findFirstJsonValue(raw: string) {
  const start = raw.search(/[\[{]/)
  if (start < 0) return null

  let depth = 0
  let inString = false
  let escaped = false
  const opening = raw[start]
  const closing = opening === '[' ? ']' : '}'
  const openChar = opening
  const closeChar = closing

  for (let index = start; index < raw.length; index++) {
    const char = raw[index]
    if (inString) {
      if (escaped) {
        escaped = false
      } else if (char === '\\') {
        escaped = true
      } else if (char === '"') {
        inString = false
      }
      continue
    }

    if (char === '"') {
      inString = true
    } else if (char === openChar) {
      depth += 1
    } else if (char === closeChar) {
      depth -= 1
      if (depth === 0) return raw.slice(start, index + 1)
    }
  }

  return null
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function cleanString(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

function normalizeAction(value: unknown, index: number, errors: string[]): CodeGenerationToolAction | null {
  const record = asRecord(value)
  if (!record) {
    errors.push(`action_${index}_not_object`)
    return null
  }

  const kind = cleanString(record.kind)
  if (kind === 'write_file') {
    const path = cleanString(record.path)
    const content = typeof record.content === 'string' ? record.content : null
    if (!path) errors.push(`action_${index}_path_missing`)
    if (content === null) errors.push(`action_${index}_content_missing`)
    if (!path || content === null) return null
    const language = cleanString(record.language)
    return language ? { kind, path, content, language } : { kind, path, content }
  }

  if (kind === 'read_file') {
    const path = cleanString(record.path)
    if (!path) {
      errors.push(`action_${index}_path_missing`)
      return null
    }
    return { kind, path }
  }

  if (kind === 'apply_patch') {
    const path = cleanString(record.path)
    const search = typeof record.search === 'string' ? record.search : null
    const replace = typeof record.replace === 'string' ? record.replace : null
    if (!path) errors.push(`action_${index}_path_missing`)
    if (search === null) errors.push(`action_${index}_search_missing`)
    if (replace === null) errors.push(`action_${index}_replace_missing`)
    if (!path || search === null || replace === null) return null
    return { kind, path, search, replace, all: record.all === true }
  }

  if (kind === 'run_command') {
    const command = cleanString(record.command)
    if (!command) {
      errors.push(`action_${index}_command_missing`)
      return null
    }
    const reason = cleanString(record.reason)
    return reason ? { kind, command, reason } : { kind, command }
  }

  errors.push(`action_${index}_kind_invalid`)
  return null
}

function extractActionArray(parsed: unknown, errors: string[]) {
  if (Array.isArray(parsed)) return parsed
  const record = asRecord(parsed)
  if (record && Array.isArray(record.actions)) return record.actions
  errors.push('actions_array_missing')
  return []
}

export function parseCodeGenerationActions(raw: string): CodeGenerationActionParseResult {
  const text = stripThinkingAndFences(raw)
  // Tolerant au marqueur manquant: les modeles locaux (qwen3-coder...) emettent
  // tres souvent le tableau d actions JSON SANS le prefixe AURORA_CODE_ACTIONS/1.
  // Auparavant on echouait sec ('protocol_marker_missing') puis le contenu JSON
  // brut etait ecrit tel quel dans le fichier (page affichant {"actions":[...]}).
  // On cherche donc la 1ere valeur JSON dans tout le texte quand le marqueur
  // manque, et on ne bascule sur le repli code-brut que si aucune action valide.
  const hasMarker = text.includes(CODE_GENERATION_ACTION_PROTOCOL_VERSION)
  const searchZone = hasMarker
    ? text.slice(text.indexOf(CODE_GENERATION_ACTION_PROTOCOL_VERSION) + CODE_GENERATION_ACTION_PROTOCOL_VERSION.length)
    : text
  const json = findFirstJsonValue(searchZone)
  if (!json) {
    // Charge jamais refermee = limite de tokens atteinte au milieu du contenu.
    // Un fichier partiel vaut mieux qu un run perdu: la boucle de correction
    // sait completer un fichier incomplet, pas ressusciter un projet vide.
    const salvaged = salvageTruncatedWriteFile(searchZone)
    if (salvaged) {
      return {
        ok: true,
        actions: [{
          kind: 'write_file',
          path: salvaged.path,
          ...(salvaged.language ? { language: salvaged.language } : {}),
          content: salvaged.content,
        }],
        errors: [],
      }
    }
    return { ok: false, actions: [], errors: [hasMarker ? 'json_payload_missing' : 'protocol_marker_missing'] }
  }

  const errors: string[] = []
  let parsed: unknown
  try {
    parsed = JSON.parse(json)
  } catch {
    // Cause dominante: le modele a insere de VRAIS retours a la ligne dans la
    // chaine `content` au lieu de `\n`. Reparation exacte et sans risque: on ne
    // touche qu une charge qui a deja echoue au parse.
    try {
      parsed = JSON.parse(repairJsonControlCharacters(json))
    } catch {
      const salvaged = salvageTruncatedWriteFile(json)
      if (salvaged) {
        return {
          ok: true,
          actions: [{
            kind: 'write_file',
            path: salvaged.path,
            ...(salvaged.language ? { language: salvaged.language } : {}),
            content: salvaged.content,
          }],
          errors: [],
        }
      }
      return { ok: false, actions: [], errors: ['json_payload_invalid'] }
    }
  }

  const actionValues = extractActionArray(parsed, errors)
  const actions = actionValues
    .map((value, index) => normalizeAction(value, index, errors))
    .filter((action): action is CodeGenerationToolAction => Boolean(action))

  if (actions.length === 0) errors.push('actions_empty')
  return errors.length === 0
    ? { ok: true, actions, errors: [] }
    : { ok: false, actions, errors }
}

export function buildCodeGenerationActionInstructions(item: CodeGenerationQueueItem) {
  return [
    'FORMAT OUTIL STRICT:',
    `Commence par ${CODE_GENERATION_ACTION_PROTOCOL_VERSION}.`,
    'Puis emets un JSON strict, sans commentaire, sous forme de tableau ou {"actions":[...]}.',
    'Actions autorisees:',
    '- {"kind":"read_file","path":"src/App.tsx"}',
    '- {"kind":"write_file","path":"src/App.tsx","language":"tsx","content":"code complet"}',
    '- {"kind":"apply_patch","path":"src/App.tsx","search":"texte exact","replace":"texte exact","all":false}',
    '- {"kind":"run_command","command":"npm run build","reason":"validation"}',
    '',
    `Fichier cible de cette etape: ${item.path}`,
    `Role: ${item.role || 'non specifie'}`,
    `Langage attendu: ${item.language || 'inferer depuis le chemin'}`,
    `Required: ${item.required}`,
    item.imports.length ? `Imports prevus: ${item.imports.join(', ')}` : '',
    item.exports.length ? `Exports prevus: ${item.exports.join(', ')}` : '',
    item.notes.length ? `Notes: ${item.notes.join(' ; ')}` : '',
    '',
    'Regle principale: pour un fichier required, fournis au minimum une action write_file ou un patch qui le rend present et complet.',
    'Ne produis aucun texte hors protocole.',
  ].filter(Boolean).join('\n')
}
