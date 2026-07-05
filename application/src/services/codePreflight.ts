import {
  CODE_SINGLE_MODEL,
} from '../config/models'
import { fsExists, getWorkspacePath, runWorkspaceCommand } from '../hooks/useTauri'
import { resilientOllamaGenerate } from './ollamaResilience'
import type { CodeIntent } from './codeIntent'

type PreflightCodeFile = {
  name: string
  language: string
  content: string
}

type ToolProbeSpec = {
  id: string
  executable: string
  args: string[]
  label: string
}

export type CodePreflightToolFact = {
  id: string
  label: string
  available: boolean
  version: string | null
  command: string
}

export type CodePreflightReport = {
  summary: string
  chosenStack: string
  packageManager: string | null
  executionStrategy: string
  localConstraints: string[]
  machineFindings: string[]
  workspaceFindings: string[]
  reuseGuidance: string[]
  mustInspectFirst: string[]
  validationPlan: string[]
  toolFacts: CodePreflightToolFact[]
}

const TOOL_SPECS: ToolProbeSpec[] = [
  { id: 'git', label: 'Git', executable: 'git', args: ['--version'] },
  { id: 'node', label: 'Node.js', executable: 'node', args: ['--version'] },
  { id: 'npm', label: 'npm', executable: 'npm', args: ['--version'] },
  { id: 'pnpm', label: 'pnpm', executable: 'pnpm', args: ['--version'] },
  { id: 'yarn', label: 'Yarn', executable: 'yarn', args: ['--version'] },
  { id: 'bun', label: 'Bun', executable: 'bun', args: ['--version'] },
  { id: 'python', label: 'Python', executable: 'python', args: ['--version'] },
  { id: 'pip', label: 'pip', executable: 'pip', args: ['--version'] },
  { id: 'cargo', label: 'Cargo', executable: 'cargo', args: ['--version'] },
  { id: 'rustc', label: 'rustc', executable: 'rustc', args: ['--version'] },
  { id: 'go', label: 'Go', executable: 'go', args: ['version'] },
  { id: 'dotnet', label: '.NET', executable: 'dotnet', args: ['--version'] },
  { id: 'java', label: 'Java', executable: 'java', args: ['-version'] },
  { id: 'javac', label: 'javac', executable: 'javac', args: ['-version'] },
]

const WORKSPACE_MARKERS = [
  'package.json',
  'pnpm-lock.yaml',
  'yarn.lock',
  'bun.lock',
  'bun.lockb',
  'tsconfig.json',
  'vite.config.ts',
  'vite.config.js',
  'webpack.config.js',
  'webpack.config.ts',
  'pyproject.toml',
  'requirements.txt',
  'Cargo.toml',
  'src-tauri/Cargo.toml',
  'go.mod',
  'pom.xml',
  'build.gradle',
  'build.gradle.kts',
]

const PREFLIGHT_TOOL_TIMEOUT_MS = 4_000
const PREFLIGHT_SYNTHESIS_TIMEOUT_MS = 25_000
const PREFLIGHT_HEARTBEAT_MS = 4_000

function normalizeWhitespace(text: string) {
  return text.replace(/\s+/g, ' ').trim()
}

function shorten(text: string, limit = 220) {
  const normalized = normalizeWhitespace(text)
  return normalized.length <= limit ? normalized : `${normalized.slice(0, limit)}...`
}

function uniqueStrings(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))]
}

function extractVersion(output: string) {
  const normalized = output.replace(/\r/g, '').trim()
  const line = normalized.split('\n').find((entry) => entry.trim()) || normalized
  const quotedVersion = line.match(/"([^"]+)"/)?.[1]
  if (quotedVersion) return quotedVersion

  const semver = line.match(/\bv?\d+\.\d+(?:\.\d+)?(?:[-+][\w.-]+)?\b/i)?.[0]
  if (semver) return semver

  return line ? shorten(line, 80) : null
}

