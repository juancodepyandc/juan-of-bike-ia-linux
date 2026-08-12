// Fichiers de REPRISE: ce qu il faut pour qu un autre humain puisse recuperer
// le projet sans rien deviner.
//
// Constat mesure sur les sept projets publies: aucun `.gitignore`, aucun
// `.env.example`, aucun `.nvmrc`. Un projet React livre sans `.gitignore`, la
// premiere chose que fera son proprietaire est de commiter `node_modules/`.
// C est exactement le genre de detail qui separe une demo d un livrable.
//
// Tout est DERIVE du projet reel: la liste d ignorance suit la pile detectee,
// et `.env.example` ne liste que les variables que le code lit vraiment. On
// n invente pas de licence: choisir a la place de l auteur serait une faute.

import type { CodeFile } from './codeOrchestratorTypes.ts'

const ALWAYS_IGNORED = [
  '# Dependances',
  'node_modules/',
  '',
  '# Build',
  'dist/',
  'build/',
  '.output/',
  '',
  '# Environnement local — ne JAMAIS commiter de secret',
  '.env',
  '.env.local',
  '.env.*.local',
  '',
  '# Journaux et caches',
  '*.log',
  'npm-debug.log*',
  '.cache/',
  '.vite/',
  '',
  '# Systeme et editeurs',
  '.DS_Store',
  'Thumbs.db',
  '.idea/',
  '.vscode/*',
  '!.vscode/extensions.json',
]

const PYTHON_IGNORED = ['', '# Python', '__pycache__/', '*.py[cod]', '.venv/', 'venv/', '.pytest_cache/', '.mypy_cache/']
const RUST_IGNORED = ['', '# Rust', 'target/', '**/*.rs.bk']
const GO_IGNORED = ['', '# Go', 'bin/', '*.test']

function hasFile(files: readonly CodeFile[], pattern: RegExp): boolean {
  return files.some((file) => pattern.test(file.name.replace(/\\/g, '/')))
}

export function buildGitignore(files: readonly CodeFile[]): string {
  const lines = [...ALWAYS_IGNORED]
  if (hasFile(files, /\.py$/i) || hasFile(files, /(^|\/)requirements\.txt$/i)) lines.push(...PYTHON_IGNORED)
  if (hasFile(files, /(^|\/)Cargo\.toml$/i)) lines.push(...RUST_IGNORED)
  if (hasFile(files, /(^|\/)go\.mod$/i)) lines.push(...GO_IGNORED)
  return `${lines.join('\n')}\n`
}

/**
 * Variables d environnement REELLEMENT lues par le code.
 *
 * On ne devine pas une liste type: on extrait `process.env.X`,
 * `import.meta.env.X` et `os.environ["X"]`. Une variable qui n est jamais lue
 * n a rien a faire dans un `.env.example`.
 */
export function collectEnvVariables(files: readonly CodeFile[]): string[] {
  const found = new Set<string>()
  const patterns = [
    /process\.env\.([A-Z0-9_]{2,})/g,
    /process\.env\[['"]([A-Z0-9_]{2,})['"]\]/g,
    /import\.meta\.env\.([A-Z0-9_]{2,})/g,
    /os\.environ(?:\.get)?[[(]\s*['"]([A-Z0-9_]{2,})['"]/g,
  ]
  for (const file of files) {
    const filePath = file.name.replace(/\\/g, '/')
    // Ne jamais lire une dependance ni un artefact: un `node_modules` egare
    // remonterait les variables d environnement de la MACHINE dans le
    // `.env.example` du projet (constate en test: APPDATA, ANTIGRAVITY_AGENT).
    if (/(^|\/)(node_modules|dist|build|vendor|\.git)\//.test(filePath)) continue
    if (/(^|\/)(\.env|README)/i.test(filePath)) continue
    if (!/\.(m?[jt]sx?|vue|svelte|astro|py|rb|go|rs|php)$/i.test(filePath)) continue
    for (const pattern of patterns) {
      for (const match of file.content.matchAll(pattern)) {
        const name = match[1]
        // NODE_ENV et MODE sont fournis par l outillage, pas par l utilisateur.
        if (['NODE_ENV', 'MODE', 'BASE_URL', 'PROD', 'DEV', 'SSR'].includes(name)) continue
        found.add(name)
      }
    }
  }
  // Une liste sans fin ne se renseigne pas: on borne a ce qu un humain lira.
  return [...found].sort().slice(0, 24)
}

export function buildEnvExample(variables: readonly string[]): string {
  return [
    '# Copier ce fichier en `.env` puis renseigner les valeurs.',
    '# `.env` est ignore par git: aucun secret ne doit etre commite.',
    '',
    ...variables.map((name) => `${name}=`),
    '',
  ].join('\n')
}

/** Version majeure de Node exigee par la pile livree. */
export function resolveNodeMajor(files: readonly CodeFile[]): number | null {
  const manifest = files.find((file) => /(^|\/)package\.json$/i.test(file.name))
  if (!manifest) return null
  try {
    const parsed = JSON.parse(manifest.content) as {
      engines?: { node?: string }
      devDependencies?: Record<string, string>
      dependencies?: Record<string, string>
    }
    const declared = parsed.engines?.node
    const fromEngines = declared ? Number(String(declared).match(/(\d+)/)?.[1]) : NaN
    if (Number.isFinite(fromEngines)) return fromEngines
    const vite = parsed.devDependencies?.vite ?? parsed.dependencies?.vite
    const viteMajor = vite ? Number(String(vite).match(/(\d+)/)?.[1]) : NaN
    if (Number.isFinite(viteMajor)) return viteMajor >= 7 ? 20 : 18
    return 20
  } catch {
    return null
  }
}

/**
 * Ajoute les fichiers de reprise manquants. Idempotent: un fichier deja fourni
 * par le modele n est jamais ecrase.
 */
export function upsertProjectScaffoldFiles(files: CodeFile[]): CodeFile[] {
  const present = new Set(files.map((file) => file.name.replace(/\\/g, '/').toLowerCase()))
  const added: CodeFile[] = []

  if (!present.has('.gitignore')) {
    added.push({ name: '.gitignore', language: 'text', content: buildGitignore(files) })
  }

  const variables = collectEnvVariables(files)
  if (variables.length > 0 && !present.has('.env.example')) {
    added.push({ name: '.env.example', language: 'text', content: buildEnvExample(variables) })
  }

  const nodeMajor = resolveNodeMajor(files)
  if (nodeMajor && !present.has('.nvmrc')) {
    added.push({ name: '.nvmrc', language: 'text', content: `${nodeMajor}\n` })
  }

  return added.length === 0 ? files : [...files, ...added]
}
