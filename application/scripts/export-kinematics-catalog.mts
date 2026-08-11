/**
 * export-kinematics-catalog — TS -> Python single source of truth.
 *
 * WHY THIS EXISTS
 * ---------------
 * kinematicsLibrary.ts defines 45 motion presets, each with a real primitive
 * sequence. motion_baker.py (the compiler that actually produces Blender
 * keyframes) used to hard-code only 3 of them — walk_cycle, run_cycle, idle.
 * The other 42 fell through to _compile_custom_pose(), which emits ONE no-op
 * marker keyframe. Result: "il rugit", "il saute", "le loup marche" and every
 * creature / mechanism / vehicle preset produced an animated GLB containing
 * zero real motion, while every gate in the pipeline still reported success.
 *
 * Rather than re-typing 42 presets in Python (guaranteed drift), the baker now
 * reads the catalog this script emits. TS stays the source of truth; the JSON
 * is the contract; Python is a consumer.
 *
 * REGENERATE after ANY change to the preset tables in kinematicsLibrary.ts:
 *   node --experimental-strip-types application/scripts/export-kinematics-catalog.mts \
 *     > application/python-services/kinematics_catalog.json
 *
 * The Python side asserts the preset id set matches its parser's VERB_TO_PRESET
 * targets, so a stale catalog fails loudly instead of silently animating nothing.
 */
import {
  selectKinematicPresets,
  listAllPresetIds,
} from '../src/services/kinematicsLibrary.ts'

const SUBJECTS = [
  'character', 'creature', 'body_part', 'vehicle', 'mechanism', 'assembly', 'object',
] as const

const CLASSES = [
  'belt_drive', 'gear_train', 'cylinder_actuator', 'hinge_joint', 'linkage',
  'cable_routing', 'pc_cabling', 'electrical_harness', 'led_strip',
  'electrical_system', 'generic',
] as const

// selectKinematicPresets() is the only public accessor; sweep it over the full
// cross-product so no preset is missed, then assert coverage.
const byId = new Map<string, any>()
for (const subjectKind of SUBJECTS) {
  for (const systemClass of CLASSES) {
    for (const preset of selectKinematicPresets({ subjectKind, systemClass } as any)) {
      if (!byId.has(preset.id)) byId.set(preset.id, preset)
    }
  }
}

const expected = listAllPresetIds()
const missing = expected.filter((id) => !byId.has(id))
if (missing.length > 0) {
  console.error(`COVERAGE_GAP: presets unreachable via selectKinematicPresets: ${missing.join(', ')}`)
  process.exit(3)
}

const presets: Record<string, unknown> = {}
for (const id of expected) {
  const p = byId.get(id)
  presets[id] = {
    label: p.label,
    duration_seconds: p.duration_seconds,
    loop: Boolean(p.loop),
    primitives: p.primitives,
  }
}

console.log(JSON.stringify({
  schema: 'aurora.kinematics.catalog.v1',
  generated_from: 'application/src/services/kinematicsLibrary.ts',
  regenerate_with: 'node --experimental-strip-types application/scripts/export-kinematics-catalog.mts',
  preset_count: expected.length,
  presets,
}, null, 2))