function chooseRelevantToolIds(intent: CodeIntent) {
  const selected = new Set<string>(['git'])
  const projectType = intent.projectType

  if (
    projectType.startsWith('spa_')
    || projectType.startsWith('ssr_')
    || projectType.startsWith('fullstack_')
    || projectType.startsWith('desktop_')
    || projectType === 'api_express'
    || projectType === 'cli_node'
    || projectType === 'game_web'
    || projectType === 'library_npm'
  ) {
    selected.add('node')
    selected.add('npm')
    selected.add('pnpm')
    selected.add('yarn')
    selected.add('bun')
  }

  if (
    projectType === 'desktop_tauri'
    || projectType === 'api_actix'
    || projectType === 'cli_rust'
    || projectType === 'system_rust'
    || projectType === 'library_crate'
  ) {
    selected.add('cargo')
    selected.add('rustc')
  }

  if (
    projectType === 'api_fastapi'
    || projectType === 'api_django'
    || projectType === 'api_flask'
    || projectType === 'fullstack_django'
    || projectType === 'cli_python'
    || projectType === 'data_python'
  ) {
    selected.add('python')
    selected.add('pip')
  }

  if (projectType === 'api_gin' || projectType === 'cli_go') {
    selected.add('go')
  }

  if (projectType === 'api_dotnet' || intent.languages.includes('csharp')) {
    selected.add('dotnet')
  }

  if (projectType === 'api_spring' || intent.languages.includes('java') || intent.languages.includes('kotlin')) {
    selected.add('java')
    selected.add('javac')
  }

  return TOOL_SPECS.filter((tool) => selected.has(tool.id))
}

async function probeTool(spec: ToolProbeSpec, cwd: string): Promise<CodePreflightToolFact> {
  try {
    const result = await runWorkspaceCommand(spec.executable, spec.args, cwd, PREFLIGHT_TOOL_TIMEOUT_MS)
    return {
      id: spec.id,
      label: spec.label,
      available: result.ok,
      version: result.ok ? extractVersion(result.output) : null,
      command: `${spec.executable} ${spec.args.join(' ')}`.trim(),
    }
  } catch {
    return {
      id: spec.id,
      label: spec.label,
      available: false,
      version: null,
      command: `${spec.executable} ${spec.args.join(' ')}`.trim(),
    }
  }
}

async function inspectWorkspaceMarkers(rootPath: string) {
  const checks = await Promise.all(
    WORKSPACE_MARKERS.map(async (marker) => ({
      marker,
      present: await fsExists(`${rootPath}/${marker}`).catch(() => false),
    })),
  )

  return checks.filter((entry) => entry.present).map((entry) => entry.marker)
}

function inspectExistingFiles(files: PreflightCodeFile[]) {
  const normalized = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const findings: string[] = []
  const mustInspectFirst: string[] = []

  if (files.length > 0) {
    findings.push(`${files.length} fichier(s) existent deja dans le projet courant.`)
    mustInspectFirst.push(...files.slice(0, 8).map((file) => file.name))
  }

  if (normalized.includes('package.json')) findings.push('Le projet courant contient deja un package.json.')
  if (normalized.includes('tsconfig.json')) findings.push('Le projet courant contient deja un tsconfig.json.')
  if (normalized.includes('src-tauri/cargo.toml')) findings.push('Le projet courant contient deja un shell Tauri Rust.')
  if (normalized.includes('requirements.txt') || normalized.includes('pyproject.toml')) findings.push('Le projet courant contient deja un environnement Python.')
  if (normalized.includes('cargo.toml')) findings.push('Le projet courant contient deja un manifeste Cargo.')
  if (normalized.includes('go.mod')) findings.push('Le projet courant contient deja un module Go.')

  return {
    findings,
    mustInspectFirst: uniqueStrings(mustInspectFirst),
  }
}

function selectPreferredPackageManager(toolFacts: CodePreflightToolFact[], workspaceMarkers: string[]) {
  const available = new Set(toolFacts.filter((tool) => tool.available).map((tool) => tool.id))
  if (workspaceMarkers.includes('pnpm-lock.yaml') && available.has('pnpm')) return 'pnpm'
  if (workspaceMarkers.includes('yarn.lock') && available.has('yarn')) return 'yarn'
  if ((workspaceMarkers.includes('bun.lock') || workspaceMarkers.includes('bun.lockb')) && available.has('bun')) return 'bun'
  if (available.has('npm')) return 'npm'
  if (available.has('pnpm')) return 'pnpm'
  if (available.has('yarn')) return 'yarn'
  if (available.has('bun')) return 'bun'
  return null
}

