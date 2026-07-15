import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  getTreeSitterGrammarWasmPath,
  isTreeSitterLanguageSupported,
  listTreeSitterSupportedLanguages,
  parseCodeWithTreeSitter,
} from '../services/codeTreeSitterAst.ts'

describe('codeTreeSitterAst', () => {
  test('expose les grammaires WASM des langages WS8', () => {
    for (const lang of ['ts', 'tsx', 'py', 'rust', 'go', 'java', 'cpp', 'swift', 'kotlin', 'dart']) {
      assert.equal(isTreeSitterLanguageSupported(lang), true, lang)
      assert.match(getTreeSitterGrammarWasmPath(lang) ?? '', /tree-sitter-.*\.wasm$/)
    }
    assert.equal(isTreeSitterLanguageSupported('brainfuck'), false)
    assert.ok(listTreeSitterSupportedLanguages().includes('typescript'))
  })

  test('parse un fichier JavaScript reel avec web-tree-sitter', async () => {
    const result = await parseCodeWithTreeSitter('function f(x) { return x + 1 }', 'javascript')

    assert.equal(result.ok, true, JSON.stringify(result))
    if (!result.ok) return
    assert.equal(result.rootType, 'program')
    assert.equal(result.hasError, false)
    assert.ok(result.namedNodeCount >= 4)
    assert.match(result.sexp, /function_declaration/)
  })
})
