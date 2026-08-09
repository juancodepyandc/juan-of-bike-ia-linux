// Verrouille le repli de plan d architecture.
//
// Panne reelle en verification de bout en bout: l architecte a rendu, sur TOUS
// ses candidats, un JSON valide mais de moins de deux fichiers
// (architecture_plan_invalid:files_min_2). runPlanningPhase levait, puis
// runFullPipeline levait sur isArchitecturePlanUsable. Zero fichier livre,
// alors que l intention etait parfaitement connue — et que le repli existait
// deja un etage plus bas, jamais atteint.

import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { buildFallbackArchitecturePlan } from '../services/codeArchitecturePlanFallback.ts'
import { parseArchitecturePlanJson } from '../services/codeArchitecturePlan.ts'
import { buildGenerationQueueFromArchitecturePlan } from '../services/codeGenerationQueue.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'

const PROMPTS = [
  'landing page premium pour la marque Mercedes-Benz, hero anime, section specs',
  'dashboard fintech temps reel, graphique live, tableau triable',
  'script python qui parse un csv et sort un rapport',
  'jeu pong arcade canvas avec score',
  'application react avec routage et theme sombre',
]

describe('buildFallbackArchitecturePlan', () => {
  test('produit un plan VALIDE pour chaque type de projet courant', () => {
    for (const prompt of PROMPTS) {
      const intent = classifyCodeIntent(prompt)
      const plan = buildFallbackArchitecturePlan(intent, prompt)
      const parsed = parseArchitecturePlanJson(plan)
      assert.equal(parsed.ok, true, `plan invalide pour "${prompt}": ${parsed.errors.join(',')}`)
    }
  })

  test('respecte le minimum de deux fichiers, meme pour un projet mono-fichier', () => {
    // C est exactement le cas qui a tue le run: files_min_2.
    const prompt = 'script python qui parse un csv'
    const intent = classifyCodeIntent(prompt)
    const parsed = parseArchitecturePlanJson(buildFallbackArchitecturePlan(intent, prompt))
    assert.equal(parsed.ok, true, parsed.errors.join(','))
    assert.ok(parsed.plan.files.length >= 2, `attendu >= 2 fichiers, obtenu ${parsed.plan.files.length}`)
  })

  test('garde la porte d entree du type de projet', () => {
    const prompt = 'landing page premium pour la marque Mercedes-Benz'
    const intent = classifyCodeIntent(prompt)
    const parsed = parseArchitecturePlanJson(buildFallbackArchitecturePlan(intent, prompt))
    assert.equal(parsed.ok, true)
    assert.ok(
      parsed.plan.files.some((f) => f.path.toLowerCase() === 'index.html'),
      `index.html absent: ${parsed.plan.files.map((f) => f.path).join(', ')}`,
    )
  })

  test('le plan de repli produit une file de generation exploitable', () => {
    const prompt = 'landing page premium pour la marque Mercedes-Benz'
    const intent = classifyCodeIntent(prompt)
    const queue = buildGenerationQueueFromArchitecturePlan(buildFallbackArchitecturePlan(intent, prompt))
    assert.ok(queue, 'la file ne doit pas etre nulle')
    assert.ok(queue.items.length >= 2, `file trop courte: ${queue.items.length}`)
  })

  test('le plan de repli annonce clairement ce qu il est', () => {
    const intent = classifyCodeIntent(PROMPTS[0])
    const parsed = parseArchitecturePlanJson(buildFallbackArchitecturePlan(intent, PROMPTS[0]))
    assert.match(parsed.plan.summary, /repli/i)
    assert.ok(parsed.plan.risks.length >= 1, 'le repli doit declarer son propre risque')
  })

  test('conserve le projectType de l intent', () => {
    const prompt = 'jeu pong arcade canvas avec score'
    const intent = classifyCodeIntent(prompt)
    const parsed = parseArchitecturePlanJson(buildFallbackArchitecturePlan(intent, prompt))
    assert.equal(parsed.plan.projectType, intent.projectType)
  })
})

describe('parseArchitecturePlanJson — reparation des caracteres de controle', () => {
  test('un plan avec de vrais sauts de ligne dans une chaine est repare', () => {
    const plan = {
      schemaVersion: 'aurora.code.architecture-plan.v1',
      projectType: 'static_web',
      summary: 'PLACEHOLDER_SUMMARY_LONG_ENOUGH_FOR_THE_SCHEMA_CHECK',
      stack: { runtime: 'node', packageManager: 'npm', languages: ['js'], frameworks: [], dependencies: [], scripts: [] },
      files: [
        { path: 'index.html', role: 'page', language: 'html', required: true, imports: [], exports: [], notes: [] },
        { path: 'style.css', role: 'styles', language: 'css', required: true, imports: [], exports: [], notes: [] },
      ],
      dataFlow: ['a -> b'],
      execution: { install: [], dev: [], build: [], test: [], preview: 'index.html' },
      generationOrder: ['index.html', 'style.css'],
      validation: ['ok1', 'ok2'],
      risks: [{ risk: 'r', mitigation: 'm' }],
      design: { palette: [], typography: [], ux: [], responsive: [] },
    }
    // Injecte un VRAI saut de ligne dans le summary, comme le fait le modele.
    const broken = JSON.stringify(plan).replace('PLACEHOLDER_SUMMARY_LONG_ENOUGH_FOR_THE_SCHEMA_CHECK', 'ligne une\nligne deux, resume assez long pour passer')
    assert.throws(() => JSON.parse(broken), 'le JSON doit bien etre casse au depart')
    const parsed = parseArchitecturePlanJson(broken)
    assert.equal(parsed.ok, true, `attendu repare, erreurs=${parsed.errors.join(',')}`)
  })

  test('un plan valide reste parse a l identique', () => {
    const intent = classifyCodeIntent(PROMPTS[0])
    const plan = buildFallbackArchitecturePlan(intent, PROMPTS[0])
    assert.equal(parseArchitecturePlanJson(plan).ok, true)
  })
})
