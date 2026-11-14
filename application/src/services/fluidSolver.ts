import { Vector3 } from 'three'
import type { FluidConfig, SceneEntity, Vec3 } from './simulator/types.ts'

export type FluidParticle = {
  position: Vector3
  prevPosition: Vector3
  velocity: Vector3
  density: number
  pressure: number
  mass: number
  temperature: number
  lambda?: number
  surfaceNormal?: Vector3
  curvature?: number
  densityError?: number
}

export type FluidDiagnostics = {
  averageDensity: number
  maxDensityError: number
  averagePressure: number
  maxPressure: number
  kineticEnergy: number
  potentialEnergy: number
  totalEnergy: number
  linearMomentum: Vec3
  cflSubsteps: number
  courantNumber: number
  incompressibilityIterations: number
}

export type FluidRuntime = {
  entityId: string
  config: FluidConfig
  origin: Vec3
  particles: FluidParticle[]
  smoothingRadius: number
  restDensity: number
  color: string
  diagnostics?: FluidDiagnostics
}

type Cell = number[]

function hashCell(x: number, y: number, z: number): string {
  return `${x}|${y}|${z}`
}

/**
 * 3D Poly6 Smoothing Kernel W_poly6(r, h) (Müller et al., SCA 2003):
 *   W_poly6(r, h) = (315 / (64 * pi * h^9)) * (h^2 - r^2)^3   for 0 <= r <= h
 */
export function poly6Kernel(rSq: number, h: number): number {
  const hSq = h * h
  if (rSq < 0 || rSq >= hSq || h <= 0) return 0
  const diff = hSq - rSq
  const h9 = hSq * hSq * hSq * hSq * h
  const coeff = 315 / (64 * Math.PI * h9)
  return coeff * diff * diff * diff
}

/**
 * Analytical gradient of the 3D Poly6 Kernel:
 *   grad W_poly6(r_vec, h) = -(945 / (32 * pi * h^9)) * (h^2 - r^2)^2 * r_vec
 */
export function poly6Gradient(
  rx: number,
  ry: number,
  rz: number,
  rSq: number,
  h: number,
  out: Vector3 = new Vector3(),
): Vector3 {
  const hSq = h * h
  if (rSq <= 1e-18 || rSq >= hSq || h <= 0) {
    return out.set(0, 0, 0)
  }
  const diff = hSq - rSq
  const h9 = hSq * hSq * hSq * hSq * h
  const scale = (-945 / (32 * Math.PI * h9)) * diff * diff
  return out.set(rx * scale, ry * scale, rz * scale)
}

/**
 * Analytical Laplacian of the 3D Poly6 Kernel (used for color field mean curvature):
 *   laplacian W_poly6(r, h) = -(945 / (32 * pi * h^9)) * (h^2 - r^2) * (3*h^2 - 7*r^2)
 */
export function poly6Laplacian(rSq: number, h: number): number {
  const hSq = h * h
  if (rSq < 0 || rSq >= hSq || h <= 0) return 0
  const h9 = hSq * hSq * hSq * hSq * h
  const coeff = -945 / (32 * Math.PI * h9)
  return coeff * (hSq - rSq) * (3 * hSq - 7 * rSq)
}

/**
 * 3D Spiky Kernel W_spiky(r, h) (Desbrun & Gascuel 1996):
 *   W_spiky(r, h) = (15 / (pi * h^6)) * (h - r)^3   for 0 <= r <= h
 */
export function spikyKernel(r: number, h: number): number {
  if (r < 0 || r >= h || h <= 0) return 0
  const diff = h - r
  const h6 = h * h * h * h * h * h
  const coeff = 15 / (Math.PI * h6)
  return coeff * diff * diff * diff
}

/**
 * Analytical gradient of the 3D Spiky Kernel (prevents particle clumping under pressure):
 *   grad W_spiky(r_vec, h) = -(45 / (pi * h^6)) * (h - r)^2 * (r_vec / r)
 */
