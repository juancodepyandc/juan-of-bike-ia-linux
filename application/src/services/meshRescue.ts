// ---------------------------------------------------------------------------
// meshRescue.ts — typed React-side client for the Aurora 3D rescue toolchain
// (Python scripts shipped in v78t–v79c, exposed via the bridge_server.py
// endpoints). One thin wrapper per endpoint, with strict response types
// matching each script's `aurora.<schema>.v1` JSON output.
//
// The matching Python sources are:
//   application/python-services/mesh_quality_score.py        -> scoreMesh
//   application/python-services/auto_validate_mesh.py        -> autoValidate
//   application/python-services/mesh_color_diagnostic.py     -> colorDiagnostic
//   application/python-services/bake_vertex_colors.py        -> bakeColors
//   application/python-services/mesh_reshape.py              -> (via auto_rescue)
//   application/python-services/auto_rescue_mesh.py          -> autoRescue
//   application/python-services/mesh_compare.py              -> compareMeshes
//   application/python-services/aurora_3d_viewer.py          -> generateViewerHtml
//   application/python-services/mesh_run_index.py            -> getRunIndex
//
// When the schemas there change, bump the corresponding *V1 type alias here
// AND update test_mesh_rescue.ts (TODO once the test harness is wired).
// ---------------------------------------------------------------------------

// Subject kinds mirror application/python-services/subject_kind_extractor.py
// KIND_PATTERNS (and mesh_quality_score.KIND_ASPECT). Keep in sync — there is
// no compile-time check across language boundaries.
export type ThreeDSubjectKind =
  | 'character'
  | 'humanoid'
  | 'quadruped'
  | 'creature'
  | 'pc_tower'
  | 'case'
  | 'computer'
  | 'vehicle'
  | 'product'
  | 'gadget'
  | 'architecture'
  | 'sphere'
  | 'generic'

export type ThreeDPipelineCurrent =
  | 'hunyuan3d'
  | 'dreamgaussian'
  | 'procedural'
  | 'mesh_postprocess'

export type ThreeDPipelineNext = ThreeDPipelineCurrent | 'procedural_or_multiview' | null

// ---------- mesh-score ----------

export type MeshQualityV1 = {
  ok: true
  schema: 'aurora.mesh_quality.v1'
  mesh_path: string
  subject_kind: ThreeDSubjectKind
  overall_score: number
  retry_recommended: boolean
  retry_threshold: number
  retry_reasons: string[]
  failed_axes: string[]
  scores: {
    color_richness: { score: number; has_vertex_colors: boolean; unique_colors: number; variance: number }
    geometric_density: { score: number; vertex_count: number; face_count: number; vertex_floor: number; passes_floor: boolean }
    silhouette_aspect: { score: number; extents_m: number[]; normalized: number[]; expected: number[] | string; aspect_l1_distance?: number }
    manifold_health: { score: number; is_watertight: boolean; euler_number: number | null; broken_faces: number; error?: string }
    surface_quality: { score: number; mean_face_area?: number; std_face_area?: number; coefficient_of_variation?: number; error?: string }
  }
}

export type MeshScoreResponse = { ok: true; score: MeshQualityV1 } | { ok: false; error: string }

// ---------- auto-validate ----------

export type AutoValidateV1 = {
  ok: true
  schema: 'aurora.auto_validate.v1'
  mesh_path: string
  prompt: string
  current_pipeline: ThreeDPipelineCurrent
  extraction: {
    kind: ThreeDSubjectKind
    confidence: number
    matched_pattern: string | null
    alternatives: string[]
  }
  score: {
    overall_score: number
    retry_recommended: boolean
    failed_axes: string[]
    retry_reasons: string[]
    axes: Record<string, number>
  }
  next_action: {
    action: 'retry_pipeline' | 'accept'
    next_pipeline: ThreeDPipelineNext
    reason: string
  }
}

