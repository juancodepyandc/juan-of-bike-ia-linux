import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import {
  codeModelNamesEqual,
  normalizeOllamaModelName,
  selectCodeRoleModel,
} from '../services/codeModelRouting.ts'

const intent = { projectType: 'spa_react', complexity: 'enterprise' } as unknown as CodeIntent

describe('codeModelRouting', () => {
  test('normalise les tags Ollama sans confondre les roles', () => {
    assert.equal(normalizeOllamaModelName('Qwen3:32B:latest'), 'qwen3:32b')
    assert.equal(codeModelNamesEqual('qwen3:32b:latest', 'qwen3:32b'), true)
    assert.equal(codeModelNamesEqual('qwen3-coder:30b', 'qwen3:32b'), false)
  })

  test('garde le modele coder pour la generation meme si un generaliste est configure', () => {
    const decision = selectCodeRoleModel('generation', intent, 0, {
      configuredCodeModel: 'qwen3:14b',
      installedModels: ['qwen3:14b', 'qwen3-coder:30b'],
      hardware: { ram_gb: 30, vram_gb: 16 },
    })

    assert.equal(decision.model, 'qwen3-coder:30b')
    assert.equal(decision.role, 'coder')
  })

  test('selectionne un architecte/verifieur distinct quand /api/tags le prouve', () => {
    const decision = selectCodeRoleModel('planning', intent, 0, {
      configuredCodeModel: 'qwen3-coder:30b',
      installedModels: ['qwen3-coder:30b', 'qwen3:32b-q4_K_M'],
      hardware: { ram_gb: 30, vram_gb: 16 },
    })

    assert.equal(decision.model, 'qwen3:32b-q4_K_M')
    assert.equal(decision.role, 'architect')
    assert.equal(decision.distinctFromCoder, true)
    assert.equal(decision.installedMatch, true)
  })

  test('n invente pas un role model absent dans le chemin live', () => {
    const decision = selectCodeRoleModel('correction', intent, 2, {
      configuredCodeModel: 'qwen3-coder:30b',
      installedModels: ['qwen3-coder:30b'],
    })

    assert.equal(decision.model, 'qwen3-coder:30b')
    assert.equal(decision.distinctFromCoder, false)
    assert.match(decision.reason, /fallback-coder/)
  })
})

