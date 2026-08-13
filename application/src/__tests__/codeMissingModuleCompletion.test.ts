import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildCompletionQueueItems,
  describeMissingModules,
  findUnresolvedLocalImports,
  prioritizeCompileErrors,
} from '../services/codeMissingModuleCompletion.ts'
import type { CodeFile } from '../services/codeOrchestratorTypes.ts'

/** Reduction du run 1121: deux composants importes, jamais generes. */
const PROJECT: CodeFile[] = [
  {
    name: 'src/components/Header.tsx',
    language: 'tsx',
    content: "import React from 'react'\nimport Logo from './Logo'\nimport { NavLinks } from './NavLinks'\nexport default function Header() { return <header><Logo /><NavLinks /></header> }",
  },
  {
    name: 'src/components/NavLinks.tsx',
    language: 'tsx',
    content: "export function NavLinks() { return <nav /> }",
  },
  {
    name: 'src/pages/AboutPage.tsx',
    language: 'tsx',
    content: "import StorySection from '../components/StorySection'\nimport { formatDate, slugify } from '../utils/format'\nexport default function AboutPage() { return <StorySection /> }",
  },
  { name: 'src/utils/format.ts', language: 'typescript', content: 'export const formatDate = () => ""\nexport const slugify = () => ""' },
  { name: 'package.json', language: 'json', content: '{"name":"x"}' },
]

describe('modules importes mais absents — un constat exact, pas une heuristique', () => {
  test('trouve exactement les deux imports non resolus du run 1121', () => {
    const missing = findUnresolvedLocalImports(PROJECT)
    assert.deepEqual(missing.map((m) => m.targetPath).sort(), [
      'src/components/Logo',
      'src/components/StorySection',
    ])
  })

  test('ne signale RIEN quand tout se resout, extensions et index compris', () => {
    const complete: CodeFile[] = [
      { name: 'src/App.tsx', language: 'tsx', content: "import A from './a'\nimport B from './b/index'\nimport C from './c.tsx'\nimport D from './d'" },
      { name: 'src/a.ts', language: 'typescript', content: 'export default 1' },
      { name: 'src/b/index.tsx', language: 'tsx', content: 'export default 1' },
      { name: 'src/c.tsx', language: 'tsx', content: 'export default 1' },
      { name: 'src/d/index.ts', language: 'typescript', content: 'export default 1' },
    ]
    assert.deepEqual(findUnresolvedLocalImports(complete), [])
  })

  test('les paquets npm et les modules node ne sont jamais pris pour des fichiers', () => {
    const files: CodeFile[] = [{
      name: 'src/App.tsx', language: 'tsx',
      content: "import React from 'react'\nimport fs from 'node:fs'\nimport { z } from 'zod'\nimport '@/styles/app.css'",
    }]
    assert.deepEqual(findUnresolvedLocalImports(files), [])
  })

  test('les liaisons attendues sont relevees pour ecrire les bons exports', () => {
    const missing = findUnresolvedLocalImports(PROJECT)
    const logo = missing.find((m) => m.targetPath === 'src/components/Logo')!
    assert.deepEqual(logo.bindings, ['default:Logo'])
    assert.equal(logo.importer, 'src/components/Header.tsx')
    assert.equal(logo.specifier, './Logo')
  })
})

describe('completion de la file — un composant importe est un composant voulu', () => {
  test('les elements portent chemin, extension, exports et role', () => {
    const items = buildCompletionQueueItems(findUnresolvedLocalImports(PROJECT), 38)
    assert.deepEqual(items.map((i) => i.path).sort(), [
      'src/components/Logo.tsx',
      'src/components/StorySection.tsx',
    ])
    const logo = items.find((i) => i.path === 'src/components/Logo.tsx')!
    assert.equal(logo.required, true)
    assert.equal(logo.language, 'tsx')
    assert.equal(logo.order, 38)
    assert.deepEqual(logo.exports, ['default Logo'])
    assert.match(logo.role, /importe par src\/components\/Header\.tsx/)
    assert.ok(logo.notes.some((n) => /export par defaut/.test(n)))
  })

  test('un module utilitaire minuscule ne devient pas un composant .tsx', () => {
    const files: CodeFile[] = [{
      name: 'src/App.tsx', language: 'tsx',
      content: "import { helper } from './utils/helper'\nexport default function App(){ return null }",
    }]
    const items = buildCompletionQueueItems(findUnresolvedLocalImports(files), 1)
    assert.equal(items[0].path, 'src/utils/helper.ts')
    assert.deepEqual(items[0].exports, ['helper'])
  })

  test('la completion est bornee', () => {
    const many: CodeFile[] = [{
      name: 'src/App.tsx', language: 'tsx',
      content: Array.from({ length: 30 }, (_, i) => `import C${i} from './c${i}'`).join('\n'),
    }]
    assert.equal(buildCompletionQueueItems(findUnresolvedLocalImports(many), 1).length, 12)
  })

  test('le constat est resume lisiblement', () => {
    assert.match(describeMissingModules(findUnresolvedLocalImports(PROJECT)), /2 module\(s\) importe\(s\) mais absent\(s\)/)
    assert.equal(describeMissingModules([]), '')
  })
})

describe('ordre causal des erreurs de compilation', () => {
  const OUTPUT = [
    "src/pages/AboutPage.tsx(2,26): error TS2307: Cannot find module '../components/StorySection' or its corresponding type declarations.",
    "src/pages/AboutPage.tsx(9,14): error TS2339: Property 'totalWeekly' does not exist on type 'OrdersState'.",
    "src/pages/AboutPage.tsx(11,3): error TS7006: Parameter 'link' implicitly has an 'any' type.",
    "src/stores/orders.ts(4,9): error TS2339: Property 'x' does not exist.",
  ].join('\n')

  test('les modules introuvables passent en tete, leurs consequences sont nommees', () => {
    const out = prioritizeCompileErrors(OUTPUT)
    assert.match(out, /CAUSE STRUCTURELLE — MODULES INTROUVABLES/)
    assert.ok(out.indexOf('TS2307') < out.indexOf('probablement des consequences'))
    assert.match(out, /2 autre\(s\) erreur\(s\) DANS CES MEMES FICHIERS/)
    // Une erreur dans un AUTRE fichier n est pas classee en consequence.
    const head = out.slice(0, out.indexOf('## SORTIE COMPLETE'))
    assert.equal(head.includes('src/stores/orders.ts'), false)
    // La sortie d origine reste integralement disponible.
    assert.ok(out.includes(OUTPUT))
  })

  test('sans module introuvable, la sortie est rendue telle quelle', () => {
    const plain = "src/a.ts(1,1): error TS2339: Property 'x' does not exist."
    assert.equal(prioritizeCompileErrors(plain), plain)
    assert.equal(prioritizeCompileErrors(''), '')
  })
})
