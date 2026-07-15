import test from 'node:test'
import assert from 'node:assert/strict'

import { detectFileLanguage } from '../views/codeViewLanguage.ts'
import { isHeavyWebGLProject } from '../views/codeViewPreviewHeuristics.ts'
import type { CodeFile } from '../services/codeOrchestrator.ts'

const file = (name: string, content: string, language = 'plaintext'): CodeFile => ({
  name,
  content,
  language,
})

test('detectFileLanguage privilegie extension et shebang', () => {
  assert.deepEqual(detectFileLanguage('src/App.tsx', 'export default function App() {}'), {
    lang: 'tsx',
    confidence: 0.98,
    shebang: false,
  })
  assert.deepEqual(detectFileLanguage('bin/task', '#!/usr/bin/env python3\nprint("ok")'), {
    lang: 'python',
    confidence: 0.85,
    shebang: true,
  })
})

test('detectFileLanguage retombe sur les signatures source', () => {
  assert.equal(detectFileLanguage('Dockerfile', 'FROM node:22\n').lang, 'dockerfile')
  assert.equal(detectFileLanguage('README', 'plain text').lang, 'plaintext')
  assert.equal(detectFileLanguage('module', 'fn main() {\n  println!("ok");\n}').lang, 'rust')
  assert.equal(detectFileLanguage('script', 'def run():\n    return 1').lang, 'python')
})

test('isHeavyWebGLProject detecte les projets preview dangereux', () => {
  assert.equal(isHeavyWebGLProject([
    file('src/App.tsx', 'import * as THREE from "three"\nexport function Scene() {}', 'tsx'),
  ]), true)
  assert.equal(isHeavyWebGLProject([
    file('src/game.js', 'const gl = canvas.getContext("webgl")\nrequestAnimationFrame(render)', 'js'),
  ]), true)
  assert.equal(isHeavyWebGLProject([
    file('src/App.tsx', '<main>simple page</main>', 'tsx'),
  ]), false)
})

test('isHeavyWebGLProject bloque les fichiers trop volumineux', () => {
  assert.equal(isHeavyWebGLProject([
    file('src/generated.js', 'x'.repeat(80_001), 'js'),
  ]), true)
})
