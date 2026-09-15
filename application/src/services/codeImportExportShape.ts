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

/**
 * Neutralise commentaires et litteraux de chaine, EN CONSERVANT les offsets.
 *
 * Les analyses d'imports et d'exports balayaient la source brute a coups
 * d'expressions regulieres. Elles voyaient donc :
 *
 *     // import Faux from 'faux'          -> import fantome
 *     /* import Bidon from 'bidon' *SLASH -> import fantome
 *     const s = "import Chaine from 'x'"  -> import fantome
 *
 * Mesure : sur un fichier portant trois leurres et un seul vrai import,
 * `readImports` en rendait QUATRE. La consequence n'est pas cosmetique :
 * `planImportShapeFixes` compare ce qu'un module importe a ce que la cible
 * exporte, puis REECRIT le code. Un export apercu dans un commentaire fait
 * croire a un nom disponible, et la reparation transforme un import valide
 * en import d'un symbole qui n'existe pas — du code livre qui ne compile plus.
 *
 * On remplace le contenu neutralise par des espaces de MEME LONGUEUR, en
 * gardant les sauts de ligne : les positions restent valides, donc les
 * fragments extraits correspondent toujours au texte d'origine.
 */
export function maskNonCode(source: string): string {
  const out = source.split('')
  const n = source.length
  const blanchir = (from: number, to: number) => {
    for (let k = from; k < to && k < n; k += 1) {
      if (out[k] !== '\n' && out[k] !== '\r') out[k] = ' '
    }
  }

  // Automate a pile : les gabarits peuvent s'imbriquer via `${ ... }`, et
  // l'interieur d'une interpolation est du VRAI code, qu'il faut continuer a
  // analyser. Une premiere version traitait le gabarit comme une chaine
  // ordinaire ; le backtick FERMANT etait alors pris pour l'ouverture d'une
  // nouvelle chaine, et tout le reste du fichier passait en blanc — les
  // imports situes plus bas disparaissaient. La pile evite cela.
  const pileGabarits: number[] = [] // profondeur d'accolades par gabarit ouvert
  let i = 0
  while (i < n) {
    const c = source[i]
    const suivant = source[i + 1]

    // Dans une interpolation : on suit les accolades pour savoir quand elle
    // se referme et que le gabarit reprend.
    if (pileGabarits.length > 0) {
      const haut = pileGabarits.length - 1
      if (c === '{') { pileGabarits[haut] += 1; i += 1; continue }
      if (c === '}') {
        pileGabarits[haut] -= 1
        if (pileGabarits[haut] === 0) {
          pileGabarits.pop()
          // Reprise de la partie litterale du gabarit.
          i = masqueCorpsGabarit(i + 1)
          continue
        }
        i += 1
        continue
      }
    }

    if (c === '/' && suivant === '/') {
      let j = i + 2
      while (j < n && source[j] !== '\n') j += 1
      blanchir(i, j)
      i = j
      continue
    }
    if (c === '/' && suivant === '*') {
      let j = i + 2
      while (j < n && !(source[j] === '*' && source[j + 1] === '/')) j += 1
      const stop = Math.min(j + 2, n)
      blanchir(i, stop)
      i = stop
      continue
    }
    if (c === '"' || c === "'") {
      let j = i + 1
      while (j < n) {
        if (source[j] === '\\') { j += 2; continue }
        if (source[j] === c) break
        if (source[j] === '\n') break // chaine non fermee : on s'arrete a la ligne
        j += 1
      }
      blanchir(i + 1, j)
      i = Math.min(j + 1, n)
      continue
    }
    if (c === '`') {
      i = masqueCorpsGabarit(i + 1)
      continue
    }
    i += 1
  }

  /**
   * Blanchit la partie litterale d'un gabarit a partir de `depart` et rend la
   * position ou l'analyse doit reprendre : soit apres le backtick fermant,
   * soit au debut d'une interpolation (dont le contenu reste du code).
   */
  function masqueCorpsGabarit(depart: number): number {
    let j = depart
    while (j < n) {
      if (source[j] === '\\') { j += 2; continue }
      if (source[j] === '`') { blanchir(depart, j); return j + 1 }
      if (source[j] === '$' && source[j + 1] === '{') {
        blanchir(depart, j)
        pileGabarits.push(1)
        return j + 2
      }
      j += 1
    }
    blanchir(depart, n)
    return n
  }

  return out.join('')
}

