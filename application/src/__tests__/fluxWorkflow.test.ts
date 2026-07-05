import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { createFluxWorkflow } from '../utils/fluxWorkflow.ts'
import { parseImageIntent } from '../utils/imagePromptParser.ts'

function findT5(workflow: Record<string, unknown>): string {
  for (const node of Object.values(workflow)) {
    const item = node as { class_type?: string; inputs?: Record<string, unknown> }
    if (item.class_type === 'CLIPTextEncodeFlux' && item.inputs) {
      return String(item.inputs.t5xxl || '')
    }
    if (item.class_type === 'CLIPTextEncode' && item.inputs) {
      return String(item.inputs.text || '')
    }
  }
  return ''
}

function findClipL(workflow: Record<string, unknown>): string {
  for (const node of Object.values(workflow)) {
    const item = node as { class_type?: string; inputs?: Record<string, unknown> }
    if (item.class_type === 'CLIPTextEncodeFlux' && item.inputs) {
      return String(item.inputs.clip_l || '')
    }
    if (item.class_type === 'CLIPTextEncode' && item.inputs) {
      return String(item.inputs.text || '')
    }
  }
  return ''
}

function findScheduler(workflow: Record<string, unknown>): { denoise: number; steps: number } | null {
  for (const node of Object.values(workflow)) {
    const item = node as { class_type?: string; inputs?: Record<string, unknown> }
    if (item.class_type === 'BasicScheduler' && item.inputs) {
      return {
        denoise: Number(item.inputs.denoise),
        steps: Number(item.inputs.steps),
      }
    }
  }
  return null
}

function findDualClipLoader(workflow: Record<string, unknown>): Record<string, unknown> | null {
  for (const node of Object.values(workflow)) {
    const item = node as { class_type?: string; inputs?: Record<string, unknown> }
    if (item.class_type === 'DualCLIPLoader' && item.inputs) return item.inputs
  }
  return null
}

function findNodeByClass(workflow: Record<string, unknown>, classType: string): { inputs?: Record<string, unknown> } | null {
  for (const node of Object.values(workflow)) {
    const item = node as { class_type?: string; inputs?: Record<string, unknown> }
    if (item.class_type === classType) return item
  }
  return null
}

describe('createFluxWorkflow - prompt negatif FLUX', () => {
  test('negativePrompt ne revient jamais dans le positif', () => {
    const workflow = createFluxWorkflow({
      prompt: 'a beautiful sunset',
      width: 1024,
      height: 1024,
      steps: 28,
      filenamePrefix: 'test',
      negativePrompt: 'XYZQVPDBUKJK_unique_token',
    })

    const t5 = findT5(workflow)

    assert.ok(!t5.includes('((avoid:'))
    assert.ok(!t5.includes('avoid:'))
    assert.ok(!t5.includes('XYZQVPDBUKJK_unique_token'))
  })

  test('clip_l reste libre du hack avoid', () => {
    const workflow = createFluxWorkflow({
      prompt: 'a sunset',
      width: 1024,
      height: 1024,
      steps: 28,
      filenamePrefix: 'test',
      negativePrompt: 'rain',
    })

    const clipL = findClipL(workflow)

    assert.ok(!clipL.includes('avoid'))
    assert.ok(!clipL.includes('((avoid:'))
  })
})

