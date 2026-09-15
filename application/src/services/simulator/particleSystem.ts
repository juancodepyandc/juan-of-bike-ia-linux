import { Color, Vector3 } from 'three'
import type { ParticleEmitterConfig, SceneEntity, Vec3 } from './types.ts'

export type Particle = {
  position: Vector3
  velocity: Vector3
  age: number
  lifetime: number
  size: number
  rotation: number
  rotationSpeed: number
  color: Color
  alpha: number
  active: boolean
}

export type EmitterRuntime = {
  id: string
  entityId: string
  config: ParticleEmitterConfig
  origin: Vector3
  direction: Vector3
  particles: Particle[]
  emissionRemainder: number
  startColorRef: Color
  endColorRef: Color
}

export type TurbulenceField = {
  strength: number
  scale: number
  seed: number
}

const DEFAULT_TURBULENCE: TurbulenceField = { strength: 1, scale: 1.2, seed: 1234 }

function hash3(x: number, y: number, z: number, seed: number) {
  const h = Math.sin(x * 127.1 + y * 311.7 + z * 74.7 + seed * 0.137) * 43758.5453
  return h - Math.floor(h)
}

function curlNoise(p: Vector3, field: TurbulenceField): Vector3 {
  const e = 0.12 * field.scale
  const s = field.seed
  const dx = hash3(p.x + e, p.y, p.z, s) - hash3(p.x - e, p.y, p.z, s)
  const dy = hash3(p.x, p.y + e, p.z, s + 1) - hash3(p.x, p.y - e, p.z, s + 1)
  const dz = hash3(p.x, p.y, p.z + e, s + 2) - hash3(p.x, p.y, p.z - e, s + 2)
  return new Vector3(dy - dz, dz - dx, dx - dy).multiplyScalar(field.strength)
}

export class ParticleSystem {
  private emitters = new Map<string, EmitterRuntime>()
  private turbulence: TurbulenceField = DEFAULT_TURBULENCE
  private globalGravity = new Vector3(0, -9.81, 0)
  private attractors: Array<{ position: Vector3; strength: number; radius: number }> = []

  setGravity(g: Vec3) {
    this.globalGravity.set(g[0], g[1], g[2])
  }

  setTurbulence(field: Partial<TurbulenceField>) {
    this.turbulence = { ...this.turbulence, ...field }
  }

  setAttractors(list: Array<{ position: Vec3; strength: number; radius: number }>) {
    this.attractors = list.map((a) => ({ position: new Vector3(a.position[0], a.position[1], a.position[2]), strength: a.strength, radius: a.radius }))
  }

  sync(entities: SceneEntity[]) {
    const seen = new Set<string>()
    for (const entity of entities) {
      if (entity.type !== 'emitter' || !entity.emitter) continue
      seen.add(entity.id)
      const existing = this.emitters.get(entity.id)
      const origin = new Vector3(...entity.transform.position)
      const rot = entity.transform.rotation
      const direction = new Vector3(0, 1, 0).applyEuler({ x: rot[0], y: rot[1], z: rot[2], order: 'XYZ' } as unknown as never)
      if (existing) {
        existing.config = entity.emitter
        existing.origin.copy(origin)
        existing.direction.copy(direction)
        existing.startColorRef = new Color(entity.emitter.startColor)
        existing.endColorRef = new Color(entity.emitter.endColor)
      } else {
        const runtime: EmitterRuntime = {
          id: entity.id,
          entityId: entity.id,
          config: entity.emitter,
          origin,
          direction,
          particles: [],
          emissionRemainder: 0,
          startColorRef: new Color(entity.emitter.startColor),
          endColorRef: new Color(entity.emitter.endColor),
        }
        this.emitters.set(entity.id, runtime)
      }
    }
    for (const id of Array.from(this.emitters.keys())) {
      if (!seen.has(id)) this.emitters.delete(id)
    }
  }

  step(dt: number) {
    for (const runtime of this.emitters.values()) {
      this.stepRuntime(runtime, dt)
    }
  }

  getEmitters(): EmitterRuntime[] {
    return Array.from(this.emitters.values())
  }

  emitBurst(entityId: string, count: number) {
    const runtime = this.emitters.get(entityId)
    if (!runtime) return
    for (let i = 0; i < count; i += 1) this.spawnParticle(runtime)
  }

  private stepRuntime(runtime: EmitterRuntime, dt: number) {
    const cfg = runtime.config
    runtime.emissionRemainder += cfg.rate * dt
    while (runtime.emissionRemainder >= 1 && runtime.particles.length < cfg.maxParticles) {
      runtime.emissionRemainder -= 1
      this.spawnParticle(runtime)
    }
    for (const particle of runtime.particles) {
      if (!particle.active) continue
      particle.age += dt
      const life = particle.age / particle.lifetime
      if (life >= 1) { particle.active = false; continue }
      const acc = this.globalGravity.clone().multiplyScalar(cfg.gravityInfluence)
      if (cfg.turbulence > 0) {
        const curl = curlNoise(particle.position, { ...this.turbulence, strength: cfg.turbulence })
        acc.add(curl)
      }
      for (const a of this.attractors) {
        const delta = a.position.clone().sub(particle.position)
        const d = delta.length()
        if (d > 0.01 && d < a.radius) {
          const influence = (1 - d / a.radius) * a.strength
          acc.addScaledVector(delta.divideScalar(d), influence)
        }
      }
      particle.velocity.addScaledVector(acc, dt)
      const dragFactor = Math.pow(1 - cfg.drag, dt * 60)
      particle.velocity.multiplyScalar(dragFactor)
      particle.position.addScaledVector(particle.velocity, dt)
      const sizeT = cfg.startSize + (cfg.endSize - cfg.startSize) * life
      particle.size = sizeT
      particle.rotation += particle.rotationSpeed * dt
      const alphaT = cfg.startAlpha + (cfg.endAlpha - cfg.startAlpha) * life
      particle.alpha = alphaT
      particle.color.copy(runtime.startColorRef).lerp(runtime.endColorRef, life)
    }
    runtime.particles = runtime.particles.filter((p) => p.active)
  }

  private spawnParticle(runtime: EmitterRuntime) {
    const cfg = runtime.config
    const jitter = new Vector3((Math.random() - 0.5) * cfg.spread, (Math.random() - 0.5) * cfg.spread, (Math.random() - 0.5) * cfg.spread)
    const velocity = runtime.direction.clone().multiplyScalar(cfg.initialSpeed).add(jitter)
    const particle: Particle = {
      position: runtime.origin.clone().add(new Vector3((Math.random() - 0.5) * 0.05, (Math.random() - 0.5) * 0.05, (Math.random() - 0.5) * 0.05)),
      velocity,
      age: 0,
      lifetime: cfg.lifetime * (0.8 + Math.random() * 0.4),
      size: cfg.startSize,
      rotation: Math.random() * Math.PI * 2,
      rotationSpeed: cfg.rotationSpeed * (Math.random() - 0.5) * 2,
      color: runtime.startColorRef.clone(),
      alpha: cfg.startAlpha,
      active: true,
    }
    runtime.particles.push(particle)
  }
}
