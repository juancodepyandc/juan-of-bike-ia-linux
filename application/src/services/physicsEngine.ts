import { Box3, Euler, Matrix4, Quaternion, Vector3 } from 'three'
import type { ColliderShape, PhysicsBody, SceneEntity, Vec3 } from './simulator/types.ts'

/**
 * Symplectic integration scheme selector.
 * - `yoshida4`: 4th-order canonical composition of Störmer-Verlet steps (Yoshida 1990).
 * - `velocityVerlet`: 2nd-order symplectic Velocity-Verlet (Kick-Drift-Kick).
 */
export type SymplecticIntegratorKind = 'yoshida4' | 'velocityVerlet'

/**
 * Exact analytical coefficients for Haruo Yoshida's 4th-order symplectic integrator
 * (Physics Letters A, Vol. 150, Issues 5-7, 1990, pp. 262-268).
 *
 * Composes three 2nd-order symmetric Störmer-Verlet steps with weights:
 *   w1 = 1 / (2 - 2^(1/3))
 *   w0 = -2^(1/3) / (2 - 2^(1/3)) = 1 - 2*w1
 * preserving the canonical symplectic 2-form dq ^ dp to O(dt^4).
 */
const CBRT2 = Math.cbrt(2)
export const YOSHIDA4_W1 = 1 / (2 - CBRT2)
export const YOSHIDA4_W0 = -CBRT2 / (2 - CBRT2)
export const YOSHIDA4_C: readonly [number, number, number, number] = [
  YOSHIDA4_W1 * 0.5,
  (YOSHIDA4_W0 + YOSHIDA4_W1) * 0.5,
  (YOSHIDA4_W0 + YOSHIDA4_W1) * 0.5,
  YOSHIDA4_W1 * 0.5,
]
export const YOSHIDA4_D: readonly [number, number, number] = [
  YOSHIDA4_W1,
  YOSHIDA4_W0,
  YOSHIDA4_W1,
]

export type HarmonicSpringLink = {
  id: string
  bodyA: string
  bodyB: string | null
  anchorWorldB?: Vec3
  restLength: number
  stiffness: number
  damping: number
}

export type CflAdaptiveConfig = {
  cflTarget?: number
  minSubSteps?: number
  maxSubSteps?: number
  minCharacteristicLength?: number
}

export type CflSubstepDiagnostic = {
  subSteps: number
  subDt: number
  courantNumber: number
  maxLinearSpeed: number
  maxAcceleration: number
  maxAngularSpeed: number
  minCharacteristicLength: number
}

export type MechanicalInvariants = {
  kineticEnergy: number
  translationalKineticEnergy: number
  rotationalKineticEnergy: number
  potentialEnergy: number
  gravitationalPotentialEnergy: number
  elasticPotentialEnergy: number
  pairwisePotentialEnergy: number
  totalEnergy: number
  initialEnergy: number | null
  relativeEnergyDrift: number
  linearMomentum: Vec3
  linearMomentumMagnitude: number
  angularMomentum: Vec3
  angularMomentumMagnitude: number
  isConservative: boolean
  cflSubsteps: number
  courantNumber: number
}

type RigidBodyState = {
  id: string
  kind: 'static' | 'dynamic' | 'kinematic'
  mass: number
  invMass: number
  position: Vector3
  previousPosition: Vector3
  quaternion: Quaternion
  velocity: Vector3
  angularVelocity: Vector3
  friction: number
  restitution: number
  linearDamping: number
  angularDamping: number
  gravityScale: number
  collider: ColliderShape
  halfExtents: Vector3
  radius: number
  characteristicLength: number
  locked: PhysicsBody['locked']
  forceAccum: Vector3
  torqueAccum: Vector3
  externalForce: Vector3
  externalTorque: Vector3
  inertia: Vector3
  invInertia: Vector3
}

export type ContactEvent = {
  a: string
  b: string
  point: Vec3
  normal: Vec3
  depth: number
  impulse: number
}

/**
 * Pure adaptive Courant-Friedrichs-Lewy (CFL) substep estimator.
 * Evaluates translational, accelerative, rotational, and harmonic stiffness scales
 * to guarantee numerical stability and prevent tunneling for arbitrary time steps.
 */
export function computeAdaptiveCflSubsteps(
  dt: number,
  bodies: Iterable<{
    kind: 'static' | 'dynamic' | 'kinematic'
    velocity: { x: number; y: number; z: number }
    angularVelocity: { x: number; y: number; z: number }
    acceleration?: { x: number; y: number; z: number }
    characteristicLength: number
    mass?: number
  }>,
  gravityMagnitude = 9.81,
  maxSpringStiffness = 0,
  config: CflAdaptiveConfig = {},
): CflSubstepDiagnostic {
  const safeDt = Number.isFinite(dt) && dt > 0 ? dt : 1 / 120
  const cflTarget = Math.max(0.05, config.cflTarget ?? 0.25)
  const minSubSteps = Math.max(1, Math.floor(config.minSubSteps ?? 2))
  const maxSubSteps = Math.max(minSubSteps, Math.floor(config.maxSubSteps ?? 64))
  const lengthFloor = Math.max(1e-4, config.minCharacteristicLength ?? 0.02)

  let maxLinearSpeed = 0
  let maxAcceleration = Math.max(0, gravityMagnitude)
  let maxAngularSpeed = 0
  let minCharacteristicLength = Number.POSITIVE_INFINITY
  let minDynamicMass = Number.POSITIVE_INFINITY
  let hasDynamic = false

  for (const b of bodies) {
    const charLen = Math.max(lengthFloor, Number.isFinite(b.characteristicLength) ? b.characteristicLength : 0.5)
    if (charLen < minCharacteristicLength) minCharacteristicLength = charLen
    if (b.kind !== 'dynamic') continue
    hasDynamic = true

    const vx = Number.isFinite(b.velocity.x) ? b.velocity.x : 0
    const vy = Number.isFinite(b.velocity.y) ? b.velocity.y : 0
    const vz = Number.isFinite(b.velocity.z) ? b.velocity.z : 0
    const speed = Math.hypot(vx, vy, vz)
    if (speed > maxLinearSpeed) maxLinearSpeed = speed

    const wx = Number.isFinite(b.angularVelocity.x) ? b.angularVelocity.x : 0
    const wy = Number.isFinite(b.angularVelocity.y) ? b.angularVelocity.y : 0
    const wz = Number.isFinite(b.angularVelocity.z) ? b.angularVelocity.z : 0
    const omega = Math.hypot(wx, wy, wz)
    if (omega > maxAngularSpeed) maxAngularSpeed = omega

    if (b.acceleration) {
      const ax = Number.isFinite(b.acceleration.x) ? b.acceleration.x : 0
      const ay = Number.isFinite(b.acceleration.y) ? b.acceleration.y : 0
      const az = Number.isFinite(b.acceleration.z) ? b.acceleration.z : 0
      const acc = Math.hypot(ax, ay, az)
      if (acc > maxAcceleration) maxAcceleration = acc
    }

    if (b.mass && b.mass > 0 && b.mass < minDynamicMass) {
      minDynamicMass = b.mass
    }
  }

  if (!hasDynamic || !Number.isFinite(minCharacteristicLength)) {
    minCharacteristicLength = 0.5
  }

  // 1. Advective Courant number: C_v = v_max * dt / L_min
  const cflAdvective = (maxLinearSpeed * safeDt) / minCharacteristicLength
  // 2. Free-fall / acceleration Courant number: C_a = sqrt(a_max / L_min) * dt
  const cflAccelerative = Math.sqrt(maxAcceleration / minCharacteristicLength) * safeDt
  // 3. Rotational Lie-group Courant number: C_w = omega_max * dt / pi
  const cflRotational = (maxAngularSpeed * safeDt) / Math.PI
  // 4. Harmonic stiffness Courant number: C_k = sqrt(k / m_min) * dt
  const cflStiffness =
    maxSpringStiffness > 0 && Number.isFinite(minDynamicMass)
      ? Math.sqrt(maxSpringStiffness / minDynamicMass) * safeDt
      : 0

  const courantNumber = Math.max(cflAdvective, cflAccelerative, cflRotational, cflStiffness)
  const rawSteps = Math.ceil(courantNumber / cflTarget)
  const subSteps = Math.max(minSubSteps, Math.min(maxSubSteps, Number.isFinite(rawSteps) ? rawSteps : minSubSteps))
  const subDt = safeDt / subSteps

  return {
    subSteps,
    subDt,
    courantNumber,
    maxLinearSpeed,
    maxAcceleration,
    maxAngularSpeed,
    minCharacteristicLength,
  }
}

