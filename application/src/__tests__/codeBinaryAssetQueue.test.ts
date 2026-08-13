import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { describeBinaryAssetSkip, isBinaryAssetPath } from '../services/codeBinaryAssetPaths.ts'
import { buildGenerationQueueFromArchitecturePlan } from '../services/codeGenerationQueue.ts'
import {
  checkArchitecturePlanFileContract,
  describeArchitecturePlanContractIssue,
} from '../services/codeArchitecturePlanContract.ts'
import { executeCodeGenerationQueue } from '../services/codeGenerationExecutor.ts'
import { isLoadBearingItem } from '../services/codeGenerationExecutor.ts'
import type { CodeGenerationQueueItem } from '../services/codeGenerationQueue.ts'

/** Plan reduit a la forme REELLE du run 1081: des images dans la file WS3. */
const PLAN_1081 = JSON.stringify({
  schemaVersion: 'aurora.code.architecture-plan.v1',
  projectType: 'spa_react',
  summary: 'Site vitrine de brulerie avec une mini page admin pour les commandes.',
  stack: { dependencies: [{ name: 'react', version: '18', type: 'runtime' }], scripts: [{ name: 'build', command: 'vite build', purpose: 'build' }] },
  execution: { install: ['npm install'], dev: ['npm run dev'], build: ['npm run build'], test: [], preview: 'npm run preview' },
  dataFlow: ['Les commandes vivent dans un store local lu par la page admin.'],
  risks: [{ risk: 'Pas de paiement reel', mitigation: 'Formulaire de demonstration explicite' }],
  validation: ['npm run build passe', 'la page admin liste les commandes'],
  files: [
    { path: 'index.html', role: 'coquille', language: 'html', required: true, imports: [], exports: [], notes: [] },
    { path: 'package.json', role: 'manifeste', language: 'json', required: true, imports: [], exports: [], notes: [] },
    { path: 'src/App.tsx', role: 'racine', language: 'tsx', required: true, imports: [], exports: [], notes: [] },
    { path: 'public/logo.svg', role: 'logo', language: 'svg', required: true, imports: [], exports: [], notes: [] },
    { path: 'public/coffee-hero.jpg', role: 'hero', language: 'jpg', required: true, imports: [], exports: [], notes: [] },
    { path: 'public/team-photo.jpg', role: 'equipe', language: 'jpg', required: true, imports: [], exports: [], notes: [] },
    { path: 'README.md', role: 'doc', language: 'markdown', required: true, imports: [], exports: [], notes: [] },
  ],
  generationOrder: [
    'index.html', 'package.json', 'src/App.tsx',
    'public/logo.svg', 'public/coffee-hero.jpg', 'public/team-photo.jpg', 'README.md',
  ],
})

describe('ressources binaires — on ne pose pas une question sans reponse', () => {
  test('le predicat distingue le binaire du texte, .svg compris', () => {
    for (const path of ['public/team-photo.jpg', 'a/b.PNG', 'fonts/x.woff2', 'assets/scene.glb', 'demo.mp4', 'db.sqlite3']) {
      assert.equal(isBinaryAssetPath(path), true, path)
    }
    // `.svg` est du XML: le run 1081 en a produit un valide. Le critere est
    // « binaire », pas « ressource ».
    for (const path of ['public/logo.svg', 'src/App.tsx', 'style.css', 'README.md', 'data.json', 'Dockerfile']) {
      assert.equal(isBinaryAssetPath(path), false, path)
    }
  })

  test('la file WS3 ne demande plus les images au modele', () => {
    const queue = buildGenerationQueueFromArchitecturePlan(PLAN_1081)
    assert.ok(queue)
    assert.deepEqual(
      queue.items.map((i) => i.path),
      ['index.html', 'package.json', 'src/App.tsx', 'public/logo.svg', 'README.md'],
    )
    assert.deepEqual(queue.binaryAssetPaths, ['public/coffee-hero.jpg', 'public/team-photo.jpg'])
    // Les ordres restent contigus apres retrait: l executor les affiche.
    assert.deepEqual(queue.items.map((i) => i.order), [1, 2, 3, 4, 5])
  })

  test('le contrat de plan ne reclame pas ce que la file ne produit plus', () => {
    // Sans cette symetrie, le contrat exigerait `public/team-photo.jpg`, la
    // regeneration serait declenchee, et elle echouerait a nouveau: le piege du
    // conseil irrealisable.
    const delivered = [
      { name: 'index.html', language: 'html', content: '<!DOCTYPE html><html></html>' },
      { name: 'package.json', language: 'json', content: '{"name":"x"}' },
      { name: 'src/App.tsx', language: 'tsx', content: 'export default function App() { return null }' },
      { name: 'public/logo.svg', language: 'svg', content: '<svg />' },
    ]
    const report = checkArchitecturePlanFileContract(delivered, PLAN_1081)
    assert.ok(report)
    assert.deepEqual(report.missingRequiredFiles, [])
    assert.equal(report.ok, true)
    assert.equal(describeArchitecturePlanContractIssue(delivered, PLAN_1081), null)
    assert.equal(report.checkedRequiredFiles.includes('public/team-photo.jpg'), false)
  })

  test('le saut est NOMME, jamais silencieux', () => {
    const text = describeBinaryAssetSkip(['public/a.jpg', 'public/b.png'])
    assert.match(text, /2 ressource\(s\) binaire\(s\)/)
    assert.match(text, /phase d assets/)
    assert.equal(describeBinaryAssetSkip([]), '')
  })
})

