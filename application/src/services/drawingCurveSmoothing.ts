// Bezier path tools : conversion d'une polyline (croquis tactile) en
// suite de courbes Bezier cubiques lisses + simplification Ramer-Douglas-
// Peucker pour réduire les nœuds tout en préservant la forme.
//
// Pure math TS. Pas de canvas.

export type Point = { x: number; y: number }

/**
 * Ramer-Douglas-Peucker : simplifie une polyline en ne gardant que les
 * points significatifs (distance perpendiculaire > epsilon).
 */
export function rdp(points: Point[], epsilon: number): Point[] {
  if (points.length < 3) return points.slice()
  return rdpRecursive(points, 0, points.length - 1, epsilon)
}

function rdpRecursive(points: Point[], first: number, last: number, epsilon: number): Point[] {
  let maxDist = 0
  let maxIdx = first
  for (let i = first + 1; i < last; i += 1) {
    const d = perpendicularDistance(points[i], points[first], points[last])
    if (d > maxDist) {
      maxDist = d
      maxIdx = i
    }
  }
  if (maxDist > epsilon) {
    const left = rdpRecursive(points, first, maxIdx, epsilon)
    const right = rdpRecursive(points, maxIdx, last, epsilon)
    return [...left.slice(0, -1), ...right]
  }
  return [points[first], points[last]]
}

function perpendicularDistance(p: Point, a: Point, b: Point): number {
  const dx = b.x - a.x
  const dy = b.y - a.y
  if (dx === 0 && dy === 0) return Math.hypot(p.x - a.x, p.y - a.y)
  const t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy)
  const tClamped = Math.max(0, Math.min(1, t))
  const projX = a.x + tClamped * dx
  const projY = a.y + tClamped * dy
  return Math.hypot(p.x - projX, p.y - projY)
}

// --- Catmull-Rom → Bezier --------------------------------------------------
//
// On convertit une polyline (points) en spline lisse via Catmull-Rom puis on
// la transcrit en suite de courbes Bezier cubiques pour SVG.

export type CubicBezier = {
  start: Point
  control1: Point
  control2: Point
  end: Point
}

/**
 * Convertit une polyline en N-1 courbes cubic Bezier qui passent par tous
 * les points. Utilise Catmull-Rom (tension τ = 0.5 = uniform Catmull-Rom).
 */
export function polylineToBeziers(points: Point[], tension = 0.5): CubicBezier[] {
  if (points.length < 2) return []
  if (points.length === 2) {
    // Ligne droite → Bezier dégénéré (control = endpoints).
    return [{ start: points[0], control1: points[0], control2: points[1], end: points[1] }]
  }
  const beziers: CubicBezier[] = []
  // Pad : ajoute virtuellement P[-1] = P[0] et P[N] = P[N-1] (extrapolation
  // simple pour les segments aux extrémités).
  const pad = (i: number) => {
    if (i < 0) return points[0]
    if (i >= points.length) return points[points.length - 1]
    return points[i]
  }
  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = pad(i - 1)
    const p1 = points[i]
    const p2 = points[i + 1]
    const p3 = pad(i + 2)
    const c1 = {
      x: p1.x + (p2.x - p0.x) * tension / 3,
      y: p1.y + (p2.y - p0.y) * tension / 3,
    }
    const c2 = {
      x: p2.x - (p3.x - p1.x) * tension / 3,
      y: p2.y - (p3.y - p1.y) * tension / 3,
    }
    beziers.push({ start: p1, control1: c1, control2: c2, end: p2 })
  }
  return beziers
}

/**
 * Sérialise une suite de Beziers en path SVG.
 *   M start.x start.y C c1.x c1.y c2.x c2.y end.x end.y ...
 */
export function beziersToSvgPath(beziers: CubicBezier[]): string {
  if (beziers.length === 0) return ''
  const f = (n: number) => Number(n.toFixed(2))
  const head = `M ${f(beziers[0].start.x)} ${f(beziers[0].start.y)}`
  const segs = beziers.map((b) =>
    `C ${f(b.control1.x)} ${f(b.control1.y)} ${f(b.control2.x)} ${f(b.control2.y)} ${f(b.end.x)} ${f(b.end.y)}`,
  ).join(' ')
  return `${head} ${segs}`.trim()
}

/**
 * Évalue une courbe Bezier cubique à t ∈ [0..1].
 */
export function bezierPoint(curve: CubicBezier, t: number): Point {
  const it = 1 - t
  const x = it ** 3 * curve.start.x + 3 * it ** 2 * t * curve.control1.x + 3 * it * t ** 2 * curve.control2.x + t ** 3 * curve.end.x
  const y = it ** 3 * curve.start.y + 3 * it ** 2 * t * curve.control1.y + 3 * it * t ** 2 * curve.control2.y + t ** 3 * curve.end.y
  return { x, y }
}

/**
 * Longueur approximée d'une courbe Bezier cubique par adaptive subdivision.
 */
export function bezierLength(curve: CubicBezier, segments = 32): number {
  let total = 0
  let prev = curve.start
  for (let i = 1; i <= segments; i += 1) {
    const t = i / segments
    const cur = bezierPoint(curve, t)
    total += Math.hypot(cur.x - prev.x, cur.y - prev.y)
    prev = cur
  }
  return total
}

// --- Pipeline complet ------------------------------------------------------

/**
 * Convertit un croquis brut (polyline tactile) en SVG path lisse :
 *   1. RDP pour réduire le nombre de points
 *   2. Catmull-Rom → Beziers
 *   3. sérialise en path "d" attribute SVG.
 */
export type SmoothOptions = {
  /** Tolérance RDP (px). Plus élevé = plus simplifié. */
  epsilon?: number
  /** Tension Catmull-Rom. */
  tension?: number
}

export function smoothPolyline(points: Point[], opts: SmoothOptions = {}): { path: string; simplifiedPoints: Point[]; beziers: CubicBezier[] } {
  const eps = opts.epsilon ?? 2
  const tension = opts.tension ?? 0.5
  const simplified = rdp(points, eps)
  const beziers = polylineToBeziers(simplified, tension)
  return {
    path: beziersToSvgPath(beziers),
    simplifiedPoints: simplified,
    beziers,
  }
}
