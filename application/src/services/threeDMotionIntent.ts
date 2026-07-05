// ────────────────────────────────────────────────────────────────────────────
// threeDMotionIntent — LLM-driven motion-intent classifier (no hardcoded
// brand → animation map). Given a free-form prompt, it asks gemma3:12b
// (or qwen3:14b fallback) to REASON about what the subject IS in real life
// and DEDUCE which kind of motion intrinsically belongs to it.
//
// The key idea: the LLM is the expert, not us. We never write
// "if Strimer → RGB" anywhere. We just describe the 6 animation primitives
// the system can bake and let the model pick. If text-confidence < 0.85,
// the caller is expected to fall back to a VLM pass on an isometric render
// of the freshly generated mesh (Qwen3-VL).
//
// Categories returned are aligned 1:1 with the motion_baker.py compiler so
// the JSON can be piped straight to bake without translation.
//
// Schema: aurora.motion-intent.v1  (versioned for future drift)
// ────────────────────────────────────────────────────────────────────────────

import { ollamaChat } from '../hooks/useTauri'

export type MotionCategory =
  | 'led_emission'        // RGB/LED material animation, no rig (Strimer, addressable strips)
  | 'fan_pwm'             // rotation around an axis (PC fan, propeller)
  | 'oled_screen'         // image-sequence on a UV face (LiveDash, e-paper, screen)
  | 'creature_organic'    // skeletal anatomy + idle/walk/breathe (humanoid, animal, monster)
  | 'mechanical_simple'   // keyframed positions/rotations (button press, hinge, slider)
  | 'rigid_static'        // ZERO motion (raw RAM stick, passive heatsink, rock)

export type LedPattern = 'chase' | 'rainbow' | 'breathing' | 'pulse' | 'static_color'

export type ColorAnimation = {
  pattern: LedPattern
  speed_hz: number              // cycles per second (1.0 = 1Hz default)
  colors: string[]              // hex palette, e.g. ["#ff0033","#33ff33"]
  emission_strength: number     // EEVEE/Cycles emission strength multiplier
  led_count?: number            // optional, when pattern is chase
}

export type MechanicalAnimation = {
  axis: 'X' | 'Y' | 'Z'
  motion_type: 'rotation' | 'translation' | 'oscillation'
  rpm?: number                  // for rotation
  amplitude?: number            // metres for translation, degrees for oscillation
  period_s?: number             // for oscillation
}

export type ScreenContentType =
  | 'text_scroll'      // scrolling marquee text
  | 'icon_rotation'    // rotating mock icons (CPU/RAM/FAN)
  | 'system_stats'     // CPU% bar + temp + spark (LiveDash style)
  | 'mixed'            // alternates text + icon + stats every quarter
  // legacy aliases (still accepted by the baker, normalised to one of the four above)
  | 'icon_carousel' | 'temperature_dash' | 'logo_loop'

export type ScreenAnimation = {
  content_kind: ScreenContentType
  // iter5.B: explicit alias used by motion_intent_baker.py PNG-seq pipeline
  // — when both are present, content_type wins. When only content_kind is
  // present, the Python side maps logo_loop/icon_carousel→icon_rotation,
  // temperature_dash→system_stats.
  content_type?: ScreenContentType
  resolution_px: [number, number]   // e.g. [320,240] for LiveDash 2"
  frame_rate: number                // 12 fps is enough for OLED mock
  text?: string                     // when content_kind=text_scroll
}

export type CreatureAnimation = {
  base_loop: 'idle_breathing' | 'walk_cycle' | 'run_cycle' | 'hover'
  bpm?: number                  // breathing rate, beats per minute
  stride_length_m?: number
  // iter5.A: optional topology hint for the Rigify auto-rig pass.
  //   humanoid  → human_metarig (biped)
  //   quadruped → basic_quadruped_metarig
  //   serpent   → 6-bone spline chain (snakes)
  //   auto      → bbox heuristic decides
  // When omitted the Python runner heuristic picks one from the mesh bbox.
  locomotion?: 'humanoid' | 'quadruped' | 'serpent' | 'auto'
}

export type MotionIntent = {
  schema: 'aurora.motion-intent.v1'
  category: MotionCategory
  confidence: number            // 0..1 — caller decides VLM fallback at <0.85
  rationale: string             // free-text "why" — for UI debug panel
  // exactly one of the next four is present, depending on category
  color_anim?: ColorAnimation
  mechanical_anim?: MechanicalAnimation
  screen_anim?: ScreenAnimation
  creature_anim?: CreatureAnimation
  // user-typed free-text "fais clignoter en bleu toutes les 200ms"
  // is normalised by the same classifier into one of the 4 anim blocks above.
  custom_motion_text?: string
  // model id that produced the verdict (for logs / metrics)
  model: string
}

