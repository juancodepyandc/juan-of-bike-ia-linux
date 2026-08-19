#!/usr/bin/env node
/**
 * Comprehensive Human-Prompt Validation Suite for AuroraIA Image Module
 * 
 * Tests natural human phrasing across:
 * 1. Image Generation (Landscape, Scene, Character, Object, Other/Creature/Vehicle)
 * 2. Image Modification (Known reference add, Invented element add, Sky/Atmosphere change, Apparel overlay)
 * 3. Image Transfer / Multi-reference (Known subject recognition, Unknown/Descriptive transfer)
 * 4. Multi-Interface checks: CLI, UI logic, Bridge/Tunnel endpoints
 */

import assert from 'node:assert/strict'
import { parseImageIntent, buildNegativePrompt, resolveReferenceDenoise } from '../src/utils/imagePromptParser.ts'
import { buildPrompt, parseBrief } from '../src/services/imagePromptBuilder.ts'
import { applyEditLexicon, looksFrench, translateEditInstructionToEnglish } from '../src/utils/kontextInstructionTranslator.ts'
import { buildKontextInstruction, createFluxKontextWorkflow } from '../src/utils/fluxKontextWorkflow.ts'
import { detectSubjectToResearch, buildAppearanceClause } from '../src/services/selfInformedReference.ts'
import { createFluxWorkflow } from '../src/utils/fluxWorkflow.ts'

console.log('='.repeat(70))
console.log('🚀 LANCEMENT DE LA SUITE DE TESTS : PROMPTS HUMAINS (CLI, UI, TUNNEL)')
console.log('='.repeat(70))

let totalTests = 0
let passedTests = 0
const failures = []

async function runTestCase(category, name, fn) {
  totalTests++
  process.stdout.write(`\n[${category}] ${name} ... `)
  try {
    await fn()
    passedTests++
    console.log('✅ OK')
  } catch (err) {
    failures.push({ category, name, error: err.message || String(err) })
    console.log(`❌ ECHEC: ${err.message}`)
  }
}

// -----------------------------------------------------------------------------
// 1. GENERATION D'IMAGES : PROMPTS HUMAINS NATURELS
// -----------------------------------------------------------------------------

// 1.1 Paysage (Landscape) - Connu
await runTestCase('Génération - Paysage', '1.1 Village de Magnolia (Fairy Tail) avec perspective et guilde', async () => {
  const userPrompt = 'fais moi le village de magnolia dans fairy tail avec la guilde au bord de la rivière'
  const brief = parseBrief(userPrompt)
  const built = buildPrompt({ ...brief, subject: userPrompt, style: 'anime-clean' })
  
  assert.ok(built.positive.includes('magnolia'), 'Doit inclure Magnolia')
  assert.match(built.positive, /linear depth perspective/i, 'Doit imposer la perspective linéaire')
  assert.match(built.positive, /scale down smoothly/i, 'Doit rétrécir les éléments distants vers le point de fuite')
  assert.match(built.negative, /giant background people/i, 'Doit interdire les personnages géants au loin')
  assert.match(built.negative, /messy unrecognizable faces on banners/i, 'Doit interdire les visages difformes sur banderoles')
})

// 1.2 Paysage (Landscape) - Naturel / Original
await runTestCase('Génération - Paysage', '1.2 Plage tropicale au coucher de soleil avec falaises', async () => {
  const userPrompt = 'une plage tropicale au coucher de soleil avec des falaises rocheuses et des vagues calmes'
  const brief = parseBrief(userPrompt)
  assert.equal(brief.lighting, 'golden-hour', 'Doit détecter golden-hour pour coucher de soleil')
  const built = buildPrompt({ ...brief, subject: userPrompt, style: 'photorealistic' })
  
  assert.ok(built.positive.includes('plage tropicale'), 'Sujet inclus')
  assert.ok(built.positive.includes('golden hour'), 'Éclairage golden hour inclus')
  assert.match(built.positive, /linear depth perspective/i, 'Perspective spatiale requise')
})