describe('createFluxWorkflow - styles', () => {
  test('pixel_art verrouille la grille et evite les regles photo', () => {
    const workflow = createFluxWorkflow({
      prompt: '32x32 sprite chevalier pixel art',
      width: 1024,
      height: 1024,
      steps: 28,
      filenamePrefix: 'pixel',
      style: 'pixel_art',
    })

    const t5 = findT5(workflow)
    const scheduler = findScheduler(workflow)

    assert.match(t5, /nearest-neighbor/i)
    assert.match(t5, /no anti-aliasing/i)
    assert.match(t5, /integer pixel grid/i)
    assert.ok(!t5.includes('native high-resolution detail'))
    assert.ok(!t5.includes('no blocky pixels'))
    assert.equal(scheduler?.steps, 36)
  })

  test('chaque style majeur ajoute ses contraintes de rendu', () => {
    const checks: Array<[string, RegExp]> = [
      ['realistic', /physically plausible materials/i],
      ['anime', /clean anime key visual/i],
      ['watercolor', /transparent pigment washes/i],
      ['technical_render', /CAD-like silhouette/i],
      ['comic', /bold ink outlines/i],
    ]

    for (const [style, marker] of checks) {
      const workflow = createFluxWorkflow({
        prompt: 'portrait heroique',
        width: 1024,
        height: 1024,
        steps: 28,
        filenamePrefix: 'style',
        style: style as Parameters<typeof createFluxWorkflow>[0]['style'],
      })

      assert.match(findT5(workflow), marker)
    }
  })

  test('creation complexe ne force pas une seule entite', () => {
    const workflow = createFluxWorkflow({
      prompt: 'scene de cirque avec un automate qui jongle avec trois cubes lumineux',
      width: 768,
      height: 768,
      steps: 20,
      filenamePrefix: 'scene',
      style: 'cinematic',
    })

    const t5 = findT5(workflow)

    assert.doesNotMatch(t5, /ONE entity only in the frame/i)
    assert.doesNotMatch(t5, /ONE single continuous view of ONE subject/i)
    assert.match(t5, /no unintended duplicated objects/i)
  })

  test('plein pied ajoute un contrat anti-cadrage coupe', () => {
    const workflow = createFluxWorkflow({
      prompt: 'Goldorak devant la tour Eiffel, plan plein pied',
      width: 1024,
      height: 1024,
      steps: 28,
      filenamePrefix: 'full_body',
      style: 'anime',
    })

    const t5 = findT5(workflow)

    assert.match(t5, /head to toe/i)
    assert.match(t5, /no cropped limbs/i)
  })
})

describe('createFluxWorkflow - edition referencee', () => {
  test('sans reference utilise denoise 1.0', () => {
    const workflow = createFluxWorkflow({
      prompt: 'a sunset',
      width: 1024,
      height: 1024,
      steps: 28,
      filenamePrefix: 'test',
    })

    assert.equal(findScheduler(workflow)?.denoise, 1.0)
  })

  test('reference + denoise explicite reste honore', () => {
    const workflow = createFluxWorkflow({
      prompt: 'meme image',
      width: 1024,
      height: 1024,
      steps: 28,
      filenamePrefix: 'test',
      referenceImage: { filename: 'ref.png', denoise: 0.35 },
    })

    assert.equal(findScheduler(workflow)?.denoise, 0.35)
  })

  test('suppression ajoute un contrat de reconstruction sans reinjecter la cible', () => {
    const intent = parseImageIntent('meme image mais sans le chat')
    const workflow = createFluxWorkflow({
      prompt: intent.cleanedPrompt,
      width: 1024,
      height: 1024,
      steps: 28,
      filenamePrefix: 'edit',
      referenceImage: { filename: 'ref.png' },
      editIntent: intent,
    })

    const t5 = findT5(workflow)
    const scheduler = findScheduler(workflow)

    assert.match(t5, /removed area is naturally inpainted/i)
    assert.ok(!t5.toLowerCase().includes('chat'))
    assert.equal(scheduler?.denoise, 0.5)
    assert.equal(scheduler?.steps, 40)
  })

  test('suppression de personne retire aussi vetements et silhouette', () => {
    const intent = parseImageIntent('suppression complete de l homme metis et ajout du chat de Fairy Tail nomme Happy assis sur l epaule droite', { hasReference: true })
    const workflow = createFluxWorkflow({
      prompt: intent.cleanedPrompt,
      width: 1024,
      height: 1536,
      steps: 28,
      filenamePrefix: 'edit_person_removal',
      referenceImage: { filename: 'ref.png' },
      editIntent: intent,
    })

    const t5 = findT5(workflow)

    assert.match(t5, /remove the whole visible target/i)
    assert.match(t5, /clothing, shirt fabric, straps/i)
    assert.match(t5, /do not leave garments/i)
    assert.match(t5, /no oversized shoulder, expanded chest/i)
  })

  test('ajout cible augmente assez la force de transformation', () => {
    const intent = parseImageIntent('ajoute des lunettes rouges')
    const workflow = createFluxWorkflow({
      prompt: intent.cleanedPrompt,
      width: 1024,
      height: 1024,
      steps: 28,
      filenamePrefix: 'edit',
      referenceImage: { filename: 'ref.png' },
      editIntent: intent,
    })

    const t5 = findT5(workflow)
    const scheduler = findScheduler(workflow)

    assert.match(t5, /lunettes rouges/i)
    assert.ok((scheduler?.denoise ?? 0) >= 0.48)
    assert.ok((scheduler?.steps ?? 0) >= 38)
  })

  test('ajout de personnage autorise une entite ajoutee au lieu de forcer une seule entite', () => {
    const intent = parseImageIntent('sur la photo ajoute le personnage Kora comme un ami avec une main sur l epaule', { hasReference: true })
    const workflow = createFluxWorkflow({
      prompt: intent.cleanedPrompt,
      width: 1024,
      height: 1024,
      steps: 28,
      filenamePrefix: 'edit',
      referenceImage: { filename: 'ref.png' },
      editIntent: intent,
    })

    const t5 = findT5(workflow)

    assert.doesNotMatch(t5, /ONE entity only in the frame/i)
    assert.doesNotMatch(t5, /ONE single continuous view of ONE subject/i)
    assert.match(t5, /allow every requested added element/i)
    assert.match(t5, /relationship or emotion legible/i)
  })

  test('ajout objet simple n est pas contredit par la regle une seule entite', () => {
    const intent = parseImageIntent('sur la photo ajoute une couronne doree', { hasReference: true })
    const workflow = createFluxWorkflow({
      prompt: intent.cleanedPrompt,
      width: 1024,
      height: 1024,
      steps: 28,
      filenamePrefix: 'edit',
      referenceImage: { filename: 'ref.png' },
      editIntent: intent,
    })

    const t5 = findT5(workflow)

    assert.doesNotMatch(t5, /ONE entity only in the frame/i)
    assert.match(t5, /allow every requested added element/i)
  })
})