// ────────────────────────────────────────────────────────────────────────────
// System prompt — DOES NOT enumerate brands. Asks the model to act as a
// physics-aware industrial designer that knows what real objects do.
// ────────────────────────────────────────────────────────────────────────────

const SYSTEM_PROMPT = `You are a 3D animation intent classifier for a real-time Blender pipeline.
Given a description of an object or subject, you decide which ONE of six
motion primitives the system should bake. You DO NOT have a brand list — you
reason from first principles about what the object actually is and what it
does in real life.

Six categories (pick exactly one):

1. led_emission — the subject is an LED-bearing surface or cable whose
   "motion" is purely a colour pattern on its emissive material. No rig.
   Examples (do not memorise — reason): RGB cable extension, addressable
   strip, neon sign, smart bulb, status LED.

2. fan_pwm — the subject is a fan, propeller, turbine, motor rotor, or any
   blade that spins around a fixed axis at constant RPM in normal use.

3. oled_screen — the subject contains a small embedded screen (OLED,
   e-paper, IPS dashboard) which displays scrolling text or icons in normal
   use. The screen face must be UV-unwrappable.

4. creature_organic — the subject is alive: human, humanoid, animal, fantasy
   monster, robot with anatomy. Needs a skeletal rig + idle/walk/breathing
   cycle.

5. mechanical_simple — the subject has a hinge, button, slider, lever, or
   single-DoF joint that opens/closes/presses with a clear linear or rotary
   motion. NOT a fan (use fan_pwm) and NOT a creature (use creature_organic).

6. rigid_static — the subject is inert hardware whose normal state is
   stationary: passive heatsink, RAM stick without RGB, screw, bolt,
   bracket, plain enclosure, rock, statue.

Output ONLY a JSON object, no markdown, no commentary. Schema:

{
  "schema": "aurora.motion-intent.v1",
  "category": "<one of the 6 above>",
  "confidence": <0.0-1.0 — how sure you are>,
  "rationale": "<one sentence explaining your reasoning>",
  "color_anim":     { "pattern": "chase|rainbow|breathing|pulse|static_color",
                      "speed_hz": <number>, "colors": ["#hex",…],
                      "emission_strength": <number>, "led_count": <int?> },
  "mechanical_anim": { "axis": "X|Y|Z",
                       "motion_type": "rotation|translation|oscillation",
                       "rpm": <number?>, "amplitude": <number?>,
                       "period_s": <number?> },
  "screen_anim":    { "content_kind": "text_scroll|icon_carousel|temperature_dash|logo_loop",
                      "content_type": "text_scroll|icon_rotation|system_stats|mixed",
                      "resolution_px": [<w>,<h>], "frame_rate": <number>,
                      "text": "<string?>" },
  "creature_anim":  { "base_loop": "idle_breathing|walk_cycle|run_cycle|hover",
                      "bpm": <number?>, "stride_length_m": <number?>,
                      "locomotion": "humanoid|quadruped|serpent|auto" }
}

Include ONLY the *_anim block matching the category you chose. Omit the
other three. For rigid_static, include none of the four blocks.

Reasoning checklist before answering:
- Is the subject alive or articulated as a creature? → creature_organic.
- Does it spin in normal operation around a single axis? → fan_pwm.
- Does it display dynamic text/icons on an embedded screen? → oled_screen.
- Does it have integrated programmable LEDs whose colour changes? → led_emission.
- Does it have a single-DoF moving part (hinge/button/slider)? → mechanical_simple.
- Otherwise (and especially if it's plain inert hardware): rigid_static.

When you choose oled_screen, ALSO choose a content_type:
  - text_scroll    if the screen scrolls a marquee/string
  - icon_rotation  if it cycles through icons (CPU, RAM, FAN, GPU)
  - system_stats   if it shows live numbers (temp/percent/RPM) — typical for LiveDash
  - mixed          if it alternates several modes
When you choose creature_organic, ALSO choose locomotion:
  - humanoid  for biped humans / humanoid robots
  - quadruped for animals on 4 legs (dog, dragon, lion, wolf)
  - serpent   for snakes, eels, worms
  - auto      when truly unsure (the system will infer from the mesh bbox)

Named-character locomotion rule:
- A named anime/manga/game/comic character or proper-name protagonist doing
  "walk", "run", "jump", "dance" or another body action is creature_organic
  with locomotion=humanoid unless the prompt clearly says animal/quadruped/serpent.
- Never reduce "walking" to vertical bobbing: walking requires articulated
  leg/arm/pelvis motion or the pipeline must report that rigging failed.

Confidence scoring:
- 0.95+ when the description is unambiguous ("RGB strip", "fan 120mm").
- 0.85-0.94 when you're sure but the prompt is brief.
- 0.70-0.84 when there's product-name knowledge involved (you can still
  reason — e.g. "Lian Li Strimer Plus V2" is clearly a cable extension
  with addressable LEDs given the name pattern).
- below 0.70 when truly ambiguous — caller will run a VLM pass on the mesh.

Custom-motion override: if the user appends a free-text instruction like
"fais clignoter en bleu toutes les 200ms" or "rotation lente axe Y", you
MUST reflect it in the chosen *_anim block (override defaults) AND copy
the raw user text into a top-level "custom_motion_text" field.`

