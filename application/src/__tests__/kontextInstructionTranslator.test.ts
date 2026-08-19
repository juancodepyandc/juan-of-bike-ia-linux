import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  applyEditLexicon,
  looksFrench,
  translateEditInstructionToEnglish,
} from '../utils/kontextInstructionTranslator.ts'
import { buildKontextInstruction } from '../utils/fluxKontextWorkflow.ts'
import { parseImageIntent } from '../utils/imagePromptParser.ts'

describe('applyEditLexicon — pieges idiomatiques FR->EN', () => {
  test('noeud papillon -> bow tie (le bug en live)', () => {
    assert.match(applyEditLexicon('ajoute un noeud papillon'), /\bbow tie\b/)
    assert.match(applyEditLexicon('ajoute un nœud papillon'), /\bbow tie\b/)
    // jamais de traduction litterale "butterfly"
    assert.doesNotMatch(applyEditLexicon('ajoute un noeud papillon'), /butterfly|papillon/i)
  })

  test('lunettes de soleil -> sunglasses (unite avant lunettes seul)', () => {
    assert.match(applyEditLexicon('ajoute des lunettes de soleil'), /\bsunglasses\b/)
    assert.doesNotMatch(applyEditLexicon('ajoute des lunettes de soleil'), /soleil/i)
  })

  test("boucles d'oreilles -> earrings", () => {
    assert.match(applyEditLexicon("enleve les boucles d'oreilles"), /\bearrings\b/)
  })

  test('verbes traduits : ajoute/enleve/remplace', () => {
    assert.match(applyEditLexicon('ajoute un chapeau'), /^add\b/)
    assert.match(applyEditLexicon('enleve le collier'), /^remove\b/)
    assert.match(applyEditLexicon('remplace le fond'), /^replace\b/)
  })

  test('mot a initiale accentuee gere (frontiere Unicode, pas \\b ASCII)', () => {
    // "écharpe" commence par un accent : \b ASCII ne le voit pas comme mot.
    assert.match(applyEditLexicon('ajoute une écharpe'), /\bscarf\b/)
  })

  test('couleur des cheveux -> hair color (bon ordre des mots)', () => {
    assert.match(applyEditLexicon('change la couleur des cheveux en blond'), /hair color into blonde/)
  })

  test('coiffure : longueur/texture/couleur traduites + ordre EN correct', () => {
    // le bug "cheveux courts" -> "hair courts" (court ignore -> cheveux longs)
    assert.equal(applyEditLexicon('ajoute des cheveux courts'), 'add short hair')
    assert.equal(applyEditLexicon('ajoute des cheveux longs blonds'), 'add long blonde hair')
    assert.equal(applyEditLexicon('ajoute des cheveux mi-longs ondulés'), 'add medium-length wavy hair')
    assert.equal(applyEditLexicon('ajoute des cheveux roux bouclés'), 'add red curly hair')
    // "cheveux" seul reste "hair"
    assert.equal(applyEditLexicon('ajoute des cheveux'), 'add hair')
  })

  test('connecteur et/ou et vetements', () => {
    assert.equal(applyEditLexicon('ajoute une barbe et des cheveux longs'), 'add a beard and long hair')
    assert.match(applyEditLexicon('change la chemise en rouge'), /change the shirt into red/)
    assert.match(applyEditLexicon('mets un pull'), /\bsweater\b/)
  })
})

describe('looksFrench — porte de traduction', () => {
  test('detecte le francais', () => {
    assert.equal(looksFrench('ajoute un noeud papillon'), true)
    assert.equal(looksFrench('change la couleur des cheveux'), true)
  })
  test('laisse l anglais tranquille', () => {
    assert.equal(looksFrench('add a bow tie'), false)
    assert.equal(looksFrench('remove the sunglasses'), false)
  })
})

describe('translateEditInstructionToEnglish — sans LLM (lexique seul)', () => {
  test('prompt anglais inchange (zero corruption)', async () => {
    const en = 'add a red bow tie around the neck'
    assert.equal(await translateEditInstructionToEnglish(en), en)
  })

  test('noeud papillon est resolu sans appel LLM', async () => {
    const out = await translateEditInstructionToEnglish('ajoute un noeud papillon')
    assert.match(out, /\bbow tie\b/)
    assert.doesNotMatch(out, /papillon|butterfly/i)
  })

  test('ne leve jamais et renvoie une chaine non vide', async () => {
    const out = await translateEditInstructionToEnglish('remplace le fond par une plage')
    assert.ok(typeof out === 'string' && out.length > 0)
    assert.match(out, /\bbeach\b/)
  })

  test('traduit une suppression complete puis ajout de Happy sur epaule droite', async () => {
    const out = await translateEditInstructionToEnglish(
      'suppression complete de l homme metis et ajout du chat de Fairy Tail nomme Happy assis sur l epaule droite',
    )

    assert.match(out, /remove the mixed-race man/i)
    assert.match(out, /Happy, the cat from Fairy Tail/i)
    assert.match(out, /sitting on the right shoulder/i)
    assert.doesNotMatch(out, /\b(homme|metis|chat|epaule|assis|nomme)\b/i)
  })
})

