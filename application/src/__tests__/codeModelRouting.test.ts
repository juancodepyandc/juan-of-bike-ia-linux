import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import { CODE_CLOUD_HIGH_MODEL } from '../config/models.ts'
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

  test('escalade aussi la generation quand le plateau est prouve', () => {
    const decision = selectCodeRoleModel('generation', intent, 4, {
      configuredCodeModel: 'qwen3-coder:30b',
      installedModels: ['qwen3-coder:30b', CODE_CLOUD_HIGH_MODEL],
      // machine costaude: le gros modele cloud tient -> escalade autorisee.
      hardware: { ram_gb: 128, vram_gb: 80 },
      plateau: true,
    })

    assert.equal(decision.model, CODE_CLOUD_HIGH_MODEL)
    assert.equal(decision.role, 'coder')
    assert.equal(decision.distinctFromCoder, true)
    assert.match(decision.reason, /plateau-cloud-escalation:4/)
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

  test('escalade sur plateau vers un modele cloud installe', () => {
    const decision = selectCodeRoleModel('correction', intent, 6, {
      configuredCodeModel: 'qwen3-coder:30b',
      installedModels: ['qwen3-coder:30b', CODE_CLOUD_HIGH_MODEL],
      // machine costaude: le gros modele cloud tient -> escalade autorisee.
      hardware: { ram_gb: 128, vram_gb: 80 },
      plateau: true,
    })

    assert.equal(decision.model, CODE_CLOUD_HIGH_MODEL)
    assert.equal(decision.distinctFromCoder, true)
    assert.match(decision.reason, /plateau-cloud-escalation/)
  })

  test('GARDE ANTI-GEL: refuse un modele cloud trop gros sur un poste local', () => {
    // Meme cas mais poste local (16GB VRAM + 30GB RAM): le 80B ne tient pas ->
    // la garde le retire des candidats -> retombe sur le codeur (pas de gel).
    const decision = selectCodeRoleModel('correction', intent, 6, {
      configuredCodeModel: 'qwen3-coder:30b',
      installedModels: ['qwen3-coder:30b', CODE_CLOUD_HIGH_MODEL],
      hardware: { ram_gb: 30, vram_gb: 16 },
      plateau: true,
    })

    assert.notEqual(decision.model, CODE_CLOUD_HIGH_MODEL)
    assert.equal(decision.model, 'qwen3-coder:30b')
  })
})
