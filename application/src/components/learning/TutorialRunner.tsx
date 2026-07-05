import { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft,
  ArrowRight,
  Award,
  CheckCircle2,
  Lightbulb,
  RotateCcw,
  Sparkles,
  Target,
  XCircle,
} from 'lucide-react'
import { BlockMath, InlineMath } from 'react-katex'
import 'katex/dist/katex.min.css'
import MarkdownPro from '../MarkdownPro'
import {
  computeXpReward,
  getSimulationLoader,
  isStepComplete,
  scoreTutorial,
  type SimulationComponent,
  type SimulationId,
  type Tutorial,
  type TutorialStep,
} from '../../services/learning/tutorialEngine'
import { useTutorialStore } from '../../stores/tutorialStore'
import { useGamificationStore } from '../../stores/gamificationStore'

type Props = {
  tutorial: Tutorial
  onClose?: () => void
  onComplete?: (xp: number, ratio: number) => void
}

export default function TutorialRunner({ tutorial, onClose, onComplete }: Props) {
  const progressRecord = useTutorialStore((s) => s.progress[tutorial.id])
  const setStepIndex = useTutorialStore((s) => s.setStepIndex)
  const recordAnswer = useTutorialStore((s) => s.recordAnswer)
  const markCompleted = useTutorialStore((s) => s.markCompleted)
  const resetTutorial = useTutorialStore((s) => s.resetTutorial)
  const isCompleted = useTutorialStore((s) => s.completed.includes(tutorial.id))

  const addXp = useGamificationStore((s) => s.addXp)
  const updateStreak = useGamificationStore((s) => s.updateStreak)

  const stepIndex = Math.min(progressRecord?.currentStepIndex ?? 0, tutorial.steps.length - 1)
  const step = tutorial.steps[stepIndex]
  const answers = progressRecord?.answers ?? {}
  const awardedRef = useRef(false)

  const [selectedChoice, setSelectedChoice] = useState<string | null>(answers[step.id] ?? null)
  const [showHint, setShowHint] = useState(false)

  useEffect(() => {
    setSelectedChoice(answers[step.id] ?? null)
    setShowHint(false)
  }, [step.id, answers])

  const totalSteps = tutorial.steps.length
  const progressPct = ((stepIndex + 1) / totalSteps) * 100

  const quizLocked = Boolean(step.quiz && (!selectedChoice || !isStepComplete(step, selectedChoice)))
  const isLastStep = stepIndex === totalSteps - 1
  const score = useMemo(() => scoreTutorial(tutorial, answers), [tutorial, answers])

  const handleChoose = (choiceId: string) => {
    if (!step.quiz) return
    const choice = step.quiz.choices.find((c) => c.id === choiceId)
    if (!choice) return
    setSelectedChoice(choiceId)
    recordAnswer(tutorial.id, step.id, choiceId, choice.correct)
  }

  const goPrevious = () => {
    if (stepIndex === 0) return
    setStepIndex(tutorial.id, stepIndex - 1)
  }

  const goNext = () => {
    if (quizLocked) return
    if (!isLastStep) {
      setStepIndex(tutorial.id, stepIndex + 1)
      return
    }
    const final = scoreTutorial(tutorial, answers)
    markCompleted(tutorial.id, final.total, final.correct)
    if (!awardedRef.current && !isCompleted) {
      awardedRef.current = true
      const xp = computeXpReward(tutorial, final.ratio)
      addXp(xp)
      updateStreak()
      onComplete?.(xp, final.ratio)
    }
  }

  return (
    <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-aurora-panel/60 backdrop-blur">
      <div className="flex items-center justify-between border-b border-white/5 px-5 py-3">
        <div className="flex items-center gap-3">
          <button onClick={onClose} className="btn-ghost text-xs">
            <ArrowLeft size={12} /> Quitter
          </button>
          <div className="text-[11px] uppercase tracking-widest text-aurora-text-dim">
            {tutorial.difficulty} · {tutorial.durationMin} min
          </div>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-aurora-text-dim">
          <Target size={12} className="text-cyan-300" />
          Étape {stepIndex + 1} / {totalSteps}
        </div>
      </div>

      <div className="h-1 w-full bg-white/5">
        <motion.div
          className="h-full bg-gradient-to-r from-cyan-400 via-violet-400 to-pink-400"
          animate={{ width: `${progressPct}%` }}
          transition={{ type: 'spring', stiffness: 120, damping: 20 }}
        />
      </div>

      <div className="grid gap-5 p-5 lg:grid-cols-[1.3fr_1fr]">
        <div className="space-y-4">
          <div>
            <div className="mono-kicker text-[10px] text-aurora-text-dim">{tutorial.title}</div>
            <h2 className="text-2xl font-black gradient-text-ocean mt-1">{step.title}</h2>
            {step.objective && (
              <p className="mt-1 text-xs text-cyan-200/80 italic">
                <Sparkles size={10} className="inline mr-1" />
                Objectif : {step.objective}
              </p>
            )}
          </div>

          <div className="prose prose-invert max-w-none text-sm">
            <MarkdownPro content={step.body} idPrefix={`tuto-${tutorial.id}-${step.id}`} />
          </div>

          {step.media?.map((media, idx) => (
            <StepMedia key={`${step.id}-media-${idx}`} media={media} />
          ))}

          {step.simulationId && <LazySimulation id={step.simulationId} />}
        </div>

        <aside className="space-y-4">
          {step.quiz ? (
            <QuizBlock
              step={step}
              selectedChoice={selectedChoice}
              onChoose={handleChoose}
              showHint={showHint}
              onToggleHint={() => setShowHint((v) => !v)}
            />
          ) : (
            <div className="holo-card holo-card-cyan p-4 text-xs text-aurora-text-dim">
              Pas de quiz à cette étape — observe puis passe à la suite.
            </div>
          )}

          <div className="holo-card p-4 space-y-2">
            <div className="text-[11px] uppercase tracking-widest text-aurora-text-dim">Progression</div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-aurora-text-muted">Quiz réussis</span>
              <span className="font-mono font-bold text-emerald-300">
                {score.correct} / {score.total}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-aurora-text-muted">XP prévu</span>
              <span className="font-mono font-bold text-cyan-300">
                {computeXpReward(tutorial, score.ratio)} XP
              </span>
            </div>
            <button
              onClick={() => {
                resetTutorial(tutorial.id)
                awardedRef.current = false
              }}
              className="btn-ghost text-[11px] w-full justify-center"
            >
              <RotateCcw size={10} /> Recommencer
            </button>
          </div>

          {isCompleted && (
            <div className="holo-card holo-card-pink p-4 text-xs">
              <div className="flex items-center gap-2 text-pink-200 font-bold">
                <Award size={14} /> Tutoriel validé
              </div>
              <p className="mt-1 text-aurora-text-dim leading-relaxed">
                Tu peux relire chaque étape ou passer au tutoriel suivant.
              </p>
            </div>
          )}
        </aside>
      </div>

      <div className="flex items-center justify-between border-t border-white/5 px-5 py-3">
        <button
          onClick={goPrevious}
          disabled={stepIndex === 0}
          className="btn-ghost text-xs disabled:opacity-40"
        >
          <ArrowLeft size={12} /> Précédent
        </button>
        <div className="text-[11px] text-aurora-text-dim">
          {quizLocked ? 'Choisis la bonne réponse pour continuer' : ' '}
        </div>
        <button
          onClick={goNext}
          disabled={quizLocked}
          className="btn-aurora text-xs py-2 px-4 disabled:opacity-40"
        >
          {isLastStep ? (
            <>
              <CheckCircle2 size={12} /> Terminer
            </>
          ) : (
            <>
              Suivant <ArrowRight size={12} />
            </>
          )}
        </button>
      </div>
    </div>
  )
}

