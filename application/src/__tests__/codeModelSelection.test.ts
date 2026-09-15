import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  CODE_CLOUD_HIGH_MODEL,
  CODE_LEGACY_HIGH_MODEL,
  CODE_LEGACY_MODEL,
  CODE_LIGHT_MODEL,
  CODE_LOCAL_PRIMARY_MODEL,
  CODE_NEXT_HIGH_MODEL,
  CODE_NEXT_MODEL,
  CODE_PRIMARY_MODEL,
  getCodeRecoveryFallbackModels,
  selectCodeModelForHardware,
  selectAdaptiveReasoningModel,
} from '../config/models.ts'

describe('code model selection', () => {
  test('keeps an explicitly selected trained learning model in the Academy on limited RAM', () => {
    assert.equal(selectAdaptiveReasoningModel({ ram_gb: 16 }, 'aurora-rl-learning:v1'), 'aurora-rl-learning:v1')
  })
  test('local production code model is the fitting Qwen3-Coder 30B (not the oversized Next)', () => {
    // qwen3-coder:30b (18GB, MoE 3B actifs) tient sur 16GB VRAM + 30GB RAM ; les
    // variantes qwen3-coder-next (q4_K_M 51GB, q8_0 ~85GB) non — elles sont
    // reservees au chemin cloud (CODE_CLOUD_HIGH_MODEL).
    assert.equal(CODE_PRIMARY_MODEL, CODE_LOCAL_PRIMARY_MODEL)
    assert.equal(CODE_LOCAL_PRIMARY_MODEL, 'qwen3-coder:30b')
    assert.equal(CODE_CLOUD_HIGH_MODEL, CODE_NEXT_HIGH_MODEL)
  })

  test('prefers the installed qwen3-coder:30b on the real 16GB box', () => {
    const selected = selectCodeModelForHardware(
      { ram_gb: 30, vram_gb: 16 },
      [CODE_LOCAL_PRIMARY_MODEL, CODE_LEGACY_MODEL, CODE_LIGHT_MODEL],
      null,
    )

    assert.equal(selected, CODE_LOCAL_PRIMARY_MODEL)
  })

  test('never auto-selects the 51GB Next model on constrained local hardware, even if installed', () => {
    const selected = selectCodeModelForHardware(
      { ram_gb: 30, vram_gb: 16 },
      [CODE_NEXT_MODEL, CODE_LOCAL_PRIMARY_MODEL, CODE_LIGHT_MODEL],
      CODE_NEXT_MODEL, // meme une preference sauvegardee sur le Next ne doit pas le ressusciter
    )

    assert.notEqual(selected, CODE_NEXT_MODEL)
    assert.equal(selected, CODE_LOCAL_PRIMARY_MODEL)
  })

  test('falls back to the legacy 30B Q4 (fitting) rather than the 7B when the primary is absent', () => {
    const selected = selectCodeModelForHardware(
      { ram_gb: 30, vram_gb: 16 },
      [CODE_LEGACY_MODEL, CODE_LIGHT_MODEL],
      CODE_LIGHT_MODEL,
    )

    assert.equal(selected, CODE_LEGACY_MODEL)
  })

  test('prefers legacy Q8 over legacy Q4 when both are installed and the primary is absent', () => {
    const selected = selectCodeModelForHardware(
      { ram_gb: 96, vram_gb: 64 },
      [CODE_LEGACY_MODEL, CODE_LEGACY_HIGH_MODEL, CODE_LIGHT_MODEL],
      CODE_LEGACY_MODEL,
    )

    assert.equal(selected, CODE_LEGACY_HIGH_MODEL)
  })

  test('does not prefer the 7B fallback on constrained local hardware', () => {
    const fallbacks = getCodeRecoveryFallbackModels(
      { ram_gb: 16, vram_gb: 8 },
      [CODE_LEGACY_MODEL, CODE_LIGHT_MODEL],
      CODE_LIGHT_MODEL,
    )

    assert.equal(fallbacks[0], CODE_LEGACY_MODEL)
    assert.ok(fallbacks.indexOf(CODE_LIGHT_MODEL) > fallbacks.indexOf(CODE_LEGACY_MODEL))
  })
})
