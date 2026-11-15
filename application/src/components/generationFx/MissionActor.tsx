import { useLayoutEffect, useRef, type CSSProperties } from 'react'
import rigs from '../../assets/mission-cast/rigs.json'
import type { FxModule } from './fxBus.ts'
import type { MascotState } from './mascots.tsx'
import './missionStage.css'

export const missionCast = {
  conversation: { name: 'Lumo', asset: 'lumo' },
  image: { name: 'Prisma', asset: 'prisma' },
  '3d': { name: 'Poly', asset: 'poly' },
  code: { name: 'Forge', asset: 'forge' },
  drawing: { name: 'Sumi', asset: 'sumi' },
  voice: { name: 'Écho', asset: 'echo' },
  video: { name: 'Klap', asset: 'klap' },
  learning: { name: 'Sage', asset: 'sage' },
  cyber: { name: 'Senti', asset: 'senti' },
  business: { name: 'Sovereign', asset: 'sovereign' },
  cowork: { name: 'Navi', asset: 'navi' },
} satisfies Record<FxModule, { name: string; asset: keyof typeof rigs }>

const portraits = import.meta.glob<string>('../../assets/mission-cast/*.webp', {
  eager: true, query: '?url', import: 'default',
})

type Point = { x: number; y: number }
type Rig = (typeof rigs)[keyof typeof rigs]
const bounds = (value: number) => Math.max(0, Math.min(1, value))
const smooth = (t: number) => t * t * (3 - 2 * t)

