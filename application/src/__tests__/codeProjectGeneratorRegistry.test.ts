import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { classifyCodeIntent, buildCodeSystemPromptFromIntent } from '../services/codeIntent.ts'
import {
  buildProjectGeneratorPromptBlock,
  getProjectGeneratorForType,
} from '../services/codeProjectGeneratorRegistry.ts'
import type { CodeProjectType } from '../services/codeIntentTypes.ts'

describe('codeProjectGeneratorRegistry', () => {
  test('expose un generateur pour chaque nouveau type WS6', () => {
    const types: CodeProjectType[] = [
      'embedded_esp32',
      'embedded_arduino',
      'compiler',
      'os_kernel',
      'distributed_system',
      'mobile_ios',
      'mobile_android',
      'desktop_app',
      'engine_3d',
      'ide',
    ]

    for (const type of types) {
      const generator = getProjectGeneratorForType(type)
      assert.ok(generator, `missing generator for ${type}`)
      assert.equal(generator.projectType, type)
      assert.ok(generator.requiredFiles.length >= 3)
      assert.ok(generator.qualityBar.length >= 3)
    }
  })

  test('injecte le generateur specialise dans le prompt systeme', () => {
    const intent = classifyCodeIntent('cree un compilateur avec lexer parser AST et tests')
    const block = buildProjectGeneratorPromptBlock(intent)
    const prompt = buildCodeSystemPromptFromIntent(intent)

    assert.equal(intent.projectType, 'compiler')
    assert.match(block, /Generateur specialise WS6/)
    assert.match(prompt, /src\/lexer\.rs/)
    assert.match(prompt, /tests\/language\.rs/)
  })
})