export type AutoValidateResponse = { ok: true; validation: AutoValidateV1 } | { ok: false; error: string }

// ---------- color-diagnostic ----------

export type ColorDiagnosticV1 = {
  ok: true
  schema: 'aurora.color_diagnostic.v1'
  reference: { path: string; type: 'image'; unique_colors: number; variance: number; palette_top6?: { rgb_quantized: number[]; share: number }[] }
  mesh: { path: string; type: 'mesh'; unique_colors: number; variance: number; vertex_count?: number; palette_top6?: { rgb_quantized: number[]; share: number }[] }
  post_mesh: { path: string; type: 'mesh'; unique_colors: number; variance: number } | null
  color_loss_ratio_ref_to_mesh: number
  stage_lost: 'hunyuan3d' | 'post_process' | 'none'
  suggestions: string[]
}

export type ColorDiagnosticResponse = { ok: true; diagnostic: ColorDiagnosticV1 } | { ok: false; error: string }

// ---------- bake-colors ----------

export type ColorBakeV1 = {
  ok: true
  schema: 'aurora.color_bake.v1'
  input_mesh: string
  reference: string
  output_mesh: string
  subject_kind: ThreeDSubjectKind
  projection_axes: { u: number; v: number; depth: number }
  vertex_count: number
  baked_unique_colors: number
  baked_variance: number
  multi_zone: boolean
  zone_breakdown: { front: number; side: number; back: number } | null
}

export type BakeColorsResponse = { ok: true; bake: ColorBakeV1 } | { ok: false; error: string }

// ---------- mesh-sharpen ----------

export type MeshSharpenV1 = {
  ok: true
  schema: 'aurora.mesh_sharpen.v1'
  input_mesh: string
  output_mesh: string
  subject_kind: ThreeDSubjectKind
  vertex_count: number
  face_count: number
  smooth_iters: number
  smooth_lambda: number
  reshape_features: boolean
  color_smoothed: boolean
}

export type MeshSharpenResponse = { ok: true; sharpen: MeshSharpenV1 } | { ok: false; error: string }

// ---------- auto-rescue ----------

export type AutoRescueV1 = {
  ok: true
  schema: 'aurora.auto_rescue.v1'
  input_mesh: string
  reference: string
  prompt: string
  extraction: AutoValidateV1['extraction']
  final_mesh: string
  initial_score: number
  final_score: number
  score_delta: number
  final_failed_axes: string[]
  audit_trail: Array<{
    stage: string
    ok?: boolean
    mesh?: string
    overall_score?: number
    failed_axes?: string[]
    [k: string]: unknown
  }>
}

export type AutoRescueResponse = { ok: true; rescue: AutoRescueV1 } | { ok: false; error: string }

// ---------- mesh-compare ----------

export type MeshCompareV1 = {
  ok: true
  schema: 'aurora.mesh_compare.v1'
  subject_kind: ThreeDSubjectKind
  left: { path: string; overall_score: number; failed_axes: string[] }
  right: { path: string; overall_score: number; failed_axes: string[] }
  overall_delta: number
  axis_deltas: Record<string, { left: number; right: number; delta: number }>
  winner: 'left' | 'right' | 'tie'
}

export type MeshCompareResponse = { ok: true; comparison: MeshCompareV1 } | { ok: false; error: string }

// ---------- viewer-html ----------

export type ViewerV1 = {
  ok: true
  schema: 'aurora.viewer.v1'
  mesh: string
  output_html: string
  mesh_url: string
  size_bytes: number
}

export type ViewerHtmlResponse = { ok: true; viewer: ViewerV1 } | { ok: false; error: string }

// ---------- run-pipeline ----------

export type PipelineV1 = {
  ok: true
  schema: 'aurora.pipeline.v1'
  run_id: string
  prompt: string
  kind: ThreeDSubjectKind
  multi_view: boolean
  motion_prompt: string | null
  rigged_mesh: string | null
  front_reference: string
  raw_mesh: string
  final_mesh: string
  initial_score: number
  final_score: number
  score_delta: number
  elapsed_s: number
  audit_trail: Array<Record<string, unknown>>
}

