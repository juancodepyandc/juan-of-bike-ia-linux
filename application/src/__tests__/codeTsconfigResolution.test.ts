import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import { sanitizeGeneratedFileContent } from '../services/codeGeneratedFileSanitizer.ts'

// MESURE (run v130): 84 erreurs — 30 % du run — sur deux lignes de vite.config.ts.
//   vite.config.ts(1,30): TS2307 Cannot find module 'vite'
//   vite.config.ts(2,19): TS2307 Cannot find module '@vitejs/plugin-react'
// Verifie au registre npm: vite@8.2.1 et @vitejs/plugin-react@6.0.5 EXISTENT,
// et package.json les declarait. Le defaut etait `"moduleResolution": "node"`,
// qui ignore le champ `exports` — seul endroit ou ces paquets exposent leurs types.

const parse = (out: string) => JSON.parse(out) as { compilerOptions: Record<string, unknown> }

describe('tsconfig: la resolution Node10 casse les paquets a exports map', () => {
  test('le tsconfig REEL du run v130 est corrige', () => {
    const emitted = JSON.stringify({
      compilerOptions: { target: 'ES2020', module: 'ESNext', moduleResolution: 'node', noEmit: true, strict: false },
    })
    const options = parse(sanitizeGeneratedFileContent('tsconfig.json', emitted)).compilerOptions
    assert.equal(options.moduleResolution, 'bundler')
    assert.equal(options.module, 'ESNext')
  })

  test('un module CommonJS est aligne, sinon TypeScript refuse la combinaison', () => {
    const emitted = JSON.stringify({ compilerOptions: { module: 'CommonJS', moduleResolution: 'node' } })
    const options = parse(sanitizeGeneratedFileContent('tsconfig.json', emitted)).compilerOptions
    assert.equal(options.moduleResolution, 'bundler')
    assert.equal(options.module, 'ESNext')
  })

  test('une resolution ABSENTE est renseignee (le defaut implicite est Node10)', () => {
    const options = parse(sanitizeGeneratedFileContent('tsconfig.json', JSON.stringify({ compilerOptions: { target: 'ES2020' } }))).compilerOptions
    assert.equal(options.moduleResolution, 'bundler')
  })

  test('une resolution DEJA valide n est jamais ecrasee', () => {
    for (const value of ['bundler', 'nodenext', 'node16']) {
      const options = parse(sanitizeGeneratedFileContent('tsconfig.json', JSON.stringify({ compilerOptions: { moduleResolution: value, module: 'NodeNext' } }))).compilerOptions
      assert.equal(options.moduleResolution, value, value)
      assert.equal(options.module, 'NodeNext', 'le module reste celui choisi')
    }
  })

  test('les autres reglages du modele sont conserves', () => {
    const emitted = JSON.stringify({ compilerOptions: { moduleResolution: 'node', jsx: 'react-jsx', strict: true, target: 'ES2022' }, include: ['src'] })
    const out = parse(sanitizeGeneratedFileContent('tsconfig.json', emitted))
    assert.equal(out.compilerOptions.jsx, 'react-jsx')
    assert.equal(out.compilerOptions.strict, true)
    assert.equal(out.compilerOptions.target, 'ES2022')
    assert.deepEqual((out as unknown as { include: string[] }).include, ['src'])
  })
})
