import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import {
  applyArrayContainerFixes,
  planArrayContainerFixes,
  soleArrayProperty,
} from '../services/codeArrayContainerAccess.ts'

// MESURE (run v131, 8 occurrences sur 72 erreurs):
//   Property 'map' does not exist on type
//     '{ events: MarketEvent[]; loading: boolean; error: string; }'
// Un hook rend un objet d etat, l appelant fait `.map()` dessus au lieu de
// `.events.map()`. Le compilateur imprime le type ENTIER: la cible se LIT.

const f = (name: string, content: string) => ({ name, language: 'tsx', content })

describe('la cible se lit dans le type imprime par le compilateur', () => {
  test('un seul tableau -> cible unique', () => {
    assert.equal(soleArrayProperty(' events: MarketEvent[]; loading: boolean; error: string; '), 'events')
    assert.equal(soleArrayProperty(' items: Array<Order>; total: number; '), 'items')
  })

  test('zero ou plusieurs tableaux -> on ne choisit pas', () => {
    assert.equal(soleArrayProperty(' a: X[]; b: Y[]; '), null)
    assert.equal(soleArrayProperty(' loading: boolean; error: string; '), null)
  })
})

describe('destructuration oubliee: le cas reel du run v131', () => {
  const page = f('src/pages/MarketCalendarPage.tsx', [
    'export default function Page() {',
    '  const state = useMarkets()',
    '  return <div>{state.map((e) => e.name)}</div>',
    '}',
  ].join('\n'))
  const output = "src/pages/MarketCalendarPage.tsx(3,22): error TS2339: Property 'map' does not exist on type '{ events: MarketEvent[]; loading: boolean; error: string; }'."

  test('l acces est recolle sur le bon tableau', () => {
    const fixes = planArrayContainerFixes([page], output)
    assert.equal(fixes.length, 1)
    assert.equal(fixes[0].after, 'state.events.map')
    const next = applyArrayContainerFixes([page], fixes)
    assert.match(next[0].content, /state\.events\.map\(/)
  })

  test('un acces DEJA correct n est jamais double', () => {
    const ok = f('src/a.tsx', 'const x = state.events.map((e) => e)')
    const out = "src/a.tsx(1,17): error TS2339: Property 'map' does not exist on type '{ events: E[]; loading: boolean; }'."
    assert.deepEqual(planArrayContainerFixes([ok], out), [])
  })

  test('une propriete qui n est PAS une methode de tableau est ignoree', () => {
    const out = "src/a.tsx(1,1): error TS2339: Property 'title' does not exist on type '{ events: E[]; loading: boolean; }'."
    assert.deepEqual(planArrayContainerFixes([f('src/a.tsx', 'const x = state.title')], out), [])
  })

  test('un type AMBIGU (deux tableaux) n est pas repare', () => {
    const out = "src/a.tsx(1,1): error TS2339: Property 'map' does not exist on type '{ a: X[]; b: Y[]; }'."
    assert.deepEqual(planArrayContainerFixes([f('src/a.tsx', 'const x = state.map(f)')], out), [])
  })

  test('un fichier absent du livrable n est pas invente', () => {
    const out = "src/absent.tsx(1,1): error TS2339: Property 'map' does not exist on type '{ e: E[]; n: number; }'."
    assert.deepEqual(planArrayContainerFixes([f('src/a.tsx', 'x')], out), [])
  })

  test('la reparation converge: rejouee sur le resultat, plus rien a faire', () => {
    const fixes = planArrayContainerFixes([page], output)
    const next = applyArrayContainerFixes([page], fixes)
    assert.deepEqual(planArrayContainerFixes(next, output), [])
  })
})
