import type ParserNamespace from 'web-tree-sitter'

export type TreeSitterParseOk = {
  ok: true
  language: string
  grammarWasmPath: string
  rootType: string
  hasError: boolean
  /** Position EXACTE du premier noeud fautif, 1-indexee. */
  errorLocation: { line: number; column: number; kind: 'ERROR' | 'MISSING'; snippet: string } | null
  namedNodeCount: number
  sexp: string
}

export type TreeSitterParseFail = {
  ok: false
  language: string
  reason: string
}

export type TreeSitterParseResult = TreeSitterParseOk | TreeSitterParseFail

export type TreeSitterParseOptions = {
  parserWasmPath?: string
  grammarWasmPath?: string
  maxSexpLength?: number
}

const DEFAULT_PARSER_WASM_URL = new URL('../../node_modules/web-tree-sitter/tree-sitter.wasm', import.meta.url).href

const GRAMMAR_WASM_BY_LANGUAGE: Record<string, string> = {
  c: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-c.wasm', import.meta.url).href,
  cc: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-cpp.wasm', import.meta.url).href,
  cpp: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-cpp.wasm', import.meta.url).href,
  cxx: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-cpp.wasm', import.meta.url).href,
  'c++': new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-cpp.wasm', import.meta.url).href,
  dart: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-dart.wasm', import.meta.url).href,
  go: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-go.wasm', import.meta.url).href,
  golang: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-go.wasm', import.meta.url).href,
  h: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-c.wasm', import.meta.url).href,
  hpp: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-cpp.wasm', import.meta.url).href,
  java: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-java.wasm', import.meta.url).href,
  js: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-javascript.wasm', import.meta.url).href,
  jsx: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-javascript.wasm', import.meta.url).href,
  javascript: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-javascript.wasm', import.meta.url).href,
  kt: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-kotlin.wasm', import.meta.url).href,
  kotlin: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-kotlin.wasm', import.meta.url).href,
  kts: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-kotlin.wasm', import.meta.url).href,
  py: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-python.wasm', import.meta.url).href,
  python: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-python.wasm', import.meta.url).href,
  rs: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-rust.wasm', import.meta.url).href,
  rust: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-rust.wasm', import.meta.url).href,
  swift: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-swift.wasm', import.meta.url).href,
  ts: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-typescript.wasm', import.meta.url).href,
  tsx: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-tsx.wasm', import.meta.url).href,
  typescript: new URL('../../node_modules/tree-sitter-wasms/out/tree-sitter-typescript.wasm', import.meta.url).href,
}

// L EXTENSION prime sur le libelle de langage. `detectLanguage()` etiquette un
// `.tsx` en "typescript" (libelle d affichage correct pour la coloration), mais
// la grammaire `typescript` REFUSE le JSX: tout composant React valide etait
// alors declare "erreur de syntaxe". La grammaire se choisit donc sur le nom de
// fichier, et le libelle ne sert plus que de repli.
const GRAMMAR_LANGUAGE_BY_EXTENSION: Record<string, string> = {
  cjs: 'javascript', cts: 'typescript', js: 'javascript', jsx: 'jsx',
  mjs: 'javascript', mts: 'typescript', ts: 'ts', tsx: 'tsx',
}

export function resolveTreeSitterLanguage(fileName: string, declaredLanguage?: string): string | null {
  const extension = fileName.replace(/\\/g, '/').split('/').pop()?.split('.').pop()?.toLowerCase() ?? ''
  const byExtension = GRAMMAR_LANGUAGE_BY_EXTENSION[extension] ?? extension
  if (byExtension && isTreeSitterLanguageSupported(byExtension)) return byExtension
  const declared = normalizeLang(declaredLanguage ?? '')
  return declared && isTreeSitterLanguageSupported(declared) ? declared : null
}

let parserInitPromise: Promise<void> | null = null
// Cache des grammaires chargees (par chemin WASM): ce parser tourne dans la
// boucle de validation, on evite de recharger une grammaire par fichier.
const grammarCache = new Map<string, ParserNamespace.Language>()

function normalizeLang(lang: string): string {
  return lang.trim().toLowerCase()
}

export function getTreeSitterGrammarWasmPath(lang: string): string | null {
  const grammarUrl = GRAMMAR_WASM_BY_LANGUAGE[normalizeLang(lang)]
  return grammarUrl ? normalizeWasmLocation(grammarUrl) : null
}

export function isTreeSitterLanguageSupported(lang: string): boolean {
  return getTreeSitterGrammarWasmPath(lang) !== null
}

export function listTreeSitterSupportedLanguages(): string[] {
  return Object.keys(GRAMMAR_WASM_BY_LANGUAGE).sort()
}

type TreeSitterNode = ParserNamespace.SyntaxNode

function nodeIsNamed(node: TreeSitterNode): boolean {
  return typeof node.isNamed === 'function' ? node.isNamed() : Boolean(node.isNamed)
}

function nodeHasError(node: TreeSitterNode): boolean {
  return typeof node.hasError === 'function' ? node.hasError() : Boolean(node.hasError)
}

function normalizeWasmLocation(location: string): string {
  if (!location.startsWith('file://')) return location
  return decodeURIComponent(new URL(location).pathname)
}

