/**
 * Tests for the batched expert-uplift modules :
 *   - threeDLodAndRig
 *   - imagePromptBuilder
 *   - voicePhonemes
 *   - drawingStyleAndSvg
 *
 * Run: node --experimental-strip-types --test src/__tests__/expertUpliftBatch.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

// --- 3D ---------------------------------------------------------------------
import {
  defaultExportPlan,
  defaultRigForCategory,
  humanoidMixamoRig,
  lodPlanForCategory,
  validateMesh,
} from '../services/threeDLodAndRig.ts'

describe('3D LOD + rig', () => {
  test('lodPlanForCategory gives 4 levels with decreasing budget', () => {
    const plan = lodPlanForCategory('character')
    assert.equal(plan.length, 4)
    for (let i = 1; i < plan.length; i += 1) {
      assert.ok(plan[i].faceBudget < plan[i - 1].faceBudget)
    }
  })

  test('humanoid Mixamo rig exposes Hips root and 4 IK chains', () => {
    const rig = humanoidMixamoRig()
    assert.equal(rig.kind, 'humanoid-mixamo')
    const root = rig.bones.find((b) => b.parent === null)
    assert.equal(root?.id, 'Hips')
    assert.equal(rig.ikChains.length, 4)
  })

  test('mech category gets mech-articulated rig', () => {
    const r = defaultRigForCategory('mech')
    assert.equal(r.kind, 'mech-articulated')
  })

  test('static category gets static rig', () => {
    const r = defaultRigForCategory('object')
    assert.equal(r.kind, 'static')
  })

  test('default export plan for character includes animations', () => {
    const presets = defaultExportPlan('character')
    assert.ok(presets.length >= 3)
    assert.ok(presets.find((p) => p.format === 'glb')?.includeAnimations)
  })

  test('mesh validation blocks print when not watertight', () => {
    const r = validateMesh({
      faceCount: 50000, vertexCount: 25000,
      nonManifoldEdgeCount: 0, selfIntersectionCount: 0, duplicateVertexCount: 0,
      invertedNormalCount: 0, openHoleCount: 1, overlappingUvCount: 0,
      hasUvs: true, volume: 0.1, surfaceArea: 1.5, faceBudgetLod0: 140000, useCase: 'print',
    })
    assert.equal(r.watertight, false)
    assert.equal(r.blockingForExport, true)
  })

  test('mesh validation accepts preview with minor issues', () => {
    const r = validateMesh({
      faceCount: 50000, vertexCount: 25000,
      nonManifoldEdgeCount: 0, selfIntersectionCount: 0, duplicateVertexCount: 0,
      invertedNormalCount: 0, openHoleCount: 1, overlappingUvCount: 0,
      hasUvs: true, volume: 0.1, surfaceArea: 1.5, faceBudgetLod0: 140000, useCase: 'preview',
    })
    assert.equal(r.blockingForExport, false)
  })
})

// --- Image ------------------------------------------------------------------
import { buildPrompt, parseBrief } from '../services/imagePromptBuilder.ts'

describe('Image prompt builder', () => {
  test('builds positive prompt with style qualifiers', () => {
    const out = buildPrompt({ subject: 'samurai hero', style: 'cinematic', lighting: 'golden-hour' })
    assert.ok(out.positive.includes('samurai hero'))
    assert.ok(out.positive.toLowerCase().includes('golden hour'))
    assert.ok(out.positive.toLowerCase().includes('anamorphic'))
  })

  test('negative prompt depends on style', () => {
    const photo = buildPrompt({ subject: 'x', style: 'photorealistic' })
    const anime = buildPrompt({ subject: 'x', style: 'anime-clean' })
    assert.ok(photo.negative.toLowerCase().includes('cartoon'))
    assert.ok(anime.negative.toLowerCase().includes('photorealistic'))
  })

  test('aspect ratio 9:16 → 768x1344', () => {
    const out = buildPrompt({ subject: 'x', aspectRatio: '9:16' })
    assert.equal(out.width, 768)
    assert.equal(out.height, 1344)
  })

  test('highResolution triggers x4 upscale plan', () => {
    const out = buildPrompt({ subject: 'x', highResolution: true })
    assert.equal(out.upscalePlan.kind, 'realesrgan-x4')
    assert.equal(out.upscalePlan.targetWidth, 4096)
  })

  test('parseBrief extracts style + lighting + palette', () => {
    const b = parseBrief('aquarelle d\'un samouraï au coucher de soleil avec #ff5a1f et #3aa4ff, haute résolution')
    assert.equal(b.style, 'aquarelle')
    assert.equal(b.lighting, 'golden-hour')
    assert.equal(b.highResolution, true)
    assert.ok((b.paletteHints ?? []).length >= 2)
  })

  test('exif metadata includes prompt as userComment', () => {
    const out = buildPrompt({ subject: 'samurai', style: 'cinematic' })
    assert.equal(out.exif.userComment, out.positive)
    assert.ok(out.exif.software.includes('Aurora'))
  })
})

// --- Voice ------------------------------------------------------------------
import {
  FR_PHONEME_TABLE,
  pickProfileForContext,
  phonemeToViseme,
  textToVisemes,
  transition,
  VAD_RMS_THRESHOLD,
  VOICE_PROFILES,
} from '../services/voicePhonemes.ts'

describe('Voice phonemes + profiles', () => {
  test('phoneme table covers > 30 sounds', () => {
    assert.ok(FR_PHONEME_TABLE.length >= 30)
  })

  test('p/b/m share mm viseme', () => {
    assert.equal(phonemeToViseme('p'), 'mm')
    assert.equal(phonemeToViseme('b'), 'mm')
    assert.equal(phonemeToViseme('m'), 'mm')
  })

  test('unknown ipa falls back to rest', () => {
    assert.equal(phonemeToViseme('ZZ'), 'rest')
  })

  test('textToVisemes merges adjacent same-viseme frames', () => {
    const out = textToVisemes('mama', 200)
    // m+a+m+a → mm-aa-mm-aa, no merge.
    const visemes = out.map((f) => f.viseme)
    assert.ok(visemes.includes('mm'))
    assert.ok(visemes.includes('aa'))
  })

  test('pickProfileForContext maps cours → prof', () => {
    assert.equal(pickProfileForContext('cours').id, 'aurora-prof')
    assert.equal(pickProfileForContext('hype').id, 'aurora-hype')
    assert.equal(pickProfileForContext('meditation').id, 'aurora-zen')
  })

  test('5 voice profiles available', () => {
    assert.ok(VOICE_PROFILES.length >= 5)
  })

  test('VAD state machine: idle → speaking → fading on user voice', () => {
    let mode = transition('idle', { kind: 'start_speak' })
    assert.equal(mode, 'speaking')
    mode = transition(mode, { kind: 'user_voice_detected', rms: VAD_RMS_THRESHOLD + 0.01 })
    assert.equal(mode, 'fading')
    mode = transition(mode, { kind: 'user_voice_detected', rms: VAD_RMS_THRESHOLD + 0.01 })
    assert.equal(mode, 'listening')
    mode = transition(mode, { kind: 'user_voice_lost', sinceMs: 800 })
    assert.equal(mode, 'processing')
    mode = transition(mode, { kind: 'speech_recognised' })
    assert.equal(mode, 'idle')
  })

  test('VAD ignores noise below threshold', () => {
    const mode = transition('speaking', { kind: 'user_voice_detected', rms: 0.01 })
    assert.equal(mode, 'speaking')
  })
})

// --- Drawing ----------------------------------------------------------------
import {
  AURORA_PALETTE,
  classifyDrawingIntent,
  emptyDoc,
  flowChartDoc,
  gridOverlay,
  planRefinementPasses,
  serialise,
} from '../services/drawingStyleAndSvg.ts'

describe('Drawing style classifier + SVG', () => {
  test('schema brief → schema-technique', () => {
    const c = classifyDrawingIntent('schéma technique d\'un circuit avec labels')
    assert.equal(c.intent, 'schema-technique')
    assert.equal(c.preferredOutput, 'svg')
  })

  test('aquarelle brief → croquis-artistique', () => {
    const c = classifyDrawingIntent('aquarelle artistique d\'un paysage')
    assert.equal(c.intent, 'croquis-artistique')
  })

  test('flowchart brief → diagramme-flow with svg output', () => {
    const c = classifyDrawingIntent('flowchart d\'un algorithme')
    assert.equal(c.intent, 'diagramme-flow')
    assert.equal(c.preferredOutput, 'svg')
  })

  test('empty / random brief → fallback sketch-rapide low confidence', () => {
    const c = classifyDrawingIntent('zorglub')
    assert.equal(c.intent, 'sketch-rapide')
    assert.ok(c.confidence <= 0.3)
  })

  test('serialise returns well-formed SVG XML', () => {
    const doc = emptyDoc({ x: 0, y: 0, w: 100, h: 100 })
    doc.elements.push({ kind: 'circle', cx: 50, cy: 50, r: 20, fill: AURORA_PALETTE.primary })
    const xml = serialise(doc)
    assert.ok(xml.startsWith('<?xml'))
    assert.ok(xml.includes('viewBox="0 0 100 100"'))
    assert.ok(xml.includes('<circle'))
    assert.ok(xml.includes('</svg>'))
  })

  test('serialise escapes text content', () => {
    const doc = emptyDoc()
    doc.elements.push({ kind: 'text', x: 0, y: 0, text: 'A & <B>' })
    const xml = serialise(doc)
    assert.ok(xml.includes('A &amp; &lt;B&gt;'))
  })

  test('flowChartDoc renders nodes and edges', () => {
    const doc = flowChartDoc(
      [{ id: 'a', label: 'Start', x: 0, y: 0 }, { id: 'b', label: 'End', x: 200, y: 200 }],
      [{ from: 'a', to: 'b', label: 'go' }],
    )
    const xml = serialise(doc)
    assert.ok(xml.includes('Start'))
    assert.ok(xml.includes('End'))
    assert.ok(xml.includes('go'))
  })

  test('gridOverlay creates lines on both axes', () => {
    const lines = gridOverlay({ x: 0, y: 0, w: 100, h: 100 }, 25)
    // (100/25 + 1) = 5 vertical + 5 horizontal = 10
    assert.equal(lines.length, 10)
  })

  test('planRefinementPasses gives 3 passes for technical schema', () => {
    const c = classifyDrawingIntent('schema technique')
    const passes = planRefinementPasses(c)
    assert.ok(passes.length >= 3)
    assert.equal(passes[0].goal, 'composition')
  })
})
