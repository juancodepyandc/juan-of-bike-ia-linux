import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import {
  manifestUsesPackage,
  stripFormattingArtifacts,
  tryParseJson,
  upsertPackageDevDependency,
} from './codeGeneratedFileSanitizer.ts'
import { getGeneratedNodeDependencySpec } from './codeGeneratedDependencyPolicy.ts'
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

/**
 * Some local models spray Tailwind utility
 * classes (flex, grid, text-5xl, bg-…) WITHOUT including Tailwind and without
 * generating the matching CSS → an unstyled BLACK page. If an HTML file uses
 * Tailwind utilities but ships no Tailwind, inject the Play CDN + a dark-mode
 * config so the page actually renders. No-op when the model wrote real CSS or
 * already included Tailwind.
 */
// Convertit un hex (#rrggbb ou #rgb) en triplet "r g b" pour les CSS variables
// rgb(var(--c-accent) / <alpha>). Retourne null si non parsable.
function hexToRgbTriplet(hex: string | null | undefined): string | null {
  if (!hex) return null
  let h = hex.trim().replace(/^#/, '')
  if (/^[0-9a-fA-F]{3}$/.test(h)) h = h.split('').map((c) => c + c).join('')
  if (!/^[0-9a-fA-F]{6}$/.test(h)) return null
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `${r} ${g} ${b}`
}

// Mélange un triplet "r g b" vers le blanc (t=0..1) pour dériver les variantes
// claires (accent-soft, accents en thème sombre).
function lightenTriplet(triplet: string, t: number): string {
  const [r, g, b] = triplet.split(' ').map(Number)
  const mix = (c: number) => Math.round(c + (255 - c) * t)
  return `${mix(r)} ${mix(g)} ${mix(b)}`
}

// Accent du theme injecte: couleur de MARQUE si detectee (Apple/AirPods -> pas
// de violet generique), sinon un neutre professionnel (bleu ardoise) — jamais
// le violet-signature "template IA" qui trahissait toutes les generations.
function resolveThemeAccent(intent?: CodeIntent): { accent: string; soft: string; accentDark: string; softDark: string } {
  const subject = intent?.assetPlan?.subject
  const brandProfile = (subject?.source === 'brand' || subject?.source === 'inferred_brand')
    ? subject.brandProfile
    : null
  const brandTriplet = hexToRgbTriplet(brandProfile?.primaryColor)
  const accent = brandTriplet ?? '37 99 235' // neutre pro (#2563eb), pas de violet par defaut
  return {
    accent,
    soft: lightenTriplet(accent, 0.12),
    accentDark: lightenTriplet(accent, 0.18),
    softDark: lightenTriplet(accent, 0.32),
  }
}

function ensureTailwindCDN(files: CodeFile[], projectType?: string, intent?: CodeIntent): CodeFile[] {
  // Un jeu canvas est auto-style: Tailwind n y sert a rien.
  if (projectType === 'game_web') return files
  // v92: `flex`, `grid`, `hidden`, `container` sont des noms de classe
  // SEMANTIQUES courants. Les garder dans le declencheur faisait injecter
  // Tailwind dans des pages auto-stylees, et son Preflight remettait `h1` a
  // `font-size: inherit` — la landing Mercedes sortait son titre en 18 px.
  // On ne declenche donc que sur du vocabulaire sans ambiguite.
  const TW_UTIL = /class="[^"]*\b(mx-auto|justify-\w+|items-\w+|text-(xs|sm|base|lg|xl|\dxl|fg|accent)|bg-(surface|card|line|fg|accent)(-\w+)?|[pm][xytblr]?-\d|gap-\d|rounded-\w+|shadow-\w+|font-(bold|semibold|medium)|grid-cols-\d|(sm|md|lg|xl):[a-z-]+)\b/
  const HAS_TW = /cdn\.tailwindcss\.com|@tailwind\b/
  // v85g : les modeles locaux emploient des tokens Tailwind SEMANTIQUES
  // (bg-surface, text-fg, bg-accent…) qui n existent que si une config les
  // definit. On injecte donc le CDN + un theme en variables CSS + cette config.
  const { accent, soft, accentDark, softDark } = resolveThemeAccent(intent)
  const inject = [
    '<style data-aurora-theme>',
    `:root{--c-surface:255 255 255;--c-surface-elevated:248 247 245;--c-card:255 255 255;--c-fg:23 23 23;--c-fg-dim:90 92 100;--c-fg-mute:140 142 150;--c-line:230 230 234;--c-accent:${accent};--c-accent-soft:${soft}}`,
    `[data-theme="dark"],.dark{--c-surface:12 11 16;--c-surface-elevated:24 24 30;--c-card:22 22 28;--c-fg:240 240 245;--c-fg-dim:170 172 180;--c-fg-mute:120 122 130;--c-line:42 42 50;--c-accent:${accentDark};--c-accent-soft:${softDark}}`,
    `@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--c-surface:12 11 16;--c-surface-elevated:24 24 30;--c-card:22 22 28;--c-fg:240 240 245;--c-fg-dim:170 172 180;--c-fg-mute:120 122 130;--c-line:42 42 50;--c-accent:${accentDark};--c-accent-soft:${softDark}}}`,
    'body{background:rgb(var(--c-surface));color:rgb(var(--c-fg));transition:background .3s ease,color .3s ease}',
    '</style>',
    '<script src="https://cdn.tailwindcss.com"></script>',
    '<script>tailwind.config={corePlugins:{preflight:false},darkMode:["selector",\'[data-theme="dark"]\'],theme:{extend:{colors:{'
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
    // La page apporte deja sa propre feuille de style: elle est auto-stylee, on
    // n a rien a lui imposer. Injecter ici revient a ecraser son design.
    if (/<link[^>]+rel=["']?stylesheet/i.test(c) && !/\b(bg-surface|text-fg|bg-accent|shadow-2)\b/.test(c)) return f
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
    'src/main.tsx', 'src/main.jsx', 'src/main.ts', 'src/main.js',
    'src/index.tsx', 'src/index.jsx', 'src/index.ts', 'src/index.js',
    'main.tsx', 'main.jsx', 'main.ts', 'main.js',
    'index.tsx', 'index.jsx', 'index.ts', 'index.js',
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
  const strippedFiles = ensureTailwindCDN(files, intent.projectType, intent).filter((file) => {
    const name = file.name.replace(/\\/g, '/').toLowerCase()
    return name !== 'readme.md' && name !== 'start.sh' && !name.endsWith('.bat')
  })
  const baseFiles = ensureSpaViteConfig(
    ensureSpaIndexHtml(stripSyntheticFallbackFiles(strippedFiles, intent), intent),
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
