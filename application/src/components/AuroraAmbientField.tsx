/**
 * AuroraAmbientField — faithful TS port of `_design/aurora_design_lib/ambient-fx.jsx`.
 *
 * WebGL-less Canvas2D particle field that drifts upward behind the
 * AppShell's main content. 80 particles by default (scaled by density),
 * each with depth (z = 0.3..1) controlling size + alpha, slight
 * horizontal sway via sin(t*0.0003 + phase), wrapping at edges. Tinted
 * via the source's oklchToRgb conversion (re-implemented here so the
 * file is self-contained and doesn't depend on AuroraSphereV1).
 *
 * Respects `prefers-reduced-motion` — the canvas is rendered but the
 * rAF loop is skipped, leaving a single static frame.
 */
import { useEffect, useRef } from 'react'

type Props = {
  tint?: string
  density?: number
  speed?: number
}

function oklchToRgb(input: string): [number, number, number] {
  if (typeof input === 'string' && input.startsWith('#') && (input.length === 7 || input.length === 4)) {
    const hex = input.length === 4
      ? input.slice(1).split('').map((c) => c + c).join('')
      : input.slice(1)
    return [
      parseInt(hex.slice(0, 2), 16) / 255,
      parseInt(hex.slice(2, 4), 16) / 255,
      parseInt(hex.slice(4, 6), 16) / 255,
    ]
  }
  const m = String(input).match(/oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)/)
  if (!m) return [0.7, 0.5, 0.3]
  const L = parseFloat(m[1])
  const C = parseFloat(m[2])
  const H = (parseFloat(m[3]) * Math.PI) / 180
  const a = C * Math.cos(H)
  const b = C * Math.sin(H)
  const lp = L + 0.3963377774 * a + 0.2158037573 * b
  const mp = L - 0.1055613458 * a - 0.0638541728 * b
  const sp = L - 0.0894841775 * a - 1.2914855480 * b
  const ll = lp * lp * lp
  const mm = mp * mp * mp
  const ss = sp * sp * sp
  const r = 4.0767416621 * ll - 3.3077115913 * mm + 0.2309699292 * ss
  const g = -1.2684380046 * ll + 2.6097574011 * mm - 0.3413193965 * ss
  const bl = -0.0041960863 * ll - 0.7034186147 * mm + 1.7076147010 * ss
  return [
    Math.max(0, Math.min(1, r)),
    Math.max(0, Math.min(1, g)),
    Math.max(0, Math.min(1, bl)),
  ]
}

type Particle = {
  x: number
  y: number
  z: number
  r: number
  vy: number
  vx: number
  ph: number
}

export default function AuroraAmbientField({
  tint = 'oklch(0.65 0.18 40)',
  density = 0.8,
  speed = 1,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  // v82ae : tint lives in a ref so the rAF loop reads the latest color
  // without re-running the entire useEffect on every module switch.
  // Previous version recreated particles + canvas + rAF on each tint
  // change which on aurora_v1 happens every Sidebar click — that was
  // an expensive churn during navigation.
  const tintRef = useRef(tint)
  useEffect(() => { tintRef.current = tint }, [tint])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const reduced = typeof window !== 'undefined'
      && window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches

    const t0 = performance.now()
    const N = Math.floor(80 * density)
    const parts: Particle[] = Array.from({ length: N }, () => ({
      x: Math.random(),
      y: Math.random(),
      z: Math.random() * 0.7 + 0.3,
      r: Math.random() * 1.6 + 0.3,
      vy: (Math.random() * 0.00006 + 0.00002) * speed,
      vx: (Math.random() - 0.5) * 0.00004 * speed,
      ph: Math.random() * Math.PI * 2,
    }))
    let R = 0, G = 0, B = 0
    let lastTint = ''
    const refreshTint = () => {
      const t = tintRef.current
      if (t === lastTint) return
      lastTint = t
      const rgb = oklchToRgb(t)
      R = (rgb[0] * 255) | 0
      G = (rgb[1] * 255) | 0
      B = (rgb[2] * 255) | 0
    }
    refreshTint()

    const resize = () => {
      const dpr = Math.min(2, window.devicePixelRatio || 1)
      const r = canvas.getBoundingClientRect()
      canvas.width = Math.max(2, Math.floor(r.width * dpr))
      canvas.height = Math.max(2, Math.floor(r.height * dpr))
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)

    let raf = 0
    let lastDraw = 0
    // v82ad : throttle to 30fps. The previous 60fps loop was a major
    // CPU eater (one of the user's "pas fluide" causes). 30fps is more
    // than enough for ambient drift at this opacity. ~50% CPU savings.
    const FRAME_MS = 33
    const tick = () => {
      const t = performance.now() - t0
      if (t - lastDraw >= FRAME_MS) {
        lastDraw = t
        // Pick up tint changes lazily — costs one string compare/frame
        // when nothing changed, vs the previous useEffect-restart cost.
        refreshTint()
        const w = canvas.width
        const h = canvas.height
        ctx.clearRect(0, 0, w, h)
        for (const p of parts) {
          p.y -= p.vy
          p.x += p.vx + Math.sin(t * 0.0003 + p.ph) * 0.00012
          if (p.y < -0.05) { p.y = 1.05; p.x = Math.random() }
          if (p.x < -0.05) p.x = 1.05
          if (p.x > 1.05) p.x = -0.05
          const a = 0.18 * p.z + 0.05 * Math.sin(t * 0.001 + p.ph)
          ctx.beginPath()
          ctx.arc(p.x * w, p.y * h, p.r * p.z * 1.4, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(${R},${G},${B},${Math.max(0, a)})`
          ctx.fill()
        }
      }
      if (!reduced) raf = requestAnimationFrame(tick)
    }
    tick()

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
    }
    // density + speed only — tint is read via tintRef so module
    // switches don't restart the rAF loop. (v82ae)
  }, [density, speed])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute', inset: 0,
        width: '100%', height: '100%',
        pointerEvents: 'none', zIndex: 1,
      }}
    />
  )
}
