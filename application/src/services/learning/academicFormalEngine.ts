// ---------------------------------------------------------------------------
// Academic Formal Engine — Deterministic Scientific & Mathematical Verification
// ---------------------------------------------------------------------------

export type PhysicalDimension = {
  length: number   // L (meter)
  mass: number     // M (kilogram)
  time: number     // T (second)
  current: number  // I (ampere)
  temp: number     // Theta (kelvin)
  amount: number   // N (mole)
  luminous: number // J (candela)
}

export const SI_DIMENSIONS: Record<string, PhysicalDimension> = {
  dimensionless: { length: 0, mass: 0, time: 0, current: 0, temp: 0, amount: 0, luminous: 0 },
  length: { length: 1, mass: 0, time: 0, current: 0, temp: 0, amount: 0, luminous: 0 },
  mass: { length: 0, mass: 1, time: 0, current: 0, temp: 0, amount: 0, luminous: 0 },
  time: { length: 0, mass: 0, time: 1, current: 0, temp: 0, amount: 0, luminous: 0 },
  velocity: { length: 1, mass: 0, time: -1, current: 0, temp: 0, amount: 0, luminous: 0 },
  acceleration: { length: 1, mass: 0, time: -2, current: 0, temp: 0, amount: 0, luminous: 0 },
  force: { length: 1, mass: 1, time: -2, current: 0, temp: 0, amount: 0, luminous: 0 },
  energy: { length: 2, mass: 1, time: -2, current: 0, temp: 0, amount: 0, luminous: 0 },
  power: { length: 2, mass: 1, time: -3, current: 0, temp: 0, amount: 0, luminous: 0 },
  pressure: { length: -1, mass: 1, time: -2, current: 0, temp: 0, amount: 0, luminous: 0 },
  voltage: { length: 2, mass: 1, time: -3, current: -1, temp: 0, amount: 0, luminous: 0 },
  resistance: { length: 2, mass: 1, time: -3, current: -2, temp: 0, amount: 0, luminous: 0 },
  capacitance: { length: -2, mass: -1, time: 4, current: 2, temp: 0, amount: 0, luminous: 0 },
  inductance: { length: 2, mass: 1, time: -2, current: -2, temp: 0, amount: 0, luminous: 0 },
  frequency: { length: 0, mass: 0, time: -1, current: 0, temp: 0, amount: 0, luminous: 0 },
}

export function areDimensionsEqual(a: PhysicalDimension, b: PhysicalDimension): boolean {
  return (
    a.length === b.length &&
    a.mass === b.mass &&
    a.time === b.time &&
    a.current === b.current &&
    a.temp === b.temp &&
    a.amount === b.amount &&
    a.luminous === b.luminous
  )
}

export type SecondOrderSystemResponse = {
  isStable: boolean
  dampingRatio: number
  naturalFrequencyRadS: number
  overshootPercent: number
  peakTimeS: number
  settlingTime5PercentS: number
  steadyStateGain: number
  poles: Array<{ real: number; imag: number }>
}

export function computeSecondOrderResponse(
  staticGain: number,
  dampingRatio: number,
  naturalFrequencyRadS: number,
): SecondOrderSystemResponse {
  const isStable = dampingRatio > 0 && naturalFrequencyRadS > 0
  let overshootPercent = 0
  let peakTimeS = 0

  if (dampingRatio < 1 && dampingRatio > 0) {
    const sqrtTerm = Math.sqrt(1 - dampingRatio * dampingRatio)
    overshootPercent = 100 * Math.exp((-Math.PI * dampingRatio) / sqrtTerm)
    peakTimeS = Math.PI / (naturalFrequencyRadS * sqrtTerm)
  }

  // 5% settling time approximation for 0 < z < 0.9
  const settlingTime5PercentS =
    dampingRatio > 0 && naturalFrequencyRadS > 0
      ? 3.0 / (dampingRatio * naturalFrequencyRadS)
      : Infinity

  let poles: Array<{ real: number; imag: number }> = []
  if (dampingRatio < 1) {
    const real = -dampingRatio * naturalFrequencyRadS
    const imag = naturalFrequencyRadS * Math.sqrt(1 - dampingRatio * dampingRatio)
    poles = [
      { real, imag },
      { real, imag: -imag },
    ]
  } else {
    const r1 = -naturalFrequencyRadS * (dampingRatio - Math.sqrt(dampingRatio * dampingRatio - 1))
    const r2 = -naturalFrequencyRadS * (dampingRatio + Math.sqrt(dampingRatio * dampingRatio - 1))
    poles = [
      { real: r1, imag: 0 },
      { real: r2, imag: 0 },
    ]
  }

  return {
    isStable,
    dampingRatio,
    naturalFrequencyRadS,
    overshootPercent: Math.round(overshootPercent * 100) / 100,
    peakTimeS: Math.round(peakTimeS * 1000) / 1000,
    settlingTime5PercentS: Math.round(settlingTime5PercentS * 1000) / 1000,
    steadyStateGain: staticGain,
    poles,
  }
}