// ────────────────────────────────────────────────────────────────────────────
// Hardware-aware model selection (RTX 5070 Ti / 16 GB VRAM, MAX_LOADED=1)
// ────────────────────────────────────────────────────────────────────────────

export type HardwareHint = {
  vram_free_gb?: number
  prefer_speed?: boolean        // when true, pick the smallest competent model
}

function pickModel(hw?: HardwareHint): string {
  // gemma3:12b q4 ~7-8 GB, fits with one mesh-render context.
  // qwen3:14b q4 ~9 GB, also fits but slightly slower; reserve for
  // fallback when gemma response is unparseable.
  if (hw?.prefer_speed) return 'gemma3:12b'
  return 'gemma3:12b'
}

// ────────────────────────────────────────────────────────────────────────────
// Parsing & validation
// ────────────────────────────────────────────────────────────────────────────

function safeJsonExtract(text: string): unknown | null {
  if (!text) return null
  // strip <think> blocks (qwen3 reasoning models leak them sometimes)
  const cleaned = text
    .replace(/<think>[\s\S]*?<\/think>/g, '')
    .replace(/```json\s*/gi, '')
    .replace(/```/g, '')
    .trim()
  const match = cleaned.match(/\{[\s\S]*\}/)
  if (!match) return null
  try { return JSON.parse(match[0]) }
  catch { return null }
}

function isCategory(value: unknown): value is MotionCategory {
  return value === 'led_emission' || value === 'fan_pwm' || value === 'oled_screen'
    || value === 'creature_organic' || value === 'mechanical_simple' || value === 'rigid_static'
}

function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(1, n))
}

