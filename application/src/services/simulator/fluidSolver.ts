import { Vector3 } from 'three'
import type { FluidConfig, SceneEntity, Vec3 } from './types.ts'

export type FluidParticle = {
  position: Vector3
  prevPosition: Vector3
  velocity: Vector3
  density: number
  pressure: number
  mass: number
  temperature: number
}

export type FluidRuntime = {
  entityId: string
  config: FluidConfig
  origin: Vec3
  particles: FluidParticle[]
  smoothingRadius: number
  restDensity: number
  color: string
}

type Cell = number[]

function hashCell(x: number, y: number, z: number): string {
  return `${x}|${y}|${z}`
}

export class FluidSolver {
  private runtimes = new Map<string, FluidRuntime>()
  private gravity = new Vector3(0, -9.81, 0)

  setGravity(g: Vec3) {
    this.gravity.set(g[0], g[1], g[2])
  }

  sync(entities: SceneEntity[]) {
    const seen = new Set<string>()
    for (const entity of entities) {
      if (entity.type !== 'fluid' || !entity.fluid) continue
      seen.add(entity.id)
      const existing = this.runtimes.get(entity.id)
      if (existing) {
        if (existing.config.preset !== entity.fluid.preset || existing.config.particleCount !== entity.fluid.particleCount) {
          this.runtimes.set(entity.id, this.makeRuntime(entity))
        } else {
          existing.config = entity.fluid
          existing.origin = [...entity.transform.position]
        }
      } else {
        this.runtimes.set(entity.id, this.makeRuntime(entity))
      }
    }
    for (const id of Array.from(this.runtimes.keys())) {
      if (!seen.has(id)) this.runtimes.delete(id)
    }
  }

  step(dt: number) {
    const subDt = Math.min(dt, 1 / 60)
    for (const runtime of this.runtimes.values()) {
      this.stepRuntime(runtime, subDt)
    }
  }

  getRuntimes(): FluidRuntime[] {
    return Array.from(this.runtimes.values())
  }

  private makeRuntime(entity: SceneEntity): FluidRuntime {
    const cfg = entity.fluid!
    const particleCount = Math.min(4096, Math.max(16, cfg.particleCount))
    const origin: Vec3 = [...entity.transform.position]
    const size = cfg.containerSize
    const particles: FluidParticle[] = []
    const perAxis = Math.cbrt(particleCount)
    const steps = Math.ceil(perAxis)
    const dx = size[0] / Math.max(1, steps)
    const dy = size[1] / Math.max(1, steps)
    const dz = size[2] / Math.max(1, steps)
    let count = 0
    for (let x = 0; x < steps && count < particleCount; x += 1) {
      for (let y = 0; y < steps && count < particleCount; y += 1) {
        for (let z = 0; z < steps && count < particleCount; z += 1) {
          const px = origin[0] - size[0] / 2 + dx * x + dx / 2
          const py = origin[1] - size[1] / 2 + dy * y + dy / 2
          const pz = origin[2] - size[2] / 2 + dz * z + dz / 2
          const pos = new Vector3(px, py, pz)
          particles.push({
            position: pos,
            prevPosition: pos.clone(),
            velocity: new Vector3(),
            density: cfg.density,
            pressure: 0,
            mass: 1,
            temperature: cfg.temperature,
          })
          count += 1
        }
      }
    }
    const smoothingRadius = Math.max(0.08, Math.min(size[0], size[1], size[2]) / Math.max(3, Math.cbrt(particleCount)))
    const color = cfg.preset === 'water' ? '#3aa4ff' : cfg.preset === 'lava' ? '#ff6a20' : cfg.preset === 'honey' ? '#ffb03a' : cfg.preset === 'smoke2d' ? '#a0a0a0' : '#5ac8ff'
    return { entityId: entity.id, config: cfg, origin, particles, smoothingRadius, restDensity: cfg.density, color }
  }

