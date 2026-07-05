/**
 * meshPostprocess — TypeScript wrapper for python-services/mesh_postprocess.py
 *
 * The 3D pipeline already calls mesh_postprocess automatically inside the
 * Hunyuan3D and DreamGaussian Python workers (after export). This wrapper
 * lets the React UI also call it on demand, in async mode, so the user can:
 *   - retry post-processing on a previously-generated mesh with different params
 *   - apply an aggressive smoothing pass when the viewer reports artefacts
 *   - run post-process on a user-uploaded GLB without re-running Hunyuan3D
 *
 * Returns structured progress events when an onProgress callback is provided.
 */

import { runPythonScript, getWorkspacePath } from '../hooks/useTauri'

export type MeshPostprocessProfile = 'character' | 'creature' | 'product' | 'mechanical_part' | 'body_part' | 'vehicle' | 'default'
export type MeshPostprocessMotionReadiness = 'static_only' | 'poseable' | 'articulated' | 'rig_candidate'

export type MeshPostprocessParams = {
  inputPath: string
  outputPath: string
  intentPurpose?: MeshPostprocessProfile
  motionReadiness?: MeshPostprocessMotionReadiness
  /** 0.001 (very strict) → 0.02 (very aggressive). Defaults per profile. */
  floaterRatio?: number
  /** Total Taubin smoothing iterations. Higher = smoother but more shrink. */
  smoothIterations?: number
  /** Cap on faces after decimation. Lower = lighter mesh. */
  targetFaces?: number
  disableFillHoles?: boolean
  subdivide?: boolean
  /**
   * v81: scale the exported mesh so its largest extent (or the chosen axis)
   * matches this size in meters. Set when the user prompt mentions a real-
   * world dimension like "30cm" or "1m" — the mesh ships at the requested
   * size so downstream rigging (pendulum period, vehicle wheel radius) uses
   * physically correct units.
   */
  targetDimensionMeters?: number
  targetDimensionAxis?: 'max' | 'x' | 'y' | 'z'
  /**
   * v77zi: bilateral symmetry enforcement on the YZ plane. Recommended for
   * character / creature / body_part subjects where Hunyuan3D often outputs
   * subtle left-right drift that Meshy automatically averages out.
   */
  enforceSymmetry?: boolean
  /** 0.5 perfect symmetric mean, 0.55 default, 0.7 light correction only. */
  symmetryBlend?: number
  onProgress?: (event: { stage: string; detail: string }) => void
}

/**
 * v81: parse a real-world dimension hint from a free-text prompt. Returns
 * meters + which axis (height = z, length = max, depth = y) when a clear
 * number+unit signal appears. Examples:
 *   "epee de 1m20" -> 1.2 max
 *   "lustre 80cm de haut" -> 0.8 z
 *   "rouleau 50mm" -> 0.05 max
 *   "vase 30 centimetres" -> 0.3 max
 * Returns null when nothing parseable is found.
 */
export function parsePromptDimension(prompt: string): { meters: number; axis: 'max' | 'x' | 'y' | 'z' } | null {
  if (!prompt) return null
  const lower = prompt.toLowerCase()
  // Capture: number (with optional decimal or m+cm combo), unit
  const re = /(\d+)\s*(?:[.,]\s*(\d+))?\s*(m\b|metre|meter|cm|centimetre|centimeter|mm|millimetre|millimeter)/i
  const matches = Array.from(lower.matchAll(new RegExp(re, 'gi')))
  if (matches.length === 0) return null
  // Prefer the most specific "X m Ycm" combo (height for swords/staves) when
  // present; otherwise pick the first match.
  const first = matches[0]
  const intPart = Number(first[1])
  const decPart = first[2] ? Number(first[2]) / 10 ** first[2].length : 0
  const unit = first[3].toLowerCase()
  let value = intPart + decPart
  if (unit.startsWith('mm') || unit.startsWith('millim')) value = value / 1000
  else if (unit.startsWith('cm') || unit.startsWith('centim')) value = value / 100
  // m / metre / meter -> already meters
  if (value <= 0 || value > 100) return null
  // Axis hint: "haut" / "tall" / "high" -> z, "long" -> max, "large" -> x
  let axis: 'max' | 'x' | 'y' | 'z' = 'max'
  if (/\b(haut|hauteur|tall|height|debout|stand)\b/i.test(prompt)) axis = 'z'
  else if (/\b(large|largeur|width|wide)\b/i.test(prompt)) axis = 'x'
  else if (/\b(profond|profondeur|depth|deep)\b/i.test(prompt)) axis = 'y'
  return { meters: value, axis }
}

