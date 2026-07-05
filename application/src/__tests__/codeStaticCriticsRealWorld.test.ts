/**
 * Tests anti-faux-positifs : applique les critics statiques sur du vrai
 * code AuroraIA-v2 qui est manifestement OK. Si une règle se déclenche
 * en blocker, c'est qu'elle est trop large.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compositeStaticCritic, securityCritic } from '../services/codeStaticCritics.ts'
import type { CodeProject } from '../services/codeMultiPassCritique.ts'
import type { CodeIntent } from '../services/codeIntent.ts'

const fakeIntent = {} as CodeIntent

function loadProject(paths: string[]): CodeProject {
  return {
    generationId: 'aurora-real',
    files: paths.map((p) => {
      const content = readFileSync(`src/${p}`, 'utf-8')
      const ext = p.split('.').pop() ?? 'ts'
      return { name: p, language: ext, content }
    }),
  }
}

describe('Real-world code : pas de faux positif blocker', () => {
  test('un service Aurora bien-écrit ne déclenche aucun blocker', async () => {
    const projects = [
      ['services/simulator/analyticIntegrators.ts'],
      ['services/learning/spacedRepetition.ts'],
      ['services/cyber/kdfCostAnalyzer.ts'],
      ['services/conversationMemory.ts'],
      ['services/imagePromptBuilder.ts'],
    ]
    for (const paths of projects) {
      const project = loadProject(paths)
      const report = await compositeStaticCritic(project, fakeIntent)
      const blockers = report.issues.filter((i) => i.severity === 'block')
      assert.equal(blockers.length, 0, `Faux positifs blocker dans ${paths[0]}: ${blockers.map((b) => b.message).join(' | ')}`)
    }
  })

  test('overall score ≥ 0.7 sur du code Aurora réel', async () => {
    const project = loadProject([
      'services/simulator/analyticIntegrators.ts',
      'services/simulator/dataRecorder.ts',
    ])
    const r = await compositeStaticCritic(project, fakeIntent)
    assert.ok(r.overallScore >= 0.7, `score ${r.overallScore} sur du code propre`)
  })

  test('aucune règle SQLi/NoSQLi/LDAP/redirect ne s\'active sur le tokenizer FR', async () => {
    const project = loadProject(['services/conversationMemory.ts'])
    const r = await securityCritic(project, fakeIntent)
    const flagged = r.issues.filter((i) =>
      /SQL injection|NoSQL|LDAP|redirect|ReDoS|prototype pollution/i.test(i.message),
    )
    assert.equal(flagged.length, 0, `Faux positifs sur conversationMemory : ${flagged.map((f) => f.message).join(' | ')}`)
  })

  test('aucun blocker sur le code-loop service', async () => {
    const project = loadProject(['services/codeMultiPassCritique.ts'])
    const r = await securityCritic(project, fakeIntent)
    const blockers = r.issues.filter((i) => i.severity === 'block')
    assert.equal(blockers.length, 0, `Faux positifs : ${blockers.map((b) => b.message).join(' | ')}`)
  })
})
