import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { BookOpen, CheckCircle2, Clock, Play, Sparkles, Trophy } from 'lucide-react'
import {
  listTutorials,
  type LabId,
  type Tutorial,
  type TutorialDifficulty,
} from '../../services/learning/tutorialEngine'
import { useTutorialStore } from '../../stores/tutorialStore'
import TutorialRunner from './TutorialRunner'

type Props = {
  lab: LabId
  accent?: 'cyan' | 'violet' | 'emerald' | 'orange' | 'pink'
}

const DIFFICULTY_LABEL: Record<TutorialDifficulty, string> = {
  debutant: 'Débutant',
  intermediaire: 'Intermédiaire',
  avance: 'Avancé',
}

const DIFFICULTY_COLORS: Record<TutorialDifficulty, string> = {
  debutant: 'text-emerald-300 border-emerald-400/40 bg-emerald-500/10',
  intermediaire: 'text-cyan-300 border-cyan-400/40 bg-cyan-500/10',
  avance: 'text-pink-300 border-pink-400/40 bg-pink-500/10',
}

export default function TutorialsPanel({ lab, accent = 'cyan' }: Props) {
  const tutorials = useMemo(() => listTutorials(lab), [lab])
  const completedIds = useTutorialStore((s) => s.completed)
  const openTutorial = useTutorialStore((s) => s.openTutorial)
  const activeId = useTutorialStore((s) => s.activeTutorialId)
  const closeTutorial = useTutorialStore((s) => s.closeTutorial)
  const progress = useTutorialStore((s) => s.progress)

  const [filter, setFilter] = useState<TutorialDifficulty | 'all'>('all')

  const visible = useMemo(() => {
    if (filter === 'all') return tutorials
    return tutorials.filter((t) => t.difficulty === filter)
  }, [tutorials, filter])

  const activeTutorial = activeId ? tutorials.find((t) => t.id === activeId) : null

  if (tutorials.length === 0) {
    return (
      <div className="holo-card p-5 text-sm text-aurora-text-dim">
        Aucun tutoriel guidé disponible pour ce laboratoire pour le moment.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <AnimatePresence mode="wait">
        {activeTutorial ? (
          <motion.div
            key={`runner-${activeTutorial.id}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
          >
            <TutorialRunner tutorial={activeTutorial} onClose={closeTutorial} />
          </motion.div>
        ) : (
          <motion.div
            key="grid"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="space-y-4"
          >
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <div className="mono-kicker text-[10px] text-aurora-text-dim">
                  Tutoriels guidés
                </div>
                <h3 className="text-xl font-bold gradient-text-ocean">
                  Apprends pas-à-pas avec des quiz
                </h3>
              </div>
              <div className="flex gap-1.5 p-1 rounded-2xl border border-white/10 bg-white/5 backdrop-blur">
                {(['all', 'debutant', 'intermediaire', 'avance'] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={`btn-pill text-[11px] ${filter === f ? 'is-active' : ''}`}
                  >
                    {f === 'all' ? 'Tous' : DIFFICULTY_LABEL[f]}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {visible.map((tutorial) => (
                <TutorialCard
                  key={tutorial.id}
                  tutorial={tutorial}
                  completed={completedIds.includes(tutorial.id)}
                  stepIndex={progress[tutorial.id]?.currentStepIndex ?? 0}
                  onOpen={() => openTutorial(tutorial.id)}
                  accent={accent}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function TutorialCard({
  tutorial,
  completed,
  stepIndex,
  onOpen,
  accent,
}: {
  tutorial: Tutorial
  completed: boolean
  stepIndex: number
  onOpen: () => void
  accent: 'cyan' | 'violet' | 'emerald' | 'orange' | 'pink'
}) {
  const pct = Math.min(100, ((stepIndex + (completed ? 1 : 0)) / tutorial.steps.length) * 100)
  const accentGrad = {
    cyan: 'from-cyan-400 to-blue-500',
    violet: 'from-violet-400 to-purple-500',
    emerald: 'from-emerald-400 to-teal-500',
    orange: 'from-orange-400 to-rose-500',
    pink: 'from-pink-400 to-fuchsia-500',
  }[accent]

  return (
    <motion.button
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.98 }}
      onClick={onOpen}
      className="group relative overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur p-4 text-left transition-all hover:border-cyan-400/40"
    >
      <div className="flex items-start justify-between gap-3">
        <div
          className={`rounded-xl bg-gradient-to-br ${accentGrad} p-2 shadow-lg shrink-0`}
        >
          <BookOpen size={16} className="text-white" />
        </div>
        {completed && (
          <div className="flex items-center gap-1 text-[10px] text-emerald-300">
            <CheckCircle2 size={12} /> Terminé
          </div>
        )}
      </div>
      <h4 className="mt-3 text-sm font-bold text-aurora-text leading-snug">
        {tutorial.title}
      </h4>
      <p className="mt-1 text-xs text-aurora-text-dim line-clamp-2">{tutorial.summary}</p>

      <div className="mt-3 flex items-center gap-2 flex-wrap">
        <span
          className={`text-[10px] px-2 py-0.5 rounded-full border ${DIFFICULTY_COLORS[tutorial.difficulty]}`}
        >
          {DIFFICULTY_LABEL[tutorial.difficulty]}
        </span>
        <span className="text-[10px] text-aurora-text-dim inline-flex items-center gap-1">
          <Clock size={10} /> {tutorial.durationMin} min
        </span>
        <span className="text-[10px] text-aurora-text-dim inline-flex items-center gap-1">
          <Trophy size={10} /> {tutorial.xpReward} XP
        </span>
        <span className="text-[10px] text-aurora-text-dim inline-flex items-center gap-1">
          <Sparkles size={10} /> {tutorial.steps.length} étapes
        </span>
      </div>

      <div className="mt-3 h-1 w-full rounded-full bg-white/5 overflow-hidden">
        <div className={`h-full bg-gradient-to-r ${accentGrad}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-3 flex items-center gap-2 text-[11px] font-bold text-cyan-300 opacity-0 group-hover:opacity-100 transition-opacity">
        <Play size={12} /> {completed ? 'Revoir' : stepIndex > 0 ? 'Reprendre' : 'Commencer'}
      </div>
    </motion.button>
  )
}
