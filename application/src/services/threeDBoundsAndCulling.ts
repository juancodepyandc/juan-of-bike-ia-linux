// Bounding volumes + frustum culling, sans Three.js. Utile pour :
//   - décider quels meshes envoyer au shader vs skip (cull invisible)
//   - estimer la collision broad-phase (AABB-AABB rapide avant precise mesh)
//   - calculer la sphère englobante minimale (Ritter ~ 1990)
//   - intersection ray-AABB (slab method, picking 3D)
//
// Pure math TS. Aucune dépendance.

export type Vec3 = [number, number, number]

export type AABB = {
  min: Vec3
  max: Vec3
}

export type Sphere = {
  center: Vec3
  radius: number
}

export type Frustum = {
  /** 6 plans : near, far, left, right, top, bottom. Chaque plan = (a,b,c,d) avec ax+by+cz+d=0. */
  planes: Array<[number, number, number, number]>
}

export function aabbFromPoints(points: Vec3[]): AABB {
  if (points.length === 0) {
    return { min: [0, 0, 0], max: [0, 0, 0] }
  }
  const min: Vec3 = [Infinity, Infinity, Infinity]
  const max: Vec3 = [-Infinity, -Infinity, -Infinity]
  for (const p of points) {
    for (let i = 0; i < 3; i += 1) {
      if (p[i] < min[i]) min[i] = p[i]
      if (p[i] > max[i]) max[i] = p[i]
    }
  }
  return { min, max }
}

export function aabbCenter(box: AABB): Vec3 {
  return [
    (box.min[0] + box.max[0]) / 2,
    (box.min[1] + box.max[1]) / 2,
    (box.min[2] + box.max[2]) / 2,
  ]
}

export function aabbExtents(box: AABB): Vec3 {
  return [
    (box.max[0] - box.min[0]) / 2,
    (box.max[1] - box.min[1]) / 2,
    (box.max[2] - box.min[2]) / 2,
  ]
}

export function aabbVolume(box: AABB): number {
  return (box.max[0] - box.min[0]) * (box.max[1] - box.min[1]) * (box.max[2] - box.min[2])
}

/** Test AABB-AABB pour broad-phase collision detection. O(1). */
export function aabbIntersect(a: AABB, b: AABB): boolean {
  return a.min[0] <= b.max[0] && a.max[0] >= b.min[0]
    && a.min[1] <= b.max[1] && a.max[1] >= b.min[1]
    && a.min[2] <= b.max[2] && a.max[2] >= b.min[2]
}

/** Union de 2 AABB. */
export function aabbUnion(a: AABB, b: AABB): AABB {
  return {
    min: [Math.min(a.min[0], b.min[0]), Math.min(a.min[1], b.min[1]), Math.min(a.min[2], b.min[2])],
    max: [Math.max(a.max[0], b.max[0]), Math.max(a.max[1], b.max[1]), Math.max(a.max[2], b.max[2])],
  }
}

/**
 * Sphère englobante par algo de Ritter — pas le minimum absolu mais O(N)
 * et < 5 % d'overhead.
 */
export function sphereFromPoints(points: Vec3[]): Sphere {
  if (points.length === 0) return { center: [0, 0, 0], radius: 0 }
  // Étape 1 : trouve le point le plus éloigné d'un point quelconque.
  const p0 = points[0]
  let maxDistSq = 0
  let p1 = p0
  for (const p of points) {
    const d = sqDist(p, p0)
    if (d > maxDistSq) {
      maxDistSq = d
      p1 = p
    }
  }
  // Étape 2 : trouve le point le plus éloigné de p1 → p2.
  maxDistSq = 0
  let p2 = p1
  for (const p of points) {
    const d = sqDist(p, p1)
    if (d > maxDistSq) {
      maxDistSq = d
      p2 = p
    }
  }
  // Sphère initiale : centre = milieu(p1, p2), rayon = ‖p1-p2‖/2.
  let center: Vec3 = [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, (p1[2] + p2[2]) / 2]
  let radius = Math.sqrt(maxDistSq) / 2
  // Étape 3 : étend la sphère pour englober tout point qui en sort.
  for (const p of points) {
    const d = Math.sqrt(sqDist(p, center))
    if (d > radius) {
      const newRadius = (radius + d) / 2
      const ratio = (newRadius - radius) / d
      center = [
        center[0] + (p[0] - center[0]) * ratio,
        center[1] + (p[1] - center[1]) * ratio,
        center[2] + (p[2] - center[2]) * ratio,
      ]
      radius = newRadius
    }
  }
  return { center, radius }
}

