/**
 * v77zn — motion serializer (pure, dep-free).
 *
 * Bridges the TS-side MotionDescriptor (kinematicsLibrary.ts) and the
 * Blender-side motion baker (python-services/motion_baker.py). Emits a
 * JSON shape both ends can agree on without sharing Python or TS types.
 *
 * Wire format (stable):
 *   {
 *     "schema": "aurora.motion.v1",
 *     "id": "character.walk_cycle",
 *     "label": "Marcher (cycle complet)",
 *     "source": "preset" | "custom",
 *     "loop": true,
 *     "fps": 24,
 *     "duration_seconds": 1.0,
 *     "frame_count": 24,
 *     "primitives": [
 *       {
 *         "kind": "gait",
 *         "target": "legs",
 *         "axis": "x",
 *         "amplitude": 30,
 *         "frequency_hz": 1.0,
 *         "duration_seconds": 1.0,
 *         "description": "..."
 *       },
 *       ...
 *     ]
 *   }
 *
 * The frame_count is precomputed so the baker doesn't have to round again.
 * fps=24 by default to match what rigify_autorig exports.
 *
 * Pure: no Tauri / React / fs deps.
 */

import type { MotionDescriptor, KinematicPrimitive } from './kinematicsLibrary.ts'

export type SerializedMotionPrimitive = {
  kind: KinematicPrimitive['kind']
  target: string | null
  axis: 'x' | 'y' | 'z' | 'auto' | null
  amplitude: number | null
  frequency_hz: number | null
  duration_seconds: number | null
  description: string | null
}

export type SerializedMotion = {
  schema: 'aurora.motion.v1'
  id: string
  label: string
  source: 'preset' | 'custom'
  loop: boolean
  fps: number
  duration_seconds: number
  frame_count: number
  primitives: SerializedMotionPrimitive[]
}

const DEFAULT_FPS = 24

function clampPositiveNumber(value: number | undefined, fallback: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return fallback
  return value
}

function nullableString(value: string | undefined | null): string | null {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed.length === 0 ? null : trimmed
}

function nullableAxis(value: KinematicPrimitive['axis']): SerializedMotionPrimitive['axis'] {
  if (value === 'x' || value === 'y' || value === 'z' || value === 'auto') return value
  return null
}

function nullableNumber(value: number | undefined | null): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  return value
}

export function serializeMotionForBlender(
  descriptor: MotionDescriptor,
  options: { fps?: number } = {},
): SerializedMotion {
  const fps = clampPositiveNumber(options.fps, DEFAULT_FPS) || DEFAULT_FPS
  const duration = clampPositiveNumber(descriptor.duration_seconds, 1.0)
  const frameCount = Math.max(1, Math.round(duration * fps))

  const primitives: SerializedMotionPrimitive[] = (descriptor.primitives ?? []).map((p) => ({
    kind: p.kind,
    target: nullableString(p.target),
    axis: nullableAxis(p.axis),
    amplitude: nullableNumber(p.amplitude),
    frequency_hz: nullableNumber(p.frequency_hz),
    duration_seconds: nullableNumber(p.duration_seconds),
    description: nullableString(p.description),
  }))

  return {
    schema: 'aurora.motion.v1',
    id: descriptor.id,
    label: descriptor.label,
    source: descriptor.source,
    loop: !!descriptor.loop,
    fps,
    duration_seconds: duration,
    frame_count: frameCount,
    primitives,
  }
}

export function serializeMotionToJson(
  descriptor: MotionDescriptor,
  options: { fps?: number; pretty?: boolean } = {},
): string {
  const payload = serializeMotionForBlender(descriptor, { fps: options.fps })
  return options.pretty ? JSON.stringify(payload, null, 2) : JSON.stringify(payload)
}
