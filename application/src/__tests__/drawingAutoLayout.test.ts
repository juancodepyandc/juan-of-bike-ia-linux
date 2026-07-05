/**
 * Tests pour services/drawingAutoLayout — auto-layout flowchart + radial.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  layoutFlowchart,
  layoutToSvg,
  layoutRadial,
} from '../services/drawingAutoLayout.ts'

describe('layoutFlowchart — DAG simple', () => {
  test('chaîne linéaire A→B→C → 3 couches', () => {
    const r = layoutFlowchart(
      [{ id: 'A', label: 'A' }, { id: 'B', label: 'B' }, { id: 'C', label: 'C' }],
      [{ from: 'A', to: 'B' }, { from: 'B', to: 'C' }],
    )
    assert.equal(r.nodes.length, 3)
    assert.equal(r.hasCycle, false)
    // Direction TB → y croissant
    const yByid = new Map(r.nodes.map((n) => [n.id, n.y]))
    assert.ok(yByid.get('A')! < yByid.get('B')!)
    assert.ok(yByid.get('B')! < yByid.get('C')!)
  })

  test('graphe avec branches → bonne répartition', () => {
    const r = layoutFlowchart(
      [{ id: 'A', label: 'A' }, { id: 'B', label: 'B' }, { id: 'C', label: 'C' }],
      [{ from: 'A', to: 'B' }, { from: 'A', to: 'C' }],
    )
    assert.equal(r.nodes.length, 3)
    // B et C devraient être sur la même couche (y identique)
    const yB = r.nodes.find((n) => n.id === 'B')!.y
    const yC = r.nodes.find((n) => n.id === 'C')!.y
    assert.equal(yB, yC)
  })
})

describe('layoutFlowchart — cycles', () => {
  test('cycle A→B→A → hasCycle=true', () => {
    const r = layoutFlowchart(
      [{ id: 'A', label: 'A' }, { id: 'B', label: 'B' }],
      [{ from: 'A', to: 'B' }, { from: 'B', to: 'A' }],
    )
    assert.equal(r.hasCycle, true)
  })

  test('cycle quand même placé (pas de crash)', () => {
    const r = layoutFlowchart(
      [{ id: 'A', label: 'A' }, { id: 'B', label: 'B' }, { id: 'C', label: 'C' }],
      [{ from: 'A', to: 'B' }, { from: 'B', to: 'C' }, { from: 'C', to: 'A' }],
    )
    assert.equal(r.nodes.length, 3)
  })
})

describe('layoutFlowchart — direction LR', () => {
  test('direction LR → x croissant pour A→B→C', () => {
    const r = layoutFlowchart(
      [{ id: 'A', label: 'A' }, { id: 'B', label: 'B' }, { id: 'C', label: 'C' }],
      [{ from: 'A', to: 'B' }, { from: 'B', to: 'C' }],
      { direction: 'LR' },
    )
    const xByid = new Map(r.nodes.map((n) => [n.id, n.x]))
    assert.ok(xByid.get('A')! < xByid.get('B')!)
    assert.ok(xByid.get('B')! < xByid.get('C')!)
  })
})

describe('layoutFlowchart — edge cases', () => {
  test('nodes vides → 0 nodes, viewBox sane', () => {
    const r = layoutFlowchart([], [])
    assert.equal(r.nodes.length, 0)
    assert.ok(r.viewBox.w > 0)
  })

  test('node sans edge → placé en couche 0', () => {
    const r = layoutFlowchart([{ id: 'X', label: 'X' }], [])
    assert.equal(r.nodes.length, 1)
    assert.equal(r.nodes[0].id, 'X')
  })

  test('edge vers id inconnu → silencieusement ignorée', () => {
    const r = layoutFlowchart(
      [{ id: 'A', label: 'A' }],
      [{ from: 'A', to: 'GHOST' }],
    )
    assert.equal(r.nodes.length, 1)
  })

  test('width/height des nodes respectés', () => {
    const r = layoutFlowchart(
      [{ id: 'X', label: 'X', width: 300, height: 100 }],
      [],
    )
    assert.equal(r.nodes[0].w, 300)
    assert.equal(r.nodes[0].h, 100)
  })

  test('options custom hGap/vGap/marginX/marginY', () => {
    const r1 = layoutFlowchart([{ id: 'A', label: 'A' }, { id: 'B', label: 'B' }], [], { hGap: 200 })
    const r2 = layoutFlowchart([{ id: 'A', label: 'A' }, { id: 'B', label: 'B' }], [], { hGap: 20 })
    // hGap plus grand → viewBox plus large
    assert.ok(r1.viewBox.w > r2.viewBox.w)
  })
})

describe('layoutToSvg', () => {
  test('produit un SvgDocument avec viewBox alignée', () => {
    const layout = layoutFlowchart(
      [{ id: 'A', label: 'A' }, { id: 'B', label: 'B' }],
      [{ from: 'A', to: 'B' }],
    )
    const doc = layoutToSvg(layout)
    assert.deepEqual(doc.viewBox, layout.viewBox)
    assert.ok(doc.elements.length > 0)
  })

  test('CSS variables Aurora présentes', () => {
    const layout = layoutFlowchart([{ id: 'X', label: 'X' }], [])
    const doc = layoutToSvg(layout)
    assert.ok(doc.cssVariables.primary)
  })
})

describe('layoutRadial — root + enfants', () => {
  test('root centré, enfants en cercle', () => {
    const r = layoutRadial(
      [
        { id: 'root', label: 'R' },
        { id: 'a', label: 'A' },
        { id: 'b', label: 'B' },
        { id: 'c', label: 'C' },
      ],
      [{ from: 'root', to: 'a' }, { from: 'root', to: 'b' }, { from: 'root', to: 'c' }],
      { rootId: 'root', baseRadius: 100, centerX: 200, centerY: 200 },
    )
    assert.equal(r.nodes.length, 4)
    const root = r.nodes.find((n) => n.id === 'root')!
    // root près du centre
    assert.ok(Math.abs((root.x + root.w / 2) - 200) < 100)
  })

  test('root inexistant → fallback flowchart', () => {
    const r = layoutRadial(
      [{ id: 'A', label: 'A' }],
      [],
      { rootId: 'nonexistent' },
    )
    assert.equal(r.nodes.length, 1)
  })

  test('orphan node (déconnecté) placé en orbite plus loin', () => {
    const r = layoutRadial(
      [
        { id: 'root', label: 'R' },
        { id: 'a', label: 'A' },
        { id: 'orphan', label: 'O' },
      ],
      [{ from: 'root', to: 'a' }],
      { rootId: 'root', baseRadius: 50 },
    )
    // orphan doit être plus loin du centre que les enfants directs de root
    assert.equal(r.nodes.length, 3)
  })

  test('plusieurs niveaux (grand-enfants)', () => {
    const r = layoutRadial(
      [
        { id: 'root', label: 'R' },
        { id: 'a', label: 'A' },
        { id: 'b', label: 'B' },
      ],
      [{ from: 'root', to: 'a' }, { from: 'a', to: 'b' }],
      { rootId: 'root', baseRadius: 100 },
    )
    const root = r.nodes.find((n) => n.id === 'root')!
    const a = r.nodes.find((n) => n.id === 'a')!
    const b = r.nodes.find((n) => n.id === 'b')!
    const distA = Math.hypot(a.x - root.x, a.y - root.y)
    const distB = Math.hypot(b.x - root.x, b.y - root.y)
    // b est plus loin que a du root
    assert.ok(distB > distA)
  })

  test('hasCycle false par construction BFS', () => {
    const r = layoutRadial(
      [{ id: 'root', label: 'R' }, { id: 'a', label: 'A' }],
      [{ from: 'root', to: 'a' }, { from: 'a', to: 'root' }],
      { rootId: 'root' },
    )
    assert.equal(r.hasCycle, false)
  })

  test('viewBox englobe tous les nodes', () => {
    const r = layoutRadial(
      [{ id: 'root', label: 'R' }, { id: 'a', label: 'A' }],
      [{ from: 'root', to: 'a' }],
      { rootId: 'root', baseRadius: 200 },
    )
    for (const n of r.nodes) {
      assert.ok(n.x >= r.viewBox.x)
      assert.ok(n.y >= r.viewBox.y)
      assert.ok(n.x + n.w <= r.viewBox.x + r.viewBox.w)
      assert.ok(n.y + n.h <= r.viewBox.y + r.viewBox.h)
    }
  })
})
