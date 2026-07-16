import assert from 'node:assert/strict'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { describe, test } from 'node:test'

const scenariosUrl = pathToFileURL(join(process.cwd(), 'python-services/aurora_code/cdp_scenarios.mjs')).href

describe('WS9/WS12 CDP modules', () => {
  test('les scenarios audit et simulation conservent leurs contrats', async () => {
    const { audit, simulate, viewportName } = await import(scenariosUrl)
    const outputDir = mkdtempSync(join(tmpdir(), 'aurora-cdp-test-'))
    const inspectCalls: Array<{ width: number; height: number; mobile: boolean }> = []
    const inspect = async (_url: string, _path: string, width: number, height: number, _wait: number, mobile: boolean) => {
      inspectCalls.push({ width, height, mobile })
      return {
        ok: true,
        console_errors: [],
        exceptions: [],
        failed_requests: [],
        render_metrics: { bodyTextLength: 120, headingCount: 2, interactiveCount: 3 },
        performance_metrics: { TaskDuration: 0.25 },
      }
    }

    try {
      assert.equal(viewportName(390, 844), '390x844')
      const simulation = await simulate('http://127.0.0.1:1420', outputDir, 1, inspect)
      assert.equal(simulation.schemaVersion, 'aurora.code.simulation-lab/1')
      assert.equal(simulation.stages.length, 3)
      assert.ok(simulation.stages.every((stage: { realExecution: boolean }) => stage.realExecution))

      const visualAudit = await audit('http://127.0.0.1:1420', outputDir, 1, inspect)
      assert.equal(visualAudit.schemaVersion, 'aurora.code.visual-render-audit/1')
      assert.deepEqual(visualAudit.viewports.map((item: { viewport: string }) => item.viewport), ['390x844', '834x1112', '1440x900'])
      assert.equal(inspectCalls.length, 6)
    } finally {
      rmSync(outputDir, { recursive: true, force: true })
    }
  })
})
