import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import { formatArchitecturePlanDependenciesForMarkdown } from './codeArchitecturePlan.ts'
import {
  manifestUsesPackage,
  stripFormattingArtifacts,
  tryParseJson,
  upsertPackageDevDependency,
} from './codeGeneratedFileSanitizer.ts'
import { getGeneratedNodeDependencySpec } from './codeGeneratedDependencyPolicy.ts'
import { isSyntheticFallbackFile } from './codeProjectValidation.ts'

type ProjectRunbook = {
  installSteps: string[]
  runSteps: string[]
}

function buildProjectRunbook(files: CodeFile[], intent: CodeIntent): ProjectRunbook {
  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasPackageJson = normalizedNames.some((name) => name.endsWith('package.json'))
  const hasRequirements = normalizedNames.includes('requirements.txt')
  const hasCargo = normalizedNames.some((name) => name.endsWith('cargo.toml'))
  const hasIndexHtml = normalizedNames.includes('index.html')
  const pythonEntry = files.find((file) => /(^|\/)(main|app)\.py$/i.test(file.name.replace(/\\/g, '/')))
  const runCommand = intent.devCommand || intent.buildCommand

  if (intent.projectType === 'static_web' || intent.projectType === 'game_web') {
    return {
      installSteps: ['Aucune installation requise.'],
      runSteps: [
        hasIndexHtml ? 'Ouvrir `index.html` dans un navigateur.' : 'Le projet doit fournir un `index.html` pour la preview.',
      ],
    }
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
    || hasPackageJson
  ) {
    const resolvedRunCommand = runCommand || (hasPackageJson ? 'npm start' : 'npm run dev')
    const installSteps = ['```bash', 'npm install', '```']
    if (intent.projectType === 'desktop_tauri' && hasCargo) {
      installSteps.push('', '```bash', 'cargo build', '```')
    }
    return {
      installSteps,
      runSteps: ['```bash', resolvedRunCommand, '```'],
    }
  }

  if (
    intent.projectType === 'api_fastapi'
    || intent.projectType === 'api_django'
    || intent.projectType === 'api_flask'
    || intent.projectType === 'fullstack_django'
    || intent.projectType === 'cli_python'
    || intent.projectType === 'data_python'
  ) {
    const resolvedRunCommand = runCommand || (pythonEntry ? `python ${pythonEntry.name}` : 'python main.py')
    return {
      installSteps: hasRequirements
        ? ['```bash', 'pip install -r requirements.txt', '```']
        : ['Installer Python 3.11+ puis les dependances du projet.'],
      runSteps: ['```bash', resolvedRunCommand, '```'],
    }
  }

  if (intent.projectType === 'api_actix' || intent.projectType === 'cli_rust' || intent.projectType === 'system_rust' || intent.projectType === 'library_crate') {
    const resolvedRunCommand = runCommand || 'cargo run'
    return {
      installSteps: ['```bash', 'cargo build', '```'],
      runSteps: ['```bash', resolvedRunCommand, '```'],
    }
  }

  if (intent.projectType === 'api_gin' || intent.projectType === 'cli_go') {
    const resolvedRunCommand = runCommand || 'go run .'
    return {
      installSteps: ['```bash', 'go mod tidy', '```'],
      runSteps: ['```bash', resolvedRunCommand, '```'],
    }
  }

  return {
    installSteps: ['Voir les fichiers de configuration du projet pour les dependances exactes.'],
    runSteps: ['Consulter le code livre et le README pour lancer manuellement le projet.'],
  }
}

