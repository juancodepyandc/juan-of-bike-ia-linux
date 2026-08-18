import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import {
  applyImportShapeFixes,
  planImportShapeFixes,
  readImports,
  readModuleExports,
  resolveLocalImport,
} from '../services/codeImportExportShape.ts'

// BALAYAGE DE CORPUS (42 runs, 1187 erreurs TypeScript localisees):
//   100x TS2307 (dont 88 chemins LOCAUX) + 92x TS2613/TS2614
// Une seule famille: l import ne correspond pas a ce que la cible exporte.
// Cas reels repris ci-dessous, tires des livrables archives.

const f = (name: string, content: string) => ({ name, language: name.endsWith('x') ? 'tsx' : 'typescript', content })

describe('lecture du graphe: exports et imports se LISENT, ne se devinent pas', () => {
  test('les formes d export sont reconnues', () => {
    assert.deepEqual(readModuleExports('export default Home').hasDefault, true)
    const named = readModuleExports('export const Home = () => null\nexport function About() {}')
    assert.equal(named.hasDefault, false)
    assert.deepEqual([...named.named].sort(), ['About', 'Home'])
    const list = readModuleExports('const A = 1\nconst B = 2\nexport { A, B as C }')
    assert.deepEqual([...list.named].sort(), ['A', 'C'])
    assert.equal(readModuleExports('const X = 1\nexport { X as default }').hasDefault, true)
  })

  test('les formes d import sont reconnues', () => {
    const imports = readImports("import Home from './Home'\nimport { a, b as c } from './x'\nimport type { T } from './t'")
    assert.equal(imports[0].defaultBinding, 'Home')
    assert.deepEqual(imports[1].namedBindings, ['a', 'b'])
    assert.equal(imports[2].specifier, './t')
  })

  test('la resolution suit les fichiers REELLEMENT livres', () => {
    const files = [f('src/App.tsx', ''), f('src/components/Home.tsx', ''), f('src/data/index.ts', '')]
    assert.equal(resolveLocalImport(files, 'src/App.tsx', './components/Home'), 'src/components/Home.tsx')
    assert.equal(resolveLocalImport(files, 'src/App.tsx', './data'), 'src/data/index.ts')
    assert.equal(resolveLocalImport(files, 'src/App.tsx', './absent'), null)
    assert.equal(resolveLocalImport(files, 'src/App.tsx', 'react'), null, 'un paquet npm n est pas notre affaire')
  })
})

describe('reconciliation de forme: cas reels du corpus', () => {
  test('audit_v108 — import par defaut, la cible n exporte que des noms', () => {
    const files = [
      f('src/App.tsx', "import Home from './components/Home'\nexport default Home"),
      f('src/components/Home.tsx', 'export const Home = () => null'),
    ]
    const fixes = planImportShapeFixes(files)
    assert.equal(fixes.length, 1)
    assert.match(fixes[0].reason, /n a pas d export par defaut/)
    const next = applyImportShapeFixes(files, fixes)
    assert.match(next[0].content, /import \{ Home \} from '\.\/components\/Home'/)
  })

  test('audit_v101 — import nomme, la cible n expose qu un defaut', () => {
    const files = [
      f('src/pages/AdminPage.tsx', "import { useAdminStore } from '../store/adminStore'"),
      f('src/store/adminStore.ts', 'const useAdminStore = () => null\nexport default useAdminStore'),
    ]
    const fixes = planImportShapeFixes(files)
    assert.equal(fixes.length, 1)
    const next = applyImportShapeFixes(files, fixes)
    assert.match(next[0].content, /import useAdminStore from '\.\.\/store\/adminStore'/)
  })

  test('nom different: la cible n expose qu un seul nom, on aliase', () => {
    const files = [
      f('src/App.tsx', "import Links from './data/footerLinks'"),
      f('src/data/footerLinks.ts', 'export const FOOTER_LINKS = []'),
    ]
    const next = applyImportShapeFixes(files, planImportShapeFixes(files))
    assert.match(next[0].content, /import \{ FOOTER_LINKS as Links \}/)
  })

  test('AMBIGU: plusieurs noms, aucun ne correspond -> on ne devine pas', () => {
    const files = [
      f('src/App.tsx', "import Thing from './x'"),
      f('src/x.ts', 'export const A = 1\nexport const B = 2'),
    ]
    assert.deepEqual(planImportShapeFixes(files), [], 'deviner serait une invention, pas une reparation')
  })

  test('un import coherent n est jamais touche', () => {
    const files = [
      f('src/App.tsx', "import Home from './Home'\nimport { helper } from './util'"),
      f('src/Home.tsx', 'export default function Home() {}'),
      f('src/util.ts', 'export const helper = () => null'),
    ]
    assert.deepEqual(planImportShapeFixes(files), [])
  })

  test('une cible ABSENTE est laissee a la completion de modules, pas inventee', () => {
    const files = [f('src/App.tsx', "import Missing from './components/Missing'")]
    assert.deepEqual(planImportShapeFixes(files), [])
  })

  test('les paquets npm ne sont jamais reecrits', () => {
    const files = [f('src/App.tsx', "import React from 'react'\nimport { z } from 'zod'")]
    assert.deepEqual(planImportShapeFixes(files), [])
  })

  test('la reparation converge: rejouee, elle n a plus rien a faire', () => {
    const files = [
      f('src/App.tsx', "import Home from './components/Home'"),
      f('src/components/Home.tsx', 'export const Home = () => null'),
    ]
    const next = applyImportShapeFixes(files, planImportShapeFixes(files))
    assert.deepEqual(planImportShapeFixes(next), [])
  })
})
