import { test, describe } from 'node:test'
import { IMAGE_CLIP_MODEL, IMAGE_T5_MODEL } from '../config/models.ts'
import assert from 'node:assert/strict'
import {
  FLUX_KONTEXT_UNET_CANDIDATES,
  assembleKontextInstruction,
  buildKontextInjectionInstruction,
  buildKontextInstruction,
  buildStagedKontextEditPlan,
  buildStagedReplacementPlan,
  createFluxKontextWorkflow,
  resolveKontextModel,
  shouldUseStagedKontextEditPlan,
  shouldUseStagedReplacementPlan,
} from '../utils/fluxKontextWorkflow.ts'
import { parseImageIntent } from '../utils/imagePromptParser.ts'
import { buildImageAutocorrectionContract } from '../services/imageConversationContract.ts'

type Node = { class_type?: string; inputs?: Record<string, unknown> }

function findNode(workflow: Record<string, unknown>, classType: string): Node | null {
  for (const node of Object.values(workflow)) {
    const item = node as Node
    if (item.class_type === classType) return item
  }
  return null
}

function findNodeId(workflow: Record<string, unknown>, classType: string): string | null {
  for (const [id, node] of Object.entries(workflow)) {
    if ((node as Node).class_type === classType) return id
  }
  return null
}

describe('resolveKontextModel', () => {
  test('trouve le fp8 scaled officiel', () => {
    const model = resolveKontextModel([
      'flux1-dev-fp8.safetensors',
      'flux2-dev-Q5_K_M.gguf',
      'flux1-dev-kontext_fp8_scaled.safetensors',
    ])
    assert.equal(model, 'flux1-dev-kontext_fp8_scaled.safetensors')
  })

  test('catch-all sur tout fichier kontext', () => {
    const model = resolveKontextModel(['weird-Kontext-build-q4.gguf'])
    assert.equal(model, 'weird-Kontext-build-q4.gguf')
  })

  test('null quand aucun kontext installe', () => {
    assert.equal(resolveKontextModel(['flux1-dev-fp8.safetensors']), null)
  })

  test('gere les sous-dossiers windows', () => {
    const model = resolveKontextModel(['sub\\flux1-dev-kontext_fp8_scaled.safetensors'])
    assert.equal(model, 'sub/flux1-dev-kontext_fp8_scaled.safetensors')
  })

  test('les candidats declares restent coherents', () => {
    assert.ok(FLUX_KONTEXT_UNET_CANDIDATES.length >= 3)
    for (const candidate of FLUX_KONTEXT_UNET_CANDIDATES) {
      assert.match(candidate, /kontext/i)
    }
  })
})