function buildLinuxLaunchScriptLines(files: CodeFile[], intent: CodeIntent): string[] {
  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasPackageJson = normalizedNames.some((name) => name.endsWith('package.json'))
  const hasRequirements = normalizedNames.includes('requirements.txt')
  const hasCargo = normalizedNames.some((name) => name.endsWith('cargo.toml'))
  const pythonEntry = files.find((file) => /(^|\/)(main|app)\.py$/i.test(file.name.replace(/\\/g, '/')))
  const runCommand = intent.devCommand || intent.buildCommand

  if (intent.projectType === 'static_web') return []

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
    || hasPackageJson
  ) {
    const resolvedRunCommand = runCommand || (hasPackageJson ? 'npm start' : 'npm run dev')
    const lines = [
      '#!/usr/bin/env bash',
      'set -euo pipefail',
      'cd "$(dirname "$0")"',
      'if ! command -v npm >/dev/null 2>&1; then echo "Node.js avec npm est requis." >&2; exit 1; fi',
      'if [ ! -d "node_modules" ]; then npm install; fi',
    ]
    if (intent.projectType === 'desktop_tauri' && hasCargo) {
      lines.push('if ! command -v cargo >/dev/null 2>&1; then echo "Rust/Cargo est requis pour Tauri." >&2; exit 1; fi')
    }
    lines.push(resolvedRunCommand)
    return lines
  }

  if (
    intent.projectType === 'api_fastapi'
    || intent.projectType === 'api_django'
    || intent.projectType === 'api_flask'
    || intent.projectType === 'fullstack_django'
    || intent.projectType === 'cli_python'
    || intent.projectType === 'data_python'
  ) {
    const resolvedRunCommand = runCommand || (pythonEntry ? `python ${pythonEntry.name}` : 'python main.py')
    const lines = [
      '#!/usr/bin/env bash',
      'set -euo pipefail',
      'cd "$(dirname "$0")"',
      'command -v python >/dev/null 2>&1 || { echo "Python est requis." >&2; exit 1; }',
    ]
    if (hasRequirements) lines.push('python -m pip install -r requirements.txt')
    lines.push(resolvedRunCommand)
    return lines
  }

  if (intent.projectType === 'api_actix' || intent.projectType === 'cli_rust' || intent.projectType === 'system_rust' || intent.projectType === 'library_crate') {
    return [
      '#!/usr/bin/env bash',
      'set -euo pipefail',
      'cd "$(dirname "$0")"',
      'command -v cargo >/dev/null 2>&1 || { echo "Rust/Cargo est requis." >&2; exit 1; }',
      runCommand || 'cargo run',
    ]
  }

  if (intent.projectType === 'api_gin' || intent.projectType === 'cli_go') {
    return [
      '#!/usr/bin/env bash',
      'set -euo pipefail',
      'cd "$(dirname "$0")"',
      'command -v go >/dev/null 2>&1 || { echo "Go est requis." >&2; exit 1; }',
      'go mod tidy',
      runCommand || 'go run .',
    ]
  }

  return []
}

function generateLinuxLaunchScript(files: CodeFile[], intent: CodeIntent): CodeFile | null {
  const hasLaunchScript = files.some((f) => /^(start|launch|lancement)\.(sh|bat)$/i.test(f.name.replace(/.*[/\\]/, '')))
  if (hasLaunchScript) return null

  const lines = buildLinuxLaunchScriptLines(files, intent)
  if (lines.length === 0) return null

  return {
    name: 'start.sh',
    language: 'bash',
    content: lines.join('\n'),
  }
}

/**
 * Some local models spray Tailwind utility
 * classes (flex, grid, text-5xl, bg-…) WITHOUT including Tailwind and without
 * generating the matching CSS → an unstyled BLACK page. If an HTML file uses
 * Tailwind utilities but ships no Tailwind, inject the Play CDN + a dark-mode
 * config so the page actually renders. No-op when the model wrote real CSS or
 * already included Tailwind.
 */