export function spikyGradient(
  rx: number,
  ry: number,
  rz: number,
  r: number,
  h: number,
  out: Vector3 = new Vector3(),
): Vector3 {
  if (r <= 1e-12 || r >= h || h <= 0) {
    return out.set(0, 0, 0)
  }
  const diff = h - r
  const h6 = h * h * h * h * h * h
  const scale = (-45 / (Math.PI * h6)) * ((diff * diff) / r)
  return out.set(rx * scale, ry * scale, rz * scale)
}

/**
 * Analytical Laplacian of the 3D Viscosity Kernel (Müller et al., SCA 2003):
 *   laplacian W_visc(r, h) = (45 / (pi * h^6)) * (h - r)   for 0 <= r <= h
 * Strictly positive inside the support radius, guaranteeing positive-definite viscous dissipation.
 */
export function viscosityLaplacian(r: number, h: number): number {
  if (r < 0 || r >= h || h <= 0) return 0
  const h6 = h * h * h * h * h * h
  return (45 / (Math.PI * h6)) * (h - r)
}

/**
 * 3D Pairwise Cohesion Spline Kernel (Akinci et al., SIGGRAPH 2013):
 *   W_cohesion(r, h) = (32 / (pi * h^9)) *
 *     { 2*(h - r)^3 * r^3 - h^6 / 64,   for 0 < r <= 0.5*h
 *     { (h - r)^3 * r^3,                for 0.5*h < r <= h
 */
export function cohesionKernel(r: number, h: number): number {
  if (r <= 0 || r >= h || h <= 0) return 0
  const h3 = h * h * h
  const h6 = h3 * h3
  const h9 = h6 * h3
  const coeff = 32 / (Math.PI * h9)
  const diff = h - r
  const term = diff * diff * diff * r * r * r
  if (r <= 0.5 * h) {
    return coeff * (2 * term - h6 / 64)
  }
  return coeff * term
}

/**
 * Weakly Compressible Tait Equation of State (WCSPH — Monaghan 1994 / Cole 1948):
 *   P = B * ((rho / rho0)^gamma - 1),   with B = rho0 * c_s^2 / gamma,  gamma = 7
 * Clamps tensile negative pressures to 0 to suppress artificial void cavitation at free surfaces.
 */
export function computeTaitPressure(
  density: number,
  restDensity: number,
  speedOfSound = 18.0,
  gamma = 7,
): number {
  const safeRest = Math.max(1e-6, restDensity)
  const safeDensity = Math.max(0, density)
  const ratio = safeDensity / safeRest
  if (ratio <= 1) return 0
  const bConstant = (safeRest * speedOfSound * speedOfSound) / Math.max(1, gamma)
  const pressure = bConstant * (Math.pow(ratio, gamma) - 1)
  return Number.isFinite(pressure) ? Math.max(0, pressure) : 0
}

/**
 * Computes adaptive CFL substepping for SPH fluid integration based on:
 * - Maximum particle velocity v_max
 * - Acoustic wave speed c_s
 * - External & pressure acceleration scale
 * - Smoothing length h
 */
export function computeAdaptiveFluidCflSubsteps(
  dt: number,
  smoothingRadius: number,
  particles: readonly FluidParticle[],
  gravityMag: number,
  speedOfSound = 18.0,
  cflTarget = 0.4,
  minSubSteps = 2,
  maxSubSteps = 12,
): { subSteps: number; subDt: number; courantNumber: number } {
  const safeDt = Number.isFinite(dt) && dt > 0 ? dt : 1 / 60
  const h = Math.max(0.02, smoothingRadius)
  let maxVelSq = 0
  for (let i = 0; i < particles.length; i += 1) {
    const vSq = particles[i].velocity.lengthSq()
    if (vSq > maxVelSq) maxVelSq = vSq
  }
  const maxVel = Math.sqrt(maxVelSq)
  const effectiveWaveSpeed = maxVel + 0.25 * speedOfSound
  const cflAdv = (effectiveWaveSpeed * safeDt) / h
  const cflForce = Math.sqrt((Math.max(0.1, gravityMag) * safeDt * safeDt) / h)
  const courantNumber = Math.max(cflAdv, cflForce)
  const needed = Math.ceil(courantNumber / Math.max(0.1, cflTarget))
  const subSteps = Math.max(minSubSteps, Math.min(maxSubSteps, Number.isFinite(needed) ? needed : minSubSteps))
  return {
    subSteps,
    subDt: safeDt / subSteps,
    courantNumber,
  }
}