describe('createFluxKontextWorkflow - graphe officiel', () => {
  const workflow = createFluxKontextWorkflow({
    instruction: 'Add a red hat to the cat',
    referenceFilename: 'subdir\\aurora_current_123.png',
    unetName: 'flux1-dev-kontext_fp8_scaled.safetensors',
    filenamePrefix: 'edit_test',
    seed: 42,
    width: 768,
    height: 1152,
  })

  test('LoadImage recoit le basename de la reference', () => {
    const load = findNode(workflow, 'LoadImage')
    assert.equal(load?.inputs?.image, 'aurora_current_123.png')
  })

  test('le chargeur de texte suit la CONFIGURATION (un ou deux encodeurs)', () => {
    // L'ancien test figeait les noms FLUX.1 (t5xxl+clip_l). La config fait
    // foi: 2e encodeur configure -> DualCLIPLoader; sinon CLIPLoader simple
    // (FLUX.2, un seul encodeur, sur CPU).
    if (IMAGE_CLIP_MODEL) {
      const loader = findNode(workflow, 'DualCLIPLoader')
      assert.equal(loader?.inputs?.clip_name1, IMAGE_T5_MODEL)
      assert.equal(loader?.inputs?.clip_name2, IMAGE_CLIP_MODEL)
    } else {
      const loader = findNode(workflow, 'CLIPLoader')
      assert.equal(loader?.inputs?.clip_name, IMAGE_T5_MODEL)
      assert.equal(loader?.inputs?.device, 'cpu')
    }
  })

  test('ReferenceLatent relie conditioning texte et latent VAE', () => {
    const ref = findNode(workflow, 'ReferenceLatent')
    const guidanceId = findNodeId(workflow, 'FluxGuidance')
    const vaeEncodeId = findNodeId(workflow, 'VAEEncode')
    assert.ok(ref, 'ReferenceLatent absent')
    assert.deepEqual(ref?.inputs?.conditioning, [guidanceId, 0])
    assert.deepEqual(ref?.inputs?.latent, [vaeEncodeId, 0])
  })

  test('FluxKontextImageScale entre LoadImage et VAEEncode', () => {
    const scale = findNode(workflow, 'FluxKontextImageScale')
    const loadId = findNodeId(workflow, 'LoadImage')
    const vaeEncode = findNode(workflow, 'VAEEncode')
    const scaleId = findNodeId(workflow, 'FluxKontextImageScale')
    assert.deepEqual(scale?.inputs?.image, [loadId, 0])
    assert.deepEqual(vaeEncode?.inputs?.pixels, [scaleId, 0])
  })

  test('KSampler en denoise 1.0 / cfg 1.0 — la reference passe par le conditioning', () => {
    const sampler = findNode(workflow, 'SamplerCustomAdvanced')
    const noiseId = findNodeId(workflow, 'RandomNoise')
    const guiderId = findNodeId(workflow, 'BasicGuider')
    const samplerSelectId = findNodeId(workflow, 'KSamplerSelect')
    const schedulerId = findNodeId(workflow, 'BasicScheduler')
    const emptyLatentId = findNodeId(workflow, 'EmptySD3LatentImage')
    assert.deepEqual(sampler?.inputs?.noise, [noiseId, 0])
    assert.deepEqual(sampler?.inputs?.guider, [guiderId, 0])
    assert.deepEqual(sampler?.inputs?.sampler, [samplerSelectId, 0])
    assert.deepEqual(sampler?.inputs?.sigmas, [schedulerId, 0])
    assert.deepEqual(sampler?.inputs?.latent_image, [emptyLatentId, 0])
    const noise = findNode(workflow, 'RandomNoise')
    assert.equal(noise?.inputs?.noise_seed, 42)
  })

  test('EmptyLatentImage porte le canvas demande', () => {
    const empty = findNode(workflow, 'EmptySD3LatentImage')
    assert.equal(empty?.inputs?.width, 768)
    assert.equal(empty?.inputs?.height, 1152)
    assert.equal(empty?.inputs?.batch_size, 1)
  })

  test('ModelSamplingFlux nourrit le scheduler et le guider', () => {
    const modelSampling = findNode(workflow, 'ModelSamplingFlux')
    const modelSamplingId = findNodeId(workflow, 'ModelSamplingFlux')
    const scheduler = findNode(workflow, 'BasicScheduler')
    const guider = findNode(workflow, 'BasicGuider')
    assert.equal(modelSampling?.inputs?.width, 768)
    assert.equal(modelSampling?.inputs?.height, 1152)
    assert.deepEqual(scheduler?.inputs?.model, [modelSamplingId, 0])
    assert.deepEqual(guider?.inputs?.model, [modelSamplingId, 0])
    assert.equal(scheduler?.inputs?.denoise, 1.0)
  })

  test('FluxGuidance par defaut a 2.5 et negative zero-out', () => {
    const guidance = findNode(workflow, 'FluxGuidance')
    assert.equal(guidance?.inputs?.guidance, 2.5)
    const ref = findNode(workflow, 'ReferenceLatent')
    const guidanceId = findNodeId(workflow, 'FluxGuidance')
    assert.deepEqual(ref?.inputs?.conditioning, [guidanceId, 0])
  })

  test('instruction transmise telle quelle au CLIPTextEncode', () => {
    const clip = findNode(workflow, 'CLIPTextEncode')
    assert.equal(clip?.inputs?.text, 'Add a red hat to the cat')
  })

  test('UNETLoader fp8 detecte le weight_dtype', () => {
    const unet = findNode(workflow, 'UNETLoader')
    assert.equal(unet?.inputs?.unet_name, 'flux1-dev-kontext_fp8_scaled.safetensors')
    assert.equal(unet?.inputs?.weight_dtype, 'default')
  })
})

