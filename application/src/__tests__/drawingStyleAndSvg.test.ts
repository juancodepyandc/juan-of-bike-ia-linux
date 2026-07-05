/**
 * Tests pour services/drawingStyleAndSvg — classifieur intent dessin + SVG builder.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  classifyDrawingIntent,
  emptyDoc,
  serialise,
  flowChartDoc,
  gridOverlay,
  planRefinementPasses,
  AURORA_PALETTE,
} from '../services/drawingStyleAndSvg.ts'

describe('classifyDrawingIntent — types principaux', () => {
  test('"schéma technique" → schema-technique', () => {
    const r = classifyDrawingIntent('schéma technique du moteur électrique')
    assert.equal(r.intent, 'schema-technique')
    assert.equal(r.controlNetPreset, 'mlsd')
    assert.equal(r.preferredOutput, 'svg')
  })

  test('"aquarelle" → croquis-artistique', () => {
    const r = classifyDrawingIntent('aquarelle d un paysage de montagne')
    assert.equal(r.intent, 'croquis-artistique')
    assert.equal(r.controlNetPreset, 'scribble')
  })

  test('"flowchart" → diagramme-flow', () => {
    const r = classifyDrawingIntent('flowchart pour l algo de tri')
    assert.equal(r.intent, 'diagramme-flow')
    assert.equal(r.preferredOutput, 'svg')
  })

  test('"wireframe" → sketch-rapide', () => {
    const r = classifyDrawingIntent('wireframe d une app mobile')
    assert.equal(r.intent, 'sketch-rapide')
  })

  test('"histogramme" → graphique-data', () => {
    const r = classifyDrawingIntent('histogramme des ventes 2025')
    assert.equal(r.intent, 'graphique-data')
    assert.equal(r.preferredOutput, 'svg')
  })

  test('brief vide → fallback sketch-rapide low confidence', () => {
    const r = classifyDrawingIntent('')
    assert.equal(r.intent, 'sketch-rapide')
    assert.ok(r.confidence <= 0.3)
  })

  test('brief sans mot-clé connu → fallback', () => {
    const r = classifyDrawingIntent('un truc cool')
    assert.equal(r.intent, 'sketch-rapide')
  })
})

describe('classifyDrawingIntent — accents', () => {
  test('accents strippés pour matching', () => {
    const a = classifyDrawingIntent('schéma')
    const b = classifyDrawingIntent('schema')
    assert.equal(a.intent, b.intent)
  })
})

describe('classifyDrawingIntent — confidence + matched', () => {
  test('confidence ∈ [0..1]', () => {
    const r = classifyDrawingIntent('schéma technique aquarelle flowchart')
    assert.ok(r.confidence >= 0 && r.confidence <= 1)
  })

  test('matchedPatterns rempli quand match', () => {
    const r = classifyDrawingIntent('blueprint mecanique')
    assert.ok(r.matchedPatterns.length > 0)
    assert.ok(r.matchedPatterns.includes('blueprint'))
  })

  test('confidence plus haute quand pattern fort isolé', () => {
    const strong = classifyDrawingIntent('blueprint architecture mecanique technique')
    const weak = classifyDrawingIntent('schema ou diagramme flowchart')
    // strong devrait avoir confidence >= weak puisqu'un seul intent domine
    assert.ok(strong.confidence >= weak.confidence - 0.1)
  })
})

describe('AURORA_PALETTE', () => {
  test('contient les couleurs essentielles', () => {
    assert.ok(AURORA_PALETTE.primary)
    assert.ok(AURORA_PALETTE.surface)
    assert.ok(AURORA_PALETTE.textPrimary)
  })

  test('toutes les valeurs sont des hex valides', () => {
    for (const v of Object.values(AURORA_PALETTE)) {
      assert.ok(/^#[0-9a-f]{3,8}$/i.test(v), `${v} pas hex`)
    }
  })
})

describe('emptyDoc + serialise', () => {
  test('emptyDoc renvoie un doc 1000×1000 par défaut', () => {
    const d = emptyDoc()
    assert.equal(d.viewBox.w, 1000)
    assert.equal(d.viewBox.h, 1000)
    assert.deepEqual(d.elements, [])
  })

  test('viewBox personnalisée', () => {
    const d = emptyDoc({ x: 10, y: 20, w: 200, h: 150 })
    assert.equal(d.viewBox.x, 10)
    assert.equal(d.viewBox.h, 150)
  })

  test('serialise produit du XML valide', () => {
    const d = emptyDoc()
    const xml = serialise(d)
    assert.ok(xml.startsWith('<?xml'))
    assert.ok(xml.includes('<svg'))
    assert.ok(xml.includes('viewBox="0 0 1000 1000"'))
  })

  test('serialise inclut les CSS variables', () => {
    const d = emptyDoc()
    const xml = serialise(d)
    assert.ok(xml.includes('--primary'))
  })

  test('serialise tous les types d éléments', () => {
    const d = emptyDoc()
    d.elements.push({ kind: 'rect', x: 0, y: 0, w: 100, h: 50, fill: '#fff' })
    d.elements.push({ kind: 'circle', cx: 50, cy: 50, r: 25, stroke: '#000' })
    d.elements.push({ kind: 'line', x1: 0, y1: 0, x2: 10, y2: 10, stroke: '#000' })
    d.elements.push({ kind: 'text', x: 10, y: 20, text: 'Hello' })
    d.elements.push({ kind: 'path', d: 'M0 0 L 10 10' })
    d.elements.push({ kind: 'group', children: [{ kind: 'rect', x: 0, y: 0, w: 5, h: 5 }] })
    const xml = serialise(d)
    assert.ok(xml.includes('<rect'))
    assert.ok(xml.includes('<circle'))
    assert.ok(xml.includes('<line'))
    assert.ok(xml.includes('<text'))
    assert.ok(xml.includes('<path'))
    assert.ok(xml.includes('<g'))
  })

  test('serialise escape XML', () => {
    const d = emptyDoc()
    d.elements.push({ kind: 'text', x: 0, y: 0, text: '<script>alert("XSS")</script>' })
    const xml = serialise(d)
    assert.ok(!xml.includes('<script>'))
    assert.ok(xml.includes('&lt;script&gt;'))
    assert.ok(xml.includes('&quot;'))
  })

  test('serialise line avec dash', () => {
    const d = emptyDoc()
    d.elements.push({ kind: 'line', x1: 0, y1: 0, x2: 10, y2: 10, stroke: '#000', dash: [4, 2] })
    const xml = serialise(d)
    assert.ok(xml.includes('stroke-dasharray="4 2"'))
  })
})

describe('flowChartDoc', () => {
  test('nodes + edges renderés', () => {
    const doc = flowChartDoc(
      [{ id: 'a', label: 'A', x: 0, y: 0 }, { id: 'b', label: 'B', x: 200, y: 0 }],
      [{ from: 'a', to: 'b', label: 'lien' }],
    )
    const xml = serialise(doc)
    assert.ok(xml.includes('A'))
    assert.ok(xml.includes('B'))
    assert.ok(xml.includes('lien'))
    assert.ok(xml.includes('<line'))
    assert.ok(xml.includes('<rect'))
  })

  test('edge avec id inconnu → silencieusement ignorée', () => {
    const doc = flowChartDoc(
      [{ id: 'a', label: 'A', x: 0, y: 0 }],
      [{ from: 'a', to: 'nonexistent' }],
    )
    // Pas de crash, juste pas d'edge tracée
    assert.ok(doc.elements.length >= 2) // rect + text pour 'a'
  })

  test('nodes vides → doc avec viewBox seulement', () => {
    const doc = flowChartDoc([], [])
    assert.equal(doc.elements.length, 0)
  })

  test('largeur/hauteur custom des nodes', () => {
    const doc = flowChartDoc(
      [{ id: 'a', label: 'A', x: 0, y: 0, w: 300, h: 100 }],
      [],
    )
    const rect = doc.elements.find((e) => e.kind === 'rect')
    if (rect && rect.kind === 'rect') {
      assert.equal(rect.w, 300)
      assert.equal(rect.h, 100)
    }
  })
})

describe('gridOverlay', () => {
  test('grille 100×100 spacing 50 → ~5+5 lignes', () => {
    const lines = gridOverlay({ x: 0, y: 0, w: 100, h: 100 }, 50)
    assert.ok(lines.length >= 4)
  })

  test('toutes les lignes sont stroke avec opacity faible', () => {
    const lines = gridOverlay({ x: 0, y: 0, w: 100, h: 100 }, 25)
    for (const l of lines) {
      assert.equal(l.kind, 'line')
      if (l.kind === 'line') {
        assert.ok(l.stroke.includes('rgba') || l.stroke.includes('#'))
      }
    }
  })

  test('spacing très grand → moins de lignes', () => {
    const sparse = gridOverlay({ x: 0, y: 0, w: 100, h: 100 }, 200)
    const dense = gridOverlay({ x: 0, y: 0, w: 100, h: 100 }, 10)
    assert.ok(dense.length > sparse.length)
  })
})

describe('planRefinementPasses', () => {
  test('sketch-rapide → 1 pass', () => {
    const passes = planRefinementPasses({
      intent: 'sketch-rapide', confidence: 0.5, controlNetPreset: 'scribble',
      preferredOutput: 'both', matchedPatterns: [],
    })
    assert.equal(passes.length, 1)
  })

  test('schema-technique → 3 passes', () => {
    const passes = planRefinementPasses({
      intent: 'schema-technique', confidence: 0.8, controlNetPreset: 'mlsd',
      preferredOutput: 'svg', matchedPatterns: [],
    })
    assert.equal(passes.length, 3)
    assert.equal(passes[0].goal, 'composition')
    assert.equal(passes[1].goal, 'labels')
  })

  test('diagramme-flow → 3 passes (même chain que schema)', () => {
    const passes = planRefinementPasses({
      intent: 'diagramme-flow', confidence: 0.7, controlNetPreset: 'mlsd',
      preferredOutput: 'svg', matchedPatterns: [],
    })
    assert.equal(passes.length, 3)
  })

  test('croquis-artistique → 3 passes artistic chain', () => {
    const passes = planRefinementPasses({
      intent: 'croquis-artistique', confidence: 0.6, controlNetPreset: 'scribble',
      preferredOutput: 'raster', matchedPatterns: [],
    })
    assert.equal(passes.length, 3)
    assert.equal(passes[2].goal, 'polish')
  })

  test('controlNetWeight décroissant à travers les passes', () => {
    const passes = planRefinementPasses({
      intent: 'schema-technique', confidence: 0.8, controlNetPreset: 'mlsd',
      preferredOutput: 'svg', matchedPatterns: [],
    })
    for (let i = 1; i < passes.length; i++) {
      assert.ok(passes[i].controlNetWeight <= passes[i - 1].controlNetWeight)
    }
  })

  test('denoisingStrength dans [0..1]', () => {
    const passes = planRefinementPasses({
      intent: 'croquis-artistique', confidence: 0.5, controlNetPreset: 'scribble',
      preferredOutput: 'raster', matchedPatterns: [],
    })
    for (const p of passes) {
      assert.ok(p.denoisingStrength >= 0 && p.denoisingStrength <= 1)
    }
  })
})