// 1.3 Scène - Connue
await runTestCase('Génération - Scène', '1.3 Centre-ville de Springfield avec centrale au loin', async () => {
  const userPrompt = 'le centre ville de springfield avec la taverne de moe et la centrale nucléaire au loin'
  const brief = parseBrief(userPrompt)
  const built = buildPrompt({ ...brief, subject: userPrompt, style: 'flat-illustration' })
  
  assert.match(built.positive, /accurate linear depth perspective/i, 'Doit respecter l échelle d éloignement')
  assert.match(built.negative, /out-of-scale figures/i, 'Doit interdire les personnages hors d échelle')
  assert.match(built.negative, /blurry humanoid blobs/i, 'Doit interdire les silhouettes informes')
})

// 1.4 Scène - Originale
await runTestCase('Génération - Scène', '1.4 Duel magique nocturne dans une ruelle pavée sous la pluie', async () => {
  const userPrompt = 'un duel magique nocturne dans une vieille ruelle pavée sous une pluie fine'
  const brief = parseBrief(userPrompt)
  const built = buildPrompt({ ...brief, subject: userPrompt, style: 'cinematic' })
  
  assert.ok(built.positive.includes('duel magique'), 'Sujet présent')
  assert.match(built.positive, /linear depth perspective/i, 'Perspective ruelle pavée présente')
  assert.match(built.positive, /anamorphic lens|cinematographic frame/i, 'Style cinéma appliqué')
})

// 1.5 Personnage - Connu
await runTestCase('Génération - Personnage', '1.5 Natsu Dragneel avec poing enflammé', async () => {
  const userPrompt = 'natsu dragneel avec un grand sourire confiant et son poing enflammé'
  const target = detectSubjectToResearch(userPrompt, null)
  assert.ok(target, 'Doit détecter le personnage')
  assert.equal(target.subject.toLowerCase(), 'natsu dragneel', 'Nom du personnage extrait')
  assert.equal(target.kind, 'character', 'Doit être classé character et non place')
  
  const brief = parseBrief(userPrompt)
  const built = buildPrompt({ ...brief, subject: userPrompt, style: 'anime-clean' })
  assert.ok(built.positive.includes('natsu dragneel'))
  assert.match(built.positive, /on-model face/i, 'Doit préserver le visage fidèle du modèle')
})

// 1.6 Personnage - Original
await runTestCase('Génération - Personnage', '1.6 Jeune guerrière cybernétique aux cheveux courts violets', async () => {
  const userPrompt = 'une jeune guerrière cybernétique avec des cheveux courts violets et une veste lumineuse'
  const brief = parseBrief(userPrompt)
  const built = buildPrompt({ ...brief, subject: userPrompt, style: 'cinematic' })
  
  assert.ok(built.positive.includes('jeune guerrière'))
  assert.match(built.positive, /depth staging|cinematographic frame/i)
})

// 1.7 Objet - Magique
await runTestCase('Génération - Objet', '1.7 Épée magique ancienne incrustée de cristaux bleus', async () => {
  const userPrompt = 'une épée magique ancienne incrustée de cristaux luminescents bleus sur un socle de pierre'
  const brief = parseBrief(userPrompt)
  const built = buildPrompt({ ...brief, subject: userPrompt, style: 'concept-art' })
  
  assert.ok(built.positive.includes('épée magique'))
  assert.match(built.positive, /production concept art|clear focal path/i)
})

// 1.8 Objet - Mécanique / Horlogerie
await runTestCase('Génération - Objet', '1.8 Montre à gousset mécanique en or ouvragé', async () => {
  const userPrompt = 'une montre à gousset mécanique en or ouvragé avec rouages apparents'
  const brief = parseBrief(userPrompt)
  const built = buildPrompt({ ...brief, subject: userPrompt, style: 'photorealistic' })
  
  assert.ok(built.positive.includes('montre à gousset'))
  assert.match(built.positive, /detailed skin texture|real lens imperfections|natural shadows/i)
})

// 1.9 Créature
await runTestCase('Génération - Créature', '1.9 Dragon rouge majestueux sur un sommet enneigé', async () => {
  const userPrompt = 'un dragon rouge majestueux posé sur le sommet d une montagne enneigée'
  const brief = parseBrief(userPrompt)
  const built = buildPrompt({ ...brief, subject: userPrompt, style: 'concept-art' })
  
  assert.ok(built.positive.includes('dragon rouge'))
  assert.match(built.positive, /linear depth perspective/i)
})

