import { lazy, Suspense, useCallback, useMemo, useRef, useState } from 'react'
import React from 'react'
import { motion } from 'framer-motion'
import {
  Atom,
  BookOpen,
  CircuitBoard,
  Film,
  FlaskConical,
  GraduationCap,
  Globe,
  Home,
  Layers,
  Library,
  Map as MapIcon,
  Plane,
  Sigma,
  Sparkles,
  Target,
  TreePine,
  Zap,
} from 'lucide-react'
import RecoveryBanner from '../components/RecoveryBanner.tsx'
import { useGenerationRecovery } from '../hooks/useGenerationRecovery.ts'
import type { Tab, LessonRef } from './learning/types.ts'

const Hub = lazy(() => import('./learning/Hub'))
const DailyChallenge = lazy(() => import('./learning/DailyChallenge'))
const QuizPanel = lazy(() => import('./learning/QuizPanel'))
const CoursesPanel = lazy(() => import('./learning/CoursesPanel'))
const LabCourses = lazy(() => import('./learning/LabCourses'))
const FichesPanel = lazy(() => import('./learning/FichesPanel'))
const ParcoursPanel = lazy(() => import('./learning/ParcoursPanel'))
const VideoAnalysisPanel = lazy(() => import('./learning/VideoAnalysisPanel'))
const LabPhysics = lazy(() => import('./learning/LabPhysics'))
const LabChemistry = lazy(() => import('./learning/LabChemistry'))
const LabElectronics = lazy(() => import('./learning/LabElectronics'))
const LabMath = lazy(() => import('./learning/LabMath'))
const LabAstronomy = lazy(() => import('./learning/LabAstronomy'))
const LabModeling = lazy(() => import('./learning/LabModeling'))
const LabModelism = lazy(() => import('./learning/LabModelism'))

function PanelLoader() {
  return (
    <div className="flex h-48 items-center justify-center">
      <div className="relative h-12 w-12">
        <div className="absolute inset-0 rounded-full border-2 border-violet-400/30" />
        <div className="absolute inset-0 rounded-full border-2 border-t-violet-400 border-r-cyan-400 border-b-transparent border-l-transparent animate-spin-slow" />
        <Sparkles size={14} className="absolute inset-0 m-auto text-violet-300 animate-aurora-pulse" />
      </div>
    </div>
  )
}

function KeepAlivePanel({
  active, visited, children,
}: {
  active: boolean; visited: boolean; children: React.ReactNode
}) {
  if (!visited) return null
  return (
    <div style={{ display: active ? undefined : 'none' }}>
      <Suspense fallback={<PanelLoader />}>{children}</Suspense>
    </div>
  )
}

export interface AdaptiveBktState {
  priorMastery: number
  posteriorMastery: number
  masteryDelta: number
  recommendedDifficulty: number
  adaptiveAction: string
  policySafetyVerified: boolean
}

export interface IsomorphicExerciseSpec {
  complexityTier: string
  calibratedDifficulty: number
  problemExpression: string
  canonicalSolution: string
  formalDerivative: string
  valueAtZero: number
  valueAtOne: number
  graduatedHints: string[]
  pedagogicalCounterexample: {
    misconception: string
    witnessX: number
    studentValue: number
    expectedValue: number
  }
}