/**
 * Exact Lie-group exponential map on SO(3) / SU(2) unit quaternions:
 *   q(t + dt) = exp(0.5 * dt * omega) * q(t)
 * Uses a 6th-order Taylor expansion near ||omega|| -> 0 to guarantee C^infinity
 * smoothness and eliminate division-by-zero NaN/Inf.
 */
function integrateQuaternionExponentialMap(q: Quaternion, omega: Vector3, dt: number): void {
  const wx = omega.x
  const wy = omega.y
  const wz = omega.z
  const omegaMagSq = wx * wx + wy * wy + wz * wz
  if (omegaMagSq <= 0 || dt === 0) return

  const halfThetaSq = 0.25 * dt * dt * omegaMagSq
  let s: number
  let c: number
  if (halfThetaSq < 1e-8) {
    s = 0.5 * dt * (1 - halfThetaSq / 6 + (halfThetaSq * halfThetaSq) / 120)
    c = 1 - halfThetaSq * 0.5 + (halfThetaSq * halfThetaSq) / 24
  } else {
    const halfTheta = Math.sqrt(halfThetaSq)
    const omegaMag = (2 * halfTheta) / Math.abs(dt)
    s = (Math.sin(halfTheta) / omegaMag) * Math.sign(dt)
    c = Math.cos(halfTheta)
  }

  const dqX = wx * s
  const dqY = wy * s
  const dqZ = wz * s
  const dqW = c

  const qx = q.x
  const qy = q.y
  const qz = q.z
  const qw = q.w

  q.set(
    dqW * qx + dqX * qw + dqY * qz - dqZ * qy,
    dqW * qy - dqX * qz + dqY * qw + dqZ * qx,
    dqW * qz + dqX * qy - dqY * qx + dqZ * qw,
    dqW * qw - dqX * qx - dqY * qy - dqZ * qz,
  )
  q.normalize()
}

function computeBodyFrameRotationalQuantities(
  body: RigidBodyState,
): { rotationalKineticEnergy: number; angularMomentumWorld: Vector3 } {
  const qInv = body.quaternion.clone().invert()
  const omegaBody = body.angularVelocity.clone().applyQuaternion(qInv)
  const LBody = new Vector3(
    body.inertia.x * omegaBody.x,
    body.inertia.y * omegaBody.y,
    body.inertia.z * omegaBody.z,
  )
  const rotationalKineticEnergy =
    0.5 * (omegaBody.x * LBody.x + omegaBody.y * LBody.y + omegaBody.z * LBody.z)
  const angularMomentumWorld = LBody.applyQuaternion(body.quaternion)
  return { rotationalKineticEnergy, angularMomentumWorld }
}

function applyWorldInverseInertia(body: RigidBodyState, vecWorld: Vector3): Vector3 {
  if (body.kind !== 'dynamic') return new Vector3(0, 0, 0)
  const qInv = body.quaternion.clone().invert()
  const local = vecWorld.clone().applyQuaternion(qInv)
  local.set(
    body.locked.rx ? 0 : local.x * body.invInertia.x,
    body.locked.ry ? 0 : local.y * body.invInertia.y,
    body.locked.rz ? 0 : local.z * body.invInertia.z,
  )
  return local.applyQuaternion(body.quaternion)
}

function computeEulerPoinsotAngularAcceleration(body: RigidBodyState, torqueWorld: Vector3): Vector3 {
  if (body.kind !== 'dynamic') return new Vector3(0, 0, 0)
  const qInv = body.quaternion.clone().invert()
  const omegaBody = body.angularVelocity.clone().applyQuaternion(qInv)
  const tauBody = torqueWorld.clone().applyQuaternion(qInv)

  const IOmegaX = body.inertia.x * omegaBody.x
  const IOmegaY = body.inertia.y * omegaBody.y
  const IOmegaZ = body.inertia.z * omegaBody.z

  const gyroX = omegaBody.y * IOmegaZ - omegaBody.z * IOmegaY
  const gyroY = omegaBody.z * IOmegaX - omegaBody.x * IOmegaZ
  const gyroZ = omegaBody.x * IOmegaY - omegaBody.y * IOmegaX

  const alphaBody = new Vector3(
    body.locked.rx ? 0 : (tauBody.x - gyroX) * body.invInertia.x,
    body.locked.ry ? 0 : (tauBody.y - gyroY) * body.invInertia.y,
    body.locked.rz ? 0 : (tauBody.z - gyroZ) * body.invInertia.z,
  )
  const alphaWorld = alphaBody.applyQuaternion(body.quaternion)
  if (body.locked.rx) alphaWorld.x = 0
  if (body.locked.ry) alphaWorld.y = 0
  if (body.locked.rz) alphaWorld.z = 0
  return alphaWorld
}

function sanitizeVector3(v: Vector3, fallback = 0): void {
  if (!Number.isFinite(v.x)) v.x = fallback
  if (!Number.isFinite(v.y)) v.y = fallback
  if (!Number.isFinite(v.z)) v.z = fallback
}