function normalizeIntent(raw: unknown, model: string): MotionIntent | null {
  if (!raw || typeof raw !== 'object') return null
  const r = raw as Record<string, unknown>
  if (!isCategory(r.category)) return null

  const intent: MotionIntent = {
    schema: 'aurora.motion-intent.v1',
    category: r.category,
    confidence: clamp01(typeof r.confidence === 'number' ? r.confidence : 0.7),
    rationale: typeof r.rationale === 'string' ? r.rationale.slice(0, 400) : '',
    model,
  }

  if (typeof r.custom_motion_text === 'string' && r.custom_motion_text.trim()) {
    intent.custom_motion_text = r.custom_motion_text.trim().slice(0, 280)
  }

  // category-specific block — pick exactly the matching one
  switch (intent.category) {
    case 'led_emission': {
      const c = r.color_anim as Record<string, unknown> | undefined
      const colors = Array.isArray(c?.colors) ? (c.colors as unknown[]).filter(x => typeof x === 'string').slice(0, 16) as string[] : ['#ff0033', '#33ccff', '#ffaa00']
      intent.color_anim = {
        pattern: (c?.pattern as LedPattern) ?? 'rainbow',
        speed_hz: typeof c?.speed_hz === 'number' ? c.speed_hz : 1.0,
        colors,
        emission_strength: typeof c?.emission_strength === 'number' ? c.emission_strength : 4.0,
        led_count: typeof c?.led_count === 'number' ? Math.round(c.led_count) : undefined,
      }
      break
    }
    case 'fan_pwm':
    case 'mechanical_simple': {
      const m = r.mechanical_anim as Record<string, unknown> | undefined
      intent.mechanical_anim = {
        axis: (m?.axis as 'X' | 'Y' | 'Z') ?? 'Z',
        motion_type: (m?.motion_type as 'rotation' | 'translation' | 'oscillation')
          ?? (intent.category === 'fan_pwm' ? 'rotation' : 'oscillation'),
        rpm: typeof m?.rpm === 'number' ? m.rpm : (intent.category === 'fan_pwm' ? 1200 : undefined),
        amplitude: typeof m?.amplitude === 'number' ? m.amplitude : undefined,
        period_s: typeof m?.period_s === 'number' ? m.period_s : undefined,
      }
      break
    }
    case 'oled_screen': {
      const s = r.screen_anim as Record<string, unknown> | undefined
      const res = Array.isArray(s?.resolution_px) && (s!.resolution_px as unknown[]).length === 2
        ? [Number((s!.resolution_px as unknown[])[0]) || 320, Number((s!.resolution_px as unknown[])[1]) || 240] as [number, number]
        : [320, 240] as [number, number]
      intent.screen_anim = {
        content_kind: (s?.content_kind as ScreenAnimation['content_kind']) ?? 'text_scroll',
        resolution_px: res,
        frame_rate: typeof s?.frame_rate === 'number' ? s.frame_rate : 12,
        text: typeof s?.text === 'string' ? s.text : undefined,
      }
      // iter5.B: pass through content_type when LLM emits it
      if (typeof s?.content_type === 'string') {
        intent.screen_anim.content_type = s.content_type as ScreenContentType
      }
      break
    }
    case 'creature_organic': {
      const cr = r.creature_anim as Record<string, unknown> | undefined
      intent.creature_anim = {
        base_loop: (cr?.base_loop as CreatureAnimation['base_loop']) ?? 'idle_breathing',
        bpm: typeof cr?.bpm === 'number' ? cr.bpm : 14,
        stride_length_m: typeof cr?.stride_length_m === 'number' ? cr.stride_length_m : undefined,
      }
      // iter5.A: pass through locomotion hint when LLM emits it
      if (typeof cr?.locomotion === 'string'
          && ['humanoid', 'quadruped', 'serpent', 'auto'].includes(cr.locomotion as string)) {
        intent.creature_anim.locomotion = cr.locomotion as CreatureAnimation['locomotion']
      }
      break
    }
    case 'rigid_static':
      // Intentionally no anim block.
      break
  }

  return intent
}

// ────────────────────────────────────────────────────────────────────────────
// Pure-deterministic fallback — used when Ollama is offline. Heuristic only,
// NOT the path we want to take in production. Marked confidence=0.0 so the
// caller knows to schedule a VLM pass.
// ────────────────────────────────────────────────────────────────────────────

export function deterministicMotionIntentFallback(prompt: string): MotionIntent {
  const p = (prompt || '').toLowerCase()
  // keep this DELIBERATELY MINIMAL — we want the LLM path, not the rules path.
  let category: MotionCategory = 'rigid_static'
  const explicitLocomotion = /\b(marche|marcher|walk|walks|walking|court|courir|run|runs|running|jog|sprint|danse|dance|dancing|saute|jump|jumping)\b/.test(p)
  const hardSurfaceMotion = /\b(fan|ventilateur|propeller|pwm|rotor|gear|engrenage|hinge|button|bouton|slider|lever|levier|switch|interrupteur|cable|strimer|led|rgb|oled|screen|display)\b/.test(p)
  if (/\b(rgb|argb|led|strimer|neon|chase|rainbow|emissive)\b/.test(p)) category = 'led_emission'
  else if (/\b(fan|ventilateur|propeller|h[eé]lice|pwm|rotor)\b/.test(p)) category = 'fan_pwm'
  else if (/\b(oled|livedash|screen|[eé]cran|display|dashboard)\b/.test(p)) category = 'oled_screen'
  else if (/\b(human|humanoid|character|personnage|monster|monstre|creature|animal|dragon|wolf|loup|anime|manga|fairy\s*tail)\b/.test(p) || (explicitLocomotion && !hardSurfaceMotion)) category = 'creature_organic'
  else if (/\b(hinge|charni[eè]re|button|bouton|slider|lever|levier|switch|interrupteur)\b/.test(p)) category = 'mechanical_simple'

  const intent: MotionIntent = {
    schema: 'aurora.motion-intent.v1',
    category,
    confidence: category === 'creature_organic' && explicitLocomotion && !hardSurfaceMotion ? 0.82 : 0.0,
    rationale: 'Ollama unreachable — deterministic regex fallback (treat as low confidence, run VLM).',
    model: 'fallback:regex',
  }
  if (category === 'led_emission') {
    intent.color_anim = { pattern: 'rainbow', speed_hz: 1.0, colors: ['#ff0044', '#44ff88', '#4488ff'], emission_strength: 4.0 }
  } else if (category === 'fan_pwm') {
    intent.mechanical_anim = { axis: 'Z', motion_type: 'rotation', rpm: 1200 }
  } else if (category === 'oled_screen') {
    intent.screen_anim = { content_kind: 'text_scroll', resolution_px: [320, 240], frame_rate: 12 }
  } else if (category === 'creature_organic') {
    const base_loop: CreatureAnimation['base_loop'] = /\b(court|courir|run|running|sprint)\b/.test(p)
      ? 'run_cycle'
      : explicitLocomotion ? 'walk_cycle' : 'idle_breathing'
    intent.creature_anim = { base_loop, bpm: base_loop === 'idle_breathing' ? 14 : 96, locomotion: 'humanoid' }
  }
  return intent
}

