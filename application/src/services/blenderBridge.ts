/**
 * Blender MCP Bridge — Pilots Blender headless or via MCP server for:
 * - Procedural modeling (mechanisms, cables, geometry nodes)
 * - Auto-rigging (Rigify / MPFB)
 * - Mesh validation (3D Print Toolbox checks)
 * - Post-generation cleanup (retopo, UV, texture bake)
 * - Animation (keyframes, drivers, constraints)
 *
 * Two modes:
 * 1. Headless CLI: blender --background --python <script.py>
 * 2. MCP server: if blender-mcp is running, uses tool calls
 */

import { runPythonScript, getWorkspacePath } from '../hooks/useTauri'

export type BlenderScriptResult = {
  ok: boolean
  outputPath?: string
  format?: 'glb' | 'fbx' | 'obj' | 'blend'
  error?: string
  validationReport?: MeshValidationReport
  animationFrames?: number
  rigBones?: number
}

export type MeshValidationReport = {
  nonManifoldEdges: number
  degenerateFaces: number
  openBoundaries: number
  selfIntersections: number
  disconnectedComponents: number
  scaleMeters: [number, number, number]
  watertight: boolean
  vertexCount: number
  faceCount: number
  issues: MeshValidationIssue[]
}

export type MeshValidationIssue = {
  severity: 'error' | 'warning' | 'info'
  check: string
  message: string
  autoFixAvailable: boolean
  fixScript?: string
}

export type ProceduralTemplate =
  | 'pulley_belt_system'
  | 'gear_train_system'
  | 'cylinder_actuator_system'
  | 'hinge_joint_system'
  | 'linkage_system'
  | 'cable_bundle_system'
  | 'strimer_plus_v2_cable'
  | 'led_strip_system'
  | 'humanoid_performer'
  | 'physics_chain_system'
  | 'humanoid_rig'
  | 'generic_cleanup'

/**
 * Optional palette override: keys are tokens of the PALETTE on the Python side
 * (`pulley`, `belt`, `gear`, `cable`, `strand`, `led`, `housing`, `frame`, `rod`, etc.)
 * or any substring of an object name. Values are CSS hex strings (`"#ff8800"`) or
 * RGB tuples (0-1 or 0-255). Forwarded to Blender via the AURORA_COLORS env var.
 */
export type ColorOverrides = Record<string, string | [number, number, number]>

export type ProceduralParams = {
  template: ProceduralTemplate
  prompt: string
  parameters: Record<string, unknown>
  outputDir: string
  runId: string
  format: 'glb' | 'fbx' | 'obj'
  /** Optional palette override respected by PBR + emission shaders + LED lights. */
  colors?: ColorOverrides
}

export type RiggingParams = {
  meshPath: string
  rigSystem: 'rigify' | 'mpfb' | 'auto'
  subjectKind: 'humanoid' | 'creature' | 'quadruped' | 'mechanical' | 'mechanism' | 'vehicle' | 'wheeled' | 'prop' | 'pendulum' | 'hanging' | 'swing' | 'product' | 'object' | 'tool'
  style: 'anime' | 'realistic'
  testAction?: string
  outputDir: string
  runId: string
  /**
   * Optional physics overrides: mass, friction, restitution. Falls back to defaults if undefined.
   */
  physics?: {
    densityKgPerM3?: number
    frictionCoefficient?: number
    restitution?: number
    angularVelocityRadPerS?: number
    pendulumPeriodSeconds?: number
  }
  /**
   * Optional motion JSON path: aurora.motion.v1 file to bake into NLA action. Falls back if undefined.
   */
  motionJsonPath?: string
}

export type MeshCleanupParams = {
  meshPath: string
  checks: string[]
  autoFix: boolean
  outputDir: string
  runId: string
}

function parseJsonFromOutput(output: string): Record<string, unknown> | null {
  const lines = output.split('\n').map((l) => l.trim()).filter(Boolean)
  for (let i = lines.length - 1; i >= 0; i--) {
    try {
      return JSON.parse(lines[i]) as Record<string, unknown>
    } catch {}
  }
  return null
}

/**
 * Run a Blender Python script via the headless CLI bridge.
 */
export async function runBlenderScript(
  scriptPath: string,
  args: string[] = [],
): Promise<BlenderScriptResult> {
  try {
    const workspacePath = await getWorkspacePath()
    const bridgePath = `${workspacePath}/python-services/blender_bridge.py`
    const output = await runPythonScript(bridgePath, [
      '--script', scriptPath,
      ...args,
    ])
    const result = parseJsonFromOutput(output)
    if (result?.ok) {
      return result as unknown as BlenderScriptResult
    }
    return { ok: false, error: result?.error as string || 'Blender script failed without details.' }
  } catch (err) {
    return { ok: false, error: String(err) }
  }
}

/**
 * Run procedural modeling in Blender for mechanisms, cables, etc.
 */
