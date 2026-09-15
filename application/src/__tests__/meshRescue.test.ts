/**
 * Unit tests for the meshRescue.ts typed bridge client.
 * Run: node --experimental-strip-types --test src/__tests__/meshRescue.test.ts
 *
 * We inject a mock fetch into createMeshRescueClient so the tests don't
 * actually hit the bridge. Each method must:
 *   - call the correct path
 *   - send the correct payload (POST body or GET querystring)
 *   - return the parsed JSON unchanged so the typed Response unions flow
 *     through correctly.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import {
  createMeshRescueClient,
  rescueMeshAutonomous,
  type FetchLike,
  type AutoRescueV1,
} from '../services/meshRescue.ts'

type Recorded = {
  url: string
  method: string
  body?: unknown
}

function makeRecorder(reply: unknown, status = 200): { fetch: FetchLike; calls: Recorded[] } {
  const calls: Recorded[] = []
  const fetchImpl: FetchLike = async (input, init) => {
    let body: unknown = undefined
    if (init?.body) {
      try { body = JSON.parse(init.body as string) } catch { body = init.body }
    }
    calls.push({
      url: typeof input === 'string' ? input : (input as URL).toString(),
      method: (init?.method ?? 'GET').toUpperCase(),
      body,
    })
    return new Response(JSON.stringify(reply), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  return { fetch: fetchImpl, calls }
}

const BASE = 'http://127.0.0.1:3001'

describe('createMeshRescueClient', () => {
  test('scoreMesh hits POST /api/3d/mesh-score with mesh_path + kind', async () => {
    const reply = {
      ok: true,
      score: {
        ok: true,
        schema: 'aurora.mesh_quality.v1',
        mesh_path: 'm.glb',
        subject_kind: 'pc_tower',
        overall_score: 90.2,
        retry_recommended: false,
        retry_threshold: 60,
        retry_reasons: [],
        failed_axes: [],
        scores: {},
      },
    }
    const { fetch: f, calls } = makeRecorder(reply)
    const client = createMeshRescueClient(BASE, f)
    const res = await client.scoreMesh('m.glb', 'pc_tower')
    assert.equal(calls.length, 1)
    assert.equal(calls[0].method, 'POST')
    assert.equal(calls[0].url, `${BASE}/api/3d/mesh-score`)
    assert.deepEqual(calls[0].body, { mesh_path: 'm.glb', kind: 'pc_tower' })
    assert.equal(res.ok, true)
  })

  test('autoValidate defaults pipeline to hunyuan3d', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true,
      validation: {
        ok: true, schema: 'aurora.auto_validate.v1',
        mesh_path: 'm.glb', prompt: 'p', current_pipeline: 'hunyuan3d',
        extraction: { kind: 'pc_tower', confidence: 1, matched_pattern: 'boitier', alternatives: [] },
        score: { overall_score: 70, retry_recommended: true, failed_axes: [], retry_reasons: [], axes: {} },
        next_action: { action: 'retry_pipeline', next_pipeline: 'dreamgaussian', reason: 'x' },
      },
    })
    const client = createMeshRescueClient(BASE, f)
    await client.autoValidate('m.glb', 'p')
    assert.deepEqual(calls[0].body, { mesh_path: 'm.glb', prompt: 'p', pipeline: 'hunyuan3d' })
  })

  test('autoValidate honors explicit pipeline override', async () => {
    const { fetch: f, calls } = makeRecorder({ ok: false, error: 'x' })
    const client = createMeshRescueClient(BASE, f)
    await client.autoValidate('m.glb', 'p', 'dreamgaussian')
    assert.deepEqual(calls[0].body, { mesh_path: 'm.glb', prompt: 'p', pipeline: 'dreamgaussian' })
  })

  test('colorDiagnostic maps optional postMesh to post_mesh', async () => {
    const { fetch: f, calls } = makeRecorder({ ok: false, error: 'noop' })
    const client = createMeshRescueClient(BASE, f)
    await client.colorDiagnostic('ref.png', 'm.glb')
    assert.deepEqual(calls[0].body, { reference: 'ref.png', mesh: 'm.glb', post_mesh: null })
    await client.colorDiagnostic('ref.png', 'm.glb', 'post.glb')
    assert.deepEqual(calls[1].body, { reference: 'ref.png', mesh: 'm.glb', post_mesh: 'post.glb' })
  })

  test('sharpenMesh sends defaults when no opts', async () => {
    const { fetch: f, calls } = makeRecorder({ ok: false, error: 'noop' })
    const client = createMeshRescueClient(BASE, f)
    await client.sharpenMesh('m.glb', 'out.glb', 'pc_tower')
    assert.equal(calls[0].url, `${BASE}/api/3d/mesh-sharpen`)
    assert.deepEqual(calls[0].body, { mesh: 'm.glb', output: 'out.glb', kind: 'pc_tower' })
  })

  test('sharpenMesh propagates iters / lambda / flags', async () => {
    const { fetch: f, calls } = makeRecorder({ ok: false, error: 'noop' })
    const client = createMeshRescueClient(BASE, f)
    await client.sharpenMesh('m.glb', 'out.glb', 'humanoid', {
      smoothIters: 6, smoothLambda: 0.4, noFeatures: true, noColorSmooth: true,
    })
    assert.deepEqual(calls[0].body, {
      mesh: 'm.glb', output: 'out.glb', kind: 'humanoid',
      smooth_iters: 6, smooth_lambda: 0.4,
      no_features: true, no_color_smooth: true,
    })
  })

  test('bakeColors propagates multi_zone flag', async () => {
    const { fetch: f, calls } = makeRecorder({ ok: false, error: 'noop' })
    const client = createMeshRescueClient(BASE, f)
    await client.bakeColors('m.glb', 'r.png', 'o.glb', 'pc_tower')
    assert.deepEqual(calls[0].body, {
      mesh: 'm.glb', reference: 'r.png', output: 'o.glb',
      kind: 'pc_tower', multi_zone: false,
    })
    await client.bakeColors('m.glb', 'r.png', 'o.glb', 'pc_tower', true)
    assert.equal((calls[1].body as { multi_zone: boolean }).multi_zone, true)
  })

  test('autoRescue posts the right shape', async () => {
    const { fetch: f, calls } = makeRecorder({ ok: false, error: 'noop' })
    const client = createMeshRescueClient(BASE, f)
    await client.autoRescue('m.glb', 'r.png', 'p', 'out/')
    assert.equal(calls[0].url, `${BASE}/api/3d/auto-rescue`)
    assert.deepEqual(calls[0].body, {
      mesh: 'm.glb', reference: 'r.png', prompt: 'p', output_dir: 'out/',
    })
  })

  test('compareMeshes posts left/right/kind', async () => {
    const { fetch: f, calls } = makeRecorder({ ok: false, error: 'noop' })
    const client = createMeshRescueClient(BASE, f)
    await client.compareMeshes('a.glb', 'b.glb', 'humanoid')
    assert.deepEqual(calls[0].body, { left: 'a.glb', right: 'b.glb', kind: 'humanoid' })
  })

  test('generateViewerHtml omits title when missing', async () => {
    const { fetch: f, calls } = makeRecorder({ ok: false, error: 'noop' })
    const client = createMeshRescueClient(BASE, f)
    await client.generateViewerHtml('m.glb', 'v.html')
    assert.deepEqual(calls[0].body, { mesh: 'm.glb', output: 'v.html' })
    await client.generateViewerHtml('m.glb', 'v.html', 'My viewer')
    assert.deepEqual(calls[1].body, { mesh: 'm.glb', output: 'v.html', title: 'My viewer' })
  })

  test('getRunIndex builds querystring from opts', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, index: {
        ok: true, schema: 'aurora.run_index.v1',
        directory: 'output/3d', scored: false, kind_for_scoring: null,
        run_count: 0, standalone_count: 0, runs: [], standalones: [],
      },
    })
    const client = createMeshRescueClient(BASE, f)
    await client.getRunIndex()
    assert.equal(calls[0].url, `${BASE}/api/3d/run-index`)
    assert.equal(calls[0].method, 'GET')
    await client.getRunIndex({ kind: 'pc_tower', score: true })
    assert.match(calls[1].url, /\?kind=pc_tower&score=1$/)
  })

  test('runPipeline omits optional opts when absent', async () => {
    const { fetch: f, calls } = makeRecorder({ ok: false, error: 'noop' })
    const client = createMeshRescueClient(BASE, f)
    await client.runPipeline('a prompt', 'r1')
    assert.equal(calls[0].url, `${BASE}/api/3d/run-pipeline`)
    assert.equal(calls[0].method, 'POST')
    assert.deepEqual(calls[0].body, { prompt: 'a prompt', run_id: 'r1' })
  })

  test('runPipeline forwards motionPrompt + multiView + force', async () => {
    const { fetch: f, calls } = makeRecorder({ ok: false, error: 'noop' })
    const client = createMeshRescueClient(BASE, f)
    await client.runPipeline('p', 'r2', {
      motionPrompt: 'le perso marche', multiView: true, force: true,
    })
    assert.deepEqual(calls[0].body, {
      prompt: 'p', run_id: 'r2',
      motion_prompt: 'le perso marche', multi_view: true, force: true,
    })
  })

  test('runPipeline forwards UI parity fields for image character jobs', async () => {
    const { fetch: f, calls } = makeRecorder({ ok: false, error: 'noop' })
    const client = createMeshRescueClient(BASE, f)
    await client.runPipeline('Abraham Lincoln', 'r3', {
      purpose: 'character',
      subjectKind: 'character',
      images: ['https://example.test/lincoln.jpg'],
      multiView: false,
    })
    assert.deepEqual(calls[0].body, {
      prompt: 'Abraham Lincoln',
      run_id: 'r3',
      multi_view: false,
      purpose: 'character',
      subject_kind: 'character',
      images: ['https://example.test/lincoln.jpg'],
    })
  })

  test('runRegressionSuite posts UI-safe regression options', async () => {
    const reply = {
      ok: true,
      suite: {
        ok: true,
        schema: 'aurora.3d.regression_suite.v1',
        run_id: 'unit',
        generated_at: '2026-06-24T00:00:00Z',
        output_dir: 'output/3d/regression_suite/unit',
        fixture_smoke: true,
        live_reference: false,
        strict_mesh: true,
        case_count: 1,
        cases: [],
        summary: {
          failed_case_ids: [],
          skipped_mesh_case_ids: [],
          deterministic_contract: 'shared',
        },
      },
      returncode: 0,
    }
    const { fetch: f, calls } = makeRecorder(reply)
    const client = createMeshRescueClient(BASE, f)
    const out = await client.runRegressionSuite({
      caseIds: ['public_domain_known_person_abraham_lincoln'],
      fixtureSmoke: true,
      liveReference: false,
      strictMesh: true,
      meshMap: { mechanical_belt_drive_motion: 'application/output/3d/proc_pulley/pbr_pulley_proc.glb' },
    })
    assert.equal(calls[0].url, `${BASE}/api/3d/regression-suite`)
    assert.equal(calls[0].method, 'POST')
    assert.deepEqual(calls[0].body, {
      case_ids: ['public_domain_known_person_abraham_lincoln'],
      fixture_smoke: true,
      live_reference: false,
      strict_mesh: true,
      mesh_map: { mechanical_belt_drive_motion: 'application/output/3d/proc_pulley/pbr_pulley_proc.glb' },
    })
    assert.equal(out.ok, true)
  })

  test('motionParity hits GET /api/3d/motion-parity', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, returncode: 0, summary: 'PARITY_OK: 22 fixtures pass',
    })
    const client = createMeshRescueClient(BASE, f)
    const out = await client.motionParity()
    assert.equal(calls[0].url, `${BASE}/api/3d/motion-parity`)
    assert.equal(calls[0].method, 'GET')
    assert.equal(out.ok, true)
    assert.match(out.summary, /22 fixtures/)
  })

  test('scoreHistory defaults to top mode (no params)', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, history: { top: [] },
    })
    const client = createMeshRescueClient(BASE, f)
    const out = await client.scoreHistory()
    assert.equal(calls[0].url, `${BASE}/api/3d/score-history`)
    assert.equal(calls[0].method, 'GET')
    assert.equal(out.ok, true)
  })

  test('scoreHistory builds run_id + limit querystring', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, history: { events: [] },
    })
    const client = createMeshRescueClient(BASE, f)
    await client.scoreHistory({ runId: 'cat5_jellopus_mesh', limit: 5 })
    assert.equal(calls[0].url, `${BASE}/api/3d/score-history?run_id=cat5_jellopus_mesh&limit=5`)
    assert.equal(calls[0].method, 'GET')
  })

  test('scoreHistory forwards top=N', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, history: { top: [] },
    })
    const client = createMeshRescueClient(BASE, f)
    await client.scoreHistory({ top: 25 })
    assert.equal(calls[0].url, `${BASE}/api/3d/score-history?top=25`)
  })

  test('getTrackerHealth defaults (no staleMin)', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, health: {
        schema: 'aurora.tracker_health.v1', now: '2026-04-30T12:00:00Z',
        stale_threshold_min: 30, in_progress_count: 0, stale_count: 0,
        stale_tasks: [], ok: true,
      },
    })
    const client = createMeshRescueClient(BASE, f)
    const out = await client.getTrackerHealth()
    assert.equal(calls[0].url, `${BASE}/api/agents/health`)
    assert.equal(calls[0].method, 'GET')
    assert.equal(out.ok, true)
    if (out.ok) {
      assert.equal(out.health.stale_count, 0)
    }
  })

  test('getWatchdog forwards all knobs', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, watchdog: {
        schema: 'aurora.watchdog.v1',
        health: null, recent_dispatches: [],
        trend: null, top_runs: [], metrics_summary: null,
      },
    })
    const client = createMeshRescueClient(BASE, f)
    const out = await client.getWatchdog({ staleMin: 60, recent: 10, top: 3 })
    assert.equal(
      calls[0].url,
      `${BASE}/api/agents/watchdog?stale_min=60&recent=10&top=3`,
    )
    assert.equal(calls[0].method, 'GET')
    assert.equal(out.ok, true)
    if (out.ok) {
      assert.equal(out.watchdog.schema, 'aurora.watchdog.v1')
    }
  })

  test('listAgents hits GET /api/agents/list', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, schema_version: 'aurora.tracker.v1',
      leads: { '3d-lead': { sub_agents: ['3d-quality-rescuer'] } },
      crosscut: ['tunnel-validator'], descriptions: {}, agent_count: 38,
    })
    const client = createMeshRescueClient(BASE, f)
    const out = await client.listAgents()
    assert.equal(calls[0].url, `${BASE}/api/agents/list`)
    assert.equal(calls[0].method, 'GET')
    assert.equal(out.ok, true)
    if (out.ok) {
      assert.equal(out.agent_count, 38)
    }
  })

  test('getAgent encodes the name', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, name: '3d-quality-rescuer',
      description: 'rescue chain', model: 'claude-opus-4-7',
      color: 'cyan', body: '...',
    })
    const client = createMeshRescueClient(BASE, f)
    await client.getAgent('3d-quality-rescuer')
    assert.equal(calls[0].url, `${BASE}/api/agents/3d-quality-rescuer`)
  })

  test('getAgentMetrics hits GET /api/agents/metrics', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, metrics: {
        schema: 'aurora.metrics.v1',
        generated_at: '2026-04-30T13:00:00Z',
        total_dispatches: 20, global_done: 20, global_blocked: 0,
        global_success_rate: 1.0, leads: {},
      },
    })
    const client = createMeshRescueClient(BASE, f)
    const out = await client.getAgentMetrics()
    assert.equal(calls[0].url, `${BASE}/api/agents/metrics`)
    assert.equal(calls[0].method, 'GET')
    assert.equal(out.ok, true)
    if (out.ok) {
      assert.equal(out.metrics.total_dispatches, 20)
    }
  })

  test('getDispatches builds full querystring from all filters', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, query: {
        schema: 'aurora.tracker_query.v1',
        generated_at: '2026-04-30T13:00:00Z',
        filters: { run_id: 'cat5', lead: '3d-quality-rescuer',
                   status: 'done', since: '2026-04-30T00:00:00Z',
                   limit: 5 },
        match_count: 2,
        tasks: [],
      },
    })
    const client = createMeshRescueClient(BASE, f)
    const out = await client.getDispatches({
      runId: 'cat5', lead: '3d-quality-rescuer',
      status: 'done', since: '2026-04-30T00:00:00Z', limit: 5,
    })
    assert.equal(
      calls[0].url,
      `${BASE}/api/agents/dispatches?run_id=cat5&lead=3d-quality-rescuer&status=done&since=2026-04-30T00%3A00%3A00Z&limit=5`,
    )
    assert.equal(calls[0].method, 'GET')
    assert.equal(out.ok, true)
    if (out.ok) {
      assert.equal(out.query.match_count, 2)
    }
  })

  test('getDispatches with no opts hits bare URL', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, query: {
        schema: 'aurora.tracker_query.v1',
        generated_at: '2026-04-30T13:00:00Z',
        filters: { run_id: null, lead: null, status: null,
                   since: null, limit: null },
        match_count: 0, tasks: [],
      },
    })
    const client = createMeshRescueClient(BASE, f)
    await client.getDispatches()
    assert.equal(calls[0].url, `${BASE}/api/agents/dispatches`)
  })

  test('getAgentCoverage hits GET /api/agents/coverage', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, coverage: {
        schema: 'aurora.coverage.v1',
        generated_at: '2026-04-30T12:00:00Z',
        total_declared: 38, total_dispatched: 2, total_dead: 36,
        coverage_pct: 5.3, by_lead: [], dead: [],
      },
    })
    const client = createMeshRescueClient(BASE, f)
    const out = await client.getAgentCoverage()
    assert.equal(calls[0].url, `${BASE}/api/agents/coverage`)
    assert.equal(calls[0].method, 'GET')
    assert.equal(out.ok, true)
    if (out.ok) {
      assert.equal(out.coverage.total_dead, 36)
      assert.equal(out.coverage.coverage_pct, 5.3)
    }
  })

  test('getWatchdog defaults to no params', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, watchdog: {
        schema: 'aurora.watchdog.v1',
        health: null, recent_dispatches: [],
        trend: null, top_runs: [], metrics_summary: null,
      },
    })
    const client = createMeshRescueClient(BASE, f)
    await client.getWatchdog()
    assert.equal(calls[0].url, `${BASE}/api/agents/watchdog`)
  })

  test('getTrackerHealth forwards staleMin', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, health: {
        schema: 'aurora.tracker_health.v1', now: 'x',
        stale_threshold_min: 60, in_progress_count: 0,
        stale_count: 0, stale_tasks: [], ok: true,
      },
    })
    const client = createMeshRescueClient(BASE, f)
    await client.getTrackerHealth({ staleMin: 60 })
    assert.equal(calls[0].url, `${BASE}/api/agents/health?stale_min=60`)
  })

  test('scoreHistory trend mode sets trend=1', async () => {
    const { fetch: f, calls } = makeRecorder({
      ok: true, history: {
        schema: 'aurora.score_trend.v1', total_events: 8, total_runs: 2,
        promoted_runs: 2, promote_rate: 1.0, mean_delta: 20.0,
        best_delta: 20.0, worst_delta: 20.0, axis_lifts: { color_richness: 2 },
        kind_breakdown: {}, last_ts: '2026-04-30T11:24:25Z',
      },
    })
    const client = createMeshRescueClient(BASE, f)
    const out = await client.scoreHistory({ trend: true })
    assert.equal(calls[0].url, `${BASE}/api/3d/score-history?trend=1`)
    assert.equal(out.ok, true)
    if (out.ok && 'schema' in out.history) {
      assert.equal(out.history.schema, 'aurora.score_trend.v1')
      assert.equal(out.history.promoted_runs, 2)
    } else {
      assert.fail('expected trend payload')
    }
  })

  test('throws on non-2xx', async () => {
    const fetchImpl: FetchLike = async () =>
      new Response('boom', { status: 500, statusText: 'server err' })
    const client = createMeshRescueClient(BASE, fetchImpl)
    await assert.rejects(
      () => client.scoreMesh('m.glb', 'pc_tower'),
      /500 server err/,
    )
  })

  test('strips trailing slash from base URL', async () => {
    const { fetch: f, calls } = makeRecorder({ ok: false, error: 'noop' })
    const client = createMeshRescueClient(`${BASE}/`, f)
    await client.scoreMesh('m.glb', 'pc_tower')
    assert.equal(calls[0].url, `${BASE}/api/3d/mesh-score`)
  })
})


describe('rescueMeshAutonomous helper', () => {
  test('returns the rescue payload on success', async () => {
    const expected: AutoRescueV1 = {
      ok: true, schema: 'aurora.auto_rescue.v1',
      input_mesh: 'm.glb', reference: 'r.png', prompt: 'p',
      extraction: { kind: 'pc_tower', confidence: 1, matched_pattern: 'boitier', alternatives: [] },
      final_mesh: 'out/m_baked.glb', initial_score: 70.2, final_score: 90.2,
      score_delta: 20.0, final_failed_axes: [], audit_trail: [],
    }
    const { fetch: f } = makeRecorder({ ok: true, rescue: expected })
    const client = createMeshRescueClient(BASE, f)
    const out = await rescueMeshAutonomous(client, {
      mesh: 'm.glb', reference: 'r.png', prompt: 'p', outputDir: 'out',
    })
    assert.equal(out.score_delta, 20)
    assert.equal(out.final_mesh, 'out/m_baked.glb')
  })

  test('throws when bridge returns ok=false', async () => {
    const { fetch: f } = makeRecorder({ ok: false, error: 'reference not found' })
    const client = createMeshRescueClient(BASE, f)
    await assert.rejects(
      () => rescueMeshAutonomous(client, {
        mesh: 'm.glb', reference: 'r.png', prompt: 'p', outputDir: 'out',
      }),
      /reference not found/,
    )
  })
})