export class PhysicsEngine {
  private bodies = new Map<string, RigidBodyState>()
  private springs = new Map<string, HarmonicSpringLink>()
  private gravity = new Vector3(0, -9.81, 0)
  private gravitationalConstant = 0
  private softeningLength = 0.05
  private potentialReferenceY = -5
  private integratorKind: SymplecticIntegratorKind = 'yoshida4'
  private enforceConservativeEnergyProjection = true
  private accumulator = 0
  private fixedDt = 1 / 120
  private minSubSteps = 2
  private maxSubSteps = 48
  private cflTarget = 0.25
  private lastCflDiagnostic: CflSubstepDiagnostic = {
    subSteps: 2,
    subDt: 1 / 240,
    courantNumber: 0,
    maxLinearSpeed: 0,
    maxAcceleration: 9.81,
    maxAngularSpeed: 0,
    minCharacteristicLength: 0.5,
  }
  private baselineEnergy: number | null = null
  private lastInvariants: MechanicalInvariants = {
    kineticEnergy: 0,
    translationalKineticEnergy: 0,
    rotationalKineticEnergy: 0,
    potentialEnergy: 0,
    gravitationalPotentialEnergy: 0,
    elasticPotentialEnergy: 0,
    pairwisePotentialEnergy: 0,
    totalEnergy: 0,
    initialEnergy: null,
    relativeEnergyDrift: 0,
    linearMomentum: [0, 0, 0],
    linearMomentumMagnitude: 0,
    angularMomentum: [0, 0, 0],
    angularMomentumMagnitude: 0,
    isConservative: true,
    cflSubsteps: 2,
    courantNumber: 0,
  }
  private listeners: Array<(events: ContactEvent[]) => void> = []
  private lastContacts: ContactEvent[] = []

  setGravity(value: Vec3) {
    this.gravity.set(value[0], value[1], value[2])
    this.baselineEnergy = null
  }

  getGravity(): Vector3 {
    return this.gravity.clone()
  }

  setIntegrator(kind: SymplecticIntegratorKind) {
    this.integratorKind = kind
  }

  getIntegrator(): SymplecticIntegratorKind {
    return this.integratorKind
  }

  setPairwiseGravity(gravitationalConstant: number, softeningLength = 0.05) {
    this.gravitationalConstant = Math.max(0, gravitationalConstant)
    this.softeningLength = Math.max(1e-4, softeningLength)
    this.baselineEnergy = null
  }

  setEnergyProjectionEnabled(enabled: boolean) {
    this.enforceConservativeEnergyProjection = enabled
  }

  addSpringConstraint(link: HarmonicSpringLink) {
    this.springs.set(link.id, { ...link })
    this.baselineEnergy = null
  }

  removeSpringConstraint(id: string) {
    this.springs.delete(id)
    this.baselineEnergy = null
  }

  onContacts(fn: (events: ContactEvent[]) => void) {
    this.listeners.push(fn)
    return () => {
      this.listeners = this.listeners.filter((l) => l !== fn)
    }
  }

  reset() {
    this.bodies.clear()
    this.springs.clear()
    this.lastContacts = []
    this.accumulator = 0
    this.baselineEnergy = null
    this.lastInvariants = this.computeMechanicalInvariants()
  }

  syncFromEntities(entities: SceneEntity[]) {
    const seen = new Set<string>()
    const seenSprings = new Set<string>()

    for (const entity of entities) {
      if (entity.constraint && entity.constraint.kind === 'spring' && entity.constraint.bodyA) {
        seenSprings.add(entity.id)
        const restLength = Math.max(0, (entity.constraint.limitMin + entity.constraint.limitMax) * 0.5)
        this.springs.set(entity.id, {
          id: entity.id,
          bodyA: entity.constraint.bodyA,
          bodyB: entity.constraint.bodyB,
          anchorWorldB: entity.constraint.anchorB,
          restLength,
          stiffness: Math.max(0, entity.constraint.stiffness),
          damping: Math.max(0, entity.constraint.damping),
        })
      }

      if (!entity.physics || !entity.physics.enabled) continue
      seen.add(entity.id)
      let body = this.bodies.get(entity.id)
      if (!body) {
        body = this.makeBody(entity)
        this.bodies.set(entity.id, body)
        this.baselineEnergy = null
      } else {
        this.updateBodyConfig(body, entity)
      }
    }

    for (const id of Array.from(this.bodies.keys())) {
      if (!seen.has(id)) {
        this.bodies.delete(id)
        this.baselineEnergy = null
      }
    }

    for (const id of Array.from(this.springs.keys())) {
      if (!seenSprings.has(id) && id.startsWith('entity-')) {
        this.springs.delete(id)
      }
    }

    this.lastInvariants = this.computeMechanicalInvariants()
  }

  applyForce(id: string, force: Vec3) {
    const b = this.bodies.get(id)
    if (!b || b.kind !== 'dynamic') return
    b.forceAccum.x += force[0]
    b.forceAccum.y += force[1]
    b.forceAccum.z += force[2]
  }

  applyTorque(id: string, torque: Vec3) {
    const b = this.bodies.get(id)
    if (!b || b.kind !== 'dynamic') return
    b.torqueAccum.x += torque[0]
    b.torqueAccum.y += torque[1]
    b.torqueAccum.z += torque[2]
  }

  applyImpulse(id: string, impulse: Vec3) {
    const b = this.bodies.get(id)
    if (!b || b.kind !== 'dynamic') return
    if (!b.locked.x) b.velocity.x += impulse[0] * b.invMass
    if (!b.locked.y) b.velocity.y += impulse[1] * b.invMass
    if (!b.locked.z) b.velocity.z += impulse[2] * b.invMass
    this.baselineEnergy = null
  }

  step(dt: number) {
    if (!Number.isFinite(dt) || dt <= 0) return
    const clamped = Math.min(dt, 0.05)
    this.accumulator += clamped
    let ticks = 0
    while (this.accumulator >= this.fixedDt && ticks < 10) {
      this.simulateFixed(this.fixedDt)
      this.accumulator -= this.fixedDt
      ticks += 1
    }
  }

  stepExact(dt: number) {
    if (!Number.isFinite(dt) || dt <= 0) return
    this.simulateFixed(dt)
  }

  getBodyState(id: string) {
    const b = this.bodies.get(id)
    if (!b) return null
    return {
      position: [b.position.x, b.position.y, b.position.z] as Vec3,
      quaternion: [b.quaternion.x, b.quaternion.y, b.quaternion.z, b.quaternion.w] as [number, number, number, number],
      velocity: [b.velocity.x, b.velocity.y, b.velocity.z] as Vec3,
      angularVelocity: [b.angularVelocity.x, b.angularVelocity.y, b.angularVelocity.z] as Vec3,
    }
  }

  getLastContacts(): ContactEvent[] {
    return this.lastContacts
  }

  getLastCflDiagnostic(): CflSubstepDiagnostic {
    return { ...this.lastCflDiagnostic }
  }

  getInvariants(): MechanicalInvariants {
    return this.lastInvariants
  }