export async function runProceduralModeling(params: ProceduralParams): Promise<BlenderScriptResult> {
  try {
    const workspacePath = await getWorkspacePath()
    // When colors is provided, merge it into parameters.colors (so the Python
    // template sees it per-run) AND expose it via AURORA_COLORS env var so the
    // shared PBR colorizer can respect it across every object/material.
    const parameters = params.colors
      ? { ...params.parameters, colors: params.colors, __aurora_colors: params.colors }
      : params.parameters
    const args = [
      '--mode', 'procedural',
      '--template', params.template,
      '--prompt', params.prompt,
      '--params', JSON.stringify(parameters),
      '--output-dir', params.outputDir,
      '--run-id', params.runId,
      '--format', params.format,
    ]
    if (params.colors) {
      args.push('--colors', JSON.stringify(params.colors))
    }
    const output = await runPythonScript(`${workspacePath}/python-services/blender_bridge.py`, args)
    const result = parseJsonFromOutput(output)
    if (result?.ok) {
      return result as unknown as BlenderScriptResult
    }
    return { ok: false, error: result?.error as string || 'Procedural modeling failed.' }
  } catch (err) {
    return { ok: false, error: String(err) }
  }
}

/**
 * Auto-rig a mesh in Blender (Rigify for humanoids, custom for mechanical).
 */
export async function runAutoRig(params: RiggingParams): Promise<BlenderScriptResult> {
  try {
    const workspacePath = await getWorkspacePath()
    const output = await runPythonScript(`${workspacePath}/python-services/blender_bridge.py`, [
      '--mode', 'rig',
      '--mesh', params.meshPath,
      '--rig-system', params.rigSystem,
      '--subject-kind', params.subjectKind,
      '--style', params.style,
      ...(params.testAction ? ['--test-action', params.testAction] : []),
      '--output-dir', params.outputDir,
      '--run-id', params.runId,
      ...(params.physics ? ['--physics', JSON.stringify(params.physics)] : []),
      ...(params.motionJsonPath ? ['--motion-path', params.motionJsonPath] : []),
    ])
    const result = parseJsonFromOutput(output)
    if (result?.ok) {
      return result as unknown as BlenderScriptResult
    }
    return { ok: false, error: result?.error as string || 'Auto-rig failed.' }
  } catch (err) {
    return { ok: false, error: String(err) }
  }
}

/**
 * Validate a mesh in Blender (non-manifold, degenerate faces, etc.)
 * and optionally auto-fix issues.
 */
export async function runMeshValidation(params: MeshCleanupParams): Promise<BlenderScriptResult> {
  try {
    const workspacePath = await getWorkspacePath()
    const output = await runPythonScript(`${workspacePath}/python-services/blender_bridge.py`, [
      '--mode', 'validate',
      '--mesh', params.meshPath,
      '--checks', params.checks.join(','),
      ...(params.autoFix ? ['--auto-fix'] : []),
      '--output-dir', params.outputDir,
      '--run-id', params.runId,
    ])
    const result = parseJsonFromOutput(output)
    if (result?.ok) {
      return result as unknown as BlenderScriptResult
    }
    return { ok: false, error: result?.error as string || 'Mesh validation failed.' }
  } catch (err) {
    return { ok: false, error: String(err) }
  }
}

/**
 * Mesh cleanup and post-processing in Blender.
 * Auto-fix common issues: non-manifold, degenerate faces, UV, scale.
 */
export async function runMeshCleanup(params: MeshCleanupParams): Promise<BlenderScriptResult> {
  try {
    const workspacePath = await getWorkspacePath()
    const output = await runPythonScript(`${workspacePath}/python-services/blender_bridge.py`, [
      '--mode', 'cleanup',
      '--mesh', params.meshPath,
      '--checks', params.checks.join(','),
      '--auto-fix',
      '--output-dir', params.outputDir,
      '--run-id', params.runId,
    ])
    const result = parseJsonFromOutput(output)
    if (result?.ok) {
      return result as unknown as BlenderScriptResult
    }
    return { ok: false, error: result?.error as string || 'Mesh cleanup failed.' }
  } catch (err) {
    return { ok: false, error: String(err) }
  }
}

export type MeshScreenshotResult = {
  ok: boolean
  screenshots: Array<{ view: string; path: string }>
  error?: string
}

/**
 * Render a mesh to PNG screenshot(s) using trimesh + matplotlib.
 * Used for real mesh-vs-reference fidelity comparison in the auto-correction loop.
 * This captures what the actual 3D mesh looks like, not the reference image.
 */
export async function renderMeshScreenshot({
  meshPath,
  outputPath,
  views = ['front_3q'],
}: {
  meshPath: string
  outputPath: string
  views?: string[]
}): Promise<MeshScreenshotResult> {
  try {
    const workspacePath = await getWorkspacePath()
    const output = await runPythonScript(`${workspacePath}/python-services/mesh_screenshot.py`, [
      '--mesh', meshPath,
      '--output', outputPath,
      '--views', views.join(','),
    ])
    const result = parseJsonFromOutput(output)
    if (result?.ok && Array.isArray(result.screenshots)) {
      return {
        ok: true,
        screenshots: result.screenshots as Array<{ view: string; path: string }>,
      }
    }
    return { ok: false, screenshots: [], error: result?.error as string || 'Mesh screenshot rendering failed.' }
  } catch (err) {
    return { ok: false, screenshots: [], error: String(err) }
  }
}
