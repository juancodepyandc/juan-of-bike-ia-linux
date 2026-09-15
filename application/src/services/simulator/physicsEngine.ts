import { Box3, Euler, Matrix4, Quaternion, Vector3 } from 'three'
import type { ColliderShape, PhysicsBody, SceneEntity, Vec3 } from './types.ts'

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
  locked: PhysicsBody['locked']
  forceAccum: Vector3
  torqueAccum: Vector3
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

export class PhysicsEngine {
  private bodies = new Map<string, RigidBodyState>()
  private gravity = new Vector3(0, -9.81, 0)
  private globalDamping = 0.999
  private accumulator = 0
  private fixedDt = 1 / 120
  private subSteps = 2
  private listeners: Array<(events: ContactEvent[]) => void> = []
  private lastContacts: ContactEvent[] = []

  setGravity(value: Vec3) {
    this.gravity.set(value[0], value[1], value[2])
  }

  getGravity(): Vector3 {
    return this.gravity.clone()
  }

  onContacts(fn: (events: ContactEvent[]) => void) {
    this.listeners.push(fn)
    return () => {
      this.listeners = this.listeners.filter((l) => l !== fn)
    }
  }

  reset() {
    this.bodies.clear()
    this.lastContacts = []
    this.accumulator = 0
  }

  syncFromEntities(entities: SceneEntity[]) {
    const seen = new Set<string>()
    for (const entity of entities) {
      if (!entity.physics || !entity.physics.enabled) continue
      seen.add(entity.id)
      let body = this.bodies.get(entity.id)
      if (!body) {
        body = this.makeBody(entity)
        this.bodies.set(entity.id, body)
      } else {
        this.updateBodyConfig(body, entity)
      }
    }
    for (const id of Array.from(this.bodies.keys())) {
      if (!seen.has(id)) this.bodies.delete(id)
    }
  }

  applyForce(id: string, force: Vec3) {
    const b = this.bodies.get(id)
    if (!b || b.kind !== 'dynamic') return
    b.forceAccum.x += force[0]
    b.forceAccum.y += force[1]
    b.forceAccum.z += force[2]
  }

  applyImpulse(id: string, impulse: Vec3) {
    const b = this.bodies.get(id)
    if (!b || b.kind !== 'dynamic') return
    b.velocity.x += impulse[0] * b.invMass
    b.velocity.y += impulse[1] * b.invMass
    b.velocity.z += impulse[2] * b.invMass
  }