  computeMechanicalInvariants(): MechanicalInvariants {
    let translationalKineticEnergy = 0
    let rotationalKineticEnergy = 0
    let gravitationalPotentialEnergy = 0
    let elasticPotentialEnergy = 0
    let pairwisePotentialEnergy = 0

    const linearMomentum = new Vector3(0, 0, 0)
    const angularMomentum = new Vector3(0, 0, 0)
    let isConservative = true

    const dynamicBodies: RigidBodyState[] = []

    for (const body of this.bodies.values()) {
      if (body.kind !== 'dynamic' || body.mass <= 0) continue
      dynamicBodies.push(body)

      if (body.linearDamping > 1e-9 || body.angularDamping > 1e-9) {
        isConservative = false
      }

      const vSq = body.velocity.lengthSq()
      translationalKineticEnergy += 0.5 * body.mass * vSq

      const { rotationalKineticEnergy: rotKE, angularMomentumWorld: Lrot } =
        computeBodyFrameRotationalQuantities(body)
      rotationalKineticEnergy += rotKE

      const relPos = new Vector3(
        body.position.x,
        body.position.y - this.potentialReferenceY,
        body.position.z,
      )
      gravitationalPotentialEnergy += -body.mass * body.gravityScale * this.gravity.dot(relPos)

      const pLinear = body.velocity.clone().multiplyScalar(body.mass)
      linearMomentum.add(pLinear)

      const orbitalL = new Vector3().crossVectors(body.position, pLinear)
      angularMomentum.add(orbitalL).add(Lrot)
    }

    for (const spring of this.springs.values()) {
      if (spring.stiffness <= 0) continue
      const a = this.bodies.get(spring.bodyA)
      if (!a) continue
      const posB = spring.bodyB
        ? this.bodies.get(spring.bodyB)?.position
        : spring.anchorWorldB
          ? new Vector3(spring.anchorWorldB[0], spring.anchorWorldB[1], spring.anchorWorldB[2])
          : null
      if (!posB) continue
      const dist = a.position.distanceTo(posB)
      const stretch = dist - spring.restLength
      elasticPotentialEnergy += 0.5 * spring.stiffness * stretch * stretch
      if (spring.damping > 1e-9) isConservative = false
    }

    if (this.gravitationalConstant > 0 && dynamicBodies.length > 1) {
      const epsSq = this.softeningLength * this.softeningLength
      for (let i = 0; i < dynamicBodies.length; i += 1) {
        for (let j = i + 1; j < dynamicBodies.length; j += 1) {
          const bi = dynamicBodies[i]
          const bj = dynamicBodies[j]
          const distSq = bi.position.distanceToSquared(bj.position)
          pairwisePotentialEnergy +=
            -(this.gravitationalConstant * bi.mass * bj.mass) / Math.sqrt(distSq + epsSq)
        }
      }
    }

    const kineticEnergy = translationalKineticEnergy + rotationalKineticEnergy
    const potentialEnergy =
      gravitationalPotentialEnergy + elasticPotentialEnergy + pairwisePotentialEnergy
    const totalEnergy = kineticEnergy + potentialEnergy

    if (this.baselineEnergy === null && dynamicBodies.length > 0) {
      this.baselineEnergy = totalEnergy
    }

    const relativeEnergyDrift =
      this.baselineEnergy !== null
        ? Math.abs(totalEnergy - this.baselineEnergy) / Math.max(Math.abs(this.baselineEnergy), 1e-12)
        : 0

    return {
      kineticEnergy,
      translationalKineticEnergy,
      rotationalKineticEnergy,
      potentialEnergy,
      gravitationalPotentialEnergy,
      elasticPotentialEnergy,
      pairwisePotentialEnergy,
      totalEnergy,
      initialEnergy: this.baselineEnergy,
      relativeEnergyDrift,
      linearMomentum: [linearMomentum.x, linearMomentum.y, linearMomentum.z],
      linearMomentumMagnitude: linearMomentum.length(),
      angularMomentum: [angularMomentum.x, angularMomentum.y, angularMomentum.z],
      angularMomentumMagnitude: angularMomentum.length(),
      isConservative,
      cflSubsteps: this.lastCflDiagnostic.subSteps,
      courantNumber: this.lastCflDiagnostic.courantNumber,
    }
  }

  private makeBody(entity: SceneEntity): RigidBodyState {
    const phys = entity.physics!
    const invMass = phys.kind === 'dynamic' && phys.mass > 0 ? 1 / phys.mass : 0
    const halfExtents = this.computeHalfExtents(entity)
    const radius = Math.max(halfExtents.x, halfExtents.y, halfExtents.z)
    const characteristicLength = Math.max(
      0.02,
      phys.collider === 'sphere'
        ? radius
        : Math.min(halfExtents.x, halfExtents.y, halfExtents.z) * 2,
    )
    const inertia = this.computeInertia(phys, halfExtents, radius)
    const quaternion = new Quaternion().setFromEuler(
      new Euler(entity.transform.rotation[0], entity.transform.rotation[1], entity.transform.rotation[2], 'XYZ'),
    )
    return {
      id: entity.id,
      kind: phys.kind,
      mass: phys.mass,
      invMass,
      position: new Vector3(...entity.transform.position),
      previousPosition: new Vector3(...entity.transform.position),
      quaternion,
      velocity: new Vector3(...phys.velocity),
      angularVelocity: new Vector3(...phys.angularVelocity),
      friction: phys.friction,
      restitution: phys.restitution,
      linearDamping: phys.linearDamping,
      angularDamping: phys.angularDamping,
      gravityScale: phys.gravityScale,
      collider: phys.collider,
      halfExtents,
      radius,
      characteristicLength,
      locked: { ...phys.locked },
      forceAccum: new Vector3(),
      torqueAccum: new Vector3(),
      externalForce: new Vector3(),
      externalTorque: new Vector3(),
      inertia,
      invInertia: new Vector3(
        inertia.x > 0 ? 1 / inertia.x : 0,
        inertia.y > 0 ? 1 / inertia.y : 0,
        inertia.z > 0 ? 1 / inertia.z : 0,
      ),
    }
  }

  private updateBodyConfig(body: RigidBodyState, entity: SceneEntity) {
    const phys = entity.physics!
    body.kind = phys.kind
    body.mass = phys.mass
    body.invMass = phys.kind === 'dynamic' && phys.mass > 0 ? 1 / phys.mass : 0
    body.friction = phys.friction
    body.restitution = phys.restitution
    body.linearDamping = phys.linearDamping
    body.angularDamping = phys.angularDamping
    body.gravityScale = phys.gravityScale
    body.collider = phys.collider
    body.halfExtents = this.computeHalfExtents(entity)
    body.radius = Math.max(body.halfExtents.x, body.halfExtents.y, body.halfExtents.z)
    body.characteristicLength = Math.max(
      0.02,
      phys.collider === 'sphere'
        ? body.radius
        : Math.min(body.halfExtents.x, body.halfExtents.y, body.halfExtents.z) * 2,
    )
    body.inertia = this.computeInertia(phys, body.halfExtents, body.radius)
    body.invInertia.set(
      body.inertia.x > 0 ? 1 / body.inertia.x : 0,
      body.inertia.y > 0 ? 1 / body.inertia.y : 0,
      body.inertia.z > 0 ? 1 / body.inertia.z : 0,
    )
    body.locked = { ...phys.locked }
  }