describe('translateEditInstructionToEnglish — polish LLM', () => {
  test('appelle le LLM quand du francais subsiste, et accepte un retour anglais', async () => {
    let called = false
    const generate = async (_model: string, _prompt: string) => {
      called = true
      return { response: 'add a green checkered scarf around the neck' }
    }
    // "à" (accent) survit au lexique -> du francais residuel subsiste -> LLM appele.
    const out = await translateEditInstructionToEnglish(
      'ajoute une écharpe à carreaux verts',
      { generate, model: 'qwen3:14b', timeoutMs: 5000 },
    )
    assert.equal(called, true)
    assert.match(out, /scarf/)
    assert.equal(looksFrench(out), false)
  })

  test('repli sur le lexique si le LLM renvoie du francais', async () => {
    const generate = async () => ({ response: 'ajoute une echarpe française' })
    const out = await translateEditInstructionToEnglish(
      'ajoute une écharpe à carreaux',
      { generate, model: 'qwen3:14b', timeoutMs: 5000 },
    )
    // le garde-fou rejette le retour francais -> on garde le lexique (scarf present)
    assert.match(out, /scarf/)
  })

  test('repli sur le lexique si le LLM timeout', async () => {
    const generate = () => new Promise<{ response: string }>(() => { /* ne resout jamais */ })
    const out = await translateEditInstructionToEnglish(
      'ajoute une écharpe à pois dorée',
      { generate, model: 'qwen3:14b', timeoutMs: 200 },
    )
    assert.match(out, /scarf/)
  })
})

describe('buildKontextInstruction — chemin englishCore', () => {
  test('quand englishCore fourni : tout en anglais, sans cible francaise', () => {
    const intent = parseImageIntent('ajoute un noeud papillon', { hasReference: true })
    const instr = buildKontextInstruction('ajoute un noeud papillon', intent, {
      englishCore: 'add a black bow tie',
    })
    assert.match(instr, /add a black bow tie/)
    assert.match(instr, /Integrate the requested new element/i)
    assert.match(instr, /Keep everything else unchanged/i)
    // aucune fuite de francais dans l'instruction finale
    assert.doesNotMatch(instr, /noeud|papillon/i)
  })

  test('sans englishCore : comportement historique (repli FR) preserve', () => {
    const intent = parseImageIntent('ajoute un chapeau rouge', { hasReference: true })
    const instr = buildKontextInstruction('ajoute un chapeau rouge', intent)
    assert.match(instr, /Add .*chapeau rouge/i)
  })

  test('ajout cape noire + flammes bleues préserve la tenue originale et le visage', () => {
    const prompt = 'ajout d une cape noir et donc flamme bleu en plus'
    const intent = parseImageIntent(prompt, { hasReference: true })
    const lex = applyEditLexicon(prompt)
    assert.match(lex, /black cape/i)
    assert.match(lex, /blue flames/i)

    const instr = buildKontextInstruction(prompt, intent, {
      englishCore: 'add a black cape and additional blue flames',
    })
    assert.match(instr, /add a black cape and additional blue flames/i)
    assert.match(instr, /worn over the character's body/i)
    assert.match(instr, /clothing keep their original colors.*unchanged/i)
    assert.match(instr, /flames.*appear around the character alongside existing elements/i)
    assert.match(instr, /same face, same hair/i)
  })

  test('demande nuit étoilée applique un background_change sans foule ni altération de personnage', () => {
    const prompt = 'demande nuit étoilée'
    const intent = parseImageIntent(prompt, { hasReference: true })
    assert.equal(intent.editMode, 'background_change')

    const lex = applyEditLexicon(prompt)
    assert.match(lex, /starry night sky/i)

    const instr = buildKontextInstruction(prompt, intent, {
      englishCore: 'change the background into a starry night sky with glowing stars',
    })
    assert.match(instr, /Change only the background and sky/i)
    assert.match(instr, /Preserve the foreground character's exact face, facial features, hair style, hair color/i)
    assert.match(instr, /Do not add any random bystanders, extra crowd/i)
  })
})
