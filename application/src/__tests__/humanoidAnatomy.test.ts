/**
 * v77zl: validate humanoid anatomy directive block.
 *
 * The FLUX prompt builder injects this block before the diffusion model
 * generates the reference image. A regression here means humanoid
 * subjects (character / creature / body_part) silently lose their
 * Meshy-grade anatomical priors and revert to blob silhouettes / chibi
 * proportions / inverted hips on the very first generation pass.
 *
 * Run: node --experimental-strip-types src/__tests__/humanoidAnatomy.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { buildHumanoidAnatomyBlock } from '../services/humanoidAnatomy.ts'

const CHARACTER_INTENT = { purpose: 'character' as const, subjectKind: 'character' as const }
const PRODUCT_INTENT = { purpose: 'product' as const, subjectKind: 'product' as const }
const VEHICLE_INTENT = { purpose: 'product' as const, subjectKind: 'vehicle' as const }
const CREATURE_INTENT = { purpose: 'visual_preview' as const, subjectKind: 'creature' as const }
const BODY_PART_INTENT = { purpose: 'body_part' as const, subjectKind: 'body_part' as const }

describe('buildHumanoidAnatomyBlock — fires only for humanoid subjects', () => {
  test('character intent → block present', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'un guerrier elfique')
    assert.ok(block.length > 0)
    assert.match(block, /HUMANOID ANATOMY DIRECTIVES/)
    assert.match(block, /3:1/)
    assert.match(block, /Bilateral symmetry/)
  })

  test('creature intent → block present', () => {
    const block = buildHumanoidAnatomyBlock(CREATURE_INTENT, 'a dragon creature')
    assert.ok(block.length > 0)
    assert.match(block, /HUMANOID ANATOMY DIRECTIVES/)
  })

  test('body_part intent → block present', () => {
    const block = buildHumanoidAnatomyBlock(BODY_PART_INTENT, 'an arm with detailed anatomy')
    assert.ok(block.length > 0)
  })

  test('product intent → empty', () => {
    const block = buildHumanoidAnatomyBlock(PRODUCT_INTENT, 'a sleek consumer device')
    assert.equal(block, '')
  })

  test('vehicle intent → empty', () => {
    const block = buildHumanoidAnatomyBlock(VEHICLE_INTENT, 'a sports car')
    assert.equal(block, '')
  })
})

describe('buildHumanoidAnatomyBlock — realistic vs stylised modes', () => {
  test('"realistic" prompt → 1:7 adult ratio mentioned', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'un personnage realiste adult')
    assert.match(block, /1:7 head:body/i)
    assert.match(block, /NO chibi proportions/)
  })

  test('"chibi" prompt → stylised mode acknowledged, no anti-chibi line', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'a chibi character')
    assert.match(block, /Stylised mode acknowledged/)
    assert.doesNotMatch(block, /NO chibi proportions/)
  })

  test('"anime" prompt → stylised mode', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'un personnage anime fille')
    assert.match(block, /Stylised mode acknowledged/)
  })

  test('neutral prompt → balanced default', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'a character')
    assert.match(block, /Neutral character mode/)
  })
})

describe('buildHumanoidAnatomyBlock — previousMetrics inject specific corrections', () => {
  test('aspect < 1.4 → blob-shape correction', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'a character', {
      aspectRatio: 1.0,
      headVertexFraction: 0.15,
      headBodyWidthRatio: 0.4,
    })
    assert.match(block, /CORRECTIONS FROM PREVIOUS ATTEMPT/)
    assert.match(block, /silhouette was blob-shaped/)
    assert.match(block, /1\.00/)
  })

  test('aspect 1.5 → squat correction', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'a character', {
      aspectRatio: 1.5,
      headVertexFraction: 0.15,
      headBodyWidthRatio: 0.4,
    })
    assert.match(block, /squat/)
    assert.match(block, /1\.50/)
  })

  test('head fraction > 0.45 → dominant head correction', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'a character', {
      aspectRatio: 3.0,
      headVertexFraction: 0.55,
      headBodyWidthRatio: 0.4,
    })
    assert.match(block, /head dominated/)
    assert.match(block, /55%/)
  })

  test('head fraction > 0.30 with realistic prompt → chibi-when-realistic correction', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'realistic adult character', {
      aspectRatio: 2.5,
      headVertexFraction: 0.35,
      headBodyWidthRatio: 0.4,
    })
    assert.match(block, /chibi proportions/)
    assert.match(block, /35%/)
  })

  test('head fraction > 0.30 without realistic → no chibi-when-realistic correction', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'a stylised chibi character', {
      aspectRatio: 2.5,
      headVertexFraction: 0.35,
      headBodyWidthRatio: 0.4,
    })
    assert.doesNotMatch(block, /chibi proportions.*realistic was requested/)
  })

  test('head_body_width > 1.5 → inverted correction', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'a character', {
      aspectRatio: 3.0,
      headVertexFraction: 0.15,
      headBodyWidthRatio: 1.8,
    })
    assert.match(block, /head was 1\.80x wider than legs/)
    assert.match(block, /Hips and feet MUST be wider than head/)
  })

  test('all metrics OK → no PREVIOUS ATTEMPT block', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'a character', {
      aspectRatio: 3.5,
      headVertexFraction: 0.15,
      headBodyWidthRatio: 0.4,
    })
    assert.doesNotMatch(block, /CORRECTIONS FROM PREVIOUS ATTEMPT/)
  })

  test('null metrics → no PREVIOUS ATTEMPT block', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'a character', null)
    assert.doesNotMatch(block, /CORRECTIONS FROM PREVIOUS ATTEMPT/)
  })

  test('undefined metrics → no PREVIOUS ATTEMPT block', () => {
    const block = buildHumanoidAnatomyBlock(CHARACTER_INTENT, 'a character')
    assert.doesNotMatch(block, /CORRECTIONS FROM PREVIOUS ATTEMPT/)
  })
})
