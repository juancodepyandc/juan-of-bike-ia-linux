import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  IMAGE_STYLES,
  buildPrompt,
  parseBrief,
  type ImageBrief,
} from '../services/imagePromptBuilder.ts'

describe('buildPrompt — composition de base', () => {
  test('subject seul → positive contient subject', () => {
    const r = buildPrompt({ subject: 'un chat noir' })
    assert.ok(r.positive.startsWith('un chat noir'))
  })

  test('avec style photoréaliste → qualifiers ajoutés', () => {
    const r = buildPrompt({ subject: 'portrait', style: 'photorealistic' })
    assert.ok(r.positive.includes('hyperrealistic'))
    assert.ok(r.positive.includes('8k'))
  })

  test('avec composition + lighting + mood → tous présents', () => {
    const r = buildPrompt({
      subject: 'landscape',
      composition: 'wide-shot',
      lighting: 'golden-hour',
      mood: 'serene',
    })
    assert.ok(r.positive.includes('wide'))
    assert.ok(r.positive.includes('golden hour'))
    assert.ok(r.positive.includes('serene'))
  })

  test('paletteHints inclus en color palette', () => {
    const r = buildPrompt({
      subject: 'fleur',
      paletteHints: ['#ff8800', '#5e3c98'],
    })
    assert.ok(r.positive.includes('color palette'))
    assert.ok(r.positive.includes('#ff8800'))
  })
})

describe('buildPrompt — negative prompt', () => {
  test('toujours inclut "lowres" et "jpeg artifacts"', () => {
    const r = buildPrompt({ subject: 'x' })
    assert.ok(r.negative.includes('lowres'))
    assert.ok(r.negative.includes('jpeg artifacts'))
  })

  test('photorealistic → "cartoon" + "3d render" exclus', () => {
    const r = buildPrompt({ subject: 'x', style: 'photorealistic' })
    assert.ok(r.negative.includes('cartoon'))
    assert.ok(r.negative.includes('3d render'))
  })

  test('anime → photorealistic exclu', () => {
    const r = buildPrompt({ subject: 'x', style: 'anime-clean' })
    assert.ok(r.negative.includes('photorealistic'))
  })

  test('manga-bw → "color" exclu', () => {
    const r = buildPrompt({ subject: 'x', style: 'manga-bw' })
    assert.ok(r.negative.includes('color'))
  })

  test('pas de doublons dans negative', () => {
    const r = buildPrompt({ subject: 'x', style: 'photorealistic' })
    const tokens = r.negative.split(', ')
    assert.equal(new Set(tokens).size, tokens.length)
  })
})

describe('buildPrompt — aspect ratio & dimensions', () => {
  test('default 1:1 → 1024x1024', () => {
    const r = buildPrompt({ subject: 'x' })
    assert.equal(r.width, 1024)
    assert.equal(r.height, 1024)
  })

  test('16:9 → 1344x768', () => {
    const r = buildPrompt({ subject: 'x', aspectRatio: '16:9' })
    assert.equal(r.width, 1344)
    assert.equal(r.height, 768)
  })

  test('9:16 portrait → 768x1344', () => {
    const r = buildPrompt({ subject: 'x', aspectRatio: '9:16' })
    assert.equal(r.width, 768)
    assert.equal(r.height, 1344)
  })

  test('21:9 ultra-wide → 1536x640', () => {
    const r = buildPrompt({ subject: 'x', aspectRatio: '21:9' })
    assert.equal(r.width, 1536)
    assert.equal(r.height, 640)
  })
})

describe('buildPrompt — EXIF metadata', () => {
  test('description = subject', () => {
    const r = buildPrompt({ subject: 'mon sujet test' })
    assert.equal(r.exif.description, 'mon sujet test')
  })

  test('software contient "AuroraIA"', () => {
    const r = buildPrompt({ subject: 'x' })
    assert.ok(r.exif.software.includes('AuroraIA'))
  })

  test('userComment = positive prompt', () => {
    const r = buildPrompt({ subject: 'sujet' })
    assert.equal(r.exif.userComment, r.positive)
  })
})

describe('buildPrompt — upscale plan', () => {
  test('highResolution=false → plan none', () => {
    const r = buildPrompt({ subject: 'x' })
    assert.equal(r.upscalePlan.kind, 'none')
  })

  test('highResolution=true → realesrgan-x4 + dimensions x4', () => {
    const r = buildPrompt({ subject: 'x', aspectRatio: '1:1', highResolution: true })
    assert.equal(r.upscalePlan.kind, 'realesrgan-x4')
    assert.equal(r.upscalePlan.targetWidth, 4096)
    assert.equal(r.upscalePlan.targetHeight, 4096)
  })

  test('pixel-art highResolution utilise nearest-neighbor', () => {
    const r = buildPrompt({ subject: '32x32 sprite chevalier', style: 'pixel-art', highResolution: true })
    assert.equal(r.upscalePlan.kind, 'pixel-nearest-x4')
    assert.equal(r.renderProfile.upscaleMethod, 'nearest-neighbor-x4')
    assert.equal(r.renderProfile.logicalCanvas.width, 32)
  })
})