  private stepRuntime(runtime: FluidRuntime, dt: number) {
    const cfg = runtime.config
    const h = runtime.smoothingRadius
    const cellSize = h
    const grid = new Map<string, Cell>()
    for (let i = 0; i < runtime.particles.length; i += 1) {
      const p = runtime.particles[i].position
      const key = hashCell(Math.floor(p.x / cellSize), Math.floor(p.y / cellSize), Math.floor(p.z / cellSize))
      let cell = grid.get(key)
      if (!cell) {
        cell = []
        grid.set(key, cell)
      }
      cell.push(i)
    }
    const gravity = this.gravity.clone().multiplyScalar(cfg.gravity / 9.81)
    for (const particle of runtime.particles) {
      particle.prevPosition.copy(particle.position)
      particle.velocity.addScaledVector(gravity, dt)
      particle.position.addScaledVector(particle.velocity, dt)
    }
    const iterations = 3
    for (let iter = 0; iter < iterations; iter += 1) {
      for (let i = 0; i < runtime.particles.length; i += 1) {
        const a = runtime.particles[i]
        const cx = Math.floor(a.position.x / cellSize)
        const cy = Math.floor(a.position.y / cellSize)
        const cz = Math.floor(a.position.z / cellSize)
        let density = 0
        for (let dx = -1; dx <= 1; dx += 1) {
          for (let dy = -1; dy <= 1; dy += 1) {
            for (let dz = -1; dz <= 1; dz += 1) {
              const cell = grid.get(hashCell(cx + dx, cy + dy, cz + dz))
              if (!cell) continue
              for (const j of cell) {
                if (j === i) continue
                const b = runtime.particles[j]
                const delta = b.position.clone().sub(a.position)
                const distSq = delta.lengthSq()
                if (distSq < 1e-6 || distSq > h * h) continue
                const dist = Math.sqrt(distSq)
                const q = 1 - dist / h
                density += q * q
                const sep = Math.max(0, (h - dist) * 0.5 * (1 - cfg.viscosity))
                const nx = delta.divideScalar(dist)
                if (sep > 0) {
                  a.position.addScaledVector(nx, -sep * 0.5)
                  b.position.addScaledVector(nx, sep * 0.5)
                }
                const viscFactor = cfg.viscosity * 0.3
                if (viscFactor > 0) {
                  const velDiff = b.velocity.clone().sub(a.velocity).multiplyScalar(viscFactor * q * dt)
                  a.velocity.add(velDiff)
                  b.velocity.sub(velDiff)
                }
              }
            }
          }
        }
        a.density = density
      }
    }
    const surfaceT = cfg.surfaceTension
    if (surfaceT > 0) {
      for (const p of runtime.particles) {
        const center = new Vector3(runtime.origin[0], runtime.origin[1], runtime.origin[2])
        const toCenter = center.clone().sub(p.position)
        const len = toCenter.length()
        if (len > 1e-4) p.velocity.addScaledVector(toCenter.divideScalar(len), surfaceT * 0.02)
      }
    }
    for (const p of runtime.particles) {
      p.velocity.copy(p.position.clone().sub(p.prevPosition).divideScalar(dt))
      this.applyContainerBounds(p, runtime)
    }
  }

  private applyContainerBounds(particle: FluidParticle, runtime: FluidRuntime) {
    const o = runtime.origin
    const s = runtime.config.containerSize
    const damping = 0.35
    if (runtime.config.containerKind === 'sphere') {
      const r = Math.min(s[0], s[1], s[2]) / 2
      const delta = particle.position.clone().sub(new Vector3(o[0], o[1], o[2]))
      const d = delta.length()
      if (d > r) {
        delta.multiplyScalar(r / d)
        particle.position.set(o[0] + delta.x, o[1] + delta.y, o[2] + delta.z)
        particle.velocity.multiplyScalar(damping)
      }
      return
    }
    const minX = o[0] - s[0] / 2, maxX = o[0] + s[0] / 2
    const minY = o[1] - s[1] / 2, maxY = o[1] + s[1] / 2
    const minZ = o[2] - s[2] / 2, maxZ = o[2] + s[2] / 2
    if (particle.position.x < minX) { particle.position.x = minX; particle.velocity.x = -particle.velocity.x * damping }
    else if (particle.position.x > maxX) { particle.position.x = maxX; particle.velocity.x = -particle.velocity.x * damping }
    if (particle.position.y < minY) { particle.position.y = minY; particle.velocity.y = -particle.velocity.y * damping }
    else if (particle.position.y > maxY) { particle.position.y = maxY; particle.velocity.y = -particle.velocity.y * damping }
    if (particle.position.z < minZ) { particle.position.z = minZ; particle.velocity.z = -particle.velocity.z * damping }
    else if (particle.position.z > maxZ) { particle.position.z = maxZ; particle.velocity.z = -particle.velocity.z * damping }
  }
}
