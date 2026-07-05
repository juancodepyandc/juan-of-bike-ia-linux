import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode, RefObject } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  BookOpen,
  Check,
  ChevronDown,
  Clock,
  Download,
  Flame,
  Gamepad2,
  GraduationCap,
  Heart,
  Layers,
  Lightbulb,
  Loader2,
  Map as MapIcon,
  RefreshCw,
  RotateCcw,
  Shuffle,
  Sparkles,
  Swords,
  Star,
  Target,
  Timer,
  Trophy,
  Trash2,
  Zap,
} from 'lucide-react'
import AskAboutContentBox from '../../components/AskAboutContentBox'
import ClarificationDialog from '../../components/ClarificationDialog'
import type { ClarificationRequest } from '../../components/ClarificationDialog'
import ContextFilesField from '../../components/ContextFilesField'
import ModuleAssetPackCard from '../../components/ModuleAssetPackCard'
import RecoveryBanner from '../../components/RecoveryBanner'
import { buildLearningModuleAssets } from '../../config/moduleAssetPacks'
import { useManagedRuntime } from '../../hooks/useManagedRuntime'
import { useModuleAssetPack } from '../../hooks/useModuleAssetPack'
import { ollamaChatStream } from '../../hooks/useTauri'
import { prepareTaskIntelligence } from '../../services/taskIntelligence'
import { researchLearningTopic, summarizeSourcesForUI, buildAcademicLevelInstructions, type LearningSource, type AcademicIntent } from '../../services/learningResearch'
import { useAppStore } from '../../stores/appStore'
import { useFlashcardsStore, detectSubjectKind, SUBJECT_HINTS, type Flashcard, type FlashcardDeck, type SubjectKind, type KeyPoint } from '../../stores/flashcardsStore'
import MarkdownPro from '../../components/MarkdownPro'
import LyraCharacter from '../../components/voice/LyraCharacter'
import { useLessonProgressStore, LESSON_QUIZ_PASSING_SCORE } from '../../stores/lessonProgressStore'
import { useGamificationStore } from '../../stores/gamificationStore'
import { useGenerationTrackerStore } from '../../stores/generationTrackerStore'
import { useModuleHistoryStore } from '../../stores/moduleHistoryStore'
import { useGenerationRecovery } from '../../hooks/useGenerationRecovery'
import { getErrorMessage } from '../../utils/errors'
import { prepareContextFiles } from '../../utils/multimodalContext'

import type { Tab, LearningPathNode } from './types'
import { LearningMetricCard, DashboardCharts } from './sharedComponents'
import { forecastFromLeitner } from '../../services/learning/fsrsLeitnerBridge'
import { curriculumSvgString } from '../../services/learning/curriculumGraphSvg'