function buildFallbackReport(
  intent: CodeIntent,
  toolFacts: CodePreflightToolFact[],
  workspaceMarkers: string[],
  existingFileFacts: ReturnType<typeof inspectExistingFiles>,
): CodePreflightReport {
  const available = new Set(toolFacts.filter((tool) => tool.available).map((tool) => tool.id))
  const packageManager = selectPreferredPackageManager(toolFacts, workspaceMarkers)
  const chosenStack = [
    intent.projectType.replace(/_/g, ' '),
    intent.frameworks.length > 0 ? `via ${intent.frameworks.join(', ')}` : '',
  ].filter(Boolean).join(' ')

  const localConstraints: string[] = []
  if (intent.projectType === 'desktop_tauri' && !available.has('cargo')) {
    localConstraints.push('Cargo manque localement: il faudra l installer ou preparer un fallback de build avant validation.')
  }
  if (
    (
      intent.projectType.startsWith('spa_')
      || intent.projectType.startsWith('ssr_')
      || intent.projectType.startsWith('desktop_')
      || intent.projectType.startsWith('fullstack_')
      || intent.projectType === 'api_express'
    )
    && !available.has('node')
  ) {
    localConstraints.push('Node.js manque localement: la stack Node demande une installation ou une preparation automatique.')
  }
  if (
    (
      intent.projectType === 'api_fastapi'
      || intent.projectType === 'api_django'
      || intent.projectType === 'api_flask'
      || intent.projectType === 'fullstack_django'
    )
    && !available.has('python')
  ) {
    localConstraints.push('Python manque localement: la stack Python demandera une preparation automatique.')
  }

  const machineFindings = toolFacts.map((tool) =>
    tool.available
      ? `${tool.label} disponible (${tool.version || 'version detectee'}).`
      : `${tool.label} absent du PATH local.`,
  )
  const workspaceFindings = [
    workspaceMarkers.length > 0
      ? `Le workspace local contient deja: ${workspaceMarkers.slice(0, 8).join(', ')}.`
      : 'Aucun marqueur de stack supplementaire n a ete trouve a la racine du workspace local.',
    ...existingFileFacts.findings,
  ]
  const reuseGuidance = [
    existingFileFacts.mustInspectFirst.length > 0
      ? `Relire d abord: ${existingFileFacts.mustInspectFirst.slice(0, 6).join(', ')}.`
      : 'Aucun fichier projet courant n etait disponible pour une reprise directe.',
    'Fixer la stack et les versions avant de produire le moindre fichier source.',
  ]
  const validationPlan = [
    'Verifier les manifests, scripts et fichiers de config locaux avant toute generation finale.',
    'Executer ensuite la build ou la commande de verification la plus directe pour la stack choisie.',
  ]

  return {
    summary: `Preflight local termine: ${chosenStack || 'stack non determinee'} avec ${toolFacts.filter((tool) => tool.available).length} outil(s) clefs disponibles.`,
    chosenStack: chosenStack || 'stack a confirmer',
    packageManager,
    executionStrategy: 'Prioriser la stack demandee si elle reste fidele a la mission; installer ou preparer ce qui manque avant validation plutot que coder a l aveugle.',
    localConstraints,
    machineFindings,
    workspaceFindings,
    reuseGuidance,
    mustInspectFirst: existingFileFacts.mustInspectFirst,
    validationPlan,
    toolFacts,
  }
}

function annotateFallbackReport(report: CodePreflightReport, note: string): CodePreflightReport {
  return {
    ...report,
    summary: `${report.summary} ${note}`.trim(),
    localConstraints: uniqueStrings([note, ...report.localConstraints]).slice(0, 8),
    validationPlan: uniqueStrings([
      ...report.validationPlan,
      'Le preflight a degrade proprement vers un mode deterministe pour eviter tout blocage silencieux.',
    ]).slice(0, 8),
  }
}

