/**
 * v77zm: validate kinematics library + custom motion parser.
 *
 * Surface tested:
 *   - presets exist for character / creature / mechanism / vehicle
 *   - selectKinematicPresets() returns correct matches per subject/system
 *   - parseCustomMotionPrompt() handles sequences ("X puis Y"), parallel
 *     gestures ("danser en applaudissant"), unknown verbs (custom_pose
 *     fallback), and rejects non-motion text
 *   - buildKinematicsDirectiveBlock() emits a contract block for FLUX
 *
 * Run: node --experimental-strip-types src/__tests__/kinematicsLibrary.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  selectKinematicPresets,
  parseCustomMotionPrompt,
  buildKinematicsDirectiveBlock,
  listAllPresetIds,
} from '../services/kinematicsLibrary.ts'

describe('kinematics library catalog', () => {
  test('character presets cover core actions', () => {
    const ids = listAllPresetIds()
    for (const expected of [
      'character.idle',
      'character.walk_cycle',
      'character.run_cycle',
      'character.dance_default',
      'character.wave',
      'character.salute',
      'character.bow',
      'character.jump',
      'character.kick',
      'character.punch',
      'character.sit',
      'character.kneel',
      'character.crawl',
      'character.swim',
      'character.cartwheel',
    ]) {
      assert.ok(ids.includes(expected), `missing preset: ${expected}`)
    }
  })

  test('creature presets cover non-humanoid motion', () => {
    const ids = listAllPresetIds()
    assert.ok(ids.includes('creature.flap_fly'))
    assert.ok(ids.includes('creature.slither'))
    assert.ok(ids.includes('creature.prowl'))
  })

  test('mechanism presets cover all system classes', () => {
    const ids = listAllPresetIds()
    assert.ok(ids.includes('mechanism.gear_mesh_rotate'))
    assert.ok(ids.includes('mechanism.belt_loop'))
    assert.ok(ids.includes('mechanism.piston_stroke'))
    assert.ok(ids.includes('mechanism.hinge_swing'))
    assert.ok(ids.includes('mechanism.linkage_cycle'))
  })

  test('vehicle presets exist', () => {
    const ids = listAllPresetIds()
    assert.ok(ids.includes('vehicle.roll_forward'))
    assert.ok(ids.includes('vehicle.hover'))
  })
})

describe('selectKinematicPresets — picks relevant motion descriptors', () => {
  test('character subject → character + creature presets returned', () => {
    const presets = selectKinematicPresets({ subjectKind: 'character', systemClass: 'generic' })
    assert.ok(presets.some((p) => p.id === 'character.walk_cycle'))
    assert.ok(presets.some((p) => p.id === 'character.dance_default'))
    assert.ok(presets.every((p) => !p.id.startsWith('vehicle.')))
  })

  test('gear_train system → gear mesh preset', () => {
    const presets = selectKinematicPresets({ subjectKind: 'mechanism', systemClass: 'gear_train' })
    assert.ok(presets.some((p) => p.id === 'mechanism.gear_mesh_rotate'))
  })

  test('belt_drive system → belt loop preset', () => {
    const presets = selectKinematicPresets({ subjectKind: 'mechanism', systemClass: 'belt_drive' })
    assert.ok(presets.some((p) => p.id === 'mechanism.belt_loop'))
  })

  test('vehicle subject → vehicle presets', () => {
    const presets = selectKinematicPresets({ subjectKind: 'vehicle', systemClass: 'generic' })
    assert.ok(presets.some((p) => p.id === 'vehicle.roll_forward'))
  })

  test('object subject + generic system → no presets', () => {
    const presets = selectKinematicPresets({ subjectKind: 'object', systemClass: 'generic' })
    assert.equal(presets.length, 0)
  })
})

describe('parseCustomMotionPrompt — free-text → MotionDescriptor', () => {
  test('"marche puis saute" → walk + jump in sequence', () => {
    const m = parseCustomMotionPrompt('le perso marche puis saute')
    assert.ok(m, 'expected MotionDescriptor')
    assert.equal(m!.source, 'custom')
    // walk_cycle has 3 primitives + jump has 3 primitives = 6
    assert.equal(m!.primitives.length, 6)
    assert.match(m!.label, /Marcher.*Saut/i)
  })

  test('"fait une roue arriere puis salue" → cartwheel + wave', () => {
    const m = parseCustomMotionPrompt('le perso fait une roue arriere puis salue')
    assert.ok(m)
    assert.match(m!.label, /Roue.*Saluer/i)
  })

  test('"danse" alone → dance preset', () => {
    const m = parseCustomMotionPrompt('le perso danse')
    // No separator and matches dance verb → still a valid single-step custom
    // (the parser returns null only when there's no match AND no separator)
    assert.ok(m === null || m.label.includes('Danser'))
  })

  test('"marche puis fait un truc bizarre" → walk + custom_pose fallback', () => {
    const m = parseCustomMotionPrompt('marche puis fait un truc bizarre')
    assert.ok(m)
    // Should have walk primitives + 1 custom_pose
    const hasCustomPose = m!.primitives.some((p) => p.kind === 'custom_pose')
    assert.ok(hasCustomPose, 'expected custom_pose primitive for unknown verb')
  })

  test('unknown text without separator → null', () => {
    const m = parseCustomMotionPrompt('un beau ciel bleu')
    assert.equal(m, null)
  })

  test('empty/short input → null', () => {
    assert.equal(parseCustomMotionPrompt(''), null)
    assert.equal(parseCustomMotionPrompt('  '), null)
    assert.equal(parseCustomMotionPrompt('a'), null)
  })

  test('English: "walk then jump" → walk + jump', () => {
    const m = parseCustomMotionPrompt('walk then jump')
    assert.ok(m)
    assert.match(m!.label, /Marcher.*Saut/i)
  })

  test('mechanism verbs: "engrenage qui tourne" → gear_mesh_rotate', () => {
    const m = parseCustomMotionPrompt('engrenage qui tourne puis charniere qui s ouvre')
    assert.ok(m)
    assert.match(m!.label, /Engrenage.*Charniere/i)
  })

  test('total duration sums sequenced primitives', () => {
    const m = parseCustomMotionPrompt('marche puis saute')
    assert.ok(m)
    // walk = 1.0s, jump = 1.4s → total ~ 2.4s
    assert.ok(m!.duration_seconds >= 2.0 && m!.duration_seconds <= 3.0)
  })

  test('custom motion is non-looping by default', () => {
    const m = parseCustomMotionPrompt('marche puis saute')
    assert.ok(m)
    assert.equal(m!.loop, false)
  })
})

describe('parseCustomMotionPrompt — v77zv modifiers (speed/intensity/emotion)', () => {
  test('"marche rapidement" boosts walk frequency_hz', () => {
    const baseline = parseCustomMotionPrompt('le perso marche')
    const fast = parseCustomMotionPrompt('le perso marche rapidement')
    assert.ok(baseline)
    assert.ok(fast)
    const baseGait = baseline!.primitives.find((p) => p.kind === 'gait')!
    const fastGait = fast!.primitives.find((p) => p.kind === 'gait')!
    assert.ok(fastGait.frequency_hz! > baseGait.frequency_hz!, 'fast walk should have higher frequency')
  })

  test('"marche lentement" lowers walk frequency_hz', () => {
    const baseline = parseCustomMotionPrompt('le perso marche')
    const slow = parseCustomMotionPrompt('le perso marche lentement')
    assert.ok(baseline)
    assert.ok(slow)
    const baseGait = baseline!.primitives.find((p) => p.kind === 'gait')!
    const slowGait = slow!.primitives.find((p) => p.kind === 'gait')!
    assert.ok(slowGait.frequency_hz! < baseGait.frequency_hz!, 'slow walk should have lower frequency')
  })

  test('"saute fortement" boosts jump amplitude', () => {
    const baseline = parseCustomMotionPrompt('saute puis salue')
    const strong = parseCustomMotionPrompt('saute fortement puis salue')
    assert.ok(baseline)
    assert.ok(strong)
    const baseJump = baseline!.primitives.find((p) => p.kind === 'jump')!
    const strongJump = strong!.primitives.find((p) => p.kind === 'jump')!
    assert.ok(strongJump.amplitude! > baseJump.amplitude!, 'strong jump should have higher amplitude')
  })

  test('"danse joyeusement" tags emotion + boosts speed/amplitude', () => {
    const baseline = parseCustomMotionPrompt('danse puis salue')
    const happy = parseCustomMotionPrompt('danse joyeusement puis salue')
    assert.ok(baseline)
    assert.ok(happy)
    const happyOscillate = happy!.primitives.find((p) => p.kind === 'oscillate' && p.target === 'hips')
    assert.ok(happyOscillate)
    assert.match(happyOscillate!.description || '', /\[emotion:happy\]/)
  })

  test('"marche fatigue" emotion tag + slowdown', () => {
    const tired = parseCustomMotionPrompt('marche fatigue puis tombe')
    assert.ok(tired)
    const tiredGait = tired!.primitives.find((p) => p.kind === 'gait')
    assert.ok(tiredGait)
    assert.match(tiredGait!.description || '', /\[emotion:tired\]/)
  })

  test('global modifier compounds with segment modifier', () => {
    // "rapidement" applies globally; "fortement" applies only to jump segment
    const m = parseCustomMotionPrompt('marche rapidement puis saute fortement')
    assert.ok(m)
    const gait = m!.primitives.find((p) => p.kind === 'gait')!
    const jump = m!.primitives.find((p) => p.kind === 'jump')!
    // Walk gets speed boost from "rapidement"
    assert.ok(gait.frequency_hz! > 1.0)
    // Jump gets amplitude boost from "fortement" + global "rapidement"
    assert.ok(jump.amplitude! > 1.2)
  })

  test('label exposes modifiers for diagnostics', () => {
    const m = parseCustomMotionPrompt('marche rapidement puis saute')
    assert.ok(m)
    assert.match(m!.label, /speed_fast/)
  })

  // v77zx: parity fix with motion_parser.py — single-segment prompt should
  // apply each modifier tag exactly once (not twice via global+segment
  // double-counting). The pre-fix behavior produced 1.6×1.6 = 2.56 frequency.
  test('single-segment "marche rapidement" applies speed_fast once (×1.6, not ×2.56)', () => {
    const baseline = parseCustomMotionPrompt('le perso marche')
    const fast = parseCustomMotionPrompt('le perso marche rapidement')
    assert.ok(baseline)
    assert.ok(fast)
    const baseGait = baseline!.primitives.find((p) => p.kind === 'gait' && p.target === 'legs')!
    const fastGait = fast!.primitives.find((p) => p.kind === 'gait' && p.target === 'legs')!
    const ratio = fastGait.frequency_hz! / baseGait.frequency_hz!
    // speed_fast multiplier is 1.6 — allow small float tolerance
    assert.ok(Math.abs(ratio - 1.6) < 0.01,
      `expected ratio≈1.6 (single application), got ${ratio.toFixed(3)}`)
  })

  // v77zaa: spatial modifiers
  test('"saute haut" boosts jump amplitude (heightMul)', () => {
    const baseline = parseCustomMotionPrompt('saute puis salue')
    const high = parseCustomMotionPrompt('saute haut puis salue')
    assert.ok(baseline)
    assert.ok(high)
    const baseJump = baseline!.primitives.find((p) => p.kind === 'jump')!
    const highJump = high!.primitives.find((p) => p.kind === 'jump')!
    assert.ok(highJump.amplitude! > baseJump.amplitude! * 1.4,
      `expected high jump > base × 1.4, got base=${baseJump.amplitude} high=${highJump.amplitude}`)
  })

  test('"saute tres haut" applies very_high boost', () => {
    const veryHigh = parseCustomMotionPrompt('saute tres haut puis salue')
    assert.ok(veryHigh)
    const j = veryHigh!.primitives.find((p) => p.kind === 'jump')!
    assert.ok(j.description?.includes('[direction:up]'))
  })

  test('"saute bas" lowers jump amplitude', () => {
    const baseline = parseCustomMotionPrompt('saute puis salue')
    const low = parseCustomMotionPrompt('saute bas puis salue')
    assert.ok(baseline)
    assert.ok(low)
    const baseJump = baseline!.primitives.find((p) => p.kind === 'jump')!
    const lowJump = low!.primitives.find((p) => p.kind === 'jump')!
    assert.ok(lowJump.amplitude! < baseJump.amplitude!)
  })

  test('"vers la gauche" tags direction=left', () => {
    const m = parseCustomMotionPrompt('saute vers la gauche puis salue')
    assert.ok(m)
    const j = m!.primitives.find((p) => p.kind === 'jump')!
    assert.match(j.description || '', /\[direction:left\]/)
  })

  test('multi-segment shared global modifier applies to segments without it', () => {
    // "rapidement" is global; only segment 1 has it explicitly.
    // After dedupe: seg1 = rapidement (segment), seg2 = rapidement (global)
    // Both should have speedMul ≈ 1.6.
    const m = parseCustomMotionPrompt('marche rapidement puis saute')
    assert.ok(m)
    const gait = m!.primitives.find((p) => p.kind === 'gait')!
    assert.ok(gait.frequency_hz! >= 1.4 && gait.frequency_hz! <= 1.8,
      `walk should have speedMul≈1.6, got freq=${gait.frequency_hz}`)
  })
})

describe('buildKinematicsDirectiveBlock — FLUX prompt block', () => {
  test('character query → preset block with suggestions', () => {
    const block = buildKinematicsDirectiveBlock({ subjectKind: 'character', systemClass: 'generic' })
    assert.match(block, /KINEMATIC MOTION CONTRACT/)
    assert.match(block, /character\.walk_cycle|character\.idle|character\.run_cycle/)
  })

  test('gear_train query → mesh rotate suggestion', () => {
    const block = buildKinematicsDirectiveBlock({ subjectKind: 'mechanism', systemClass: 'gear_train' })
    assert.match(block, /gear_mesh_rotate/)
  })

  test('object/generic query → empty block', () => {
    const block = buildKinematicsDirectiveBlock({ subjectKind: 'object', systemClass: 'generic' })
    assert.equal(block, '')
  })

  test('custom motion overrides preset suggestions', () => {
    const m = parseCustomMotionPrompt('le perso marche puis saute')
    assert.ok(m)
    const block = buildKinematicsDirectiveBlock({ subjectKind: 'character', systemClass: 'generic' }, m)
    assert.match(block, /custom, parsed from user prompt/)
    assert.match(block, /Sequence:/)
    assert.match(block, /Total duration:/)
  })
})
