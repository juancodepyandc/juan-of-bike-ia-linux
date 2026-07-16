import { fsExists, runWorkspaceCommand } from '../hooks/useTauri'
import type { CodeIntent } from './codeIntent'

type ToolProbeSpec = {
  id: string
  executable: string
  args: string[]
  label: string
}

export type CodePreflightFile = {
  name: string
  language: string
  content: string
}

export type CodePreflightToolFact = {
  id: string
  label: string
  available: boolean
  version: string | null
  command: string
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

function normalizeWhitespace(text: string) {
  return text.replace(/\s+/g, ' ').trim()
}

function shorten(text: string, limit = 220) {
  const normalized = normalizeWhitespace(text)
  return normalized.length <= limit ? normalized : `${normalized.slice(0, limit)}...`
}

export function uniquePreflightStrings(values: string[]) {
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

export function chooseRelevantPreflightTools(intent: CodeIntent) {
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
    for (const id of ['node', 'npm', 'pnpm', 'yarn', 'bun']) selected.add(id)
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

  if (projectType === 'api_gin' || projectType === 'cli_go') selected.add('go')
  if (projectType === 'api_dotnet' || intent.languages.includes('csharp')) selected.add('dotnet')
  if (projectType === 'api_spring' || intent.languages.includes('java') || intent.languages.includes('kotlin')) {
    selected.add('java')
    selected.add('javac')
  }

  return TOOL_SPECS.filter((tool) => selected.has(tool.id))
}

export async function probePreflightTool(
  spec: ToolProbeSpec,
  cwd: string,
): Promise<CodePreflightToolFact> {
  const command = `${spec.executable} ${spec.args.join(' ')}`.trim()
  try {
    const result = await runWorkspaceCommand(spec.executable, spec.args, cwd, PREFLIGHT_TOOL_TIMEOUT_MS)
    return {
      id: spec.id,
      label: spec.label,
      available: result.ok,
      version: result.ok ? extractVersion(result.output) : null,
      command,
    }
  } catch {
    return { id: spec.id, label: spec.label, available: false, version: null, command }
  }
}

export async function inspectPreflightWorkspaceMarkers(rootPath: string) {
  const checks = await Promise.all(
    WORKSPACE_MARKERS.map(async (marker) => ({
      marker,
      present: await fsExists(`${rootPath}/${marker}`).catch(() => false),
    })),
  )
  return checks.filter((entry) => entry.present).map((entry) => entry.marker)
}

export function inspectPreflightExistingFiles(files: CodePreflightFile[]) {
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

  return { findings, mustInspectFirst: uniquePreflightStrings(mustInspectFirst) }
}

export function selectPreferredPackageManager(
  toolFacts: CodePreflightToolFact[],
  workspaceMarkers: string[],
) {
  const available = new Set(toolFacts.filter((tool) => tool.available).map((tool) => tool.id))
  if (workspaceMarkers.includes('pnpm-lock.yaml') && available.has('pnpm')) return 'pnpm'
  if (workspaceMarkers.includes('yarn.lock') && available.has('yarn')) return 'yarn'
  if ((workspaceMarkers.includes('bun.lock') || workspaceMarkers.includes('bun.lockb')) && available.has('bun')) return 'bun'
  for (const id of ['npm', 'pnpm', 'yarn', 'bun']) {
    if (available.has(id)) return id
  }
  return null
}
