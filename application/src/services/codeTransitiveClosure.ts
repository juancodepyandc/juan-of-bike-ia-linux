// ---------------------------------------------------------------------------
// codeTransitiveClosure — le fichier qui PLANTE n est pas le fichier a REPARER.
//
// Deux mesures, deux runs, meme forme. Elles ont ete signalees separement et
// laissees ouvertes deux fois; c est le meme defaut.
//
// 1. CONTRAT DE TYPES REPARTI (run 1171, neuf passes)
//
//      passe 3  AdminPage.tsx TS2339 Property 'clearOrders' does not exist
//                                    on type 'OrderState'      score 68
//      passe 5  AdminPage.tsx TS2304 Cannot find name 'Order'   score 68
//
//    `Order` etait declare DEUX fois (src/types/index.ts et
//    src/store/orderStore.ts). Le modele alignait l usage sur le type, puis, la
//    passe suivante, le type sur l usage. Il ne voyait jamais les deux cotes
//    ensemble, donc ne pouvait pas trancher.
//
// 2. ARBRE DE MONTAGE REACT (run 1181)
//
//      la trace nommait src/routes/AppRoutes.tsx
//      la cause vivait dans src/main.tsx — aucun routeur monte nulle part
//
//    La passe ciblee a corrige le fichier NOMME par la trace, sans effet.
//
// Dans les deux cas la passe recevait UN fichier — celui que l erreur nomme —
// et devait prendre une decision qui engage plusieurs fichiers. Aucune quantite
// de passes supplementaires ne repare cela: c est une information absente, pas
// un manque d essais.
//
// Ce module calcule la fermeture: le fichier fautif, PLUS les modules qui
// declarent les symboles en cause, PLUS ceux qui les consomment. La passe voit
// alors le contrat entier et peut le rendre coherent d un seul geste.
//
// Deterministe de bout en bout: les imports et les exports se lisent, ils ne se
// devinent pas. Rien ici n est confie a un modele.
// ---------------------------------------------------------------------------

import type { CodeFile } from './codeSandboxTypes.ts'

const IMPORT_RE = /(?:^|\n)\s*import\s+(?:type\s+)?(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]/g
const EXPORT_FROM_RE = /(?:^|\n)\s*export\s+(?:type\s+)?(?:\*|\{[^}]*\})\s+from\s+['"]([^'"]+)['"]/g

