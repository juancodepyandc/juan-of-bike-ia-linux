import {
  parseArchitecturePlanJson,
  type CodeArchitectureFile,
} from './codeArchitecturePlan.ts'
import type { CodeIntent } from './codeIntent.ts'

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

// Fichiers par defaut selon le type de projet. Filet de securite ABSOLU: si le
// plan d architecture ne produit aucune file exploitable (LLM qui rend du
// markdown au lieu du JSON, JSON malforme...), la generation NE DOIT JAMAIS
// echouer a 0 fichier. On synthetise une file minimale et executable pour que
// l executor agentique produise au moins un projet lancable.
export function defaultFilesForIntent(intent: CodeIntent): Array<{ path: string; role: string; language: string | null }> {
  const pt = String(intent.projectType || '')
  const langs = Array.isArray(intent.languages) ? intent.languages.map((l) => String(l).toLowerCase()) : []
  const webTriplet = [
    { path: 'index.html', role: 'page principale', language: 'html' },
    { path: 'style.css', role: 'feuille de style', language: 'css' },
    { path: 'script.js', role: 'interactivite', language: 'javascript' },
  ]
  if (pt.startsWith('spa_') || pt.startsWith('ssr_') || pt.startsWith('fullstack_')) {
    return [
      { path: 'index.html', role: 'html entry', language: 'html' },
      { path: 'src/main.tsx', role: 'react entry', language: 'typescript' },
      { path: 'src/App.tsx', role: 'root component', language: 'typescript' },
      { path: 'src/styles.css', role: 'styles', language: 'css' },
    ]
  }
  if (langs.includes('python') || pt.startsWith('api_') || pt.startsWith('cli')) {
    return [{ path: 'main.py', role: 'point d entree', language: 'python' }]
  }
  // Repli generique universel: une page web statique (cas le plus courant +
  // toujours affichable dans le viewer). Couvre static_web, game_web, unknown...
  return webTriplet
}

export function buildFallbackGenerationQueue(intent: CodeIntent): CodeGenerationQueue {
  const items: CodeGenerationQueueItem[] = defaultFilesForIntent(intent).map((f, i) => ({
    path: f.path,
    order: i + 1,
    required: true,
    role: f.role,
    language: f.language,
    imports: [],
    exports: [],
    notes: [],
  }))
  return {
    source: 'architecture_plan',
    items,
    requiredCount: items.length,
    optionalCount: 0,
    omittedOrderPaths: [],
  }
}

/**
 * Construit la file, avec repli garanti: si le plan ne parse pas OU ne produit
 * aucun fichier, on retombe sur une file par defaut derivee de l intent. Ne
 * retourne JAMAIS null quand un intent est fourni -> plus d echec fatal
 * "plan_without_queue".
 */
export function buildGenerationQueueWithFallback(
  architecturePlan: string | null | undefined,
  intent: CodeIntent,
): { queue: CodeGenerationQueue; usedFallback: boolean } {
  const fromPlan = buildGenerationQueueFromArchitecturePlan(architecturePlan)
  if (fromPlan && fromPlan.items.length > 0) return { queue: fromPlan, usedFallback: false }
  return { queue: buildFallbackGenerationQueue(intent), usedFallback: true }
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