export type RunPipelineResponse = { ok: true; pipeline: PipelineV1 } | { ok: false; error: string }

export type RunPipelineOptions = {
  motionPrompt?: string
  multiView?: boolean
  force?: boolean
  purpose?: string
  subjectKind?: ThreeDSubjectKind
  images?: string[]
}

// ---------- 3d-regression-suite ----------

export type ThreeDRegressionSuiteOptions = {
  caseIds?: string[]
  fixtureSmoke?: boolean
  liveReference?: boolean
  strictMesh?: boolean
  meshMap?: Record<string, string>
}

export type ThreeDRegressionCheck = {
  name: string
  ok: boolean
  expected?: unknown
  actual?: unknown
  severity?: 'error' | 'warning' | string
}

export type ThreeDRegressionCaseV1 = {
  id: string
  title: string
  prompt: string
  purpose: string
  subject_kind: string
  motion_readiness: string
  motion_prompt: string | null
  routing: Record<string, unknown>
  route_checks: ThreeDRegressionCheck[]
  contract_checks: ThreeDRegressionCheck[]
  reference_policy: Record<string, unknown>
  reference_search: Record<string, unknown>
  mesh_audit: Record<string, unknown>
  ok: boolean
}

export type ThreeDRegressionSuiteV1 = {
  ok: boolean
  schema: 'aurora.3d.regression_suite.v1'
  run_id: string
  generated_at: string
  output_dir: string
  fixture_smoke: boolean
  live_reference: boolean
  strict_mesh: boolean
  case_count: number
  cases: ThreeDRegressionCaseV1[]
  summary: {
    failed_case_ids: string[]
    skipped_mesh_case_ids: string[]
    deterministic_contract: string
  }
}

export type ThreeDRegressionSuiteResponse =
  | { ok: true; suite: ThreeDRegressionSuiteV1; returncode?: number }
  | { ok: false; error: string }

// ---------- motion-parity ----------

export type MotionParityResponse = {
  ok: boolean
  returncode: number
  summary: string
  stderr_tail?: string
}

// ---------- score-history ----------

export type ScoreEventV1 = {
  schema: 'aurora.score_event.v1'
  ts: string
  run_id: string
  mesh_path: string
  subject_kind: string
  stage: string
  overall_score: number
  failed_axes: string[]
  axis_scores: Record<string, number>
}

export type ScoreHistoryRunSummary = {
  run_id: string
  subject_kind: string | null
  initial_score: number | null
  final_score: number | null
  score_delta: number
  stages: string[]
  events_count: number
  last_ts: string | null
}

export type ScoreTrendV1 = {
  schema: 'aurora.score_trend.v1'
  total_events: number
  total_runs: number
  promoted_runs: number
  promote_rate: number
  mean_delta: number
  best_delta: number
  worst_delta: number
  axis_lifts: Record<string, number>
  kind_breakdown: Record<string, number>
  last_ts: string | null
}

export type ScoreHistoryResponse =
  | { ok: true; history: { top: ScoreHistoryRunSummary[] } }
  | { ok: true; history: { events: ScoreEventV1[] } }
  | { ok: true; history: ScoreTrendV1 }
  | { ok: false; error: string }

// ---------- agent registry (list / single) ----------

export type AgentListV1 = {
  ok: true
  schema_version: string
  leads: Record<string, { sub_agents?: string[]; delegates_to?: string[]; consumed_by?: string[] }>
  crosscut: string[]
  descriptions: Record<string, string>
  agent_count: number
}

export type AgentDetailV1 = {
  ok: true
  name: string
  description: string
  model: string
  color: string
  body: string
}

export type AgentListResponse = AgentListV1 | { ok: false; error: string }
export type AgentDetailResponse = AgentDetailV1 | { ok: false; error: string }

