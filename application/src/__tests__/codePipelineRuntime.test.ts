import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import {
  CODE_EXPERT_CONTEXT_TOKENS,
  CODE_EXPERT_OUTPUT_TOKENS,
  DOCUMENTATION_EXTENSIONS_EARLY,
  clipText,
  getModelShortName,
  selectModel,
  selectModelDecision,
} from '../services/codePipelineRuntime.ts'

const intent = { projectType: 'spa_react', complexity: 'complex' } as unknown as CodeIntent

describe('codePipelineRuntime', () => {
  test('selectModel route les roles via les modeles installes', () => {
    const routing = {
      installedModels: ['qwen3-coder:30b', 'qwen3:32b'],
      hardware: { ram_gb: 30, vram_gb: 16 },
    }

    assert.equal(selectModel('generation', intent, 0, 'qwen3-coder:30b', routing), 'qwen3-coder:30b')
    assert.equal(selectModel('planning', intent, 0, 'qwen3-coder:30b', routing), 'qwen3:32b')
    assert.equal(selectModel('correction', intent, 9, 'qwen3-coder:30b', routing), 'qwen3:32b')

    const decision = selectModelDecision('correction', intent, 9, 'qwen3-coder:30b', routing)
    assert.equal(decision.role, 'verifier')
    assert.equal(decision.distinctFromCoder, true)
    assert.equal(decision.installedMatch, true)
  })

  test('selectModel retombe sur le codeur si aucun verifieur installe n est connu', () => {
    assert.equal(
      selectModel('correction', intent, 3, 'qwen3-coder:30b', { installedModels: ['qwen3-coder:30b'] }),
      'qwen3-coder:30b',
    )
  })

  test('getModelShortName retire registre et tag', () => {
    assert.equal(getModelShortName('registry.local/qwen3-coder:30b'), 'qwen3-coder')
    assert.equal(getModelShortName('qwen3:32b'), 'qwen3')
  })

  test('clipText tronque proprement les sorties longues', () => {
    assert.equal(clipText('  court  ', 20), 'court')
    assert.match(clipText('abcdef', 3), /^abc\n\.\.\.\[sortie tronquee\]$/)
  })

  test('constantes critiques du pipeline restent exposees', () => {
    assert.equal(CODE_EXPERT_CONTEXT_TOKENS, 8192)
    assert.equal(CODE_EXPERT_OUTPUT_TOKENS, 8192)
    assert.equal(DOCUMENTATION_EXTENSIONS_EARLY.has('md'), true)
  })
})