/**
 * Localise le PREMIER noeud fautif.
 *
 * Sans lui, le critic annoncait « AboutPage.tsx: erreur de syntaxe » — vrai,
 * mais inexploitable: le modele devait relire 200 lignes pour trouver quoi. Le
 * parser connait pourtant la position exacte, il suffisait de la lire.
 * Mesure reelle (run 1011): quatre passes de correction sur ce seul manque.
 */
function findFirstError(root: TreeSitterNode, source: string): TreeSitterParseOk['errorLocation'] {
  const stack: TreeSitterNode[] = [root]
  let best: { node: TreeSitterNode; kind: 'ERROR' | 'MISSING' } | null = null
  while (stack.length > 0) {
    const node = stack.pop()!
    const isMissing = typeof node.isMissing === 'function' ? node.isMissing() : Boolean((node as unknown as { isMissing?: boolean }).isMissing)
    if (node.type === 'ERROR' || isMissing) {
      const kind = isMissing ? 'MISSING' : 'ERROR'
      // On garde le noeud le plus PRECIS, pas le plus tot: quand un fichier ne
      // parse plus des la premiere ligne, l ERROR racine couvre tout le fichier
      // et pointer « 1:1 » n aide personne. Le noeud le plus court est celui qui
      // cerne vraiment le jeton fautif (mesure: « 1:1 » -> « 15:23, pres de
      // location: 'Presqu'île' » — l apostrophe non echappee, la vraie cause).
      const span = node.endIndex - node.startIndex
      const bestSpan = best ? best.node.endIndex - best.node.startIndex : Number.MAX_SAFE_INTEGER
      if (!best || span < bestSpan || (span === bestSpan && node.startIndex < best.node.startIndex)) {
        best = { node, kind }
      }
      // On DESCEND quand meme: un ERROR racine couvre tout le fichier et
      // contient presque toujours un noeud fautif plus precis.
      for (const child of node.children) stack.push(child)
      continue
    }
    if (!nodeHasError(node)) continue
    for (const child of node.children) stack.push(child)
  }
  if (!best) return null
  const { node, kind } = best
  // Un ERROR qui part de l octet 0 couvre tout le fichier (cas d une chaine non
  // terminee qui avale la suite): « 1:1 » n apprend rien. On pointe alors la
  // FRONTIERE d analyse — la fin du dernier fragment correctement parse, c est
  // la que le parser a decroche.
  let offset = node.startIndex
  if (offset === 0 && node.children.length > 0) {
    const parsed = node.children.filter((child) => child.type !== 'ERROR')
    const frontier = parsed.length > 0 ? parsed[parsed.length - 1].endIndex : 0
    if (frontier > 0) offset = frontier
  }
  const lines = source.slice(0, offset).split('\n')
  const line = lines.length
  const column = (lines[lines.length - 1]?.length ?? 0) + 1
  const snippet = source.split('\n')[line - 1]?.trim().slice(0, 120) ?? ''
  return { line, column, kind, snippet }
}

function countNamedNodes(root: TreeSitterNode): number {
  let count = 0
  const stack: TreeSitterNode[] = [root]
  while (stack.length > 0) {
    const node = stack.pop()!
    if (nodeIsNamed(node)) count += 1
    for (const child of node.namedChildren) stack.push(child)
  }
  return count
}

export async function parseCodeWithTreeSitter(
  content: string,
  lang: string,
  options: TreeSitterParseOptions = {},
): Promise<TreeSitterParseResult> {
  const language = normalizeLang(lang)
  const grammarWasmPath = options.grammarWasmPath ?? getTreeSitterGrammarWasmPath(language)
  if (!grammarWasmPath) {
    return { ok: false, language, reason: `Langage non supporte par tree-sitter: ${lang}` }
  }

  try {
    const module = await import('web-tree-sitter')
    const Parser = (module.default ?? module) as typeof ParserNamespace
    parserInitPromise ??= Parser.init({
      locateFile(scriptName: string) {
        if (scriptName.endsWith('.wasm')) {
          return normalizeWasmLocation(options.parserWasmPath ?? DEFAULT_PARSER_WASM_URL)
        }
        return scriptName
      },
    })
    await parserInitPromise

    let parserLanguage = grammarCache.get(grammarWasmPath)
    if (!parserLanguage) {
      parserLanguage = await Parser.Language.load(grammarWasmPath)
      grammarCache.set(grammarWasmPath, parserLanguage)
    }
    const parser = new Parser()
    parser.setLanguage(parserLanguage)
    const tree = parser.parse(content)
    if (!tree) {
      parser.delete()
      return { ok: false, language, reason: 'tree-sitter parse a retourne null' }
    }

    const root = tree.rootNode
    const sexp = root.toString()
    const result: TreeSitterParseOk = {
      ok: true,
      language,
      grammarWasmPath,
      rootType: root.type,
      hasError: nodeHasError(root),
      errorLocation: nodeHasError(root) ? findFirstError(root, content) : null,
      namedNodeCount: countNamedNodes(root),
      sexp: sexp.slice(0, options.maxSexpLength ?? 4000),
    }
    tree.delete()
    parser.delete()
    return result
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return { ok: false, language, reason: message }
  }
}
