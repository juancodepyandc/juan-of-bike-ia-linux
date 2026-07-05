/**
 * Tests pour services/entNotesAnalysis — trend analysis des notes ENT.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  normalizeGrade,
  groupBySubject,
  subjectTrend,
  analyzeAllSubjects,
  formatTrend,
} from '../services/entNotesAnalysis.ts'
import type { HarvestNoteItem } from '../services/entHarvestService.ts'

function note(overrides: Partial<HarvestNoteItem> = {}): HarvestNoteItem {
  return {
    subject: 'Maths',
    grade: 12,
    scale: 20,
    classAverage: 11,
    date: '2026-03-15',
    title: 'DS chapitre 4',
    ...overrides,
  }
}

describe('normalizeGrade', () => {
  test('grade /20 → renvoie tel quel', () => {
    assert.equal(normalizeGrade(15, 20), 15)
  })

  test('grade /10 → multiplie par 2', () => {
    assert.equal(normalizeGrade(7, 10), 14)
  })

  test('grade /100 (pourcentage) → /20 équivalent', () => {
    assert.equal(normalizeGrade(75, 100), 15)
  })

  test('null → null', () => {
    assert.equal(normalizeGrade(null), null)
  })

  test('NaN → null', () => {
    assert.equal(normalizeGrade(NaN), null)
  })

  test('scale absent : grade ≤ 20 → /20', () => {
    assert.equal(normalizeGrade(13), 13)
  })

  test('scale absent : grade > 20 → suppose pourcentage', () => {
    assert.equal(normalizeGrade(80), 16)
  })

  test('scale absent : grade > 100 → null', () => {
    assert.equal(normalizeGrade(150), null)
  })
})

describe('groupBySubject', () => {
  test('regroupe par subject', () => {
    const notes = [
      note({ subject: 'Maths', grade: 10 }),
      note({ subject: 'Physique', grade: 14 }),
      note({ subject: 'Maths', grade: 16 }),
    ]
    const g = groupBySubject(notes)
    assert.equal(g.Maths.length, 2)
    assert.equal(g.Physique.length, 1)
  })

  test('tri chronologique ascendant par date', () => {
    const notes = [
      note({ date: '2026-03-15' }),
      note({ date: '2026-01-10' }),
      note({ date: '2026-02-20' }),
    ]
    const g = groupBySubject(notes)
    const dates = g.Maths.map((n) => n.date)
    assert.deepEqual(dates, ['2026-01-10', '2026-02-20', '2026-03-15'])
  })

  test('subject vide → ignoré', () => {
    const notes = [note({ subject: '' }), note({ subject: 'Maths' })]
    const g = groupBySubject(notes)
    assert.equal(Object.keys(g).length, 1)
    assert.ok('Maths' in g)
  })

  test('subject trim les whitespaces', () => {
    const notes = [note({ subject: '  Maths  ' })]
    const g = groupBySubject(notes)
    assert.ok('Maths' in g)
  })
})

describe('subjectTrend', () => {
  test('aucune note valide → priority 0, direction unknown', () => {
    const t = subjectTrend('Maths', [])
    assert.equal(t.noteCount, 0)
    assert.equal(t.priority, 0)
    assert.equal(t.direction, 'unknown')
  })

  test('moyenne calculée correctement', () => {
    const t = subjectTrend('Maths', [
      note({ grade: 10 }),
      note({ grade: 14 }),
      note({ grade: 12 }),
    ])
    assert.equal(t.studentAvg, 12)
    assert.equal(t.noteCount, 3)
  })

  test('classAvg agrégée si disponible', () => {
    const t = subjectTrend('Maths', [
      note({ grade: 10, classAverage: 9 }),
      note({ grade: 12, classAverage: 11 }),
    ])
    assert.equal(t.classAvg, 10)
    assert.equal(t.gapVsClass, 1)
  })

  test('direction up si notes croissantes', () => {
    const t = subjectTrend('Maths', [
      note({ grade: 8, date: '2026-01-01' }),
      note({ grade: 10, date: '2026-02-01' }),
      note({ grade: 14, date: '2026-03-01' }),
    ])
    // Note: subjectTrend reçoit notes déjà triées normalement, mais ici on les passe brutes.
    // Le slope est calculé dans l'ordre du tableau passé.
    assert.equal(t.direction, 'up')
  })

  test('direction down si notes décroissantes', () => {
    const t = subjectTrend('Maths', [
      note({ grade: 16 }),
      note({ grade: 13 }),
      note({ grade: 10 }),
    ])
    assert.equal(t.direction, 'down')
  })

  test('priority haute si moyenne basse', () => {
    const low = subjectTrend('Maths', [note({ grade: 5 }), note({ grade: 6 })])
    const high = subjectTrend('Maths', [note({ grade: 17 }), note({ grade: 18 })])
    assert.ok(low.priority > high.priority)
  })

  test('priority bumped si sous-classe', () => {
    const underclass = subjectTrend('Maths', [note({ grade: 10, classAverage: 14 })])
    const overclass = subjectTrend('Maths', [note({ grade: 10, classAverage: 8 })])
    assert.ok(underclass.priority > overclass.priority)
  })

  test('priority ∈ [0..100]', () => {
    const t = subjectTrend('Maths', [note({ grade: 5, classAverage: 15 })])
    assert.ok(t.priority >= 0 && t.priority <= 100)
  })

  test('recentNormalized normalisé [0..1]', () => {
    const t = subjectTrend('Maths', [note({ grade: 20 }), note({ grade: 10 }), note({ grade: 5 })])
    for (const v of t.recentNormalized) {
      assert.ok(v >= 0 && v <= 1)
    }
  })

  test('recentNormalized limité à 6 dernières', () => {
    const notes = Array.from({ length: 10 }, (_, i) => note({ grade: i }))
    const t = subjectTrend('Maths', notes)
    assert.equal(t.recentNormalized.length, 6)
  })
})

describe('analyzeAllSubjects', () => {
  test('renvoie array triée par priority desc', () => {
    const notes = [
      note({ subject: 'Maths', grade: 5 }),         // priority haute
      note({ subject: 'Physique', grade: 18 }),     // priority basse
      note({ subject: 'Anglais', grade: 12 }),       // moyenne
    ]
    const trends = analyzeAllSubjects(notes)
    assert.equal(trends.length, 3)
    for (let i = 1; i < trends.length; i++) {
      assert.ok(trends[i - 1].priority >= trends[i].priority)
    }
  })

  test('aucune note → []', () => {
    assert.deepEqual(analyzeAllSubjects([]), [])
  })
})

describe('formatTrend', () => {
  test('format avec arrow up + gap positif', () => {
    const t = subjectTrend('Maths', [
      note({ grade: 14, classAverage: 12 }),
      note({ grade: 16, classAverage: 13 }),
    ])
    const s = formatTrend(t)
    assert.ok(s.includes('Maths'))
    assert.ok(s.includes('/20'))
    assert.ok(/[▲▼→]/.test(s))
  })

  test('format avec gap négatif', () => {
    const t = subjectTrend('Maths', [note({ grade: 8, classAverage: 13 })])
    const s = formatTrend(t)
    assert.ok(s.includes('-') || s.includes('vs classe'))
  })

  test('format sans classe disponible', () => {
    const t = subjectTrend('Maths', [note({ grade: 12, classAverage: null })])
    const s = formatTrend(t)
    assert.ok(!s.includes('vs classe'))
  })
})