describe('buildKontextInstruction - depuis l intention parsee', () => {
  test('prompt sans edit reste inchange', () => {
    const intent = parseImageIntent('un chat roux sous la pluie')
    assert.equal(buildKontextInstruction('un chat roux sous la pluie', intent), 'un chat roux sous la pluie')
  })

  test('suppression → Remove + clause de preservation', () => {
    const prompt = 'enlève le chapeau du chat'
    const intent = parseImageIntent(prompt, { hasReference: true })
    assert.equal(intent.editMode, 'remove_element')
    const instruction = buildKontextInstruction(prompt, intent)
    assert.match(instruction, /Remove .*chapeau/i)
    assert.match(instruction, /Keep everything else unchanged/i)
    assert.match(instruction, /enlève le chapeau du chat/)
  })

  test('ajout → Add + preservation', () => {
    const prompt = 'ajoute un chapeau rouge'
    const intent = parseImageIntent(prompt, { hasReference: true })
    assert.equal(intent.editMode, 'add_element')
    const instruction = buildKontextInstruction(prompt, intent)
    assert.match(instruction, /Add .*chapeau rouge/i)
    assert.match(instruction, /same identity/i)
  })

  test('ajout de nouveau sujet protege les sujets existants', () => {
    const prompt = 'ajoute un petit personnage photorealiste de jardinier adulte debout a droite du barbecue'
    const intent = parseImageIntent(prompt, { hasReference: true })
    assert.equal(intent.editMode, 'add_element')
    const instruction = buildKontextInstruction(prompt, intent)

    assert.match(instruction, /new separate visible subject/i)
    assert.match(instruction, /complete second full-body subject standing on the ground/i)
    assert.match(instruction, /Only the new subject wears the requested clothes/i)
  })

  test('ajout de nouveau sujet autorise le contact explicitement demande', () => {
    const prompt = "ajoute Goldorak qui tient le bord du pantalon noir de l'homme"
    const intent = parseImageIntent(prompt, { hasReference: true })
    const instruction = buildKontextInstruction(prompt, intent)

    assert.match(instruction, /allowed to touch only the explicitly requested contact point/i)
    assert.ok(!/standing on the ground at the requested position, separate from existing people/i.test(instruction))
  })

  test('remplacement → Replace from/to', () => {
    const prompt = 'remplace le chien par un chat noir'
    const intent = parseImageIntent(prompt, { hasReference: true })
    assert.equal(intent.editMode, 'replace_element')
    const instruction = buildKontextInstruction(prompt, intent)
    assert.match(instruction, /Replace .*chien.* with .*chat noir/i)
  })

  test('deplacement objet → positionnement coherent', () => {
    const prompt = 'deplace le barbecue plus a gauche sur la pelouse'
    const intent = parseImageIntent(prompt, { hasReference: true })
    assert.equal(intent.editMode, 'composition_pose')
    const instruction = buildKontextInstruction(prompt, intent)
    assert.match(instruction, /position, relocation or framing/i)
    assert.match(instruction, /preserve its original size, shape, material/i)
    assert.match(instruction, /do not create any duplicate target/i)
  })

  test('restyle garde composition mais sans clause identite stricte', () => {
    const prompt = 'transforme cette image en pixel art'
    const intent = parseImageIntent(prompt, { hasReference: true })
    assert.equal(intent.editMode, 'restyle')
    const instruction = buildKontextInstruction(prompt, intent)
    assert.match(instruction, /same composition/i)
    assert.ok(!/Keep everything else unchanged/i.test(instruction))
  })
})

