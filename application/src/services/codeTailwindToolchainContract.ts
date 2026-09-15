// ---------------------------------------------------------------------------
// codeTailwindToolchainContract — la file emet des classes Tailwind, elle emet
// leur outillage.
//
// Strictement le miroir de codeTestToolchainContract: « la file emet des tests,
// elle emet leur outillage ». Mesure du run v126, sur le livrable reel:
//
//   12x  [error] Classes Tailwind detectees sans configuration Tailwind
//                (8 utilities, ex: container...)
//   fichiers de style emis: src/styles/global.css   (aucune directive)
//   tailwind.config.*  ABSENT      postcss.config.*  ABSENT
//
// Douze fois le meme reproche, jamais le fichier manquant. La reparation est
// entierement DETERMINISTE — les quatre fichiers sont connus d avance — donc
// elle ne passe pas par un modele probabiliste.
//
// Prudence deliberee: on ne touche a rien si le projet est deja outille, si le
// manifeste est illisible (on ne sait pas), ou si Tailwind vient d un CDN.
// ---------------------------------------------------------------------------

import type { CodeFile } from './codeOrchestratorTypes.ts'
import {
  TAILWIND_UTILITY_THRESHOLD,
  countTailwindUtilities,
  detectTailwindSetup,
  findTailwindStylesheet,
  hasTailwindDirectives,
} from './codeTailwindUsage.ts'

export type TailwindToolchainFix = {
  addFiles: CodeFile[]
  /** Feuille de style a prefixer des directives, si elle existe deja. */
  stylesheetToPrefix: string | null
  addDevDependencies: Record<string, string>
  notes: string[]
}

const TAILWIND_CONFIG = `/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx,vue,svelte}'],
  theme: { extend: {} },
  plugins: [],
}
`

const POSTCSS_CONFIG = `export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
`

const DIRECTIVES = '@tailwind base;\n@tailwind components;\n@tailwind utilities;\n'

const DEV_DEPENDENCIES: Record<string, string> = {
  tailwindcss: '^3.4.17',
  postcss: '^8.4.49',
  autoprefixer: '^10.4.20',
}

const normalizedName = (name: string) => name.replace(/\\/g, '/').toLowerCase()

/**
 * Ne propose rien si aucune classe Tailwind n est emise, si le projet est deja
 * outille, ou si le manifeste est illisible.
 */
export function planTailwindToolchainFix(files: CodeFile[]): TailwindToolchainFix | null {
  const usage = countTailwindUtilities(files)
  if (usage.count < TAILWIND_UTILITY_THRESHOLD) return null

  const setup = detectTailwindSetup(files)
  // « unreadable »: on n a pas pu lire le manifeste. On ne repare pas a
  // l aveugle — le JSON invalide est signale ailleurs, et c est LUI le defaut.
  if (setup !== 'absent') return null

  const paths = files.map((file) => normalizedName(file.name))
  const addFiles: CodeFile[] = []
  const notes: string[] = []

  if (!paths.some((p) => /(^|\/)tailwind\.config\./.test(p))) {
    addFiles.push({ name: 'tailwind.config.js', language: 'javascript', content: TAILWIND_CONFIG })
    notes.push('tailwind.config.js ajoute (sans lui aucune classe n est compilee)')
  }
  if (!paths.some((p) => /(^|\/)postcss\.config\./.test(p))) {
    addFiles.push({ name: 'postcss.config.js', language: 'javascript', content: POSTCSS_CONFIG })
    notes.push('postcss.config.js ajoute (Tailwind est un plugin PostCSS)')
  }

  let stylesheetToPrefix: string | null = null
  if (!hasTailwindDirectives(files)) {
    const sheet = findTailwindStylesheet(files)
    if (sheet) {
      stylesheetToPrefix = sheet.name
      notes.push(`directives @tailwind ajoutees en tete de ${sheet.name}`)
    } else {
      addFiles.push({ name: 'src/index.css', language: 'css', content: DIRECTIVES })
      notes.push('src/index.css cree avec les directives @tailwind (aucune feuille de style emise)')
    }
  }

  const addDevDependencies: Record<string, string> = {}
  const packageFile = files.find((file) => normalizedName(file.name) === 'package.json')
  if (packageFile) {
    try {
      const manifest = JSON.parse(packageFile.content) as Record<string, unknown>
      const dev = (manifest.devDependencies && typeof manifest.devDependencies === 'object' ? manifest.devDependencies : {}) as Record<string, unknown>
      const prod = (manifest.dependencies && typeof manifest.dependencies === 'object' ? manifest.dependencies : {}) as Record<string, unknown>
      for (const [name, spec] of Object.entries(DEV_DEPENDENCIES)) {
        if (!(name in dev) && !(name in prod)) addDevDependencies[name] = spec
      }
      if (Object.keys(addDevDependencies).length > 0) {
        notes.push(`devDependencies: ${Object.keys(addDevDependencies).join(', ')}`)
      }
    } catch {
      return null
    }
  }

  if (addFiles.length === 0 && !stylesheetToPrefix && Object.keys(addDevDependencies).length === 0) return null
  return { addFiles, stylesheetToPrefix, addDevDependencies, notes }
}

