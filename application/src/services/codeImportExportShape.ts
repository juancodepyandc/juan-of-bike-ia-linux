// ---------------------------------------------------------------------------
// codeImportExportShape — la forme de l import doit correspondre a ce que la
// cible exporte VRAIMENT.
//
// BALAYAGE DE CORPUS (42 runs archives, 1187 erreurs TypeScript localisees):
//
//   100x  TS2307  Cannot find module '...'        dont 88 chemins LOCAUX
//    92x  TS2613/TS2614  no exported member / no default export
//
// Les noms cites ne sont pas des paquets npm mais des modules du projet:
// `../components/OrderList`, `../components/ContactForm`, `./Logo`,
// `../store/useOrderStore`... Une seule famille, donc: **l import ne
// correspond pas a ce que la cible exporte**.
//
// Mesure sur les livrables FINAUX (529 imports locaux, 42 runs):
//   61  cible absente (le module n a jamais ete emis)
//    9  import par defaut  / cible n exporte que des noms
//   10  import nomme       / cible n exporte qu un defaut
//  449  coherents
//
// Les 19 desaccords de FORME se reparent sans modele: le graphe se LIT. Ce
// module ne traite que ceux-la, et seulement quand la reponse est unique —
// une cible ambigue est laissee au modele plutot que devinee.
// ---------------------------------------------------------------------------

import type { CodeFile } from './codeOrchestratorTypes.ts'

export type ModuleExports = { named: Set<string>; hasDefault: boolean }

const SOURCE_FILE = /\.(tsx?|jsx?|mjs|cjs)$/i

const normalize = (name: string) => name.replace(/\\/g, '/')

export function readModuleExports(source: string): ModuleExports {
  const named = new Set<string>()
  let hasDefault = /(^|\n)\s*export\s+default\b/.test(source)
  for (const match of source.matchAll(/export\s+(?:async\s+)?(?:const|let|var|function|class|type|interface|enum)\s+([A-Za-z_$][\w$]*)/g)) {
    named.add(match[1])
  }
  for (const match of source.matchAll(/export\s*\{([^}]*)\}/g)) {
    for (const part of match[1].split(',')) {
      const alias = part.trim().split(/\s+as\s+/).pop()?.trim()
      if (!alias) continue
      if (alias === 'default') hasDefault = true
      else named.add(alias)
    }
  }
  return { named, hasDefault }
}

export type ParsedImport = {
  statement: string
  specifier: string
  defaultBinding?: string
  namedBindings: string[]
}

export function readImports(source: string): ParsedImport[] {
  const out: ParsedImport[] = []
  for (const match of source.matchAll(/import\s+(?:type\s+)?([^;'"]+?)\s+from\s*['"]([^'"]+)['"]/g)) {
    const clause = match[1].trim()
    const namedPart = /\{([^}]*)\}/.exec(clause)?.[1]
    const defaultBinding = /^([A-Za-z_$][\w$]*)\s*(?:,|$)/.exec(clause)?.[1]
    const namedBindings = namedPart
      ? namedPart.split(',').map((part) => part.trim().split(/\s+as\s+/)[0].trim()).filter(Boolean)
      : []
    out.push({ statement: match[0], specifier: match[2], defaultBinding, namedBindings })
  }
  return out
}

/** Resolution d un specifier RELATIF contre les fichiers reellement livres. */
export function resolveLocalImport(files: CodeFile[], fromPath: string, specifier: string): string | null {
  if (!specifier.startsWith('.')) return null
  const segments = normalize(fromPath).split('/').slice(0, -1)
  for (const part of specifier.split('/')) {
    if (part === '.' || part === '') continue
    if (part === '..') segments.pop()
    else segments.push(part)
  }
  const base = segments.join('/')
  const candidates = [base, `${base}.ts`, `${base}.tsx`, `${base}.js`, `${base}.jsx`, `${base}/index.ts`, `${base}/index.tsx`]
  for (const candidate of candidates) {
    const hit = files.find((file) => normalize(file.name) === candidate)
    if (hit) return normalize(hit.name)
  }
  return null
}

export type ImportShapeFix = {
  file: string
  specifier: string
  before: string
  after: string
  reason: string
}

/**
 * Ne propose un correctif que lorsque la reponse est UNIQUE. Une cible qui
 * exporte plusieurs noms sans defaut, importee par defaut sous un nom qui ne
 * correspond a aucun d eux, reste au modele: deviner lequel serait une
 * invention, pas une reparation.
 */
export function planImportShapeFixes(files: CodeFile[]): ImportShapeFix[] {
  const fixes: ImportShapeFix[] = []
  const exportsCache = new Map<string, ModuleExports>()
  const exportsFor = (path: string): ModuleExports => {
    const cached = exportsCache.get(path)
    if (cached) return cached
    const source = files.find((file) => normalize(file.name) === path)?.content ?? ''
    const parsed = readModuleExports(source)
    exportsCache.set(path, parsed)
    return parsed
  }

  for (const file of files) {
    if (!SOURCE_FILE.test(file.name)) continue
    for (const parsed of readImports(file.content)) {
      const target = resolveLocalImport(files, file.name, parsed.specifier)
      if (!target) continue
      const targetExports = exportsFor(target)

      // Cas 1 — import par DEFAUT, la cible n exporte que des NOMS.
      if (parsed.defaultBinding && parsed.namedBindings.length === 0 && !targetExports.hasDefault && targetExports.named.size > 0) {
        const exact = targetExports.named.has(parsed.defaultBinding) ? parsed.defaultBinding : null
        const only = targetExports.named.size === 1 ? [...targetExports.named][0] : null
        const pick = exact ?? only
        if (!pick) continue
        const after = parsed.statement.replace(
          parsed.defaultBinding,
          pick === parsed.defaultBinding ? `{ ${pick} }` : `{ ${pick} as ${parsed.defaultBinding} }`,
        )
        fixes.push({
          file: normalize(file.name), specifier: parsed.specifier, before: parsed.statement, after,
          reason: `${target} n a pas d export par defaut; il exporte ${pick}`,
        })
        continue
      }

      // Cas 2 — import NOMME, la cible n expose qu un defaut.
      if (parsed.namedBindings.length === 1 && !parsed.defaultBinding && targetExports.hasDefault) {
        const wanted = parsed.namedBindings[0]
        if (targetExports.named.has(wanted)) continue
        const after = parsed.statement.replace(/\{[^}]*\}/, wanted)
        fixes.push({
          file: normalize(file.name), specifier: parsed.specifier, before: parsed.statement, after,
          reason: `${target} n exporte pas ${wanted}; il expose un export par defaut`,
        })
      }
    }
  }
  return fixes
}

/** Applique les correctifs. Fonction pure. */
export function applyImportShapeFixes(files: CodeFile[], fixes: ImportShapeFix[]): CodeFile[] {
  if (fixes.length === 0) return files
  const byFile = new Map<string, ImportShapeFix[]>()
  for (const fix of fixes) {
    const list = byFile.get(fix.file) ?? []
    list.push(fix)
    byFile.set(fix.file, list)
  }
  return files.map((file) => {
    const list = byFile.get(normalize(file.name))
    if (!list) return file
    let content = file.content
    for (const fix of list) content = content.replace(fix.before, fix.after)
    return { ...file, content }
  })
}

export function describeImportShapeFixes(fixes: ImportShapeFix[]): string {
  return fixes.map((fix) => `${fix.file}: ${fix.reason}`).join(' ; ')
}