// ---------- agent metrics ----------

export type AgentMetricsLead = {
  count: number
  done: number
  blocked: number
  in_progress: number
  avg_duration_s: number | null
  max_duration_s: number | null
  min_duration_s: number | null
  last_finished_at: string | null
  last_status: string | null
  last_verdict: string | null
}

export type AgentMetricsV1 = {
  schema: 'aurora.metrics.v1'
  generated_at: string
  total_dispatches: number
  global_done: number
  global_blocked: number
  global_success_rate: number | null
  leads: Record<string, AgentMetricsLead>
}

export type AgentMetricsResponse =
  | { ok: true; metrics: AgentMetricsV1 }
  | { ok: false; error: string }

// ---------- tracker query (dispatches) ----------

export type DispatchEntry = {
  id?: string
  lead?: string
  brief?: string
  status?: 'in_progress' | 'done' | 'blocked' | string
  started_at?: string
  finished_at?: string | null
  verdict?: string | null
  files_touched?: string[]
  metadata?: {
    run_id?: string
    kind?: string
    score_delta?: number
    initial_score?: number
    final_score?: number
    elapsed_s?: number
    [k: string]: unknown
  }
}

export type DispatchQueryV1 = {
  schema: 'aurora.tracker_query.v1'
  generated_at: string
  filters: {
    run_id: string | null
    lead: string | null
    status: string | null
    since: string | null
    limit: number | null
  }
  match_count: number
  tasks: DispatchEntry[]
}

export type DispatchQueryResponse =
  | { ok: true; query: DispatchQueryV1 }
  | { ok: false; error: string }

// ---------- agent coverage ----------

export type AgentCoverageRow = {
  name: string
  role: 'lead' | 'sub' | 'crosscut' | 'orchestrator' | 'unknown'
  parent_lead: string
  dispatch_count: number
  last_dispatch_at: string | null
}

export type AgentCoverageV1 = {
  schema: 'aurora.coverage.v1'
  generated_at: string
  total_declared: number
  total_dispatched: number
  total_dead: number
  coverage_pct: number
  by_lead: AgentCoverageRow[]
  dead: string[]
}

export type AgentCoverageResponse =
  | { ok: true; coverage: AgentCoverageV1 }
  | { ok: false; error: string }

// ---------- watchdog ----------

export type WatchdogDispatch = {
  id?: string
  lead?: string
  brief?: string
  status?: string
  started_at?: string
  finished_at?: string | null
  verdict?: string | null
  files_touched?: string[]
}

export type WatchdogV1 = {
  schema: 'aurora.watchdog.v1'
  health: TrackerHealthV1 | null
  recent_dispatches: WatchdogDispatch[]
  trend: ScoreTrendV1 | null
  top_runs: ScoreHistoryRunSummary[]
  metrics_summary: {
    total_dispatches: number
    global_success_rate: number | null
  } | null
}

export type WatchdogResponse =
  | { ok: true; watchdog: WatchdogV1 }
  | { ok: false; error: string }

// ---------- tracker-health ----------

export type StaleTaskV1 = {
  id: string
  lead: string
  started_at: string
  age_minutes: number
  brief: string
}

export type TrackerHealthV1 = {
  schema: 'aurora.tracker_health.v1'
  now: string
  stale_threshold_min: number
  in_progress_count: number
  stale_count: number
  stale_tasks: StaleTaskV1[]
  ok: boolean
}

export type TrackerHealthResponse =
  | { ok: true; health: TrackerHealthV1 }
  | { ok: false; error: string }

// ---------- run-index ----------

export type RunIndexFile = {
  name: string
  path: string
  size_bytes: number
  mtime_iso: string
  mtime: number
  role: string
  score?: { overall_score: number; retry_recommended: boolean; failed_axes: string[] } | { error: string }
}