function paintTriangle(ctx: CanvasRenderingContext2D, image: HTMLImageElement, source: Point[], posed: Point[]) {
  const [p, q, r] = source
  const [a, b, c] = posed
  const sx = q.x - p.x
  const sy = q.y - p.y
  const tx = r.x - p.x
  const ty = r.y - p.y
  const determinant = sx * ty - sy * tx
  if (Math.abs(determinant) < .01) return
  const xx = ((b.x - a.x) * ty - (c.x - a.x) * sy) / determinant
  const xy = ((c.x - a.x) * sx - (b.x - a.x) * tx) / determinant
  const yx = ((b.y - a.y) * ty - (c.y - a.y) * sy) / determinant
  const yy = ((c.y - a.y) * sx - (b.y - a.y) * tx) / determinant
  const center = { x: (a.x + b.x + c.x) / 3, y: (a.y + b.y + c.y) / 3 }
  ctx.save()
  ctx.beginPath()
  posed.forEach((point, i) => {
    const f = .55 / Math.max(1, Math.hypot(point.x - center.x, point.y - center.y))
    const x = point.x + (point.x - center.x) * f
    const y = point.y + (point.y - center.y) * f
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  ctx.closePath()
  ctx.clip()
  ctx.transform(xx, yx, xy, yy, a.x - xx * p.x - xy * p.y, a.y - yx * p.x - yy * p.y)
  ctx.drawImage(image, 0, 0)
  ctx.restore()
}

function pose(ctx: CanvasRenderingContext2D, image: HTMLImageElement, rig: Rig,
  rest: Point[], swing: number, reach: number, direction: number, toward: number) {
  const [w,h] = rig.dimensions
  const shoulder = Math.round(rig.face_protected_y)
  ctx.clearRect(0, 0, w, h)
  ctx.drawImage(image, 0, 0, w, shoulder, 0, 0, w, shoulder)
  ctx.save()
  ctx.beginPath()
  ctx.rect(0, shoulder, w, h - shoulder)
  ctx.clip()
  const articulated = rig.points.map(([x, y, armLeft, armRight, legLeft, legRight]) => {
    const hand = reach * (toward < 0 ? armRight : armLeft)
    return {
      x: x + w * (direction * (.11 * (legRight - legLeft) - .038 * (armRight - armLeft)) * swing + toward * .20 * hand),
      y: y - h * (.024 * legLeft * Math.max(0, swing) + .024 * legRight * Math.max(0, -swing) + .13 * hand),
    }
  })
  for (const face of rig.faces) paintTriangle(ctx, image, face.map(i => rest[i]), face.map(i => articulated[i]))
  ctx.restore()
}

const restPoints = Object.fromEntries(Object.entries(rigs).map(([name, rig]) => [
  name, rig.points.map(([x, y]) => ({ x, y })),
]))

export function MissionActor({ module, x, facing, gesture, cue, entrance, compact = false, label = false }: {
  module: FxModule; x: number; facing: number; gesture: number; cue?: number | string;
  entrance?: number; compact?: boolean; label?: boolean
}) {
  const member = missionCast[module]
  const rig = rigs[member.asset]
  const source = portraits[`../../assets/mission-cast/${member.asset}.webp`]
  const el = useRef<HTMLDivElement>(null)
  const picture = useRef<HTMLImageElement>(null)
  const animation = useRef<HTMLCanvasElement>(null)
  const location = useRef(entrance ?? x)
  useLayoutEffect(() => {
    const actor = el.current
    const image = picture.current
    const canvas = animation.current
    if (!actor || !image || !canvas) return
    const from = location.current
    const distance = x - from
    const direction = Math.sign(distance) || facing
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced || (!distance && !gesture)) {
      location.current = x
      actor.style.left = `${x * 100}%`
      actor.style.setProperty('--actor-step', '0px')
      actor.dataset.posed = 'false'
      return
    }
    const travel = Math.abs(distance) < .01 ? 0 : 440 + 1460 * Math.abs(distance)
    const gesturing = gesture > 0 ? 710 : 0
    const ctx = canvas.getContext('2d')
    let frame = 0
    let start: number | undefined
    let paintedAt = -Infinity
    const animate = (now: number) => {
      start ??= now
      const age = now - start
      const stepping = travel ? bounds(age / travel) : 1
      const action = gesturing ? bounds((age - travel) / gesturing) : 1
      const span = Math.max(1, Math.round(Math.abs(distance) * 7))
      const swing = Math.sin(stepping * Math.PI * 2 * span) * Math.sin(stepping * Math.PI)
      const reach = Math.sin(action * Math.PI) * gesture
      location.current = from + distance * smooth(stepping)
      actor.style.left = `${location.current * 100}%`
      actor.style.setProperty('--actor-step', `${-4 * Math.abs(swing)}px`)
      const moving = stepping < 1 || action < 1
      if (moving && ctx && image.complete && image.naturalWidth && now - paintedAt >= 32) {
        pose(ctx, image, rig, restPoints[member.asset], swing, reach, direction, facing)
        actor.dataset.posed = 'true'
        paintedAt = now
      }
      if (moving) frame = requestAnimationFrame(animate)
      else actor.dataset.posed = 'false'
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [cue, facing, gesture, member.asset, rig, x])
  return <div className={`mission-actor${compact ? ' mission-actor--compact' : ''}`} ref={el}
    aria-hidden={!label} style={{ left: `${location.current * 100}%`, '--actor-ratio': rig.dimensions[0]/rig.dimensions[1] } as CSSProperties}>
    <div className="mission-actor__body">
      <img ref={picture} src={source} alt="" decoding="async" draggable={false}/>
      <canvas ref={animation} width={rig.dimensions[0]} height={rig.dimensions[1]}/>
    </div>
    {label && <span>{member.name}</span>}
  </div>
}

export function MissionActorTrack({ module, state, phase, narrow, embedded = false, tool }: {
  module: FxModule; state: MascotState; phase: number; narrow: boolean; embedded?: boolean; tool?: Point | null
}) {
  const working = state === 'working' || state === 'checking'
  const inspecting = embedded && module === '3d' && working && phase >= 2
  const drawingSide = tool && working ? (tool.x < .55 ? .73 : .29) : null
  const x = drawingSide ?? (embedded
    ? inspecting ? .13 : working ? .81 : .91
    : working ? (narrow ? .85 : .76) : .91)
  const gesture = working ? (state === 'checking' ? .55 : .8) : 0
  return <div aria-hidden="true" className={`mission-actor-track${embedded ? ' mission-actor-track--embedded' : ''}`}
    data-module={module} data-phase={phase} data-state={state}>
    <MissionActor module={module} x={x} facing={x < .5 ? 1 : -1} gesture={gesture}
      cue={phase} entrance={.91} compact={narrow}/>
  </div>
}
