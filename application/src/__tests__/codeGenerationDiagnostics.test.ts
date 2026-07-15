import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import type { CodeSandboxResult } from '../services/codeSandbox.ts'
import {
  buildEmptyGenerationDiagnostic,
  detectEnvironmentBlocker,
} from '../services/codeGenerationDiagnostics.ts'

const intent = { projectType: 'spa_react' } as unknown as CodeIntent

function sandbox(partial: Partial<CodeSandboxResult>): CodeSandboxResult {
  return {
    ok: false,
    rootPath: '/tmp/project',
    summary: '',
    question: null,
    detectedLanguage: 'node',
    steps: [],
    ...partial,
  }
}

describe('codeGenerationDiagnostics', () => {
  test('diagnostique les sorties vides et refus LLM', () => {
    assert.match(buildEmptyGenerationDiagnostic('', intent, 2), /aucun contenu exploitable/)
    assert.match(
      buildEmptyGenerationDiagnostic('Je suis desole, je ne peux pas generer ce code.', intent, 1),
      /refus ou une excuse/,
    )
  })

  test('diagnostique une narration de plan au lieu de fichiers', () => {
    const diagnostic = buildEmptyGenerationDiagnostic([
      'Projet detecte: spa_react',
      'Frameworks: react',
      'Preflight local: inspecter package.json',
    ].join('\n'), intent, 0)

    assert.match(diagnostic, /mode analyse\/preflight/)
  })

  test('detecte les blocages environnement explicites', () => {
    const autoInstall = detectEnvironmentBlocker(sandbox({
      steps: [{ label: 'Install', command: 'auto-install:node', ok: false, output: 'failed' }],
    }), ['runtime_unavailable'])
    assert.equal(autoInstall, 'node n a pas pu etre prepare automatiquement')

    const missingCommand = detectEnvironmentBlocker(sandbox({
      steps: [{ label: 'Run', command: 'npm test', ok: false, output: 'Failed to spawn command deno: ENOENT' }],
    }), ['runtime_unavailable'])
    assert.equal(missingCommand, 'commande deno absente du poste local')
  })

  test('ignore les sandboxes OK', () => {
    assert.equal(detectEnvironmentBlocker(sandbox({ ok: true }), ['runtime_unavailable']), null)
  })
})