function serializeToolFacts(toolFacts: CodePreflightToolFact[]) {
  return toolFacts
    .map((tool) => `- ${tool.label}: ${tool.available ? `disponible (${tool.version || 'version inconnue'})` : 'absent'}`)
    .join('\n')
}

function serializeList(title: string, values: string[]) {
  return values.length > 0
    ? `${title}\n${values.map((value) => `- ${value}`).join('\n')}`
    : `${title}\n- rien de notable`
}

function buildPreflightPrompt(
  prompt: string,
  intent: CodeIntent,
  toolFacts: CodePreflightToolFact[],
  workspaceMarkers: string[],
  existingFileFacts: ReturnType<typeof inspectExistingFiles>,
) {
  return [
    'Tu es l architecte preflight du module CODE d AuroraIA.',
    'Avant toute generation de code, tu dois choisir une strategie fidele, precise et executable a partir des faits locaux.',
    '',
    'Reponds UNIQUEMENT en JSON valide avec cette forme exacte:',
    '{',
    '  "summary": "resume court et decisif",',
    '  "chosenStack": "stack retenue ou maintenue",',
    '  "packageManager": "npm|pnpm|yarn|bun|null",',
    '  "executionStrategy": "comment proceder avant la generation",',
    '  "localConstraints": ["contrainte locale"],',
    '  "machineFindings": ["fait machine"],',
    '  "workspaceFindings": ["fait workspace"],',
    '  "reuseGuidance": ["quoi relire ou reutiliser"],',
    '  "mustInspectFirst": ["fichier ou point a inspecter en premier"],',
    '  "validationPlan": ["verification concrete avant livraison"],',
    '}',
    '',
    'Regles:',
    '- Ne propose PAS encore de code source.',
    '- Priorite 1: fidelite a la mission utilisateur.',
    '- Priorite 2: utiliser au mieux ce qui existe deja localement.',
    '- Si la stack demandee manque localement mais reste necessaire, garde cette stack et note l installation/preparation requise au lieu de changer aveuglement.',
    '- Si des fichiers existent deja, privilegie leur lecture avant toute reecriture.',
    '- Sois concret et decisif.',
    '',
    `Mission utilisateur: ${prompt}`,
    `Projet detecte: ${intent.projectType} (${intent.complexity})`,
    intent.frameworks.length > 0 ? `Frameworks detectes: ${intent.frameworks.join(', ')}` : '',
    intent.languages.length > 0 ? `Langages detectes: ${intent.languages.join(', ')}` : '',
    '',
    'Outils locaux detectes:',
    serializeToolFacts(toolFacts),
    '',
    serializeList('Marqueurs du workspace local:', workspaceMarkers),
    '',
    serializeList('Faits issus des fichiers deja presents:', existingFileFacts.findings),
    '',
    serializeList('Fichiers a inspecter en priorite si present:', existingFileFacts.mustInspectFirst),
  ].filter(Boolean).join('\n')
}

function parsePreflightResponse(raw: string): Partial<CodePreflightReport> | null {
  try {
    const cleaned = raw.trim()
      .replace(/^```json?\s*/i, '')
      .replace(/\s*```$/, '')
      .trim()
    return JSON.parse(cleaned) as Partial<CodePreflightReport>
  } catch {
    return null
  }
}

function startPreflightHeartbeat(
  setPhase: ((detail: string, progress: number) => void) | undefined,
  timeoutMs: number,
) {
  if (!setPhase) {
    return () => {}
  }

  const startedAt = Date.now()
  let tick = 0

  const timer = globalThis.setInterval(() => {
    tick += 1
    const elapsed = Date.now() - startedAt
    const remainingSeconds = Math.max(0, Math.ceil((timeoutMs - elapsed) / 1000))
    setPhase(
      `Preflight local: synthese strategique en cours (${remainingSeconds}s avant fallback automatique)...`,
      Math.min(16, 11 + tick),
    )
  }, PREFLIGHT_HEARTBEAT_MS)

  return () => globalThis.clearInterval(timer)
}

