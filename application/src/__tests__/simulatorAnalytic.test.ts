/**
 * Tests for the analytic simulator stack (integrators + recorder + phenomena).
 *
 * Run: node --experimental-strip-types --test src/__tests__/simulatorAnalytic.test.ts
 *
 * Why these tests matter: the simulator is the BAC-prep workhorse for Juan
 * (STI2D/SIN). If the pendulum drifts +5%/period or the CSV gets corrupted,
 * the whole "expert" promise dies.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  adaptiveRK45,
  energyDrift,
  rk4,
  rollFixed,
  symplecticEuler,
  velocityVerlet,
} from '../services/simulator/analyticIntegrators.ts'
import { DataRecorder } from '../services/simulator/dataRecorder.ts'
import {
  ANALYTIC_PHENOMENA,
  getAnalyticPhenomenon,
  pendulumPeriodSmallAngle,
  resolveParams,
  rlcPulsation,
  stepDiffusion,
  terminalVelocity,
} from '../services/simulator/analyticPhenomena.ts'
import { createRng, hashSeed, nextFloat, nextGaussian, nextUnitVec3, shuffle } from '../services/simulator/seededRandom.ts'
import { AnalyticSession, startSession } from '../services/simulator/analyticSession.ts'

describe('rk4', () => {
  test('y\' = -y converges to e^{-T}', () => {
    let y = [1]
    let t = 0
    const dt = 0.01
    const T = 1
    while (t < T - 1e-12) {
      y = rk4((_t, yy) => [-yy[0]], t, y, dt)
      t += dt
    }
    assert.ok(Math.abs(y[0] - Math.exp(-T)) < 1e-7, `got ${y[0]}, expected ${Math.exp(-T)}`)
  })
})

describe('velocityVerlet', () => {
  test('harmonic oscillator preserves energy within 0.1%', () => {
    const k = 5, m = 1
    let q = [1]
    let v = [0]
    let t = 0
    const dt = 0.005
    const E0 = 0.5 * k * q[0] * q[0]
    let driftMax = 0
    for (let i = 0; i < 4000; i += 1) {
      const step = velocityVerlet((_t, qq) => [-(k / m) * qq[0]], t, q, v, dt)
      q = step.q
      v = step.v
      t += dt
      const E = 0.5 * m * v[0] * v[0] + 0.5 * k * q[0] * q[0]
      driftMax = Math.max(driftMax, Math.abs(E - E0) / E0)
    }
    assert.ok(driftMax < 1e-3, `Verlet energy drift too high: ${driftMax}`)
  })
})

describe('symplecticEuler', () => {
  test('bounded energy drift on harmonic oscillator', () => {
    const k = 5, m = 1
    let q = [1]
    let v = [0]
    const dt = 0.01
    const E0 = 0.5 * k * q[0] * q[0]
    let driftMax = 0
    for (let i = 0; i < 2000; i += 1) {
      const step = symplecticEuler((_t, qq) => [-(k / m) * qq[0]], 0, q, v, dt)
      q = step.q
      v = step.v
      const E = 0.5 * m * v[0] * v[0] + 0.5 * k * q[0] * q[0]
      driftMax = Math.max(driftMax, Math.abs(E - E0) / E0)
    }
    // Symplectic Euler is only 1st order — accept up to ~3%.
    assert.ok(driftMax < 0.05, `symplecticEuler drift too high: ${driftMax}`)
  })
})

describe('adaptiveRK45', () => {
  test('takes one accepted step on a smooth ODE', () => {
    const res = adaptiveRK45((_t, y) => [-y[0]], 0, [1], 0.1, { atol: 1e-8, rtol: 1e-6 })
    assert.equal(res.rejected, false)
    assert.ok(res.tNext > 0)
    assert.ok(Math.abs(res.y[0] - Math.exp(-0.1)) < 1e-5)
  })

  test('rejects a too-aggressive step on stiff system', () => {
    // Decaying exponential with rate 1000 — large dt should be rejected.
    const res = adaptiveRK45((_t, y) => [-1000 * y[0]], 0, [1], 0.1, { atol: 1e-9, rtol: 1e-9 })
    assert.equal(res.rejected, true)
    assert.ok(res.dtNext < 0.1)
  })

  test('dtNext stays inside [minDt, maxDt]', () => {
    const res = adaptiveRK45((_t, y) => [y[0]], 0, [1], 0.01, { minDt: 1e-4, maxDt: 0.1 })
    assert.ok(res.dtNext >= 1e-4 && res.dtNext <= 0.1)
  })
})

describe('rollFixed', () => {
  test('verlet on pendulum recovers period within 1% at small angle', () => {
    const L = 1, g = 9.81, theta0 = 0.05
    let zeroCrossings = 0
    let prevTheta = theta0
    let zeroT: number[] = []
    rollFixed(
      (_t, q) => [-(g / L) * Math.sin(q[0])],
      [theta0],
      [0],
      {
        duration: 8,
        dt: 1 / 480,
        integrator: 'verlet',
        sampleStride: 1,
        onSample: (t, q) => {
          if (prevTheta > 0 && q[0] <= 0) {
            zeroCrossings += 1
            zeroT.push(t)
          }
          prevTheta = q[0]
        },
      },
    )
    assert.ok(zeroCrossings >= 3)
    // Each full oscillation produces exactly one downward zero crossing, so
    // zeroT[k] - zeroT[k-1] is one period.
    const period = zeroT[2] - zeroT[1]
    const expected = pendulumPeriodSmallAngle(L, g)
    assert.ok(Math.abs(period - expected) / expected < 0.01, `period ${period}s vs expected ${expected}s`)
  })
})

describe('energyDrift', () => {
  test('returns relative drift', () => {
    const d = energyDrift(() => ({ kinetic: 1.5, potential: 0.5 }), 0, [0], [0], 2)
    assert.equal(d, 0)
    const d2 = energyDrift(() => ({ kinetic: 1, potential: 1.05 }), 0, [0], [0], 2)
    assert.ok(Math.abs(d2 - 0.025) < 1e-9)
  })
})

describe('DataRecorder', () => {
  test('rejects duplicate channel ids', () => {
    assert.throws(() => new DataRecorder([{ id: 'x', label: 'x' }, { id: 'x', label: 'x2' }]))
  })

  test('honours minDtSeconds gate', () => {
    const rec = new DataRecorder([{ id: 'v', label: 'v' }], { minDtSeconds: 0.05 })
    assert.equal(rec.push(0, { v: 1 }), true)
    assert.equal(rec.push(0.01, { v: 2 }), false)
    assert.equal(rec.push(0.1, { v: 3 }), true)
    assert.equal(rec.size(), 2)
  })

  test('ring buffer caps samples', () => {
    const rec = new DataRecorder([{ id: 'v', label: 'v' }], { maxSamples: 100 })
    for (let i = 0; i < 500; i += 1) rec.push(i * 0.001, { v: i })
    assert.ok(rec.size() <= 100)
  })

  test('csv includes header units and stable rows', () => {
    const rec = new DataRecorder([
      { id: 'theta', label: 'angle', unit: 'rad' },
      { id: 'omega', label: 'vitesse', unit: 'rad/s' },
    ])
    rec.push(0, { theta: 0.1, omega: 0 })
    rec.push(0.01, { theta: 0.099, omega: -0.02 })
    const csv = rec.toCsv()
    const lines = csv.split('\n')
    assert.equal(lines[0], 't (s),angle (rad),vitesse (rad/s)')
    assert.equal(lines.length, 3)
  })

  test('diagnostics reports min/max/mean/std', () => {
    const rec = new DataRecorder([{ id: 'v', label: 'v', unit: 'm/s' }])
    for (let i = 0; i < 10; i += 1) rec.push(i, { v: i })
    const diag = rec.diagnostics()
    assert.equal(diag.v.min, 0)
    assert.equal(diag.v.max, 9)
    assert.ok(Math.abs(diag.v.mean - 4.5) < 1e-9)
    assert.equal(diag.v.count, 10)
  })

  test('decimate respects max points', () => {
    const rec = new DataRecorder([{ id: 'v', label: 'v' }])
    for (let i = 0; i < 1000; i += 1) rec.push(i * 0.001, { v: i })
    const out = rec.decimate(50)
    assert.ok(out.length <= 50)
  })

  test('NaN values cleaned in csv', () => {
    const rec = new DataRecorder([{ id: 'v', label: 'v' }])
    rec.push(0, { v: 1 })
    rec.push(0.01, {} as never)
    const csv = rec.toCsv()
    const lines = csv.split('\n')
    assert.equal(lines[2].endsWith(','), true)
  })

  test('toCsvReport inclut résumé statistique en commentaire', () => {
    const rec = new DataRecorder([
      { id: 'x', label: 'position', unit: 'm' },
      { id: 'v', label: 'vitesse', unit: 'm/s' },
    ])
    for (let i = 0; i < 10; i += 1) rec.push(i * 0.1, { x: i, v: i * 2 })
    const csv = rec.toCsvReport({
      phenomenon: 'spring-damped',
      integrator: 'verlet',
      durationS: 1,
      params: { k: 100, m: 1 },
    })
    const lines = csv.split('\n')
    // Comment header lines
    assert.ok(lines[0].startsWith('#'))
    assert.ok(lines.some((l) => l.includes('spring-damped')))
    assert.ok(lines.some((l) => l.includes('verlet')))
    assert.ok(lines.some((l) => l.includes('k=100')))
    // Stats per channel : position min=0 max=9
    assert.ok(lines.some((l) => l.includes('position') && l.includes('# ')))
    // CSV header présent après les commentaires
    assert.ok(lines.some((l) => l.startsWith('t (s)')))
  })

  test('toCsvReport sans meta fonctionne quand même', () => {
    const rec = new DataRecorder([{ id: 'x', label: 'pos' }])
    rec.push(0, { x: 1 })
    const csv = rec.toCsvReport()
    assert.ok(csv.startsWith('#'))
    assert.ok(csv.includes('Samples : 1'))
  })
})

describe('seededRandom', () => {
  test('hashSeed is deterministic and 32-bit', () => {
    assert.equal(hashSeed('aurora'), hashSeed('aurora'))
    assert.ok(hashSeed('aurora') >>> 0 === hashSeed('aurora'))
  })

  test('same seed → identical stream', () => {
    const a = createRng('abc')
    const b = createRng('abc')
    for (let i = 0; i < 100; i += 1) assert.equal(nextFloat(a), nextFloat(b))
  })

  test('gaussian roughly N(0,1)', () => {
    const rng = createRng(42)
    let sum = 0
    let sumSq = 0
    const N = 5000
    for (let i = 0; i < N; i += 1) {
      const x = nextGaussian(rng)
      sum += x
      sumSq += x * x
    }
    const mean = sum / N
    const variance = sumSq / N - mean * mean
    assert.ok(Math.abs(mean) < 0.05, `mean ${mean}`)
    assert.ok(Math.abs(variance - 1) < 0.1, `variance ${variance}`)
  })

  test('unitVec3 is normalised', () => {
    const rng = createRng(1)
    for (let i = 0; i < 50; i += 1) {
      const [x, y, z] = nextUnitVec3(rng)
      assert.ok(Math.abs(Math.hypot(x, y, z) - 1) < 1e-9)
    }
  })

  test('shuffle preserves multiset', () => {
    const rng = createRng(123)
    const original = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    const shuffled = shuffle(rng, original.slice())
    assert.equal(shuffled.length, original.length)
    const sortedA = shuffled.slice().sort((a, b) => a - b)
    assert.deepEqual(sortedA, original)
  })
})

describe('analytic phenomena', () => {
  test('catalogue exposes >= 5 phenomena across categories', () => {
    assert.ok(ANALYTIC_PHENOMENA.length >= 5)
    const cats = new Set(ANALYTIC_PHENOMENA.map((p) => p.category))
    assert.ok(cats.size >= 3)
  })

  test('pendulum-exact small-angle period matches 2π√(L/g) within 1%', () => {
    const phen = getAnalyticPhenomenon('pendulum-exact')!
    const params = resolveParams(phen, { length: 1, gravity: 9.81, theta0: 0.05, friction: 0, mass: 1 })
    const expected = pendulumPeriodSmallAngle(params.length, params.gravity)

    const { q: q0, v: v0 } = phen.initial(params)
    let zeroT: number[] = []
    let prev = q0[0]
    rollFixed(
      phen.acceleration(params),
      q0,
      v0,
      {
        duration: 6,
        dt: phen.suggestedDt,
        integrator: 'verlet',
        onSample: (t, q) => {
          if (prev > 0 && q[0] <= 0) zeroT.push(t)
          prev = q[0]
        },
      },
    )
    assert.ok(zeroT.length >= 3)
    const period = zeroT[2] - zeroT[1]
    assert.ok(Math.abs(period - expected) / expected < 0.01, `period ${period}s vs expected ${expected}s`)
  })

  test('rlc pulsation matches 1/√(LC)', () => {
    const phen = getAnalyticPhenomenon('rlc-series')!
    const params = resolveParams(phen, { R: 0, L: 1e-2, C: 1e-6, q0: 1e-5 })
    assert.ok(Math.abs(rlcPulsation(params.L, params.C) - 10000) < 1e-3)
  })

  test('terminal velocity converges', () => {
    const v = terminalVelocity(1, 9.81, 1.225, 0.47, 0.0043)
    assert.ok(v > 40 && v < 120, `terminal velocity ${v}`)
  })

  test('stepDiffusion preserves Dirichlet BCs and propagates heat', () => {
    const phen = getAnalyticPhenomenon('thermal-rod-1d')!
    const params = resolveParams(phen, { length: 0.1, nodes: 20, alpha: 1.1e-4, tempHot: 500, tempCold: 293 })
    let T = phen.initial(params).q.slice()
    const initialCentre = T[Math.floor(T.length / 2)]
    for (let i = 0; i < 2000; i += 1) {
      T = stepDiffusion(phen, params, T, 0.01)
    }
    // Dirichlet BCs must stay pinned.
    assert.equal(T[0], 500)
    assert.equal(T[T.length - 1], 293)
    // Heat must have propagated to the centre.
    assert.ok(T[Math.floor(T.length / 2)] > initialCentre + 1, `centre ${T[Math.floor(T.length / 2)]} did not move from ${initialCentre}`)
  })

  test('each phenomenon channel-set has unique ids', () => {
    for (const phen of ANALYTIC_PHENOMENA) {
      const ids = new Set<string>()
      for (const ch of phen.channels) {
        assert.equal(ids.has(ch.id), false, `phenomenon ${phen.id} dupes channel ${ch.id}`)
        ids.add(ch.id)
      }
    }
  })
})

describe('AnalyticSession', () => {
  test('records samples on init + after advance', () => {
    const phen = getAnalyticPhenomenon('spring-damped')!
    const session = startSession(phen, { mass: 1, stiffness: 100, damping: 0 }, { dt: 1 / 200 })
    const before = session.recorder.size()
    session.advance(1)
    assert.ok(session.recorder.size() > before)
  })

  test('reset wipes samples and restores t=0', () => {
    const phen = getAnalyticPhenomenon('spring-damped')!
    const session = startSession(phen, {})
    session.advance(2)
    assert.ok(session.getState().t > 1.5)
    session.reset()
    assert.equal(session.getState().t, 0)
    assert.equal(session.recorder.size(), 1)
  })

  test('energy drift channel stays small on conservative system', () => {
    const phen = getAnalyticPhenomenon('spring-damped')!
    const session = startSession(phen, { damping: 0, mass: 1, stiffness: 100, x0: 0.4, v0: 0 }, { dt: 1 / 480, integrator: 'verlet' })
    session.advance(5)
    const diag = session.diagnostics()
    const drift = diag.channels.__energyDrift
    assert.ok(Math.abs(drift.max) < 0.01, `verlet drift ${drift.max}`)
  })

  test('adaptiveRK45 mode advances time without crashing', () => {
    const phen = getAnalyticPhenomenon('pendulum-double')!
    const session = startSession(phen, {}, { integrator: 'adaptiveRK45', dt: 1 / 400 })
    const before = session.getState().t
    session.advance(2)
    assert.ok(session.getState().t > before)
  })

  test('csv export non-empty and CSV-shaped', () => {
    const phen = getAnalyticPhenomenon('pendulum-exact')!
    const session = startSession(phen, {}, { dt: 1 / 100 })
    session.advance(0.5)
    const csv = session.exportCsv()
    const lines = csv.split('\n')
    assert.ok(lines.length > 2)
    assert.equal(lines[0].startsWith('t (s),'), true)
  })

  test('AnalyticSession respects maxStepsPerAdvance budget', () => {
    const phen = getAnalyticPhenomenon('pendulum-exact')!
    const session = new AnalyticSession(phen, {}, { dt: 0.001, maxStepsPerAdvance: 100 })
    const res = session.advance(10)
    assert.ok(res.clippedByBudget)
    assert.equal(res.stepsTaken, 100)
  })

  test('lentille mince : 1/di - 1/do = 1/f vérifiée', () => {
    const phen = getAnalyticPhenomenon('thin-lens')!
    const session = startSession(phen, { focal: 0.1, objectDistance: -0.2, objectHeight: 0.02 })
    session.advance(0.5)
    const diag = session.diagnostics()
    const di = diag.channels.di.last
    // Calcul attendu : 1/di = 1/f + 1/do = 1/0.1 + 1/(-0.2) = 10 - 5 = 5 → di = 0.2
    assert.ok(Math.abs(di - 0.2) < 0.01, `di = ${di}, attendu 0.2`)
  })

  test('lentille mince : grandissement γ = -di/do calculé correctement', () => {
    const phen = getAnalyticPhenomenon('thin-lens')!
    const session = startSession(phen, { focal: 0.1, objectDistance: -0.3, objectHeight: 0.01 })
    session.advance(0.5)
    const diag = session.diagnostics()
    // di = 1/(1/0.1 + 1/-0.3) = 1/(10 - 3.33) = 0.15
    // γ = -0.15 / -0.3 = 0.5
    const gamma = diag.channels.gamma.last
    assert.ok(Math.abs(gamma - 0.5) < 0.05, `γ = ${gamma}, attendu 0.5`)
  })

  test('Doppler : source qui s\'approche → f\' > f', () => {
    const phen = getAnalyticPhenomenon('doppler-1d')!
    const session = startSession(phen, { c: 343, fSource: 440, vSource: 30, xObserver: 100, xSourceInit: -50 })
    session.advance(0.1)
    const diag = session.diagnostics()
    // vSource > 0, observateur à droite → source approche → f' > 440
    assert.ok(diag.channels.fPerceived.last > 440, `f' = ${diag.channels.fPerceived.last}`)
  })

  test('Doppler : source qui s\'éloigne → f\' < f', () => {
    const phen = getAnalyticPhenomenon('doppler-1d')!
    const session = startSession(phen, { c: 343, fSource: 440, vSource: -30, xObserver: 100, xSourceInit: 50 })
    session.advance(0.1)
    const diag = session.diagnostics()
    // vSource < 0, observateur à droite → source s'éloigne → f' < 440
    assert.ok(diag.channels.fPerceived.last < 440, `f' = ${diag.channels.fPerceived.last}`)
  })

  test('Corde vibrante : énergie quasi-conservée sans damping', () => {
    const phen = getAnalyticPhenomenon('vibrating-string')!
    const session = startSession(phen, {
      length: 0.5, nodes: 32, celerity: 200, damping: 0, pluckPos: 0.5, pluckAmp: 0.01,
    }, { dt: 1 / 20000 })
    session.advance(0.05)
    const diag = session.diagnostics()
    // Sans damping, l'énergie doit rester proche de sa valeur initiale.
    const energy = diag.channels.energy
    const drift = Math.abs(energy.max - energy.min) / Math.max(1e-9, energy.max)
    assert.ok(drift < 0.3, `dérive d'énergie ${(drift * 100).toFixed(0)}%`)
  })

  test('Corde vibrante : Dirichlet BCs respectées (y[0]=y[n-1]=0 toujours)', () => {
    const phen = getAnalyticPhenomenon('vibrating-string')!
    const params = resolveParams(phen, { length: 1, nodes: 16, celerity: 100, damping: 0, pluckPos: 0.5, pluckAmp: 0.01 })
    const { q: y0 } = phen.initial(params)
    assert.equal(y0[0], 0)
    assert.equal(y0[y0.length - 1], 0)
    // Après une intégration, les bords doivent rester nuls (Dirichlet implicite via out[0]=out[n-1]=0).
    const accel = phen.acceleration(params)
    const v0 = new Array(y0.length).fill(0)
    const a = accel(0, y0, v0)
    assert.equal(a[0], 0)
    assert.equal(a[a.length - 1], 0)
  })

  test('phase portrait : pendule sans amortissement → orbite fermée', async () => {
    const { computePhasePortrait } = await import('../services/simulator/phasePortrait.ts')
    const phen = getAnalyticPhenomenon('pendulum-exact')!
    const params = resolveParams(phen, { length: 1, gravity: 9.81, theta0: 0.5, friction: 0, mass: 1 })
    const portrait = computePhasePortrait(
      phen.acceleration(params),
      phen.initial(params).q,
      phen.initial(params).v,
      { duration: 5, dt: 1 / 240, stride: 2 },
    )
    assert.equal(portrait.topology, 'closed-orbit')
    assert.ok(portrait.trajectory.length > 100)
  })

  test('phase portrait : pendule amorti → spirale amortie', async () => {
    const { computePhasePortrait } = await import('../services/simulator/phasePortrait.ts')
    const phen = getAnalyticPhenomenon('pendulum-exact')!
    const params = resolveParams(phen, { length: 1, gravity: 9.81, theta0: 0.5, friction: 0.5, mass: 1 })
    const portrait = computePhasePortrait(
      phen.acceleration(params),
      phen.initial(params).q,
      phen.initial(params).v,
      { duration: 15, dt: 1 / 240, stride: 4 },
    )
    assert.equal(portrait.topology, 'damped-spiral')
  })

  test('phase portrait : période détectée proche du théorique pour pendule petit', async () => {
    const { computePhasePortrait } = await import('../services/simulator/phasePortrait.ts')
    const phen = getAnalyticPhenomenon('pendulum-exact')!
    const params = resolveParams(phen, { length: 1, gravity: 9.81, theta0: 0.05, friction: 0, mass: 1 })
    const portrait = computePhasePortrait(
      phen.acceleration(params),
      phen.initial(params).q,
      phen.initial(params).v,
      { duration: 8, dt: 1 / 480, stride: 2 },
    )
    const T = portrait.detectedPeriodS
    const Texpected = 2 * Math.PI * Math.sqrt(1 / 9.81)
    assert.ok(T != null && Math.abs(T - Texpected) / Texpected < 0.05, `T=${T}, T_th=${Texpected}`)
  })

  test('FFT discrète : sinus pur produit pic à f attendue', async () => {
    const { discreteSpectrum, findResonances } = await import('../services/simulator/phasePortrait.ts')
    const N = 256
    const f0 = 8 / N // 8 cycles sur 256 points
    const signal = Array.from({ length: N }, (_, n) => Math.cos(2 * Math.PI * f0 * n))
    const spectrum = discreteSpectrum(signal)
    const peaks = findResonances(spectrum)
    assert.ok(peaks.length >= 1)
    const top = peaks[0]
    assert.ok(Math.abs(top.frequency - f0) < 0.01, `peak ${top.frequency}, expected ${f0}`)
  })

  test('exportCsvReport contient phénomène et paramètres', () => {
    const phen = getAnalyticPhenomenon('spring-damped')!
    const session = startSession(phen, { mass: 0.5, stiffness: 80, damping: 0.6 }, { dt: 1 / 100 })
    session.advance(0.5)
    const report = session.exportCsvReport()
    assert.ok(report.startsWith('#'))
    assert.ok(report.includes('spring-damped'))
    assert.ok(report.includes('mass=0.5') || report.includes('stiffness=80'))
    assert.ok(report.includes('verlet') || report.includes('rk4') || report.includes('adaptive'))
  })
})