export type RunIndexV1 = {
  ok: true
  schema: 'aurora.run_index.v1'
  directory: string
  scored: boolean
  kind_for_scoring: ThreeDSubjectKind | null
  run_count: number
  standalone_count: number
  runs: Array<{
    run_id: string
    files: RunIndexFile[]
    latest_mtime_iso: string | null
    total_size_bytes: number
    has_mesh: boolean
    has_reference: boolean
  }>
  standalones: RunIndexFile[]
}

export type RunIndexResponse = { ok: true; index: RunIndexV1 } | { ok: false; error: string }

// ---------- bridge base + helpers ----------

export type BridgeBase = string  // e.g. 'http://127.0.0.1:3001' or the tunnel URL

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>

const defaultFetch: FetchLike = (input, init) =>
  (typeof fetch !== 'undefined'
    ? fetch(input, init)
    : Promise.reject(new Error('fetch is not available in this environment')))

async function postJson<T>(
  base: BridgeBase, path: string, body: unknown, fetchImpl: FetchLike = defaultFetch,
): Promise<T> {
  const res = await fetchImpl(`${base.replace(/\/$/, '')}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = ''
    try { detail = await res.text() } catch { /* ignore */ }
    throw new Error(`POST ${path} failed: ${res.status} ${res.statusText} ${detail.slice(0, 200)}`)
  }
  return (await res.json()) as T
}

async function getJson<T>(
  base: BridgeBase, path: string, fetchImpl: FetchLike = defaultFetch,
): Promise<T> {
  const res = await fetchImpl(`${base.replace(/\/$/, '')}${path}`)
  if (!res.ok) {
    let detail = ''
    try { detail = await res.text() } catch { /* ignore */ }
    throw new Error(`GET ${path} failed: ${res.status} ${res.statusText} ${detail.slice(0, 200)}`)
  }
  return (await res.json()) as T
}

// ---------- public API ----------

export type MeshRescueClient = {
  scoreMesh(meshPath: string, kind: ThreeDSubjectKind): Promise<MeshScoreResponse>
  autoValidate(meshPath: string, prompt: string, pipeline?: ThreeDPipelineCurrent): Promise<AutoValidateResponse>
  colorDiagnostic(reference: string, mesh: string, postMesh?: string): Promise<ColorDiagnosticResponse>
  bakeColors(mesh: string, reference: string, output: string, kind: ThreeDSubjectKind, multiZone?: boolean): Promise<BakeColorsResponse>
  sharpenMesh(mesh: string, output: string, kind: ThreeDSubjectKind, opts?: { smoothIters?: number; smoothLambda?: number; noFeatures?: boolean; noColorSmooth?: boolean }): Promise<MeshSharpenResponse>
  autoRescue(mesh: string, reference: string, prompt: string, outputDir: string): Promise<AutoRescueResponse>
  compareMeshes(left: string, right: string, kind: ThreeDSubjectKind): Promise<MeshCompareResponse>
  generateViewerHtml(mesh: string, output: string, title?: string): Promise<ViewerHtmlResponse>
  runPipeline(prompt: string, runId: string, opts?: RunPipelineOptions): Promise<RunPipelineResponse>
  runRegressionSuite(opts?: ThreeDRegressionSuiteOptions): Promise<ThreeDRegressionSuiteResponse>
  motionParity(): Promise<MotionParityResponse>
  getRunIndex(opts?: { kind?: ThreeDSubjectKind; score?: boolean }): Promise<RunIndexResponse>
  scoreHistory(opts?: { runId?: string; top?: number; limit?: number; trend?: boolean }): Promise<ScoreHistoryResponse>
  getTrackerHealth(opts?: { staleMin?: number }): Promise<TrackerHealthResponse>
  getWatchdog(opts?: { staleMin?: number; recent?: number; top?: number }): Promise<WatchdogResponse>
  getAgentCoverage(): Promise<AgentCoverageResponse>
  getDispatches(opts?: {
    runId?: string
    lead?: string
    status?: 'in_progress' | 'done' | 'blocked'
    since?: string
    limit?: number
  }): Promise<DispatchQueryResponse>
  listAgents(): Promise<AgentListResponse>
  getAgent(name: string): Promise<AgentDetailResponse>
  getAgentMetrics(): Promise<AgentMetricsResponse>
}

/**
 * Build a typed client over the Aurora bridge endpoints. `base` is typically
 * `http://127.0.0.1:3001` for local development, or the active Cloudflare
 * tunnel URL in production. Pass a custom `fetch` for testing or for Tauri's
 * `tauriFetch` if cross-origin restrictions bite.
 */
export function createMeshRescueClient(base: BridgeBase, fetchImpl?: FetchLike): MeshRescueClient {
  return {
    scoreMesh: (meshPath, kind) =>
      postJson<MeshScoreResponse>(base, '/api/3d/mesh-score', { mesh_path: meshPath, kind }, fetchImpl),
    autoValidate: (meshPath, prompt, pipeline = 'hunyuan3d') =>
      postJson<AutoValidateResponse>(base, '/api/3d/auto-validate', { mesh_path: meshPath, prompt, pipeline }, fetchImpl),
    colorDiagnostic: (reference, mesh, postMesh) =>
      postJson<ColorDiagnosticResponse>(base, '/api/3d/color-diagnostic', { reference, mesh, post_mesh: postMesh ?? null }, fetchImpl),
    bakeColors: (mesh, reference, output, kind, multiZone) =>
      postJson<BakeColorsResponse>(base, '/api/3d/bake-colors', { mesh, reference, output, kind, multi_zone: multiZone ?? false }, fetchImpl),
    sharpenMesh: (mesh, output, kind, opts) =>
      postJson<MeshSharpenResponse>(base, '/api/3d/mesh-sharpen', {
        mesh, output, kind,
        ...(opts?.smoothIters !== undefined ? { smooth_iters: opts.smoothIters } : {}),
        ...(opts?.smoothLambda !== undefined ? { smooth_lambda: opts.smoothLambda } : {}),
        ...(opts?.noFeatures ? { no_features: true } : {}),
        ...(opts?.noColorSmooth ? { no_color_smooth: true } : {}),
      }, fetchImpl),
    autoRescue: (mesh, reference, prompt, outputDir) =>
      postJson<AutoRescueResponse>(base, '/api/3d/auto-rescue', { mesh, reference, prompt, output_dir: outputDir }, fetchImpl),
    compareMeshes: (left, right, kind) =>
      postJson<MeshCompareResponse>(base, '/api/3d/mesh-compare', { left, right, kind }, fetchImpl),
    generateViewerHtml: (mesh, output, title) =>
      postJson<ViewerHtmlResponse>(base, '/api/3d/viewer-html', { mesh, output, ...(title ? { title } : {}) }, fetchImpl),
    runPipeline: (prompt, runId, opts) =>
      postJson<RunPipelineResponse>(base, '/api/3d/run-pipeline', {
        prompt, run_id: runId,
        ...(opts?.motionPrompt ? { motion_prompt: opts.motionPrompt } : {}),
        ...(typeof opts?.multiView === 'boolean' ? { multi_view: opts.multiView } : {}),
        ...(opts?.purpose ? { purpose: opts.purpose } : {}),
        ...(opts?.subjectKind ? { subject_kind: opts.subjectKind } : {}),
        ...(opts?.images?.length ? { images: opts.images } : {}),
        ...(opts?.force ? { force: true } : {}),
      }, fetchImpl),
    runRegressionSuite: (opts) =>
      postJson<ThreeDRegressionSuiteResponse>(base, '/api/3d/regression-suite', {
        ...(opts?.caseIds ? { case_ids: opts.caseIds } : {}),
        fixture_smoke: opts?.fixtureSmoke ?? false,
        live_reference: opts?.liveReference ?? false,
        strict_mesh: opts?.strictMesh ?? false,
        mesh_map: opts?.meshMap ?? {},
      }, fetchImpl),
    motionParity: () =>
      getJson<MotionParityResponse>(base, '/api/3d/motion-parity', fetchImpl),
    getRunIndex: (opts) => {
      const params = new URLSearchParams()
      if (opts?.kind) params.set('kind', opts.kind)
      if (opts?.score) params.set('score', '1')
      const qs = params.toString() ? `?${params.toString()}` : ''
      return getJson<RunIndexResponse>(base, `/api/3d/run-index${qs}`, fetchImpl)
    },
    scoreHistory: (opts) => {
      const params = new URLSearchParams()
      if (opts?.trend) params.set('trend', '1')
      if (opts?.runId) params.set('run_id', opts.runId)
      if (typeof opts?.top === 'number') params.set('top', String(opts.top))
      if (typeof opts?.limit === 'number') params.set('limit', String(opts.limit))
      const qs = params.toString() ? `?${params.toString()}` : ''
      return getJson<ScoreHistoryResponse>(base, `/api/3d/score-history${qs}`, fetchImpl)
    },
    getTrackerHealth: (opts) => {
      const params = new URLSearchParams()
      if (typeof opts?.staleMin === 'number') params.set('stale_min', String(opts.staleMin))
      const qs = params.toString() ? `?${params.toString()}` : ''
      return getJson<TrackerHealthResponse>(base, `/api/agents/health${qs}`, fetchImpl)
    },
    getWatchdog: (opts) => {
      const params = new URLSearchParams()
      if (typeof opts?.staleMin === 'number') params.set('stale_min', String(opts.staleMin))
      if (typeof opts?.recent === 'number') params.set('recent', String(opts.recent))
      if (typeof opts?.top === 'number') params.set('top', String(opts.top))
      const qs = params.toString() ? `?${params.toString()}` : ''
      return getJson<WatchdogResponse>(base, `/api/agents/watchdog${qs}`, fetchImpl)
    },
    getAgentCoverage: () =>
      getJson<AgentCoverageResponse>(base, '/api/agents/coverage', fetchImpl),
    getDispatches: (opts) => {
      const params = new URLSearchParams()
      if (opts?.runId) params.set('run_id', opts.runId)
      if (opts?.lead) params.set('lead', opts.lead)
      if (opts?.status) params.set('status', opts.status)
      if (opts?.since) params.set('since', opts.since)
      if (typeof opts?.limit === 'number') params.set('limit', String(opts.limit))
      const qs = params.toString() ? `?${params.toString()}` : ''
      return getJson<DispatchQueryResponse>(base, `/api/agents/dispatches${qs}`, fetchImpl)
    },
    listAgents: () =>
      getJson<AgentListResponse>(base, '/api/agents/list', fetchImpl),
    getAgent: (name) =>
      getJson<AgentDetailResponse>(base, `/api/agents/${encodeURIComponent(name)}`, fetchImpl),
    getAgentMetrics: () =>
      getJson<AgentMetricsResponse>(base, '/api/agents/metrics', fetchImpl),
  }
}

// ---------- thin orchestration helper ----------

/**
 * High-level convenience: given a fresh GLB + its FLUX reference + the original
 * prompt, run the auto_rescue chain on the bridge and return the final mesh
 * path + audit. Throws if the bridge returns ok=false (caller decides UX).
 */
export async function rescueMeshAutonomous(
  client: MeshRescueClient,
  args: { mesh: string; reference: string; prompt: string; outputDir: string },
): Promise<AutoRescueV1> {
  const res = await client.autoRescue(args.mesh, args.reference, args.prompt, args.outputDir)
  if (!res.ok) {
    throw new Error(`auto_rescue failed: ${(res as { error: string }).error}`)
  }
  return res.rescue
}
