/**
 * RigPlayer — runtime player for Character Forge outputs.
 *
 * Reads the `rig.yaml`-derived JSON (stored in AvatarEntry.path when the
 * Forge publishes) and animates the extracted PNG layers in a stacked
 * Canvas/CSS layout:
 *
 *   - static layers           → fixed PNG
 *   - blink / eye             → scale(Y, 0.2) at random intervals
 *   - float_and_contract      → scale pulses (star_eye pattern)
 *   - float_and_rotate        → slow rotation (moon_eye pattern)
 *   - rigid_swing / hair_sway → sine-wave rotation
 *   - phonemes (mouth)        → swap frame among A/O/E/M/rest by TTS
 *   - fx_triggered            → opacity pulse on mood change
 *
 * No backend dependency. Picks up animation params from `rig.anim_rules`.
 * Missing layers gracefully fall back to the reference portrait only — so
 * even a half-finished Forge produces a watchable preview.
 */
import { useEffect, useMemo, useRef, useState } from 'react'

export interface RigLayer {
  id: string
  z: number
  kind: string
  variants?: string[]
}

export interface RigPlayerData {
  /** Full Forge payload serialized into AvatarEntry.path */
  imageSrc: string
  features?: Record<string, unknown> | null
  forge?: {
    meta?: { id: string; display_name: string }
    rig?: {
      layers: RigLayer[]
      anim_rules: Record<string, Record<string, unknown>>
    }
    layers?: Array<{ layerId: string; url: string }>
    baseLayer?: string | null
  }
}

export interface RigPlayerProps {
  /** The avatar entry's path field (JSON). If it isn't a Forge avatar, we
   * just render the plain imageSrc without animation. */
  data: RigPlayerData
  /** Emotional state coming from the conversation / TTS. */
  mood?: 'idle' | 'talking' | 'excited' | 'sad' | 'thinking'
  /** Current phoneme frame when TTS is active. */
  phoneme?: 'rest' | 'A' | 'O' | 'E' | 'M'
  /** Display size in pixels. */
  size?: number
  /** Apply a subtle parallax on hover / cursor move — desktop eye-candy. */
  parallax?: boolean
}

// ---------------------------------------------------------------------------
// Per-kind animation recipes — CSS transforms and key-frames applied through
// inline `style` on a `<div>` that wraps each layer PNG.
// ---------------------------------------------------------------------------

type AnimRule = Record<string, unknown>
function getRule(rules: Record<string, AnimRule> | undefined, key: string): AnimRule | undefined {
  if (!rules) return undefined
  return rules[key]
}