export function serializeCodePreflightReport(report: CodePreflightReport) {
  return [
    `Resume: ${report.summary}`,
    `Stack retenue: ${report.chosenStack}`,
    `Package manager: ${report.packageManager || 'aucun'}`,
    `Strategie: ${report.executionStrategy}`,
    serializeList('Contraintes locales:', report.localConstraints),
    serializeList('Constats machine:', report.machineFindings),
    serializeList('Constats workspace:', report.workspaceFindings),
    serializeList('Reprise / reutilisation:', report.reuseGuidance),
    serializeList('Inspection prioritaire:', report.mustInspectFirst),
    serializeList('Plan de validation:', report.validationPlan),
  ].join('\n\n')
}

export async function runCodePreflight({
  prompt,
  intent,
  existingFiles,
  model,
  setPhase,
}: {
  prompt: string
  intent: CodeIntent
  existingFiles: PreflightCodeFile[]
  model?: string
  setPhase?: (detail: string, progress: number) => void
}): Promise<CodePreflightReport> {
  const workspacePath = await getWorkspacePath()
  const relevantTools = chooseRelevantToolIds(intent)

  setPhase?.('Preflight local: scan des outils et du workspace...', 8)
  const [toolFacts, workspaceMarkers] = await Promise.all([
    Promise.all(relevantTools.map((tool) => probeTool(tool, workspacePath))),
    inspectWorkspaceMarkers(workspacePath),
  ])

  const existingFileFacts = inspectExistingFiles(existingFiles)
  const fallback = buildFallbackReport(intent, toolFacts, workspaceMarkers, existingFileFacts)

  try {
    setPhase?.('Preflight local: synthese strategique...', 11)
    const selectedModel = model || CODE_SINGLE_MODEL
    const stopHeartbeat = startPreflightHeartbeat(setPhase, PREFLIGHT_SYNTHESIS_TIMEOUT_MS)
    let response: Awaited<ReturnType<typeof resilientOllamaGenerate>> | undefined
    try {
      response = await resilientOllamaGenerate(
        selectedModel,
        buildPreflightPrompt(prompt, intent, toolFacts, workspaceMarkers, existingFileFacts),
        { timeoutMs: PREFLIGHT_SYNTHESIS_TIMEOUT_MS },
      )
    } finally {
      stopHeartbeat()
    }
    const parsed = parsePreflightResponse(response?.response || '')
    if (!parsed) {
      setPhase?.('Preflight local: synthese non exploitable, fallback robuste applique...', 16)
      return annotateFallbackReport(
        fallback,
        'La synthese IA du preflight etait inutilisable; Aurora a poursuivi avec un diagnostic deterministe fiable.',
      )
    }

    return {
      summary: String(parsed.summary || fallback.summary),
      chosenStack: String(parsed.chosenStack || fallback.chosenStack),
      packageManager: parsed.packageManager ? String(parsed.packageManager) : fallback.packageManager,
      executionStrategy: String(parsed.executionStrategy || fallback.executionStrategy),
      localConstraints: uniqueStrings((parsed.localConstraints || fallback.localConstraints).map(String)).slice(0, 8),
      machineFindings: uniqueStrings((parsed.machineFindings || fallback.machineFindings).map(String)).slice(0, 10),
      workspaceFindings: uniqueStrings((parsed.workspaceFindings || fallback.workspaceFindings).map(String)).slice(0, 10),
      reuseGuidance: uniqueStrings((parsed.reuseGuidance || fallback.reuseGuidance).map(String)).slice(0, 8),
      mustInspectFirst: uniqueStrings((parsed.mustInspectFirst || fallback.mustInspectFirst).map(String)).slice(0, 8),
      validationPlan: uniqueStrings((parsed.validationPlan || fallback.validationPlan).map(String)).slice(0, 8),
      toolFacts,
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    const timedOut = /timed out after/i.test(message)
    setPhase?.(
      timedOut
        ? 'Preflight local: synthese time-boxee, fallback robuste applique...'
        : 'Preflight local: synthese indisponible, fallback robuste applique...',
      16,
    )
    return annotateFallbackReport(
      fallback,
      timedOut
        ? 'La synthese IA du preflight a depasse son temps utile; Aurora a bascule automatiquement vers un mode de secours deterministe.'
        : 'La synthese IA du preflight a echoue; Aurora a bascule automatiquement vers un mode de secours deterministe.',
    )
  }
}