describe('buildPrompt - pixel art approfondi', () => {
  test('pixel art verrouille grille, palette et anti-aliasing', () => {
    const r = buildPrompt({ subject: 'sprite RPG 32x32 chevalier', style: 'pixel-art' })
    assert.match(r.positive, /nearest-neighbor/i)
    assert.match(r.positive, /indexed 16 color palette/i)
    assert.match(r.negative, /anti-aliasing/i)
    assert.match(r.negative, /smooth gradients/i)
    assert.ok(r.qualityChecklist.some((item) => /grille de pixels/.test(item)))
    assert.ok(r.styleGuide.engineHints.some((item) => /basse resolution logique/.test(item)))
  })
})

describe('buildPrompt - toutes les categories de rendu', () => {
  test('chaque style exporte ajoute un vrai contrat de medium', () => {
    for (const style of IMAGE_STYLES) {
      const result = buildPrompt({ subject: 'sujet test', style })

      assert.ok(result.positive.length > 80, `${style} doit enrichir le prompt positif`)
      assert.ok(result.negative.split(', ').length >= 6, `${style} doit avoir des exclusions utiles`)
      assert.ok(result.qualityChecklist.length >= 6, `${style} doit avoir une checklist solide`)
      assert.ok(result.styleGuide.engineHints.length >= 3, `${style} doit guider le moteur`)
      assert.ok(result.qualityChecklist.includes('medium stylistique respecte'))
    }
  })
})

describe('parseBrief — détection style', () => {
  test('"photo réaliste" → photorealistic', () => {
    assert.equal(parseBrief('photo réaliste d un chien').style, 'photorealistic')
  })

  test('"cinematic" → cinematic', () => {
    assert.equal(parseBrief('paysage cinematic').style, 'cinematic')
  })

  test('"aquarelle" → aquarelle', () => {
    assert.equal(parseBrief('aquarelle de Paris').style, 'aquarelle')
  })

  test('"manga noir" → manga-bw', () => {
    assert.equal(parseBrief('portrait manga noir et blanc').style, 'manga-bw')
  })

  test('"anime" sans noir → anime-clean', () => {
    assert.equal(parseBrief('anime girl').style, 'anime-clean')
  })

  test('"pixel art" → pixel-art', () => {
    assert.equal(parseBrief('pixel art chevalier').style, 'pixel-art')
  })

  test('"sprite Aseprite" → pixel-art', () => {
    assert.equal(parseBrief('sprite Aseprite chevalier 32x32').style, 'pixel-art')
  })

  test('aucun style mentionné → undefined', () => {
    assert.equal(parseBrief('un chat').style, undefined)
  })
})

describe('parseBrief — détection lighting', () => {
  test('"golden hour" → golden-hour', () => {
    assert.equal(parseBrief('photo golden hour').lighting, 'golden-hour')
  })

  test('"coucher de soleil" → golden-hour', () => {
    assert.equal(parseBrief('coucher de soleil sur la mer').lighting, 'golden-hour')
  })

  test('"neon cyberpunk" → neon-cyberpunk', () => {
    assert.equal(parseBrief('rue neon cyberpunk').lighting, 'neon-cyberpunk')
  })

  test('"brouillard" → volumetric-fog', () => {
    assert.equal(parseBrief('forêt brouillard').lighting, 'volumetric-fog')
  })

  test('aucun lighting → undefined', () => {
    assert.equal(parseBrief('un chat').lighting, undefined)
  })
})

describe('parseBrief — aspect ratio', () => {
  test('"portrait" → 9:16', () => {
    assert.equal(parseBrief('portrait classique').aspectRatio, '9:16')
  })

  test('"paysage 16:9" → 16:9', () => {
    assert.equal(parseBrief('paysage 16:9').aspectRatio, '16:9')
  })

  test('"carré" → 1:1', () => {
    assert.equal(parseBrief('photo carré').aspectRatio, '1:1')
  })

  test('rien spécifié → undefined', () => {
    assert.equal(parseBrief('un chat').aspectRatio, undefined)
  })
})

describe('parseBrief — palette + résolution', () => {
  test('hex extraits dans paletteHints', () => {
    const r = parseBrief('logo avec #ff8800 et #5e3c98')
    assert.ok(r.paletteHints?.includes('#ff8800'))
    assert.ok(r.paletteHints?.includes('#5e3c98'))
  })

  test('"haute résolution" → highResolution=true', () => {
    assert.equal(parseBrief('photo haute résolution').highResolution, true)
  })

  test('"8k" → highResolution=true', () => {
    assert.equal(parseBrief('rendu 8k').highResolution, true)
  })

  test('pas de mention → highResolution=false', () => {
    assert.equal(parseBrief('un chat').highResolution, false)
  })
})

describe('parseBrief — accent-insensitive', () => {
  test('"résolution" et "resolution" donnent même résultat', () => {
    const a = parseBrief('haute résolution')
    const b = parseBrief('haute resolution')
    assert.equal(a.highResolution, b.highResolution)
  })

  test('"isométrique" → isometric-3d', () => {
    assert.equal(parseBrief('vue isométrique').style, 'isometric-3d')
  })
})

describe('Pipeline parseBrief → buildPrompt', () => {
  test('cohérent end-to-end', () => {
    const brief = parseBrief('photo réaliste golden hour, portrait, 4k')
    const built = buildPrompt({ ...brief, subject: 'jeune femme' })
    assert.ok(built.positive.includes('jeune femme'))
    assert.ok(built.positive.includes('hyperrealistic'))
    assert.ok(built.positive.includes('golden hour'))
    assert.equal(built.upscalePlan.kind, 'realesrgan-x4')
    assert.equal(built.width, 768)
  })
})
