/**
 * v77zy: validate quadruped + vehicle anatomy directive blocks.
 *
 * Mirror of humanoidAnatomy.test.ts pattern:
 *   - block fires only for matching subject + prompt cues
 *   - off-target subjects produce empty string
 *   - previousMetrics injects specific corrections per failure category
 *
 * Run: node --experimental-strip-types src/__tests__/subjectAnatomy.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildQuadrupedAnatomyBlock,
  buildVehicleAnatomyBlock,
} from '../services/subjectAnatomy.ts'

const CREATURE = { purpose: 'visual_preview' as const, subjectKind: 'creature' as const }
const CHARACTER = { purpose: 'character' as const, subjectKind: 'character' as const }
const VEHICLE = { purpose: 'product' as const, subjectKind: 'vehicle' as const }
const PRODUCT = { purpose: 'product' as const, subjectKind: 'product' as const }

describe('buildQuadrupedAnatomyBlock — fires only on quadruped cues', () => {
  test('chien prompt → block fired', () => {
    const block = buildQuadrupedAnatomyBlock(CREATURE, 'un chien qui galope dans un champ')
    assert.ok(block.length > 0)
    assert.match(block, /QUADRUPED ANATOMY DIRECTIVES/)
    assert.match(block, /Four distinct legs/)
  })

  test('cat / horse / lion prompts all match', () => {
    for (const subject of ['a cat', 'a horse', 'un loup', 'a lion', 'a leopard', 'a kangaroo']) {
      const block = buildQuadrupedAnatomyBlock(CREATURE, subject)
      assert.ok(block.length > 0, `should fire on "${subject}"`)
    }
  })

  test('non-quadruped creature (dragon flying) → no block', () => {
    const block = buildQuadrupedAnatomyBlock(CREATURE, 'a dragon flying over the mountains')
    assert.equal(block, '')
  })

  test('character intent → no block (humanoid handled elsewhere)', () => {
    const block = buildQuadrupedAnatomyBlock(CHARACTER, 'un guerrier elfique')
    assert.equal(block, '')
  })

  test('realistic mode adds photorealistic fur directive', () => {
    const block = buildQuadrupedAnatomyBlock(CREATURE, 'a realistic horse standing in pasture')
    assert.match(block, /photorealistic fur/)
  })

  test('previousMetrics injects body ratio correction', () => {
    const block = buildQuadrupedAnatomyBlock(CREATURE, 'un chien', { bodyToShoulderRatio: 0.8 })
    assert.match(block, /PREVIOUS ATTEMPT FAILED.*ratio/i)
    assert.match(block, /horizontal/)
  })

  test('previousMetrics injects leg-count correction', () => {
    const block = buildQuadrupedAnatomyBlock(CREATURE, 'un chat', { legCountVisible: 2 })
    assert.match(block, /only 2 leg/)
    assert.match(block, /ALL 4 LEGS/)
  })

  test('previousMetrics injects head/tail corrections', () => {
    const block = buildQuadrupedAnatomyBlock(CREATURE, 'un cheval', {
      headToBodyRatio: 0.4,
      tailToBodyRatio: 1.2,
    })
    assert.match(block, /head was oversized/)
    assert.match(block, /tail longer than body/)
  })

  test('null/undefined metrics → no PREVIOUS ATTEMPT block', () => {
    const block = buildQuadrupedAnatomyBlock(CREATURE, 'un chat', null)
    assert.doesNotMatch(block, /PREVIOUS ATTEMPT/)
  })
})

describe('v77zae species detection (quadruped)', () => {
  test('chien → dog species ratios in directive', () => {
    const block = buildQuadrupedAnatomyBlock(CREATURE, 'un chien labrador')
    assert.match(block, /Species detected: dog/)
    assert.match(block, /1\.4|1\.5/)  // body/shoulder ratio for dog
  })

  test('chat → cat species (compact build)', () => {
    const block = buildQuadrupedAnatomyBlock(CREATURE, 'un chat tigre')
    // Order: chat matches first. Could also match tiger via the 'tigre' keyword.
    assert.match(block, /Species detected: (cat|tiger)/)
  })

  test('cheval → horse species (long body, long snout)', () => {
    const block = buildQuadrupedAnatomyBlock(CREATURE, 'un cheval purebred')
    assert.match(block, /Species detected: horse/)
    assert.match(block, /Long pronounced snout/)
  })

  test('ours → bear species (very short tail)', () => {
    const block = buildQuadrupedAnatomyBlock(CREATURE, 'un ours brun')
    assert.match(block, /Species detected: bear/)
    assert.match(block, /very short/)
  })

  test('elephant → elephant species (massive head ratio)', () => {
    const block = buildQuadrupedAnatomyBlock(CREATURE, 'un elephant africain')
    assert.match(block, /Species detected: elephant/)
    assert.match(block, /trunk/)
  })

  test('generic creature without species → falls back to range', () => {
    const block = buildQuadrupedAnatomyBlock(CREATURE, 'a fantastic four-legged beast')
    assert.match(block, /1\.3 \(compact cat\) and 1\.7/)
  })
})

describe('v77zae vehicle class detection', () => {
  test('sports car → very low ground clearance', () => {
    const block = buildVehicleAnatomyBlock(VEHICLE, 'a Ferrari sports car')
    assert.match(block, /Class detected: sports_car/)
    assert.match(block, /very low/)
  })

  test('SUV → high ground clearance', () => {
    const block = buildVehicleAnatomyBlock(VEHICLE, 'a Range Rover suv')
    assert.match(block, /Class detected: suv/)
    assert.match(block, /high ground clearance/)
  })

  test('motorcycle → 2 wheels, no track', () => {
    const block = buildVehicleAnatomyBlock(VEHICLE, 'a Harley motorcycle')
    assert.match(block, /Class detected: motorcycle/)
    assert.match(block, /2 wheel/)
  })

  test('bus → 6 wheels + high height', () => {
    const block = buildVehicleAnatomyBlock(VEHICLE, 'a bus stopping at the station')
    assert.match(block, /Class detected: bus/)
  })

  test('generic car without class → falls back to default ratios', () => {
    const block = buildVehicleAnatomyBlock(VEHICLE, 'an unknown vehicle prototype')
    assert.match(block, /Wheelbase \(front axle to rear axle/)
  })
})

describe('buildVehicleAnatomyBlock — fires for vehicle subject', () => {
  test('vehicle subject → block fired', () => {
    const block = buildVehicleAnatomyBlock(VEHICLE, 'a sleek sports car')
    assert.ok(block.length > 0)
    assert.match(block, /VEHICLE ANATOMY DIRECTIVES/)
    assert.match(block, /4 wheel/)
  })

  test('non-vehicle subject → no block', () => {
    const block = buildVehicleAnatomyBlock(PRODUCT, 'a phone')
    assert.equal(block, '')
  })

  test('motorcycle prompt → 2-wheel mode', () => {
    const block = buildVehicleAnatomyBlock(VEHICLE, 'a motorcycle in motion')
    assert.match(block, /2 wheel/)
    assert.match(block, /Two-wheeled mode/)
  })

  test('truck prompt → 6+ wheel mode', () => {
    const block = buildVehicleAnatomyBlock(VEHICLE, 'a heavy duty truck')
    assert.match(block, /6 wheel/)
    assert.match(block, /Truck mode/)
  })

  test('previousMetrics injects wheelbase correction', () => {
    const block = buildVehicleAnatomyBlock(VEHICLE, 'a car', { wheelbaseToLengthRatio: 0.35 })
    assert.match(block, /PREVIOUS ATTEMPT FAILED.*wheelbase/i)
    assert.match(block, /push wheels to the corners/)
  })

  test('previousMetrics injects wheel-count correction', () => {
    const block = buildVehicleAnatomyBlock(VEHICLE, 'a car', { wheelCountVisible: 3 })
    assert.match(block, /3 wheel\(s\) visible/)
    assert.match(block, /expected 4/)
  })

  test('previousMetrics injects oversized-wheel correction', () => {
    const block = buildVehicleAnatomyBlock(VEHICLE, 'a car', { wheelToHeightRatio: 0.7 })
    assert.match(block, /wheels were oversized/)
  })

  test('null/undefined metrics → no PREVIOUS ATTEMPT block', () => {
    const block = buildVehicleAnatomyBlock(VEHICLE, 'a car', null)
    assert.doesNotMatch(block, /PREVIOUS ATTEMPT/)
  })
})
