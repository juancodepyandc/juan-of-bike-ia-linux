import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildCodegenDependencyBan,
  describeGeneratedImportRemediation,
  findCodegenDependency,
  isGeneratedArtifactPath,
  substituteCodegenDependencies,
} from '../services/codeCodegenDependencies.ts'
import { parseArchitecturePlanJson } from '../services/codeArchitecturePlan.ts'
import { buildArchitecturePlanJsonInstructions } from '../services/codeArchitecturePlanInstructions.ts'
import { buildGenerationQueueFromArchitecturePlan } from '../services/codeGenerationQueue.ts'
import { checkArchitecturePlanFileContract } from '../services/codeArchitecturePlanContract.ts'

/** Plan a la forme REELLE du run 1111: TanStack Router + son arbre genere. */
const PLAN_1111 = JSON.stringify({
  schemaVersion: 'aurora.code.architecture-plan.v1',
  projectType: 'spa_react',
  summary: 'Site vitrine de brulerie avec une mini page admin pour les commandes.',
  stack: {
    dependencies: [
      { name: 'react', version: '19.0.0', type: 'runtime', reason: 'ui' },
      { name: '@tanstack/react-router', version: '1.42.13', type: 'runtime', reason: 'routage' },
      { name: '@tanstack/router-devtools', version: '1.42.13', type: 'runtime', reason: 'debug' },
    ],
    scripts: [{ name: 'build', command: 'vite build', purpose: 'build' }],
  },
  execution: { install: ['npm install'], dev: ['npm run dev'], build: ['npm run build'], test: [], preview: 'npm run preview' },
  dataFlow: ['Les commandes vivent dans un store local lu par la page admin.'],
  risks: [{ risk: 'Pas de paiement reel', mitigation: 'Formulaire de demonstration' }],
  validation: ['npm run build passe', 'la page admin liste les commandes'],
  files: [
    { path: 'index.html', role: 'coquille', language: 'html', required: true, imports: [], exports: [], notes: [] },
    { path: 'package.json', role: 'manifeste', language: 'json', required: true, imports: [], exports: [], notes: [] },
    { path: 'src/App.tsx', role: 'racine', language: 'tsx', required: true, imports: [], exports: [], notes: [] },
    { path: 'src/routeTree.gen.ts', role: 'arbre de routes', language: 'typescript', required: true, imports: [], exports: [], notes: [] },
  ],
  generationOrder: ['index.html', 'package.json', 'src/App.tsx', 'src/routeTree.gen.ts'],
})

describe('dependances a generateur — on ne pose pas une question sans reponse', () => {
  test('le registre reconnait la famille TanStack Router et propose un remplacant', () => {
    const entry = findCodegenDependency('@tanstack/react-router')
    assert.ok(entry)
    assert.equal(entry.substitute, 'react-router-dom')
    assert.match(entry.generates, /routeTree\.gen/)
    assert.equal(findCodegenDependency('react-router-dom'), null)
    assert.equal(findCodegenDependency('react'), null)
  })

  test('les artefacts generes sont reconnus, le code ecrit a la main ne l est pas', () => {
    for (const path of ['src/routeTree.gen.ts', 'app/routes.gen.tsx', 'src/__generated__/q.ts', 'src/generated/api.ts', 'x.generated.js']) {
      assert.equal(isGeneratedArtifactPath(path), true, path)
    }
    for (const path of ['src/App.tsx', 'src/routes/index.tsx', 'src/gen.ts', 'src/generator.ts', 'package.json']) {
      assert.equal(isGeneratedArtifactPath(path), false, path)
    }
  })

  test('la substitution est deterministe et tracee', () => {
    const { dependencies, replacements } = substituteCodegenDependencies([
      { name: 'react', version: '19.0.0' },
      { name: '@tanstack/react-router', version: '1.42.13' },
      { name: '@tanstack/router-devtools', version: '1.42.13' },
    ])
    assert.deepEqual(dependencies.map((d) => d.name), ['react', 'react-router-dom'])
    // Sans remplacant, la dependance est retiree plutot que laissee irreparable.
    assert.deepEqual(replacements, ['@tanstack/react-router -> react-router-dom', '@tanstack/router-devtools retiree'])
    assert.match(String(dependencies[1].reason), /remplace @tanstack\/react-router/)
  })

  test('le plan reel du run 1111 est repare a la lecture', () => {
    const parsed = parseArchitecturePlanJson(PLAN_1111)
    assert.equal(parsed.ok, true)
    const names = parsed.plan.stack.dependencies.map((d) => d.name)
    assert.equal(names.includes('@tanstack/react-router'), false)
    assert.equal(names.includes('react-router-dom'), true)
    // Le fichier genere ne figure plus au plan: personne ne peut l ecrire.
    assert.equal(parsed.plan.files.some((f) => f.path === 'src/routeTree.gen.ts'), false)
  })

  test('la file ET le contrat s accordent: ni l une ni l autre ne reclame le genere', () => {
    const queue = buildGenerationQueueFromArchitecturePlan(PLAN_1111)
    assert.ok(queue)
    assert.equal(queue.items.some((i) => /routeTree\.gen/.test(i.path)), false)

    const delivered = [
      { name: 'index.html', language: 'html', content: '<!DOCTYPE html><html></html>' },
      { name: 'package.json', language: 'json', content: '{"name":"x"}' },
      { name: 'src/App.tsx', language: 'tsx', content: 'export default function App(){return null}' },
    ]
    const report = checkArchitecturePlanFileContract(delivered, PLAN_1111)
    assert.ok(report)
    assert.deepEqual(report.missingRequiredFiles, [])
  })

  test('la consigne du planificateur nomme l interdit ET son remplacant', () => {
    const ban = buildCodegenDependencyBan()
    assert.match(ban, /@tanstack\/react-router -> utilise react-router-dom/)
    assert.match(ban, /GENERATION DE CODE que ce pipeline n execute pas/)
    assert.ok(buildArchitecturePlanJsonInstructions().includes(ban))
  })
})

describe('conseil REALISABLE quand un artefact genere est importe malgre tout', () => {
  test('on demande de changer de bibliotheque, pas de creer le fichier', () => {
    const advice = describeGeneratedImportRemediation({
      importPath: './routeTree.gen',
      dependencyNames: ['react', '@tanstack/react-router'],
    })
    assert.ok(advice)
    assert.match(advice, /artefact GENERE/)
    assert.match(advice, /REMPLACE @tanstack\/react-router par react-router-dom/)
    // Le conseil impossible d origine ne doit plus apparaitre.
    assert.equal(/Ajouter le fichier/.test(advice), false)
  })

  test('un import local ordinaire garde le conseil normal', () => {
    assert.equal(describeGeneratedImportRemediation({
      importPath: './components/Header',
      dependencyNames: ['react'],
    }), null)
  })

  test('sans coupable identifie, on dit quand meme quoi faire', () => {
    const advice = describeGeneratedImportRemediation({
      importPath: './src/__generated__/types.ts',
      dependencyNames: ['react'],
    })
    assert.ok(advice)
    assert.match(advice, /Retire cet import/)
  })
})
