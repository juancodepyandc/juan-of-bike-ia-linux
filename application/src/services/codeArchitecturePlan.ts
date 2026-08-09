import { repairJsonControlCharacters } from './codeGenerationActionSalvage.ts'

export const CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION = 'aurora.code.architecture-plan.v1'

export type CodeArchitectureDependency = {
  name: string
  version?: string
  type: 'runtime' | 'dev' | 'system'
  reason?: string
}

export type CodeArchitectureScript = {
  name: string
  command: string
  purpose?: string
}

export type CodeArchitectureFile = {
  path: string
  role: string
  language?: string
  required: boolean
  imports: string[]
  exports: string[]
  notes: string[]
}

export type CodeArchitectureRisk = {
  risk: string
  mitigation: string
}

export type CodeArchitecturePlan = {
  schemaVersion: typeof CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION
  projectType: string
  summary: string
  stack: {
    runtime: string
    packageManager: string
    languages: string[]
    frameworks: string[]
    dependencies: CodeArchitectureDependency[]
    scripts: CodeArchitectureScript[]
  }
  files: CodeArchitectureFile[]
  dataFlow: string[]
  execution: {
    install: string[]
    dev: string[]
    build: string[]
    test: string[]
    preview: string
  }
  generationOrder: string[]
  validation: string[]
  risks: CodeArchitectureRisk[]
  design: {
    palette: string[]
    typography: string[]
    ux: string[]
    responsive: string[]
  }
}

export const CODE_ARCHITECTURE_PLAN_SCHEMA = {
  type: 'object',
  required: [
    'schemaVersion',
    'projectType',
    'summary',
    'stack',
    'files',
    'dataFlow',
    'execution',
    'generationOrder',
    'validation',
    'risks',
    'design',
  ],
  properties: {
    schemaVersion: { const: CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION },
    projectType: { type: 'string', minLength: 2 },
    summary: { type: 'string', minLength: 20 },
    stack: {
      type: 'object',
      required: ['runtime', 'packageManager', 'languages', 'frameworks', 'dependencies', 'scripts'],
    },
    files: { type: 'array', minItems: 2 },
    dataFlow: { type: 'array', minItems: 1 },
    execution: { type: 'object', required: ['install', 'dev', 'build', 'test', 'preview'] },
    generationOrder: { type: 'array', minItems: 1 },
    validation: { type: 'array', minItems: 2 },
    risks: { type: 'array', minItems: 1 },
    design: { type: 'object', required: ['palette', 'typography', 'ux', 'responsive'] },
  },
} as const

export type CodeArchitecturePlanParseResult =
  | { ok: true; plan: CodeArchitecturePlan; serialized: string; errors: [] }
  | { ok: false; plan: null; serialized: null; errors: string[] }

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function cleanString(value: unknown, fallback = '') {
  return typeof value === 'string' ? value.trim() : fallback
}

function stringArray(value: unknown) {
  if (!Array.isArray(value)) return []
  return Array.from(new Set(value.map((item) => cleanString(item)).filter(Boolean)))
}

function normalizeDependency(value: unknown): CodeArchitectureDependency | null {
  const record = asRecord(value)
  if (!record) return null
  const name = cleanString(record.name)
  if (!name) return null
  const rawType = cleanString(record.type).toLowerCase()
  const type: CodeArchitectureDependency['type'] =
    rawType === 'dev' || rawType === 'system' ? rawType : 'runtime'
  const dependency: CodeArchitectureDependency = { name, type }
  const version = cleanString(record.version)
  const reason = cleanString(record.reason)
  if (version) dependency.version = version
  if (reason) dependency.reason = reason
  return dependency
}

function normalizeScript(value: unknown): CodeArchitectureScript | null {
  const record = asRecord(value)
  if (!record) return null
  const name = cleanString(record.name)
  const command = cleanString(record.command)
  if (!name || !command) return null
  const purpose = cleanString(record.purpose)
  return purpose ? { name, command, purpose } : { name, command }
}

function isSafeRelativePlanPath(path: string) {
  return Boolean(path)
    && !path.startsWith('/')
    && !/^[a-zA-Z]:[\\/]/.test(path)
    && !path.split(/[\\/]+/).includes('..')
}

function normalizeFile(value: unknown): CodeArchitectureFile | null {
  const record = asRecord(value)
  if (!record) return null
  const path = cleanString(record.path)
  const role = cleanString(record.role)
  if (!isSafeRelativePlanPath(path) || !role) return null
  const language = cleanString(record.language)
  return {
    path,
    role,
    language: language || undefined,
    required: typeof record.required === 'boolean' ? record.required : true,
    imports: stringArray(record.imports),
    exports: stringArray(record.exports),
    notes: stringArray(record.notes),
  }
}

