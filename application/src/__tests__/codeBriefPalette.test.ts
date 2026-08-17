/**
 * Run 1161 — la design-spec exigeait un noir bleute d un brief terracotta.
 *
 * Extrait textuel du brief reel (output/code/audit_v118/payload.json):
 *
 *   « on n'est PAS un truc minimaliste blanc scandinave […] On veut plutôt des
 *     couleurs chaudes, terracotta, marron torréfié, un peu de vert olive
 *     peut-être, ça doit sentir l'artisanal et le chaleureux »
 *
 * Reponse de la porte, en `required: true`:
 *   background oklch(0.13 0.012 252) · accent #7c3aed
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  briefContradictsDarkBackground,
  resolveBriefPalette,
} from '../services/codeBriefPalette.ts'

const BRIEF = "Sur le style : on n'est PAS un truc minimaliste blanc scandinave comme tout le monde "
  + "fait pour le café en ce moment, j'en ai marre de voir ça partout. On veut plutôt des couleurs "
  + 'chaudes, terracotta, marron torréfié, un peu de vert olive peut-être, ça doit sentir '
  + "l'artisanal et le chaleureux, presque un peu \"carnet de voyage\" mais propre quand même."

describe('la palette nommee dans le brief fait autorite', () => {
  test('brief reel: les deux couleurs de tete sont celles de la marque', () => {
    const palette = resolveBriefPalette(BRIEF)
    assert.deepEqual(
      palette.colors.slice(0, 2).map((c) => c.token),
      ['marron torrefie', 'vert olive'],
    )
    assert.match(palette.colors[0].hex, /^#[0-9a-f]{6}$/)
  })

  test('brief reel: un fond quasi noir est CONTREDIT, il ne peut pas etre exige', () => {
    const palette = resolveBriefPalette(BRIEF)
    assert.equal(palette.wantsLight, true)
    assert.equal(palette.wantsDark, false)
    assert.equal(briefContradictsDarkBackground(palette), true)
  })

  test('brief reel: « blanc » est refuse, il ne devient pas une demande', () => {
    const palette = resolveBriefPalette(BRIEF)
    assert.equal(palette.colors.some((c) => c.token === 'blanc'), false)
    assert.equal(palette.colors.some((c) => c.token === 'minimaliste'), false)
  })

  test('un brief qui demande du sombre garde le fond sombre', () => {
    const palette = resolveBriefPalette('Un dashboard en dark mode, fond sombre, accents bleus.')
    assert.equal(palette.wantsDark, true)
    assert.equal(palette.wantsLight, false)
    assert.equal(briefContradictsDarkBackground(palette), false)
  })

  test('un hex ecrit noir sur blanc passe devant le vocabulaire', () => {
    const palette = resolveBriefPalette('La charte impose #A0522D et #2F4F4F.')
    assert.equal(palette.colors[0].hex, '#a0522d')
    assert.equal(palette.colors[1].hex, '#2f4f4f')
  })

  test('un hex court est etendu', () => {
    assert.equal(resolveBriefPalette('accent #f80').colors[0].hex, '#ff8800')
  })

  test('un brief muet sur la couleur ne contredit rien', () => {
    const palette = resolveBriefPalette('Fais-moi une app de gestion de taches.')
    assert.deepEqual(palette.colors, [])
    assert.equal(palette.wantsLight, false)
    assert.equal(briefContradictsDarkBackground(palette), false)
  })

  test('la porte peut se justifier: chaque decision porte sa preuve', () => {
    const palette = resolveBriefPalette(BRIEF)
    assert.ok(palette.evidence.some((e) => /terracotta/.test(e)), palette.evidence.join(' | '))
    assert.ok(palette.evidence.some((e) => /ambiance claire/.test(e)), palette.evidence.join(' | '))
  })
})
