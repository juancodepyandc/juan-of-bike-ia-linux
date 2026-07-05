/**
 * Tests pour services/videoBrollSynthesizer — prompts SDXL/FLUX pour B-roll
 * markers alignés sur le script timing.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  extractSubject,
  synthesizeBrollPrompts,
} from '../services/videoBrollSynthesizer.ts'
import { planTimeline } from '../services/videoCompositionPlanner.ts'

describe('extractSubject', () => {
  test('phrase courte → tokens sans stopwords', () => {
    const r = extractSubject('Le chat noir mange du poisson dans le jardin')
    assert.ok(!r.toLowerCase().includes(' le '))
    assert.ok(r.includes('chat'))
    assert.ok(r.includes('poisson'))
  })

  test('ponctuation strippée', () => {
    const r = extractSubject('Le, chat ; noir : mange ! du poisson ?')
    assert.ok(!r.includes(','))
    assert.ok(!r.includes('?'))
  })

  test('maxTokens limite la longueur', () => {
    const r = extractSubject('aaa bbb ccc ddd eee fff ggg hhh', 3)
    const tokens = r.split(' ').filter(Boolean)
    assert.equal(tokens.length, 3)
  })

  test('texte vide → ""', () => {
    assert.equal(extractSubject(''), '')
  })

  test('uniquement stopwords → ""', () => {
    assert.equal(extractSubject('le la les un une des'), '')
  })

  test('case-insensitive sur les stopwords', () => {
    const r = extractSubject('LE chat NOIR')
    assert.ok(r.toLowerCase().includes('chat'))
    assert.ok(!r.toLowerCase().startsWith('le'))
  })
})

describe('synthesizeBrollPrompts', () => {
  function makeReq(over: Partial<Parameters<typeof synthesizeBrollPrompts>[0]> = {}) {
    const timeline = planTimeline({
      script: 'Python est un langage facile. Aujourd hui on apprend les listes. Les listes sont des conteneurs. Voici un exemple.',
      format: '16:9',
      tone: 'tutoriel',
      platform: 'youtube-long',
      ...((over.timeline ? {} : {}) as object),
    })
    return {
      timeline,
      script: 'Python est un langage facile. Aujourd hui on apprend les listes. Les listes sont des conteneurs. Voici un exemple.',
      wordsPerMinute: 160,
      tone: 'tutoriel' as const,
      ...over,
    }
  }

  test('renvoie un résultat par marker', () => {
    const req = makeReq()
    const r = synthesizeBrollPrompts(req)
    assert.equal(r.length, req.timeline.brollMarkers.length)
  })

  test('chaque résultat a prompt + negative + dimensions', () => {
    const req = makeReq()
    const r = synthesizeBrollPrompts(req)
    for (const item of r) {
      assert.ok(item.prompt.length > 0)
      assert.ok(item.negative.length > 0)
      assert.ok(item.width > 0)
      assert.ok(item.height > 0)
    }
  })

  test('timeline sans marker → []', () => {
    const req = makeReq()
    req.timeline.brollMarkers = []
    const r = synthesizeBrollPrompts(req)
    assert.deepEqual(r, [])
  })

  test('aspectRatio 16:9 par défaut', () => {
    const r = synthesizeBrollPrompts(makeReq())
    if (r.length > 0) {
      assert.equal(r[0].aspectRatio, '16:9')
    }
  })

  test('tone storytelling → style cinematic dans prompt', () => {
    const req = makeReq()
    const r = synthesizeBrollPrompts({ ...req, tone: 'storytelling' })
    if (r.length > 0) {
      assert.ok(r[0].prompt.toLowerCase().includes('cinema') || r[0].prompt.toLowerCase().includes('anamorphic'))
    }
  })

  test('tone pub → style studio-product', () => {
    const req = makeReq()
    const r = synthesizeBrollPrompts({ ...req, tone: 'pub' })
    if (r.length > 0) {
      assert.ok(r[0].prompt.toLowerCase().includes('studio') || r[0].prompt.toLowerCase().includes('product'))
    }
  })

  test('preferredStyle override le tone-default', () => {
    const req = makeReq()
    const r = synthesizeBrollPrompts({ ...req, preferredStyle: 'pixel-art' })
    if (r.length > 0) {
      assert.ok(r[0].prompt.toLowerCase().includes('pixel'))
    }
  })

  test('markerIndex correctement assigné', () => {
    const r = synthesizeBrollPrompts(makeReq())
    for (let i = 0; i < r.length; i++) {
      assert.equal(r[i].markerIndex, i)
    }
  })

  test('scriptExcerpt contient des mots du script', () => {
    const req = makeReq()
    const r = synthesizeBrollPrompts(req)
    if (r.length > 0) {
      const scriptWords = new Set(req.script.toLowerCase().split(/\s+/))
      const excerptWords = r[0].scriptExcerpt.toLowerCase().split(/\s+/)
      // Au moins 1 mot du script
      assert.ok(excerptWords.some((w) => scriptWords.has(w)))
    }
  })

  test('atMs correspond au marker timeline', () => {
    const req = makeReq()
    const r = synthesizeBrollPrompts(req)
    for (let i = 0; i < r.length; i++) {
      assert.equal(r[i].atMs, req.timeline.brollMarkers[i].atMs)
    }
  })
})

describe('synthesizeBrollPrompts — formats', () => {
  test('timeline 9:16 → aspectRatio 9:16', () => {
    const timeline = planTimeline({
      script: 'court script. autre phrase. encore une.',
      format: '9:16',
      tone: 'tutoriel',
      platform: 'tiktok',
    })
    const r = synthesizeBrollPrompts({
      timeline,
      script: 'court script. autre phrase. encore une.',
      wordsPerMinute: 160,
      tone: 'tutoriel',
    })
    if (r.length > 0) {
      assert.equal(r[0].aspectRatio, '9:16')
    }
  })

  test('timeline 1:1 → aspectRatio 1:1', () => {
    const timeline = planTimeline({
      script: 'court',
      format: '1:1',
      tone: 'tutoriel',
      platform: 'classroom',
    })
    const r = synthesizeBrollPrompts({
      timeline,
      script: 'court',
      wordsPerMinute: 160,
      tone: 'tutoriel',
    })
    if (r.length > 0) {
      assert.equal(r[0].aspectRatio, '1:1')
    }
  })
})