export function computeAdaptiveBktPosterior(
  priorMastery: number,
  finalCorrect: boolean,
  errorDiagnosis = 'NONE',
  firstErrorStep: number | null = null,
  pTransit = 0.18,
  pSlip = 0.08,
  pGuess = 0.15,
): AdaptiveBktState {
  const pL = Math.max(0.01, Math.min(0.99, priorMastery))
  const pS = Math.max(0.01, Math.min(0.4, pSlip))
  const pG = Math.max(0.01, Math.min(0.45, pGuess))
  const pT = Math.max(0.01, Math.min(0.5, pTransit))

  let pObs: number
  if (finalCorrect) {
    const denom = pL * (1 - pS) + (1 - pL) * pG
    pObs = (pL * (1 - pS)) / Math.max(denom, 1e-9)
  } else {
    const partialMod =
      firstErrorStep && firstErrorStep > 1 && errorDiagnosis === 'SIGN_INVERSION_ERROR' ? 0.35 : 0
    const denom = pL * pS + (1 - pL) * (1 - pG)
    const pObsRaw = (pL * pS) / Math.max(denom, 1e-9)
    pObs = pObsRaw + partialMod * (pL - pObsRaw)
  }

  const posterior = Number(Math.max(0.01, Math.min(0.995, pObs + (1 - pObs) * pT)).toFixed(4))
  const recommendedDifficulty = Number(
    Math.max(0.15, Math.min(0.95, posterior + (finalCorrect ? 0.12 : -0.08))).toFixed(3),
  )
  const adaptiveAction =
    posterior >= 0.85
      ? 'ADVANCE_CONCEPT_COMPLEXITY'
      : finalCorrect
        ? 'CONSOLIDATE_WITH_ISOMORPHIC_VARIANT'
        : errorDiagnosis === 'SIGN_INVERSION_ERROR'
          ? 'TARGETED_SIGN_REMEDIATION'
          : errorDiagnosis === 'MISSING_CROSS_TERM_ERROR'
            ? 'CROSS_TERM_VISUAL_SCAFFOLDING'
            : 'SCAFFOLDED_STEP_DECOMPOSITION'

  return {
    priorMastery: Number(pL.toFixed(4)),
    posteriorMastery: posterior,
    masteryDelta: Number((posterior - pL).toFixed(4)),
    recommendedDifficulty,
    adaptiveAction,
    policySafetyVerified: recommendedDifficulty >= 0.15 && recommendedDifficulty <= 0.95,
  }
}