  step(dt: number) {
    const clamped = Math.min(dt, 0.05)
    this.accumulator += clamped
    let ticks = 0
    while (this.accumulator >= this.fixedDt && ticks < 10) {
      this.simulateFixed(this.fixedDt)
      this.accumulator -= this.fixedDt
      ticks += 1
    }
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

  private makeBody(entity: SceneEntity): RigidBodyState {
    const phys = entity.physics!
    const invMass = phys.kind === 'dynamic' && phys.mass > 0 ? 1 / phys.mass : 0
    const halfExtents = this.computeHalfExtents(entity)
    const radius = Math.max(halfExtents.x, halfExtents.y, halfExtents.z)
    const inertia = this.computeInertia(phys, halfExtents, radius)
    const quaternion = new Quaternion().setFromEuler(new Euler(entity.transform.rotation[0], entity.transform.rotation[1], entity.transform.rotation[2], 'XYZ'))
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
      locked: { ...phys.locked },
      forceAccum: new Vector3(),
      torqueAccum: new Vector3(),
      inertia,
      invInertia: new Vector3(inertia.x > 0 ? 1 / inertia.x : 0, inertia.y > 0 ? 1 / inertia.y : 0, inertia.z > 0 ? 1 / inertia.z : 0),
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
    const hx = halfExtents.x, hy = halfExtents.y, hz = halfExtents.z
    const m = phys.mass / 3
    return new Vector3(m * (hy * hy + hz * hz), m * (hx * hx + hz * hz), m * (hx * hx + hy * hy))
  }

  private simulateFixed(dt: number) {
    const events: ContactEvent[] = []
    for (let sub = 0; sub < this.subSteps; sub += 1) {
      const subDt = dt / this.subSteps
      for (const body of this.bodies.values()) {
        if (body.kind !== 'dynamic') continue
        body.previousPosition.copy(body.position)
        const ax = this.gravity.x * body.gravityScale + body.forceAccum.x * body.invMass
        const ay = this.gravity.y * body.gravityScale + body.forceAccum.y * body.invMass
        const az = this.gravity.z * body.gravityScale + body.forceAccum.z * body.invMass
        if (!body.locked.x) body.velocity.x += ax * subDt
        if (!body.locked.y) body.velocity.y += ay * subDt
        if (!body.locked.z) body.velocity.z += az * subDt
        const linDamp = Math.pow(1 - body.linearDamping, subDt * 60)
        body.velocity.multiplyScalar(linDamp * this.globalDamping)
        if (!body.locked.x) body.position.x += body.velocity.x * subDt
        if (!body.locked.y) body.position.y += body.velocity.y * subDt
        if (!body.locked.z) body.position.z += body.velocity.z * subDt
        const angDamp = Math.pow(1 - body.angularDamping, subDt * 60)
        body.angularVelocity.multiplyScalar(angDamp)
        if (body.angularVelocity.lengthSq() > 1e-9) {
          const omega = body.angularVelocity.clone().multiplyScalar(subDt)
          const dq = new Quaternion(omega.x * 0.5, omega.y * 0.5, omega.z * 0.5, 0).multiply(body.quaternion)
          body.quaternion.x += dq.x
          body.quaternion.y += dq.y
          body.quaternion.z += dq.z
          body.quaternion.w += dq.w
          body.quaternion.normalize()
        }
        body.forceAccum.set(0, 0, 0)
        body.torqueAccum.set(0, 0, 0)
      }
      this.resolveCollisions(events)
    }
    this.lastContacts = events
    if (events.length > 0 && this.listeners.length > 0) {
      for (const l of this.listeners) l(events)
    }
  }

  private resolveCollisions(events: ContactEvent[]) {
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
        }
      }
    }
    for (const body of list) {
      this.applyWorldBounds(body)
    }
  }

  private detectContact(a: RigidBodyState, b: RigidBodyState): ContactEvent | null {
    if (a.collider === 'sphere' && b.collider === 'sphere') return this.sphereSphere(a, b)
    if (a.collider === 'plane' || b.collider === 'plane') {
      const plane = a.collider === 'plane' ? a : b
      const other = a.collider === 'plane' ? b : a
      return this.spherePlane(other, plane)
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
    return { a: a.id, b: b.id, point: [point.x, point.y, point.z], normal: [normal.x, normal.y, normal.z], depth: overlap, impulse: 0 }
  }

  private spherePlane(body: RigidBodyState, plane: RigidBodyState): ContactEvent | null {
    const planeY = plane.position.y
    const depth = (planeY + plane.halfExtents.y) - (body.position.y - body.radius)
    if (depth <= 0) return null
    const normal = new Vector3(0, 1, 0)
    const point = new Vector3(body.position.x, planeY, body.position.z)
    return { a: body.id, b: plane.id, point: [point.x, point.y, point.z], normal: [normal.x, normal.y, normal.z], depth, impulse: 0 }
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
    if (ox < oy && ox < oz) { normal = new Vector3(Math.sign(dx) || 1, 0, 0); depth = ox }
    else if (oy < oz) { normal = new Vector3(0, Math.sign(dy) || 1, 0); depth = oy }
    else { normal = new Vector3(0, 0, Math.sign(dz) || 1); depth = oz }
    const point = a.position.clone().add(b.position).multiplyScalar(0.5)
    return { a: a.id, b: b.id, point: [point.x, point.y, point.z], normal: [normal.x, normal.y, normal.z], depth, impulse: 0 }
  }

  private applyContactResponse(a: RigidBodyState, b: RigidBodyState, event: ContactEvent) {
    const n = new Vector3(event.normal[0], event.normal[1], event.normal[2])
    const invMassSum = a.invMass + b.invMass
    if (invMassSum <= 0) return
    const correction = (event.depth / invMassSum) * 0.8
    if (a.invMass > 0) a.position.addScaledVector(n, -correction * a.invMass)
    if (b.invMass > 0) b.position.addScaledVector(n, correction * b.invMass)
    const relVel = b.velocity.clone().sub(a.velocity)
    const velAlongNormal = relVel.dot(n)
    if (velAlongNormal > 0) return
    const e = Math.min(a.restitution, b.restitution)
    const jScalar = -(1 + e) * velAlongNormal / invMassSum
    const impulse = n.clone().multiplyScalar(jScalar)
    if (a.invMass > 0) a.velocity.addScaledVector(impulse, -a.invMass)
    if (b.invMass > 0) b.velocity.addScaledVector(impulse, b.invMass)
    const tangent = relVel.clone().addScaledVector(n, -velAlongNormal)
    if (tangent.lengthSq() > 1e-8) {
      tangent.normalize()
      const jt = -relVel.dot(tangent) / invMassSum
      const mu = Math.sqrt(a.friction * b.friction)
      const clampedJt = Math.max(-Math.abs(jScalar) * mu, Math.min(Math.abs(jScalar) * mu, jt))
      const frictionImpulse = tangent.multiplyScalar(clampedJt)
      if (a.invMass > 0) a.velocity.addScaledVector(frictionImpulse, -a.invMass)
      if (b.invMass > 0) b.velocity.addScaledVector(frictionImpulse, b.invMass)
    }
    event.impulse = jScalar
  }

  private applyWorldBounds(body: RigidBodyState) {
    const floor = -5
    if (body.position.y < floor + body.radius && body.kind === 'dynamic') {
      body.position.y = floor + body.radius
      if (body.velocity.y < 0) body.velocity.y = -body.velocity.y * body.restitution
      body.velocity.x *= 1 - body.friction * 0.1
      body.velocity.z *= 1 - body.friction * 0.1
    }
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