export class FluidSolver {
  private runtimes = new Map<string, FluidRuntime>()
  private gravity = new Vector3(0, -9.81, 0)
  private speedOfSound = 18.0
  private taitGamma = 7

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
        if (
          existing.config.preset !== entity.fluid.preset ||
          existing.config.particleCount !== entity.fluid.particleCount
        ) {
          this.runtimes.set(entity.id, this.makeRuntime(entity))
        } else {
          existing.config = entity.fluid
          existing.restDensity = Math.max(1, entity.fluid.density)
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
    if (!Number.isFinite(dt) || dt <= 0) return
    const frameDt = Math.min(dt, 1 / 30)
    for (const runtime of this.runtimes.values()) {
      this.stepRuntime(runtime, frameDt)
    }
  }

  getRuntimes(): FluidRuntime[] {
    return Array.from(this.runtimes.values())
  }

  getDiagnostics(entityId?: string): FluidDiagnostics | null {
    if (entityId) {
      return this.runtimes.get(entityId)?.diagnostics ?? null
    }
    const first = this.runtimes.values().next().value as FluidRuntime | undefined
    return first?.diagnostics ?? null
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
    const spacing = Math.min(dx, dy, dz)

    const smoothingRadius = Math.max(
      0.08,
      Math.max(spacing * 1.65, Math.min(size[0], size[1], size[2]) / Math.max(3, Math.cbrt(particleCount))),
    )
    const restDensity = Math.max(1, cfg.density)

    let kernelLatticeSum = poly6Kernel(0, smoothingRadius)
    for (let ix = -2; ix <= 2; ix += 1) {
      for (let iy = -2; iy <= 2; iy += 1) {
        for (let iz = -2; iz <= 2; iz += 1) {
          if (ix === 0 && iy === 0 && iz === 0) continue
          const rx = ix * dx
          const ry = iy * dy
          const rz = iz * dz
          const rSq = rx * rx + ry * ry + rz * rz
          if (rSq < smoothingRadius * smoothingRadius) {
            kernelLatticeSum += poly6Kernel(rSq, smoothingRadius)
          }
        }
      }
    }
    const calibratedMass = kernelLatticeSum > 1e-9 ? restDensity / kernelLatticeSum : 1

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
            density: restDensity,
            pressure: 0,
            mass: calibratedMass,
            temperature: cfg.temperature,
            lambda: 0,
            surfaceNormal: new Vector3(),
            curvature: 0,
            densityError: 0,
          })
          count += 1
        }
      }
    }

    const color =
      cfg.preset === 'water'
        ? '#3aa4ff'
        : cfg.preset === 'lava'
          ? '#ff6a20'
          : cfg.preset === 'honey'
            ? '#ffb03a'
            : cfg.preset === 'smoke2d'
              ? '#a0a0a0'
              : '#5ac8ff'

    return {
      entityId: entity.id,
      config: cfg,
      origin,
      particles,
      smoothingRadius,
      restDensity,
      color,
    }
  }

  private buildSpatialGrid(particles: readonly FluidParticle[], cellSize: number): Map<string, Cell> {
    const grid = new Map<string, Cell>()
    const invCell = 1 / Math.max(1e-6, cellSize)
    for (let i = 0; i < particles.length; i += 1) {
      const p = particles[i].position
      const key = hashCell(Math.floor(p.x * invCell), Math.floor(p.y * invCell), Math.floor(p.z * invCell))
      let cell = grid.get(key)
      if (!cell) {
        cell = []
        grid.set(key, cell)
      }
      cell.push(i)
    }
    return grid
  }

  private stepRuntime(runtime: FluidRuntime, dt: number) {
    const cfg = runtime.config
    const particles = runtime.particles
    const n = particles.length
    if (n === 0) return

    const h = Math.max(0.04, runtime.smoothingRadius)
    const hSq = h * h
    const restDensity = Math.max(1, runtime.restDensity || cfg.density || 1000)
    const invRestDensity = 1 / restDensity
    const gravity = this.gravity.clone().multiplyScalar(cfg.gravity / 9.81)

    const cfl = computeAdaptiveFluidCflSubsteps(
      dt,
      h,
      particles,
      gravity.length(),
      this.speedOfSound,
    )

    const pbfIterations = 4
    const cfmRelaxation = 150.0
    const tensileDq = 0.25 * h
    const wTensileRef = Math.max(1e-12, poly6Kernel(tensileDq * tensileDq, h))
    const tensileK = 0.0008

    const forces = Array.from({ length: n }, () => new Vector3())
    const posDeltas = Array.from({ length: n }, () => new Vector3())
    const xsphDeltas = Array.from({ length: n }, () => new Vector3())
    const colorLaplacians = new Float64Array(n)
    const tmpGrad = new Vector3()

    for (let sub = 0; sub < cfl.subSteps; sub += 1) {
      const subDt = cfl.subDt
      const grid = this.buildSpatialGrid(particles, h)

      // --- Pass 1: SPH Density (Poly6), Tait Equation of State Pressure & Color Field Normal/Laplacian ---
      for (let i = 0; i < n; i += 1) {
        const pi = particles[i]
        const cx = Math.floor(pi.position.x / h)
        const cy = Math.floor(pi.position.y / h)
        const cz = Math.floor(pi.position.z / h)

        let rho = pi.mass * poly6Kernel(0, h)
        const normal = pi.surfaceNormal ?? new Vector3()
        normal.set(0, 0, 0)
        let colorLap = 0

        for (let dx = -1; dx <= 1; dx += 1) {
          for (let dy = -1; dy <= 1; dy += 1) {
            for (let dz = -1; dz <= 1; dz += 1) {
              const cell = grid.get(hashCell(cx + dx, cy + dy, cz + dz))
              if (!cell) continue
              for (let k = 0; k < cell.length; k += 1) {
                const j = cell[k]
                if (j === i) continue
                const pj = particles[j]
                const rx = pi.position.x - pj.position.x
                const ry = pi.position.y - pj.position.y
                const rz = pi.position.z - pj.position.z
                const rSq = rx * rx + ry * ry + rz * rz
                if (rSq >= hSq) continue

                rho += pj.mass * poly6Kernel(rSq, h)

                const volJ = pj.mass / Math.max(restDensity * 0.25, pj.density || restDensity)
                poly6Gradient(rx, ry, rz, rSq, h, tmpGrad)
                normal.addScaledVector(tmpGrad, h * volJ)
                colorLap += volJ * poly6Laplacian(rSq, h)
              }
            }
          }
        }

        pi.density = Math.max(restDensity * 0.1, rho)
        pi.pressure = computeTaitPressure(pi.density, restDensity, this.speedOfSound, this.taitGamma)
        pi.surfaceNormal = normal
        colorLaplacians[i] = colorLap
        const normMag = normal.length()
        pi.curvature = normMag > 0.05 ? -colorLap / normMag : 0
      }

      // --- Pass 2: SPH Pressure (Spiky Gradient), Viscosity (Laplacian) & Curvature/Cohesion Surface Tension ---
      const muViscosity = Math.max(0, cfg.viscosity) * restDensity * 0.15
      const sigmaSurface = Math.max(0, cfg.surfaceTension) * restDensity * 0.04

      for (let i = 0; i < n; i += 1) {
        const pi = particles[i]
        const f = forces[i]
        f.set(
          pi.mass * gravity.x,
          pi.mass * gravity.y,
          pi.mass * gravity.z,
        )

        const cx = Math.floor(pi.position.x / h)
        const cy = Math.floor(pi.position.y / h)
        const cz = Math.floor(pi.position.z / h)
        const rhoISq = pi.density * pi.density
        const pOverRhoISq = pi.pressure / rhoISq
        const ni = pi.surfaceNormal!

        if (sigmaSurface > 0) {
          const nMag = ni.length()
          if (nMag > 0.05) {
            const curvScale = (-sigmaSurface * colorLaplacians[i]) / nMag
            f.x += ni.x * curvScale * pi.mass * invRestDensity
            f.y += ni.y * curvScale * pi.mass * invRestDensity
            f.z += ni.z * curvScale * pi.mass * invRestDensity
          }
        }

        for (let dx = -1; dx <= 1; dx += 1) {
          for (let dy = -1; dy <= 1; dy += 1) {
            for (let dz = -1; dz <= 1; dz += 1) {
              const cell = grid.get(hashCell(cx + dx, cy + dy, cz + dz))
              if (!cell) continue
              for (let k = 0; k < cell.length; k += 1) {
                const j = cell[k]
                if (j === i) continue
                const pj = particles[j]
                const rx = pi.position.x - pj.position.x
                const ry = pi.position.y - pj.position.y
                const rz = pi.position.z - pj.position.z
                const rSq = rx * rx + ry * ry + rz * rz
                if (rSq <= 1e-16 || rSq >= hSq) continue
                const r = Math.sqrt(rSq)

                const pOverRhoJSq = pj.pressure / (pj.density * pj.density)
                const pressureSymmetric = -pi.mass * pj.mass * (pOverRhoISq + pOverRhoJSq)
                spikyGradient(rx, ry, rz, r, h, tmpGrad)
                f.addScaledVector(tmpGrad, pressureSymmetric)

                if (muViscosity > 0) {
                  const lapVisc = viscosityLaplacian(r, h)
                  const viscScale = muViscosity * pi.mass * (pj.mass / pj.density) * lapVisc
                  f.x += (pj.velocity.x - pi.velocity.x) * viscScale
                  f.y += (pj.velocity.y - pi.velocity.y) * viscScale
                  f.z += (pj.velocity.z - pi.velocity.z) * viscScale
                }

                if (sigmaSurface > 0) {
                  const colorSymmetry = (2 * restDensity) / (pi.density + pj.density)
                  const wCoh = cohesionKernel(r, h)
                  const cohMag = -sigmaSurface * pi.mass * pj.mass * wCoh * colorSymmetry
                  const invR = 1 / r
                  f.x += rx * invR * cohMag
                  f.y += ry * invR * cohMag
                  f.z += rz * invR * cohMag
                }
              }
            }
          }
        }
      }

      // --- Pass 3: Symplectic Position Prediction ---
      for (let i = 0; i < n; i += 1) {
        const p = particles[i]
        p.prevPosition.copy(p.position)
        const invMass = 1 / Math.max(1e-9, p.mass)
        p.velocity.x += forces[i].x * invMass * subDt
        p.velocity.y += forces[i].y * invMass * subDt
        p.velocity.z += forces[i].z * invMass * subDt
        p.position.x += p.velocity.x * subDt
        p.position.y += p.velocity.y * subDt
        p.position.z += p.velocity.z * subDt
      }

      // --- Pass 4: Iterative Incompressibility Constraint Projection (PBF / Macklin & Müller 2013) ---
      const pbfGrid = this.buildSpatialGrid(particles, h)
      for (let iter = 0; iter < pbfIterations; iter += 1) {
        for (let i = 0; i < n; i += 1) {
          const pi = particles[i]
          const cx = Math.floor(pi.position.x / h)
          const cy = Math.floor(pi.position.y / h)
          const cz = Math.floor(pi.position.z / h)

          let rho = pi.mass * poly6Kernel(0, h)
          let gradSumSq = 0
          let gradSelfX = 0
          let gradSelfY = 0
          let gradSelfZ = 0

          for (let dx = -1; dx <= 1; dx += 1) {
            for (let dy = -1; dy <= 1; dy += 1) {
              for (let dz = -1; dz <= 1; dz += 1) {
                const cell = pbfGrid.get(hashCell(cx + dx, cy + dy, cz + dz))
                if (!cell) continue
                for (let k = 0; k < cell.length; k += 1) {
                  const j = cell[k]
                  if (j === i) continue
                  const pj = particles[j]
                  const rx = pi.position.x - pj.position.x
                  const ry = pi.position.y - pj.position.y
                  const rz = pi.position.z - pj.position.z
                  const rSq = rx * rx + ry * ry + rz * rz
                  if (rSq <= 1e-16 || rSq >= hSq) continue

                  rho += pj.mass * poly6Kernel(rSq, h)
                  const r = Math.sqrt(rSq)
                  spikyGradient(rx, ry, rz, r, h, tmpGrad)
                  const scaleJ = pj.mass * invRestDensity
                  const gx = tmpGrad.x * scaleJ
                  const gy = tmpGrad.y * scaleJ
                  const gz = tmpGrad.z * scaleJ
                  gradSelfX += gx
                  gradSelfY += gy
                  gradSelfZ += gz
                  gradSumSq += gx * gx + gy * gy + gz * gz
                }
              }
            }
          }

          gradSumSq += gradSelfX * gradSelfX + gradSelfY * gradSelfY + gradSelfZ * gradSelfZ
          pi.density = Math.max(restDensity * 0.1, rho)
          const constraint = Math.max(0, pi.density * invRestDensity - 1)
          pi.densityError = Math.abs(pi.density - restDensity) * invRestDensity
          pi.lambda = constraint > 0 ? -constraint / (gradSumSq + cfmRelaxation) : 0
        }

        for (let i = 0; i < n; i += 1) {
          const pi = particles[i]
          const deltaP = posDeltas[i]
          deltaP.set(0, 0, 0)
          const cx = Math.floor(pi.position.x / h)
          const cy = Math.floor(pi.position.y / h)
          const cz = Math.floor(pi.position.z / h)
          const lambdaI = pi.lambda ?? 0

          for (let dx = -1; dx <= 1; dx += 1) {
            for (let dy = -1; dy <= 1; dy += 1) {
              for (let dz = -1; dz <= 1; dz += 1) {
                const cell = pbfGrid.get(hashCell(cx + dx, cy + dy, cz + dz))
                if (!cell) continue
                for (let k = 0; k < cell.length; k += 1) {
                  const j = cell[k]
                  if (j === i) continue
                  const pj = particles[j]
                  const rx = pi.position.x - pj.position.x
                  const ry = pi.position.y - pj.position.y
                  const rz = pi.position.z - pj.position.z
                  const rSq = rx * rx + ry * ry + rz * rz
                  if (rSq <= 1e-16 || rSq >= hSq) continue
                  const r = Math.sqrt(rSq)

                  const wRatio = poly6Kernel(rSq, h) / wTensileRef
                  const wRatio2 = wRatio * wRatio
                  const sCorr = -tensileK * wRatio2 * wRatio2

                  spikyGradient(rx, ry, rz, r, h, tmpGrad)
                  const weight = pj.mass * invRestDensity * (lambdaI + (pj.lambda ?? 0) + sCorr)
                  deltaP.addScaledVector(tmpGrad, weight)
                }
              }
            }
          }
        }

        for (let i = 0; i < n; i += 1) {
          particles[i].position.add(posDeltas[i])
          this.applyContainerPositionClamp(particles[i], runtime)
        }
      }

      // --- Pass 5: Symplectic Velocity Recovery + XSPH Coherent Velocity Smoothing + Boundary Reflection ---
      const invSubDt = 1 / Math.max(1e-9, subDt)
      for (let i = 0; i < n; i += 1) {
        const p = particles[i]
        p.velocity.set(
          (p.position.x - p.prevPosition.x) * invSubDt,
          (p.position.y - p.prevPosition.y) * invSubDt,
          (p.position.z - p.prevPosition.z) * invSubDt,
        )
      }

      const xsphEpsilon = Math.min(0.25, 0.04 + cfg.viscosity * 0.2)
      for (let i = 0; i < n; i += 1) {
        const pi = particles[i]
        const xsph = xsphDeltas[i]
        xsph.set(0, 0, 0)
        const cx = Math.floor(pi.position.x / h)
        const cy = Math.floor(pi.position.y / h)
        const cz = Math.floor(pi.position.z / h)

        for (let dx = -1; dx <= 1; dx += 1) {
          for (let dy = -1; dy <= 1; dy += 1) {
            for (let dz = -1; dz <= 1; dz += 1) {
              const cell = pbfGrid.get(hashCell(cx + dx, cy + dy, cz + dz))
              if (!cell) continue
              for (let k = 0; k < cell.length; k += 1) {
                const j = cell[k]
                if (j === i) continue
                const pj = particles[j]
                const rx = pi.position.x - pj.position.x
                const ry = pi.position.y - pj.position.y
                const rz = pi.position.z - pj.position.z
                const rSq = rx * rx + ry * ry + rz * rz
                if (rSq >= hSq) continue

                const w = poly6Kernel(rSq, h)
                const factor = (2 * pj.mass * w) / Math.max(1e-6, pi.density + pj.density)
                xsph.x += (pj.velocity.x - pi.velocity.x) * factor
                xsph.y += (pj.velocity.y - pi.velocity.y) * factor
                xsph.z += (pj.velocity.z - pi.velocity.z) * factor
              }
            }
          }
        }
      }

      for (let i = 0; i < n; i += 1) {
        const p = particles[i]
        p.velocity.addScaledVector(xsphDeltas[i], xsphEpsilon)
        this.applyContainerBounds(p, runtime)
        if (!Number.isFinite(p.position.x) || !Number.isFinite(p.position.y) || !Number.isFinite(p.position.z)) {
          p.position.set(runtime.origin[0], runtime.origin[1], runtime.origin[2])
        }
        if (!Number.isFinite(p.velocity.x) || !Number.isFinite(p.velocity.y) || !Number.isFinite(p.velocity.z)) {
          p.velocity.set(0, 0, 0)
        }
      }
    }

    let sumDensity = 0
    let maxDensityError = 0
    let sumPressure = 0
    let maxPressure = 0
    let kineticEnergy = 0
    let potentialEnergy = 0
    const momentum = new Vector3()
    const minY = runtime.origin[1] - runtime.config.containerSize[1] * 0.5

    for (let i = 0; i < n; i += 1) {
      const p = particles[i]
      sumDensity += p.density
      const err = Math.abs(p.density - restDensity) * invRestDensity
      if (err > maxDensityError) maxDensityError = err
      sumPressure += p.pressure
      if (p.pressure > maxPressure) maxPressure = p.pressure
      kineticEnergy += 0.5 * p.mass * p.velocity.lengthSq()
      potentialEnergy += p.mass * Math.abs(cfg.gravity) * Math.max(0, p.position.y - minY)
      momentum.addScaledVector(p.velocity, p.mass)
    }

    runtime.diagnostics = {
      averageDensity: sumDensity / n,
      maxDensityError,
      averagePressure: sumPressure / n,
      maxPressure,
      kineticEnergy,
      potentialEnergy,
      totalEnergy: kineticEnergy + potentialEnergy,
      linearMomentum: [momentum.x, momentum.y, momentum.z],
      cflSubsteps: cfl.subSteps,
      courantNumber: cfl.courantNumber,
      incompressibilityIterations: pbfIterations,
    }
  }

  private applyContainerPositionClamp(particle: FluidParticle, runtime: FluidRuntime) {
    const o = runtime.origin
    const s = runtime.config.containerSize
    if (runtime.config.containerKind === 'sphere') {
      const r = Math.min(s[0], s[1], s[2]) / 2
      const dx = particle.position.x - o[0]
      const dy = particle.position.y - o[1]
      const dz = particle.position.z - o[2]
      const d = Math.hypot(dx, dy, dz)
      if (d > r && d > 1e-9) {
        const scale = r / d
        particle.position.set(o[0] + dx * scale, o[1] + dy * scale, o[2] + dz * scale)
      }
      return
    }
    const minX = o[0] - s[0] / 2
    const maxX = o[0] + s[0] / 2
    const minY = o[1] - s[1] / 2
    const maxY = o[1] + s[1] / 2
    const minZ = o[2] - s[2] / 2
    const maxZ = o[2] + s[2] / 2
    if (particle.position.x < minX) particle.position.x = minX
    else if (particle.position.x > maxX) particle.position.x = maxX
    if (particle.position.y < minY) particle.position.y = minY
    else if (particle.position.y > maxY) particle.position.y = maxY
    if (particle.position.z < minZ) particle.position.z = minZ
    else if (particle.position.z > maxZ) particle.position.z = maxZ
  }

  private applyContainerBounds(particle: FluidParticle, runtime: FluidRuntime) {
    const o = runtime.origin
    const s = runtime.config.containerSize
    const damping = 0.35
    if (runtime.config.containerKind === 'sphere') {
      const r = Math.min(s[0], s[1], s[2]) / 2
      const delta = particle.position.clone().sub(new Vector3(o[0], o[1], o[2]))
      const d = delta.length()
      if (d > r && d > 1e-9) {
        const normal = delta.clone().divideScalar(d)
        delta.multiplyScalar(r / d)
        particle.position.set(o[0] + delta.x, o[1] + delta.y, o[2] + delta.z)
        const vDotN = particle.velocity.dot(normal)
        if (vDotN > 0) {
          particle.velocity.addScaledVector(normal, -(1 + damping) * vDotN)
        }
      }
      return
    }
    const minX = o[0] - s[0] / 2
    const maxX = o[0] + s[0] / 2
    const minY = o[1] - s[1] / 2
    const maxY = o[1] + s[1] / 2
    const minZ = o[2] - s[2] / 2
    const maxZ = o[2] + s[2] / 2
    if (particle.position.x <= minX) {
      particle.position.x = minX
      if (particle.velocity.x < 0) particle.velocity.x = -particle.velocity.x * damping
    } else if (particle.position.x >= maxX) {
      particle.position.x = maxX
      if (particle.velocity.x > 0) particle.velocity.x = -particle.velocity.x * damping
    }
    if (particle.position.y <= minY) {
      particle.position.y = minY
      if (particle.velocity.y < 0) particle.velocity.y = -particle.velocity.y * damping
    } else if (particle.position.y >= maxY) {
      particle.position.y = maxY
      if (particle.velocity.y > 0) particle.velocity.y = -particle.velocity.y * damping
    }
    if (particle.position.z <= minZ) {
      particle.position.z = minZ
      if (particle.velocity.z < 0) particle.velocity.z = -particle.velocity.z * damping
    } else if (particle.position.z >= maxZ) {
      particle.position.z = maxZ
      if (particle.velocity.z > 0) particle.velocity.z = -particle.velocity.z * damping
    }
  }
}