describe('createFluxWorkflow - forme du graphe', () => {
  test('DualCLIPLoader suit l ordre du workflow officiel: t5 puis clip_l', () => {
    const workflow = createFluxWorkflow({
      prompt: 'test',
      width: 512,
      height: 512,
      steps: 20,
      filenamePrefix: 'aurora_test',
    })

    const loader = findDualClipLoader(workflow)

    assert.equal(loader?.clip_name1, 't5xxl_fp8_e4m3fn.safetensors')
    assert.equal(loader?.clip_name2, 'clip_l.safetensors')
  })

  test('ModelSamplingFlux nourrit scheduler et guider', () => {
    const workflow = createFluxWorkflow({
      prompt: 'test',
      width: 512,
      height: 768,
      steps: 20,
      filenamePrefix: 'aurora_test',
    })

    const modelSampling = findNodeByClass(workflow, 'ModelSamplingFlux')
    const scheduler = findNodeByClass(workflow, 'BasicScheduler')
    const guider = findNodeByClass(workflow, 'BasicGuider')

    assert.equal(modelSampling?.inputs?.width, 512)
    assert.equal(modelSampling?.inputs?.height, 768)
    assert.deepEqual(scheduler?.inputs?.model, ['4', 0])
    assert.deepEqual(guider?.inputs?.model, ['4', 0])
  })

  test('retourne des noeuds numeriques et un SaveImage final', () => {
    const workflow = createFluxWorkflow({
      prompt: 'test',
      width: 512,
      height: 512,
      steps: 20,
      filenamePrefix: 'aurora_test',
      seed: 12345,
    })

    const ids = Object.keys(workflow)
    const saveNode = Object.values(workflow).find((node) => {
      const item = node as { class_type?: string; inputs?: Record<string, unknown> }
      return item.class_type === 'SaveImage'
        && String(item.inputs?.filename_prefix || '').includes('aurora_test')
    })
    const noiseNode = Object.values(workflow).find((node) => {
      return (node as { class_type?: string }).class_type === 'RandomNoise'
    }) as { inputs?: { noise_seed?: number } } | undefined

    assert.ok(ids.length > 5)
    for (const id of ids) assert.match(id, /^\d+$/)
    assert.ok(saveNode)
    assert.equal(noiseNode?.inputs?.noise_seed, 12345)
  })
})
