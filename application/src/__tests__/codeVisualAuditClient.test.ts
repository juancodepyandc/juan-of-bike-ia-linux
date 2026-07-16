import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
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