export function readModuleExports(rawSource: string): ModuleExports {
  const source = maskNonCode(rawSource)
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

export function readImports(rawSource: string): ParsedImport[] {
  // Le specifier vit ENTRE GUILLEMETS : on le lit donc sur la source
  // d'origine, aux positions rendues par le balayage du texte masque.
  const masked = maskNonCode(rawSource)
  const out: ParsedImport[] = []
  for (const match of masked.matchAll(/import\s+(?:type\s+)?([^;'"]+?)\s+from\s*['"]([^'"]*)['"]/g)) {
    const debut = match.index ?? 0
    const statement = rawSource.slice(debut, debut + match[0].length)
    const specifier = /from\s*['"]([^'"]+)['"]/.exec(statement)?.[1]
    if (!specifier) continue
    const clause = match[1].trim()
    const namedPart = /\{([^}]*)\}/.exec(clause)?.[1]
    const defaultBinding = /^([A-Za-z_$][\w$]*)\s*(?:,|$)/.exec(clause)?.[1]
    const namedBindings = namedPart
      ? namedPart.split(',').map((part) => part.trim().split(/\s+as\s+/)[0].trim()).filter(Boolean)
      : []
    out.push({ statement, specifier, defaultBinding, namedBindings })
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

export type DirectoryIndexFix = {
  /** Chemin de l index a creer, ex. `src/components/AdminDashboard/index.ts`. */
  path: string
  /** Module reexporte, ex. `./AdminDashboard`. */
  target: string
  hasDefault: boolean
  named: string[]
}

/**
 * Le module-REPERTOIRE sans index.
 *
 * MESURE (run v129, 20 occurrences sur un seul import):
 *   AppRoutes.tsx : import AdminDashboard from '../components/AdminDashboard'
 *   livre         : src/components/AdminDashboard/AdminDashboard.tsx
 *
 * Le modele ecrit `components/Foo/Foo.tsx` puis importe `components/Foo`. Sans
 * `index`, rien ne resout — et le compilateur repete TS2307 a chaque passe.
 *
 * On ne reecrit PAS l importateur: on cree l index manquant. Un seul fichier
 * repare tous les importateurs du repertoire d un coup, et personne ne voit son
 * code modifie. Deterministe: la cible est choisie sans ambiguite ou pas du
 * tout — fichier homonyme du repertoire, sinon fichier source unique.
 */
export function planDirectoryModuleIndexes(files: CodeFile[]): DirectoryIndexFix[] {
  const paths = files.map((file) => normalize(file.name))
  const existing = new Set(paths)
  const fixes = new Map<string, DirectoryIndexFix>()

  for (const file of files) {
    if (!SOURCE_FILE.test(file.name)) continue
    for (const parsed of readImports(file.content)) {
      if (!parsed.specifier.startsWith('.')) continue
      if (resolveLocalImport(files, file.name, parsed.specifier)) continue

      const segments = normalize(file.name).split('/').slice(0, -1)
      for (const part of parsed.specifier.split('/')) {
        if (part === '.' || part === '') continue
        if (part === '..') segments.pop()
        else segments.push(part)
      }
      const dir = segments.join('/')
      if (!dir || fixes.has(dir)) continue
      // Le specifier designe-t-il un REPERTOIRE reellement livre ?
      const inside = paths.filter((p) => p.startsWith(`${dir}/`) && SOURCE_FILE.test(p))
      if (inside.length === 0) continue
      if (existing.has(`${dir}/index.ts`) || existing.has(`${dir}/index.tsx`)) continue

      const base = dir.split('/').pop() ?? ''
      const homonym = inside.find((p) => p.split('/').pop()?.replace(/\.[^.]+$/, '') === base)
      const target = homonym ?? (inside.length === 1 ? inside[0] : null)
      if (!target) continue

      const source = files.find((f) => normalize(f.name) === target)?.content ?? ''
      const exports = readModuleExports(source)
      fixes.set(dir, {
        path: `${dir}/index.ts`,
        target: `./${target.split('/').pop()?.replace(/\.[^.]+$/, '')}`,
        hasDefault: exports.hasDefault,
        named: [...exports.named],
      })
    }
  }
  return [...fixes.values()]
}

/** Cree les index manquants. Fonction pure — aucun fichier existant modifie. */
export function applyDirectoryModuleIndexes(files: CodeFile[], fixes: DirectoryIndexFix[]): CodeFile[] {
  if (fixes.length === 0) return files
  const created = fixes.map((fix) => {
    const lines: string[] = []
    if (fix.hasDefault) lines.push(`export { default } from '${fix.target}'`)
    if (fix.named.length > 0) lines.push(`export { ${fix.named.join(', ')} } from '${fix.target}'`)
    if (lines.length === 0) lines.push(`export * from '${fix.target}'`)
    return { name: fix.path, language: 'typescript', content: `${lines.join('\n')}\n` }
  })
  return [...files, ...created]
}
