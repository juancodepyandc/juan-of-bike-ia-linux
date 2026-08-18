import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import {
  alignLanguageLabels,
  applyExtensionFixes,
  containsJsx,
  planExtensionFixes,
} from '../services/codeFileExtensionCoherence.ts'
import {
  applyTailwindToolchainFix,
  planTailwindToolchainFix,
} from '../services/codeTailwindToolchainContract.ts'
import {
  countTailwindUtilities,
  detectTailwindSetup,
  hasTailwindDirectives,
} from '../services/codeTailwindUsage.ts'

// La ligne EXACTE emise par le run v126, celle qui a coute sept passes de
// modele puis « boucle infinie detectee apres 7 passes ».
const VITEST_SETUP_V126 = `import { vi } from 'vitest'
import React from 'react'

vi.mock('framer-motion', () => {
  return {
    motion: { div: 'div', h1: 'h1', p: 'p', img: 'img' },
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  }
})
`

describe('extension vs contenu: la correction est deterministe, pas probabiliste', () => {
  test('le JSX est detecte, et les formes TypeScript voisines ne le sont pas', () => {
    assert.ok(containsJsx(VITEST_SETUP_V126), 'fragment <>...</> = JSX')
    assert.ok(containsJsx('const a = <Foo bar="x" />'), 'element auto-fermant = JSX')
    assert.ok(containsJsx('return <div className="x">hi</div>'), 'balise fermante = JSX')

    // Aucune de ces formes n exige une grammaire JSX. Un faux positif ici
    // renommerait des fichiers sains.
    assert.equal(containsJsx('const id = <T,>(x: T): T => x'), false, 'generique flechee')
    assert.equal(containsJsx('const n = <number>value'), false, 'assertion de type')
    assert.equal(containsJsx('if (a < b && c > d) return 1'), false, 'comparaisons')
    assert.equal(containsJsx('const s = "</div>"'), false, 'JSX dans une chaine')
    assert.equal(containsJsx('// <Foo />\n const x = 1'), false, 'JSX en commentaire')
    assert.equal(containsJsx('const t = `</span>`'), false, 'JSX dans un gabarit')
    assert.equal(containsJsx('type A = Array<Map<string, number>>'), false, 'generiques imbriques')
  })

  test('un .ts porteur de JSX est renomme en .tsx (mesure du run v126)', () => {
    const files = [{ name: 'src/vitest.setup.ts', language: 'typescript', content: VITEST_SETUP_V126 }]
    const fixes = planExtensionFixes(files)
    assert.equal(fixes.length, 1)
    assert.equal(fixes[0].from, 'src/vitest.setup.ts')
    assert.equal(fixes[0].to, 'src/vitest.setup.tsx')
    // Le motif nomme les codes que le compilateur a REELLEMENT emis 24 fois.
    assert.match(fixes[0].reason, /TS1110\/TS1161/)

    const next = applyExtensionFixes(files, fixes)
    assert.equal(next[0].name, 'src/vitest.setup.tsx')
    assert.equal(next[0].language, 'tsx', 'le libelle de langage suit l extension')
  })

  test('un .js porteur de JSX est renomme en .jsx', () => {
    const fixes = planExtensionFixes([{ name: 'src/App.js', language: 'javascript', content: 'export default () => <div />' }])
    assert.deepEqual(fixes.map((f) => f.to), ['src/App.jsx'])
  })

  test('les references qui portent l extension sont recollees', () => {
    const files = [
      { name: 'src/vitest.setup.ts', language: 'typescript', content: VITEST_SETUP_V126 },
      { name: 'vite.config.ts', language: 'typescript', content: "export default { test: { setupFiles: ['./src/vitest.setup.ts'] } }" },
      { name: 'tsconfig.json', language: 'json', content: '{"include":["src/vitest.setup.ts","src/**/*"]}' },
    ]
    const next = applyExtensionFixes(files, planExtensionFixes(files))
    assert.match(next[1].content, /\.\/src\/vitest\.setup\.tsx/)
    assert.doesNotMatch(next[1].content, /vitest\.setup\.ts['"]/)
    assert.match(next[2].content, /src\/vitest\.setup\.tsx/)
  })

  test('un .tsx SANS JSX n est pas touche: rien n est casse, on ne redecide pas', () => {
    assert.deepEqual(planExtensionFixes([{ name: 'src/types.tsx', language: 'tsx', content: 'export type A = string' }]), [])
  })

  test('un renommage qui ecraserait un fichier existant est refuse', () => {
    const files = [
      { name: 'src/App.ts', language: 'typescript', content: 'export default () => <div />' },
      { name: 'src/App.tsx', language: 'tsx', content: 'export const Other = () => <span />' },
    ]
    assert.deepEqual(planExtensionFixes(files), [], 'mieux vaut ne rien faire que perdre du contenu')
  })

  test('autre sens de la famille: le libelle suit l extension', () => {
    // Defaut deja ferme dans l autre sens: un `.tsx` etiquete `typescript`
    // recevait une grammaire qui refuse le JSX.
    const { files, changed } = alignLanguageLabels([{ name: 'src/App.tsx', language: 'typescript', content: 'x' }])
    assert.equal(files[0].language, 'tsx')
    assert.deepEqual(changed, ['src/App.tsx: typescript -> tsx'])
  })
})

describe('la file emet des classes Tailwind, elle emet leur outillage', () => {
  const page = {
    name: 'src/App.tsx',
    language: 'tsx',
    content: '<div className="container flex items-center gap-4 px-6 py-4 rounded-lg bg-amber-600 shadow-md text-2xl">x</div>',
  }
  const manifest = { name: 'package.json', language: 'json', content: '{"name":"x","dependencies":{"react":"^18.2.0"}}' }
  const sheet = { name: 'src/styles/global.css', language: 'css', content: 'body { margin: 0; }' }

  test('mesure du run v126: classes utilisees, outillage absent', () => {
    const files = [page, manifest, sheet]
    assert.ok(countTailwindUtilities(files).count >= 8)
    assert.equal(detectTailwindSetup(files), 'absent')
    assert.equal(hasTailwindDirectives(files), false)
  })

  test('les quatre pieces manquantes sont livrees, pas reprochees douze fois', () => {
    const files = [page, manifest, sheet]
    const fix = planTailwindToolchainFix(files)
    assert.ok(fix, 'un plan doit exister')
    const next = applyTailwindToolchainFix(files, fix!)

    assert.ok(next.some((f) => f.name === 'tailwind.config.js'))
    assert.ok(next.some((f) => f.name === 'postcss.config.js'))
    assert.equal(hasTailwindDirectives(next), true)
    assert.equal(detectTailwindSetup(next), 'configured')

    const pkg = JSON.parse(next.find((f) => f.name === 'package.json')!.content) as { devDependencies: Record<string, string> }
    assert.ok(pkg.devDependencies.tailwindcss)
    assert.ok(pkg.devDependencies.postcss)
    assert.ok(pkg.devDependencies.autoprefixer)
    // Le plan est idempotent: rejoue, il n a plus rien a faire.
    assert.equal(planTailwindToolchainFix(next), null)
  })

  test('les directives sont ajoutees EN TETE de la feuille existante, sans la perdre', () => {
    const files = [page, manifest, sheet]
    const next = applyTailwindToolchainFix(files, planTailwindToolchainFix(files)!)
    const css = next.find((f) => f.name === 'src/styles/global.css')!
    assert.match(css.content, /^@tailwind base;/)
    assert.match(css.content, /body \{ margin: 0; \}/)
  })

  test('rien a faire si Tailwind vient d un CDN, ou est deja declare', () => {
    const cdn = { name: 'index.html', language: 'html', content: '<script src="https://cdn.tailwindcss.com"></script>' }
    assert.equal(planTailwindToolchainFix([page, manifest, sheet, cdn]), null)

    const declared = { name: 'package.json', language: 'json', content: '{"name":"x","devDependencies":{"tailwindcss":"^3.4.0"}}' }
    assert.equal(planTailwindToolchainFix([page, declared, sheet]), null)
  })

  test('un manifeste ILLISIBLE ne declenche pas de reparation a l aveugle', () => {
    const broken = { name: 'package.json', language: 'json', content: '{"name":"x",}' }
    assert.equal(detectTailwindSetup([page, broken, sheet]), 'unreadable')
    assert.equal(planTailwindToolchainFix([page, broken, sheet]), null, 'le JSON invalide est LE defaut, signale ailleurs')
  })

  test('sous le seuil, on ne fabrique pas un projet Tailwind qui n existe pas', () => {
    const light = { name: 'src/App.tsx', language: 'tsx', content: '<div className="flex">x</div>' }
    assert.equal(planTailwindToolchainFix([light, manifest, sheet]), null)
  })
})
