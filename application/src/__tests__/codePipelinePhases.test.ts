import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  isArchitecturePlanUsable,
  runIntentPhase,
} from '../services/codePipelinePhases.ts'

describe('codePipelinePhases', () => {
  test('valide uniquement les plans architecte exploitables', () => {
    const validPlan = [
      '### Comprehension',
      'Application React complete avec routage et donnees persistantes.',
      '### Stack',
      'React, TypeScript, Vite, Zustand.',
      '### Fichiers a generer',
      '- `package.json`',
      '- `src/App.tsx`',
      '- `src/main.tsx`',
      '- `src/store/useTodos.ts`',
      '### Commandes',
      '`npm install` puis `npm run dev`.',
      'Ce plan contient assez de details pour piloter une generation fichier par fichier.',
    ].join('\n')

    assert.equal(isArchitecturePlanUsable(validPlan), true)
    assert.equal(isArchitecturePlanUsable('### Stack\nReact'), false)
    assert.equal(isArchitecturePlanUsable(null), false)
  })

  test('runIntentPhase route par le classifieur deterministe et emet la phase', () => {
    const phases: Array<[string, number]> = []
    const intent = runIntentPhase('cree une page HTML vitrine responsive', (detail, progress) => {
      phases.push([detail, progress])
    })

    assert.equal(intent.projectType, 'static_web')
    assert.deepEqual(phases[0], ['Classification du projet...', 5])
  })
})