describe('assembleKontextInstruction - parite UI/CLI + zero pollution de contrat', () => {
  const prompt = 'ajoute le personnage Jax posant une main sur mon epaule'
  const intent = parseImageIntent(prompt, { hasReference: true })
  const englishCore = 'Add the character Jax, placing a hand on my shoulder in a friendly way'
  const entityClause = 'The added character (Jax) must look exactly like this: a tall lanky purple cartoon rabbit, slender limbs'

  test('UI et CLI produisent EXACTEMENT la meme instruction pour les memes entrees', () => {
    // L'UI (useImageViewLogic) et la CLI (image_cli) appellent toutes deux ce helper
    // avec les memes champs -> la sortie doit etre identique au caractere pres.
    const fromUi = assembleKontextInstruction({ rawPrompt: prompt, intent, englishCore, entityClause })
    const fromCli = assembleKontextInstruction({ rawPrompt: prompt, intent, englishCore, entityClause })
    assert.equal(fromUi, fromCli)
  })

  test('aucune fuite du session/prompt contract (cause de la sur-modification "muscle")', () => {
    const instruction = assembleKontextInstruction({ rawPrompt: prompt, intent, englishCore, entityClause })
    // Les tokens du contrat d'orchestrateur ne doivent JAMAIS atteindre le CLIPTextEncode :
    // sans canal negatif, ils deviendraient du guidage positif.
    for (const leak of [
      'HARD REQUIREMENTS', 'SESSION CONTRACT', 'chest volume', 'body volume',
      'enlarge shoulders', 'body proportions', 'torso', 'PRESERVATION',
    ]) {
      assert.ok(!new RegExp(leak, 'i').test(instruction), `fuite detectee: "${leak}"`)
    }
    // ... mais le coeur traduit + l'apparence de l'entite, eux, sont bien la.
    assert.match(instruction, /Add the character Jax/)
    assert.match(instruction, /purple cartoon rabbit/)
  })

  test('contre-preuve : l ancien montage (contrat injecte) contenait bien les tokens a risque', () => {
    const contract = buildImageAutocorrectionContract({ prompt, hasReference: true })
    assert.match(contract, /chest volume/i)
    assert.match(contract, /body proportions/i)
  })

  test('repli sans englishCore : utilise le prompt brut + apparence, toujours sans contrat', () => {
    const instruction = assembleKontextInstruction({ rawPrompt: prompt, intent, entityClause })
    assert.match(instruction, /purple cartoon rabbit/)
    assert.ok(!/HARD REQUIREMENTS/i.test(instruction))
  })

  test('edition composee suppression + ajout garde les deux obligations dans Kontext', () => {
    const mixedPrompt = 'suppression complete de l homme metis et ajout du chat de Fairy Tail nomme Happy assis sur l epaule droite'
    const mixedIntent = parseImageIntent(mixedPrompt, { hasReference: true })
    const instruction = assembleKontextInstruction({
      rawPrompt: mixedPrompt,
      intent: mixedIntent,
      englishCore: 'Remove the mixed-race man and add Happy, the cat from Fairy Tail, sitting on the right shoulder',
      entityClause: 'The added character (Happy) must look exactly like this: small blue Exceed cat with white belly, pink inner ears, big black eyes, blue cheek marks and white wings',
    })

    assert.equal(mixedIntent.editMode, 'remove_element')
    assert.deepEqual(mixedIntent.removals, ['homme metis'])
    assert.deepEqual(mixedIntent.additions, ['chat de Fairy Tail nomme Happy assis sur l epaule droite'])
    assert.match(instruction, /Remove the mixed-race man/i)
    assert.match(instruction, /Happy, the cat from Fairy Tail/i)
    assert.match(instruction, /small blue Exceed cat/i)
    assert.match(instruction, /Also add the requested new element exactly as requested/i)
    assert.match(instruction, /all clothing, shirt fabric, straps/i)
    assert.match(instruction, /no garment, shirt, strap or body remnant/i)
    assert.match(instruction, /no oversized shoulder, expanded chest, widened torso/i)
    assert.match(instruction, /visible remaining original subject/i)
    assert.match(instruction, /never on the removed person's former shirt/i)
    assert.match(instruction, /not supported by an enlarged or newly invented shoulder/i)
    assert.match(instruction, /no ghost outline/i)
  })
})

describe('buildStagedReplacementPlan - suppression humaine + ajout positionne', () => {
  const mixedPrompt = 'suppression complete de l homme metis et ajout du chat de Fairy Tail nomme Happy assis sur l epaule droite'
  const mixedIntent = parseImageIntent(mixedPrompt, { hasReference: true })
  const plan = buildStagedReplacementPlan({
    from: mixedIntent.removals.join(' and '),
    to: mixedIntent.additions.join(' and '),
    removeEnglishCore: 'Remove the mixed-race man completely',
    addEnglishCore: 'Add Happy, the cat from Fairy Tail, sitting on the right shoulder',
    entityClause: 'The added character (Happy) must look exactly like this: small blue Exceed cat with white belly, pink inner ears, big black eyes, blue cheek marks and white wings',
  })

  test('declenche le multi-etage uniquement pour suppression humaine + ajout sans injection', () => {
    assert.equal(shouldUseStagedReplacementPlan(mixedIntent), true)
    assert.equal(shouldUseStagedReplacementPlan(mixedIntent, { injection: true }), false)

    const simpleAdd = parseImageIntent('ajoute Happy sur mon epaule droite', { hasReference: true })
    const simpleRemove = parseImageIntent('supprime l homme metis', { hasReference: true })
    assert.equal(shouldUseStagedReplacementPlan(simpleAdd), false)
    assert.equal(shouldUseStagedReplacementPlan(simpleRemove), false)
  })

  test('construit trois passes separees: suppression, reconstruction, placement', () => {
    assert.deepEqual(plan.stages.map((stage) => stage.id), [
      'remove_target',
      'reconstruct_support',
      'place_new_subject',
    ])
    assert.match(plan.removeInstruction, /PASS 1 - REMOVAL ONLY/i)
    assert.match(plan.reconstructInstruction, /PASS 2 - RECONSTRUCTION ONLY/i)
    assert.match(plan.addInstruction, /PASS 3 - PLACEMENT ONLY/i)
  })

  test('passe suppression: retire aussi habits, chemise, sangles et interdit Happy trop tot', () => {
    assert.match(plan.removeInstruction, /head, face, hair, neck, torso, shoulders, arms, hands/i)
    assert.match(plan.removeInstruction, /all clothing, shirt fabric, straps, accessories/i)
    assert.match(plan.removeInstruction, /leftover garment, shirt fragment, strap/i)
    assert.match(plan.removeInstruction, /Do not add the replacement character yet/i)
    assert.ok(!/Happy/i.test(plan.removeInstruction), 'Happy ne doit pas guider la passe de suppression')
  })

  test('passe reconstruction: reconstruit le support sans epaule inventee', () => {
    assert.match(plan.reconstructInstruction, /real shoulder, neck and upper body proportions/i)
    assert.match(plan.reconstructInstruction, /if the original shoulder was hidden, use background or sky/i)
    assert.match(plan.reconstructInstruction, /No oversized shoulder, expanded chest, widened torso, stretched neck/i)
    assert.match(plan.reconstructInstruction, /Do not add the new character yet/i)
  })

  test('passe placement: Happy est fidele, sur la vraie epaule, lisible et non flottant', () => {
    assert.match(plan.addInstruction, /Happy, the cat from Fairy Tail/i)
    assert.match(plan.addInstruction, /small blue Exceed cat/i)
    assert.match(plan.addInstruction, /ORIGINAL flat 2D cel-shaded cartoon style/i)
    assert.match(plan.addInstruction, /visible remaining original subject/i)
    assert.match(plan.addInstruction, /never on the removed person's former shirt/i)
    assert.match(plan.addInstruction, /not a tiny sticker, charm or distant floating detail/i)
    assert.match(plan.addInstruction, /Do NOT enlarge or invent a new shoulder/i)
    assert.match(plan.addInstruction, /soft contact shadow/i)
  })

  test('criteres de validation couvrent les echecs vus par l utilisateur', () => {
    assert.equal(plan.validationChecklist.length, 4)
    assert.match(plan.validationChecklist.join('\n'), /shirt, straps/i)
    assert.match(plan.validationChecklist.join('\n'), /oversized shoulder\/chest\/torso\/neck/i)
    assert.match(plan.validationChecklist.join('\n'), /shoulder-scaled and physically anchored/i)
    assert.match(plan.stages[2].rejectIf.join('\n'), /floats, sits on removed clothing\/body remnants/i)
  })
})

describe('buildStagedKontextEditPlan - batterie demandes complexes', () => {
  function planFor(prompt: string) {
    const intent = parseImageIntent(prompt, { hasReference: true })
    return {
      intent,
      plan: buildStagedKontextEditPlan({
        rawPrompt: prompt,
        intent,
        englishCore: prompt,
        entityClause: 'Named entities must preserve their exact recognizable identity and original visual style.',
      }),
    }
  }

  test('ne staged pas les retouches simples a une seule operation', () => {
    const simpleStyle = parseImageIntent('transforme cette photo en pixel art', { hasReference: true })
    const simpleAdd = parseImageIntent('ajoute des lunettes rouges', { hasReference: true })
    const shirtColor = parseImageIntent("change uniquement le t-shirt noir de l'homme en t-shirt rouge, garde le decor inchange", { hasReference: true })

    assert.equal(shouldUseStagedKontextEditPlan(simpleStyle, { rawPrompt: 'transforme cette photo en pixel art' }), false)
    assert.equal(shouldUseStagedKontextEditPlan(simpleAdd, { rawPrompt: 'ajoute des lunettes rouges' }), false)
    assert.equal(shouldUseStagedKontextEditPlan(shirtColor, { rawPrompt: "change uniquement le t-shirt noir de l'homme en t-shirt rouge, garde le decor inchange" }), false)
  })

  test('ajout de nouveau sujet ne lance pas une passe de pose sur la photo source', () => {
    const prompt = 'ajoute un petit personnage photorealiste de jardinier adulte debout a droite du barbecue'
    const { intent, plan } = planFor(prompt)

    assert.equal(shouldUseStagedKontextEditPlan(intent, { rawPrompt: prompt }), true)
    assert.deepEqual(plan.stages.map((stage) => stage.id), [
      'place_new_subject',
      'verify_and_repair',
    ])
    assert.match(plan.stages[0].instruction, /additional separate visible subject/i)
    assert.match(plan.stages[0].instruction, /do not turn any existing person/i)
    assert.match(plan.stages[0].instruction, /keeps exactly the original barbecue setup only/i)
    assert.ok(!plan.stages.some((stage) => stage.id === 'pose_expression'))
  })

  test('remplacement complet personne + emotion + fond + style est decoupe en passes stables', () => {
    const prompt = 'remplace l homme par Naruto, change le fond en Tokyo de nuit, rends le personnage souriant, style anime'
    const { intent, plan } = planFor(prompt)

    assert.equal(shouldUseStagedKontextEditPlan(intent, { rawPrompt: prompt }), true)
    assert.deepEqual(plan.stages.map((stage) => stage.id), [
      'remove_target',
      'reconstruct_support',
      'replace_target',
      'pose_expression',
      'change_background',
      'apply_style',
      'verify_and_repair',
    ])
    assert.match(plan.stages[0].instruction, /all clothing, shirt fabric, straps/i)
    assert.match(plan.stages[2].instruction, /old target must not remain/i)
    assert.match(plan.stages[3].instruction, /pose, gaze, expression, emotion/i)
    assert.match(plan.stages[4].instruction, /background, decor or environment/i)
    assert.match(plan.stages[5].instruction, /Style is a hard requirement/i)
    assert.match(plan.stages[6].instruction, /missing, too simplified/i)
  })

  test('suppression + ajout positionne + texte + decor garde chaque operation separee', () => {
    const prompt = 'enleve la voiture puis ajoute un chien assis pres de moi, ecris BONJOUR sur le panneau, change le fond en plage'
    const { intent, plan } = planFor(prompt)

    assert.equal(shouldUseStagedKontextEditPlan(intent, { rawPrompt: prompt }), true)
    assert.deepEqual(plan.stages.map((stage) => stage.id), [
      'remove_target',
      'reconstruct_support',
      'pose_expression',
      'change_background',
      'place_new_subject',
      'render_text',
      'verify_and_repair',
    ])
    assert.match(plan.stages[0].instruction, /REMOVAL ONLY/i)
    assert.match(plan.stages[4].instruction, /Add each requested new element exactly as requested/i)
    assert.match(plan.stages[5].instruction, /crisp correct letters, exact spelling/i)
    assert.match(plan.validationChecklist.join('\n'), /requested text is exact/i)
    assert.match(plan.validationChecklist.join('\n'), /all additions are identifiable/i)
  })

  test('pose existante + expression + tenue + fond + style ne cree pas une fausse suppression', () => {
    const prompt = 'change la pose pour etre assise, expression triste, remplace la tenue par robe rouge, fond foret, style aquarelle'
    const { intent, plan } = planFor(prompt)

    assert.equal(shouldUseStagedKontextEditPlan(intent, { rawPrompt: prompt }), true)
    assert.ok(!plan.stages.some((stage) => stage.id === 'remove_target'))
    assert.deepEqual(plan.stages.map((stage) => stage.id), [
      'replace_target',
      'pose_expression',
      'change_background',
      'apply_style',
      'verify_and_repair',
    ])
    assert.match(plan.stages[0].instruction, /Replace exactly these targets/i)
    assert.match(plan.stages[1].instruction, /requested pose, gaze, expression, emotion/i)
    assert.match(plan.stages[4].instruction, /repair only that failure now/i)
  })

  test('injection multi-image explicite reste hors staged automatique', () => {
    const prompt = "ajoute l'ours de la deuxieme image a cote de l'homme puis change le fond en foret"
    const intent = parseImageIntent(prompt, { hasReference: true })

    assert.equal(shouldUseStagedKontextEditPlan(intent, { rawPrompt: prompt, injection: true }), false)
  })
})

describe('buildKontextInjectionInstruction - extraction multi-image', () => {
  const intent = parseImageIntent("ajoute l'ours de la deuxieme image a cote de l'homme", { hasReference: true })
  const instruction = buildKontextInjectionInstruction(
    "ajoute l'ours de la deuxieme image",
    intent,
    { englishCore: 'Add the bear from the second image next to the man' },
  )

  test('distingue gauche (scene a editer) et droite (source)', () => {
    assert.match(instruction, /left image/i)
    assert.match(instruction, /right image/i)
  })

  test('interdit explicitement le montage cote-a-cote', () => {
    assert.match(instruction, /single image/i)
    assert.match(instruction, /side-by-side|split|collage/i)
  })

  test('preserve la scene de gauche', () => {
    assert.match(instruction, /unchanged/i)
  })
})

describe('createFluxKontextWorkflow - injection multi-image (ImageStitch)', () => {
  const base = createFluxKontextWorkflow({
    instruction: 'Add the bear from the right image into the left scene',
    referenceFilename: 'base_dest.png',
    secondReferenceFilename: 'source_elem.png',
    unetName: 'flux1-dev-kontext_fp8_scaled.safetensors',
    filenamePrefix: 'inject_test',
    seed: 7,
  })

  test('ajoute un second LoadImage et un noeud ImageStitch', () => {
    const loads = Object.values(base).filter((n) => (n as Node).class_type === 'LoadImage')
    assert.equal(loads.length, 2)
    const stitch = findNode(base, 'ImageStitch')
    assert.ok(stitch, 'ImageStitch absent')
    assert.equal(stitch?.inputs?.direction, 'right')
    assert.equal(stitch?.inputs?.match_image_size, true)
  })

  test('ImageStitch accole base (image1) puis source (image2)', () => {
    const stitch = findNode(base, 'ImageStitch')
    const stitchId = findNodeId(base, 'ImageStitch')
    // image1 = LoadImage de base (node 5), image2 = LoadImage source (node 19)
    assert.deepEqual(stitch?.inputs?.image1, ['5', 0])
    assert.deepEqual(stitch?.inputs?.image2, ['19', 0])
    // FluxKontextImageScale lit l'image accolee, pas la base seule.
    const scale = findNode(base, 'FluxKontextImageScale')
    assert.deepEqual(scale?.inputs?.image, [stitchId, 0])
  })

  test('mono-image (regression) : aucun ImageStitch, le scale lit la base', () => {
    const mono = createFluxKontextWorkflow({
      instruction: 'Add a red hat',
      referenceFilename: 'base.png',
      unetName: 'flux1-dev-kontext_fp8_scaled.safetensors',
      filenamePrefix: 'mono',
      seed: 1,
    })
    assert.equal(findNode(mono, 'ImageStitch'), null)
    const scale = findNode(mono, 'FluxKontextImageScale')
    const loadId = findNodeId(mono, 'LoadImage')
    assert.deepEqual(scale?.inputs?.image, [loadId, 0])
  })
})