function ensureTailwindCDN(files: CodeFile[], projectType?: string): CodeFile[] {
  // A canvas game is self-styled (inline <style> + canvas draw calls) and never
  // needs Tailwind. The utility-class heuristic below false-positives on plain
  // class names like "container", injecting a ~2 KB marketing theme + an external
  // CDN script as dead weight. Skip it for games entirely.
  if (projectType === 'game_web') return files
  const TW_UTIL = /class="[^"]*\b(flex|grid|hidden|container|mx-auto|justify-\w+|items-\w+|text-(xs|sm|base|lg|xl|\dxl|center|fg|accent)|bg-[a-z]+(-\d{2,3})?|[pmgw][xytblr]?-\d|gap-\d|rounded(-\w+)?|shadow(-\w+)?|font-(bold|semibold|medium)|grid-cols-\d)\b/
  const HAS_TW = /cdn\.tailwindcss\.com|@tailwind\b/
  // v85g : local models spray SEMANTIC Tailwind tokens (bg-surface, text-fg,
  // text-fg-dim, bg-accent, shadow-2…) that need a config to be defined —
  // without it the classes resolve to NOTHING → unstyled/black page. We inject
  // the Play CDN + a CSS-variable theme + a Tailwind config that defines that
  // exact vocabulary, with light/dark wired to [data-theme="dark"]/.dark AND
  // prefers-color-scheme, so the page renders styled and the dark toggle works.
  const inject = [
    '<style data-aurora-theme>',
    ':root{--c-surface:255 255 255;--c-surface-elevated:248 247 245;--c-card:255 255 255;--c-fg:23 23 23;--c-fg-dim:90 92 100;--c-fg-mute:140 142 150;--c-line:230 230 234;--c-accent:124 92 255;--c-accent-soft:139 110 255}',
    '[data-theme="dark"],.dark{--c-surface:12 11 16;--c-surface-elevated:24 24 30;--c-card:22 22 28;--c-fg:240 240 245;--c-fg-dim:170 172 180;--c-fg-mute:120 122 130;--c-line:42 42 50;--c-accent:160 140 255;--c-accent-soft:175 155 255}',
    '@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--c-surface:12 11 16;--c-surface-elevated:24 24 30;--c-card:22 22 28;--c-fg:240 240 245;--c-fg-dim:170 172 180;--c-fg-mute:120 122 130;--c-line:42 42 50;--c-accent:160 140 255;--c-accent-soft:175 155 255}}',
    'body{background:rgb(var(--c-surface));color:rgb(var(--c-fg));transition:background .3s ease,color .3s ease}',
    '</style>',
    '<script src="https://cdn.tailwindcss.com"></script>',
    '<script>tailwind.config={darkMode:["selector",\'[data-theme="dark"]\'],theme:{extend:{colors:{'
    + 'surface:{DEFAULT:"rgb(var(--c-surface) / <alpha-value>)",elevated:"rgb(var(--c-surface-elevated) / <alpha-value>)"},'
    + 'card:"rgb(var(--c-card) / <alpha-value>)",line:"rgb(var(--c-line) / <alpha-value>)",'
    + 'fg:{DEFAULT:"rgb(var(--c-fg) / <alpha-value>)",dim:"rgb(var(--c-fg-dim) / <alpha-value>)",mute:"rgb(var(--c-fg-mute) / <alpha-value>)"},'
    + 'accent:{DEFAULT:"rgb(var(--c-accent) / <alpha-value>)",soft:"rgb(var(--c-accent-soft) / <alpha-value>)"}},'
    + 'boxShadow:{2:"0 4px 16px rgb(0 0 0 / 0.08)",3:"0 12px 32px rgb(0 0 0 / 0.14)"}}}};</script>',
  ].join('\n')
  return files.map((f) => {
    if (!/\.html?$/i.test(f.name)) return f
    const c = f.content
    if (!TW_UTIL.test(c) || HAS_TW.test(c)) return f
    let next = c
    if (/<\/head>/i.test(next)) next = next.replace(/<\/head>/i, `${inject}\n</head>`)
    else if (/<head[^>]*>/i.test(next)) next = next.replace(/<head[^>]*>/i, (m) => `${m}\n${inject}`)
    else next = `${inject}\n${next}`
    return { ...f, content: next }
  })
}

function ensureSpaIndexHtml(files: CodeFile[], intent: CodeIntent): CodeFile[] {
  if (!intent.projectType.startsWith('spa_')) return files

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  if (normalizedNames.includes('index.html')) return files

  const entry = [
    'src/main.tsx',
    'src/main.jsx',
    'src/main.ts',
    'src/main.js',
    'src/index.tsx',
    'src/index.jsx',
    'src/index.ts',
    'src/index.js',
    'main.tsx',
    'main.jsx',
    'main.ts',
    'main.js',
    'index.tsx',
    'index.jsx',
    'index.ts',
    'index.js',
  ].find((candidate) => normalizedNames.includes(candidate))

  if (!entry) return files

  const title = intent.projectType.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
  const html = [
    '<!doctype html>',
    '<html lang="en">',
    '  <head>',
    '    <meta charset="UTF-8" />',
    '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />',
    `    <title>${title}</title>`,
    '  </head>',
    '  <body>',
    '    <div id="root"></div>',
    `    <script type="module" src="/${entry}"></script>`,
    '  </body>',
    '</html>',
    '',
  ].join('\n')

  return [
    ...files,
    {
      name: 'index.html',
      language: 'html',
      content: html,
    },
  ]
}