function normalizeRisk(value: unknown): CodeArchitectureRisk | null {
  const record = asRecord(value)
  if (!record) return null
  const risk = cleanString(record.risk)
  const mitigation = cleanString(record.mitigation)
  return risk && mitigation ? { risk, mitigation } : null
}

function findFirstJsonObject(raw: string) {
  const withoutThink = raw.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
  const fence = withoutThink.match(/```(?:json)?\s*([\s\S]*?)```/i)
  const candidates = fence ? [fence[1], withoutThink] : [withoutThink]

  for (const candidate of candidates) {
    for (let start = candidate.indexOf('{'); start >= 0; start = candidate.indexOf('{', start + 1)) {
      let depth = 0
      let inString = false
      let escaped = false
      for (let index = start; index < candidate.length; index++) {
        const char = candidate[index]
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
        } else if (char === '{') {
          depth += 1
        } else if (char === '}') {
          depth -= 1
          if (depth === 0) return candidate.slice(start, index + 1)
        }
      }
    }
  }
  return null
}

export function normalizeArchitecturePlan(candidate: unknown): CodeArchitecturePlanParseResult {
  const record = asRecord(candidate)
  const errors: string[] = []
  if (!record) return { ok: false, plan: null, serialized: null, errors: ['plan_not_object'] }

  const schemaVersion = cleanString(record.schemaVersion)
  if (schemaVersion !== CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION) errors.push('schemaVersion_invalid')
  const projectType = cleanString(record.projectType)
  if (!projectType) errors.push('projectType_missing')
  const summary = cleanString(record.summary)
  if (summary.length < 20) errors.push('summary_too_short')

  const stackRecord = asRecord(record.stack)
  if (!stackRecord) errors.push('stack_missing')
  const dependencies = Array.isArray(stackRecord?.dependencies)
    ? stackRecord.dependencies.map(normalizeDependency).filter((item): item is CodeArchitectureDependency => Boolean(item))
    : []
  const scripts = Array.isArray(stackRecord?.scripts)
    ? stackRecord.scripts.map(normalizeScript).filter((item): item is CodeArchitectureScript => Boolean(item))
    : []

  const files = Array.isArray(record.files)
    ? record.files.map(normalizeFile).filter((item): item is CodeArchitectureFile => Boolean(item))
    : []
  if (files.length < 2) errors.push('files_min_2')

  const executionRecord = asRecord(record.execution)
  if (!executionRecord) errors.push('execution_missing')
  const execution = {
    install: stringArray(executionRecord?.install),
    dev: stringArray(executionRecord?.dev),
    build: stringArray(executionRecord?.build),
    test: stringArray(executionRecord?.test),
    preview: cleanString(executionRecord?.preview),
  }
  if ([...execution.install, ...execution.dev, ...execution.build, ...execution.test, execution.preview].filter(Boolean).length === 0) {
    errors.push('execution_empty')
  }

  const generationOrder = stringArray(record.generationOrder)
  if (generationOrder.length === 0) errors.push('generationOrder_missing')
  const validation = stringArray(record.validation)
  if (validation.length < 2) errors.push('validation_min_2')
  const dataFlow = stringArray(record.dataFlow)
  if (dataFlow.length === 0) errors.push('dataFlow_missing')
  const risks = Array.isArray(record.risks)
    ? record.risks.map(normalizeRisk).filter((item): item is CodeArchitectureRisk => Boolean(item))
    : []
  if (risks.length === 0) errors.push('risks_missing')

  const designRecord = asRecord(record.design)
  const design = {
    palette: stringArray(designRecord?.palette),
    typography: stringArray(designRecord?.typography),
    ux: stringArray(designRecord?.ux),
    responsive: stringArray(designRecord?.responsive),
  }

  if (errors.length > 0) return { ok: false, plan: null, serialized: null, errors }

  const plan: CodeArchitecturePlan = {
    schemaVersion: CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
    projectType,
    summary,
    stack: {
      runtime: cleanString(stackRecord?.runtime, 'non precise'),
      packageManager: cleanString(stackRecord?.packageManager, 'non precise'),
      languages: stringArray(stackRecord?.languages),
      frameworks: stringArray(stackRecord?.frameworks),
      dependencies,
      scripts,
    },
    files,
    dataFlow,
    execution,
    generationOrder,
    validation,
    risks,
    design,
  }

  return { ok: true, plan, serialized: serializeArchitecturePlan(plan), errors: [] }
}