export type MeshPostprocessResult = {
  ok: boolean
  outputPath?: string
  engine?: 'pymeshlab' | 'trimesh'
  beforeFaces?: number
  afterFaces?: number
  beforeVerts?: number
  afterVerts?: number
  droppedFloaters?: number
  error?: string
}

function parseLastJsonLine(output: string): Record<string, unknown> | null {
  const lines = output.split('\n').map((line) => line.trim()).filter(Boolean)
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    try {
      return JSON.parse(lines[index]) as Record<string, unknown>
    } catch {
      // try next
    }
  }
  return null
}

function parseProgressLines(output: string, onProgress?: MeshPostprocessParams['onProgress']) {
  if (!onProgress) return
  for (const line of output.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed.startsWith('PROGRESS:')) continue
    const remainder = trimmed.slice('PROGRESS:'.length)
    const splitIdx = remainder.indexOf(':')
    if (splitIdx < 0) {
      onProgress({ stage: remainder, detail: '' })
      continue
    }
    onProgress({ stage: remainder.slice(0, splitIdx), detail: remainder.slice(splitIdx + 1) })
  }
}

/**
 * Run mesh post-processing on an existing 3D mesh file.
 *
 * Best-effort: emits progress events as the Python worker logs PROGRESS:stage:detail
 * lines, then resolves with the final structured result.
 */
export async function postProcessMesh(params: MeshPostprocessParams): Promise<MeshPostprocessResult> {
  const workspace = await getWorkspacePath()
  const args: string[] = [
    '--input', params.inputPath,
    '--output', params.outputPath,
    '--intent-purpose', params.intentPurpose ?? 'default',
    '--motion-readiness', params.motionReadiness ?? 'static_only',
  ]
  if (params.floaterRatio !== undefined) args.push('--floater-ratio', String(params.floaterRatio))
  if (params.smoothIterations !== undefined) args.push('--smooth-iterations', String(params.smoothIterations))
  if (params.targetFaces !== undefined) args.push('--target-faces', String(params.targetFaces))
  if (params.disableFillHoles) args.push('--no-fill-holes')
  if (params.subdivide) args.push('--subdivide')
  if (params.targetDimensionMeters !== undefined && params.targetDimensionMeters > 0) {
    args.push('--target-dimension-meters', String(params.targetDimensionMeters))
    if (params.targetDimensionAxis) args.push('--target-dimension-axis', params.targetDimensionAxis)
  }
  if (params.enforceSymmetry) {
    args.push('--enforce-symmetry')
    if (params.symmetryBlend !== undefined) {
      args.push('--symmetry-blend', String(params.symmetryBlend))
    }
  }

  try {
    const output = await runPythonScript(`${workspace}/python-services/mesh_postprocess.py`, args)
    parseProgressLines(output, params.onProgress)
    const result = parseLastJsonLine(output) as MeshPostprocessResult | null
    if (!result) {
      return { ok: false, error: 'mesh_postprocess returned no JSON result' }
    }
    return {
      ok: Boolean(result.ok),
      outputPath: typeof result.outputPath === 'string' ? result.outputPath : params.outputPath,
      engine: result.engine,
      beforeFaces: typeof result.beforeFaces === 'number' ? result.beforeFaces : undefined,
      afterFaces: typeof result.afterFaces === 'number' ? result.afterFaces : undefined,
      beforeVerts: typeof result.beforeVerts === 'number' ? result.beforeVerts : undefined,
      afterVerts: typeof result.afterVerts === 'number' ? result.afterVerts : undefined,
      droppedFloaters: typeof result.droppedFloaters === 'number' ? result.droppedFloaters : undefined,
      error: typeof result.error === 'string' ? result.error : undefined,
    }
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : String(error) }
  }
}

/**
 * Aggressive rescue profile: extreme floater removal, heavy smoothing,
 * decimation to a low face budget. Use when the mesh has obvious artefacts
 * (spikes, floaters, dark patches) and the user wants to salvage it.
 */
export async function rescueMeshAggressively(
  inputPath: string,
  outputPath: string,
  onProgress?: MeshPostprocessParams['onProgress'],
): Promise<MeshPostprocessResult> {
  return postProcessMesh({
    inputPath,
    outputPath,
    floaterRatio: 0.015,
    smoothIterations: 28,
    targetFaces: 45_000,
    onProgress,
  })
}
