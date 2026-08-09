// Verrouille le respect strict du type de projet dans la planification.
//
// Defaut reel: intention `static_web`, plan rendu en Next.js (src/app/layout.tsx,
// next.config.js) sans index.html. Deux mecanismes s additionnaient:
//   1. le prompt se contentait d INFORMER ("Projet detecte: static_web") puis
//      demandait "les solutions les plus modernes" — donc invitait a changer de
//      stack;
//   2. le scoreur recompensait plus de fichiers / dependances / scripts, donc un
//      plan Next.js battait mecaniquement un plan statique correct.

import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildProjectTypeStackContract,
  checkPlanProjectTypeConformity,
  projectTypeConformityPenalty,
} from '../services/codeProjectTypeStackContract.ts'
import { selectBestArchitecturePlan } from '../services/codeArchitecturePlanSelection.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'

const intentOf = (projectType: string) => ({ projectType } as never)

function plan(projectType: string, paths: string[], extra: Record<string, unknown> = {}) {
  return {
    schemaVersion: 'aurora.code.architecture-plan.v1',
    projectType,
    summary: 'Resume suffisamment long pour satisfaire le schema de validation du plan.',
    stack: {
      runtime: 'node',
      packageManager: 'npm',
      languages: ['javascript'],
      frameworks: [],
      dependencies: [],
      scripts: [],
      ...(extra.stack as object ?? {}),
    },
    files: paths.map((p) => ({
      path: p, role: 'module', language: 'text', required: true, imports: [], exports: [], notes: [],
    })),
    dataFlow: ['a -> b'],
    execution: { install: [], dev: [], build: [], test: [], preview: 'index.html' },
    generationOrder: paths,
    validation: ['v1', 'v2'],
    risks: [{ risk: 'r', mitigation: 'm' }],
    design: { palette: [], typography: [], ux: [], responsive: [] },
  }
}

describe('checkPlanProjectTypeConformity', () => {
  test('signale un plan Next.js rendu pour un static_web (cas reel)', () => {
    const p = plan('static_web', ['src/app/layout.tsx', 'src/app/page.tsx', 'next.config.js'])
    const report = checkPlanProjectTypeConformity(p as never, intentOf('static_web'))
    assert.equal(report.conform, false)
    assert.ok(report.violations.length >= 2, `violations=${report.violations.join(',')}`)
    assert.deepEqual(report.missingEntryFiles, ['index.html'])
  })

  test('accepte un plan statique correct', () => {
    const p = plan('static_web', ['index.html', 'style.css', 'script.js'])
    const report = checkPlanProjectTypeConformity(p as never, intentOf('static_web'))
    assert.equal(report.conform, true, `violations=${report.violations.join(',')}`)
  })

  test('signale un plan qui se declare d un autre type', () => {
    const p = plan('ssr_nextjs', ['index.html', 'style.css'])
    const report = checkPlanProjectTypeConformity(p as never, intentOf('static_web'))
    assert.equal(report.conform, false)
    assert.ok(report.violations.some((v) => v.includes('plan.projectType')))
  })

  test('Next.js reste legitime pour une intention ssr_nextjs', () => {
    const p = plan('ssr_nextjs', ['package.json', 'src/app/layout.tsx', 'next.config.js'])
    const report = checkPlanProjectTypeConformity(p as never, intentOf('ssr_nextjs'))
    assert.equal(report.conform, true, `violations=${report.violations.join(',')}`)
  })

  test('un CLI python ne doit pas embarquer de package.json ni d index.html', () => {
    const p = plan('cli_python', ['main.py', 'package.json'])
    const report = checkPlanProjectTypeConformity(p as never, intentOf('cli_python'))
    assert.equal(report.conform, false)
  })
})

describe('selection de plan — le type de projet renverse le biais du scoreur', () => {
  test('un plan statique correct BAT un plan Next.js plus lourd sur un static_web', () => {
    // Sans penalite, le candidat Next.js gagne: plus de fichiers, plus de
    // dependances, plus de scripts. C est exactement ce qui se produisait.
    const heavyNext = JSON.stringify(plan(
      'static_web',
      ['src/app/layout.tsx', 'src/app/page.tsx', 'next.config.js', 'tailwind.config.ts', 'tsconfig.json', 'package.json'],
      { stack: { dependencies: [{ name: 'next', type: 'runtime' }, { name: 'react', type: 'runtime' }], scripts: [{ name: 'build', command: 'next build', purpose: 'build' }] } },
    ))
    const cleanStatic = JSON.stringify(plan('static_web', ['index.html', 'style.css', 'script.js']))

    const withoutIntent = selectBestArchitecturePlan([heavyNext, cleanStatic])
    assert.equal(withoutIntent.selected?.index, 0, 'sans intent, le plan lourd gagne (biais historique)')

    const withIntent = selectBestArchitecturePlan([heavyNext, cleanStatic], intentOf('static_web'))
    assert.equal(withIntent.selected?.index, 1, 'avec le type impose, le plan statique correct gagne')
  })

  test('la penalite est nulle sur un plan conforme', () => {
    const p = plan('static_web', ['index.html', 'style.css'])
    assert.equal(projectTypeConformityPenalty(p as never, intentOf('static_web')), 0)
  })

  test('la penalite croit avec le nombre de violations', () => {
    const one = plan('static_web', ['index.html', 'next.config.js'])
    const many = plan('static_web', ['next.config.js', 'src/app/layout.tsx', 'src/app/page.tsx'])
    assert.ok(
      projectTypeConformityPenalty(many as never, intentOf('static_web'))
      > projectTypeConformityPenalty(one as never, intentOf('static_web')),
    )
  })
})

describe('buildProjectTypeStackContract', () => {
  test('rend le type contraignant et cite la porte d entree', () => {
    const intent = classifyCodeIntent('landing page premium pour la marque Mercedes-Benz')
    const block = buildProjectTypeStackContract(intent)
    assert.match(block, /CONTRAINTE, PAS SUGGESTION/)
    assert.match(block, /static_web/)
    assert.match(block, /index\.html/)
  })

  test('interdit explicitement les frameworks etrangers sur un static_web', () => {
    const block = buildProjectTypeStackContract(intentOf('static_web'))
    assert.match(block, /AUCUN framework applicatif/i)
    assert.match(block, /next\.config\.js/)
  })

  test('n interdit rien d absurde sur un type qui attend le framework', () => {
    const block = buildProjectTypeStackContract(intentOf('ssr_nextjs'))
    assert.match(block, /Next\.js/)
    assert.doesNotMatch(block, /AUCUN framework applicatif/i)
  })
})