function StepMedia({ media }: { media: NonNullable<TutorialStep['media']>[number] }) {
  if (media.kind === 'formula') {
    return (
      <div className="holo-card p-4 space-y-2">
        <div className="text-[10px] uppercase tracking-widest text-aurora-text-dim">Formule</div>
        <div className="text-lg">
          <BlockMath>{media.tex}</BlockMath>
        </div>
        {media.caption && (
          <div className="text-xs text-aurora-text-dim italic">{media.caption}</div>
        )}
      </div>
    )
  }
  if (media.kind === 'image') {
    return (
      <img
        src={media.src}
        alt={media.alt}
        className="rounded-2xl border border-white/10 max-w-full"
        loading="lazy"
      />
    )
  }
  if (media.kind === 'table') {
    return (
      <div className="holo-card p-0 overflow-hidden">
        <table className="w-full text-xs">
          {media.headers && (
            <thead className="bg-white/5 text-aurora-text-dim">
              <tr>
                {media.headers.map((h, idx) => (
                  <th key={idx} className="px-3 py-2 text-left font-bold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {media.rows.map((row, r) => (
              <tr key={r} className="odd:bg-white/[0.02]">
                {row.map((cell, c) => (
                  <td key={c} className="px-3 py-2 text-aurora-text">
                    <InlineTextWithMath text={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  if (media.kind === 'quote') {
    return (
      <blockquote className="holo-card holo-card-warm p-4 text-sm italic text-aurora-text">
        «&nbsp;{media.text}&nbsp;»
        {media.author && (
          <footer className="mt-1 text-[11px] not-italic text-aurora-text-dim">
            — {media.author}
          </footer>
        )}
      </blockquote>
    )
  }
  return null
}

function InlineTextWithMath({ text }: { text: string }) {
  const parts = text.split(/\$([^$]+)\$/g)
  if (parts.length === 1) return <>{text}</>
  return (
    <>
      {parts.map((part, idx) =>
        idx % 2 === 1 ? <InlineMath key={idx}>{part}</InlineMath> : <span key={idx}>{part}</span>,
      )}
    </>
  )
}

function QuizBlock({
  step,
  selectedChoice,
  onChoose,
  showHint,
  onToggleHint,
}: {
  step: TutorialStep
  selectedChoice: string | null
  onChoose: (id: string) => void
  showHint: boolean
  onToggleHint: () => void
}) {
  if (!step.quiz) return null
  const selected = step.quiz.choices.find((c) => c.id === selectedChoice)
  return (
    <div className="holo-card holo-card-cyan p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-widest text-cyan-300">Quiz</div>
        {step.quiz.hint && (
          <button onClick={onToggleHint} className="btn-ghost text-[10px]">
            <Lightbulb size={10} /> Indice
          </button>
        )}
      </div>
      <p className="text-sm text-aurora-text font-medium">{step.quiz.question}</p>
      <div className="space-y-2">
        {step.quiz.choices.map((choice) => {
          const active = selectedChoice === choice.id
          const wasChosen = active
          const showFeedback = wasChosen
          const classes = showFeedback
            ? choice.correct
              ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100'
              : 'border-rose-400 bg-rose-500/15 text-rose-100'
            : 'border-white/10 bg-white/5 text-aurora-text hover:border-cyan-400/40'
          return (
            <button
              key={choice.id}
              onClick={() => onChoose(choice.id)}
              className={`w-full rounded-xl border px-3 py-2 text-left text-xs transition-all ${classes}`}
            >
              <div className="flex items-center gap-2">
                {showFeedback &&
                  (choice.correct ? <CheckCircle2 size={12} /> : <XCircle size={12} />)}
                <span>{choice.label}</span>
              </div>
              {active && choice.explanation && (
                <div className="mt-2 text-[11px] opacity-90">{choice.explanation}</div>
              )}
            </button>
          )
        })}
      </div>
      <AnimatePresence>
        {showHint && step.quiz.hint && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="text-[11px] text-amber-200/90 italic"
          >
            {step.quiz.hint}
          </motion.div>
        )}
      </AnimatePresence>
      {selected && !selected.correct && (
        <p className="text-[11px] text-rose-200/80">
          Essaie une autre option — tu peux changer ta réponse.
        </p>
      )}
    </div>
  )
}

function LazySimulation({ id }: { id: SimulationId }) {
  const loader = getSimulationLoader(id)
  if (!loader) {
    return (
      <div className="holo-card p-4 text-xs text-aurora-text-dim italic">
        Simulation « {id} » non disponible dans cette version.
      </div>
    )
  }
  const Comp = useMemo<React.LazyExoticComponent<SimulationComponent>>(
    () => lazy(() => loader().then((mod) => ({ default: mod }))),
    [id],
  )
  return (
    <div className="holo-card p-4">
      <div className="text-[10px] uppercase tracking-widest text-aurora-text-dim mb-2">
        Simulation
      </div>
      <Suspense
        fallback={<div className="text-xs text-aurora-text-dim">Chargement de la simulation…</div>}
      >
        <Comp />
      </Suspense>
    </div>
  )
}
