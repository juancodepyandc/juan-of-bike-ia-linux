// ---------------------------------------------------------------------------
// codeTailwindUsage — source unique de verite sur « ce projet utilise-t-il
// Tailwind, et est-il outille pour ? »
//
// La detection vivait en double intention: la PORTE savait accuser, mais rien
// ne savait REPARER. Mesure sur le livrable du run v126:
//
//   12x  [error] projet - Classes Tailwind detectees sans configuration
//                Tailwind (8 utilities, ex: container...)
//
// Douze fois le meme reproche, zero fois le fichier manquant. Meme famille que
// l outillage de test deja ferme: si la file emet des classes Tailwind, elle
// doit emettre de quoi les COMPILER. Un reproche repete douze fois qui ne
// s accompagne pas du correctif est un conseil inachevable de plus.
// ---------------------------------------------------------------------------

import type { CodeFile } from './codeOrchestratorTypes.ts'

const VARIANT_PREFIX = /^(?:sm|md|lg|xl|2xl|dark|hover|focus|active|disabled|group-hover|motion-safe|motion-reduce):/g

const UTILITY_SHAPE = /^(?:container|sr-only|flex|inline-flex|grid|hidden|block|relative|absolute|fixed|sticky|inset-|top-|right-|bottom-|left-|z-\d+|min-h-|max-w-|w-(?:\d|full|screen)|h-(?:\d|full|screen)|p[trblxy]?-\d+|m[trblxy]?-\d+|mx-auto|gap-\d+|space-[xy]-\d+|items-|justify-|content-|rounded(?:-|$)|border(?:-|$)|shadow(?:-|$)|bg-|text-|font-|leading-|tracking-|opacity-|transition|duration-|ease-|overflow-|object-|aspect-|scale-|translate-|rotate-|transform|from-|via-|to-|backdrop-|dark:bg-|dark:text-|dark:border-)/

/** Seuil partage entre la porte qui accuse et la reparation qui livre. */
export const TAILWIND_UTILITY_THRESHOLD = 8

export function extractClassTokens(content: string): string[] {
  const tokens: string[] = []
  const classAttr = /\bclass(?:Name)?\s*=\s*["']([^"']+)["']/g
  let match: RegExpExecArray | null
  while ((match = classAttr.exec(content)) !== null) {
    tokens.push(...match[1].split(/\s+/).filter(Boolean))
  }
  return tokens
}

export function isLikelyTailwindUtility(token: string): boolean {
  return UTILITY_SHAPE.test(token.replace(VARIANT_PREFIX, ''))
}

const MARKUP_FILE = /\.(tsx|jsx|html?|vue|svelte)$/i

export function countTailwindUtilities(files: CodeFile[]): { count: number; examples: string[] } {
  const examples = new Set<string>()
  let count = 0
  for (const file of files) {
    if (!MARKUP_FILE.test(file.name)) continue
    for (const token of extractClassTokens(file.content)) {
      if (!isLikelyTailwindUtility(token)) continue
      count += 1
      if (examples.size < 6) examples.add(token)
    }
  }
  return { count, examples: [...examples] }
}

/**
 * Trois etats, jamais deux: un manifeste illisible n est PAS « pas de
 * Tailwind ». Une porte qui n a pas pu lire ne condamne pas.
 */
export type TailwindSetupState = 'configured' | 'absent' | 'unreadable'

const normalizedName = (name: string) => name.replace(/\\/g, '/').toLowerCase()

export function findTailwindStylesheet(files: CodeFile[]): CodeFile | null {
  const css = files.filter((file) => /\.(css|scss)$/i.test(file.name))
  if (css.length === 0) return null
  // La feuille d entree: celle qui est importee par le code, sinon la plus
  // proche de la racine, sinon la plus grosse. Deterministe dans tous les cas.
  const imported = css.find((file) => {
    const base = normalizedName(file.name)
    return files.some((other) => other !== file && other.content.includes(base.split('/').pop() || ''))
  })
  if (imported) return imported
  return [...css].sort((a, b) => normalizedName(a.name).split('/').length - normalizedName(b.name).split('/').length)[0]
}

export function detectTailwindSetup(files: CodeFile[]): TailwindSetupState {
  const paths = files.map((file) => normalizedName(file.name))
  if (paths.some((p) => /(^|\/)(tailwind\.config\.(?:js|cjs|mjs|ts))$/.test(p))) return 'configured'
  if (files.some((file) => /cdn\.tailwindcss\.com/i.test(file.content))) return 'configured'

  const packageFile = files.find((file) => normalizedName(file.name) === 'package.json')
  if (!packageFile) return 'absent'
  try {
    const manifest = JSON.parse(packageFile.content) as {
      dependencies?: Record<string, unknown>
      devDependencies?: Record<string, unknown>
    }
    return manifest.dependencies?.tailwindcss || manifest.devDependencies?.tailwindcss ? 'configured' : 'absent'
  } catch {
    return 'unreadable'
  }
}

/** Les directives sont-elles deja presentes dans une feuille de style ? */
export function hasTailwindDirectives(files: CodeFile[]): boolean {
  return files.some((file) => /\.(css|scss)$/i.test(file.name) && /@tailwind\s+(?:base|components|utilities)\b/.test(file.content))
}
