/**
 * Static wiring guard for user-visible video capabilities.
 *
 * These checks intentionally cross the UI/service/bridge boundaries. A button
 * is not considered implemented merely because a component renders it.
 */
import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(relativeUrl: string): string {
  return readFileSync(new URL(relativeUrl, import.meta.url), 'utf8')
}

const hook = source('../hooks/useVideoViewLogic.ts')
const api = source('../services/cinemaApi.ts')
const bridge = source('../../bridge_server.py')
const v1 = source('../views/AuroraV1VideoView.tsx')
const v4 = source('../views/AuroraV4VideoView.tsx')
const videoView = source('../views/VideoView.tsx')
const voicePanel = source('../components/VideoVoiceLibraryPanel.tsx')

describe('module vidéo — aucune capacité visible orpheline', () => {
  test('annuler appelle le backend et le backend expose la route', () => {
    assert.match(hook, /await cinemaCancelJob\(activeJobId\)/)
    assert.match(api, /\/api\/cinema\/cancel\/\$\{encodeURIComponent\(jobId\)\}/)
    assert.ok(bridge.includes('@app.route("/api/cinema/cancel/<job_id>"'))
  })

  test('prévisualiser les personnages lance puis surveille un vrai job', () => {
    assert.match(hook, /cinemaPreviewKeyframes\(storyboard\)/)
    assert.match(hook, /cinemaJobStatus\(spawn\.jobId\)/)
    assert.ok(bridge.includes('@app.route("/api/cinema/preview-keyframes"'))
  })

  test('les médias V1 et V4 passent par le résolveur asset unique', () => {
    assert.match(v1, /cinemaAssetUrl\(q\.keyframe_url\)/)
    assert.match(v4, /cinemaAssetUrl\(raw\)/)
    assert.doesNotMatch(v1, /\/files\/\$\{encodeURIComponent/)
    assert.doesNotMatch(v4, /\/files\/\$\{encodeURIComponent/)
  })

  test('le prompt analysé est réellement composé avant génération', () => {
    assert.match(videoView, /composeWanPrompt\(timedGenerationPrompt, cinematicAnalysis/)
    assert.match(videoView, /'--prompt',\s*finalGenerationPrompt/)
  })

  test('les boutons 8 s et 16 s traversent le segmenteur sans plafond 97 silencieux', () => {
    const generator = source('../../python-services/video_generate.py')
    const cinema = source('../../python-services/cinema/cinema_pipeline.py')
    assert.match(videoView, /const MAX_FRAMES = 97 \* 5/)
    assert.match(videoView, /'--num_frames',\s*String\(profile\.numFrames\)/)
    assert.doesNotMatch(videoView, /String\(Math\.min\(profile\.numFrames, 97\)\)/)
    assert.match(generator, /if num_frames > VIDEO_SEGMENT_MAX_FRAMES:/)
    assert.match(generator, /render_long_shot\(/)
    assert.match(cinema, /extract_sharp_tail_frame/)
    assert.match(cinema, /aucun succès partiel/)
  })

  test('la file vidéo et son état ont une route observable', () => {
    assert.match(bridge, /_queue_video_job\(/)
    assert.ok(bridge.includes('@app.route("/api/video/queue"'))
    assert.match(bridge, /_video_gpu_queue\.snapshot\(\)/)
    assert.match(bridge, /"aurora_3d_pipeline\.py" in command/)
    assert.match(bridge, /manager\.ensure_space\("hot", reservation\)/)
  })

  test('le self-test lance le pipeline réel au lieu de tester sa présence', () => {
    assert.match(bridge, /"kind": "cinema_selftest"/)
    assert.match(bridge, /args = \["--storyboard", str\(storyboard_path\), "--output", str\(output_mp4\)\]/)
    assert.match(hook, /cinemaSelftestResultFromJob\(job\)/)
  })

  test('la vérité stockage est visible et la galerie est servie', () => {
    assert.match(api, /export async function auroraStorageStatus/)
    assert.match(hook, /setStorageStatus\(await auroraStorageStatus\(\)\)/)
    assert.match(hook, /setGallery\(await videoGallery\(\)\)/)
    assert.ok(bridge.includes('@app.route("/api/storage/status"'))
    assert.ok(bridge.includes('@app.route("/api/video/gallery"'))
    assert.match(bridge, /strategy = _video_model_strategy\(\)/)
    assert.match(bridge, /strategy\["runtime"\] = \{/)
    assert.match(bridge, /result\["model_strategy"\] = strategy/)
    assert.match(v4, /model_strategy\?\.active\.generator/)
    assert.match(v4, /v\.gallery\.files\.slice/)
  })

  test('enregistrement et synthèse vocale rejoignent aussi la file GPU', () => {
    const voiceRegisterBlock = bridge.slice(
      bridge.indexOf('def voice_register():'),
      bridge.indexOf('@app.route("/api/voice/extract"'),
    )
    const voiceSynthBlock = bridge.slice(
      bridge.indexOf('def voice_synthesize():'),
      bridge.indexOf('@app.route("/api/voice/check"'),
    )
    assert.match(voiceRegisterBlock, /_queue_video_job\(job_id, str\(script\)\)/)
    assert.match(voiceSynthBlock, /_queue_video_job\(job_id, str\(script\)\)/)
    assert.doesNotMatch(voiceSynthBlock, /_run_cinema_script_sync/)
  })

  test('CosyVoice3 est prioritaire sans installation dans le venv partagé', () => {
    const voiceClone = source('../../python-services/cinema/voice_clone.py')
    const cosyAdapter = source('../../python-services/cinema/cosyvoice3_adapter.py')
    assert.match(voiceClone, /engines = \[\s*\(\s*"cosyvoice3"/)
    assert.match(voiceClone, /AURORA_COSYVOICE3_PYTHON/)
    assert.match(cosyAdapter, /from cosyvoice\.cli\.cosyvoice import AutoModel/)
    assert.doesNotMatch(cosyAdapter, /pip install|subprocess\.(?:run|Popen)/)
    assert.match(bridge, /"--prompt-text", prompt_text/)
  })

  test('la bibliothèque de voix est utilisable dans les deux vues montées', () => {
    assert.match(v1, /<VideoVoiceLibraryPanel/)
    assert.match(v4, /<VideoVoiceLibraryPanel/)
    assert.match(voicePanel, /voiceRegister\(\{/)
    assert.match(voicePanel, /transcript: transcript\.trim\(\)/)
    assert.match(voicePanel, /await cinemaJobStatus\(jobId\)/)
    assert.match(voicePanel, /reference_quality_score/)
    assert.match(voicePanel, /voiceSynthesize\(\{/)
  })

  test('le benchmark A/B impose même prompt et même seed puis revient dans l’UI', () => {
    const benchmark = source('../../python-services/cinema/video_ab_benchmark.py')
    assert.ok(bridge.includes('@app.route("/api/cinema/benchmark"'))
    assert.match(bridge, /"video_ab_benchmark\.py"/)
    assert.match(api, /export async function cinemaBenchmark/)
    assert.match(hook, /const runBenchmark = useCallback/)
    assert.match(v4, /v\.runBenchmark\(\)/)
    assert.match(benchmark, /"--force_strategy", variant/)
    assert.match(benchmark, /"selection_graded": False/)
    assert.match(benchmark, /same-prompt\/same-seed|même prompt|same seed/i)
  })
})
