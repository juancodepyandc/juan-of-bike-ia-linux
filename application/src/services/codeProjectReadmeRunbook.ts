// ---------------------------------------------------------------------------
// codeProjectReadmeRunbook — prerequisites + real scripts + one-liner.
// Reads the ACTUAL generated package.json (or Python/Rust/Go manifest) and
// documents what is truly there, never a guessed command. Pure functions.
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestratorTypes.ts'

export type ProjectRunbook = {
  prerequisites: string[]
  scriptDocs: string[]
  oneLiner: string | null
  installBlock: string[]
  runBlock: string[]
  runUrl: string | null
}

function safeParseJson(text: string): unknown {
  try { return JSON.parse(text) } catch { return null }
}

function normalizedNames(files: CodeFile[]): string[] {
  return files.map((f) => f.name.replace(/\\/g, '/').toLowerCase())
}

function findPackageManifest(files: CodeFile[]) {
  const f = files.find((x) => x.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  return f ? (safeParseJson(f.content) as PackageJson | null) : null
}

type PackageJson = {
  name?: string
  scripts?: Record<string, string>
  dependencies?: Record<string, string>
  devDependencies?: Record<string, string>
  engines?: { node?: string }
}

const SCRIPT_PURPOSE_FR: Record<string, string> = {
  dev: 'lance le serveur de développement (hot reload).',
  start: 'démarre l\'application.',
  build: 'compile la version de production.',
  preview: 'sert le build compilé pour recette avant déploiement.',
  test: 'exécute la suite de tests.',
  lint: 'vérifie le style de code.',
  format: 'reformate le code selon le style du projet.',
  typecheck: 'vérifie les types sans compiler.',
  check: 'exécute les vérifications du projet.',
}

const SCRIPT_ORDER = ['dev', 'start', 'build', 'preview', 'test', 'typecheck', 'lint', 'format', 'check']

function scriptDocLine(name: string, command: string): string {
  const purpose = SCRIPT_PURPOSE_FR[name] || 'commande projet.'
  return `- \`npm run ${name}\` (\`${command}\`) — ${purpose}`
}

function parseMajor(spec: string | undefined): number | null {
  if (!spec || typeof spec !== 'string') return null
  const cleaned = spec.trim().replace(/^[\^~=><\s]+/, '')
  const major = parseInt(cleaned, 10)
  return Number.isNaN(major) ? null : major
}

function detectRequiredNodeVersion(pkg: PackageJson | null): string {
  const engines = pkg?.engines?.node
  if (typeof engines === 'string' && engines.trim()) return engines.trim()
  const viteMajor = parseMajor(pkg?.devDependencies?.vite || pkg?.dependencies?.vite)
  if (viteMajor !== null) {
    if (viteMajor >= 6) return `>= 20 (Vite ${viteMajor} exige Node 20+).`
    if (viteMajor >= 5) return `>= 18 (Vite ${viteMajor} exige Node 18+).`
    if (viteMajor >= 4) return `>= 16 (Vite ${viteMajor} exige Node 16+).`
  }
  const nextMajor = parseMajor(pkg?.dependencies?.next || pkg?.devDependencies?.next)
  if (nextMajor !== null && nextMajor >= 14) return `>= 18.17 (Next.js ${nextMajor} exige Node 18.17+).`
  return '>= 18.'
}

function detectRunUrl(pkg: PackageJson | null, files: string[]): string | null {
  const scripts = pkg?.scripts || {}
  const dev = (scripts.dev || scripts.start || '').toString()
  if (/\bnext\b/.test(dev)) return 'http://localhost:3000/'
  if (/\bnuxt\b/.test(dev)) return 'http://localhost:3000/'
  if (/\bremix\b/.test(dev)) return 'http://localhost:3000/'
  if (/\bvite\b/.test(dev)) return 'http://localhost:5173/'
  if (files.some((n) => /^vite\.config\./.test(n))) return 'http://localhost:5173/'
  return null
}

// --------------------------------------------------------------------------
// Runbook builders per stack family.
// --------------------------------------------------------------------------

function buildStaticRunbook(files: string[]): ProjectRunbook {
  const hasIndex = files.includes('index.html')
  return {
    prerequisites: ['Aucun (le projet est statique — un navigateur suffit).'],
    scriptDocs: [],
    oneLiner: null,
    installBlock: [],
    runBlock: hasIndex
      ? ['Ouvrir `index.html` dans un navigateur, ou servir le dossier:', '', '```bash', 'python -m http.server 8000', '```']
      : ['Servir le dossier avec un serveur HTTP simple:', '', '```bash', 'python -m http.server 8000', '```'],
    runUrl: null,
  }
}

function buildNodeRunbook(pkg: PackageJson | null, intent: CodeIntent, files: string[]): ProjectRunbook {
  const scripts: Record<string, string> = (pkg?.scripts && typeof pkg.scripts === 'object' ? pkg.scripts : {}) as Record<string, string>
  const prerequisites = [
    `Node.js ${detectRequiredNodeVersion(pkg)}`,
    'npm (fourni avec Node) — pnpm ou yarn fonctionnent aussi.',
  ]

  const preferred: string[] = []
  const seen = new Set<string>()
  for (const name of SCRIPT_ORDER) {
    if (scripts[name]) {
      preferred.push(scriptDocLine(name, scripts[name]))
      seen.add(name)
    }
  }
  const others: string[] = []
  for (const name of Object.keys(scripts).sort()) {
    if (!seen.has(name)) others.push(scriptDocLine(name, scripts[name]))
  }
  const scriptDocs = [...preferred, ...others]

  const primaryRun = scripts.dev
    ? 'npm run dev'
    : scripts.start
      ? 'npm start'
      : intent.devCommand || 'npm run dev'
  const oneLiner = `npm install && ${primaryRun}`
  return {
    prerequisites,
    scriptDocs,
    oneLiner,
    installBlock: ['```bash', 'npm install', '```'],
    runBlock: ['```bash', primaryRun, '```'],
    runUrl: detectRunUrl(pkg, files),
  }
}

function buildPythonRunbook(files: CodeFile[], intent: CodeIntent, normalized: string[]): ProjectRunbook {
  const hasRequirements = normalized.includes('requirements.txt')
  const pyEntry = files.find((f) => /(^|\/)(main|app)\.py$/i.test(f.name.replace(/\\/g, '/')))
  const runCmd = intent.devCommand || (pyEntry ? `python ${pyEntry.name}` : 'python main.py')

  const prerequisites = [
    'Python ≥ 3.10.',
    hasRequirements ? '`pip` (environnement virtuel recommandé).' : 'Installer manuellement les dépendances du projet.',
  ]
  const installBlock = hasRequirements
    ? ['```bash', 'python -m venv .venv && source .venv/bin/activate', 'pip install -r requirements.txt', '```']
    : []
  const runBlock = ['```bash', runCmd, '```']
  const oneLiner = hasRequirements
    ? `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && ${runCmd}`
    : runCmd
  return { prerequisites, scriptDocs: [], oneLiner, installBlock, runBlock, runUrl: null }
}

function buildRustRunbook(intent: CodeIntent): ProjectRunbook {
  return {
    prerequisites: ['Rust stable (`rustup toolchain install stable`).'],
    scriptDocs: [],
    oneLiner: `cargo run`,
    installBlock: ['```bash', 'cargo build', '```'],
    runBlock: ['```bash', intent.devCommand || 'cargo run', '```'],
    runUrl: null,
  }
}

function buildGoRunbook(intent: CodeIntent): ProjectRunbook {
  return {
    prerequisites: ['Go ≥ 1.21.'],
    scriptDocs: [],
    oneLiner: 'go mod tidy && go run .',
    installBlock: ['```bash', 'go mod tidy', '```'],
    runBlock: ['```bash', intent.devCommand || 'go run .', '```'],
    runUrl: null,
  }
}

function buildFallbackRunbook(): ProjectRunbook {
  return {
    prerequisites: ['Voir les fichiers de configuration du projet pour les dépendances exactes.'],
    scriptDocs: [],
    oneLiner: null,
    installBlock: [],
    runBlock: ['Consulter le code livré pour lancer manuellement le projet.'],
    runUrl: null,
  }
}

// --------------------------------------------------------------------------
// Public entrypoint.
// --------------------------------------------------------------------------

export function buildProjectRunbook(files: CodeFile[], intent: CodeIntent): ProjectRunbook {
  const normalized = normalizedNames(files)
  const pkg = findPackageManifest(files)

  if (intent.projectType === 'static_web' || intent.projectType === 'game_web') {
    return buildStaticRunbook(normalized)
  }

  if (
    intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType === 'fullstack_mern'
    || intent.projectType === 'fullstack_nextjs'
    || intent.projectType === 'desktop_electron'
    || intent.projectType === 'desktop_tauri'
    || intent.projectType === 'api_express'
    || intent.projectType === 'cli_node'
    || intent.projectType === 'library_npm'
    || normalized.some((n) => n.endsWith('package.json'))
  ) {
    return buildNodeRunbook(pkg, intent, normalized)
  }

  if (
    intent.projectType === 'api_fastapi' || intent.projectType === 'api_django'
    || intent.projectType === 'api_flask' || intent.projectType === 'fullstack_django'
    || intent.projectType === 'cli_python' || intent.projectType === 'data_python'
  ) {
    return buildPythonRunbook(files, intent, normalized)
  }

  if (
    intent.projectType === 'api_actix' || intent.projectType === 'cli_rust'
    || intent.projectType === 'system_rust' || intent.projectType === 'library_crate'
  ) {
    return buildRustRunbook(intent)
  }

  if (intent.projectType === 'api_gin' || intent.projectType === 'cli_go') {
    return buildGoRunbook(intent)
  }

  return buildFallbackRunbook()
}
