import { describe, test } from 'node:test'
import assert from 'node:assert/strict'

const {
  classifyCoworkMission,
  buildMissionContractSection,
} = await import('../services/coworkMission.ts')

describe('coworkMission classification', () => {
  test('recognises public academic/web research as research', () => {
    const profile = classifyCoworkMission('recherche en ligne des sujets officiels bac sti2d sin et fais une synthese')
    assert.equal(profile.kind, 'research')
    assert.ok(profile.preferredTools.some((tool: string) => /web_search/.test(tool)))
    assert.match(profile.finishRule, /synthese/i)
  })

  test('recognises PDF/Excel/document creation as artifact work', () => {
    const profile = classifyCoworkMission('cree un fichier Excel puis un PDF de revision et verifie le resultat')
    assert.equal(profile.kind, 'artifact')
    assert.ok(profile.requiredEvidence.some((evidence: string) => /fichier cree/i.test(evidence)))
    assert.match(profile.finishRule, /cree-le, verifie-le/i)
  })

  test('recognises SSH/server requests as remote work', () => {
    const profile = classifyCoworkMission('connecte toi a distance a mon VPS en SSH et deploie le projet')
    assert.equal(profile.kind, 'remote')
    assert.ok(profile.preferredTools.some((tool: string) => /machine_ssh/.test(tool)))
    assert.match(profile.finishRule, /probe|teste|agit/i)
  })

  test('recognises desktop application validation as debug work', () => {
    const profile = classifyCoworkMission('teste la version application desktop Tauri, pas seulement web')
    assert.equal(profile.kind, 'debug')
    assert.ok(profile.preferredTools.some((tool: string) => /tauri build|cargo check/i.test(tool)))
    assert.match(profile.finishRule, /Tauri|application/)
  })

  test('recognises coaching/organisation requests as accompaniment work', () => {
    for (const prompt of [
      'planifie ma semaine de revision du bac',
      'conseille-moi pour gerer mon budget ce mois-ci',
      'accompagne-moi pour preparer mon entretien',
    ]) {
      const profile = classifyCoworkMission(prompt)
      assert.equal(profile.kind, 'accompaniment', `kind pour: ${prompt}`)
    }
  })

  test('accompaniment finishRule forbids ending on a bare question', () => {
    const profile = classifyCoworkMission('aide-moi a m organiser et planifie ma semaine')
    assert.equal(profile.kind, 'accompaniment')
    assert.match(profile.finishRule, /Ne finis JAMAIS sur une simple question/)
  })

  test('creation request stays artifact even with a coaching verb', () => {
    const profile = classifyCoworkMission('cree un PDF de revision pour le bac')
    assert.equal(profile.kind, 'artifact')
  })
})

describe('buildMissionContractSection', () => {
  test('includes progress and recovery guidance after a failed tool', () => {
    const section = buildMissionContractSection({
      prompt: 'corrige ce bug et teste',
      runtime: 'tauri-desktop',
      history: [
        {
          action: { kind: 'shell', command: 'npm', args: ['test'] },
          result: { ok: false, error: 'missing script', durationMs: 2 },
        },
      ],
    })

    assert.match(section, /Mission probable: debug/)
    assert.match(section, /Actions KO: shellx1/)
    assert.match(section, /strategie alternative/i)
  })
})