  private computeHalfExtents(entity: SceneEntity): Vector3 {
    const scale = new Vector3(...entity.transform.scale)
    const geom = entity.geometry
    if (!geom) return new Vector3(0.5, 0.5, 0.5).multiply(scale)
    const p = geom.params
    switch (geom.kind) {
      case 'cube':
        return new Vector3((p.size ?? 1) / 2, (p.size ?? 1) / 2, (p.size ?? 1) / 2).multiply(scale)
      case 'sphere':
      case 'icosahedron':
      case 'tetrahedron':
        return new Vector3(p.radius ?? 0.75, p.radius ?? 0.75, p.radius ?? 0.75).multiply(scale)
      case 'cylinder':
        return new Vector3(p.radiusTop ?? 0.5, (p.height ?? 1) / 2, p.radiusTop ?? 0.5).multiply(scale)
      case 'cone':
        return new Vector3(p.radius ?? 0.6, (p.height ?? 1) / 2, p.radius ?? 0.6).multiply(scale)
      case 'capsule':
        return new Vector3(p.radius ?? 0.35, (p.length ?? 1) / 2 + (p.radius ?? 0.35), p.radius ?? 0.35).multiply(scale)
      case 'torus':
        return new Vector3((p.radius ?? 0.7) + (p.tube ?? 0.2), p.tube ?? 0.2, (p.radius ?? 0.7) + (p.tube ?? 0.2)).multiply(scale)
      case 'plane':
        return new Vector3((p.width ?? 4) / 2, 0.02, (p.height ?? 4) / 2).multiply(scale)
      default:
        return new Vector3(0.5, 0.5, 0.5).multiply(scale)
    }
  }

  private computeInertia(phys: PhysicsBody, halfExtents: Vector3, radius: number): Vector3 {
    if (phys.kind !== 'dynamic' || phys.mass <= 0) return new Vector3()
    if (phys.collider === 'sphere') {
      const i = (2 / 5) * phys.mass * radius * radius
      return new Vector3(i, i, i)
    }
    if (phys.collider === 'cylinder' || phys.collider === 'capsule') {
      const r = Math.max(halfExtents.x, halfExtents.z)
      const h = 2 * halfExtents.y
      const ixz = (1 / 12) * phys.mass * (3 * r * r + h * h)
      const iy = 0.5 * phys.mass * r * r
      return new Vector3(ixz, iy, ixz)
    }
    const hx = halfExtents.x
    const hy = halfExtents.y
    const hz = halfExtents.z
    const m = phys.mass / 3
    return new Vector3(m * (hy * hy + hz * hz), m * (hx * hx + hz * hz), m * (hx * hx + hy * hy))
  }

  private evaluateAccelerations(): Map<string, { linear: Vector3; angular: Vector3 }> {
    const result = new Map<string, { linear: Vector3; angular: Vector3 }>()
    const dynamicBodies: RigidBodyState[] = []

    for (const body of this.bodies.values()) {
      if (body.kind !== 'dynamic') continue
      dynamicBodies.push(body)
      const linAcc = new Vector3(
        body.locked.x ? 0 : this.gravity.x * body.gravityScale + body.externalForce.x * body.invMass,
        body.locked.y ? 0 : this.gravity.y * body.gravityScale + body.externalForce.y * body.invMass,
        body.locked.z ? 0 : this.gravity.z * body.gravityScale + body.externalForce.z * body.invMass,
      )
      const angAcc = computeEulerPoinsotAngularAcceleration(body, body.externalTorque)
      result.set(body.id, { linear: linAcc, angular: angAcc })
    }

    for (const spring of this.springs.values()) {
      if (spring.stiffness <= 0 && spring.damping <= 0) continue
      const a = this.bodies.get(spring.bodyA)
      if (!a) continue
      const b = spring.bodyB ? this.bodies.get(spring.bodyB) ?? null : null
      const posB = b
        ? b.position
        : spring.anchorWorldB
          ? new Vector3(spring.anchorWorldB[0], spring.anchorWorldB[1], spring.anchorWorldB[2])
          : null
      if (!posB) continue

      const delta = a.position.clone().sub(posB)
      const dist = delta.length()
      if (dist < 1e-9) continue
      const dir = delta.divideScalar(dist)
      const stretch = dist - spring.restLength
      const relVelAlongSpring = b
        ? a.velocity.clone().sub(b.velocity).dot(dir)
        : a.velocity.dot(dir)
      const forceScalar = -spring.stiffness * stretch - spring.damping * relVelAlongSpring

      if (a.kind === 'dynamic') {
        const accA = result.get(a.id)?.linear
        if (accA) {
          if (!a.locked.x) accA.x += dir.x * forceScalar * a.invMass
          if (!a.locked.y) accA.y += dir.y * forceScalar * a.invMass
          if (!a.locked.z) accA.z += dir.z * forceScalar * a.invMass
        }
      }
      if (b && b.kind === 'dynamic') {
        const accB = result.get(b.id)?.linear
        if (accB) {
          if (!b.locked.x) accB.x -= dir.x * forceScalar * b.invMass
          if (!b.locked.y) accB.y -= dir.y * forceScalar * b.invMass
          if (!b.locked.z) accB.z -= dir.z * forceScalar * b.invMass
        }
      }
    }

    if (this.gravitationalConstant > 0 && dynamicBodies.length > 1) {
      const epsSq = this.softeningLength * this.softeningLength
      for (let i = 0; i < dynamicBodies.length; i += 1) {
        for (let j = i + 1; j < dynamicBodies.length; j += 1) {
          const bi = dynamicBodies[i]
          const bj = dynamicBodies[j]
          const rVec = bj.position.clone().sub(bi.position)
          const rSq = rVec.lengthSq() + epsSq
          const invR3 = 1 / (rSq * Math.sqrt(rSq))
          const factor = this.gravitationalConstant * invR3

          const accI = result.get(bi.id)?.linear
          const accJ = result.get(bj.id)?.linear
          if (accI) {
            if (!bi.locked.x) accI.x += factor * bj.mass * rVec.x
            if (!bi.locked.y) accI.y += factor * bj.mass * rVec.y
            if (!bi.locked.z) accI.z += factor * bj.mass * rVec.z
          }
          if (accJ) {
            if (!bj.locked.x) accJ.x -= factor * bi.mass * rVec.x
            if (!bj.locked.y) accJ.y -= factor * bi.mass * rVec.y
            if (!bj.locked.z) accJ.z -= factor * bi.mass * rVec.z
          }
        }
      }
    }

    return result
  }