/**
 * Injecte proprement les directives Tailwind dans une feuille de style existante.
 * Selon la spec CSS et PostCSS, les regles @import (ou @charset) DOIVENT
 * preceder toutes les autres declarations (@tailwind base inclus).
 * De plus, les imports locaux fictifs (ex: 'design-spec/tokens.css') qui
 * n'existent pas sur disque sont filtres pour eviter tout crash de build.
 */
export function injectTailwindDirectivesIntoCss(content: string, existingPaths?: Set<string>): string {
  if (content.includes('@tailwind base')) return content

  const lines = content.split('\n')
  const importLines: string[] = []
  const restLines: string[] = []
  let inLeadingImports = true

  for (const line of lines) {
    const trimmed = line.trim()
    if (inLeadingImports && (trimmed.startsWith('@charset') || trimmed.startsWith('@import') || trimmed === '')) {
      if (trimmed.startsWith('@import')) {
        const match = /@import\s+['"]([^'"]+)['"]/.exec(trimmed)
        if (match) {
          const target = match[1].toLowerCase()
          // Ignorer les imports locaux fictifs inexistants
          if (!target.startsWith('http') && !target.startsWith('//') && existingPaths && !existingPaths.has(target)) {
            continue
          }
        }
        importLines.push(line)
      } else if (trimmed !== '') {
        importLines.push(line)
      }
    } else {
      inLeadingImports = false
      if (trimmed.includes('design-spec/tokens.css')) continue
      restLines.push(line)
    }
  }

  const importBlock = importLines.length > 0 ? `${importLines.join('\n')}\n\n` : ''
  const restBlock = restLines.join('\n').trimStart()
  return `${importBlock}${DIRECTIVES}\n${restBlock}`
}

/** Applique le plan. Fonction pure — on complete, on ne redecide jamais. */
export function applyTailwindToolchainFix(files: CodeFile[], fix: TailwindToolchainFix): CodeFile[] {
  const existingPaths = new Set(files.map((f) => normalizedName(f.name)))
  const next = files.map((file) => {
    if (fix.stylesheetToPrefix && file.name === fix.stylesheetToPrefix) {
      return { ...file, content: injectTailwindDirectivesIntoCss(file.content, existingPaths) }
    }
    if (normalizedName(file.name) === 'package.json' && Object.keys(fix.addDevDependencies).length > 0) {
      try {
        const manifest = JSON.parse(file.content) as Record<string, unknown>
        const dev = manifest.devDependencies && typeof manifest.devDependencies === 'object' && !Array.isArray(manifest.devDependencies)
          ? { ...(manifest.devDependencies as Record<string, unknown>) }
          : {}
        for (const [name, spec] of Object.entries(fix.addDevDependencies)) {
          if (!(name in dev)) dev[name] = spec
        }
        return { ...file, content: `${JSON.stringify({ ...manifest, devDependencies: dev }, null, 2)}\n` }
      } catch {
        return file
      }
    }
    return file
  })
  return [...next, ...fix.addFiles]
}