export function parseArchitecturePlanJson(raw: string | null | undefined): CodeArchitecturePlanParseResult {
  if (!raw?.trim()) return { ok: false, plan: null, serialized: null, errors: ['empty_plan'] }
  const jsonObject = findFirstJsonObject(raw)
  if (!jsonObject) return { ok: false, plan: null, serialized: null, errors: ['json_object_missing'] }
  try {
    return normalizeArchitecturePlan(JSON.parse(jsonObject))
  } catch {
    // Meme classe de corruption que le protocole d actions: le modele insere de
    // VRAIS caracteres de controle dans une chaine (notes, summary multi-lignes)
    // au lieu de les echapper. La reparation ne s applique que sur un chemin
    // deja en echec, donc elle ne peut pas degrader un plan valide.
    try {
      return normalizeArchitecturePlan(JSON.parse(repairJsonControlCharacters(jsonObject)))
    } catch {
      return { ok: false, plan: null, serialized: null, errors: ['json_parse_failed'] }
    }
  }
}

export function serializeArchitecturePlan(plan: CodeArchitecturePlan) {
  return JSON.stringify(plan, null, 2)
}

export function formatArchitecturePlanDependenciesForMarkdown(raw: string | null | undefined) {
  const parsed = parseArchitecturePlanJson(raw)
  if (parsed.ok) {
    const dependencyLines = parsed.plan.stack.dependencies.map((dep) => {
      const version = dep.version ? `@${dep.version}` : ''
      const reason = dep.reason ? ` — ${dep.reason}` : ''
      return `- ${dep.name}${version} (${dep.type})${reason}`
    })
    const scriptLines = parsed.plan.stack.scripts.map((script) => `- \`${script.command}\` — ${script.purpose || script.name}`)
    return [...dependencyLines, ...scriptLines].join('\n')
  }

  const legacyMatch = raw?.match(/###\s*DEPENDANCES[^\n]*\n([\s\S]*?)(?=###|$)/i)
  return legacyMatch?.[1]?.trim() || ''
}

export function buildArchitecturePlanJsonInstructions() {
  return [
    '## FORMAT DE SORTIE OBLIGATOIRE — JSON SCHEMA',
    '',
    'Reponds UNIQUEMENT avec un objet JSON valide. Aucun markdown, aucun texte avant/apres, aucun bloc ```.',
    'Le plan est un contrat machine: s il ne valide pas ce schema, il sera rejete et ignore par l executeur.',
    '',
    'Schema JSON attendu (champs requis):',
    JSON.stringify(CODE_ARCHITECTURE_PLAN_SCHEMA, null, 2),
    '',
    'Template minimal a respecter exactement:',
    JSON.stringify({
      schemaVersion: CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
      projectType: '<type detecte>',
      summary: '<20+ caracteres: intention et strategie de livraison>',
      stack: {
        runtime: '<node/python/rust/web/etc>',
        packageManager: '<npm/pnpm/pip/cargo/aucun>',
        languages: ['<langage>'],
        frameworks: ['<framework ou aucun>'],
        dependencies: [{ name: '<package>', version: '<version exacte si utile>', type: 'runtime', reason: '<pourquoi>' }],
        scripts: [{ name: '<script>', command: '<commande exacte>', purpose: '<validation ou lancement>' }],
      },
      files: [{
        path: '<chemin relatif sur POSIX>',
        role: '<responsabilite concrete>',
        language: '<langage>',
        required: true,
        imports: ['<imports locaux attendus>'],
        exports: ['<exports attendus>'],
        notes: ['<points d attention>'],
      }],
      dataFlow: ['<flux utilisateur/donnees/etat>'],
      execution: {
        install: ['<commande install ou aucune>'],
        dev: ['<commande dev/lancement>'],
        build: ['<commande build ou verification>'],
        test: ['<commande test ou validation manuelle stricte>'],
        preview: '<comment voir le resultat>',
      },
      generationOrder: ['<chemin fichier dans ordre de generation>'],
      validation: ['<critere vert mesurable>', '<autre critere vert mesurable>'],
      risks: [{ risk: '<risque>', mitigation: '<mitigation concrete>' }],
      design: {
        palette: ['<tokens/couleurs ou contrainte>'],
        typography: ['<polices/echelle>'],
        ux: ['<interactions et ergonomie>'],
        responsive: ['<breakpoints et comportements>'],
      },
    }, null, 2),
  ].join('\n')
}