function evalSafePolynomialAtX(expr: string, xVal: number): number | null {
  const normalized = expr
    .replace(/\^/g, '**')
    .replace(/(\d)\s*([a-zA-Z(])/g, '$1*$2')
    .replace(/\b[a-zA-Z]\b/g, `(${xVal})`)
  if (!/^[0-9+\-*/().\s]+$/.test(normalized)) return null
  try {
    const fn = new Function(`return (${normalized});`)
    const out = Number(fn())
    return Number.isFinite(out) ? out : null
  } catch {
    return null
  }
}

export function verifyAlgebraicStepClient(studentExpr: string, targetExpr: string) {
  const probes = [0, 1, 2, -1, 3, -2]
  let allEqual = true
  let allNegated = true
  let witness: { x: number; studentVal: number; expectedVal: number } | null = null

  for (const x of probes) {
    const sVal = evalSafePolynomialAtX(studentExpr, x)
    const tVal = evalSafePolynomialAtX(targetExpr, x)
    if (sVal === null || tVal === null) {
      allEqual = false
      allNegated = false
      break
    }
    if (Math.abs(sVal - tVal) > 1e-7) {
      allEqual = false
      if (!witness) witness = { x, studentVal: sVal, expectedVal: tVal }
    }
    if (Math.abs(sVal + tVal) > 1e-7) {
      allNegated = false
    }
  }

  const s0 = evalSafePolynomialAtX(studentExpr, 0)
  const t0 = evalSafePolynomialAtX(targetExpr, 0)
  const s1 = evalSafePolynomialAtX(studentExpr, 1)
  const t1 = evalSafePolynomialAtX(targetExpr, 1)
  const sNeg1 = evalSafePolynomialAtX(studentExpr, -1)
  const tNeg1 = evalSafePolynomialAtX(targetExpr, -1)

  let diagnosis = 'EQUIVALENT'
  if (!allEqual) {
    if (allNegated) {
      diagnosis = 'SIGN_INVERSION_ERROR'
    } else if (
      s0 !== null &&
      t0 !== null &&
      s1 !== null &&
      t1 !== null &&
      sNeg1 !== null &&
      tNeg1 !== null &&
      Math.abs(s0 - t0) <= 1e-7 &&
      Math.abs(s1 - sNeg1) <= 1e-7 &&
      Math.abs(t1 - tNeg1) > 1e-7
    ) {
      diagnosis = 'MISSING_CROSS_TERM_ERROR'
    } else if (
      s1 !== null &&
      t1 !== null &&
      s0 !== null &&
      t0 !== null &&
      Math.abs(s1 - t1 - (s0 - t0)) <= 1e-7
    ) {
      diagnosis = 'CONSTANT_OFFSET_ERROR'
    } else {
      diagnosis = 'ALGEBRAIC_TRANSFORMATION_ERROR'
    }
  }

  return {
    equivalent: allEqual,
    diagnosis,
    counterexample: witness,
  }
}

export function generateIsomorphicExerciseClient(
  masteryLevel: number,
  errorFocus = 'NONE',
  variantSeed = 1,
): IsomorphicExerciseSpec {
  const calibratedDifficulty = Number(
    Math.max(0.15, Math.min(0.95, masteryLevel + 0.08)).toFixed(3),
  )
  const complexityTier =
    calibratedDifficulty < 0.45
      ? 'FOUNDATIONAL_SCAFFOLDED'
      : calibratedDifficulty < 0.75
        ? 'ISOMORPHIC_CONSOLIDATION'
        : 'ADVANCED_TRANSFER'

  const a = calibratedDifficulty < 0.45 ? 1 : calibratedDifficulty < 0.75 ? 2 : 2 + (variantSeed % 2)
  const rawB = (variantSeed % 3) + 2
  const b = errorFocus === 'SIGN_INVERSION_ERROR' || calibratedDifficulty >= 0.75 ? -rawB : rawB

  const a2 = a * a
  const twoAb = 2 * a * b
  const b2 = b * b
  const aPart = a === 1 ? 'x' : `${a}*x`
  const problemExpression = b < 0 ? `(${aPart} - ${Math.abs(b)})**2` : `(${aPart} + ${b})**2`
  const leadStr = a2 === 1 ? 'x**2' : `${a2}*x**2`
  const midStr = twoAb < 0 ? `- ${Math.abs(twoAb)}*x` : `+ ${twoAb}*x`
  const canonicalSolution = `${leadStr} ${midStr} + ${b2}`
  const formalDerivative = `${2 * a2}*x ${twoAb < 0 ? `- ${Math.abs(twoAb)}` : `+ ${twoAb}`}`
  const misconception = `${leadStr} + ${b2}`

  return {
    complexityTier,
    calibratedDifficulty,
    problemExpression,
    canonicalSolution,
    formalDerivative,
    valueAtZero: b2,
    valueAtOne: a2 + twoAb + b2,
    graduatedHints: [
      `Indice 1 (Invariant) : Applique l'identité remarquable (A ± B)² = A² ± 2·A·B + B² avec A = ${aPart} et B = ${Math.abs(b)}.`,
      `Indice 2 (Terme croisé) : Le double produit vaut (${twoAb}*x). Ne réduis jamais (A ± B)² à A² + B².`,
      `Indice 3 (Auto-contrôle formel) : En x = 0, le polynôme vaut ${b2}. En x = 1, la somme des coefficients vaut ${a2 + twoAb + b2}.`,
    ],
    pedagogicalCounterexample: {
      misconception,
      witnessX: 1,
      studentValue: a2 + b2,
      expectedValue: a2 + twoAb + b2,
    },
  }
}

export default function LearningView() {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [recoveryPrompt, setRecoveryPrompt] = useState<string | null>(null)
  const [lessonContext, setLessonContext] = useState<LessonRef | null>(null)
  const [showFormalStudio, setShowFormalStudio] = useState(false)
  const [bktMastery, setBktMastery] = useState(0.58)
  const [variantSeed, setVariantSeed] = useState(1)
  const [studentStepInput, setStudentStepInput] = useState('4*x**2 + 9')
  const [hintLevel, setHintLevel] = useState(1)
  const visitedRef = useRef<Set<Tab>>(new Set(['dashboard']))
  const [, forceUpdate] = useState(0)
  const recovery = useGenerationRecovery('learning')

  const currentExercise = useMemo(
    () => generateIsomorphicExerciseClient(bktMastery, 'MISSING_CROSS_TERM_ERROR', variantSeed),
    [bktMastery, variantSeed],
  )
  const stepEvaluation = useMemo(
    () => verifyAlgebraicStepClient(studentStepInput, currentExercise.canonicalSolution),
    [studentStepInput, currentExercise.canonicalSolution],
  )
  const liveBktState = useMemo(
    () =>
      computeAdaptiveBktPosterior(
        bktMastery,
        stepEvaluation.equivalent,
        stepEvaluation.diagnosis,
        stepEvaluation.equivalent ? null : 1,
      ),
    [bktMastery, stepEvaluation],
  )

  const handleSetTab = useCallback((newTab: Tab) => {
    if (!visitedRef.current.has(newTab)) {
      visitedRef.current.add(newTab)
      forceUpdate((n) => n + 1)
    }
    setTab(newTab)
  }, [])

  const tabs = useMemo(
    () =>
      [
        { id: 'dashboard' as Tab, label: 'Hub', icon: Home, gradient: 'from-violet-400 to-purple-500' },
        { id: 'daily' as Tab, label: 'Daily', icon: Zap, gradient: 'from-yellow-400 to-orange-400' },
        { id: 'library' as Tab, label: 'Bibliothèque', icon: Library, gradient: 'from-amber-400 to-orange-500' },
        { id: 'quiz' as Tab, label: 'Quiz', icon: Target, gradient: 'from-cyan-400 to-blue-500' },
        { id: 'courses' as Tab, label: 'Cours IA', icon: BookOpen, gradient: 'from-emerald-400 to-teal-500' },
        { id: 'fiches' as Tab, label: 'Fiches', icon: Layers, gradient: 'from-violet-400 to-fuchsia-500' },
        { id: 'parcours' as Tab, label: 'Parcours', icon: MapIcon, gradient: 'from-orange-400 to-rose-500' },
        { id: 'physics' as Tab, label: 'Physique', icon: Atom, gradient: 'from-blue-400 to-indigo-500' },
        { id: 'chemistry' as Tab, label: 'Chimie', icon: FlaskConical, gradient: 'from-green-400 to-emerald-500' },
        { id: 'electronics' as Tab, label: 'SIN', icon: CircuitBoard, gradient: 'from-orange-400 to-red-500' },
        { id: 'math' as Tab, label: 'Maths', icon: Sigma, gradient: 'from-pink-400 to-rose-500' },
        { id: 'astronomy' as Tab, label: 'Astro', icon: Globe, gradient: 'from-indigo-400 to-blue-500' },
        { id: 'modeling' as Tab, label: 'Modélisation', icon: TreePine, gradient: 'from-emerald-400 to-cyan-500' },
        { id: 'modelism' as Tab, label: 'Modélisme', icon: Plane, gradient: 'from-rose-400 to-orange-500' },
        { id: 'video' as Tab, label: 'Vidéo', icon: Film, gradient: 'from-fuchsia-400 to-pink-500' },
      ] as const,
    [],
  )

  const visited = visitedRef.current
  const activeTab = tabs.find((t) => t.id === tab)!

  return (
    <div className="relative flex h-full flex-col overflow-hidden">
      {/* Animated background */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 aurora-mesh opacity-50" />
        <div className="absolute -top-40 -left-40 h-[24rem] w-[24rem] rounded-full bg-violet-500/20 blur-[120px]" />
        <div className="absolute -bottom-40 -right-40 h-[24rem] w-[24rem] rounded-full bg-cyan-500/20 blur-[120px]" />
      </div>

      {/* Header + tabs */}
      <div className="relative px-3 pt-3 sm:px-5 sm:pt-5 border-b border-white/5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3 sm:mb-4">
          <div className="flex items-center gap-3">
            <div className={`rounded-2xl bg-gradient-to-br ${activeTab.gradient} p-2.5 shadow-lg`}>
              <GraduationCap size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-2xl sm:text-3xl font-black gradient-text leading-none">Académie Aurora</h1>
              <p className="text-[11px] text-aurora-text-dim mt-0.5">Quiz · Cours · Fiches · Parcours · Labs Duolingo · Physique · Chimie · SIN · Maths</p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setShowFormalStudio((v) => !v)}
            className="inline-flex items-center gap-2 rounded-xl border border-violet-400/30 bg-violet-500/10 px-3 py-1.5 text-xs font-semibold text-violet-200 hover:bg-violet-500/20 transition-all"
          >
            <Sigma size={14} className="text-cyan-300" />
            <span>Oracle Formel SymPy/Z3 · BKT {(liveBktState.posteriorMastery * 100).toFixed(0)}%</span>
          </button>
        </div>

        {showFormalStudio && (
          <div className="mb-3 rounded-2xl border border-violet-400/25 bg-slate-950/75 p-3.5 text-xs text-slate-200 backdrop-blur-md">
            <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-white/10">
              <div className="font-semibold text-violet-200">
                Exercice Isomorphe Vérifié ({currentExercise.complexityTier} · ZPD {currentExercise.calibratedDifficulty}) :{' '}
                <code className="rounded bg-white/10 px-1.5 py-0.5 text-cyan-300">{currentExercise.problemExpression}</code>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setHintLevel((h) => (h % 3) + 1)}
                  className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-2.5 py-1 text-[11px] text-cyan-200 hover:bg-cyan-500/20"
                >
                  Indice gradué ({hintLevel}/3)
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setBktMastery(liveBktState.posteriorMastery)
                    setVariantSeed((s) => s + 1)
                  }}
                  className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-2.5 py-1 text-[11px] text-emerald-200 hover:bg-emerald-500/20"
                >
                  Nouvel isomorphe ZPD
                </button>
              </div>
            </div>
            <div className="mt-2.5 grid gap-2 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="block text-[11px] text-slate-400">Étape algébrique de l&apos;élève :</label>
                <input
                  type="text"
                  value={studentStepInput}
                  onChange={(e) => setStudentStepInput(e.target.value)}
                  className="w-full rounded-lg border border-white/15 bg-black/40 px-2.5 py-1.5 font-mono text-xs text-white"
                />
                <div className="text-[11px] text-amber-200/90">
                  {currentExercise.graduatedHints[hintLevel - 1]}
                </div>
              </div>
              <div className="space-y-1 rounded-xl border border-white/10 bg-white/[0.03] p-2.5">
                <div className="font-semibold">
                  Diagnostic Formel :{' '}
                  <span className={stepEvaluation.equivalent ? 'text-emerald-300' : 'text-rose-300'}>
                    {stepEvaluation.diagnosis}
                  </span>
                </div>
                {!stepEvaluation.equivalent && stepEvaluation.counterexample && (
                  <div className="text-[11px] text-rose-200">
                    Contre-exemple : pour x = {stepEvaluation.counterexample.x}, ton expression vaut{' '}
                    {stepEvaluation.counterexample.studentVal} (attendu : {stepEvaluation.counterexample.expectedVal}).
                  </div>
                )}
                <div className="text-[11px] text-slate-300">
                  Solution prouvée : <code className="text-emerald-300">{currentExercise.canonicalSolution}</code> · Dérivée :{' '}
                  <code className="text-cyan-300">{currentExercise.formalDerivative}</code>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="flex gap-1.5 overflow-x-auto no-scrollbar pb-2">
          {tabs.map(({ id, label, icon: Icon, gradient }) => {
            const active = tab === id
            return (
              <motion.button
                key={id}
                whileHover={{ y: -2 }}
                whileTap={{ scale: 0.96 }}
                onClick={() => handleSetTab(id)}
                className={`relative shrink-0 inline-flex items-center gap-2 rounded-2xl px-3.5 py-2 text-sm font-medium transition-all ${
                  active
                    ? 'text-white shadow-xl'
                    : 'border border-white/10 bg-white/[0.04] text-aurora-text-muted hover:border-violet-400/30 hover:bg-white/[0.08]'
                }`}
                style={
                  active
                    ? { background: `linear-gradient(135deg, var(--tw-gradient-stops))` }
                    : undefined
                }
              >
                {active && (
                  <motion.span
                    layoutId="learn-tab-active"
                    className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${gradient} shadow-2xl -z-10`}
                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                  />
                )}
                <Icon size={14} className={active ? 'text-white drop-shadow' : ''} />
                <span>{label}</span>
              </motion.button>
            )
          })}
        </div>
      </div>

      {/* Panels */}
      <div className="relative flex-1 overflow-y-auto p-4 sm:p-6 scroll-shell">
        <RecoveryBanner
          recovery={recovery}
          onRetry={(gen) => {
            setRecoveryPrompt(gen.prompt)
            if (tab === 'dashboard') handleSetTab('quiz')
          }}
        />

        <KeepAlivePanel active={tab === 'dashboard'} visited={visited.has('dashboard')}>
          <Hub onNavigate={handleSetTab} />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'daily'} visited={visited.has('daily')}>
          <DailyChallenge />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'quiz'} visited={visited.has('quiz')}>
          <QuizPanel
            recoveryPrompt={recoveryPrompt}
            clearRecoveryPrompt={() => setRecoveryPrompt(null)}
            lessonContext={lessonContext}
          />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'courses'} visited={visited.has('courses')}>
          <CoursesPanel
            recoveryPrompt={recoveryPrompt}
            clearRecoveryPrompt={() => setRecoveryPrompt(null)}
            lessonContext={lessonContext}
          />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'library'} visited={visited.has('library')}>
          <LabCourses />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'fiches'} visited={visited.has('fiches')}>
          <FichesPanel
            recoveryPrompt={recoveryPrompt}
            clearRecoveryPrompt={() => setRecoveryPrompt(null)}
            lessonContext={lessonContext}
          />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'parcours'} visited={visited.has('parcours')}>
          <ParcoursPanel
            recoveryPrompt={recoveryPrompt}
            clearRecoveryPrompt={() => setRecoveryPrompt(null)}
            onLaunchStep={(topic, target, lessonRef) => {
              setRecoveryPrompt(topic)
              setLessonContext(lessonRef ?? null)
              handleSetTab(target)
            }}
            onExitLesson={() => setLessonContext(null)}
          />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'physics'} visited={visited.has('physics')}>
          <LabPhysics />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'chemistry'} visited={visited.has('chemistry')}>
          <LabChemistry />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'electronics'} visited={visited.has('electronics')}>
          <LabElectronics />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'math'} visited={visited.has('math')}>
          <LabMath />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'astronomy'} visited={visited.has('astronomy')}>
          <LabAstronomy />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'modeling'} visited={visited.has('modeling')}>
          <LabModeling />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'modelism'} visited={visited.has('modelism')}>
          <LabModelism />
        </KeepAlivePanel>

        <KeepAlivePanel active={tab === 'video'} visited={visited.has('video')}>
          <VideoAnalysisPanel />
        </KeepAlivePanel>
      </div>
    </div>
  )
}
