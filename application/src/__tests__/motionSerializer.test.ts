/**
 * v77zn: validate motion serializer round-trip + schema invariants.
 *
 * The Blender-side python-services/motion_baker.py reads the JSON shape
 * emitted by serializeMotionForBlender. Any change to the wire format
 * here is a breaking change for the baker — these tests pin the schema.
 *
 * Run: node --experimental-strip-types src/__tests__/motionSerializer.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { selectKinematicPresets, parseCustomMotionPrompt } from '../services/kinematicsLibrary.ts'
import { serializeMotionForBlender, serializeMotionToJson } from '../services/motionSerializer.ts'

describe('serializeMotionForBlender — schema invariants', () => {
  test('emits stable schema tag', () => {
    const presets = selectKinematicPresets({ subjectKind: 'character', systemClass: 'generic' })
    const walk = presets.find((p) => p.id === 'character.walk_cycle')
    assert.ok(walk)
    const out = serializeMotionForBlender(walk!)
    assert.equal(out.schema, 'aurora.motion.v1')
  })

  test('preserves id, label, source, loop', () => {
    const presets = selectKinematicPresets({ subjectKind: 'character', systemClass: 'generic' })
    const walk = presets.find((p) => p.id === 'character.walk_cycle')!
    const out = serializeMotionForBlender(walk)
    assert.equal(out.id, 'character.walk_cycle')
    assert.equal(out.source, 'preset')
    assert.equal(out.loop, true)
    assert.ok(out.label.length > 0)
  })

  test('default fps=24, frame_count = round(duration * fps)', () => {
    const presets = selectKinematicPresets({ subjectKind: 'character', systemClass: 'generic' })
    const walk = presets.find((p) => p.id === 'character.walk_cycle')!
    const out = serializeMotionForBlender(walk)
    assert.equal(out.fps, 24)
    assert.equal(out.duration_seconds, 1.0)
    assert.equal(out.frame_count, 24)
  })

  test('custom fps recomputes frame_count', () => {
    const presets = selectKinematicPresets({ subjectKind: 'character', systemClass: 'generic' })
    const walk = presets.find((p) => p.id === 'character.walk_cycle')!
    const out = serializeMotionForBlender(walk, { fps: 30 })
    assert.equal(out.fps, 30)
    assert.equal(out.frame_count, 30)
  })

  test('frame_count is at least 1', () => {
    const presets = selectKinematicPresets({ subjectKind: 'character', systemClass: 'generic' })
    const sit = presets.find((p) => p.id === 'character.sit')!
    // sit has duration_seconds=0 (static pose) → frame_count must be ≥ 1
    const out = serializeMotionForBlender(sit)
    assert.ok(out.frame_count >= 1)
  })

  test('primitives normalized (null-safe)', () => {
    const presets = selectKinematicPresets({ subjectKind: 'character', systemClass: 'generic' })
    const walk = presets.find((p) => p.id === 'character.walk_cycle')!
    const out = serializeMotionForBlender(walk)
    for (const p of out.primitives) {
      assert.ok(typeof p.kind === 'string')
      // Each optional field must be present as either typed value or null
      assert.ok(p.target === null || typeof p.target === 'string')
      assert.ok(p.axis === null || ['x', 'y', 'z', 'auto'].includes(p.axis))
      assert.ok(p.amplitude === null || typeof p.amplitude === 'number')
      assert.ok(p.frequency_hz === null || typeof p.frequency_hz === 'number')
    }
  })

  test('mechanism preset (gear_mesh_rotate) serializes cleanly', () => {
    const presets = selectKinematicPresets({ subjectKind: 'mechanism', systemClass: 'gear_train' })
    const gear = presets.find((p) => p.id === 'mechanism.gear_mesh_rotate')!
    const out = serializeMotionForBlender(gear)
    assert.equal(out.id, 'mechanism.gear_mesh_rotate')
    assert.equal(out.loop, true)
    assert.ok(out.primitives.every((p) => p.kind === 'rotate'))
  })

  test('custom motion (parsed) serializes with source=custom', () => {
    const m = parseCustomMotionPrompt('le perso marche puis saute')!
    const out = serializeMotionForBlender(m)
    assert.equal(out.source, 'custom')
    assert.equal(out.loop, false)
    assert.ok(out.primitives.length >= 4)
  })

  test('serializeMotionToJson round-trips through JSON.parse', () => {
    const presets = selectKinematicPresets({ subjectKind: 'character', systemClass: 'generic' })
    const wave = presets.find((p) => p.id === 'character.wave')!
    const json = serializeMotionToJson(wave, { pretty: true })
    const parsed = JSON.parse(json)
    assert.equal(parsed.schema, 'aurora.motion.v1')
    assert.equal(parsed.id, 'character.wave')
  })

  test('NaN/Infinity in primitive numbers → null (defensive)', () => {
    const broken = {
      id: 'test.broken',
      label: 'Broken',
      description: '',
      appliesTo: { subjectKind: ['character' as const] },
      primitives: [
        // @ts-expect-error: intentional bad input for defensive coverage
        { kind: 'rotate' as const, axis: 'x' as const, amplitude: NaN, frequency_hz: Infinity },
      ],
      promptDirective: '',
      duration_seconds: 1,
      loop: true,
      source: 'preset' as const,
    }
    const out = serializeMotionForBlender(broken)
    assert.equal(out.primitives[0].amplitude, null)
    assert.equal(out.primitives[0].frequency_hz, null)
  })
})
