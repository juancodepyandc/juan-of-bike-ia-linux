import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import { manifestUsesPackage, stripFormattingArtifacts, tryParseJson, upsertPackageDevDependency } from './codeGeneratedFileSanitizer.ts'
import { getGeneratedNodeDependencySpec } from './codeGeneratedDependencyPolicy.ts'

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

export function ensureTailwindCDN(files: CodeFile[], projectType?: string, intent?: CodeIntent): CodeFile[] {
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

export function ensureTailwindTooling(files: CodeFile[]) {
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
