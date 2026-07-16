import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  CODE_SIMULATION_LAB_SCHEMA,
  isCodeSimulationLabReport,
  runCodeSimulationLab,
  summarizeCodeSimulationLab,
  type CodeSimulationLabReport,
} from '../services/codeSimulationLab.ts'

function sampleReport(): CodeSimulationLabReport {
  return {
    schemaVersion: CODE_SIMULATION_LAB_SCHEMA,
    url: 'http://127.0.0.1:1420',
    stages: [
      {
        id: 'chromium_mobile_4g_touch',
        label: 'Chromium Pixel 8 touch 4G',
        family: 'web',
        browser: 'chromium',
        status: 'executed',
        realExecution: true,
        viewport: '390x844',
        dpr: 3,
        touch: true,
        throttling: { cpu: 4, network: { latencyMs: 90 } },
      },
      {
        id: 'firefox_headless',
        label: 'Firefox headless screenshot',
        family: 'web',
        browser: 'firefox',
        status: 'executed',
        realExecution: true,
      },
      {
        id: 'renode_microcontrollers',
        label: 'Renode ESP32/Arduino/Raspberry',
        family: 'embedded',
        status: 'unavailable',
        realExecution: false,
        error: 'Renode introuvable',
      },
      {
        id: 'console_emulation_feasibility',
        label: 'Consoles anciennes/recentes',
        family: 'console',
        status: 'deferred',
        realExecution: false,
      },
    ],
  }
}

describe('codeSimulationLab', () => {
  test('valide le schema et resume les executions reelles', () => {
    const report = sampleReport()
    const summary = summarizeCodeSimulationLab(report)

    assert.equal(isCodeSimulationLabReport(report), true)
    assert.equal(summary.executed, 2)
    assert.equal(summary.realExecutions, 2)
    assert.deepEqual(summary.webBrowsers.sort(), ['chromium', 'firefox'])
    assert.match(summary.summary, /2 scenario/)
    assert.match(summary.summary, /indisponible/)
  })

  test('rejette un rapport sans stages conformes', () => {
    assert.equal(isCodeSimulationLabReport({ schemaVersion: CODE_SIMULATION_LAB_SCHEMA, url: 'x', stages: [{}] }), false)
    assert.equal(isCodeSimulationLabReport({ schemaVersion: 'old', url: 'x', stages: [] }), false)
    assert.equal(isCodeSimulationLabReport({
      schemaVersion: CODE_SIMULATION_LAB_SCHEMA,
      url: 'x',
      stages: [{ id: 'fake', label: 'Fake', family: 'web', status: 'success', realExecution: true }],
    }), false)
    assert.equal(isCodeSimulationLabReport({
      schemaVersion: CODE_SIMULATION_LAB_SCHEMA,
      url: 'x',
      stages: [{ id: 'fake', label: 'Fake', family: 'web', status: 'executed', realExecution: false }],
    }), false)
  })

  test('poste vers /api/code/simulation-lab', async () => {
    const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = []
    const fetchImpl = async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ input, init })
      return new Response(JSON.stringify({ ok: true, report: sampleReport() }), { status: 200 })
    }

    const report = await runCodeSimulationLab({
      url: 'http://127.0.0.1:1420',
      bridgeUrl: 'http://127.0.0.1:3001',
      waitMs: 900,
      fetchImpl,
    })

    assert.equal(report.schemaVersion, CODE_SIMULATION_LAB_SCHEMA)
    assert.equal(String(calls[0].input), 'http://127.0.0.1:3001/api/code/simulation-lab')
    assert.equal(JSON.parse(String(calls[0].init?.body)).waitMs, 900)
  })
})