function Dashboard({ onNavigate }: { onNavigate: (tab: Tab) => void }) {
  const { xp, level, streak, badges, quizHistory, learningPaths } = useGamificationStore()
  const { decks, cards } = useFlashcardsStore()
  const xpForNext = Math.max(100, level * level * 100)
  const xpProgress = Math.min(100, (xp / xpForNext) * 100)

  const totalCards = cards.length
  const masteredCards = cards.filter((card) => card.box >= 4).length
  const dueCards = cards.filter((card) => card.dueAt <= Date.now()).length
  // FSRS forecast 7 jours — projection lecture-seule depuis le Leitner store.
  // Donne au learner un horizon : "tu auras N cartes dues d'ici une semaine".
  const fsrsForecast7d = useMemo(() => {
    if (cards.length === 0) return 0
    const buckets = forecastFromLeitner(
      cards.map((c) => ({
        box: c.box,
        streak: c.streak,
        dueAt: c.dueAt,
        lastReviewedAt: c.lastReviewedAt,
        timesCorrect: c.timesCorrect,
        timesWrong: c.timesWrong,
        createdAt: c.createdAt,
      })),
      7,
      new Date(),
    )
    return buckets.reduce((a, b) => a + b, 0)
  }, [cards])
  const leitnerBoxes = useMemo<[number, number, number, number, number]>(() => {
    const buckets: [number, number, number, number, number] = [0, 0, 0, 0, 0]
    for (const card of cards) {
      const idx = Math.max(0, Math.min(4, card.box - 1))
      buckets[idx] += 1
    }
    return buckets
  }, [cards])
  const avgScore = quizHistory.length === 0
    ? 0
    : Math.round(
        (quizHistory.reduce((sum, entry) => sum + entry.score / Math.max(1, entry.total), 0) / quizHistory.length) * 100,
      )

  const shortcuts: Array<{ tab: Tab; icon: typeof Target; label: string; description: string; cta: string }> = [
    { tab: 'quiz', icon: Target, label: 'Quiz', description: 'Verifie tes connaissances avec 5 questions progressives', cta: 'Lancer un quiz' },
    { tab: 'courses', icon: BookOpen, label: 'Cours', description: 'Genere un cours structure sur une matiere', cta: 'Ouvrir un cours' },
    { tab: 'fiches', icon: Layers, label: 'Fiches', description: 'Fabrique un deck de flashcards avec Leitner', cta: 'Creer des fiches' },
    { tab: 'parcours', icon: MapIcon, label: 'Parcours', description: 'Construis un itineraire d apprentissage complet', cta: 'Tracer un parcours' },
  ]

  const isFresh = quizHistory.length === 0 && decks.length === 0 && learningPaths.length === 0

  return (
    <div className="space-y-6 animate-fade-in">
      {isFresh && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass rounded-2xl p-6"
        >
          <div className="flex flex-col gap-4 md:flex-row md:items-center">
            <div style={{ width: 72, height: 86, flexShrink: 0 }}>
              <LyraCharacter
                phase="speaking"
                emotion="happy"
                accent="#d4a64a"
                size={72}
              />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-aurora-text">Bienvenue dans l Academie</p>
              <p className="mt-1 text-xs leading-relaxed text-aurora-text-dim">
                Commence par generer un deck de fiches pour memoriser un sujet, un quiz pour te tester, ou un parcours pour etre guide pas a pas.
                Toutes les sorties sont ancrees sur des sources verifiees (Wikipedia FR/EN + web).
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => onNavigate('fiches')} className="inline-flex items-center gap-1.5 rounded-xl gradient-accent px-3 py-2 text-xs font-medium text-white">
                <Layers size={12} />
                <span>Creer mon premier deck</span>
              </button>
              <button onClick={() => onNavigate('parcours')} className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border bg-aurora-surface-2 px-3 py-2 text-xs font-medium text-aurora-text hover:border-aurora-accent/40">
                <MapIcon size={12} />
                <span>Tracer un parcours</span>
              </button>
            </div>
          </div>
        </motion.div>
      )}
      <LearningVarietyReminder onNavigate={onNavigate} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <LearningMetricCard icon={Star} label="Niveau" value={`${level}`} tone="accent" />
        <LearningMetricCard icon={Flame} label="Serie active" value={`${streak} jour(s)`} tone="warm" />
        <LearningMetricCard icon={Trophy} label="Badges" value={`${badges.length}`} />
        <LearningMetricCard icon={Layers} label="Fiches maitrisees" value={`${masteredCards}/${totalCards}`} tone="accent" />
      </div>

      <div className="glass rounded-2xl p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-aurora-text">Progression globale</p>
            <p className="mt-1 text-xs text-aurora-text-dim">
              XP cumulee et progression vers le prochain niveau.
            </p>
          </div>
          <p className="text-xs text-aurora-text-dim">{xp} / {xpForNext} XP</p>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-aurora-surface-2">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${xpProgress}%` }}
            className="h-full gradient-accent rounded-full"
          />
        </div>
        <div className="mt-4 grid grid-cols-3 gap-3 text-[11px] text-aurora-text-dim">
          <div className="rounded-xl border border-aurora-border/40 bg-aurora-surface-2/60 px-3 py-2">
            <p className="uppercase tracking-[0.16em]">Quiz passes</p>
            <p className="mt-1 text-base font-semibold text-aurora-text">{quizHistory.length}</p>
          </div>
          <div className="rounded-xl border border-aurora-border/40 bg-aurora-surface-2/60 px-3 py-2">
            <p className="uppercase tracking-[0.16em]">Score moyen</p>
            <p className="mt-1 text-base font-semibold text-aurora-text">{avgScore}%</p>
          </div>
          <div className="rounded-xl border border-aurora-border/40 bg-aurora-surface-2/60 px-3 py-2">
            <p className="uppercase tracking-[0.16em]">Fiches dues</p>
            <p className="mt-1 text-base font-semibold text-aurora-text">{dueCards}</p>
          </div>
        </div>
        {totalCards > 0 && (
          <div className="mt-2 flex items-center justify-between rounded-xl border border-aurora-border/30 bg-aurora-surface-2/40 px-3 py-2 text-[11px] text-aurora-text-dim">
            <span className="uppercase tracking-[0.14em]">Prévision FSRS 7j</span>
            <span className="font-semibold text-aurora-text">{fsrsForecast7d} carte{fsrsForecast7d > 1 ? 's' : ''}</span>
          </div>
        )}
      </div>

      {(() => {
        // Resume card — shows the single most actionable next step so the
        // learner does not have to hunt through 4 tabs to find where they
        // left off. Priority:
        //   1. A parcours step currently unlocked but not yet completed,
        //   2. Fiches dues today,
        //   3. The last quiz topic.
        const activePath = learningPaths.find((p) => {
          const nodes = (p.nodes || []) as LearningPathNode[]
          return nodes.some((n) => n?.status !== 'done')
        })
        const activePathNodes = (activePath?.nodes || []) as LearningPathNode[]
        const nextPathStep = activePathNodes.find((n) => n?.status !== 'done')
        const lastQuiz = quizHistory[0]
        if (!activePath && dueCards === 0 && !lastQuiz) return null
        return (
          <div className="glass rounded-2xl p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-accent/80">Continuer</p>
                <p className="mt-1 text-sm font-semibold text-aurora-text">Reprends ton etude la ou tu l as laissee</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {activePath && nextPathStep && (
                  <button
                    onClick={() => onNavigate('parcours')}
                    className="inline-flex items-center gap-1.5 rounded-xl gradient-accent px-3 py-2 text-xs font-medium text-white"
                  >
                    <MapIcon size={12} />
                    <span className="max-w-[16rem] truncate">Parcours: {nextPathStep.title || activePath.title}</span>
                  </button>
                )}
                {dueCards > 0 && (
                  <button
                    onClick={() => onNavigate('fiches')}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-accent/40 bg-aurora-accent/10 px-3 py-2 text-xs font-medium text-aurora-accent-light"
                  >
                    <Layers size={12} />
                    <span>{dueCards} fiche(s) a reviser</span>
                  </button>
                )}
                {lastQuiz && (
                  <button
                    onClick={() => onNavigate('quiz')}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border bg-aurora-surface-2 px-3 py-2 text-xs font-medium text-aurora-text hover:border-aurora-accent/40"
                  >
                    <Target size={12} />
                    <span className="max-w-[16rem] truncate">Refaire: {lastQuiz.topic}</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        )
      })()}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {shortcuts.map(({ tab, icon: Icon, label, description, cta }) => (
          <button
            key={tab}
            onClick={() => onNavigate(tab)}
            className="group glass rounded-2xl p-5 text-left transition-all hover:border-aurora-accent/40 hover:bg-aurora-accent/5"
          >
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-aurora-accent/14 p-2.5 text-aurora-accent">
                <Icon size={18} />
              </div>
              <p className="text-sm font-semibold text-aurora-text">{label}</p>
            </div>
            <p className="mt-3 text-xs leading-relaxed text-aurora-text-dim">{description}</p>
            <p className="mt-3 inline-flex items-center gap-1 text-[11px] font-medium text-aurora-accent opacity-70 transition-opacity group-hover:opacity-100">
              <span>{cta}</span>
              <span aria-hidden>→</span>
            </p>
          </button>
        ))}
      </div>

      {(quizHistory.length > 0 || decks.length > 0) && (
        <DashboardCharts quizHistory={quizHistory} leitnerBoxes={leitnerBoxes} />
      )}

      <CurriculumGraphCard />


      {decks.length > 0 && (
        <div className="glass rounded-2xl p-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-aurora-text">Decks actifs ({decks.length})</h3>
            <button
              onClick={() => onNavigate('fiches')}
              className="text-[11px] font-medium text-aurora-accent hover:underline"
            >
              Gerer →
            </button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {decks.slice(0, 6).map((deck) => {
              const pct = deck.cardCount === 0 ? 0 : Math.round((deck.masteredCount / deck.cardCount) * 100)
              return (
                <button
                  key={deck.id}
                  onClick={() => onNavigate('fiches')}
                  className="rounded-xl border border-aurora-border/50 bg-aurora-surface-2/70 p-4 text-left transition-all hover:border-aurora-accent/40"
                >
                  <p className="truncate text-sm font-medium text-aurora-text">{deck.subject}</p>
                  {deck.theme && <p className="truncate text-[11px] text-aurora-text-dim">{deck.theme}</p>}
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-aurora-surface-2">
                    <div className="h-full gradient-accent rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="mt-2 flex justify-between text-[10px] text-aurora-text-dim">
                    <span>{deck.cardCount} fiches</span>
                    <span>{pct}% maitrise</span>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {badges.length > 0 && (
        <div className="glass rounded-2xl p-5">
          <h3 className="text-sm font-semibold text-aurora-text">Badges debloques</h3>
          <div className="mt-4 flex flex-wrap gap-3">
            {badges.map((badge) => (
              <div
                key={badge.id}
                className="flex items-center gap-2 rounded-xl border border-aurora-border bg-aurora-surface-2 px-3 py-2"
              >
                <span className="text-lg">{badge.icon}</span>
                <span className="text-xs text-aurora-text">{badge.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {quizHistory.length > 0 && (
        <div className="glass rounded-2xl p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-aurora-text">Derniers quiz</h3>
            <button
              onClick={() => onNavigate('quiz')}
              className="text-[11px] font-medium text-aurora-accent hover:underline"
            >
              Relancer un quiz →
            </button>
          </div>
          <div className="mt-4 space-y-2">
            {quizHistory.slice(-6).reverse().map((entry, index) => {
              const pct = entry.total === 0 ? 0 : Math.round((entry.score / entry.total) * 100)
              const tone = pct >= 80 ? 'text-aurora-green' : pct >= 50 ? 'text-aurora-accent' : 'text-aurora-orange'
              return (
                <div
                  key={`${entry.date}-${index}`}
                  className="rounded-xl bg-aurora-surface-2 px-3 py-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate text-sm text-aurora-text">{entry.topic}</p>
                    <span className={`text-xs font-medium ${tone}`}>
                      {entry.score}/{entry.total} · {pct}%
                    </span>
                  </div>
                  <div className="mt-2 h-1 overflow-hidden rounded-full bg-aurora-surface">
                    <div
                      className={`h-full rounded-full ${pct >= 80 ? 'bg-aurora-green' : pct >= 50 ? 'gradient-accent' : 'bg-aurora-orange'}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <p className="mt-1 text-[10px] text-aurora-text-dim">
                    {new Date(entry.date).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Carte "Programme BAC STI2D/SIN" : rend l'arbre de prérequis du BO en SVG
 * inline. Filtre par track (MAT / PC / SIN / I2D) via tabs.
 */
function CurriculumGraphCard() {
  const [track, setTrack] = useState<'MAT' | 'PC' | 'SIN' | 'I2D'>('SIN')
  const svg = useMemo(() => curriculumSvgString({ track, direction: 'LR' }), [track])
  const tracks: Array<{ id: typeof track; label: string }> = [
    { id: 'SIN', label: 'SIN' },
    { id: 'MAT', label: 'Maths' },
    { id: 'PC', label: 'Physique-Chimie' },
    { id: 'I2D', label: 'I2D' },
  ]
  return (
    <div className="glass rounded-2xl p-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h3 className="text-sm font-semibold text-aurora-text">Programme BAC STI2D — arbre de prérequis</h3>
          <p className="mt-1 text-xs text-aurora-text-dim">Suis les flèches : pour atteindre un concept, maîtrise ses parents.</p>
        </div>
        <div className="flex gap-1">
          {tracks.map((t) => (
            <button
              key={t.id}
              onClick={() => setTrack(t.id)}
              className={`text-[11px] rounded-md px-2.5 py-1 font-medium ${track === t.id ? 'bg-aurora-accent text-white' : 'bg-aurora-surface-2 text-aurora-text-dim hover:text-aurora-text'}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <div
        className="mt-4 overflow-auto rounded-xl border border-aurora-border/40 bg-aurora-surface-2/40 p-2"
        style={{ maxHeight: 460 }}
        // SVG provient d'un builder déterministe (curriculumGraphSvg) qui ne
        // touche jamais à l'input utilisateur — donc innerHTML est sûr ici.
        // Si jamais on ajoutait des labels free-form, il faudrait DOMPurify.
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </div>
  )
}

// v83k — variety reminder : rappelle qu'il y a 4 formats au-delà du QCM
// (open question, mind-map, flashcards, table). Si toutes les dernières gen
// sont QCM, surligne le warning. Sinon, juste un encart pédagogique.
function LearningVarietyReminder({ onNavigate }: { onNavigate: (tab: Tab) => void }) {
  const formats: Array<{ tab: Tab; label: string; subtitle: string; icon: typeof Layers; tone: string }> = [
    { tab: 'quiz', label: 'Quiz QCM', subtitle: '4 options · feedback', icon: Target, tone: 'sky' },
    { tab: 'fiches', label: 'Fiches Leitner', subtitle: 'SM-2 spaced rep', icon: Layers, tone: 'amber' },
    { tab: 'parcours', label: 'Parcours bac', subtitle: 'synthèse → exam', icon: MapIcon, tone: 'violet' },
    { tab: 'physics', label: 'Lab simulé', subtitle: 'physique interactive', icon: Lightbulb, tone: 'emerald' },
  ]
  const toneCls: Record<string, string> = {
    sky: 'border-sky-500/30 hover:border-sky-500/60 bg-sky-500/5',
    amber: 'border-amber-500/30 hover:border-amber-500/60 bg-amber-500/5',
    violet: 'border-violet-500/30 hover:border-violet-500/60 bg-violet-500/5',
    emerald: 'border-emerald-500/30 hover:border-emerald-500/60 bg-emerald-500/5',
  }
  return (
    <div className="rounded-2xl border border-aurora-border/40 bg-aurora-surface/60 p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Pas que des QCM</p>
          <p className="text-[13px] text-aurora-text mt-0.5">4 formats expert pour varier la pratique selon le type de compétence.</p>
        </div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        {formats.map((f) => {
          const Icon = f.icon
          return (
            <button
              key={f.tab}
              onClick={() => onNavigate(f.tab)}
              className={`text-left rounded-xl border ${toneCls[f.tone]} p-3 transition-colors`}
            >
              <div className="flex items-center gap-2">
                <Icon size={14} className="text-aurora-text" />
                <span className="text-[12px] font-medium text-aurora-text">{f.label}</span>
              </div>
              <p className="mt-1 text-[10px] text-aurora-text-dim">{f.subtitle}</p>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default Dashboard
