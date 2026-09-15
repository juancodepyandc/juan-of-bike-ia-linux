import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import {
  stripFormattingArtifacts,
  tryParseJson,
} from './codeGeneratedFileSanitizer.ts'
import { ensureTailwindCDN, ensureTailwindTooling } from './codeProjectTailwindSupport.ts'
import { isSyntheticFallbackFile } from './codeProjectValidation.ts'
import { generateProjectReadme } from './codeProjectReadme.ts'
import { upsertProjectScaffoldFiles } from './codeProjectScaffoldFiles.ts'
import { repairDanglingIconLinks } from './codeDanglingBinaryAssets.ts'
import { repairMissingRouterProvider } from './codeMissingRouterProvider.ts'

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

function ensureSpaDomMount(files: CodeFile[], intent: CodeIntent): CodeFile[] {
  if (!intent.projectType.startsWith('spa_')) return files

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasMountingScript = files.some((f) => /\bcreateRoot\s*\(|ReactDOM\.render\s*\(|createApp\s*\(/.test(f.content))

  let nextFiles = [...files]

  if (!hasMountingScript) {
    const isReact = intent.projectType === 'spa_react' || intent.projectType.includes('react')
    if (isReact) {
      nextFiles.push({
        name: 'src/main.tsx',
        language: 'typescript',
        content: [
          "import React from 'react'",
          "import ReactDOM from 'react-dom/client'",
          "import App from './App'",
          "",
          "const rootElement = document.getElementById('root')",
          "if (rootElement) {",
          "  ReactDOM.createRoot(rootElement).render(",
          "    <React.StrictMode>",
          "      <App />",
          "    </React.StrictMode>,",
          "  )",
          "}",
          "",
        ].join('\n'),
      })
    }
  }

  // Ensure index.html references /src/main.tsx or the mounting entry point instead of raw App.tsx
  const indexHtmlIdx = nextFiles.findIndex((f) => /(^|\/)index\.html$/i.test(f.name.replace(/\\/g, '/')))
  if (indexHtmlIdx >= 0) {
    let html = nextFiles[indexHtmlIdx].content
    if (/src=["']\/?src\/App\.(?:tsx|jsx)["']/.test(html) || !/src=["']\/?src\/(?:main|index)\.(?:tsx|jsx)["']/.test(html)) {
      html = html.replace(/<script\b[^>]*src=["'][^"']*App\.(?:tsx|jsx)["'][^>]*>\s*<\/script>/gi, '<script type="module" src="/src/main.tsx"></script>')
      if (!html.includes('/src/main.tsx') && !html.includes('src/main.tsx')) {
        html = html.replace('</body>', '  <script type="module" src="/src/main.tsx"></script>\n</body>')
      }
      nextFiles[indexHtmlIdx] = { ...nextFiles[indexHtmlIdx], content: html }
    }
  }

  return nextFiles
}

function ensureSpaIndexHtml(files: CodeFile[], intent: CodeIntent): CodeFile[] {
  if (!intent.projectType.startsWith('spa_')) return files

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  if (normalizedNames.includes('index.html')) return files

  const entry = [
    'src/main.tsx', 'src/main.jsx', 'src/main.ts', 'src/main.js',
    'src/index.tsx', 'src/index.jsx', 'src/index.ts', 'src/index.js',
    'main.tsx', 'main.jsx', 'main.ts', 'main.js',
    'index.tsx', 'index.jsx', 'index.ts', 'index.js',
  ].find((candidate) => normalizedNames.includes(candidate)) || 'src/main.tsx'

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

function ensureSpaViteManifest(files: CodeFile[], intent: CodeIntent): CodeFile[] {
  if (!intent.projectType.startsWith('spa_')) return files

  const packageIndex = files.findIndex((f) => f.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  if (packageIndex < 0) return files

  const parsed = tryParseJson(stripFormattingArtifacts(files[packageIndex].content))
  if (!parsed || typeof parsed !== 'object') return files

  const manifest = parsed as Record<string, unknown>
  const scripts = (manifest.scripts && typeof manifest.scripts === 'object' ? { ...(manifest.scripts as Record<string, string>) } : {})
  const deps = (manifest.dependencies && typeof manifest.dependencies === 'object' ? { ...(manifest.dependencies as Record<string, string>) } : {})
  const devDeps = (manifest.devDependencies && typeof manifest.devDependencies === 'object' ? { ...(manifest.devDependencies as Record<string, string>) } : {})

  let changed = false
  if (deps['react-scripts'] || (scripts.build && scripts.build.includes('react-scripts'))) {
    delete deps['react-scripts']
    delete deps['@testing-library/jest-dom']
    delete deps['@testing-library/react']
    delete deps['@testing-library/user-event']
    delete deps['@types/jest']
    delete deps['web-vitals']
    if (deps['@types/node']) deps['@types/node'] = '^20.11.0'
    if (devDeps['@types/node']) devDeps['@types/node'] = '^20.11.0'
    if (!devDeps.vite) devDeps.vite = '^5.4.14'
    if (!devDeps['@vitejs/plugin-react']) devDeps['@vitejs/plugin-react'] = '^4.3.4'
    if (!devDeps.typescript && !deps.typescript) devDeps.typescript = '^5.3.3'
    scripts.dev = 'vite'
    scripts.build = 'tsc && vite build'
    scripts.preview = 'vite preview'
    changed = true
  }

  const KNOWN_BUILTINS = new Set(['fs', 'path', 'os', 'child_process', 'crypto', 'http', 'https', 'events', 'stream', 'util', 'url', 'assert'])

  for (const file of files) {
    if (!/\.[cm]?[jt]sx?$/i.test(file.name)) continue
    const matches = file.content.matchAll(/\b(?:import\s+(?:[\w*\s{},]+from\s+)?|from\s+)['"]([^.'"/][^'"]*|@[^'"]+)['"]/g)
    for (const match of matches) {
      const raw = match[1]
      const pkgName = raw.startsWith('@') ? raw.split('/').slice(0, 2).join('/') : raw.split('/')[0]
      if (KNOWN_BUILTINS.has(pkgName) || pkgName.startsWith('node:')) continue
      if (!deps[pkgName] && !devDeps[pkgName]) {
        deps[pkgName] = pkgName === 'react-beautiful-dnd' ? '^13.1.8' : 'latest'
        if (pkgName === 'react-beautiful-dnd' && !devDeps['@types/react-beautiful-dnd']) {
          devDeps['@types/react-beautiful-dnd'] = '^13.1.8'
        }
        changed = true
      }
    }
  }

  if (!changed) return files

  return files.map((file, idx) => (idx === packageIndex ? {
    ...file,
    content: `${JSON.stringify({ ...manifest, scripts, dependencies: deps, devDependencies: devDeps }, null, 2)}\n`,
  } : file))
}

function ensureSpaViteConfig(files: CodeFile[], intent: CodeIntent): CodeFile[] {
  if (!intent.projectType.startsWith('spa_')) return files

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  if (normalizedNames.some((name) => /^vite\.config\.(?:ts|js|mjs|mts)$/.test(name))) return files

  // Le plugin DOIT suivre le framework: on injectait React pour TOUT `spa_*`,
  // rendant tout projet Vue/Svelte inconstruisible alors que son package.json
  // etait correct.
  const PLUGIN: Partial<Record<string, [string, string]>> = {
    spa_react: ['react', '@vitejs/plugin-react'],
    spa_vue: ['vue', '@vitejs/plugin-vue'],
    spa_svelte: ['svelte', '@sveltejs/vite-plugin-svelte'],
  }
  const plugin = PLUGIN[intent.projectType]
  return [
    ...files,
    {
      name: 'vite.config.ts',
      language: 'typescript',
      content: [
        "import { defineConfig } from 'vite'",
        ...(plugin ? [`import ${plugin[0]} from '${plugin[1]}'`] : []),
        '',
        'export default defineConfig({',
        `  plugins: [${plugin ? `${plugin[0]}()` : ''}],`,
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
  const strippedFiles = ensureTailwindCDN(files, intent.projectType, intent).filter((file) => {
    const name = file.name.replace(/\\/g, '/').toLowerCase()
    return name !== 'readme.md' && name !== 'start.sh' && !name.endsWith('.bat')
  })
  const baseFiles = ensureSpaViteConfig(
    ensureSpaViteManifest(
      ensureSpaDomMount(
        ensureSpaIndexHtml(stripSyntheticFallbackFiles(strippedFiles, intent), intent),
        intent,
      ),
      intent,
    ),
    intent,
  )
  // Reprise (.gitignore, .env.example, .nvmrc) AVANT le README, qui inventorie.
  const supportedFiles = upsertProjectScaffoldFiles(ensureTailwindTooling(baseFiles))

  // start.sh doit exister AVANT le README pour que la section "Raccourci Linux/macOS"
  // ne soit ecrite QUE quand le script est reellement livre (elle mentait la moitie du temps).
  const filesWithLaunch = [...supportedFiles]
  const launchScript = generateLinuxLaunchScript(supportedFiles, intent)
  if (launchScript) filesWithLaunch.push(launchScript)
  const readme = generateProjectReadme(filesWithLaunch, intent, prompt, architecturePlan)
  // Reparation DETERMINISTE d une icone de page qui pointe un binaire absent:
  // le gabarit Vite que tout modele recopie ecrit `href="/favicon.ico"`, et ce
  // pipeline n ecrira jamais de `.ico`. Une correction mecanique ne se delegue
  // pas a un modele probabiliste (run 1161).
  // Des routes montees hors de tout routeur ne montent RIEN (run 1181: page
  // vide, acceptation 0/2). Envelopper l arbre est mecanique.
  return repairMissingRouterProvider(repairDanglingIconLinks([...filesWithLaunch, readme])).files
}

export function upsertProjectSupportFilesForTest(
  files: CodeFile[],
  intent: CodeIntent,
  prompt = '',
  architecturePlan: string | null = null,
) {
  return upsertProjectSupportFiles(files, intent, prompt, architecturePlan)
}