/** Nom de fichier normalise: separateurs unix, sans `./` de tete. */
export function normalizePath(name: string): string {
  return name.replace(/\\/g, '/').replace(/^\.\//, '')
}

const CANDIDATE_SUFFIXES = ['', '.ts', '.tsx', '.js', '.jsx', '/index.ts', '/index.tsx', '/index.js', '/index.jsx']

/**
 * Resout un specificateur RELATIF vers un fichier du projet.
 *
 * Les specificateurs nus (`react`, `zustand`) sont des dependances externes:
 * ils ne font pas partie de la fermeture, on ne peut pas les reparer.
 */
export function resolveImport(fromFile: string, specifier: string, files: CodeFile[]): string | null {
  if (!specifier.startsWith('.')) return null
  const fromDir = normalizePath(fromFile).split('/').slice(0, -1)
  const parts = specifier.split('/')
  const stack = [...fromDir]
  for (const part of parts) {
    if (part === '.' || part === '') continue
    if (part === '..') stack.pop()
    else stack.push(part)
  }
  const base = stack.join('/')
  const index = new Map(files.map((file) => [normalizePath(file.name), file.name]))
  for (const suffix of CANDIDATE_SUFFIXES) {
    const hit = index.get(`${base}${suffix}`)
    if (hit) return hit
  }
  return null
}

export type ModuleGraph = {
  /** fichier -> fichiers du projet qu il importe */
  imports: Map<string, Set<string>>
  /** fichier -> fichiers du projet qui l importent */
  importedBy: Map<string, Set<string>>
}

export function buildModuleGraph(files: CodeFile[]): ModuleGraph {
  const imports = new Map<string, Set<string>>()
  const importedBy = new Map<string, Set<string>>()
  for (const file of files) {
    imports.set(file.name, new Set())
    importedBy.set(file.name, new Set())
  }
  for (const file of files) {
    if (!/\.(?:[cm]?[jt]sx?)$/i.test(file.name)) continue
    for (const regex of [IMPORT_RE, EXPORT_FROM_RE]) {
      regex.lastIndex = 0
      for (const match of file.content.matchAll(regex)) {
        const resolved = resolveImport(file.name, match[1], files)
        if (!resolved || resolved === file.name) continue
        imports.get(file.name)?.add(resolved)
        importedBy.get(resolved)?.add(file.name)
      }
    }
  }
  return { imports, importedBy }
}

/** Le fichier exporte-t-il ce symbole ? Lecture, pas deduction. */
export function exportsSymbol(content: string, symbol: string): boolean {
  const escaped = symbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(
    `export\\s+(?:declare\\s+)?(?:default\\s+)?(?:abstract\\s+)?`
    + `(?:type|interface|class|function|const|let|var|enum)\\s+${escaped}\\b`
    + `|export\\s*\\{[^}]*\\b${escaped}\\b[^}]*\\}`,
    'm',
  ).test(content)
}

/**
 * Symboles nommes par les erreurs de compilation.
 *
 * On ne retient que ce que le compilateur cite explicitement entre
 * apostrophes: inventer des symboles elargirait la fermeture au hasard, et une
 * portee trop large est une regeneration deguisee.
 */
export function symbolsFromErrors(errors: string): string[] {
  const found = new Set<string>()
  for (const match of errors.matchAll(/'([A-Za-z_$][\w$]*)'/g)) found.add(match[1])
  return [...found]
}

export type ClosureResult = {
  /** Chemins a envoyer ensemble a la passe. */
  paths: string[]
  /** Pourquoi chacun est inclus — jamais de portee muette. */
  reasons: Record<string, string>
}

/**
 * Fermeture transitive d une reparation.
 *
 * Trois anneaux, dans cet ordre de certitude:
 *   1. les fichiers fautifs, nommes par le compilateur ou la trace;
 *   2. les modules qui DECLARENT un symbole cite par l erreur;
 *   3. les modules qui CONSOMMENT ces declarations.
 *
 * `maxPaths` borne la sortie: au-dela, on ne repare plus, on regenere.
 */
export function buildTransitiveClosure(args: {
  files: CodeFile[]
  seeds: string[]
  errors: string
  maxPaths?: number
}): ClosureResult {
  const maxPaths = args.maxPaths ?? 8
  const graph = buildModuleGraph(args.files)
  const byName = new Map(args.files.map((file) => [normalizePath(file.name), file]))
  const reasons: Record<string, string> = {}

  const add = (path: string, reason: string) => {
    if (!reasons[path]) reasons[path] = reason
  }

  for (const seed of args.seeds) {
    const file = byName.get(normalizePath(seed))
    if (file) add(file.name, 'fichier fautif nomme par l erreur')
  }

  const symbols = symbolsFromErrors(args.errors)
  const declaring: string[] = []
  // Une declaration AMBIGUE se nomme AVANT une declaration ordinaire: c est
  // elle qui nourrit l aller-retour, et `add` conserve la premiere raison
  // donnee. Mesure sur le livrable reel du run 1191: `Order` est declare a la
  // fois dans src/stores/orderStore.ts et src/types/index.ts — exactement
  // l ambiguite qui a coute neuf passes au run 1171, sur un autre run.
  const ownersBySymbol = new Map<string, CodeFile[]>()
  for (const symbol of symbols) {
    const owners = args.files.filter((file) => exportsSymbol(file.content, symbol))
    if (owners.length > 0) ownersBySymbol.set(symbol, owners)
  }
  for (const [symbol, owners] of ownersBySymbol) {
    if (owners.length < 2) continue
    for (const owner of owners) {
      declaring.push(owner.name)
      add(owner.name, `declare '${symbol}' — declaration AMBIGUE (${owners.length} modules)`)
    }
  }
  for (const [symbol, owners] of ownersBySymbol) {
    for (const owner of owners) {
      declaring.push(owner.name)
      add(owner.name, `declare '${symbol}'`)
    }
  }

  for (const declarer of declaring) {
    for (const consumer of graph.importedBy.get(declarer) ?? []) {
      add(consumer, `consomme ${normalizePath(declarer)}`)
    }
  }

  // Ordre de certitude, puis stabilite: une portee qui change d ordre d une
  // passe a l autre rend les mesures incomparables.
  const rank = (path: string) => {
    const reason = reasons[path]
    if (reason.startsWith('fichier fautif')) return 0
    if (reason.includes('AMBIGUE')) return 1
    if (reason.startsWith('declare')) return 2
    return 3
  }
  const paths = Object.keys(reasons)
    .sort((a, b) => rank(a) - rank(b) || a.localeCompare(b))
    .slice(0, maxPaths)

  const kept: Record<string, string> = {}
  for (const path of paths) kept[path] = reasons[path]
  return { paths, reasons: kept }
}

/**
 * Consigne remise a la passe quand un CYCLE a ete detecte.
 *
 * Le cycle etait detecte et arretait la boucle sans jamais changer la NATURE de
 * la strategie — retenter le meme traitement redonne le meme aller-retour. Ici
 * la consigne change: trancher le contrat en une fois, et dire lequel gagne.
 */
export function buildClosureRepairDirective(closure: ClosureResult, cycleSignature: string | null): string {
  const lines = [
    '## REPARATION DE CONTRAT — TOUS LES FICHIERS LIES, EN UNE SEULE FOIS',
  ]
  if (cycleSignature) {
    lines.push(
      `Un CYCLE a ete mesure sur: ${cycleSignature}`,
      'Les passes precedentes ont aligne l usage sur le type, puis le type sur l usage.',
      'Corriger un seul cote RECREE le defaut de l autre. Ne recommence pas ce va-et-vient.',
    )
  }
  lines.push(
    '',
    'Ces fichiers forment UN SEUL contrat. Rends-les coherents ensemble:',
    ...closure.paths.map((path) => `- ${path} — ${closure.reasons[path]}`),
    '',
    'Si un symbole est declare dans PLUSIEURS modules, choisis UNE declaration',
    'faisant autorite, supprime l autre, et fais pointer tous les consommateurs',
    'vers celle-la. Dis lequel tu as choisi.',
  )
  return lines.join('\n')
}