// 1.10 Véhicule
await runTestCase('Génération - Véhicule', '1.10 Combi van hippie des années 70 face à l océan', async () => {
  const userPrompt = 'un vieux van combi des années 70 garé face à l océan au soleil couchant'
  const brief = parseBrief(userPrompt)
  const built = buildPrompt({ ...brief, subject: userPrompt, style: 'photorealistic' })
  
  assert.ok(built.positive.includes('van combi'))
  assert.equal(brief.lighting, 'golden-hour')
})

// -----------------------------------------------------------------------------
// 2. MODIFICATION D'IMAGES : PROMPTS D'EDITION SUR IMAGE EXISTANTE
// -----------------------------------------------------------------------------

// 2.1 Ajout avec référence connue (Pikachu sur la plage)
await runTestCase('Modification - Référence connue', '2.1 Ajout de Pikachu dormant sur le sable', async () => {
  const editPrompt = 'ajoute pikachu qui dort sur le sable près de l eau'
  const intent = parseImageIntent(editPrompt, { hasReference: true })
  assert.equal(intent.editMode, 'add_element')
  assert.ok(intent.additions.some(a => a.toLowerCase().includes('pikachu')))
  
  const target = detectSubjectToResearch(editPrompt, intent)
  assert.ok(target, 'Doit détecter Pikachu pour recherche visuelle')
  assert.equal(target.subject.toLowerCase(), 'pikachu')
  
  const english = await translateEditInstructionToEnglish(editPrompt)
  assert.match(english, /pikachu/i)
  
  const kontext = buildKontextInstruction(editPrompt, intent, { englishCore: english })
  assert.match(kontext, /new separate visible subject/i, 'Doit être un nouveau sujet séparé')
  assert.match(kontext, /Keep everything else unchanged/i)
})

// 2.2 Ajout avec référence connue (Happy avec Natsu)
await runTestCase('Modification - Référence connue', '2.2 Ajout du chat Happy volant à côté', async () => {
  const editPrompt = 'ajoute le chat bleu happy de fairy tail qui vole juste à côté de lui en souriant'
  const intent = parseImageIntent(editPrompt, { hasReference: true })
  assert.equal(intent.editMode, 'add_element')
  
  const lex = applyEditLexicon(editPrompt)
  assert.match(lex, /Happy, the cat from Fairy Tail/i, 'Doit traduire l idiome Happy de Fairy Tail')
  
  const kontext = buildKontextInstruction(editPrompt, intent, { englishCore: 'add Happy, the blue cat from Fairy Tail flying next to him smiling' })
  assert.match(kontext, /Keep everything else unchanged/i)
  assert.match(kontext, /same face, same hair/i)
})

// 2.3 Ajout inventé (Feu de camp et tente)
await runTestCase('Modification - Élément inventé', '2.3 Ajout d une tente rouge et d un feu de camp', async () => {
  const editPrompt = 'ajoute une tente de camping rouge et un feu de camp avec de la fumée'
  const intent = parseImageIntent(editPrompt, { hasReference: true })
  assert.equal(intent.editMode, 'add_element')
  
  const english = await translateEditInstructionToEnglish(editPrompt)
  assert.match(english, /tent/i)
  assert.match(english, /camp/i)
  
  const kontext = buildKontextInstruction(editPrompt, intent, { englishCore: english })
  assert.match(kontext, /Integrate the requested new element/i)
})