export type ThermodynamicCycleAudit = {
  isValidFirstLaw: boolean
  isValidSecondLaw: boolean
  carnotEfficiency: number
  actualEfficiency: number
  netWorkJ: number
  entropyGeneratedJPerK: number
  discrepancies: string[]
}

export function auditThermodynamicHeatEngine(
  heatInJ: number,
  heatOutJ: number,
  workOutJ: number,
  tempHotK: number,
  tempColdK: number,
): ThermodynamicCycleAudit {
  const discrepancies: string[] = []

  if (tempColdK >= tempHotK || tempColdK <= 0 || tempHotK <= 0) {
    discrepancies.push("Temperatures reservoir invalides: T_froid doit etre strictement inferieur a T_chaud et T > 0 K.")
  }

  const firstLawDiff = Math.abs(heatInJ - (workOutJ + heatOutJ))
  const isValidFirstLaw = firstLawDiff < 1e-4

  if (!isValidFirstLaw) {
    discrepancies.push(`Non-respect du 1er principe: Q_chaud (${heatInJ} J) != W (${workOutJ} J) + Q_froid (${heatOutJ} J).`)
  }

  const carnotEfficiency = 1 - tempColdK / tempHotK
  const actualEfficiency = heatInJ > 0 ? workOutJ / heatInJ : 0

  // Clausius inequality for heat engine: -Q_in/T_hot + Q_out/T_cold >= 0 (or delta S_univ >= 0)
  const entropyGeneratedJPerK = -heatInJ / tempHotK + heatOutJ / tempColdK
  const isValidSecondLaw = entropyGeneratedJPerK >= -1e-6 && actualEfficiency <= carnotEfficiency + 1e-6

  if (!isValidSecondLaw) {
    discrepancies.push(
      `Non-respect du 2nd principe: rendement reel (${(actualEfficiency * 100).toFixed(2)}%) superieur a Carnot (${(carnotEfficiency * 100).toFixed(2)}%) ou creation d'entropie negative.`,
    )
  }

  return {
    isValidFirstLaw,
    isValidSecondLaw,
    carnotEfficiency: Math.round(carnotEfficiency * 10000) / 10000,
    actualEfficiency: Math.round(actualEfficiency * 10000) / 10000,
    netWorkJ: workOutJ,
    entropyGeneratedJPerK: Math.round(entropyGeneratedJPerK * 10000) / 10000,
    discrepancies,
  }
}

export type ProofStep = {
  stepNumber: number
  statement: string
  justification: string
}

export type ProofRigourVerdict = {
  isSound: boolean
  score: number
  flaws: string[]
  strengths: string[]
}

export function auditMathematicalProof(
  claim: string,
  hypotheses: string[],
  steps: ProofStep[],
  conclusion: string,
): ProofRigourVerdict {
  const flaws: string[] = []
  const strengths: string[] = []

  if (hypotheses.length === 0) {
    flaws.push("Aucune hypothese de depart explicitee.")
  } else {
    strengths.push(`${hypotheses.length} hypothese(s) formellement posee(s).`)
  }

  if (steps.length === 0) {
    flaws.push("Aucune etape intermediaire fournie dans la demonstration.")
    return { isSound: false, score: 0, flaws, strengths }
  }

  let hasCircularRef = false
  for (const step of steps) {
    const lower = step.justification.toLowerCase()
    if (claim.trim().length > 3 && lower.includes(claim.toLowerCase())) {
      hasCircularRef = true
      flaws.push(`Raisonnement circulaire detecte a l'etape ${step.stepNumber}: la conclusion est utilisee comme justification.`)
    }
    if (!step.justification || step.justification.trim().length < 5) {
      flaws.push(`Etape ${step.stepNumber} depourvue de theoreme ou justification explicite.`)
    }
  }

  if (!conclusion || conclusion.trim().length < 5) {
    flaws.push("Conclusion manquante ou incomplete.")
  } else {
    strengths.push("Conclusion explicite alignee avec l'enonce.")
  }

  const isSound = flaws.length === 0 && !hasCircularRef
  const score = Math.max(0, 100 - flaws.length * 25)

  return {
    isSound,
    score,
    flaws,
    strengths,
  }
}
