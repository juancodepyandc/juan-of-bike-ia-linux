#!/usr/bin/env node
// CLI wrapper around previewThreeDIntent() — verify the 3D routing decision
// for a prompt without running the full Hunyuan3D pipeline.
//
// Usage:
//   cd application && node --experimental-strip-types scripts/route_test.mjs "<prompt>"
//
// Output: JSON with pipeline, dreamgaussianPreferred, justifications, and the
// distilled subject classification.
//
// Why this exists: Cat 1 of the 3D /loop (boitier PC quartz fume / lotus or
// rose / obsidienne / acajou nordique) routed to default Hunyuan3D and produced
// a sub-par mesh. v78j added luxury-material detection that should now flip
// dreamgaussianPreferred=true. This CLI proves it deterministically.

import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const intentModule = pathToFileURL(
  path.resolve(__dirname, '..', 'src', 'services', 'threeDIntent.ts'),
).href

const { previewThreeDIntent } = await import(intentModule)

const prompt = process.argv.slice(2).join(' ').trim()
if (!prompt) {
  process.stderr.write('usage: route_test.mjs "<prompt>"\n')
  process.exit(2)
}

const intent = previewThreeDIntent(prompt, [])

const out = {
  prompt,
  pipeline: intent.pipelineRouting.pipeline,
  dreamgaussianPreferred: intent.pipelineRouting.dreamgaussianPreferred,
  proceduralTemplate: intent.pipelineRouting.proceduralTemplate,
  fallbackPipeline: intent.pipelineRouting.fallbackPipeline,
  blenderRequired: intent.pipelineRouting.blenderRequired,
  meshoomRequired: intent.pipelineRouting.meshoomRequired,
  classification: {
    purpose: intent.purpose,
    subjectKind: intent.subjectKind,
    systemClass: intent.systemClass,
    representationGoal: intent.representationGoal,
    referenceFraming: intent.referenceFraming,
    motionReadiness: intent.motionReadiness,
  },
  justifications: intent.pipelineRouting.justifications.map((j) => `[${j.risk}] ${j.point}`),
  validationChecks: intent.pipelineRouting.validationChecks,
  postProcessing: intent.pipelineRouting.postProcessing,
}

process.stdout.write(JSON.stringify(out, null, 2) + '\n')
