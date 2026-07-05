/**
 * Tests pour utils/simpleDiff — LCS-based line diff léger.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { diffLines, diffStats } from '../utils/simpleDiff.ts'

describe('diffLines', () => {
  test('strings identiques → tout en eq', () => {
    const out = diffLines('a\nb\nc', 'a\nb\nc')
    assert.equal(out.length, 3)
    for (const l of out) assert.equal(l.op, 'eq')
  })

  test('ligne ajoutée en fin', () => {
    const out = diffLines('a\nb', 'a\nb\nc')
    const adds = out.filter(l => l.op === 'add')
    assert.equal(adds.length, 1)
    assert.equal(adds[0].text, 'c')
    assert.equal(adds[0].oldLine, null)
    assert.equal(adds[0].newLine, 3)
  })

  test('ligne supprimée au milieu', () => {
    const out = diffLines('a\nb\nc', 'a\nc')
    const dels = out.filter(l => l.op === 'del')
    assert.equal(dels.length, 1)
    assert.equal(dels[0].text, 'b')
    assert.equal(dels[0].oldLine, 2)
    assert.equal(dels[0].newLine, null)
  })

  test('ligne modifiée → del + add', () => {
    const out = diffLines('hello\nworld', 'hello\nworld!')
    const ops = out.map(l => l.op).join(',')
    assert.ok(ops.includes('del'))
    assert.ok(ops.includes('add'))
  })

  test('avant vide → tout en add', () => {
    const out = diffLines('', 'a\nb')
    // Note: '' splitted = [''], 'a\nb' splitted = ['a', 'b']
    const adds = out.filter(l => l.op === 'add')
    assert.ok(adds.length >= 2)
  })

  test('après vide → tout en del', () => {
    const out = diffLines('a\nb', '')
    const dels = out.filter(l => l.op === 'del')
    assert.ok(dels.length >= 2)
  })

  test('numéros de ligne 1-based', () => {
    const out = diffLines('a\nb', 'a\nb')
    assert.equal(out[0].oldLine, 1)
    assert.equal(out[0].newLine, 1)
    assert.equal(out[1].oldLine, 2)
    assert.equal(out[1].newLine, 2)
  })
})

describe('diffStats', () => {
  test('compte par op', () => {
    const lines = diffLines('a\nb\nc', 'a\nx\nc')
    const stats = diffStats(lines)
    assert.equal(stats.added, 1)
    assert.equal(stats.removed, 1)
    assert.equal(stats.unchanged, 2)
  })

  test('aucun changement → 0/0/all', () => {
    const lines = diffLines('a\nb', 'a\nb')
    const stats = diffStats(lines)
    assert.equal(stats.added, 0)
    assert.equal(stats.removed, 0)
    assert.equal(stats.unchanged, 2)
  })

  test('tout différent', () => {
    const lines = diffLines('a\nb\nc', 'x\ny\nz')
    const stats = diffStats(lines)
    assert.equal(stats.added, 3)
    assert.equal(stats.removed, 3)
    assert.equal(stats.unchanged, 0)
  })

  test('alignement LCS — préserve les communes', () => {
    // "a b c d" vs "a x c y" → a/c en commun, b/d delete, x/y add
    const lines = diffLines('a\nb\nc\nd', 'a\nx\nc\ny')
    const stats = diffStats(lines)
    assert.equal(stats.unchanged, 2) // a + c
    assert.equal(stats.added, 2)
    assert.equal(stats.removed, 2)
  })
})
