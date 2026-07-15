/**
 * Tests pour services/auroraExpertPrompts — catalogue de prompts system
 * principal-engineer-grade pour chaque module Aurora.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  EXPERT,
  buildSystemPrompt,
  isExpertGrade,
  type ModuleKey,
} from '../services/auroraExpertPrompts.ts'

const ALL_MODULES: ModuleKey[] = [
  'conversation', 'code', 'image', 'voice', 'video',
  'drawing', 'threeD', 'learning', 'cyber', 'simulator', 'cowork',
]

describe('EXPERT catalogue', () => {
  test('contient les 11 modules attendus', () => {
    for (const m of ALL_MODULES) {
      assert.ok(m in EXPERT, `module ${m} manquant`)
    }
  })

  test('chaque module a identity/qualityBar/negative non vides', () => {
    for (const m of ALL_MODULES) {
      const s = EXPERT[m]
      assert.ok(s.identity.length > 50, `${m} identity trop court`)
      assert.ok(s.qualityBar.length > 50, `${m} qualityBar trop court`)
      assert.ok(s.negative.length > 30, `${m} negative trop court`)
    }
  })

  test('identity contient la BASE_VOICE Aurora', () => {
    for (const m of ALL_MODULES) {
      assert.ok(
        EXPERT[m].identity.includes('Aurora'),
        `${m} identity doit mentionner Aurora`,
      )
    }
  })

  test('code module a outputFormat', () => {
    assert.ok(EXPERT.code.outputFormat)
    assert.ok(EXPERT.code.outputFormat!.includes('AURORA_CODE_VFS/1'))
    assert.ok(EXPERT.code.outputFormat!.includes('length'))
  })

  test('conversation module mentionne Juan/STI2D', () => {
    assert.ok(EXPERT.conversation.identity.includes('STI2D'))
  })

  test('threeD module mentionne Hunyuan3D', () => {
    assert.ok(EXPERT.threeD.identity.includes('Hunyuan3D'))
  })

  test('cyber module : no refus principe + OSCP-level', () => {
    assert.ok(EXPERT.cyber.identity.includes('OSCP'))
    assert.ok(EXPERT.cyber.negative.toLowerCase().includes('refus'))
  })
})

describe('buildSystemPrompt', () => {
  test('renvoie chaîne contenant identity + qualité + interdits', () => {
    const p = buildSystemPrompt('code')
    assert.ok(p.includes('Aurora'))
    assert.ok(p.includes('Qualité'))
    assert.ok(p.includes('Interdits'))
  })

  test('module avec outputFormat inclut "Format de sortie"', () => {
    const p = buildSystemPrompt('code')
    assert.ok(p.includes('Format de sortie'))
    assert.ok(p.includes('AURORA_CODE_VFS/1'))
  })

  test('module sans outputFormat n inclut PAS Format de sortie', () => {
    const p = buildSystemPrompt('conversation')
    assert.ok(!p.includes('Format de sortie'))
  })

  test('chaque module produit un prompt > 500 chars', () => {
    for (const m of ALL_MODULES) {
      const p = buildSystemPrompt(m)
      assert.ok(p.length > 500, `${m} prompt trop court (${p.length})`)
    }
  })

  test('respect de l ordre identity puis qualité puis interdits', () => {
    const p = buildSystemPrompt('image')
    const idxIdent = p.indexOf('Aurora')
    const idxQual = p.indexOf('Qualité')
    const idxNeg = p.indexOf('Interdits')
    assert.ok(idxIdent < idxQual)
    assert.ok(idxQual < idxNeg)
  })
})

describe('isExpertGrade', () => {
  test('prompt contenant 2+ markers expert → true', () => {
    const txt = 'Tu es un principal-engineer avec AbortController et WCAG AA'
    assert.equal(isExpertGrade(txt), true)
  })

  test('prompt vide → false', () => {
    assert.equal(isExpertGrade(''), false)
  })

  test('prompt avec 1 marker seulement → false', () => {
    assert.equal(isExpertGrade('principal-engineer'), false)
  })

  test('prompt construit par buildSystemPrompt("code") → expert', () => {
    const p = buildSystemPrompt('code')
    assert.equal(isExpertGrade(p), true)
  })

  test('prompt construit par buildSystemPrompt("threeD") → expert', () => {
    const p = buildSystemPrompt('threeD')
    assert.equal(isExpertGrade(p), true)
  })

  test('prompt construit par buildSystemPrompt("voice") → expert', () => {
    const p = buildSystemPrompt('voice')
    assert.equal(isExpertGrade(p), true)
  })

  test('prompt construit par buildSystemPrompt("cowork") → expert', () => {
    const p = buildSystemPrompt('cowork')
    assert.equal(isExpertGrade(p), true)
  })

  test('prompt naïf non-expert → false', () => {
    const naive = 'Tu es un assistant. Sois sympa et donne des bonnes réponses.'
    assert.equal(isExpertGrade(naive), false)
  })
})

describe('Cohérence catalogue', () => {
  test('aucun module ne contient un placeholder de scaffold (XXX/FIXME/lorem)', () => {
    for (const m of ALL_MODULES) {
      const all = EXPERT[m].identity + EXPERT[m].qualityBar + EXPERT[m].negative
      assert.ok(!/\bXXX\b|\bFIXME\b|lorem ipsum/i.test(all), `${m} contient un placeholder`)
    }
  })

  test('qualityBar de chaque module est numérotée (1)/2)/...', () => {
    for (const m of ALL_MODULES) {
      const q = EXPERT[m].qualityBar
      assert.ok(/\b1\)/.test(q), `${m} qualityBar non numérotée`)
      assert.ok(/\b2\)/.test(q), `${m} qualityBar < 2 items`)
    }
  })

  test('aucun emoji décoratif dans les prompts', () => {
    for (const m of ALL_MODULES) {
      const all = EXPERT[m].identity + EXPERT[m].qualityBar + EXPERT[m].negative
      // matches typical emoji ranges via unicode escape (no emoji literal in code)
      assert.ok(!/[\u{1F300}-\u{1FAFF}]/u.test(all), `${m} contient un emoji`)
    }
  })
})