  private stepVelocityVerlet(subDt: number) {
    const acc0 = this.evaluateAccelerations()

    for (const body of this.bodies.values()) {
      if (body.kind !== 'dynamic') continue
      const a0 = acc0.get(body.id)
      if (!a0) continue

      if (!body.locked.x) body.velocity.x += 0.5 * a0.linear.x * subDt
      if (!body.locked.y) body.velocity.y += 0.5 * a0.linear.y * subDt
      if (!body.locked.z) body.velocity.z += 0.5 * a0.linear.z * subDt

      if (!body.locked.rx) body.angularVelocity.x += 0.5 * a0.angular.x * subDt
      if (!body.locked.ry) body.angularVelocity.y += 0.5 * a0.angular.y * subDt
      if (!body.locked.rz) body.angularVelocity.z += 0.5 * a0.angular.z * subDt

      if (!body.locked.x) body.position.x += body.velocity.x * subDt
      if (!body.locked.y) body.position.y += body.velocity.y * subDt
      if (!body.locked.z) body.position.z += body.velocity.z * subDt

      if (body.angularVelocity.lengthSq() > 1e-16) {
        integrateQuaternionExponentialMap(body.quaternion, body.angularVelocity, subDt)
      }
    }

    const acc1 = this.evaluateAccelerations()

    for (const body of this.bodies.values()) {
      if (body.kind !== 'dynamic') continue
      const a1 = acc1.get(body.id)
      if (!a1) continue

      if (!body.locked.x) body.velocity.x += 0.5 * a1.linear.x * subDt
      if (!body.locked.y) body.velocity.y += 0.5 * a1.linear.y * subDt
      if (!body.locked.z) body.velocity.z += 0.5 * a1.linear.z * subDt

      if (!body.locked.rx) body.angularVelocity.x += 0.5 * a1.angular.x * subDt
      if (!body.locked.ry) body.angularVelocity.y += 0.5 * a1.angular.y * subDt
      if (!body.locked.rz) body.angularVelocity.z += 0.5 * a1.angular.z * subDt
    }
  }

  private stepYoshida4(subDt: number) {
    for (let stage = 0; stage < 3; stage += 1) {
      const cDt = YOSHIDA4_C[stage] * subDt
      const dDt = YOSHIDA4_D[stage] * subDt

      for (const body of this.bodies.values()) {
        if (body.kind !== 'dynamic') continue
        if (!body.locked.x) body.position.x += body.velocity.x * cDt
        if (!body.locked.y) body.position.y += body.velocity.y * cDt
        if (!body.locked.z) body.position.z += body.velocity.z * cDt
        if (body.angularVelocity.lengthSq() > 1e-16) {
          integrateQuaternionExponentialMap(body.quaternion, body.angularVelocity, cDt)
        }
      }

      const acc = this.evaluateAccelerations()

      for (const body of this.bodies.values()) {
        if (body.kind !== 'dynamic') continue
        const a = acc.get(body.id)
        if (!a) continue
        if (!body.locked.x) body.velocity.x += a.linear.x * dDt
        if (!body.locked.y) body.velocity.y += a.linear.y * dDt
        if (!body.locked.z) body.velocity.z += a.linear.z * dDt
        if (!body.locked.rx) body.angularVelocity.x += a.angular.x * dDt
        if (!body.locked.ry) body.angularVelocity.y += a.angular.y * dDt
        if (!body.locked.rz) body.angularVelocity.z += a.angular.z * dDt
      }
    }

    const c4Dt = YOSHIDA4_C[3] * subDt
    for (const body of this.bodies.values()) {
      if (body.kind !== 'dynamic') continue
      if (!body.locked.x) body.position.x += body.velocity.x * c4Dt
      if (!body.locked.y) body.position.y += body.velocity.y * c4Dt
      if (!body.locked.z) body.position.z += body.velocity.z * c4Dt
      if (body.angularVelocity.lengthSq() > 1e-16) {
        integrateQuaternionExponentialMap(body.quaternion, body.angularVelocity, c4Dt)
      }
    }
  }

  private simulateFixed(dt: number) {
    let hasExternalNonConservativeWork = false
    for (const body of this.bodies.values()) {
      body.externalForce.copy(body.forceAccum)
      body.externalTorque.copy(body.torqueAccum)
      if (body.forceAccum.lengthSq() > 0 || body.torqueAccum.lengthSq() > 0) {
        hasExternalNonConservativeWork = true
      }
      body.forceAccum.set(0, 0, 0)
      body.torqueAccum.set(0, 0, 0)
    }

    let maxSpringStiffness = 0
    for (const s of this.springs.values()) {
      if (s.stiffness > maxSpringStiffness) maxSpringStiffness = s.stiffness
    }

    const bodyDiagnostics = Array.from(this.bodies.values()).map((b) => ({
      kind: b.kind,
      velocity: b.velocity,
      angularVelocity: b.angularVelocity,
      acceleration: {
        x: this.gravity.x * b.gravityScale + b.externalForce.x * b.invMass,
        y: this.gravity.y * b.gravityScale + b.externalForce.y * b.invMass,
        z: this.gravity.z * b.gravityScale + b.externalForce.z * b.invMass,
      },
      characteristicLength: b.characteristicLength,
      mass: b.mass,
    }))

    const cflDiag = computeAdaptiveCflSubsteps(
      dt,
      bodyDiagnostics,
      this.gravity.length(),
      maxSpringStiffness,
      {
        cflTarget: this.cflTarget,
        minSubSteps: this.minSubSteps,
        maxSubSteps: this.maxSubSteps,
      },
    )
    this.lastCflDiagnostic = cflDiag

    if (this.baselineEnergy === null) {
      this.lastInvariants = this.computeMechanicalInvariants()
    }

    const events: ContactEvent[] = []
    let hadInelasticContact = false

    for (let sub = 0; sub < cflDiag.subSteps; sub += 1) {
      const subDt = cflDiag.subDt
      for (const body of this.bodies.values()) {
        if (body.kind === 'dynamic') {
          body.previousPosition.copy(body.position)
        }
      }

      if (this.integratorKind === 'yoshida4') {
        this.stepYoshida4(subDt)
      } else {
        this.stepVelocityVerlet(subDt)
      }

      for (const body of this.bodies.values()) {
        if (body.kind !== 'dynamic') continue
        if (body.linearDamping > 0) {
          const linDamp = Math.exp(-Math.max(0, body.linearDamping) * subDt * 60)
          body.velocity.multiplyScalar(linDamp)
        }
        if (body.angularDamping > 0) {
          const angDamp = Math.exp(-Math.max(0, body.angularDamping) * subDt * 60)
          body.angularVelocity.multiplyScalar(angDamp)
        }
        sanitizeVector3(body.position)
        sanitizeVector3(body.velocity)
        sanitizeVector3(body.angularVelocity)
      }

      const subEvents: ContactEvent[] = []
      const contactOccurred = this.resolveCollisions(subEvents)
      if (contactOccurred) {
        hadInelasticContact = true
        events.push(...subEvents)
      }
    }

    for (const body of this.bodies.values()) {
      body.externalForce.set(0, 0, 0)
      body.externalTorque.set(0, 0, 0)
    }

    if (
      this.enforceConservativeEnergyProjection &&
      !hadInelasticContact &&
      !hasExternalNonConservativeWork &&
      this.baselineEnergy !== null
    ) {
      const invBefore = this.computeMechanicalInvariants()
      if (invBefore.isConservative && invBefore.kineticEnergy > 1e-10) {
        const targetKE = this.baselineEnergy - invBefore.potentialEnergy
        if (targetKE > 0) {
          const ratio = targetKE / invBefore.kineticEnergy
          if (ratio > 0.98 && ratio < 1.02 && Math.abs(ratio - 1) > 1e-12) {
            const scale = Math.sqrt(ratio)
            for (const body of this.bodies.values()) {
              if (body.kind !== 'dynamic') continue
              body.velocity.multiplyScalar(scale)
              body.angularVelocity.multiplyScalar(scale)
            }
          }
        }
      }
    }

    this.lastInvariants = this.computeMechanicalInvariants()
    this.lastContacts = events
    if (events.length > 0 && this.listeners.length > 0) {
      for (const l of this.listeners) l(events)
    }
  }

