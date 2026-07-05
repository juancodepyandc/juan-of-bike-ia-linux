/**
 * v77zp — motion pipeline orchestrator (TS).
 *
 * Closes the chain of usage for the kinematics + motion-baker stack:
 *
 *   user prompt (or preset selection)
 *     → MotionDescriptor (kinematicsLibrary.ts)
 *       → SerializedMotion JSON (motionSerializer.ts)
 *         → tmpfile under outputDir (this module)
 *           → runAutoRig({...,motionJsonPath}) (blenderBridge.ts)
 *             → blender_bridge.py --motion-path
 *               → RIGGING_SCRIPT argv[8]
 *                 → motion_baker.compile_motion_payload + apply_compiled_motion
 *                   → bpy keyframes on Rigify FK bones
 *                     → export_scene.gltf with real NLA action
 *
 * Two entry points:
 *   - runAutoRigWithMotion(params, descriptor)         — caller already has a
 *     MotionDescriptor (preset selection or programmatic).
 *   - runAutoRigFromPrompt(params, userPrompt, intent) — caller has free text;
 *     this resolves it via parseCustomMotionPrompt → falls back to top-rated
 *     preset for the intent.
 */

import { serializeMotionToJson } from './motionSerializer.ts'
import type { SerializedMotion } from './motionSerializer.ts'
import {
  parseCustomMotionPrompt,
  selectKinematicPresets,
} from './kinematicsLibrary.ts'
import type {
  MotionDescriptor as KinematicMotionDescriptor,
  KinematicSubjectKind,
  KinematicSystemClass,
} from './kinematicsLibrary.ts'
// blenderBridge transitively imports React/Tauri runtime so we lazy-load it
// at call time. The pipeline's pure layer (path computation, motion
// resolution) stays loadable in node --test where Tauri/React aren't.
import type { RiggingParams, BlenderScriptResult } from './blenderBridge.ts'

// ---------------------------------------------------------------------------
//  PATH HELPERS (pure)
// ---------------------------------------------------------------------------

/**
 * Computes the conventional motion-JSON sidecar path for a given run.
 *
 * Convention: `${outputDir}/${runId}_motion.json`. The blender_bridge.py
 * reads this path verbatim — no validation logic depends on the filename
 * shape, so callers can override if needed by writing their own file and
 * passing the path directly.
 */
export function computeMotionJsonPath(outputDir: string, runId: string): string {
  if (!outputDir || !runId) {
    throw new Error('motionPipeline: outputDir and runId are required')
  }
  // Normalize to forward slashes — blender_bridge.py uses os.path so it
  // accepts either, but staying consistent makes path debugging easier.
  const dir = outputDir.replace(/\\/g, '/').replace(/\/+$/, '')
  const safeId = runId.replace(/[^a-zA-Z0-9_.-]/g, '_')
  return `${dir}/${safeId}_motion.json`
}

// ---------------------------------------------------------------------------
//  WRITE BACKEND — bridge first (web), Tauri fs fallback (desktop)
// ---------------------------------------------------------------------------

async function writeFileViaBridge(path: string, content: string): Promise<void> {
  const { getBridgeUrl } = await import('../utils/runtime')
  const url = `${getBridgeUrl()}/api/fs/write-text`
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, content }),
    signal: AbortSignal.timeout(15_000),
  })
  if (!resp.ok) {
    throw new Error(`bridge write failed: HTTP ${resp.status} ${resp.statusText}`)
  }
  const data = (await resp.json()) as { ok?: boolean; error?: string }
  if (!data.ok) throw new Error(data.error || 'bridge refused write')
}

async function writeFileViaTauri(path: string, content: string): Promise<void> {
  const { invoke } = await import('@tauri-apps/api/core')
  await invoke('fs_write_text', { path, content })
}

/**
 * Writes a serialized motion JSON to the conventional sidecar path. Tauri
 * desktop uses the native fs command; web/dev mode hits the bridge.
 */
export async function writeMotionJsonFile(
  serialized: SerializedMotion,
  outputDir: string,
  runId: string,
): Promise<string> {
  const path = computeMotionJsonPath(outputDir, runId)
  const content = JSON.stringify(serialized)

  // Prefer Tauri direct fs when running inside the desktop app; bridge is
  // the universal fallback (works in both dev and packaged web modes).
  try {
    const { isTauriRuntime } = await import('../utils/runtime')
    if (isTauriRuntime()) {
      await writeFileViaTauri(path, content)
      return path
    }
  } catch {
    // Fall through to bridge
  }
  await writeFileViaBridge(path, content)
  return path
}

// ---------------------------------------------------------------------------
//  PUBLIC ENTRY POINTS
// ---------------------------------------------------------------------------

/**
 * Bake a known MotionDescriptor onto the rig produced by runAutoRig.
 *
 * The descriptor is serialized to outputDir/runId_motion.json and the path
 * is forwarded to blender_bridge.py via --motion-path. The result preserves
 * the standard runAutoRig contract — callers downstream don't need to know
 * motion baking happened.
 */
export async function runAutoRigWithMotion(
  params: RiggingParams,
  descriptor: KinematicMotionDescriptor,
  options: { fps?: number } = {},
): Promise<BlenderScriptResult> {
  const serialized = JSON.parse(
    serializeMotionToJson(descriptor, { fps: options.fps }),
  ) as SerializedMotion
  const motionJsonPath = await writeMotionJsonFile(serialized, params.outputDir, params.runId)
  const { runAutoRig } = await import('./blenderBridge.ts')
  return runAutoRig({ ...params, motionJsonPath })
}

export type ResolvedMotionSource =
  | { ok: true; descriptor: KinematicMotionDescriptor; source: 'parsed' | 'preset' }
  | { ok: false; reason: string }

/**
 * Given a free-text prompt + an intent (subject + system), pick the right
 * MotionDescriptor:
 *   1) parseCustomMotionPrompt(prompt) wins if the prompt is a sequence
 *      ("X puis Y" / "walk then jump")
 *   2) otherwise fall back to the top-ranked preset for the intent
 *   3) returns ok:false if nothing matches — caller decides whether to
 *      proceed without motion or surface a clarifying question
 */
export function resolveMotionFromPrompt(
  prompt: string,
  intent: { subjectKind: KinematicSubjectKind; systemClass: KinematicSystemClass },
): ResolvedMotionSource {
  const parsed = parseCustomMotionPrompt(prompt)
  if (parsed) return { ok: true, descriptor: parsed, source: 'parsed' }

  const presets = selectKinematicPresets(intent)
  if (presets.length === 0) {
    return { ok: false, reason: 'no preset available for the given subject/system combination' }
  }
  return { ok: true, descriptor: presets[0], source: 'preset' }
}

/**
 * Convenience: resolve motion from prompt + intent, then bake. Falls back
 * to plain runAutoRig when no motion can be resolved (rather than failing,
 * because rigging without motion is still useful).
 */
export async function runAutoRigFromPrompt(
  params: RiggingParams,
  prompt: string,
  intent: { subjectKind: KinematicSubjectKind; systemClass: KinematicSystemClass },
  options: { fps?: number } = {},
): Promise<BlenderScriptResult & { motionResolution?: ResolvedMotionSource }> {
  const resolution = resolveMotionFromPrompt(prompt, intent)
  if (!resolution.ok) {
    const { runAutoRig } = await import('./blenderBridge.ts')
    const result = await runAutoRig(params)
    return { ...result, motionResolution: resolution }
  }
  const result = await runAutoRigWithMotion(params, resolution.descriptor, options)
  return { ...result, motionResolution: resolution }
}
