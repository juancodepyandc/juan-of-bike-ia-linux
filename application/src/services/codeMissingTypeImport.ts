// ---------------------------------------------------------------------------
// codeMissingTypeImport — un type utilise mais jamais importe se repare SANS
// modele.
//
// Run 1171, mesure sur le livrable reel (27 fichiers, 9 passes de correction).
// La boucle a oscille sans converger, score 20 -> 65 -> 68 -> 72 -> 73:
//
//   passe 3  AdminPage.tsx  TS2339 Property 'clearOrders' does not exist on
//                                  type 'OrderState'
//            AdminPage.tsx  TS2339 Property 'coffeeName' does not exist on
//                                  type 'Order'
//   passe 5  AdminPage.tsx  TS2304 Cannot find name 'Order'
//
// Le modele alignait l usage sur le type, puis le type sur l usage. A l arrivee,
// `src/pages/AdminPage.tsx` ecrit `Order['status']` a la ligne 146 et n importe
// que `useOrderStore`. Le type `Order` est pourtant EXPORTE par le module qu il
// importe deja (`../store/orderStore`).
//
// Il n y a rien a deviner: le symbole manque, un module du projet l exporte, et
// le fichier importe deja ce module. Ajouter le nom a l import existant est une
// operation mecanique — donc elle ne se delegue pas a un modele probabiliste.
//
// Ce module ne tranche JAMAIS une ambiguite. Le projet du run 1171 declare
// `Order` DEUX fois (`src/types/index.ts` et `src/store/orderStore.ts`): la
// seule raison pour laquelle le choix est sur ici, c est que le fichier importe
// deja l un des deux. Sans ce depart, on ne touche a rien.
// ---------------------------------------------------------------------------

export type TypeImportFile = { name: string; language: string; content: string }

export type MissingTypeImportFix = {
  file: string
  symbol: string
  fromModule: string
  /** `type` pour une interface ou un alias, `value` pour une classe ou un enum. */
  kind: 'type' | 'value'
}

const MISSING_NAME_RE = /^(.+?)\((\d+),\d+\): error TS2304: Cannot find name '([A-Za-z_$][\w$]*)'/gm

function normalize(path: string): string {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '')
}

function stripExtension(path: string): string {
  return normalize(path).replace(/\.(tsx?|jsx?|mts|cts)$/i, '')
}

/** Symboles exportes par chaque module du projet, avec leur nature. */
export function collectExportedSymbols(
  files: TypeImportFile[],
): Map<string, Array<{ module: string; kind: 'type' | 'value' }>> {
  const index = new Map<string, Array<{ module: string; kind: 'type' | 'value' }>>()
  for (const file of files) {
    if (!/\.(tsx?|mts|cts)$/i.test(file.name)) continue
    const re = /^\s*export\s+(?:declare\s+)?(interface|type|class|enum)\s+([A-Za-z_$][\w$]*)/gm
    let match: RegExpExecArray | null
    while ((match = re.exec(file.content)) !== null) {
      const kind = match[1] === 'interface' || match[1] === 'type' ? 'type' : 'value'
      const list = index.get(match[2]) ?? []
      list.push({ module: stripExtension(file.name), kind })
      index.set(match[2], list)
    }
  }
  return index
}

/** Modules dont ce fichier importe deja quelque chose, resolus en chemin projet. */
function importedModulesOf(file: TypeImportFile): Map<string, string> {
  const dir = normalize(file.name).split('/').slice(0, -1).join('/')
  const resolved = new Map<string, string>()
  const re = /\bimport\s+(?:type\s+)?[^'"]*?\bfrom\s*['"](\.[^'"]+)['"]/g
  let match: RegExpExecArray | null
  while ((match = re.exec(file.content)) !== null) {
    const parts: string[] = []
    for (const part of `${dir ? `${dir}/` : ''}${match[1]}`.split('/')) {
      if (!part || part === '.') continue
      if (part === '..') { parts.pop(); continue }
      parts.push(part)
    }
    resolved.set(stripExtension(parts.join('/')), match[1])
  }
  return resolved
}

/**
 * Ajoute `symbol` a l import existant du specificateur donne. Renvoie null si
 * la reecriture n est pas sure (import par defaut seul, namespace, etc.):
 * mieux vaut ne rien faire que produire un fichier bancal.
 */
function addToExistingImport(content: string, specifier: string, symbol: string, kind: 'type' | 'value'): string | null {
  const escaped = specifier.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(`(\\bimport\\s+)(\\{[^}]*\\})(\\s*from\\s*['"]${escaped}['"])`)
  const match = re.exec(content)
  if (!match) return null
  const inner = match[2].slice(1, -1).trim()
  if (new RegExp(`(^|[,{\\s])(type\\s+)?${symbol}\\s*(,|$|\\})`).test(inner)) return null
  const entry = kind === 'type' ? `type ${symbol}` : symbol
  const nextInner = inner.length > 0 ? `${inner}, ${entry}` : entry
  return content.replace(re, `$1{ ${nextInner} }$3`)
}

/**
 * Repare les `TS2304: Cannot find name 'X'` dont la resolution est CERTAINE:
 * le fichier importe deja le module qui exporte X. Aucun autre cas n est
 * traite — une ambiguite se signale, elle ne se devine pas.
 */
export function repairMissingTypeImports(
  files: TypeImportFile[],
  compilerOutput: string,
): { files: TypeImportFile[]; fixes: MissingTypeImportFix[] } {
  const exported = collectExportedSymbols(files)
  const byPath = new Map(files.map((file) => [normalize(file.name), file]))
  const fixes: MissingTypeImportFix[] = []
  const patched = new Map<string, string>()

  MISSING_NAME_RE.lastIndex = 0
  const wanted = new Map<string, Set<string>>()
  let match: RegExpExecArray | null
  while ((match = MISSING_NAME_RE.exec(compilerOutput)) !== null) {
    const path = normalize(match[1].trim())
    ;(wanted.get(path) ?? wanted.set(path, new Set()).get(path)!).add(match[3])
  }

  for (const [path, symbols] of wanted) {
    const file = byPath.get(path)
    if (!file) continue
    let content = patched.get(path) ?? file.content
    const alreadyImported = importedModulesOf(file)

    for (const symbol of symbols) {
      const candidates = exported.get(symbol) ?? []
      if (candidates.length === 0) continue
      // Le SEUL cas sur: le fichier importe deja un module qui exporte ce nom.
      const hit = candidates.find((candidate) => alreadyImported.has(candidate.module))
      if (!hit) continue
      const specifier = alreadyImported.get(hit.module)!
      const next = addToExistingImport(content, specifier, symbol, hit.kind)
      if (!next) continue
      content = next
      fixes.push({ file: file.name, symbol, fromModule: hit.module, kind: hit.kind })
    }

    if (content !== file.content) patched.set(path, content)
  }

  if (fixes.length === 0) return { files, fixes }
  return {
    files: files.map((file) => {
      const next = patched.get(normalize(file.name))
      return next ? { ...file, content: next } : file
    }),
    fixes,
  }
}

/** Resume lisible, pour que la reparation ne soit jamais silencieuse. */
export function describeMissingTypeImportFixes(fixes: MissingTypeImportFix[]): string {
  return fixes
    .map((fix) => `${fix.file}: import de ${fix.symbol} depuis ${fix.fromModule}`)
    .join(' — ')
}