// ────────────────────────────────────────────────────────────────────────────
// PUBLIC API
// ────────────────────────────────────────────────────────────────────────────

export type ClassifyMotionIntentOptions = {
  customMotionText?: string                  // user-typed free-form override
  hardware?: HardwareHint
  signal?: AbortSignal
  // when true and confidence<0.85 the caller is responsible for a VLM pass
  warnLowConfidence?: boolean
}

export async function classifyMotionIntent(
  prompt: string,
  options?: ClassifyMotionIntentOptions,
): Promise<MotionIntent> {
  const trimmed = (prompt || '').trim()
  if (!trimmed) {
    return {
      schema: 'aurora.motion-intent.v1',
      category: 'rigid_static',
      confidence: 1.0,
      rationale: 'Empty prompt — defaulting to rigid_static.',
      model: 'fallback:empty',
    }
  }

  const userMessage = options?.customMotionText
    ? `${trimmed}\n\nUser custom-motion override (verbatim): "${options.customMotionText.trim()}"`
    : trimmed

  const model = pickModel(options?.hardware)

  try {
    const response = await ollamaChat(model, [
      { role: 'system', content: SYSTEM_PROMPT },
      { role: 'user', content: userMessage },
    ], 0.1, { num_ctx: 4096, signal: options?.signal })
    const text = (response?.message?.content || '').trim()
    const parsed = safeJsonExtract(text)
    const intent = normalizeIntent(parsed, model)
    if (intent) {
      // promote user override into the intent, even if the LLM forgot it
      if (options?.customMotionText && !intent.custom_motion_text) {
        intent.custom_motion_text = options.customMotionText.trim().slice(0, 280)
      }
      return intent
    }
    // first-shot parse failed — try qwen3:14b once before falling back to regex
    const response2 = await ollamaChat('qwen3:14b', [
      { role: 'system', content: SYSTEM_PROMPT },
      { role: 'user', content: userMessage },
    ], 0.1, { num_ctx: 4096, signal: options?.signal })
    const text2 = (response2?.message?.content || '').trim()
    const parsed2 = safeJsonExtract(text2)
    const intent2 = normalizeIntent(parsed2, 'qwen3:14b')
    if (intent2) {
      if (options?.customMotionText && !intent2.custom_motion_text) {
        intent2.custom_motion_text = options.customMotionText.trim().slice(0, 280)
      }
      return intent2
    }
  } catch {
    // Ollama unreachable or aborted — fall through to regex fallback.
  }

  const fb = deterministicMotionIntentFallback(trimmed)
  if (options?.customMotionText) fb.custom_motion_text = options.customMotionText.trim().slice(0, 280)
  return fb
}

// ────────────────────────────────────────────────────────────────────────────
// Re-classification helper for the UI "custom motion text" zone — the user
// types "fais clignoter en bleu toutes les 200ms"; we re-run the classifier
// with the original prompt + user text so the result stays coherent with
// what was actually generated.
// ────────────────────────────────────────────────────────────────────────────

export async function reclassifyWithCustomMotion(
  originalPrompt: string,
  customText: string,
  options?: Omit<ClassifyMotionIntentOptions, 'customMotionText'>,
): Promise<MotionIntent> {
  return classifyMotionIntent(originalPrompt, {
    ...(options || {}),
    customMotionText: customText,
  })
}