function sqDist(a: Vec3, b: Vec3): number {
  return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
}

/**
 * Test point-dans-frustum : retourne true si le point est dans les 6 plans.
 * Plans : (a, b, c, d) tel que ax + by + cz + d ≥ 0 = dedans.
 */
export function pointInFrustum(p: Vec3, frustum: Frustum): boolean {
  for (const [a, b, c, d] of frustum.planes) {
    if (a * p[0] + b * p[1] + c * p[2] + d < 0) return false
  }
  return true
}

/**
 * Test AABB-Frustum : conservative, retourne true si l'AABB peut être
 * visible (peut produire de faux positifs mais jamais de faux négatifs).
 */
export function aabbInFrustum(box: AABB, frustum: Frustum): boolean {
  const center = aabbCenter(box)
  const extents = aabbExtents(box)
  for (const [a, b, c, d] of frustum.planes) {
    // Distance signée du centre au plan.
    const dist = a * center[0] + b * center[1] + c * center[2] + d
    // Rayon projeté de la AABB sur la normale du plan.
    const projRadius = Math.abs(a) * extents[0] + Math.abs(b) * extents[1] + Math.abs(c) * extents[2]
    if (dist + projRadius < 0) return false // entièrement derrière → cull
  }
  return true
}

/**
 * Intersection rayon-AABB (méthode "slab"). Retourne la distance t > 0
 * la plus proche ou null si pas d'intersection.
 */
export function rayAabbIntersect(origin: Vec3, direction: Vec3, box: AABB): number | null {
  let tMin = -Infinity
  let tMax = Infinity
  for (let i = 0; i < 3; i += 1) {
    if (Math.abs(direction[i]) < 1e-9) {
      if (origin[i] < box.min[i] || origin[i] > box.max[i]) return null
    } else {
      let t1 = (box.min[i] - origin[i]) / direction[i]
      let t2 = (box.max[i] - origin[i]) / direction[i]
      if (t1 > t2) { const tmp = t1; t1 = t2; t2 = tmp }
      if (t1 > tMin) tMin = t1
      if (t2 < tMax) tMax = t2
      if (tMin > tMax) return null
    }
  }
  return tMin >= 0 ? tMin : (tMax >= 0 ? 0 : null)
}

/**
 * Build un frustum standard depuis une matrice ViewProjection (16 floats,
 * row-major). Extrait les 6 plans par la méthode Gribb-Hartmann (2001).
 */
export function frustumFromMatrix(m: number[]): Frustum {
  if (m.length !== 16) throw new Error('frustumFromMatrix: 16-element matrix required')
  // Indexation row-major : m[row * 4 + col].
  const i = (r: number, c: number) => m[r * 4 + c]
  const planes: Array<[number, number, number, number]> = [
    [i(3, 0) + i(0, 0), i(3, 1) + i(0, 1), i(3, 2) + i(0, 2), i(3, 3) + i(0, 3)], // left
    [i(3, 0) - i(0, 0), i(3, 1) - i(0, 1), i(3, 2) - i(0, 2), i(3, 3) - i(0, 3)], // right
    [i(3, 0) + i(1, 0), i(3, 1) + i(1, 1), i(3, 2) + i(1, 2), i(3, 3) + i(1, 3)], // bottom
    [i(3, 0) - i(1, 0), i(3, 1) - i(1, 1), i(3, 2) - i(1, 2), i(3, 3) - i(1, 3)], // top
    [i(3, 0) + i(2, 0), i(3, 1) + i(2, 1), i(3, 2) + i(2, 2), i(3, 3) + i(2, 3)], // near
    [i(3, 0) - i(2, 0), i(3, 1) - i(2, 1), i(3, 2) - i(2, 2), i(3, 3) - i(2, 3)], // far
  ]
  // Normalise.
  const normed: Array<[number, number, number, number]> = planes.map(([a, b, c, d]) => {
    const len = Math.hypot(a, b, c) || 1
    return [a / len, b / len, c / len, d / len]
  })
  return { planes: normed }
}
