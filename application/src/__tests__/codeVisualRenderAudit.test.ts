import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  CODE_VISUAL_RENDER_AUDIT_SCHEMA,
  buildRenderedVisualAuditCritique,
  scoreRenderedVisualAudit,
  type CodeVisualRenderAudit,
  type RenderedViewportAudit,
} from '../services/codeVisualRenderAudit.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'
import { buildVisualFidelityCritique, evaluateVisualFidelity } from '../services/codeVisualFidelity.ts'

function viewport(width: number, overrides: Partial<RenderedViewportAudit> = {}): RenderedViewportAudit {
  const viewportName = `${width}x900`
  return {
    viewport: viewportName,
    width,
    height: 900,
    screenshotPath: `/tmp/${viewportName}.png`,
    bodyTextLength: 1800,
    consoleErrors: [],
    exceptions: [],
    failedRequests: [],
    canvasPresent: false,
    textNodeCount: 24,
    headingCount: 5,
    mediaCount: 3,
    interactiveCount: 5,
    cssVarCount: 8,
    fontFamilies: ['Inter', 'Space Grotesk'],
    verticalGapMedian: 32,
    contrastSamples: [
      { viewport: viewportName, source: 'pixel', ratio: 7.2, label: 'hero' },
      { viewport: viewportName, source: 'pixel', ratio: 5.1, label: 'card' },
    ],
    vision: { score: 84, verdict: 'studio', summary: 'composition mature' },
    ...overrides,
  }
}

function audit(overrides: Partial<CodeVisualRenderAudit> = {}): CodeVisualRenderAudit {
  return {
    schemaVersion: CODE_VISUAL_RENDER_AUDIT_SCHEMA,
    url: 'http://127.0.0.1:4173',
    viewports: [viewport(390), viewport(834), viewport(1440)],
    ...overrides,
  }
}

describe('codeVisualRenderAudit', () => {
  test('score un rendu reel multi-viewport avec contraste pixel', () => {
    const report = scoreRenderedVisualAudit(audit())

    assert.equal(report.source, 'render_audit')
    assert.equal(report.passed, true)
    assert.ok(report.score >= 90)
    assert.deepEqual(report.viewports, ['390x900', '834x900', '1440x900'])
  })

  test('bloque un rendu sans screenshots ni contraste WCAG pixel', () => {
    const poor = audit({
      viewports: [
        viewport(390, {
          screenshotPath: undefined,
          bodyTextLength: 120,
          textNodeCount: 2,
          headingCount: 1,
          mediaCount: 0,
          interactiveCount: 0,
          cssVarCount: 0,
          verticalGapMedian: 4,
          contrastSamples: [{ viewport: '390x900', source: 'computed-style', ratio: 2.1 }],
          vision: { score: 30, verdict: 'tutorial', summary: 'page tutoriel' },
        }),
      ],
    })
    const report = scoreRenderedVisualAudit(poor)

    assert.equal(report.passed, false)
    assert.ok(report.failedChecks.includes('rendered_screenshots'))
    assert.ok(report.failedChecks.includes('rendered_breakpoints'))
    assert.ok(report.failedChecks.includes('pixel_contrast_wcag'))
    assert.match(buildRenderedVisualAuditCritique(report), /JUGE VISUEL RENDER-IN-THE-LOOP/)
  })

  test('evaluateVisualFidelity privilegie le rendu reel quand fourni', () => {
    const intent = classifyCodeIntent('landing page HTML CSS premium')
    const report = evaluateVisualFidelity([
      { name: 'index.html', language: 'html', content: '<html><body><h1>Bienvenue chez X</h1></body></html>' },
    ], intent, audit())

    assert.equal(report.source, 'render_audit')
    assert.equal(report.passed, true)
    assert.match(report.summary, /Rendu reel/)
  })

  test('la critique publique route vers le bloc render-in-the-loop', () => {
    const poor = scoreRenderedVisualAudit(audit({
      viewports: [viewport(390, {
        screenshotPath: undefined,
        contrastSamples: [],
        vision: { score: 20, verdict: 'tutorial', summary: 'faible' },
      })],
    }))

    assert.match(buildVisualFidelityCritique(poor), /RENDER-IN-THE-LOOP/)
  })

  test('GARDE UNIFORMITE: sans jugement vision, le check studio ne rapporte pas 12 points gratuits', () => {
    // Plusieurs checks non-vision echouent (poids gagne nettement < total), pour
    // que l'ecart vision-presente/absente survive l'arrondi. On garde screenshots
    // + contraste (checks bloquants) valides: c'est bien un rendu, seul le soin
    // visuel non-vision est moyen.
    const widths = [390, 834, 1440]
    const middling = { headingCount: 1, mediaCount: 0, interactiveCount: 0, cssVarCount: 0, verticalGapMedian: 4, fontFamilies: ['Arial'], bodyTextLength: 400, textNodeCount: 6 }
    const noVision = audit({
      viewports: widths.map((w) => viewport(w, { ...middling, vision: undefined })),
    })
    const withStudioVision = audit({
      viewports: widths.map((w) => viewport(w, {
        ...middling,
        vision: { score: 84, verdict: 'studio', summary: 'composition mature' },
      })),
    })
    const noVisionScore = scoreRenderedVisualAudit(noVision).score
    const studioScore = scoreRenderedVisualAudit(withStudioVision).score
    // Avant le fix, les deux etaient EGAUX (12 points gratuits en l'absence de
    // vision). Desormais un rendu reellement juge studio marque STRICTEMENT plus
    // qu'un rendu non juge — le signal absent n'est ni recompense ni penalise.
    assert.ok(noVisionScore < studioScore, `no-vision ${noVisionScore} doit etre < studio ${studioScore}`)
  })
})
