import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  CODE_CLOUD_HIGH_MODEL,
  CODE_LEGACY_HIGH_MODEL,
  CODE_LEGACY_MODEL,
  CODE_LIGHT_MODEL,
  CODE_NEXT_HIGH_MODEL,
  CODE_NEXT_MODEL,
  CODE_PRIMARY_MODEL,
  getCodeRecoveryFallbackModels,
  selectCodeModelForHardware,
} from '../config/models.ts'

describe('code model selection', () => {
  test('uses Qwen3-Coder-Next as the global production code model', () => {
    assert.equal(CODE_PRIMARY_MODEL, CODE_NEXT_MODEL)
    assert.equal(CODE_CLOUD_HIGH_MODEL, CODE_NEXT_HIGH_MODEL)
  })

  test('prefers Qwen3-Coder-Next when it is installed', () => {
    const selected = selectCodeModelForHardware(
      { ram_gb: 32, vram_gb: 16 },
      [CODE_LEGACY_MODEL, CODE_NEXT_MODEL, CODE_LIGHT_MODEL],
      CODE_LEGACY_MODEL,
    )

    assert.equal(selected, CODE_NEXT_MODEL)
  })

  test('prefers Qwen3-Coder-Next Q8 over Q4 when both are installed', () => {
    const selected = selectCodeModelForHardware(
      { ram_gb: 96, vram_gb: 80 },
      [CODE_NEXT_MODEL, CODE_NEXT_HIGH_MODEL, CODE_CLOUD_HIGH_MODEL],
      CODE_NEXT_MODEL,
    )

    assert.equal(selected, CODE_NEXT_HIGH_MODEL)
  })

  test('prefers the highest quality installed code model even over a saved Q4 preference', () => {
    const selected = selectCodeModelForHardware(
      { ram_gb: 64, vram_gb: 48 },
      [CODE_NEXT_MODEL, CODE_NEXT_HIGH_MODEL, CODE_LEGACY_MODEL, CODE_LIGHT_MODEL],
      CODE_LEGACY_MODEL,
    )

    assert.equal(selected, CODE_NEXT_HIGH_MODEL)
  })

  test('uses the installed legacy Q4 production code model when Next is not installed', () => {
    const selected = selectCodeModelForHardware(
      { ram_gb: 32, vram_gb: 16 },
      [CODE_LEGACY_MODEL, CODE_LIGHT_MODEL],
      CODE_LIGHT_MODEL,
    )

    assert.equal(selected, CODE_LEGACY_MODEL)
  })

  test('does not prefer the 7B fallback on constrained local hardware', () => {
    const fallbacks = getCodeRecoveryFallbackModels(
      { ram_gb: 16, vram_gb: 8 },
      [CODE_NEXT_MODEL, CODE_LEGACY_MODEL, CODE_LIGHT_MODEL],
      CODE_LIGHT_MODEL,
    )

    assert.equal(fallbacks[0], CODE_NEXT_MODEL)
    assert.ok(fallbacks.indexOf(CODE_LIGHT_MODEL) > fallbacks.indexOf(CODE_LEGACY_MODEL))
  })

  test('prefers legacy Q8 over legacy Q4 only when Next is absent', () => {
    const selected = selectCodeModelForHardware(
      { ram_gb: 96, vram_gb: 64 },
      [CODE_LEGACY_MODEL, CODE_LEGACY_HIGH_MODEL, CODE_LIGHT_MODEL],
      CODE_LEGACY_MODEL,
    )

    assert.equal(selected, CODE_LEGACY_HIGH_MODEL)
  })
})
