#!/usr/bin/env node
// Synchronisation de l'écran Image avec ComfyUI : chaque nœud réellement exécuté du
// vrai graphe FLUX.2 donne sa sous-étape ; les pas ne viennent que de l'échantillonneur ;
// les messages d'une autre exécution sont ignorés (Node, vraies sources TypeScript).
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createFluxWorkflow } from '../src/utils/fluxWorkflow.ts'
import {
  classifyComfyNode,
  diffusionPhaseFraction,
  fluxSigmaAt,
  imagePatchForEvent,
  interpretComfyMessage,
  medianStepSeconds,
  nodeClassesOf,
} from '../src/components/generationFx/comfyStages.ts'
import { MODULE_PHASE_RANGES } from '../src/components/generationFx/fxPhases.ts'

const RANGES = MODULE_PHASE_RANGES.image
const wf = createFluxWorkflow({ prompt: 'vase', width: 1024, height: 1024, steps: 28, filenamePrefix: 't', upscaleTargetMaxEdge: 4096 })
const classes = nodeClassesOf(wf)
const idOf = (re) => Object.entries(classes).find(([, c]) => re.test(c))?.[0]
const run = { promptId: 'p1', module: 'image', phaseIndex: 2, nodeClass: classes }

test('every node of the production FLUX.2 graph maps to a real sub-stage', () => {
  const stages = new Set(Object.values(classes).map(classifyComfyNode))
  for (const s of ['load_model', 'load_text_encoder', 'load_vae', 'encode_text', 'sampling', 'decode', 'save']) assert.ok(stages.has(s), s)
  assert.ok(stages.has('upscale'), 'RealESRGAN present when 4K is asked')
})

test('a real run walks queue → loading → encoding → steps → decode → save without going back', () => {
  let state = { stage: 'queued', lastLoggedStep: -1 }
  const seen = []
  const feed = (msg) => {
    const ev = interpretComfyMessage(msg, run, state)
    if (!ev) return null
    seen.push(ev.stage)
    state = { stage: ev.stage, lastLoggedStep: ev.log && typeof ev.step === 'number' ? ev.step : state.lastLoggedStep }
    return ev
  }
  assert.equal(feed({ type: 'status', data: { status: { exec_info: { queue_remaining: 3 } } } }).label, 'En file ComfyUI — 2 rendu(s) devant')
  feed({ type: 'execution_start', data: { prompt_id: 'p1' } })
  assert.equal(feed({ type: 'executing', data: { node: idOf(/UnetLoaderGGUF|UNETLoader/), prompt_id: 'p1' } }), null, 'same sub-stage: no duplicate')
  assert.equal(feed({ type: 'executing', data: { node: idOf(/^CLIPLoader/), prompt_id: 'p1' } })?.stage, 'load_text_encoder')
  assert.equal(feed({ type: 'executing', data: { node: idOf(/^CLIPTextEncode/), prompt_id: 'p1' } })?.stage, 'encode_text')
  const sampler = idOf(/Sampler/)
  feed({ type: 'executing', data: { node: sampler, prompt_id: 'p1' } })
  const step = feed({ type: 'progress', data: { value: 7, max: 28, node: sampler, prompt_id: 'p1' } })
  assert.equal(step.step, 7)
  assert.match(step.label, /pas 7\/28 \(25 %\)/)
  // un message tardif d'encodage ne fait pas reculer l'écran
  assert.equal(feed({ type: 'executing', data: { node: idOf(/^CLIPTextEncode/), prompt_id: 'p1' } }), null)
  assert.equal(feed({ type: 'executing', data: { node: idOf(/VAEDecode/), prompt_id: 'p1' } })?.stage, 'decode')
  const up = feed({ type: 'progress', data: { value: 3, max: 16, node: idOf(/ImageUpscaleWithModel/), prompt_id: 'p1' } })
  assert.equal(up.stage, 'upscale')
  assert.equal(up.step, undefined, 'upscale tiles are not diffusion steps')
  assert.equal(feed({ type: 'executed', data: { node: idOf(/^SaveImage/), prompt_id: 'p1' } })?.stage, 'save')
  assert.deepEqual(seen.filter((s, i) => s !== seen[i - 1]), ['queued', 'load_model', 'load_text_encoder', 'encode_text', 'sampling', 'decode', 'upscale', 'save'])
})

test('messages of another execution never drive the screen', () => {
  const state = { stage: 'sampling', lastLoggedStep: -1 }
  assert.equal(interpretComfyMessage({ type: 'progress', data: { value: 9, max: 9, node: '99', prompt_id: 'other' } }, run, state), null)
  assert.equal(interpretComfyMessage({ type: 'executing', data: { node: '3', prompt_id: 'other' } }, run, state), null)
})

test('screen patch: diffusion phase from the registered graph, Kontext stays on its step, upscale is finalisation', () => {
  const ev = { stage: 'sampling', label: '', step: 14, max: 28 }
  const p = imagePatchForEvent(ev, run, RANGES)
  assert.equal(p.phaseIndex, 2)
  assert.equal(p.progressKind, 'fine')
  assert.ok(p.progress > RANGES[2][0] && p.progress < RANGES[2][1])
  assert.equal(imagePatchForEvent(ev, { ...run, phaseIndex: 3 }, RANGES).phaseIndex, 3)
  const load = imagePatchForEvent({ stage: 'load_model', label: '' }, run, RANGES)
  assert.equal(load.progressKind, 'stage')
  assert.equal(load.phaseFraction, undefined, 'a milestone is not a measured speed')
  assert.equal(imagePatchForEvent({ stage: 'upscale', label: '', subStep: 4, subMax: 16 }, run, RANGES).phaseIndex, 4)
  assert.ok(diffusionPhaseFraction('encode_text') < diffusionPhaseFraction('sampling', 1, 28))
})

test('measured step speed and scheduler curve', () => {
  assert.equal(medianStepSeconds([0]), null)
  assert.equal(medianStepSeconds([0, 1000, 2100, 3000, 4000]), 1)
  assert.equal(fluxSigmaAt(0, 28), 1)
  assert.equal(fluxSigmaAt(28, 28), 0)
  assert.ok(fluxSigmaAt(14, 28) > 0.5, 'shifted schedule keeps more noise mid-way')
})
