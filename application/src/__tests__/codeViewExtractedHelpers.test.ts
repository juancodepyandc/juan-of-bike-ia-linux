import test from 'node:test'
import assert from 'node:assert/strict'

import { detectFileLanguage } from '../views/codeViewLanguage.ts'
import { isHeavyWebGLProject } from '../views/codeViewPreviewHeuristics.ts'
import { countFileSearchMatches } from '../views/codeViewSearch.ts'
import {
  buildCodePipelineLabel,
  codeContextNeedsVision,
  formatProjectType,
  isVisionContextFile,
} from '../views/codeViewShellHelpers.ts'
import type { CodeFile } from '../services/codeOrchestrator.ts'
import type { CodeIntent, CodeProjectType } from '../services/codeIntent.ts'

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

test('countFileSearchMatches echappe la recherche utilisateur', () => {
  const content = 'button Button btn button. button?'
  assert.equal(countFileSearchMatches(content, 'button'), 4)
  assert.equal(countFileSearchMatches(content, 'button.'), 1)
  assert.equal(countFileSearchMatches(content, '['), 0)
  assert.equal(countFileSearchMatches(content, ''), 0)
})

test('formatProjectType expose les libelles UI et le fallback lisible', () => {
  assert.equal(formatProjectType('spa_react'), 'App React (SPA)')
  assert.equal(formatProjectType('custom_stack' as CodeProjectType), 'custom stack')
})

test('codeContextNeedsVision detecte images, pdf et tableurs', () => {
  assert.equal(isVisionContextFile({ name: 'maquette.PNG', type: 'image/png' }), true)
  assert.equal(isVisionContextFile({ name: 'brief.pdf', type: 'application/octet-stream' }), true)
  assert.equal(codeContextNeedsVision([
    { name: 'notes.txt', type: 'text/plain' },
    { name: 'data.csv', type: 'text/csv' },
  ]), true)
  assert.equal(codeContextNeedsVision([{ name: 'notes.txt', type: 'text/plain' }]), false)
})

test('buildCodePipelineLabel reflete les etapes activees par lintent', () => {
  assert.equal(
    buildCodePipelineLabel(null),
    'Intent, preflight local, planning, generation, sandbox, correction, preview.',
  )

  const intent = {
    needsArchitecturePlanning: true,
    needsDevServer: true,
    previewType: 'dev_server',
  } as CodeIntent
  assert.equal(
    buildCodePipelineLabel(intent),
    'Preflight local → Planning archi → Generation modele expert → Sandbox isole → Boucle auto-correction → Dev server → Preview',
  )
})