function ensureSpaViteConfig(files: CodeFile[], intent: CodeIntent): CodeFile[] {
  if (!intent.projectType.startsWith('spa_')) return files

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  if (normalizedNames.some((name) => /^vite\.config\.(?:ts|js|mjs|mts)$/.test(name))) return files

  return [
    ...files,
    {
      name: 'vite.config.ts',
      language: 'typescript',
      content: [
        "import { defineConfig } from 'vite'",
        "import react from '@vitejs/plugin-react'",
        '',
        'export default defineConfig({',
        '  plugins: [react()],',
        '  server: {',
        "    host: '127.0.0.1',",
        '    port: 5173,',
        '  },',
        '})',
        '',
      ].join('\n'),
    },
  ]
}

function fileSet(files: CodeFile[]) {
  return new Set(files.map((file) => file.name.replace(/\\/g, '/').toLowerCase()))
}

function projectUsesTailwindTooling(files: CodeFile[]) {
  const names = fileSet(files)
  if ([...names].some((name) => /(^|\/)tailwind\.config\.(?:js|cjs|mjs|ts)$/.test(name))) return true
  if (files.some((file) => /@tailwind\b|@apply\b/.test(file.content))) return true

  const packageFile = files.find((file) => file.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  if (!packageFile) return false
  const manifest = tryParseJson(stripFormattingArtifacts(packageFile.content))
  return Boolean(manifest && manifestUsesPackage(manifest, 'tailwindcss'))
}

function ensureTailwindTooling(files: CodeFile[]) {
  if (!projectUsesTailwindTooling(files)) return files
  const names = fileSet(files)
  let nextFiles = files

  const packageIndex = nextFiles.findIndex((file) => file.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  if (packageIndex >= 0) {
    const manifest = tryParseJson(stripFormattingArtifacts(nextFiles[packageIndex].content))
    if (manifest) {
      let nextManifest = upsertPackageDevDependency(manifest, 'tailwindcss', getGeneratedNodeDependencySpec('tailwindcss'), true)
      nextManifest = upsertPackageDevDependency(nextManifest, 'postcss', getGeneratedNodeDependencySpec('postcss'), true)
      nextManifest = upsertPackageDevDependency(nextManifest, 'autoprefixer', getGeneratedNodeDependencySpec('autoprefixer'), true)
      nextFiles = nextFiles.map((file, index) => index === packageIndex
        ? { ...file, content: `${JSON.stringify(nextManifest, null, 2)}\n` }
        : file)
    }
  }

  if (names.has('postcss.config.js') || names.has('postcss.config.cjs') || names.has('postcss.config.mjs')) {
    return nextFiles
  }

  return [
    ...nextFiles,
    {
      name: 'postcss.config.js',
      language: 'javascript',
      content: [
        'export default {',
        '  plugins: {',
        '    tailwindcss: {},',
        '    autoprefixer: {},',
        '  },',
        '}',
        '',
      ].join('\n'),
    },
  ]
}

function stripSyntheticFallbackFiles(files: CodeFile[], intent: CodeIntent): CodeFile[] {
  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasStructuredProject =
    normalizedNames.includes('package.json')
    || normalizedNames.includes('index.html')
    || normalizedNames.some((name) => name.startsWith('src/'))

  if (!hasStructuredProject) return files

  const shouldStrip = intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType.startsWith('fullstack_')
    || intent.projectType.startsWith('api_')
    || intent.needsDevServer
    || intent.needsBundling

  if (!shouldStrip) return files
  return files.filter((file) => !isSyntheticFallbackFile(file.name))
}

export function upsertProjectSupportFiles(
  files: CodeFile[],
  intent: CodeIntent,
  prompt: string,
  architecturePlan: string | null,
): CodeFile[] {
  const strippedFiles = ensureTailwindCDN(files, intent.projectType).filter((file) => {
    const name = file.name.replace(/\\/g, '/').toLowerCase()
    return name !== 'readme.md' && name !== 'start.sh' && !name.endsWith('.bat')
  })
  const baseFiles = ensureSpaViteConfig(
    ensureSpaIndexHtml(stripSyntheticFallbackFiles(strippedFiles, intent), intent),
    intent,
  )
  const supportedFiles = ensureTailwindTooling(baseFiles)

  const nextFiles = [...supportedFiles, generateReadme(supportedFiles, intent, prompt, architecturePlan)]
  const launchScript = generateLinuxLaunchScript(supportedFiles, intent)
  if (launchScript) nextFiles.push(launchScript)

  return nextFiles
}

export function upsertProjectSupportFilesForTest(
  files: CodeFile[],
  intent: CodeIntent,
  prompt = '',
  architecturePlan: string | null = null,
) {
  return upsertProjectSupportFiles(files, intent, prompt, architecturePlan)
}

// ---------------------------------------------------------------------------
// README auto-generation — ensures every project has install/run instructions
// ---------------------------------------------------------------------------

function generateReadme(
  files: CodeFile[],
  intent: CodeIntent,
  prompt: string,
  architecturePlan: string | null,
): CodeFile {
  const fileList = files
    .filter((f) => f.name.toLowerCase() !== 'readme.md')
    .map((f) => `- \`${f.name}\` — ${f.language}`)
    .join('\n')

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasPackageJson = normalizedNames.includes('package.json')
  const hasRequirements = normalizedNames.includes('requirements.txt')
  const hasCargo = normalizedNames.some((name) => name.endsWith('cargo.toml'))

  const installSteps: string[] = []
  if (hasPackageJson) {
    installSteps.push('```bash', 'npm install', '```')
  }
  if (hasRequirements) {
    installSteps.push('```bash', 'pip install -r requirements.txt', '```')
  }
  if (hasCargo) {
    installSteps.push('```bash', 'cargo build', '```')
  }
  if (installSteps.length === 0) {
    if (intent.projectType === 'static_web' || intent.projectType === 'game_web') {
      installSteps.push('Aucune installation requise — ouvrir `index.html` dans un navigateur.')
    } else {
      installSteps.push('Voir les dependances dans les fichiers de configuration du projet.')
    }
  }

  const runSteps: string[] = []
  if (intent.devCommand) {
    runSteps.push('```bash', intent.devCommand, '```')
  } else if (intent.projectType === 'static_web') {
    runSteps.push('Ouvrir `index.html` dans un navigateur web.')
  } else if (hasPackageJson) {
    runSteps.push('```bash', 'npm start', '```')
  } else if (files.some((f) => f.name === 'app.py' || f.name === 'main.py')) {
    const entry = files.find((f) => f.name === 'app.py') ? 'app.py' : 'main.py'
    runSteps.push('```bash', `python ${entry}`, '```')
  }

  const runbook = buildProjectRunbook(files, intent)

  // Extract dependencies from plan if available
  let depsSection = ''
  if (architecturePlan) {
    const dependencies = formatArchitecturePlanDependenciesForMarkdown(architecturePlan)
    if (dependencies) {
      depsSection = `## Dependances\n\n${dependencies}\n\n`
    }
  }

  const content = [
    `# ${intent.projectType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}`,
    '',
    `> ${prompt.slice(0, 200)}${prompt.length > 200 ? '...' : ''}`,
    '',
    '## Structure du projet',
    '',
    fileList,
    '',
    depsSection,
    '## Installation',
    '',
    runbook.installSteps.join('\n'),
    '',
    '## Lancement',
    '',
    runbook.runSteps.join('\n'),
    '',
    '## Raccourci de lancement',
    '',
    'Le fichier `start.sh` est fourni quand un demarrage automatise est possible sur Linux/macOS.',
    '',
    '---',
    '*Genere par Aurora IA — Module Code*',
  ].join('\n')

  return {
    name: 'README.md',
    language: 'markdown',
    content,
  }
}
