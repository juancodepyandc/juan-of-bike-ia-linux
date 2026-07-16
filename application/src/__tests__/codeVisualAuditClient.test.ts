import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  blendRenderedVisualIntoFinalScore,
  buildVisualScoreEventFromReport,
  runCodeVisualRenderAudit,
} from '../services/codeVisualAuditClient.ts'
import { CODE_VISUAL_RENDER_AUDIT_SCHEMA, type CodeVisualRenderAudit } from '../services/codeVisualRenderAudit.ts'
import type { VisualFidelityReport } from '../services/codeVisualFidelity.ts'

function audit(): CodeVisualRenderAudit {
  return {
    schemaVersion: CODE_VISUAL_RENDER_AUDIT_SCHEMA,
    url: 'http://localhost:5173',
    viewports: [390, 834, 1440].map((width) => ({
      viewport: `${width}x900`,
      width,
      height: 900,
      screenshotPath: `/tmp/${width}.png`,
      bodyTextLength: 1600,
      consoleErrors: [],
      exceptions: [],
      failedRequests: [],
      canvasPresent: false,
      textNodeCount: 22,
      headingCount: 5,
      mediaCount: 3,
      interactiveCount: 4,
      cssVarCount: 8,
      fontFamilies: ['Inter'],
      verticalGapMedian: 28,
      contrastSamples: [
        { ratio: 6.2, source: 'pixel', viewport: `${width}x900`, label: 'body' },
        { ratio: 5.1, source: 'pixel', viewport: `${width}x900`, label: 'cta' },
      ],
      vision: { score: 82, verdict: 'studio', summary: 'studio' },
    })),
  }
}

describe('codeVisualAuditClient', () => {
  test('appelle /api/code/visual-audit et convertit en visual.score', async () => {
    let requestUrl = ''
    let requestBody: any = null
    const result = await runCodeVisualRenderAudit({
      url: 'http://localhost:5173',
      includeVision: true,
      visionModel: 'qwen3-vl:30b',
      bridgeUrl: 'http://bridge',
      eventMeta: { runId: 4, sequence: 9, timestamp: 10 },
      fetchImpl: async (input, init) => {
        requestUrl = String(input)
        requestBody = JSON.parse(String(init?.body ?? '{}'))
        return new Response(JSON.stringify({ ok: true, audit: audit() }), { status: 200 })
      },
    })

    assert.equal(requestUrl, 'http://bridge/api/code/visual-audit')
    assert.equal(requestBody.vision, true)
    assert.equal(result.report.source, 'render_audit')
    assert.equal(result.event?.kind, 'visual.score')
    assert.equal(result.event?.source, 'render_audit')
    assert.deepEqual(result.event?.viewports, ['390x900', '834x900', '1440x900'])
  })

  test('buildVisualScoreEventFromReport conserve les echecs du juge rendu', () => {
    const report: VisualFidelityReport = {
      score: 42,
      passed: false,
      floor: 75,
      checks: [],
      failedChecks: ['pixel_contrast_wcag'],
      summary: 'Rendu insuffisant',
      source: 'render_audit',
      viewports: ['390x844'],
    }

    const event = buildVisualScoreEventFromReport(report, { runId: 1, sequence: 2, timestamp: 3 })

    assert.equal(event.score, 42)
    assert.equal(event.viewport, '390x844')
    assert.deepEqual(event.failedChecks, ['pixel_contrast_wcag'])
  })
})

describe('WS9: blendRenderedVisualIntoFinalScore fait compter le juge visuel', () => {
  function report(overrides: Partial<VisualFidelityReport>): VisualFidelityReport {
    return {
      score: 90, passed: true, floor: 70, checks: [], failedChecks: [],
      summary: 'ok', source: 'render_audit', viewports: ['1440x900'],
      ...overrides,
    }
  }

  test('un rendu excellent tire le score final vers le haut mais reste pondere', () => {
    const blended = blendRenderedVisualIntoFinalScore(80, report({ score: 100, passed: true }))
    // 80*0.65 + 100*0.35 = 87
    assert.equal(blended.score, 87)
    assert.equal(blended.belowThreshold, false)
    assert.equal(blended.hint, null)
  })

  test('un rendu qui echoue le seuil plafonne le score et fournit un indice de regeneration', () => {
    const blended = blendRenderedVisualIntoFinalScore(95, report({ score: 40, passed: false, floor: 70, failedChecks: ['pixel_contrast_wcag'] }))
    assert.equal(blended.belowThreshold, true)
    assert.ok(blended.score <= 84, `score plafonne attendu <=84, recu ${blended.score}`)
    assert.ok(blended.score < 95, 'le rendu insuffisant doit faire baisser le score modele')
    assert.ok(typeof blended.hint === 'string' && blended.hint.length > 0, 'un indice de regeneration doit etre fourni')
  })

  test('un rendu juste sous le seuil est signale belowThreshold', () => {
    const blended = blendRenderedVisualIntoFinalScore(88, report({ score: 68, passed: false, floor: 70 }))
    assert.equal(blended.belowThreshold, true)
  })
})
