import assert from 'node:assert/strict'
import { test } from 'node:test'
import { explanationSvg, generateExplanationWithRepair, isExplanatoryDrawing, sketchBase64 } from '../services/drawingExplanation.ts'

const graph = () => ({ nodes: [{ id: 'a', label: 'Évaporation' }, { id: 'b', label: 'Condensation' }], edges: [{ from: 'a', to: 'b', label: 'refroidissement' }] })

test('routes explanations and flowcharts without forcing artistic requests into boxes', () => {
  for (const prompt of ['Explique le cycle de l’eau', 'Schéma explicatif du réseau', 'Organigramme de livraison']) {
    assert.equal(isExplanatoryDrawing(prompt), true, prompt)
  }
  for (const prompt of ['Aquarelle d’un chat', 'Croquis artistique au crayon', 'Histogramme des ventes']) {
    assert.equal(isExplanatoryDrawing(prompt), false, prompt)
  }
})

test('renders readable Unicode labels, dimensions and one arrowhead per relation', () => {
  const svg = explanationSvg('```json\n' + JSON.stringify(graph()) + '\n```')
  assert.match(svg, /<svg[^>]*width="\d+"[^>]*height="\d+"/)
  assert.match(svg, />Évaporation<\/text>/)
  assert.match(svg, />refroidissement<\/text>/)
  assert.equal((svg.match(/ Z"/g) ?? []).length, 1)
})

test('escapes model content instead of accepting executable SVG markup', () => {
  const fixture = graph()
  fixture.nodes[0].label = '<script>alert(1)</script>'
  const svg = explanationSvg(JSON.stringify(fixture))
  assert.doesNotMatch(svg, /<script/)
  assert.match(svg, /&lt;script&gt;/)
})

test('rejects duplicate IDs, missing endpoints and isolated nodes', () => {
  const fixtures = [
    { nodes: [{ id: 'a', label: 'A' }, { id: 'a', label: 'B' }], edges: [] },
    { ...graph(), edges: [{ from: 'a', to: 'missing' }] },
    { ...graph(), edges: [] },
    { ...graph(), nodes: [...graph().nodes, null] },
  ]
  for (const fixture of fixtures) assert.throws(() => explanationSvg(JSON.stringify(fixture)), /Schéma/)
})

test('rejects unsupported graph sizes and overflowing labels', () => {
  assert.throws(() => explanationSvg(JSON.stringify({ nodes: [], edges: [] })), /hors limites/)
  const fixture = graph()
  fixture.nodes[0].label = 'x'.repeat(33)
  assert.throws(() => explanationSvg(JSON.stringify(fixture)), /libellé/)
  assert.throws(() => explanationSvg('x'.repeat(20001)), /volumineuse/)
})

test('encodes a large sketch without overflowing the argument stack', async () => {
  const data = Uint8Array.from({ length: 400_000 }, (_, index) => index % 256)
  const encoded = await sketchBase64(new Blob([data]))
  assert.deepEqual(Buffer.from(encoded, 'base64'), Buffer.from(data))
})

test('routes a return arrow outside the boxes and keeps its label inside the canvas', () => {
  const fixture = graph()
  fixture.edges.push({ from: 'b', to: 'a', label: 'retour' })
  const svg = explanationSvg(JSON.stringify(fixture))
  assert.equal((svg.match(/ Z"/g) ?? []).length, 2)
  assert.match(svg, /L [0-9.]+ [0-9.]+ L [0-9.]+ [0-9.]+ L [0-9.]+ [0-9.]+/)
  const width = Number(svg.match(/<svg[^>]*width="([0-9.]+)"/)?.[1])
  const labelX = Number(svg.match(/<text x="([0-9.]+)"[^>]*>retour/)?.[1])
  assert.ok(width > labelX + 100)
})

test('honours monochrome drawings in the explanatory output', () => {
  const svg = explanationSvg(JSON.stringify(graph()), { monochrome: true })
  assert.match(svg, /fill="#ffffff"/)
  assert.match(svg, /fill="#111111"/)
  assert.doesNotMatch(svg, /fill="#10131d"/)
})

test('rejects control characters that would produce invalid XML', () => {
  const fixture = graph()
  fixture.nodes[0].label = 'invalid\u0000label'
  assert.throws(() => explanationSvg(JSON.stringify(fixture)), /libellé/)
})

test('a valid explanation is delivered without an unnecessary second inference', async () => {
  let calls = 0
  const svg = await generateExplanationWithRepair(async () => {
    calls += 1
    return JSON.stringify(graph())
  }, new AbortController().signal)
  assert.match(svg, /Évaporation/)
  assert.equal(calls, 1)
})

test('repairs an invalid graph automatically with the actual validation error', async () => {
  const corrections: Array<string | undefined> = []
  const svg = await generateExplanationWithRepair(async (correction) => {
    corrections.push(correction)
    return correction ? JSON.stringify(graph()) : JSON.stringify({ ...graph(), edges: [] })
  }, new AbortController().signal, { monochrome: true })
  assert.equal(corrections.length, 2)
  assert.match(corrections[1]!, /isolé/)
  assert.match(corrections[1]!, /Réponse précédente/)
  assert.match(svg, /fill="#ffffff"/)
})

test('stops after one failed automatic repair without delivering a defective SVG', async () => {
  let calls = 0
  await assert.rejects(generateExplanationWithRepair(async () => {
    calls += 1
    return '{}'
  }, new AbortController().signal), /non validé après une correction automatique/)
  assert.equal(calls, 2)
})

test('cancellation prevents a repair call or delivery after inference', async () => {
  const controller = new AbortController()
  let calls = 0
  await assert.rejects(generateExplanationWithRepair(async () => {
    calls += 1
    controller.abort()
    return '{}'
  }, controller.signal), { name: 'AbortError' })
  assert.equal(calls, 1)
})

test('does not mask a model connection failure as a graph repair', async () => {
  let calls = 0
  await assert.rejects(generateExplanationWithRepair(async () => {
    calls += 1
    throw new Error('Ollama unavailable')
  }, new AbortController().signal), /Ollama unavailable/)
  assert.equal(calls, 1)
})
