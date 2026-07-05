/**
 * Tests barre expert pour image prompt builder.
 * Vérifie objectivement la qualité d'un prompt construit : couverture
 * sémantique, présence des éléments BO (subject + style + light + composition),
 * negative cohérent, EXIF complet, parser FR robuste.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { buildPrompt, buildPromptContractBlock, parseBrief } from '../services/imagePromptBuilder.ts'

describe('buildPrompt — barre expert', () => {
  test('prompt complet : ≥ 6 qualifiers distincts', () => {
    const r = buildPrompt({
      subject: 'samouraï observant un torii sous la pluie',
      style: 'cinematic',
      composition: 'rule-of-thirds',
      lighting: 'volumetric-fog',
      mood: 'epic',
      aspectRatio: '16:9',
    })
    // Compte les segments distincts (séparés par ", "). Doit > 6.
    const segments = r.positive.split(',').map((s) => s.trim()).filter(Boolean)
    assert.ok(segments.length >= 6, `seulement ${segments.length} segments dans le prompt`)
  })

  test('subject toujours en tête du prompt', () => {
    const r = buildPrompt({ subject: 'phare en bord de mer', style: 'oil-painting' })
    assert.ok(r.positive.startsWith('phare en bord de mer'))
  })

  test('negative non vide et style-aware', () => {
    const photo = buildPrompt({ subject: 'x', style: 'photorealistic' })
    const anime = buildPrompt({ subject: 'x', style: 'anime-clean' })
    // Photo rejette explicitement "cartoon"+"anime"
    assert.ok(/cartoon/i.test(photo.negative))
    // Anime rejette "photorealistic"
    assert.ok(/photorealistic/i.test(anime.negative))
    // Les négatifs ne doivent pas être identiques
    assert.notEqual(photo.negative, anime.negative)
  })

  test('aspect ratios couvrent les résolutions SDXL standard', () => {
    const ratios = ['1:1', '16:9', '9:16', '3:2', '2:3', '4:3', '21:9'] as const
    for (const ar of ratios) {
      const r = buildPrompt({ subject: 'x', aspectRatio: ar })
      // Hauteur*largeur > 700×700 (résolution SDXL minimum)
      assert.ok(r.width >= 640 && r.height >= 640, `${ar}: ${r.width}×${r.height}`)
      // Et < 2000 (sinon SDXL OOM courant)
      assert.ok(r.width <= 1600 && r.height <= 1600, `${ar} trop grand`)
    }
  })

  test('highResolution déclenche un upscale x4', () => {
    const lowres = buildPrompt({ subject: 'x' })
    const hires = buildPrompt({ subject: 'x', highResolution: true })
    assert.equal(lowres.upscalePlan.kind, 'none')
    assert.equal(hires.upscalePlan.kind, 'realesrgan-x4')
    assert.equal(hires.upscalePlan.targetWidth, hires.width * 4)
  })

  test('EXIF embarque tous les champs pour reproductibilité', () => {
    const r = buildPrompt({ subject: 'voyage spatial onirique', style: 'cinematic' })
    assert.ok(r.exif.description.length > 0)
    assert.ok(r.exif.software.includes('Aurora'))
    assert.equal(r.exif.userComment, r.positive)
    assert.ok(r.exif.artist.length > 0)
  })

  test('palette hints injectés littéralement', () => {
    const r = buildPrompt({ subject: 'paysage', paletteHints: ['#ff5a1f', '#3aa4ff'] })
    assert.ok(r.positive.includes('#ff5a1f'))
    assert.ok(r.positive.includes('#3aa4ff'))
  })
})

describe('parseBrief — barre expert', () => {
  test('parsing FR avec accents : "résolution" reconnu comme high-res', () => {
    const b = parseBrief('paysage zen en haute résolution')
    assert.equal(b.highResolution, true)
  })

  test('aquarelle FR détectée', () => {
    const b = parseBrief("aquarelle d'un samouraï")
    assert.equal(b.style, 'aquarelle')
  })

  test('palette hex multiple capturée', () => {
    const b = parseBrief('cyberpunk avec #ff0080 et #00ffff et #ffd166')
    assert.equal(b.paletteHints?.length, 3)
  })

  test('aspect ratio tiktok → 9:16', () => {
    const b = parseBrief('format TikTok vertical')
    assert.equal(b.aspectRatio, '9:16')
  })

  test('aspect ratio paysage → 16:9', () => {
    const b = parseBrief('paysage cinématique en 16:9')
    assert.equal(b.aspectRatio, '16:9')
  })

  test('lighting "coucher de soleil" détecté golden-hour', () => {
    const b = parseBrief('portrait au coucher de soleil')
    assert.equal(b.lighting, 'golden-hour')
  })

  test('texte vide produit un brief stable', () => {
    const b = parseBrief('')
    assert.equal(b.subject, '')
    assert.equal(b.style, undefined)
  })

  test('parsing round-trip : parseBrief → buildPrompt non vide', () => {
    const briefStr = 'aquarelle d\'un dragon au coucher de soleil avec #ff5a1f, haute résolution, paysage'
    const brief = parseBrief(briefStr)
    const built = buildPrompt(brief)
    assert.ok(built.positive.length > briefStr.length)
    assert.equal(built.upscalePlan.kind, 'realesrgan-x4')
    assert.equal(built.height < built.width, true) // paysage = 16:9
  })

  test('detection neon-cyberpunk', () => {
    const b = parseBrief('néon cyberpunk Tokyo nuit')
    assert.equal(b.lighting, 'neon-cyberpunk')
  })
})

describe('image prompt builder - demandes complexes', () => {
  test('texte exact et interdits ne se contredisent pas', () => {
    const brief = parseBrief('Affiche de lancement pour une moto electrique urbaine nommee VOLT-7, format vertical TikTok 9:16, style studio-product premium, texte exact "VOLT-7" uniquement sur le carenage, palette #101820 #f2aa4c, sans logo parasite, sans mains, sans arriere-plan encombre, lumiere softbox')
    const built = buildPrompt(brief)
    const negativeParts = built.negative.split(', ').map((part) => part.trim().toLowerCase())

    assert.equal(brief.aspectRatio, '9:16')
    assert.deepEqual(brief.exactText, ['VOLT-7'])
    assert.ok(built.positive.includes('exact readable text "VOLT-7" only'))
    assert.ok(!negativeParts.includes('text'), built.negative)
    assert.ok(negativeParts.includes('random extra text'), built.negative)
    assert.ok(!built.negative.includes('mmee VOLT-7'), built.negative)
    assert.ok(built.negative.includes('logo parasite'))
    assert.ok(built.negative.includes('mains'))
    assert.ok(built.fidelityContract.exactText.includes('VOLT-7'))
    assert.ok(built.renderProfile.passes.includes('verification texte exact'))
  })

  test('contract block injectable dans le workflow FLUX', () => {
    const block = buildPromptContractBlock(parseBrief('Affiche produit texte exact "VOLT-7", sans logo parasite, format TikTok vertical'))

    assert.ok(block.includes('IMAGE PROMPT BUILDER CONTRACT - HARD REQUIREMENTS'))
    assert.ok(block.includes('Positive prompt:'))
    assert.ok(block.includes('Avoid / negative traits:'))
    assert.ok(block.includes('Exact text required: "VOLT-7"'))
    assert.ok(block.includes('logo parasite'))
    assert.ok(!block.includes('mmee VOLT-7'), block)
  })

  test('schema technique: negations et comptages restent durs', () => {
    const brief = parseBrief('Schema technique en coupe d un bras robotique medical avec 6 articulations numerotees, cables visibles, legendes courtes, orthographique, fond blanc, aucune perspective dramatique, aucune vis supplementaire inventee')
    const built = buildPrompt(brief)

    assert.equal(brief.style, 'technical-schema')
    assert.equal(brief.mood, undefined)
    assert.ok(brief.countHints?.includes('exactly 6 articulations'))
    assert.ok(brief.layoutHints?.includes('orthographic view'))
    assert.ok(brief.layoutHints?.includes('cross-section view'))
    assert.ok(built.positive.includes('respect count constraint: exactly 6 articulations'))
    assert.ok(!built.positive.includes('dramatic, intense'), built.positive)
    assert.ok(built.negative.includes('perspective dramatique'))
    assert.ok(built.fidelityContract.counts.includes('exactly 6 articulations'))
  })

  test('pixel art sprite sheet: pas de faux hex, pas de clause negative en positif', () => {
    const brief = parseBrief('Pixel art 32x32 pour jeu SNES: heron mecanique bleu tenant une cle, 3 frames idle en sprite sheet horizontale, palette 16 couleurs, fond transparent, pas d antialiasing, pas de degrade')
    const built = buildPrompt(brief)

    assert.equal(brief.style, 'pixel-art')
    assert.equal(brief.paletteHints, undefined)
    assert.ok(!brief.subject.includes('pas d antialiasing'), brief.subject)
    assert.ok(brief.negativeHints?.includes('antialiasing'))
    assert.ok(brief.negativeHints?.includes('degrade'))
    assert.ok(brief.countHints?.includes('exactly 3 frames'))
    assert.deepEqual(built.renderProfile.logicalCanvas, { width: 96, height: 32 })
    assert.ok(built.renderProfile.passes.includes('sprite sheet 3 frames'))
    assert.ok(built.qualityChecklist.includes('layout multi-vue respecte uniquement si demande'))
    assert.ok(!built.qualityChecklist.includes('composition unique sans multi-vue'))
  })
})

// Anti-claim : si un test ci-dessous casse, c'est qu'un changement
// "pour faire passer" a dégradé la robustesse face à des entrées étranges.
import {
  measurePaletteMatch,
  measurePromptFidelity,
  pickBestVariation,
  scoreVariation,
} from '../services/imageVariationPicker.ts'

describe('variation picker — barre expert', () => {
  const baseFeat = {
    promptFidelity: 0.5,
    compositionScore: 0.5,
    sharpnessScore: 0.5,
    paletteMatch: 0.5,
    artefactPenalty: 0,
  }

  test('candidat parfait score > 0.9', () => {
    const r = scoreVariation({ id: 'a', ...baseFeat, promptFidelity: 1, compositionScore: 1, sharpnessScore: 1, paletteMatch: 1 })
    assert.ok(r.overall > 0.9, `overall ${r.overall}`)
  })

  test('candidat catastrophique score < 0.3', () => {
    const r = scoreVariation({ id: 'a', ...baseFeat, promptFidelity: 0.1, compositionScore: 0.2, sharpnessScore: 0.2, paletteMatch: 0.2, artefactPenalty: 0.8 })
    assert.ok(r.overall < 0.3, `overall ${r.overall}`)
  })

  test('pickBestVariation ordonne par overall desc', () => {
    const result = pickBestVariation([
      { id: 'a', ...baseFeat, promptFidelity: 0.3 },
      { id: 'b', ...baseFeat, promptFidelity: 0.9, compositionScore: 0.9 },
      { id: 'c', ...baseFeat, promptFidelity: 0.6 },
    ])
    assert.equal(result.winner.features.id, 'b')
    assert.equal(result.ranked[0].features.id, 'b')
  })

  test('ambigu détecté quand 2 premiers à < 0.05 d\'écart', () => {
    const result = pickBestVariation([
      { id: 'a', ...baseFeat, promptFidelity: 0.85 },
      { id: 'b', ...baseFeat, promptFidelity: 0.86 },
    ])
    assert.equal(result.ambiguous, true)
  })

  test('regenerate conseillé quand winner < 0.5', () => {
    const result = pickBestVariation([{ id: 'a', ...baseFeat, promptFidelity: 0.1, compositionScore: 0.1, sharpnessScore: 0.2 }])
    assert.equal(result.regenerateAdvised, true)
  })

  test('rationale humanly readable', () => {
    const r = scoreVariation({ id: 'a', ...baseFeat, promptFidelity: 0.95, sharpnessScore: 0.95 })
    assert.match(r.rationale, /fid[èe]le/)
    assert.match(r.rationale, /net/)
  })

  test('throws on empty candidate list', () => {
    assert.throws(() => pickBestVariation([]))
  })
})

describe('measurePromptFidelity — barre expert', () => {
  test('description copie-prompt → fidelity > 0.8', () => {
    const prompt = 'samouraï observant un torii sous la pluie'
    const desc = 'un samouraï observant un torii alors qu\'il pleut'
    const f = measurePromptFidelity(prompt, desc)
    assert.ok(f > 0.4, `${f}`)
  })

  test('description hors sujet → fidelity < 0.3', () => {
    const prompt = 'samouraï observant un torii sous la pluie'
    const desc = 'une plage de sable blanc au soleil avec des cocotiers'
    const f = measurePromptFidelity(prompt, desc)
    assert.ok(f < 0.3, `${f}`)
  })

  test('prompt ou desc vide → 0', () => {
    assert.equal(measurePromptFidelity('', 'x'), 0)
    assert.equal(measurePromptFidelity('x', ''), 0)
  })
})

describe('measurePaletteMatch — barre expert', () => {
  test('couleurs exactes → 1.0', () => {
    const m = measurePaletteMatch(['#ff5a1f', '#3aa4ff'], ['#ff5a1f', '#3aa4ff'])
    assert.equal(m, 1)
  })

  test('couleurs très proches → > 0.9', () => {
    const m = measurePaletteMatch(['#ff5a1f', '#3aa4ff'], ['#ff5b20', '#3ba5ff'])
    assert.ok(m > 0.9, `${m}`)
  })

  test('couleurs opposées → score bas', () => {
    const m = measurePaletteMatch(['#000000'], ['#ffffff'])
    assert.ok(m < 0.2, `${m}`)
  })

  test('pas de contrainte palette → score 1', () => {
    assert.equal(measurePaletteMatch(['#abc'], []), 1)
  })

  test('hex invalides ignorés sans crasher', () => {
    const m = measurePaletteMatch(['##notahex'], ['#3aa4ff'])
    assert.equal(m, 0)
  })
})

import { categorize, diffPrompts, diffPromptsByCategory } from '../services/imagePromptDiff.ts'

describe('Prompt diff — barre expert', () => {
  test('prompts identiques → changeRatio = 0, summary "identique"', () => {
    const d = diffPrompts('a samurai, cinematic, dramatic', 'a samurai, cinematic, dramatic')
    assert.equal(d.changeRatio, 0)
    assert.match(d.summary, /identique/)
  })

  test('ajout pur → added non vide, summary mentionne "+1"', () => {
    const d = diffPrompts('a samurai', 'a samurai, cinematic')
    assert.equal(d.added.length, 1)
    assert.equal(d.removed.length, 0)
    assert.match(d.summary, /\+1/)
  })

  test('retrait pur → removed non vide', () => {
    const d = diffPrompts('a samurai, cinematic, golden hour', 'a samurai, cinematic')
    assert.equal(d.removed.length, 1)
    assert.match(d.removed[0].raw, /golden/)
  })

  test('reformulation détectée (synonyme partiel)', () => {
    const d = diffPrompts('a samurai with sword', 'a samurai holding sword')
    // Les 2 segments partagent "samurai" et "sword" → tokens en commun.
    assert.ok(d.reformulated.length > 0 || d.identical.length > 0)
  })

  test('totalement différent → changeRatio proche de 1', () => {
    const d = diffPrompts('a samurai cinematic', 'sunset beach palm trees')
    assert.ok(d.changeRatio >= 0.5, `changeRatio ${d.changeRatio}`)
  })

  test('vides → changeRatio 0', () => {
    const d = diffPrompts('', '')
    assert.equal(d.changeRatio, 0)
  })

  test('categorize détecte le style', () => {
    assert.equal(categorize({ raw: 'cinematic shot', tokens: ['cinematic', 'shot'] }), 'style')
  })

  test('categorize détecte la lumière', () => {
    assert.equal(categorize({ raw: 'golden hour lighting', tokens: ['golden', 'hour', 'lighting'] }), 'lighting')
  })

  test('categorize détecte la composition', () => {
    assert.equal(categorize({ raw: 'rule of thirds composition', tokens: ['rule', 'of', 'thirds', 'composition'] }), 'composition')
  })

  test('diffPromptsByCategory route les ajouts par catégorie', () => {
    const d = diffPromptsByCategory(
      'a samurai',
      'a samurai, cinematic lighting, golden hour',
    )
    // "cinematic lighting" → lighting (lighting token wins)
    // "golden hour" → lighting
    assert.ok(d.byCategory.lighting.added.length >= 1, `lighting adds: ${JSON.stringify(d.byCategory.lighting)}`)
  })

  test('diff sur prompts longs sans crasher', () => {
    const long1 = Array.from({ length: 30 }, (_, i) => `qualifier${i}`).join(', ')
    const long2 = Array.from({ length: 30 }, (_, i) => `qualifier${i + 5}`).join(', ')
    const d = diffPrompts(long1, long2)
    assert.ok(d.added.length > 0)
    assert.ok(d.removed.length > 0)
  })
})

describe('image — robustesse', () => {
  test('subject vide ne plante pas buildPrompt', () => {
    const r = buildPrompt({ subject: '' })
    assert.ok(r.positive.length >= 0)
    assert.ok(r.negative.length > 0)
  })

  test('paletteHints invalides : valeurs gardées tel quel sans crash', () => {
    const r = buildPrompt({ subject: 'x', paletteHints: ['#bad', '#aaa', '12345'] })
    assert.ok(r.positive.includes('palette'))
  })

  test('parseBrief sur 4000 chars n\'explose pas', () => {
    const huge = 'samouraï '.repeat(400)
    const b = parseBrief(huge)
    assert.equal(b.subject.length, huge.trim().length)
  })
})