describe('un fichier illisible ne detruit plus le projet entier', () => {
  const item = (path: string, required: boolean): CodeGenerationQueueItem => ({
    path, order: 1, required, role: '', language: null, imports: [], exports: [], notes: [],
  })

  test('porteur de livraison vs simple fichier requis', () => {
    for (const path of ['package.json', 'index.html', 'src/main.tsx', 'vite.config.ts', 'tsconfig.json', 'app.py']) {
      assert.equal(isLoadBearingItem(item(path, true)), true, path)
    }
    for (const path of ['src/components/Admin.tsx', 'src/data/coffees.ts', 'src/utils/formatters.ts', 'src/App.css']) {
      assert.equal(isLoadBearingItem(item(path, true)), false, path)
    }
  })

  test('le 30e fichier requis illisible est saute, les 29 autres survivent', async () => {
    const queue = {
      source: 'architecture_plan' as const,
      items: [item('src/components/Admin.tsx', true)],
      requiredCount: 1, optionalCount: 0, omittedOrderPaths: [], binaryAssetPaths: [],
    }
    const already = Array.from({ length: 29 }, (_, i) => ({
      name: `src/f${i}.tsx`, language: 'tsx', content: `export const F${i} = 1\n`,
    }))
    const result = await executeCodeGenerationQueue({
      queue,
      initialFiles: already,
      nextMeta: () => ({ runId: 1, sequence: 0, timestamp: 0 }),
      produceActions: async () => { throw new Error('action_protocol_invalid:protocol_marker_missing') },
    })

    assert.equal(result.ok, true)
    assert.equal(result.files.length, 29)
    assert.ok(result.events.some((e) => /illisible apres plusieurs tentatives/.test(String(e.message ?? ''))))
  })

  test('un PORTEUR de livraison illisible reste bloquant', async () => {
    const queue = {
      source: 'architecture_plan' as const,
      items: [item('package.json', true)],
      requiredCount: 1, optionalCount: 0, omittedOrderPaths: [], binaryAssetPaths: [],
    }
    const already = Array.from({ length: 29 }, (_, i) => ({
      name: `src/f${i}.tsx`, language: 'tsx', content: `export const F${i} = 1\n`,
    }))
    const result = await executeCodeGenerationQueue({
      queue,
      initialFiles: already,
      nextMeta: () => ({ runId: 1, sequence: 0, timestamp: 0 }),
      produceActions: async () => { throw new Error('action_protocol_invalid:protocol_marker_missing') },
    })

    assert.equal(result.ok, false)
    assert.match(String(result.error), /action_producer_failed/)
    // Le travail reste rendu a l appelant, qui le preservera.
    assert.equal(result.files.length, 29)
  })

  test('sans rien de livrable encore, tout fichier requis reste bloquant', async () => {
    const queue = {
      source: 'architecture_plan' as const,
      items: [item('src/components/Admin.tsx', true)],
      requiredCount: 1, optionalCount: 0, omittedOrderPaths: [], binaryAssetPaths: [],
    }
    const result = await executeCodeGenerationQueue({
      queue,
      initialFiles: [{ name: 'index.html', language: 'html', content: '<html></html>' }],
      nextMeta: () => ({ runId: 1, sequence: 0, timestamp: 0 }),
      produceActions: async () => { throw new Error('action_protocol_invalid:protocol_marker_missing') },
    })

    assert.equal(result.ok, false)
  })
})