  private resolveCollisions(events: ContactEvent[]): boolean {
    let anyContact = false
    const list = Array.from(this.bodies.values())
    for (let i = 0; i < list.length; i += 1) {
      for (let j = i + 1; j < list.length; j += 1) {
        const a = list[i]
        const b = list[j]
        if (a.kind === 'static' && b.kind === 'static') continue
        const event = this.detectContact(a, b)
        if (event) {
          this.applyContactResponse(a, b, event)
          events.push(event)
          anyContact = true
        }
      }
    }
    for (const body of list) {
      if (this.applyWorldBounds(body)) {
        anyContact = true
      }
    }
    return anyContact
  }

  private detectContact(a: RigidBodyState, b: RigidBodyState): ContactEvent | null {
    if (a.collider === 'sphere' && b.collider === 'sphere') return this.sphereSphere(a, b)
    if (a.collider === 'plane' || b.collider === 'plane') {
      const plane = a.collider === 'plane' ? a : b
      const other = a.collider === 'plane' ? b : a
      return this.bodyPlane(other, plane)
    }
    if (a.collider === 'sphere' && b.collider === 'box') {
      return this.sphereBox(a, b, false)
    }
    if (a.collider === 'box' && b.collider === 'sphere') {
      return this.sphereBox(b, a, true)
    }
    return this.aabbAabb(a, b)
  }

  private sphereSphere(a: RigidBodyState, b: RigidBodyState): ContactEvent | null {
    const delta = b.position.clone().sub(a.position)
    const dist = delta.length()
    const overlap = a.radius + b.radius - dist
    if (overlap <= 0) return null
    const normal = dist > 1e-6 ? delta.divideScalar(dist) : new Vector3(0, 1, 0)
    const point = a.position.clone().add(normal.clone().multiplyScalar(a.radius - overlap * 0.5))
    return {
      a: a.id,
      b: b.id,
      point: [point.x, point.y, point.z],
      normal: [normal.x, normal.y, normal.z],
      depth: overlap,
      impulse: 0,
    }
  }

  private bodyPlane(body: RigidBodyState, plane: RigidBodyState): ContactEvent | null {
    const planeY = plane.position.y + plane.halfExtents.y
    const effectiveVerticalExtent =
      body.collider === 'sphere' ? body.radius : body.halfExtents.y
    const depth = planeY - (body.position.y - effectiveVerticalExtent)
    if (depth <= 0) return null
    const normal = new Vector3(0, 1, 0)
    const point = new Vector3(body.position.x, plane.position.y, body.position.z)
    return {
      a: body.id,
      b: plane.id,
      point: [point.x, point.y, point.z],
      normal: [normal.x, normal.y, normal.z],
      depth,
      impulse: 0,
    }
  }

  private sphereBox(sphere: RigidBodyState, box: RigidBodyState, invertedOrder: boolean): ContactEvent | null {
    const qBoxInv = box.quaternion.clone().invert()
    const localCenter = sphere.position.clone().sub(box.position).applyQuaternion(qBoxInv)

    const hx = box.halfExtents.x
    const hy = box.halfExtents.y
    const hz = box.halfExtents.z

    const closestLocal = new Vector3(
      Math.max(-hx, Math.min(hx, localCenter.x)),
      Math.max(-hy, Math.min(hy, localCenter.y)),
      Math.max(-hz, Math.min(hz, localCenter.z)),
    )

    const diffLocal = localCenter.clone().sub(closestLocal)
    const distSq = diffLocal.lengthSq()
    const r = sphere.radius

    if (distSq > r * r) return null

    let normalLocal: Vector3
    let depth: number
    if (distSq > 1e-10) {
      const dist = Math.sqrt(distSq)
      normalLocal = diffLocal.divideScalar(-dist)
      depth = r - dist
    } else {
      const dx = hx - Math.abs(localCenter.x)
      const dy = hy - Math.abs(localCenter.y)
      const dz = hz - Math.abs(localCenter.z)
      if (dx <= dy && dx <= dz) {
        normalLocal = new Vector3(localCenter.x >= 0 ? -1 : 1, 0, 0)
        depth = dx + r
      } else if (dy <= dz) {
        normalLocal = new Vector3(0, localCenter.y >= 0 ? -1 : 1, 0)
        depth = dy + r
      } else {
        normalLocal = new Vector3(0, 0, localCenter.z >= 0 ? -1 : 1)
        depth = dz + r
      }
    }

    const normalWorld = normalLocal.applyQuaternion(box.quaternion).normalize()
    const pointWorld = closestLocal.applyQuaternion(box.quaternion).add(box.position)
    if (invertedOrder) {
      normalWorld.negate()
      return {
        a: box.id,
        b: sphere.id,
        point: [pointWorld.x, pointWorld.y, pointWorld.z],
        normal: [normalWorld.x, normalWorld.y, normalWorld.z],
        depth,
        impulse: 0,
      }
    }
    return {
      a: sphere.id,
      b: box.id,
      point: [pointWorld.x, pointWorld.y, pointWorld.z],
      normal: [normalWorld.x, normalWorld.y, normalWorld.z],
      depth,
      impulse: 0,
    }
  }

  private aabbAabb(a: RigidBodyState, b: RigidBodyState): ContactEvent | null {
    const dx = b.position.x - a.position.x
    const dy = b.position.y - a.position.y
    const dz = b.position.z - a.position.z
    const ox = a.halfExtents.x + b.halfExtents.x - Math.abs(dx)
    const oy = a.halfExtents.y + b.halfExtents.y - Math.abs(dy)
    const oz = a.halfExtents.z + b.halfExtents.z - Math.abs(dz)
    if (ox <= 0 || oy <= 0 || oz <= 0) return null
    let normal: Vector3
    let depth: number
    if (ox < oy && ox < oz) {
      normal = new Vector3(Math.sign(dx) || 1, 0, 0)
      depth = ox
    } else if (oy < oz) {
      normal = new Vector3(0, Math.sign(dy) || 1, 0)
      depth = oy
    } else {
      normal = new Vector3(0, 0, Math.sign(dz) || 1)
      depth = oz
    }
    const point = a.position.clone().add(b.position).multiplyScalar(0.5)
    return {
      a: a.id,
      b: b.id,
      point: [point.x, point.y, point.z],
      normal: [normal.x, normal.y, normal.z],
      depth,
      impulse: 0,
    }
  }

