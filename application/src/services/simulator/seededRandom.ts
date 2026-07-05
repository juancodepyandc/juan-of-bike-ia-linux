// Seeded RNG for the simulator — replaces Math.random() in any code path
// expected to be deterministic (particle emission, chemistry sparks…).
// Matches the simulator CLAUDE.md rule: same seed + same scene → same trajectory.
//
// Implementation: mulberry32. ~31 bits of state, period 2^32, statistically
// equivalent to PCG-XSH-RR for our use (visual jitter, sampling), and tiny
// enough to inline. For cryptography you'd want a real CSPRNG — not the case
// here.

export type RngState = { s: number }

/** Build a 32-bit seed from a string (FNV-1a). */
export function hashSeed(input: string): number {
  let h = 0x811c9dc5
  for (let i = 0; i < input.length; i += 1) {
    h ^= input.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}

export function createRng(seed: number | string = 1): RngState {
  const n = typeof seed === 'string' ? hashSeed(seed) : Math.floor(seed)
  // Avoid 0 — mulberry32 produces a trivial cycle there.
  return { s: (n || 0x9e3779b9) >>> 0 }
}

/** Uniform in [0, 1). */
export function nextFloat(rng: RngState): number {
  rng.s = (rng.s + 0x6d2b79f5) >>> 0
  let t = rng.s
  t = Math.imul(t ^ (t >>> 15), t | 1)
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296
}

/** Uniform integer in [min, max] inclusive. */
export function nextInt(rng: RngState, min: number, max: number): number {
  const lo = Math.ceil(min)
  const hi = Math.floor(max)
  if (hi < lo) throw new Error('nextInt: empty range')
  return lo + Math.floor(nextFloat(rng) * (hi - lo + 1))
}

/** Uniform in [a, b). */
export function nextRange(rng: RngState, a: number, b: number): number {
  return a + (b - a) * nextFloat(rng)
}

/** Standard normal via Box-Muller. Returns one sample per call. */
export function nextGaussian(rng: RngState, mean = 0, stdDev = 1): number {
  // Reject u1=0 to avoid log(0).
  let u1 = nextFloat(rng)
  if (u1 < 1e-12) u1 = 1e-12
  const u2 = nextFloat(rng)
  const mag = Math.sqrt(-2 * Math.log(u1))
  return mean + stdDev * mag * Math.cos(2 * Math.PI * u2)
}

/** Uniform unit vector on the 3D sphere (Marsaglia). */
export function nextUnitVec3(rng: RngState): [number, number, number] {
  while (true) {
    const x1 = nextFloat(rng) * 2 - 1
    const x2 = nextFloat(rng) * 2 - 1
    const s = x1 * x1 + x2 * x2
    if (s >= 1 || s === 0) continue
    const f = 2 * Math.sqrt(1 - s)
    return [x1 * f, x2 * f, 1 - 2 * s]
  }
}

/** Pick one element uniformly. */
export function pick<T>(rng: RngState, items: readonly T[]): T {
  if (items.length === 0) throw new Error('pick: empty')
  return items[Math.floor(nextFloat(rng) * items.length)]
}

/** In-place Fisher-Yates shuffle. */
export function shuffle<T>(rng: RngState, items: T[]): T[] {
  for (let i = items.length - 1; i > 0; i -= 1) {
    const j = Math.floor(nextFloat(rng) * (i + 1))
    const tmp = items[i]
    items[i] = items[j]
    items[j] = tmp
  }
  return items
}
