import type ParserNamespace from 'web-tree-sitter'

export type TreeSitterParseOk = {
  ok: true
  language: string
  grammarWasmPath: string
  rootType: string
  hasError: boolean
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

let parserInitPromise: Promise<void> | null = null

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

    const parserLanguage = await Parser.Language.load(grammarWasmPath)
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
