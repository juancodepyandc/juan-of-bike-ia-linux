import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION } from '../services/codeArchitecturePlan.ts'
import {
  isArchitecturePlanUsable,
  runIntentPhase,
} from '../services/codePipelinePhases.ts'

describe('codePipelinePhases', () => {
  test('valide uniquement les plans architecte JSON schema-valides', () => {
    const validPlan = JSON.stringify({
      schemaVersion: CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
      projectType: 'spa_react',
      summary: 'Application React complete avec routage et donnees persistantes.',
      stack: {
        runtime: 'node',
        packageManager: 'npm',
        languages: ['TypeScript'],
        frameworks: ['React', 'Vite'],
        dependencies: [{ name: 'react', version: '^19.0.0', type: 'runtime', reason: 'ui' }],
        scripts: [{ name: 'dev', command: 'npm run dev', purpose: 'preview' }],
      },
      files: [
        { path: 'package.json', role: 'manifest', required: true },
        { path: 'src/App.tsx', role: 'app', required: true },
      ],
      dataFlow: ['user -> app -> state'],
      execution: {
        install: ['npm install'],
        dev: ['npm run dev'],
        build: ['npm run build'],
        test: ['npm run build'],
        preview: 'vite',
      },
      generationOrder: ['package.json', 'src/App.tsx'],
      validation: ['build vert', 'preview visible'],
      risks: [{ risk: 'imports manquants', mitigation: 'generer tous les fichiers' }],
      design: { palette: ['oklch'], typography: ['Inter'], ux: ['fluide'], responsive: ['mobile'] },
    })

    assert.equal(isArchitecturePlanUsable(validPlan), true)
    assert.equal(isArchitecturePlanUsable('### Stack\nReact'), false)
    assert.equal(isArchitecturePlanUsable(null), false)
  })

  test('runIntentPhase retombe sur le classifieur deterministe sans modele et emet la phase', async () => {
    const phases: Array<[string, number]> = []
    // Sans configuredCodeModel, aucun appel LLM: repli deterministe garanti.
    const intent = await runIntentPhase('cree une page HTML vitrine responsive', (detail, progress) => {
      phases.push([detail, progress])
    })

    assert.equal(intent.projectType, 'static_web')
    assert.deepEqual(phases[0], ['Classification du projet...', 5])
  })
})
