import {
  parseArchitecturePlanJson,
  type CodeArchitectureFile,
} from './codeArchitecturePlan.ts'

export type CodeGenerationQueueItem = {
  path: string
  order: number
  required: boolean
  role: string
  language: string | null
  imports: string[]
  exports: string[]
  notes: string[]
}

export type CodeGenerationQueue = {
  source: 'architecture_plan'
  items: CodeGenerationQueueItem[]
  requiredCount: number
  optionalCount: number
  omittedOrderPaths: string[]
}

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '').toLowerCase()
}

function toQueueItem(file: CodeArchitectureFile, order: number): CodeGenerationQueueItem {
  return {
    path: file.path,
    order,
    required: file.required !== false,
    role: file.role,
    language: file.language || null,
    imports: file.imports,
    exports: file.exports,
    notes: file.notes,
  }
}

export function buildGenerationQueueFromArchitecturePlan(
  architecturePlan: string | null | undefined,
): CodeGenerationQueue | null {
  const parsed = parseArchitecturePlanJson(architecturePlan)
  if (!parsed.ok) return null

  const byPath = new Map(parsed.plan.files.map((file) => [normalizePath(file.path), file]))
  const emitted = new Set<string>()
  const items: CodeGenerationQueueItem[] = []
  const omittedOrderPaths: string[] = []

  for (const orderPath of parsed.plan.generationOrder) {
    const normalized = normalizePath(orderPath)
    const file = byPath.get(normalized)
    if (!file || emitted.has(normalized)) {
      if (!file) omittedOrderPaths.push(orderPath)
      continue
    }
    emitted.add(normalized)
    items.push(toQueueItem(file, items.length + 1))
  }

  for (const file of parsed.plan.files) {
    const normalized = normalizePath(file.path)
    if (emitted.has(normalized)) continue
    emitted.add(normalized)
    items.push(toQueueItem(file, items.length + 1))
  }

  const requiredCount = items.filter((item) => item.required).length
  return {
    source: 'architecture_plan',
    items,
    requiredCount,
    optionalCount: items.length - requiredCount,
    omittedOrderPaths,
  }
}

function formatList(label: string, values: string[]) {
  if (values.length === 0) return ''
  return `${label}: ${values.slice(0, 5).join(', ')}`
}

export function formatGenerationQueueForPrompt(queue: CodeGenerationQueue): string {
  const lines = [
    '## FILE-BY-FILE EXECUTION MANIFEST — WS3',
    '',
    'Traite cette liste comme la file d outils write_file/read_file/apply_patch/run_command.',
    'Chaque entree required=true doit produire un fichier complet via AURORA_CODE_VFS/1.',
    `Total: ${queue.items.length} fichier(s), required=${queue.requiredCount}, optional=${queue.optionalCount}.`,
    '',
  ]

  for (const item of queue.items.slice(0, 80)) {
    const parts = [
      `${item.order}. ${item.path}`,
      `required=${item.required}`,
      item.language ? `lang=${item.language}` : '',
      item.role ? `role=${item.role}` : '',
    ].filter(Boolean)
    lines.push(parts.join(' | '))
    const details = [
      formatList('imports', item.imports),
      formatList('exports', item.exports),
      formatList('notes', item.notes),
    ].filter(Boolean)
    if (details.length > 0) lines.push(`   ${details.join(' ; ')}`)
  }

  if (queue.items.length > 80) {
    lines.push(`... ${queue.items.length - 80} fichier(s) supplementaire(s) dans le plan complet.`)
  }
  if (queue.omittedOrderPaths.length > 0) {
    lines.push(`Chemins generationOrder ignores car absents de files[]: ${queue.omittedOrderPaths.slice(0, 10).join(', ')}`)
  }

  return lines.join('\n')
}
