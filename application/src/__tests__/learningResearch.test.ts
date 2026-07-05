/**
 * Tests pour services/learningResearch — détection niveau académique +
 * builders prompt + context block.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  detectAcademicIntent,
  buildAcademicLevelInstructions,
  buildContextBlock,
  summarizeSourcesForUI,
  type LearningSource,
} from '../services/learningResearch.ts'

describe('detectAcademicIntent — niveaux principaux', () => {
  test('"primaire CM1" → level primaire', () => {
    const r = detectAcademicIntent('mathématiques niveau primaire CM1')
    assert.equal(r.level, 'primaire')
  })

  test('"6eme college" → college', () => {
    const r = detectAcademicIntent('cours histoire 6eme college')
    assert.ok(['college', 'brevet'].includes(r.level))
  })

  test('"brevet 3eme" → brevet', () => {
    const r = detectAcademicIntent('annales brevet 3eme')
    assert.equal(r.level, 'brevet')
  })

  test('"seconde" → seconde', () => {
    const r = detectAcademicIntent('programme seconde lycee')
    assert.equal(r.level, 'seconde')
  })

  test('"premiere lycee" → premiere', () => {
    const r = detectAcademicIntent('cours premiere lycee SVT')
    assert.ok(['premiere', 'terminale', 'bac'].includes(r.level))
  })

  test('"terminale" → terminale', () => {
    const r = detectAcademicIntent('cours terminale spe maths')
    assert.equal(r.level, 'terminale')
  })

  test('"baccalaureat" → bac ou terminale', () => {
    const r = detectAcademicIntent('preparation baccalaureat')
    assert.ok(['bac', 'terminale'].includes(r.level))
  })

  test('"prepa MPSI" → prepa', () => {
    const r = detectAcademicIntent('prepa MPSI programme')
    assert.equal(r.level, 'prepa')
  })

  test('"licence L2" → licence', () => {
    const r = detectAcademicIntent('cours licence L2 mathematiques')
    assert.equal(r.level, 'licence')
  })

  test('"master M1" → master', () => {
    const r = detectAcademicIntent('master M1 informatique')
    assert.equal(r.level, 'master')
  })

  test('"doctorat" → doctorat', () => {
    const r = detectAcademicIntent('these de doctorat en biologie')
    assert.equal(r.level, 'doctorat')
  })

  test('"sujet général" → level general', () => {
    const r = detectAcademicIntent('quelques infos sur les chats')
    assert.equal(r.level, 'general')
  })
})

describe('detectAcademicIntent — examen focus', () => {
  test('"annales" → isExamFocus true', () => {
    const r = detectAcademicIntent('annales du bac 2023')
    assert.equal(r.isExamFocus, true)
    assert.ok(r.examKeywords.includes('annales'))
  })

  test('"epreuve type" → isExamFocus + keyword', () => {
    const r = detectAcademicIntent('epreuve type maths terminale')
    assert.equal(r.isExamFocus, true)
    assert.ok(r.examKeywords.includes('epreuve type'))
  })

  test('"oral grand oral" → keyword oral', () => {
    const r = detectAcademicIntent('preparation oral terminale')
    assert.equal(r.isExamFocus, true)
    assert.ok(r.examKeywords.includes('oral'))
  })

  test('sujet général → isExamFocus false', () => {
    const r = detectAcademicIntent('curiosite sur les volcans')
    assert.equal(r.isExamFocus, false)
    assert.deepEqual(r.examKeywords, [])
  })
})

describe('detectAcademicIntent — depth', () => {
  test('"approfondi" → depth approfondi', () => {
    const r = detectAcademicIntent('explique en detail approfondi les ondes')
    assert.ok(['approfondi', 'expert'].includes(r.depth))
  })

  test('"expert" → depth expert', () => {
    const r = detectAcademicIntent('analyse expert tres pointue physique')
    assert.ok(['expert', 'approfondi'].includes(r.depth))
  })

  test('basique → depth base', () => {
    const r = detectAcademicIntent('intro simple')
    assert.equal(r.depth, 'base')
  })

  test('"prepa" force depth expert', () => {
    const r = detectAcademicIntent('cours prepa MP')
    assert.equal(r.depth, 'expert')
  })
})

describe('buildAcademicLevelInstructions', () => {
  test('primaire → vocabulaire enfant', () => {
    const r = buildAcademicLevelInstructions({ level: 'primaire', isExamFocus: false, examKeywords: [], depth: 'base' })
    assert.ok(r.toLowerCase().includes('enfant') || r.toLowerCase().includes('simple'))
  })

  test('terminale → mention bac', () => {
    const r = buildAcademicLevelInstructions({ level: 'terminale', isExamFocus: false, examKeywords: [], depth: 'base' })
    assert.ok(r.toLowerCase().includes('bac'))
  })

  test('prepa → mention rigueur', () => {
    const r = buildAcademicLevelInstructions({ level: 'prepa', isExamFocus: false, examKeywords: [], depth: 'expert' })
    assert.ok(r.toLowerCase().includes('rigueur') || r.toLowerCase().includes('demonstration'))
  })

  test('isExamFocus → instructions FOCUS EXAMENS ajoutées', () => {
    const r = buildAcademicLevelInstructions({ level: 'terminale', isExamFocus: true, examKeywords: ['annales'], depth: 'base' })
    assert.ok(r.includes('FOCUS EXAMENS'))
  })

  test('depth expert → instructions ajoutées', () => {
    const r = buildAcademicLevelInstructions({ level: 'licence', isExamFocus: false, examKeywords: [], depth: 'expert' })
    assert.ok(r.includes('EXPERT') || r.includes('demonstrations'))
  })

  test('depth approfondi → instructions ajoutées', () => {
    const r = buildAcademicLevelInstructions({ level: 'seconde', isExamFocus: false, examKeywords: [], depth: 'approfondi' })
    assert.ok(r.toLowerCase().includes('approfondi'))
  })

  test('niveau inconnu fallback → general', () => {
    const r = buildAcademicLevelInstructions({ level: 'general', isExamFocus: false, examKeywords: [], depth: 'base' })
    assert.ok(r.length > 20)
  })
})

describe('buildContextBlock', () => {
  test('sources vides → ""', () => {
    assert.equal(buildContextBlock([]), '')
  })

  test('sources avec URL → URL incluse', () => {
    const sources: LearningSource[] = [{
      origin: 'wikipedia-fr',
      title: 'Pythagore',
      url: 'https://fr.wikipedia.org/wiki/Pythagore',
      extract: 'Pythagore est un mathématicien grec',
    }]
    const r = buildContextBlock(sources)
    assert.ok(r.includes('Wikipedia FR'))
    assert.ok(r.includes('Pythagore'))
    assert.ok(r.includes('https://fr.wikipedia.org/wiki/Pythagore'))
  })

  test('plusieurs sources → numérotées [S1] [S2]', () => {
    const sources: LearningSource[] = [
      { origin: 'wikipedia-fr', title: 'A', extract: 'extA' },
      { origin: 'wikipedia-en', title: 'B', extract: 'extB' },
    ]
    const r = buildContextBlock(sources)
    assert.ok(r.includes('[S1]'))
    assert.ok(r.includes('[S2]'))
  })

  test('origin mappés correctement', () => {
    const sources: LearningSource[] = [
      { origin: 'duckduckgo', title: 'A', extract: 'x' },
      { origin: 'llm-synthesis', title: 'B', extract: 'y' },
    ]
    const r = buildContextBlock(sources)
    assert.ok(r.includes('DuckDuckGo'))
    assert.ok(r.includes('Synthese'))
  })

  test('mentionne règle abstention', () => {
    const r = buildContextBlock([{ origin: 'wikipedia-fr', title: 'T', extract: 'e' }])
    assert.ok(r.toLowerCase().includes('abstenir') || r.toLowerCase().includes('information generale'))
  })
})

describe('summarizeSourcesForUI', () => {
  test('sources vides → message dédié', () => {
    const r = summarizeSourcesForUI([])
    assert.ok(r.includes('Aucune'))
  })

  test('1-3 sources → labels affichés', () => {
    const r = summarizeSourcesForUI([
      { origin: 'wikipedia-fr', title: 'A', extract: 'x' },
    ])
    assert.ok(r.includes('Wikipedia FR'))
    assert.ok(r.includes('A'))
  })

  test('> 3 sources → "+N autres"', () => {
    const sources: LearningSource[] = Array.from({ length: 6 }, (_, i) => ({
      origin: 'wikipedia-fr',
      title: `T${i}`,
      extract: 'x',
    }))
    const r = summarizeSourcesForUI(sources)
    assert.ok(r.includes('+3 autres'))
  })

  test('séparateur " · "', () => {
    const r = summarizeSourcesForUI([
      { origin: 'wikipedia-fr', title: 'A', extract: 'x' },
      { origin: 'wikipedia-en', title: 'B', extract: 'y' },
    ])
    assert.ok(r.includes('·'))
  })
})
