#!/usr/bin/env node
// Real TypeScript rules of the generation screen (Node type stripping).
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  animationProgress,
  codePhaseIndex,
  mascotStateFor,
  resolvePhaseIndex,
  stageForJob,
  threeDPhaseForStage,
} from '../src/components/generationFx/fxPhases.ts'

const IMAGE = ['Analyse du prompt', 'Référence visuelle', 'Diffusion FLUX', 'Édition Kontext', 'Finalisation']
const THREE_D = ['Analyse', 'Référence photo', 'Sculpture 3D', 'Matériaux & zones', 'Animation', 'Finalisation']
const CHAT = ['Analyse', 'Plan', 'Brouillon', 'Vérification', 'Raffinage', 'Livraison']

test('explicit index, step label and phase name resolve the real phase', () => {
  assert.equal(resolvePhaseIndex('image', IMAGE, { index: 3, prev: 0 }), 3)
  assert.equal(resolvePhaseIndex('image', IMAGE, { text: 'Étape 3/5 · Diffusion FLUX — pas 4/28', prev: 0 }), 2)
  assert.equal(resolvePhaseIndex('3d', THREE_D, { text: 'Référence photo — multi-vues prêtes', prev: 0 }), 1)
  assert.equal(resolvePhaseIndex('conversation', CHAT, { text: 'verify', prev: 0 }), 3)
  assert.equal(codePhaseIndex('streaming'), 3)
  assert.equal(codePhaseIndex('inconnu'), undefined)
})

test('a step label over another count is scaled, never out of range', () => {
  assert.equal(resolvePhaseIndex('3d', THREE_D, { text: 'Étape 5/5', prev: 0 }), 5)
  assert.equal(resolvePhaseIndex('image', IMAGE, { text: 'étape 9/9', prev: 0 }), 4)
})

test('without any signal the previous phase is kept (no reset to the first)', () => {
  assert.equal(resolvePhaseIndex('3d', THREE_D, { text: 'photo validée (score 0.81)', prev: 2 }), 2)
})

test('once a producer gave explicit phases, coarse percentages no longer move the phase', () => {
  // ModelView maps every Python stage to 82–95 %: 0.9 would wrongly read as "Animation"
  assert.equal(resolvePhaseIndex('3d', THREE_D, { progress: 0.9, prev: 2 }), 4)
  assert.equal(resolvePhaseIndex('3d', THREE_D, { progress: 0.9, prev: 2, explicit: true }), 2)
})

test('pipeline stage names map to the 3D screen phases', () => {
  assert.equal(threeDPhaseForStage('reference'), 1)
  assert.equal(threeDPhaseForStage('shape_run'), 2)
  assert.equal(threeDPhaseForStage('texture_run'), 3)
  assert.equal(threeDPhaseForStage('rig'), 4)
  assert.equal(threeDPhaseForStage('export'), 5)
  assert.equal(threeDPhaseForStage('memoire'), null, 'service lines do not move the phase')
})

test('every stage name actually printed by the 3D pipelines and the Blender bridge is mapped', async () => {
  const fs = await import('node:fs')
  const dir = new URL('../python-services/', import.meta.url)
  const files = ['aurora_3d_pipeline.py', 'blender_bridge.py', 'scene_process.py', 'neural_process.py', 'texture_fidelity.py', 'rig_skin_binding.py', 'semantic_animation.py']
  const service = new Set(['memoire', 'vram', 'error', 'confirm_req'])
  const unmapped = new Set()
  for (const f of files) {
    let text = ''
    try { text = fs.readFileSync(new URL(f, dir), 'utf8') } catch { continue }
    for (const m of text.matchAll(/PROGRESS:([a-z_]+):/g)) if (!service.has(m[1]) && threeDPhaseForStage(m[1]) == null) unmapped.add(m[1])
    for (const m of text.matchAll(/emit\(\s*["']([a-z_]+)["']/g)) if (!service.has(m[1]) && threeDPhaseForStage(m[1]) == null) unmapped.add(m[1])
  }
  assert.deepEqual([...unmapped], [], `stages that would not move the screen: ${[...unmapped].join(', ')}`)
  assert.equal(threeDPhaseForStage('matieres'), 3)
  assert.equal(threeDPhaseForStage('procedural'), 2)
  assert.equal(threeDPhaseForStage('livraison'), 5)
})

test('character state follows the real loading state', () => {
  assert.equal(mascotStateFor({ stage: 'queued', phaseIdx: 0 }), 'waiting')
  assert.equal(mascotStateFor({ stage: 'preparing', phaseIdx: 0 }), 'thinking')
  assert.equal(mascotStateFor({ stage: 'running', phaseIdx: 2, phaseName: 'Diffusion FLUX' }), 'working')
  assert.equal(mascotStateFor({ stage: 'running', phaseIdx: 3, phaseName: 'Vérification' }), 'checking')
  assert.equal(mascotStateFor({ stage: 'running', phaseIdx: 2, ask: true }), 'asking')
  assert.equal(mascotStateFor({ stage: 'running', phaseIdx: 2, reveal: true }), 'success')
  assert.equal(stageForJob({ status: 'queued', phase: 'idle' }), 'queued')
  assert.equal(stageForJob({ status: 'running', phase: 'prepare' }), 'preparing')
  assert.equal(stageForJob({ status: 'running', phase: 'cleanup' }), 'finalizing')
  assert.equal(stageForJob(null), 'running')
})

test('animation follows measurement first, then the real phase, and never announces the end', () => {
  assert.equal(animationProgress({ measured: 0.42, phaseIdx: 0, phaseCount: 5, phaseAgeMs: 0, elapsedMs: 0, phaseReported: true }), 0.42)
  const atPhase = animationProgress({ measured: null, phaseIdx: 2, phaseCount: 5, phaseAgeMs: 0, elapsedMs: 9e9, phaseReported: true })
  assert.equal(atPhase, 0.4)
  const longPhase = animationProgress({ measured: null, phaseIdx: 4, phaseCount: 5, phaseAgeMs: 9e9, elapsedMs: 9e9, phaseReported: true })
  assert.ok(longPhase < 0.98, `bounded (${longPhase})`)
  const noInfo = animationProgress({ measured: null, phaseIdx: 0, phaseCount: 5, phaseAgeMs: 9e9, elapsedMs: 9e9, phaseReported: false })
  assert.ok(noInfo <= 0.6)
})