  private applyContactResponse(a: RigidBodyState, b: RigidBodyState, event: ContactEvent) {
    const n = new Vector3(event.normal[0], event.normal[1], event.normal[2])
    const ab = b.position.clone().sub(a.position)
    if (ab.dot(n) < 0) {
      n.negate()
      event.normal = [n.x, n.y, n.z]
    }

    const invMassSum = a.invMass + b.invMass
    if (invMassSum <= 0) return

    const slop = 1e-4
    const baumgarte = 0.8
    const corrMag = (Math.max(0, event.depth - slop) / invMassSum) * baumgarte
    if (a.invMass > 0) {
      if (!a.locked.x) a.position.x -= n.x * corrMag * a.invMass
      if (!a.locked.y) a.position.y -= n.y * corrMag * a.invMass
      if (!a.locked.z) a.position.z -= n.z * corrMag * a.invMass
    }
    if (b.invMass > 0) {
      if (!b.locked.x) b.position.x += n.x * corrMag * b.invMass
      if (!b.locked.y) b.position.y += n.y * corrMag * b.invMass
      if (!b.locked.z) b.position.z += n.z * corrMag * b.invMass
    }

    const contactPoint = new Vector3(event.point[0], event.point[1], event.point[2])
    const ra = contactPoint.clone().sub(a.position)
    const rb = contactPoint.clone().sub(b.position)

    const vaContact = a.velocity.clone().add(new Vector3().crossVectors(a.angularVelocity, ra))
    const vbContact = b.velocity.clone().add(new Vector3().crossVectors(b.angularVelocity, rb))
    const relVel = vbContact.sub(vaContact)
    const velAlongNormal = relVel.dot(n)
    if (velAlongNormal > 0) return

    const raCrossN = new Vector3().crossVectors(ra, n)
    const rbCrossN = new Vector3().crossVectors(rb, n)
    const angTermA = new Vector3().crossVectors(applyWorldInverseInertia(a, raCrossN), ra).dot(n)
    const angTermB = new Vector3().crossVectors(applyWorldInverseInertia(b, rbCrossN), rb).dot(n)
    const effectiveInvMassNormal = Math.max(1e-12, invMassSum + Math.max(0, angTermA) + Math.max(0, angTermB))

    const e = Math.abs(velAlongNormal) < 0.05 ? 0 : Math.min(a.restitution, b.restitution)
    const jScalar = (-(1 + e) * velAlongNormal) / effectiveInvMassNormal
    const impulse = n.clone().multiplyScalar(jScalar)

    if (a.invMass > 0) {
      if (!a.locked.x) a.velocity.x -= impulse.x * a.invMass
      if (!a.locked.y) a.velocity.y -= impulse.y * a.invMass
      if (!a.locked.z) a.velocity.z -= impulse.z * a.invMass
      const dOmegaA = applyWorldInverseInertia(a, new Vector3().crossVectors(ra, impulse))
      a.angularVelocity.sub(dOmegaA)
    }
    if (b.invMass > 0) {
      if (!b.locked.x) b.velocity.x += impulse.x * b.invMass
      if (!b.locked.y) b.velocity.y += impulse.y * b.invMass
      if (!b.locked.z) b.velocity.z += impulse.z * b.invMass
      const dOmegaB = applyWorldInverseInertia(b, new Vector3().crossVectors(rb, impulse))
      b.angularVelocity.add(dOmegaB)
    }

    const tangent = relVel.clone().addScaledVector(n, -velAlongNormal)
    if (tangent.lengthSq() > 1e-10) {
      tangent.normalize()
      const raCrossT = new Vector3().crossVectors(ra, tangent)
      const rbCrossT = new Vector3().crossVectors(rb, tangent)
      const angTanA = new Vector3().crossVectors(applyWorldInverseInertia(a, raCrossT), ra).dot(tangent)
      const angTanB = new Vector3().crossVectors(applyWorldInverseInertia(b, rbCrossT), rb).dot(tangent)
      const effectiveInvMassTangent = Math.max(1e-12, invMassSum + Math.max(0, angTanA) + Math.max(0, angTanB))

      const jt = -relVel.dot(tangent) / effectiveInvMassTangent
      const mu = Math.sqrt(Math.max(0, a.friction) * Math.max(0, b.friction))
      const maxFriction = Math.abs(jScalar) * mu
      const clampedJt = Math.max(-maxFriction, Math.min(maxFriction, jt))
      const frictionImpulse = tangent.multiplyScalar(clampedJt)

      if (a.invMass > 0) {
        if (!a.locked.x) a.velocity.x -= frictionImpulse.x * a.invMass
        if (!a.locked.y) a.velocity.y -= frictionImpulse.y * a.invMass
        if (!a.locked.z) a.velocity.z -= frictionImpulse.z * a.invMass
        const dOmegaTanA = applyWorldInverseInertia(a, new Vector3().crossVectors(ra, frictionImpulse))
        a.angularVelocity.sub(dOmegaTanA)
      }
      if (b.invMass > 0) {
        if (!b.locked.x) b.velocity.x += frictionImpulse.x * b.invMass
        if (!b.locked.y) b.velocity.y += frictionImpulse.y * b.invMass
        if (!b.locked.z) b.velocity.z += frictionImpulse.z * b.invMass
        const dOmegaTanB = applyWorldInverseInertia(b, new Vector3().crossVectors(rb, frictionImpulse))
        b.angularVelocity.add(dOmegaTanB)
      }
    }
    event.impulse = jScalar
  }

  private applyWorldBounds(body: RigidBodyState): boolean {
    const floor = this.potentialReferenceY
    const extentY = body.collider === 'sphere' ? body.radius : body.halfExtents.y
    if (body.position.y < floor + extentY && body.kind === 'dynamic') {
      body.position.y = floor + extentY
      const inelastic = body.restitution < 1 || body.friction > 0
      if (body.velocity.y < 0) {
        body.velocity.y = -body.velocity.y * body.restitution
      }
      if (body.friction > 0) {
        body.velocity.x *= Math.max(0, 1 - body.friction * 0.1)
        body.velocity.z *= Math.max(0, 1 - body.friction * 0.1)
      }
      return inelastic
    }
    return false
  }
}

export function computeConvexHullBounds(points: Vec3[]): { center: Vec3; halfExtents: Vec3 } {
  if (points.length === 0) return { center: [0, 0, 0], halfExtents: [0.5, 0.5, 0.5] }
  const box = new Box3()
  for (const p of points) box.expandByPoint(new Vector3(p[0], p[1], p[2]))
  const center = box.getCenter(new Vector3())
  const size = box.getSize(new Vector3())
  return { center: [center.x, center.y, center.z], halfExtents: [size.x / 2, size.y / 2, size.z / 2] }
}

export function applyQuaternionToVector(q: [number, number, number, number], v: Vec3): Vec3 {
  const m = new Matrix4().makeRotationFromQuaternion(new Quaternion(q[0], q[1], q[2], q[3]))
  const vec = new Vector3(v[0], v[1], v[2]).applyMatrix4(m)
  return [vec.x, vec.y, vec.z]
}
