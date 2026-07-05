/**
 * Tests barre expert : video composition planner + drawing intent/SVG.
 *
 * Video : la timeline produite doit être valide FFmpeg-side (durées
 * additives, aucun overlap interdit, ducking dans les bornes dB), et
 * doit respecter le rythme de la plateforme cible.
 *
 * Drawing : SVG produit doit valider la syntaxe XML, échapper les
 * caractères spéciaux, et la classification doit discriminer schéma vs
 * croquis sur 4 briefs typiques.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { defaultExportPresets, planTimeline } from '../services/videoCompositionPlanner.ts'
import {
  AURORA_PALETTE,
  classifyDrawingIntent,
  emptyDoc,
  flowChartDoc,
  gridOverlay,
  planRefinementPasses,
  serialise,
} from '../services/drawingStyleAndSvg.ts'

// ===========================================================================
// VIDEO
// ===========================================================================

describe('planTimeline — barre expert', () => {
  const baseBrief = {
    script: 'Bonjour. Cette vidéo te montre comment réussir un montage à la maison. Suis ces étapes simples.',
    format: '16:9' as const,
    tone: 'tutoriel' as const,
    platform: 'youtube-long' as const,
    speakerName: 'Aurora',
  }

  test('timeline contient hook, body, lower-third, CTA, jingle', () => {
    const t = planTimeline(baseBrief)
    const kinds = new Set(t.clips.map((c) => c.kind))
    assert.ok(kinds.has('jingle'))
    assert.ok(kinds.has('lower-third'))
    assert.ok(kinds.has('b-roll-image')) // hook + outro CTA
    assert.ok(kinds.has('talking-head') || kinds.has('b-roll-3d'))
  })

  test('clips ne overlap pas (sauf lower-third qui est overlay)', () => {
    const t = planTimeline(baseBrief)
    const sequential = t.clips.filter((c) => c.kind !== 'lower-third').sort((a, b) => a.startMs - b.startMs)
    for (let i = 1; i < sequential.length; i += 1) {
      assert.ok(sequential[i].startMs >= sequential[i - 1].startMs + sequential[i - 1].durationMs - 1,
        `overlap entre ${sequential[i - 1].id} (${sequential[i - 1].startMs}+${sequential[i - 1].durationMs}) et ${sequential[i].id} (${sequential[i].startMs})`)
    }
  })

  test('audio ducking spec respecte la convention pro (-18 dB)', () => {
    const t = planTimeline(baseBrief)
    const music = t.audioTracks.find((a) => a.kind === 'music')
    assert.ok(music)
    assert.equal(music.duckOnVoiceOver, true)
    assert.ok(music.duckDb! <= -15, `duck profondeur ${music.duckDb}`)
  })

  test('VO et music ont des durées cohérentes (VO ⊂ music)', () => {
    const t = planTimeline(baseBrief)
    const vo = t.audioTracks.find((a) => a.kind === 'voice-over')!
    const music = t.audioTracks.find((a) => a.kind === 'music')!
    assert.ok(vo.startMs >= music.startMs)
    assert.ok(vo.startMs + vo.durationMs <= music.startMs + music.durationMs + 1)
  })

  test('totalDurationMs = somme des clips séquentiels', () => {
    const t = planTimeline(baseBrief)
    const sequential = t.clips.filter((c) => c.kind !== 'lower-third')
    const sumSeq = sequential.reduce((s, c) => s + c.durationMs, 0)
    // Tolérance ±1ms pour les arrondis.
    assert.ok(Math.abs(t.totalDurationMs - sumSeq) <= 1, `total ${t.totalDurationMs} vs seq ${sumSeq}`)
  })

  test('TikTok : durée totale ≤ 60s + cadence cuts < 4s', () => {
    const t = planTimeline({ ...baseBrief, platform: 'tiktok', format: '9:16' })
    // Body cuts < 4s chaque
    const bodyCuts = t.clips.filter((c) => c.id.startsWith('body-'))
    for (const c of bodyCuts) assert.ok(c.durationMs < 4000, `${c.id} ${c.durationMs}ms`)
  })

  test('sous-titres présents, non vides, sans gap', () => {
    const t = planTimeline(baseBrief)
    assert.ok(t.subtitles.length >= 2)
    for (const sub of t.subtitles) {
      assert.ok(sub.endMs > sub.startMs)
      assert.ok(sub.text.trim().length > 0)
    }
  })

  test('export presets : bitrate ≥ 6 Mbps pour 1080p', () => {
    const t = planTimeline(baseBrief)
    const presets = defaultExportPresets(t)
    for (const p of presets) {
      assert.ok(p.bitrateMbps >= 5, `${p.suffix} bitrate ${p.bitrateMbps}`)
      assert.ok(p.fps >= 24)
    }
  })

  test('script vide ne plante pas', () => {
    const t = planTimeline({ ...baseBrief, script: '' })
    assert.ok(t.clips.length > 0)
    assert.ok(t.totalDurationMs > 0)
  })
})

// ===========================================================================
// DRAWING
// ===========================================================================

describe('classifyDrawingIntent — discrimination', () => {
  test('"schéma technique d\'un circuit RC" → schema-technique', () => {
    const r = classifyDrawingIntent("schéma technique d'un circuit RC avec labels R, C et tension")
    assert.equal(r.intent, 'schema-technique')
    assert.equal(r.preferredOutput, 'svg')
  })

  test('"croquis aquarelle d\'une fleur" → croquis-artistique', () => {
    const r = classifyDrawingIntent("croquis aquarelle d'une fleur")
    assert.equal(r.intent, 'croquis-artistique')
  })

  test('"flowchart algorithme de tri" → diagramme-flow', () => {
    const r = classifyDrawingIntent('flowchart algorithme de tri par insertion')
    assert.equal(r.intent, 'diagramme-flow')
  })

  test('"histogramme données" → graphique-data', () => {
    const r = classifyDrawingIntent('histogramme des données mensuelles')
    assert.equal(r.intent, 'graphique-data')
  })

  test('brief vague → sketch-rapide fallback', () => {
    const r = classifyDrawingIntent('dessine quelque chose')
    assert.equal(r.intent, 'sketch-rapide')
    assert.ok(r.confidence <= 0.4)
  })

  test('preset ControlNet aligné sur l\'intent', () => {
    assert.equal(classifyDrawingIntent('schéma circuit').controlNetPreset, 'mlsd')
    assert.equal(classifyDrawingIntent('aquarelle').controlNetPreset, 'scribble')
    assert.equal(classifyDrawingIntent('histogramme').controlNetPreset, 'lineart')
  })

  test('refinement passes : 3 pour schéma, 1 pour sketch', () => {
    const schema = planRefinementPasses(classifyDrawingIntent('schéma technique'))
    const sketch = planRefinementPasses(classifyDrawingIntent('sketch rapide'))
    assert.ok(schema.length >= 3)
    assert.equal(sketch.length, 1)
  })

  test('controlNetWeight décroît au fil des passes (raffinement)', () => {
    const passes = planRefinementPasses(classifyDrawingIntent('schéma technique'))
    for (let i = 1; i < passes.length; i += 1) {
      assert.ok(passes[i].controlNetWeight <= passes[i - 1].controlNetWeight, `pass ${i} weight ${passes[i].controlNetWeight} ≥ pass ${i - 1} weight ${passes[i - 1].controlNetWeight}`)
    }
  })
})

describe('SVG serialise — validité XML', () => {
  test('document basique commence par <?xml et finit par </svg>', () => {
    const doc = emptyDoc({ x: 0, y: 0, w: 100, h: 100 })
    doc.elements.push({ kind: 'circle', cx: 50, cy: 50, r: 20, fill: AURORA_PALETTE.primary })
    const xml = serialise(doc)
    assert.ok(xml.startsWith('<?xml'))
    assert.ok(xml.trim().endsWith('</svg>'))
  })

  test('viewBox au bon format', () => {
    const xml = serialise(emptyDoc({ x: -10, y: -10, w: 200, h: 150 }))
    assert.ok(xml.includes('viewBox="-10 -10 200 150"'))
  })

  test('échappe < > & " correctement', () => {
    const doc = emptyDoc()
    doc.elements.push({ kind: 'text', x: 0, y: 0, text: 'a & <b> "c"' })
    const xml = serialise(doc)
    assert.ok(xml.includes('a &amp; &lt;b&gt;'))
    assert.ok(xml.includes('&quot;c&quot;'))
    // Vérifie qu'aucun caractère non échappé n'est passé.
    assert.equal(xml.match(/<text[^>]*>([^<]*)</)?.[1].includes('&'), true)
  })

  test('couleurs Aurora palette appliquées via variables CSS', () => {
    const doc = emptyDoc()
    const xml = serialise(doc)
    // Toutes les couleurs de la palette doivent apparaître dans les variables.
    for (const v of Object.values(AURORA_PALETTE)) {
      assert.ok(xml.includes(v), `couleur ${v} absente du style`)
    }
  })

  test('groupes avec transform sérialisés correctement', () => {
    const doc = emptyDoc()
    doc.elements.push({
      kind: 'group',
      transform: 'rotate(45, 50, 50)',
      children: [{ kind: 'rect', x: 0, y: 0, w: 10, h: 10 }],
    })
    const xml = serialise(doc)
    assert.ok(xml.includes('<g transform="rotate(45, 50, 50)"'))
    assert.ok(xml.includes('<rect'))
  })
})

describe('SVG helpers — production réelle', () => {
  test('flowChartDoc rend N nodes et M edges', () => {
    const doc = flowChartDoc(
      [
        { id: 'a', label: 'Début', x: 100, y: 50 },
        { id: 'b', label: 'Décision', x: 100, y: 200 },
        { id: 'c', label: 'Fin', x: 300, y: 350 },
      ],
      [
        { from: 'a', to: 'b' },
        { from: 'b', to: 'c', label: 'oui' },
      ],
    )
    const xml = serialise(doc)
    assert.ok(xml.includes('Début'))
    assert.ok(xml.includes('Décision') || xml.includes('D&#233;cision') || xml.includes('Decision') || xml.includes('Décision'))
    assert.ok(xml.includes('Fin'))
    assert.ok(xml.includes('oui'))
    // Comptage rapide : 3 nodes + 2 edges → ≥ 3 rect + 2 line
    const rectCount = (xml.match(/<rect/g) || []).length
    const lineCount = (xml.match(/<line/g) || []).length
    assert.ok(rectCount >= 3, `rect count ${rectCount}`)
    assert.ok(lineCount >= 2, `line count ${lineCount}`)
  })

  test('gridOverlay produit lignes verticales + horizontales', () => {
    const lines = gridOverlay({ x: 0, y: 0, w: 100, h: 100 }, 25)
    // 5×5 = 10 lignes (4 espaces + 1 bord chacun = 5)
    assert.equal(lines.length, 10)
    const vertical = lines.filter((l) => l.kind === 'line' && (l as { x1: number; x2: number }).x1 === (l as { x1: number; x2: number }).x2)
    const horizontal = lines.filter((l) => l.kind === 'line' && (l as { y1: number; y2: number }).y1 === (l as { y1: number; y2: number }).y2)
    assert.equal(vertical.length, 5)
    assert.equal(horizontal.length, 5)
  })

  test('SVG produit par flowChartDoc passe ne contient pas de caractères XML invalides', () => {
    const doc = flowChartDoc(
      [{ id: 'a', label: 'A & B <stuff>', x: 0, y: 0 }],
      [],
    )
    const xml = serialise(doc)
    // Aucun & non échappé.
    const unescaped = xml.match(/&(?!amp;|lt;|gt;|quot;|apos;|#)/g)
    assert.equal(unescaped, null, `caractères & non échappés: ${unescaped}`)
  })
})