export default function RigPlayer({
  data, mood = 'idle', phoneme = 'rest', size = 240, parallax = false,
}: RigPlayerProps) {
  const layers = data.forge?.layers || []
  const rigLayers = data.forge?.rig?.layers || []
  const animRules = data.forge?.rig?.anim_rules

  // Sort by z so transparent layers paint in the right order.
  const sortedLayers = useMemo(() => {
    const indexById = new Map(layers.map((l) => [l.layerId, l.url]))
    return rigLayers
      .filter((rl) => indexById.has(rl.id))
      .sort((a, b) => (a.z ?? 0) - (b.z ?? 0))
      .map((rl) => ({ ...rl, url: indexById.get(rl.id)! }))
  }, [layers, rigLayers])

  // --- Parallax (desktop only) ---
  const [parallaxOffset, setParallaxOffset] = useState({ x: 0, y: 0 })
  const wrapRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!parallax || !wrapRef.current) return
    const el = wrapRef.current
    const onMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect()
      const cx = rect.left + rect.width / 2
      const cy = rect.top + rect.height / 2
      setParallaxOffset({
        x: Math.max(-8, Math.min(8, (e.clientX - cx) / 40)),
        y: Math.max(-8, Math.min(8, (e.clientY - cy) / 40)),
      })
    }
    const onLeave = () => setParallaxOffset({ x: 0, y: 0 })
    el.addEventListener('mousemove', onMove)
    el.addEventListener('mouseleave', onLeave)
    return () => { el.removeEventListener('mousemove', onMove); el.removeEventListener('mouseleave', onLeave) }
  }, [parallax])

  // --- Mood-driven glow ---
  const moodGlow: Record<string, string> = {
    idle: '0 0 0 rgba(0,0,0,0)',
    talking: '0 0 22px rgba(255,215,107,0.4)',
    excited: '0 0 38px rgba(255,107,107,0.55)',
    sad: '0 0 22px rgba(80,120,180,0.35)',
    thinking: '0 0 22px rgba(150,200,255,0.3)',
  }

  // Render a Forge-less avatar the old way
  if (sortedLayers.length === 0) {
    return (
      <div
        ref={wrapRef}
        style={{
          width: size, height: size,
          position: 'relative', overflow: 'hidden',
          borderRadius: size / 2,
          boxShadow: moodGlow[mood],
          transition: 'box-shadow 0.3s ease',
        }}>
        <img src={data.imageSrc} alt="" style={{
          width: '100%', height: '100%', objectFit: 'cover',
          transform: parallax ? `translate(${parallaxOffset.x}px, ${parallaxOffset.y}px)` : undefined,
        }} />
      </div>
    )
  }

  // Full rigged rendering
  return (
    <div
      ref={wrapRef}
      className="rig-player"
      style={{
        width: size, height: size,
        position: 'relative', overflow: 'hidden',
        borderRadius: 18,
        background: 'transparent',
        boxShadow: moodGlow[mood],
        transition: 'box-shadow 0.3s ease',
      }}>
      {/* Base layer — the inpainted portrait with animated regions removed */}
      {data.forge?.baseLayer && (
        <img src={data.forge.baseLayer} alt="" style={{
          position: 'absolute', inset: 0, width: '100%', height: '100%',
          objectFit: 'cover', pointerEvents: 'none',
        }} />
      )}
      {/* Animated layers */}
      {sortedLayers.map((layer) => (
        <RigLayerView
          key={layer.id}
          layer={layer}
          size={size}
          mood={mood}
          phoneme={phoneme}
          animRules={animRules}
          parallaxOffset={parallax ? parallaxOffset : { x: 0, y: 0 }}
        />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Individual layer — picks its own CSS animation based on `kind`.
// ---------------------------------------------------------------------------

function RigLayerView({
  layer, size, mood, phoneme, animRules, parallaxOffset,
}: {
  layer: RigLayer & { url: string }
  size: number
  mood: RigPlayerProps['mood']
  phoneme: RigPlayerProps['phoneme']
  animRules?: Record<string, AnimRule>
  parallaxOffset: { x: number; y: number }
}) {
  const [blinkOn, setBlinkOn] = useState(false)

  // Random blink timer (for eyelid / star_contract / float_and_contract)
  useEffect(() => {
    if (layer.kind !== 'blink_eyelid' && layer.kind !== 'float_and_contract') return
    const blink = animRules?.['blink'] as { interval_ms?: [number, number] } | undefined
    const range = blink?.interval_ms || [3000, 5500]
    let t: ReturnType<typeof setTimeout>
    const schedule = () => {
      const next = range[0] + Math.random() * (range[1] - range[0])
      t = setTimeout(() => {
        setBlinkOn(true)
        setTimeout(() => setBlinkOn(false), 120)
        schedule()
      }, next)
    }
    schedule()
    return () => clearTimeout(t)
  }, [layer.kind, animRules])

  // Breath oscillation (all layers bob slightly with the body)
  const [breath, setBreath] = useState(0)
  useEffect(() => {
    let raf = 0
    const start = performance.now()
    const loop = (now: number) => {
      const t = (now - start) / 1000
      setBreath(Math.sin(t * 1.3) * 2) // ± 2 px
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [])

  // Mood-driven secondary animations
  const excitedScale = mood === 'excited' ? 1.08 : 1.0

  // Compute the transform based on kind
  let transform = ''
  const breathY = layer.kind === 'static' ? breath / 2 : breath

  if (layer.kind === 'blink_eyelid') {
    transform = `translate(${parallaxOffset.x}px, ${parallaxOffset.y + breathY}px) scaleY(${blinkOn ? 0.12 : 1})`
  } else if (layer.kind === 'float_and_contract') {
    const scale = blinkOn ? 0.3 : 1 * excitedScale
    transform = `translate(${parallaxOffset.x * 1.2}px, ${parallaxOffset.y * 1.2 + breathY}px) scale(${scale})`
  } else if (layer.kind === 'float_and_rotate') {
    const t = performance.now() / 1000
    const rot = Math.sin(t * 0.4) * 8
    transform = `translate(${parallaxOffset.x * 1.2}px, ${parallaxOffset.y * 1.2 + breathY}px) rotate(${rot}deg) scale(${excitedScale})`
  } else if (layer.kind === 'rigid_swing' || layer.kind === 'hair_sway') {
    const t = performance.now() / 1000
    const rot = Math.sin(t * 1.1) * 3
    transform = `translate(${parallaxOffset.x * 0.6}px, ${parallaxOffset.y * 0.6 + breathY}px) rotate(${rot}deg)`
  } else if (layer.kind === 'phonemes') {
    // For phonemes, we'd load separate frames per phoneme. Minimal MVP: use
    // the single layer PNG and apply a vertical scale matching the phoneme.
    const scaleY = ({ rest: 0.95, A: 1.25, O: 1.1, E: 1.05, M: 0.65 } as const)[phoneme || 'rest'] ?? 1
    transform = `translate(${parallaxOffset.x * 0.6}px, ${parallaxOffset.y * 0.6 + breathY}px) scaleY(${scaleY})`
  } else if (layer.kind === 'fx_triggered') {
    transform = `translate(${parallaxOffset.x}px, ${parallaxOffset.y + breathY}px)`
  } else {
    // static / custom fallback — still respect parallax + breath
    transform = `translate(${parallaxOffset.x * 0.5}px, ${parallaxOffset.y * 0.5 + breathY}px)`
  }

  const opacity = layer.kind === 'fx_triggered' && mood !== 'excited' ? 0 : 1

  return (
    <img
      src={layer.url}
      alt=""
      className={`rig-layer rig-layer-${layer.kind}`}
      data-layer-id={layer.id}
      style={{
        position: 'absolute', inset: 0, width: '100%', height: '100%',
        objectFit: 'cover', pointerEvents: 'none',
        transform,
        transformOrigin: 'center',
        transition: layer.kind === 'blink_eyelid' || layer.kind === 'float_and_contract'
          ? 'transform 0.06s ease'
          : layer.kind === 'phonemes' ? 'transform 0.08s ease' : 'none',
        opacity,
        zIndex: layer.z,
      }}
    />
  )
}