// 2.4 Ajout inventé / Vêtement (Cape noire + flammes bleues sur tenue existante)
await runTestCase('Modification - Vêtement & Effet', '2.4 Cape noire posée sur épaules + flammes bleues sans recoloration', async () => {
  const editPrompt = 'ajoute une cape noire sur ses épaules et des flammes bleues en plus des rouges sans changer sa tenue ni son visage'
  const intent = parseImageIntent(editPrompt, { hasReference: true })
  assert.equal(intent.editMode, 'add_element')
  
  const lex = applyEditLexicon(editPrompt)
  assert.match(lex, /black cape/i)
  assert.match(lex, /blue flames/i)
  assert.match(lex, /without changing the clothes or face|without changing the clothes/i)
  
  const kontext = buildKontextInstruction(editPrompt, intent, { englishCore: lex })
  assert.match(kontext, /worn over the character's body/i, 'Cape doit être posée par dessus')
  assert.match(kontext, /clothing keep their original colors.*unchanged/i, 'Tenue d origine protégée')
  assert.match(kontext, /flames.*appear around the character alongside existing elements/i, 'Flammes ajoutées sans remplacer')
  assert.match(kontext, /same face, same hair/i, 'Visage et cheveux verrouillés')
})

// 2.5 Modification d'ambiance / Arrière-plan (Nuit étoilée sans foule)
await runTestCase('Modification - Ambiance', '2.5 Retouche en nuit étoilée avec pleine lune sans foule', async () => {
  const editPrompt = 'demande nuit étoilée avec une pleine lune et un ciel clair sans ajouter de monde'
  const intent = parseImageIntent(editPrompt, { hasReference: true })
  assert.equal(intent.editMode, 'background_change', 'Doit être background_change et non scene_transform')
  
  const lex = applyEditLexicon(editPrompt)
  assert.match(lex, /starry night sky/i)
  assert.match(lex, /full moon/i)
  
  const kontext = buildKontextInstruction(editPrompt, intent, { englishCore: lex })
  assert.match(kontext, /Change only the background and sky/i)
  assert.match(kontext, /Preserve the foreground character's exact face, facial features, hair style, hair color/i)
  assert.match(kontext, /Do not add any random bystanders, extra crowd/i, 'Interdiction stricte de foule')
})

// 2.6 Modification d'ambiance (Coucher de soleil doré)
await runTestCase('Modification - Ambiance', '2.6 Coucher de soleil aux teintes orange et dorées', async () => {
  const editPrompt = 'change le fond en coucher de soleil avec des teintes orange et dorées'
  const intent = parseImageIntent(editPrompt, { hasReference: true })
  assert.equal(intent.editMode, 'background_change')
  
  const kontext = buildKontextInstruction(editPrompt, intent, { englishCore: 'change the background into sunset with orange and golden hues' })
  assert.match(kontext, /Change only the background and sky/i)
  assert.match(kontext, /Preserve the foreground character/i)
})

// -----------------------------------------------------------------------------
// 3. TRANSFERT & RECONNAISSANCE D'IMAGE AVEC PROMPT
// -----------------------------------------------------------------------------

// 3.1 Transfert de sujet connu (Natsu dans décor de Magnolia)
await runTestCase('Transfert / Reconnaissance', '3.1 Reconnaissance de Natsu transféré dans le village de Magnolia', async () => {
  const userPrompt = 'reproduis fidèlement natsu de cette image et place le dans le village de magnolia'
  const intent = parseImageIntent(userPrompt, { hasReference: true })
  assert.equal(intent.editMode, 'replicate', 'Mode réplication / fidélité')
  
  const target = detectSubjectToResearch(userPrompt, intent)
  assert.ok(target, 'Doit identifier Natsu comme sujet primaire')
  assert.match(target.subject.toLowerCase(), /natsu/i)
  
  const kontext = buildKontextInstruction(userPrompt, intent, { englishCore: 'faithfully replicate Natsu from this image and place him in the village of Magnolia' })
  assert.match(kontext, /Faithfully replicate the visual identity/i)
})

// 3.2 Transfert de sujet connu (Homer Simpson sur la Lune)
await runTestCase('Transfert / Reconnaissance', '3.2 Reconnaissance de Homer Simpson transféré sur la Lune', async () => {
  const userPrompt = 'prends homer de cette photo et mets le en costume de cosmonaute sur la lune'
  const intent = parseImageIntent(userPrompt, { hasReference: true })
  const target = detectSubjectToResearch(userPrompt, intent)
  assert.ok(target)
  assert.match(target.subject.toLowerCase(), /homer/i)
  
  const english = await translateEditInstructionToEnglish(userPrompt)
  assert.match(english, /homer/i)
})

// 3.3 Transfert de sujet inconnu avec description humaine (Robot dans temple)
await runTestCase('Transfert / Reconnaissance', '3.3 Sujet inconnu avec description naturelle dans nouveau décor', async () => {
  const userPrompt = 'fais une reproduction fidèle du robot de cette référence mais dans un temple ancien en ruines'
  const intent = parseImageIntent(userPrompt, { hasReference: true })
  assert.equal(intent.editMode, 'replicate')
  
  const kontext = buildKontextInstruction(userPrompt, intent, { englishCore: 'faithfully replicate the robot from this reference but inside an ancient temple ruin' })
  assert.match(kontext, /Faithfully replicate the visual identity/i)
  assert.match(kontext, /same identity, same face/i)
})

// 3.4 Transfert de style / pose
await runTestCase('Transfert / Reconnaissance', '3.4 Transfert de pose et composition vers armure d or', async () => {
  const userPrompt = 'garde la même pose et le même style graphique que cette image mais transforme le personnage en chevalier d or'
  const intent = parseImageIntent(userPrompt, { hasReference: true })
  const kontext = buildKontextInstruction(userPrompt, intent, { englishCore: 'keep the same pose and graphic style as this image but transform the character into a golden knight' })
  assert.match(kontext, /Keep everything else unchanged/i)
})

// -----------------------------------------------------------------------------
// 4. VALIDATION SYSTEMIQUE MULTI-INTERFACES : CLI, UI, TUNNEL
// -----------------------------------------------------------------------------

// 4.1 CLI Execution Workflow Generation
await runTestCase('Validation Système', '4.1 Génération de workflow FLUX via CLI pipeline', async () => {
  const prompt = 'un astronaute qui marche sur mars au coucher de soleil'
  const wf = createFluxWorkflow({
    prompt,
    negativePrompt: 'lowres, blurry, distorted',
    width: 1024,
    height: 1024,
    steps: 28,
    seed: 42,
  })
  assert.ok(wf, 'Le workflow JSON doit être généré')
  assert.ok(typeof wf === 'object', 'Doit être un objet ComfyUI workflow valide')
  const nodes = Object.values(wf)
  assert.ok(nodes.some(n => n.class_type === 'CLIPLoader' || n.class_type === 'CLIPTextEncode'), 'Contient CLIPLoader / CLIPTextEncode')
  assert.ok(nodes.some(n => n.class_type === 'SamplerCustomAdvanced' || n.class_type === 'KSamplerSelect'), 'Contient SamplerCustomAdvanced')
})

// 4.2 UI Kontext Workflow Generation
await runTestCase('Validation Système', '4.2 Génération de workflow FLUX Kontext via UI pipeline', async () => {
  const instruction = 'Add a black cape worn over shoulders, blue flames around hands, without changing face or clothes'
  const wf = createFluxKontextWorkflow({
    instruction,
    referenceFilename: 'input_character.png',
    unetName: 'flux1-dev-kontext_fp8.safetensors',
    filenamePrefix: 'test_kontext',
    width: 1024,
    height: 1024,
    steps: 20,
    seed: 12345,
  })
  assert.ok(wf, 'Le workflow Kontext doit être généré')
  const nodes = Object.values(wf)
  assert.ok(nodes.some(n => n.class_type === 'LoadImage'), 'Contient LoadImage')
  assert.ok(nodes.some(n => n.class_type === 'CLIPTextEncode'), 'Contient CLIPTextEncode avec instruction')
})

// 4.3 Tunnel / Bridge Proxy ComfyUI Status
await runTestCase('Validation Système', '4.3 Tunnel/Bridge Server proxy ComfyUI & Ollama', async () => {
  const res = await fetch('http://127.0.0.1:3001/proxy/comfy/system_stats', { signal: AbortSignal.timeout(3000) })
  assert.equal(res.ok, true, 'Bridge doit répondre sur /proxy/comfy/system_stats')
  const stats = await res.json()
  assert.ok(stats.devices && stats.devices.length > 0, 'ComfyUI GPU device actif')
})

// -----------------------------------------------------------------------------
// BILAN FINAL
// -----------------------------------------------------------------------------

console.log('\n' + '='.repeat(70))
console.log(`📊 BILAN DES TESTS : ${passedTests} / ${totalTests} RÉUSSIS (${Math.round((passedTests / totalTests) * 100)}%)`)
console.log('='.repeat(70))

if (failures.length > 0) {
  console.log('\n❌ DÉTAIL DES ÉCHECS :')
  for (const f of failures) {
    console.log(`- [${f.category}] ${f.name} : ${f.error}`)
  }
  process.exit(1)
} else {
  console.log('\n🎉 TOUS LES TESTS SONT AU VERT AVEC DES PROMPTS 100% NATURELS ET HUMAINS !')
  process.exit(0)
}
