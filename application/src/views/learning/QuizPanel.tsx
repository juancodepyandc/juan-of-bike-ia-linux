import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLearningSessionStore } from '../../stores/learningSessionStore'
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
import VoicePushToTalk from '../../components/VoicePushToTalk'
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
import { useLessonProgressStore, LESSON_QUIZ_PASSING_SCORE } from '../../stores/lessonProgressStore'
import { useGamificationStore } from '../../stores/gamificationStore'
import { useGenerationTrackerStore } from '../../stores/generationTrackerStore'
import { useModuleHistoryStore } from '../../stores/moduleHistoryStore'
import { useGenerationRecovery } from '../../hooks/useGenerationRecovery'
import { getErrorMessage } from '../../utils/errors'
import { prepareContextFiles } from '../../utils/multimodalContext'

import type { Tab, QuizMode, ExerciseMode, QuizFormatPref, GameTerm, GamePayload, QuizQuestion, QuizPayload, LessonRef } from './types'
import { buildLearningSystemPrompt, extractJsonArray, findBalancedSlice } from './utils'
import { XpPopup, SourcesPanel } from './sharedComponents'

function OpenAnswerBlock({
  question,
  subject,
  level,
  model,
  revealed,
  onSubmit,
  onNext,
}: {
  question: QuizQuestion
  subject: string
  level?: string
  model: string
  revealed: boolean
  onSubmit: () => void
  onNext: () => void
}) {
  const [draft, setDraft] = useState('')
  const totalPoints = question.totalPoints
    ?? (question.gradingCriteria?.reduce((sum, c) => sum + (Number.isFinite(c.points) ? c.points : 0), 0) ?? 20)

  return (
    <div className="space-y-4">
      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        disabled={revealed}
        rows={8}
        placeholder="Redige ici ta reponse comme en condition d epreuve. Pas de panique — le barème et la correction type apparaissent apres validation."
        className="w-full rounded-2xl border border-aurora-border bg-aurora-bg/60 px-4 py-3 text-sm text-aurora-text outline-none transition-colors focus:border-aurora-accent/50 disabled:opacity-70"
      />
      {!revealed && (
        <div className="flex items-center gap-2 -mt-2">
          <VoicePushToTalk
            onTranscript={(text) => setDraft((prev) => (prev.trim() ? `${prev}\n${text}` : text))}
            label="Dicter ta rédaction"
            size={36}
          />
          <span className="text-[11px] text-aurora-text-dim">Dicte ta rédaction au micro</span>
        </div>
      )}
      {!revealed && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-[11px] text-aurora-text-dim">
            {draft.trim().split(/\s+/).filter(Boolean).length} mots redige(s). Valider revele le bareme et la correction type.
          </p>
          <button
            onClick={() => onSubmit()}
            disabled={draft.trim().length < 30}
            className="rounded-xl gradient-accent px-4 py-2 text-xs font-medium text-white disabled:opacity-50"
          >
            Valider ma redaction
          </button>
        </div>
      )}
      {revealed && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-aurora-border/40 bg-aurora-surface/55 px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.18em] text-aurora-text-dim">Ta redaction</p>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-aurora-text">{draft || '(aucune redaction — lecture du corrige)'}</p>
          </div>
          {question.answerOutline && question.answerOutline.length > 0 && (
            <div className="rounded-2xl border border-aurora-accent/25 bg-aurora-accent/8 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-aurora-accent/90">Plan attendu</p>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-aurora-text">
                {question.answerOutline.map((item, idx) => <li key={idx}>{item}</li>)}
              </ol>
            </div>
          )}
          {question.gradingCriteria && question.gradingCriteria.length > 0 && (
            <div className="rounded-2xl border border-aurora-border/40 bg-aurora-surface/55 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-aurora-text-dim">Bareme officiel — total {totalPoints} pts</p>
              <ul className="mt-2 space-y-1 text-sm text-aurora-text">
                {question.gradingCriteria.map((c, idx) => (
                  <li key={idx} className="flex items-center justify-between gap-2">
                    <span>{c.label}</span>
                    <span className="font-mono text-xs text-aurora-accent">{c.points} pts</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="rounded-2xl border border-aurora-green/30 bg-aurora-green/10 px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.18em] text-aurora-green">Correction redigee</p>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-aurora-text">{question.explanation}</p>
          </div>
          <AskAboutContentBox
            label="Faire corriger ma redaction"
            subject={subject}
            level={level}
            model={model}
            context={[
              `Sujet d examen: ${question.question}`,
              question.answerOutline && question.answerOutline.length > 0
                ? `Plan attendu: ${question.answerOutline.join(' / ')}`
                : '',
              question.gradingCriteria && question.gradingCriteria.length > 0
                ? `Bareme: ${question.gradingCriteria.map((c) => `${c.label} (${c.points} pts)`).join(' | ')}`
                : '',
              `Corrige redige par le module: ${question.explanation}`,
              `Redaction de l utilisateur: ${draft || '(vide)'}`,
            ].filter(Boolean).join('\n')}
            placeholder="Ex: corrige ma redaction en appliquant le bareme, note-moi sur 20 et indique ce qui manque."
          />
          <div className="flex justify-end">
            <button
              onClick={() => onNext()}
              className="rounded-xl gradient-accent px-4 py-2 text-xs font-medium text-white"
            >
              Question suivante
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Détection format naturel du sujet ─────────���───────────────────────────

function detectQuizNaturalFormat(topicStr: string): 'mcq' | 'open' | 'ambiguous' {
  const lower = topicStr.toLowerCase()
  const mcqTerms = ['maths', 'mathématiques', 'mathematiques', 'physique', 'chimie', 'biologie', 'informatique', 'svt', 'algorithme', 'calcul', 'equation', 'géométrie', 'geometrie', 'statistique', 'trigonométrie', 'sciences naturelles']
  const openTerms = ['philo', 'philosophie', 'littérature', 'litterature', 'dissertation', 'commentaire', 'histoire', 'géographie', 'geographie', 'rédaction', 'redaction', 'argumentation', 'explication de texte', 'droit']
  const hasMcq = mcqTerms.some((k) => lower.includes(k))
  const hasOpen = openTerms.some((k) => lower.includes(k))
  if (hasMcq && !hasOpen) return 'mcq'
  if (hasOpen && !hasMcq) return 'open'
  return 'ambiguous'
}

// ── Prompt mini-jeux ─────────────────��─────────────────────────────────────

function buildGameSystemPrompt(mode: ExerciseMode): string {
  if (mode === 'words') return 'Tu es un générateur de jeux éducatifs.\nTÂCHE: Génère un jeu "Mots révélés".\nFORMAT: tableau JSON [{word,definition,hints:[h1,h2,h3]}] (6-10 objets). Retourne UNIQUEMENT le tableau JSON.'
  if (mode === 'pairs') return 'Tu es un générateur de jeux éducatifs.\nTÂCHE: Génère un jeu "Relie les paires".\nFORMAT: tableau JSON [{word,definition,hints:[]}] (6-8 objets, définitions max 80 car). Retourne UNIQUEMENT le tableau JSON.'
  return 'Tu es un générateur de jeux éducatifs.\nTÂCHE: Génère un texte à trous.\nFORMAT: objet JSON {passage,blanks:[{word,options:[4 choix],sentence}]}. passage: 4-8 phrases avec mots remplacés par __MOT__. Retourne UNIQUEMENT l\'objet JSON.'
}

// ── Mini-jeux ──────────────────────────────────────────────────────────────

function WordsGame({ data, onDone }: { data: GameTerm[]; onDone: (score: number) => void }) {
  const [current, setCurrent] = useState(0)
  const [hintsRevealed, setHintsRevealed] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const [total, setTotal] = useState(0)
  const [done, setDone] = useState(false)
  const term = data[current]
  const maxHints = Math.min(3, term?.hints?.filter(Boolean).length ?? 0)
  const markAnswer = useCallback((knew: boolean) => {
    const pts = knew ? Math.max(1, 3 - hintsRevealed) : 0
    const next = total + pts
    setTotal(next)
    if (current + 1 >= data.length) { setDone(true); onDone(next); return }
    setTimeout(() => { setCurrent((c) => c + 1); setHintsRevealed(0); setRevealed(false) }, 500)
  }, [current, data.length, hintsRevealed, onDone, total])
  if (done || !term) {
    return <div className="flex flex-col items-center gap-4 py-8 text-center"><Trophy size={40} className="text-aurora-accent" /><p className="text-xl font-bold gradient-text">Terminé ! {total} points</p></div>
  }
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="flex items-center justify-between text-xs text-aurora-text-dim"><span>Terme {current + 1}/{data.length}</span><span className="font-semibold text-aurora-accent">{total} pts</span></div>
      <div className="rounded-2xl p-6 text-center" style={{ background: 'rgba(6,182,212,0.06)', border: '1px solid rgba(6,182,212,0.2)' }}>
        <p className="text-2xl font-bold" style={{ background: 'linear-gradient(135deg,#06b6d4,#8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{term.word}</p>
        <p className="mt-2 text-xs text-aurora-text-dim">Rappelle-toi la définition, puis révèle</p>
        <div className="mt-4 space-y-2">
          {Array.from({ length: hintsRevealed }).map((_, i) => (
            <div key={i} className="rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-4 py-2 text-sm text-aurora-text-dim text-left">
              <span className="text-aurora-accent font-medium">Indice {i + 1}:</span>{' '}{term.hints?.[i] ?? ''}
            </div>
          ))}
          {hintsRevealed < maxHints && !revealed && (
            <button onClick={() => setHintsRevealed((h) => h + 1)} className="text-xs text-aurora-text-dim hover:text-aurora-accent transition-colors">Voir indice suivant (−1 pt)</button>
          )}
        </div>
        {!revealed ? (
          <button onClick={() => setRevealed(true)} className="mt-5 rounded-xl px-6 py-2.5 text-sm font-medium text-white" style={{ background: 'linear-gradient(135deg,#06b6d4,#8b5cf6)' }}>Révéler la définition</button>
        ) : (
          <div className="mt-4 space-y-3">
            <div className="rounded-xl p-4 text-sm text-aurora-text leading-relaxed text-left" style={{ background: 'rgba(6,182,212,0.08)', border: '1px solid rgba(6,182,212,0.25)' }}>{term.definition}</div>
            <div className="flex gap-2 justify-center">
              <button onClick={() => markAnswer(false)} className="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm text-red-400 hover:bg-red-500/20 transition-colors">✗ Je ne savais pas</button>
              <button onClick={() => markAnswer(true)} className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-400 hover:bg-emerald-500/20 transition-colors">✓ Je savais</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function PairsGame({ data, onDone }: { data: GameTerm[]; onDone: (score: number) => void }) {
  const shuffledRight = useMemo(() => [...data].sort(() => Math.random() - 0.5), [data])
  const [selectedLeft, setSelectedLeft] = useState<number | null>(null)
  const [selectedRight, setSelectedRight] = useState<number | null>(null)
  const [matched, setMatched] = useState<Set<number>>(new Set())
  const [wrongPair, setWrongPair] = useState<{ l: number; r: number } | null>(null)
  const [errors, setErrors] = useState(0)
  const [done, setDone] = useState(false)
  const tryMatch = useCallback((li: number, ri: number) => {
    if (data[li].word === shuffledRight[ri].word) {
      const next = new Set(matched); next.add(li); setMatched(next); setSelectedLeft(null); setSelectedRight(null)
      if (next.size >= data.length) { setDone(true); onDone(Math.max(0, data.length * 2 - errors)) }
    } else {
      setWrongPair({ l: li, r: ri }); setErrors((e) => e + 1)
      setTimeout(() => { setWrongPair(null); setSelectedLeft(null); setSelectedRight(null) }, 700)
    }
  }, [data, errors, matched, onDone, shuffledRight])
  const handleLeft = (i: number) => {
    if (matched.has(i)) return
    if (selectedRight !== null) { tryMatch(i, selectedRight); return }
    setSelectedLeft(i)
  }
  const handleRight = (i: number) => {
    const isMatchedRight = matched.has(data.findIndex((d) => d.word === shuffledRight[i].word))
    if (isMatchedRight) return
    if (selectedLeft !== null) { tryMatch(selectedLeft, i); return }
    setSelectedRight(i)
  }
  if (done) {
    return <div className="flex flex-col items-center gap-4 py-8 text-center"><Trophy size={40} className="text-aurora-accent" /><p className="text-xl font-bold gradient-text">Toutes les paires !</p><p className="text-sm text-aurora-text-dim">{Math.max(0, data.length * 2 - errors)} pts · {errors} erreur(s)</p></div>
  }
  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex items-center justify-between mb-4 text-xs text-aurora-text-dim"><span>{matched.size}/{data.length} paires</span><span>{errors} erreur(s)</span></div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-aurora-text-dim text-center mb-2">Termes</p>
          {data.map((item, i) => {
            const isMatched = matched.has(i); const isSel = selectedLeft === i; const isWrong = wrongPair?.l === i
            return <button key={i} onClick={() => handleLeft(i)} disabled={isMatched} className="w-full rounded-xl px-3 py-2.5 text-sm text-left transition-all" style={{ background: isMatched ? 'rgba(74,222,128,0.12)' : isWrong ? 'rgba(239,68,68,0.15)' : isSel ? 'rgba(6,182,212,0.15)' : 'rgba(255,255,255,0.04)', border: `1px solid ${isMatched ? 'rgba(74,222,128,0.4)' : isWrong ? 'rgba(239,68,68,0.4)' : isSel ? 'rgba(6,182,212,0.5)' : 'rgba(255,255,255,0.08)'}`, color: isMatched ? '#4ade80' : isSel ? '#06b6d4' : '#e2e8f0', opacity: isMatched ? 0.6 : 1, cursor: isMatched ? 'default' : 'pointer' }}>{isMatched ? '✓ ' : ''}{item.word}</button>
          })}
        </div>
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-aurora-text-dim text-center mb-2">Définitions</p>
          {shuffledRight.map((item, i) => {
            const leftIdx = data.findIndex((d) => d.word === item.word); const isMatched = matched.has(leftIdx); const isSel = selectedRight === i; const isWrong = wrongPair?.r === i
            return <button key={i} onClick={() => handleRight(i)} disabled={isMatched} className="w-full rounded-xl px-3 py-2.5 text-xs text-left transition-all" style={{ background: isMatched ? 'rgba(74,222,128,0.12)' : isWrong ? 'rgba(239,68,68,0.15)' : isSel ? 'rgba(139,92,246,0.15)' : 'rgba(255,255,255,0.04)', border: `1px solid ${isMatched ? 'rgba(74,222,128,0.4)' : isWrong ? 'rgba(239,68,68,0.4)' : isSel ? 'rgba(139,92,246,0.5)' : 'rgba(255,255,255,0.08)'}`, color: isMatched ? '#4ade80' : isSel ? '#a78bfa' : '#94a3b8', opacity: isMatched ? 0.6 : 1, cursor: isMatched ? 'default' : 'pointer', lineHeight: 1.35 }}>{isMatched ? '✓ ' : ''}{item.definition}</button>
          })}
        </div>
      </div>
    </div>
  )
}

function FillBlankGame({ data, onDone }: { data: GamePayload; onDone: (score: number) => void }) {
  const blanks = data.blanks ?? []
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [submitted, setSubmitted] = useState(false)
  const passageSegments = (data.passage ?? '').split(/(__\w+__)/)
  const handleSubmit = () => { setSubmitted(true); onDone(blanks.filter((b, i) => answers[i] === b.word).length * 2) }
  if (submitted) {
    let bi = 0
    const rendered = passageSegments.map((seg, i) => {
      if (/__\w+__/.test(seg)) {
        const b = blanks[bi]; const ua = answers[bi]; const ok = ua === b?.word; bi++
        return <span key={i} style={{ padding: '1px 6px', borderRadius: '4px', fontWeight: 600, background: ok ? 'rgba(74,222,128,0.2)' : 'rgba(239,68,68,0.2)', border: `1px solid ${ok ? 'rgba(74,222,128,0.5)' : 'rgba(239,68,68,0.5)'}`, color: ok ? '#4ade80' : '#f87171' }}>{ua ?? '?'}{!ok && <span className="text-xs opacity-70"> (→ {b?.word})</span>}</span>
      }
      return <span key={i}>{seg}</span>
    })
    const correct = blanks.filter((b, i) => answers[i] === b.word).length
    return <div className="mx-auto max-w-2xl space-y-4"><div className="flex items-center justify-between"><p className="text-sm font-semibold text-aurora-text">Résultat</p><p className="text-sm text-aurora-accent font-semibold">{correct}/{blanks.length} · {correct * 2} pts</p></div><div className="rounded-2xl border border-aurora-border/40 bg-aurora-surface-2 p-5 text-sm leading-loose text-aurora-text">{rendered}</div></div>
  }
  let bi2 = 0
  const renderedInput = passageSegments.map((seg, i) => {
    if (/__\w+__/.test(seg)) {
      const idx = bi2++; const ans = answers[idx]
      return <span key={i} style={{ display: 'inline-block', minWidth: '80px', padding: '1px 6px', borderRadius: '4px', fontWeight: 600, background: ans ? 'rgba(6,182,212,0.15)' : 'rgba(255,255,255,0.06)', border: `1px solid ${ans ? 'rgba(6,182,212,0.4)' : 'rgba(255,255,255,0.12)'}`, color: ans ? '#06b6d4' : '#64748b' }}>{ans ?? '___'}</span>
    }
    return <span key={i}>{seg}</span>
  })
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="rounded-2xl border border-aurora-border/40 bg-aurora-surface-2 p-5 text-sm leading-loose text-aurora-text">{renderedInput}</div>
      <div className="space-y-2">
        <p className="text-xs text-aurora-text-dim">Clique pour chaque trou :</p>
        {blanks.map((blank, idx) => (
          <div key={idx} className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-aurora-text-dim w-5">{idx + 1}.</span>
            {blank.options.map((opt) => (
              <button key={opt} onClick={() => !submitted && setAnswers((p) => ({ ...p, [idx]: opt }))} className="rounded-lg px-3 py-1.5 text-xs transition-all" style={{ background: answers[idx] === opt ? 'rgba(6,182,212,0.2)' : 'rgba(255,255,255,0.04)', border: `1px solid ${answers[idx] === opt ? 'rgba(6,182,212,0.5)' : 'rgba(255,255,255,0.1)'}`, color: answers[idx] === opt ? '#06b6d4' : '#94a3b8' }}>{opt}</button>
            ))}
          </div>
        ))}
      </div>
      <button onClick={handleSubmit} disabled={!blanks.every((_, i) => answers[i] !== undefined)} className="w-full rounded-xl py-2.5 text-sm font-medium text-white disabled:opacity-50" style={{ background: 'linear-gradient(135deg,#06b6d4,#8b5cf6)' }}>Valider</button>
    </div>
  )
}

// ── Examen blanc avec timer compte à rebours ───────────────────────────────

function ExamTimerSession({
  questions,
  durationMinutes,
  onFinish,
}: {
  questions: QuizQuestion[]
  durationMinutes: number
  onFinish: (score: number, total: number) => void
}) {
  const totalSeconds = durationMinutes * 60
  const [secondsLeft, setSecondsLeft] = useState(totalSeconds)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, number | string>>({})
  const [submitted, setSubmitted] = useState(false)
  const timerRef = useRef<number | null>(null)
  useEffect(() => {
    timerRef.current = window.setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) { window.clearInterval(timerRef.current!); setSubmitted(true); return 0 }
        return s - 1
      })
    }, 1000)
    return () => { if (timerRef.current) window.clearInterval(timerRef.current) }
  }, [])
  useEffect(() => { if (submitted && timerRef.current) window.clearInterval(timerRef.current) }, [submitted])
  const pct = (secondsLeft / totalSeconds) * 100
  const mins = Math.floor(secondsLeft / 60)
  const secs = secondsLeft % 60
  const timerUrgent = secondsLeft < 300
  const handleExamSubmit = () => {
    if (timerRef.current) window.clearInterval(timerRef.current)
    setSubmitted(true)
    const mcqQs = questions.filter((q) => q.kind !== 'open')
    onFinish(mcqQs.filter((q, i) => answers[i] === q.correctIndex).length, mcqQs.length)
  }
  if (submitted) {
    const mcqQs = questions.filter((q) => q.kind !== 'open')
    const correct = mcqQs.filter((q, i) => answers[i] === q.correctIndex).length
    const pctScore = mcqQs.length === 0 ? 0 : Math.round((correct / mcqQs.length) * 100)
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <div className="rounded-2xl p-6 text-center" style={{ background: 'rgba(6,182,212,0.06)', border: '1px solid rgba(6,182,212,0.2)' }}>
          <GraduationCap size={40} className="mx-auto text-aurora-accent" />
          <p className="mt-3 text-xl font-bold gradient-text">Examen terminé !</p>
          <p className="mt-2 text-3xl font-bold text-aurora-text">{pctScore}%</p>
          <p className="mt-1 text-sm text-aurora-text-dim">{correct}/{mcqQs.length} QCM · {secondsLeft === 0 ? 'Temps écoulé' : 'Copie remise'}</p>
        </div>
        <div className="space-y-3">
          {questions.map((q, i) => (
            <div key={i} className="rounded-xl border border-aurora-border/40 bg-aurora-surface-2 p-4">
              <p className="text-sm font-medium text-aurora-text">{i + 1}. {q.question}</p>
              {q.kind !== 'open' && <p className="mt-1 text-xs"><span className={answers[i] === q.correctIndex ? 'text-emerald-400' : 'text-red-400'}>{q.options[answers[i] as number] ?? 'Pas de réponse'}</span>{answers[i] !== q.correctIndex && <span className="text-aurora-text-dim"> → {q.options[q.correctIndex]}</span>}</p>}
              <p className="mt-2 text-xs text-aurora-text-dim border-t border-aurora-border/30 pt-2">{q.explanation}</p>
            </div>
          ))}
        </div>
      </div>
    )
  }
  const q = questions[currentIndex]
  if (!q) return null
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="rounded-2xl p-4" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Clock size={16} className={timerUrgent ? 'text-red-400 animate-pulse' : 'text-aurora-text-dim'} />
            <span className={`text-sm font-mono font-bold ${timerUrgent ? 'text-red-400' : 'text-aurora-text'}`}>{String(mins).padStart(2, '0')}:{String(secs).padStart(2, '0')}</span>
            <span className="text-xs text-aurora-text-dim">/ {durationMinutes} min</span>
          </div>
          <span className="text-xs text-aurora-text-dim">{currentIndex + 1}/{questions.length}</span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-aurora-surface-2">
          <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${pct}%`, background: timerUrgent ? 'linear-gradient(90deg,#ef4444,#f97316)' : 'linear-gradient(90deg,#06b6d4,#8b5cf6)' }} />
        </div>
      </div>
      <div className="rounded-2xl p-5" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
        <p className="text-base font-medium text-aurora-text">{q.question}</p>
        {q.kind === 'open' ? (
          <textarea className="mt-4 w-full rounded-xl border border-aurora-border bg-aurora-surface-2 p-3 text-sm text-aurora-text outline-none focus:border-aurora-accent/50 resize-none" rows={6} placeholder="Rédigez votre réponse..." value={(answers[currentIndex] as string) ?? ''} onChange={(e) => setAnswers((prev) => ({ ...prev, [currentIndex]: e.target.value }))} />
        ) : (
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {q.options.map((opt, oi) => (
              <button key={oi} onClick={() => setAnswers((prev) => ({ ...prev, [currentIndex]: oi }))} className="rounded-xl border p-3 text-sm text-left transition-all" style={{ background: answers[currentIndex] === oi ? 'rgba(6,182,212,0.15)' : 'rgba(255,255,255,0.03)', border: `1px solid ${answers[currentIndex] === oi ? 'rgba(6,182,212,0.5)' : 'rgba(255,255,255,0.08)'}`, color: answers[currentIndex] === oi ? '#06b6d4' : '#e2e8f0' }}>{opt}</button>
            ))}
          </div>
        )}
        <div className="mt-4 flex justify-between gap-2">
          <button onClick={() => setCurrentIndex((c) => Math.max(0, c - 1))} disabled={currentIndex === 0} className="rounded-lg border border-aurora-border px-3 py-1.5 text-xs text-aurora-text-dim disabled:opacity-40">← Précédent</button>
          {currentIndex < questions.length - 1
            ? <button onClick={() => setCurrentIndex((c) => c + 1)} className="rounded-lg px-4 py-1.5 text-xs text-white font-medium" style={{ background: 'linear-gradient(135deg,#06b6d4,#8b5cf6)' }}>Suivant →</button>
            : <button onClick={handleExamSubmit} className="rounded-lg px-4 py-1.5 text-xs text-white font-medium" style={{ background: 'linear-gradient(135deg,#10b981,#06b6d4)' }}>Remettre la copie</button>
          }
        </div>
      </div>
    </div>
  )
}

function QuizPanel({
  recoveryPrompt,
  clearRecoveryPrompt,
  lessonContext,
}: {
  recoveryPrompt?: string | null
  clearRecoveryPrompt?: () => void
  lessonContext?: LessonRef | null
}) {
  const recordQuizScore = useLessonProgressStore((state) => state.recordQuizScore)
  const { mainModel, visionModel } = useAppStore()
  const { trackGeneration, completeGeneration, failGeneration } = useGenerationTrackerStore()
  const { executeWithRuntime } = useManagedRuntime()
  const activeTrackerIdRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  useEffect(() => () => { abortRef.current?.abort() }, [])
  const [contextFiles, setContextFiles] = useState<File[]>([])
  const { pack: assetPack, preparePack } = useModuleAssetPack({
    module: 'learning',
    title: 'Pack modele academie',
    assets: buildLearningModuleAssets(mainModel, visionModel, contextFiles.length > 0),
  })
  const { addXp, updateStreak, unlockBadge, addQuizResult } = useGamificationStore()
  // Restore session state persisted across restarts
  const _savedQuiz = useLearningSessionStore((s) => s.quiz)
  const saveQuiz = useLearningSessionStore((s) => s.saveQuiz)
  const [topic, setTopic] = useState(_savedQuiz?.topic ?? '')
  const [mode, setMode] = useState<QuizMode>(_savedQuiz?.mode ?? 'classic')
  const [questions, setQuestions] = useState<QuizQuestion[]>(_savedQuiz?.questions ?? [])
  const [sources, setSources] = useState<LearningSource[]>(_savedQuiz?.sources ?? [])
  const [wrongQuestions, setWrongQuestions] = useState<QuizQuestion[]>([])
  const [currentIndex, setCurrentIndex] = useState(_savedQuiz?.currentIndex ?? 0)
  const [score, setScore] = useState(_savedQuiz?.score ?? 0)
  const [streak, setStreak] = useState(0)
  const [bestStreak, setBestStreak] = useState(0)
  const [answered, setAnswered] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [quizDone, setQuizDone] = useState(_savedQuiz?.quizDone ?? false)
  const [showXp, setShowXp] = useState(false)
  const [xpGained, setXpGained] = useState(0)
  const [hearts, setHearts] = useState(5)
  const [timeLeft, setTimeLeft] = useState(12)
  const [timerActive, setTimerActive] = useState(false)
  const [status, setStatus] = useState(_savedQuiz?.status ?? 'En attente de sujet.')
  const [clarification, setClarification] = useState<ClarificationRequest | null>(null)
  const [showSources, setShowSources] = useState(false)
  const [showHint, setShowHint] = useState(false)
  const [academicIntent, setAcademicIntent] = useState<AcademicIntent | null>(null)
  const [draftOpenAnswer, setDraftOpenAnswer] = useState('')
  const [quizFormatPending, setQuizFormatPending] = useState<null | { resolve: (v: 'mcq' | 'open' | 'mix') => void }>(null)
  const [exerciseMode, setExerciseMode] = useState<ExerciseMode | null>(null)
  const [gameData, setGameData] = useState<GamePayload | null>(null)
  const [gameRunning, setGameRunning] = useState(false)
  const [gameScore, setGameScore] = useState(0)
  const [isExamMode, setIsExamMode] = useState(false)
  const [examDuration, setExamDuration] = useState(60)
  const [examRunning, setExamRunning] = useState(false)
  const answeredRef = useRef<number | null>(null)
  const currentQuestion = questions[currentIndex]
  const activeModel = contextFiles.length > 0 ? visionModel : mainModel

  // Persist session state so it survives app restarts
  useEffect(() => {
    if (topic || questions.length > 0) {
      saveQuiz({ topic, mode, questions, sources, currentIndex, score, quizDone, status })
    }
  }, [topic, mode, questions, sources, currentIndex, score, quizDone, status, saveQuiz])


  const askQuizFormat = useCallback(
    (): Promise<'mcq' | 'open' | 'mix'> =>
      new Promise<'mcq' | 'open' | 'mix'>((resolve) => setQuizFormatPending({ resolve })),
    [],
  )

  // Consume recovery prompt to pre-fill the topic.
  // Format "[EXAMEN 120MIN] sujet" déclenche auto le mode examen blanc.
  useEffect(() => {
    if (recoveryPrompt) {
      const examMatch = recoveryPrompt.match(/^\[EXAMEN\s+(\d+)MIN\]\s*(.+)$/)
      if (examMatch) {
        setIsExamMode(true)
        setExerciseMode(null)
        setExamDuration(Math.min(240, Math.max(60, parseInt(examMatch[1], 10) || 120)))
        setTopic(examMatch[2])
      } else {
        setTopic(recoveryPrompt)
      }
      clearRecoveryPrompt?.()
    }
  }, [recoveryPrompt, clearRecoveryPrompt])

  const moveToNextQuestion = useCallback((correct: boolean) => {
    setTimeout(() => {
      if (currentIndex + 1 >= questions.length) {
        const finalScore = score + (correct ? 1 : 0)
        setQuizDone(true)
        setTimerActive(false)
        updateStreak()
        addQuizResult(finalScore, questions.length, topic)
        if (lessonContext && questions.length > 0) {
          const scorePct = Math.round((finalScore / questions.length) * 100)
          recordQuizScore(lessonContext.pathId, lessonContext.nodeIndex, scorePct)
        }

        if (questions.length > 0) {
          unlockBadge('first_quiz')
        }
        if (finalScore === questions.length) {
          unlockBadge('perfect_quiz')
        }
        if (mode === 'kahoot' && finalScore >= Math.ceil(questions.length * 0.8)) {
          unlockBadge('speed_demon')
        }

        setStatus('Quiz termine et progression enregistree.')
        return
      }

      setCurrentIndex((value) => value + 1)
      setAnswered(null)
      setShowHint(false)
      if (mode === 'kahoot') {
        setTimeLeft(12)
        setTimerActive(true)
      }
    }, 1200)
  }, [addQuizResult, currentIndex, lessonContext, mode, questions.length, recordQuizScore, score, topic, unlockBadge, updateStreak])

  const startReviewMode = useCallback(() => {
    if (wrongQuestions.length === 0) return
    setQuestions(wrongQuestions)
    setWrongQuestions([])
    setCurrentIndex(0)
    setScore(0)
    setAnswered(null)
    setQuizDone(false)
    setHearts(5)
    setTimeLeft(12)
    setTimerActive(mode === 'kahoot')
    setStatus('Mode revision — uniquement les questions ratees.')
  }, [wrongQuestions, mode])

  // Sync ref so timer callback always sees the latest answered value
  answeredRef.current = answered

  useEffect(() => {
    if (!timerActive || mode !== 'kahoot' || quizDone) {
      return
    }

    const timer = window.setInterval(() => {
      setTimeLeft((value) => {
        if (value <= 1) {
          window.clearInterval(timer)
          setTimerActive(false)
          if (answeredRef.current === null) {
            setAnswered(-1)
          }
          return 0
        }

        return value - 1
      })
    }, 1000)

    return () => window.clearInterval(timer)
  }, [mode, quizDone, timerActive])

  useEffect(() => {
    if (answered !== -1 || !currentQuestion) {
      return
    }

    const timeout = window.setTimeout(() => {
      moveToNextQuestion(false)
    }, 1200)

    return () => window.clearTimeout(timeout)
  }, [answered, currentQuestion, moveToNextQuestion])

  const generateQuiz = useCallback(async () => {
    if (!topic.trim()) {
      return
    }

    setIsLoading(true)
    setQuestions([])
    setSources([])
    setWrongQuestions([])
    setCurrentIndex(0)
    setScore(0)
    setStreak(0)
    setBestStreak(0)
    setAnswered(null)
    setQuizDone(false)
    setHearts(5)
    setTimeLeft(12)
    setTimerActive(false)
    setShowHint(false)
    setStatus('Preparation du quiz...')

    activeTrackerIdRef.current = trackGeneration({
      module: 'learning',
      type: 'ollama_stream',
      prompt: topic.trim(),
      startedAt: Date.now(),
    })

    abortRef.current?.abort()
    abortRef.current = new AbortController()

    try {
      await executeWithRuntime({
        module: 'learning',
        title: 'Generation quiz academie',
        services: ['ollama'],
        prepare: async ({ setPhase }) => {
          await preparePack(setPhase)
        },
        ollamaModel: activeModel,
        job: async ({ setPhase }) => {
          const preparedContext = contextFiles.length > 0 ? await prepareContextFiles(contextFiles) : []
          const taskContext = await prepareTaskIntelligence({
            module: 'learning',
            prompt: topic,
            model: preparedContext.some((file) => file.imageBase64) ? visionModel : activeModel,
            files: preparedContext,
            setPhase,
            phaseBase: 40,
            phaseSpan: 14,
          })

          if (taskContext.clarificationQuestion) {
            setPhase('Clarification utilisateur requise avant generation du quiz.', 56)
            const userAnswer = await new Promise<string | null>((resolve) => {
              setClarification({ question: taskContext.clarificationQuestion!, onRespond: resolve })
            })
            setClarification(null)
            if (userAnswer) {
              taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nPrecision utilisateur: ${userAnswer}`
            }
          }

          setPhase('Recherche de sources factuelles (Wikipedia + web)...', 58)
          setStatus('Collecte de sources verifiees pour eviter les hallucinations...')
          const research = await researchLearningTopic(topic.trim())
          setAcademicIntent(research.academicIntent)
          if (research.hasExternalSources) {
            setStatus(`Sources: ${summarizeSourcesForUI(research.sources)}${research.academicIntent.isExamFocus ? ` · Niveau ${research.academicIntent.level}` : ''}`)
          }

          // v83: quiz BAC enrichment - meme principe que cours/flashcards.
          // Quand isExamFocus, rapatrier 4 sujets BAC officiels pour calibrer
          // le format des questions sur les annales reelles plutot que de
          // laisser le LLM inventer un style d epreuve.
          let bacEnrichmentBlock: string | null = null
          if (research.academicIntent.isExamFocus) {
            try {
              const { buildBacEnrichment } = await import('../../services/bacResources')
              bacEnrichmentBlock = await buildBacEnrichment(topic.trim(), 4)
            } catch {
              // best-effort
            }
          }

          // Smart quiz format detection. Kahoot-style QCM for hard sciences,
          // open-answer dissertation for humanities, and a 3-way chooser for
          // ambiguous subjects where "Mix des deux" is a real option.
          const detectedSubjectKind = detectSubjectKind(topic.trim())
          const mcqOnlySubjects: SubjectKind[] = ['maths', 'science', 'informatique', 'economie']
          const openOnlySubjects: SubjectKind[] = ['philo', 'litterature']
          const ambiguousSubjects: SubjectKind[] = ['histoire', 'geo', 'langue', 'general', 'art']
          let forceOpenQuestions = false
          let forceMcqQuestions = false
          let mixFormat = false
          if (openOnlySubjects.includes(detectedSubjectKind)) {
            forceOpenQuestions = true
          } else if (mcqOnlySubjects.includes(detectedSubjectKind)) {
            forceMcqQuestions = true
          } else if (ambiguousSubjects.includes(detectedSubjectKind)) {
            setPhase('Choix du format de quiz...', 64)
            const userFormatChoice = await askQuizFormat()
            setQuizFormatPending(null)
            if (userFormatChoice === 'open') {
              forceOpenQuestions = true
            } else if (userFormatChoice === 'mix') {
              // Mix: ask the model to alternate QCM and open answers. The
              // system prompt reads the two flags together and produces a
              // balanced output.
              mixFormat = true
              forceOpenQuestions = true
              forceMcqQuestions = true
            } else {
              forceMcqQuestions = true
            }
          }
          void mixFormat

          setPhase('Generation du quiz structurant...', 66)
          setStatus('Le modele construit un quiz exploitable, ancre sur les sources.')

          // MEMORY-SAFE: chunks.push + join au lieu de raw += token pour eviter
          // la concatenation O(n²) qui crashe l onglet sur gros contenus (un
          // quiz examen peut depasser 30K chars, donc ~15K tokens).
          // v82lm: 4-min TTFB so academic quiz generation (research + BAC
          // enrichment + vision model cold start) doesn't AbortError.
          const rawChunks: string[] = []
          await ollamaChatStream(
            activeModel,
            [
              { role: 'system', content: buildLearningSystemPrompt('quiz', { academicIntent: research.academicIntent, subjectKind: detectedSubjectKind, forceOpenQuestions, forceMcqQuestions }) },
              ...(research.contextBlock
                ? [{ role: 'system' as const, content: research.contextBlock }]
                : []),
              ...(research.examContextBlock
                ? [{ role: 'system' as const, content: research.examContextBlock }]
                : []),
              ...(bacEnrichmentBlock
                ? [{ role: 'system' as const, content: bacEnrichmentBlock }]
                : []),
              {
                role: 'user',
                content: [
                  `Sujet: ${taskContext.enrichedPrompt}`,
                  `Niveau academique cible: ${research.academicIntent.level} (profondeur ${research.academicIntent.depth}${research.academicIntent.isExamFocus ? ', mode examen' : ''}).`,
                  'Retour attendu (JSON strict):',
                  '[{"question":"...","options":["A","B","C","D"],"correctIndex":0,"explanation":"...","concept":"...","sourceHint":"S1"}]',
                ].join('\n'),
                images: preparedContext.flatMap((file) => file.imageBase64 ? [file.imageBase64] : []),
              },
            ],
            (token) => {
              rawChunks.push(token)
            },
            () => undefined,
            { signal: abortRef.current?.signal ?? undefined, firstByteTimeoutMs: 240_000 },
          )
          const raw = rawChunks.join('')

          setPhase('Validation du quiz...', 80)
          const parsed = extractJsonArray<QuizQuestion>(raw)
          if (parsed.length === 0) {
            throw new Error('Le quiz genere est vide.')
          }

          // Auto-correction : le modele verifie ses propres reponses
          setPhase('Auto-correction des reponses...', 88)
          setStatus('Verification de l exactitude des reponses...')
          let finalQuestions = parsed.slice(0, 5)
          try {
            const correctedChunks: string[] = []
            // v82lm: also widen TTFB on the auto-correction pass — the model
            // re-reads the full quiz JSON and academic context before emitting.
            await ollamaChatStream(
              activeModel,
              [
                { role: 'system', content: buildLearningSystemPrompt('quiz_verify', { academicIntent: research.academicIntent }) },
                ...(research.contextBlock
                  ? [{ role: 'system' as const, content: research.contextBlock }]
                  : []),
                ...(research.examContextBlock
                  ? [{ role: 'system' as const, content: research.examContextBlock }]
                  : []),
                {
                  role: 'user',
                  content: `Verifie et corrige si necessaire ce quiz sur "${topic}" (niveau ${research.academicIntent.level}):\n${JSON.stringify(finalQuestions, null, 2)}`,
                },
              ],
              (token) => { correctedChunks.push(token) },
              () => undefined,
              { signal: abortRef.current?.signal ?? undefined, firstByteTimeoutMs: 180_000 },
            )
            const correctedRaw = correctedChunks.join('')
            const corrected = extractJsonArray<QuizQuestion>(correctedRaw)
            if (corrected.length > 0) {
              finalQuestions = corrected.slice(0, 5)
            }
          } catch {
            // Auto-correction best-effort — on utilise le quiz initial si echec
          }

          setQuestions(finalQuestions)
          setSources(research.sources)
          setStatus(isExamMode ? `Examen blanc prêt (${examDuration} min)` : 'Quiz chargé, prêt à démarrer.')
          if (isExamMode) {
            setExamRunning(true)
          } else if (mode === 'kahoot') {
            setTimeLeft(12)
            setTimerActive(true)
          }
        },
      })

      if (activeTrackerIdRef.current) {
        completeGeneration(activeTrackerIdRef.current, {
          resultFilename: questions.length > 0 ? `${questions.length} questions sur ${topic.slice(0, 60)}` : undefined,
        })
        activeTrackerIdRef.current = null
      }
    } catch (error) {
      const errMsg = getErrorMessage(error, 'Echec de generation du quiz.')
      if (activeTrackerIdRef.current) {
        failGeneration(activeTrackerIdRef.current, errMsg)
        activeTrackerIdRef.current = null
      }
      setStatus(errMsg)
    } finally {
      setIsLoading(false)
    }
  }, [activeModel, contextFiles, executeWithRuntime, mode, preparePack, topic, visionModel, trackGeneration, completeGeneration, failGeneration])

  const generateGame = useCallback(async () => {
    if (!topic.trim() || !exerciseMode) return
    setIsLoading(true)
    setGameData(null)
    setGameRunning(false)
    setStatus('Génération du jeu...')
    try {
      const rawChunks: string[] = []
      await ollamaChatStream(
        activeModel,
        [
          { role: 'system', content: buildGameSystemPrompt(exerciseMode) },
          { role: 'user', content: `Sujet: ${topic.trim()}` },
        ],
        (token) => { rawChunks.push(token) },
        () => undefined,
        { signal: abortRef.current?.signal ?? undefined },
      )
      const raw = rawChunks.join('')
      if (exerciseMode === 'fillblank') {
        const cleaned = raw.replace(/```(?:json)?\s*/g, '').replace(/```/g, '')
        const start = cleaned.indexOf('{')
        if (start !== -1) {
          const end = findBalancedSlice(cleaned, start, '{', '}')
          if (end !== -1) {
            try {
              const payload = JSON.parse(cleaned.slice(start, end + 1)) as GamePayload
              setGameData(payload)
              setGameRunning(true)
            } catch { setStatus('Erreur parsing jeu.') }
          }
        }
      } else {
        const terms = extractJsonArray<GameTerm>(raw)
        if (terms.length > 0) {
          setGameData({ terms })
          setGameRunning(true)
        } else {
          setStatus('Aucun terme généré.')
        }
      }
    } catch (error) {
      setStatus(getErrorMessage(error, 'Erreur génération jeu.'))
    } finally {
      setIsLoading(false)
    }
  }, [activeModel, exerciseMode, topic])

  const answerQuestion = (index: number) => {
    if (!currentQuestion || answered !== null) {
      return
    }

    setAnswered(index)
    setTimerActive(false)
    const correct = currentQuestion.correctIndex === index

    if (correct) {
      const nextStreak = streak + 1
      let gained = 10
      if (mode === 'kahoot') gained = Math.max(12, timeLeft * 3)
      if (mode === 'duolingo') gained = 15
      if (nextStreak >= 3) gained += 5

      setScore((value) => value + 1)
      setStreak(nextStreak)
      setBestStreak((value) => Math.max(value, nextStreak))
      setXpGained(gained)
      addXp(gained)
      setShowXp(true)
      window.setTimeout(() => setShowXp(false), 1400)
      setStatus(nextStreak >= 3 ? `Combo x${nextStreak}! +5 XP bonus.` : 'Bonne reponse, la progression continue.')
    } else {
      setWrongQuestions((value) => [...value, currentQuestion])
      setStreak(0)
      setStatus('Reponse incorrecte, explication affichee.')
      if (mode === 'duolingo') {
        setHearts((value) => {
          const next = value - 1
          if (next <= 0) {
            setQuizDone(true)
            setStatus('Toutes les vies sont perdues.')
            return 0
          }
          return next
        })
      }
    }

    moveToNextQuestion(correct)
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <ClarificationDialog request={clarification} />
      <AnimatePresence>{showXp && <XpPopup amount={xpGained} />}</AnimatePresence>

      {/* Smart quiz format dialog */}
      {quizFormatPending && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div
            className="w-full max-w-sm rounded-3xl p-6 text-center"
            style={{
              background: 'rgba(8,14,30,0.95)',
              border: '1px solid rgba(255,255,255,0.1)',
              boxShadow: '0 0 60px rgba(6,182,212,0.15), 0 20px 60px rgba(0,0,0,0.5)',
            }}
          >
            <div
              className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl text-2xl"
              style={{ background: 'linear-gradient(135deg,rgba(6,182,212,0.2),rgba(139,92,246,0.2))', border: '1px solid rgba(6,182,212,0.3)' }}
            >
              🎯
            </div>
            <h3 className="text-base font-semibold text-aurora-text">Quel format de quiz ?</h3>
            <p className="mt-2 text-sm text-aurora-text-dim leading-relaxed">
              Ce sujet peut se prêter à plusieurs formats. Choisis celui qui correspond à ta préparation.
            </p>
            <div className="mt-5 flex flex-col gap-3">
              <button
                onClick={() => { quizFormatPending.resolve('mcq'); setQuizFormatPending(null) }}
                className="flex items-center gap-3 rounded-2xl px-5 py-3 text-left text-sm font-medium text-white transition-all hover:scale-[1.02]"
                style={{ background: 'linear-gradient(135deg,#06b6d4,#0ea5e9)', boxShadow: '0 0 16px rgba(6,182,212,0.3)' }}
              >
                <span className="text-xl">🗂️</span>
                <div>
                  <p className="font-semibold">QCM / Exercices à trous</p>
                  <p className="text-xs text-white/75">Questions à choix multiples, réponses immédiates (style Kahoot)</p>
                </div>
              </button>
              <button
                onClick={() => { quizFormatPending.resolve('open'); setQuizFormatPending(null) }}
                className="flex items-center gap-3 rounded-2xl px-5 py-3 text-left text-sm font-medium text-white transition-all hover:scale-[1.02]"
                style={{ background: 'linear-gradient(135deg,#8b5cf6,#a855f7)', boxShadow: '0 0 16px rgba(139,92,246,0.3)' }}
              >
                <span className="text-xl">✍️</span>
                <div>
                  <p className="font-semibold">Questions ouvertes / Dissertation</p>
                  <p className="text-xs text-white/75">Rédaction, argumentation, barème détaillé</p>
                </div>
              </button>
              <button
                onClick={() => { quizFormatPending.resolve('mix'); setQuizFormatPending(null) }}
                className="flex items-center gap-3 rounded-2xl px-5 py-3 text-left text-sm font-medium text-white transition-all hover:scale-[1.02]"
                style={{ background: 'linear-gradient(135deg,#f97f3d,#f43f5e)', boxShadow: '0 0 16px rgba(249,127,61,0.3)' }}
              >
                <span className="text-xl">🔀</span>
                <div>
                  <p className="font-semibold">Mix des deux</p>
                  <p className="text-xs text-white/75">Alterne QCM rapides et questions ouvertes approfondies</p>
                </div>
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="glass rounded-2xl p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-aurora-text">Quiz adaptatif</h2>
            <p className="mt-1 text-sm text-aurora-text-dim">
              Le module Academie analyse le sujet puis construit un quiz progressif.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="rounded-xl border border-aurora-border bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text-dim">
              {status}
            </div>
            {isLoading && (
              <button
                onClick={() => { abortRef.current?.abort(); abortRef.current = null }}
                className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400 hover:bg-red-500/20 transition-colors"
              >
                ✕ Arrêter
              </button>
            )}
          </div>
        </div>
      </div>

      {questions.length === 0 && !quizDone && (
        <div className="mx-auto max-w-3xl space-y-4">
          <div className="glass rounded-2xl p-5">
            <label className="block text-xs text-aurora-text-dim">Sujet du quiz</label>
            <div className="mt-2 flex items-center gap-2">
              <input
                value={topic}
                onChange={(event) => setTopic(event.target.value)}
                placeholder="Ex: histoire de Rome, algorithmes de tri, systeme solaire..."
                className="flex-1 rounded-xl border border-aurora-border bg-aurora-surface-2 px-4 py-3 text-sm text-aurora-text outline-none focus:border-aurora-accent/50"
                onKeyDown={(event) => event.key === 'Enter' && void generateQuiz()}
              />
              <VoicePushToTalk
                onTranscript={(text) => setTopic((prev) => (prev?.trim() ? `${prev} ${text}` : text))}
                label="Dicter le sujet du quiz"
                size={40}
              />
            </div>
            <div className="mt-4">
              <ContextFilesField
                files={contextFiles}
                onFilesChange={setContextFiles}
                accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.md,.json,.csv,.tsv,.xlsx,.xls,.xlsm"
                hint="Ajoute cours, images, PDF ou tableurs pour construire le quiz."
              />
            </div>
          </div>

          <ModuleAssetPackCard pack={assetPack} />

          {/* Format auto-detection banner */}
          {topic.trim() && (() => {
            const fmt = detectQuizNaturalFormat(topic)
            if (fmt === 'ambiguous' && !exerciseMode) {
              return (
                <div className="rounded-2xl p-4" style={{ background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.25)' }}>
                  <p className="text-xs font-semibold text-aurora-text">Format de la réponse attendue ?</p>
                  <p className="mt-1 text-xs text-aurora-text-dim">Sujet ambigu — choisis le format avant de générer :</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {([
                      { id: 'mcq' as const, label: 'QCM / Exercices', desc: 'Questions à choix multiples' },
                      { id: 'open' as const, label: 'Questions ouvertes', desc: 'Dissertation, rédaction' },
                      { id: 'mix' as const, label: 'Mix des deux', desc: 'QCM + questions ouvertes' },
                    ] as const).map(({ id, label, desc }) => (
                      <button
                        key={id}
                        onClick={() => quizFormatPending?.resolve(id)}
                        className="rounded-xl px-3 py-2 text-xs text-left transition-all"
                        style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(139,92,246,0.3)', color: '#c4b5fd' }}
                      >
                        <p className="font-medium">{label}</p>
                        <p className="opacity-70">{desc}</p>
                      </button>
                    ))}
                  </div>
                </div>
              )
            }
            return null
          })()}

          {/* Quiz modes : standard */}
          {!exerciseMode && !isExamMode && (
            <>
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-aurora-text-dim">Mode Quiz</p>
                <div className="grid gap-3 sm:grid-cols-3">
                  {([
                    { id: 'classic' as const, label: 'Classique', icon: BookOpen, desc: 'Évaluation standard.' },
                    { id: 'kahoot' as const, label: 'Kahoot', icon: Gamepad2, desc: 'Rapide, chronomètre.' },
                    { id: 'duolingo' as const, label: 'Duolingo', icon: Heart, desc: 'Vies limitées.' },
                  ]).map(({ id, label, icon: Icon, desc }) => (
                    <button
                      key={id}
                      onClick={() => setMode(id)}
                      className="rounded-2xl border p-4 text-left transition-all"
                      style={{
                        background: mode === id ? 'rgba(6,182,212,0.1)' : 'rgba(255,255,255,0.03)',
                        border: `1px solid ${mode === id ? 'rgba(6,182,212,0.5)' : 'rgba(255,255,255,0.08)'}`,
                        boxShadow: mode === id ? '0 0 12px rgba(6,182,212,0.2)' : 'none',
                      }}
                    >
                      <Icon size={22} style={{ color: mode === id ? '#06b6d4' : '#64748b' }} />
                      <p className="mt-3 text-sm font-medium text-aurora-text">{label}</p>
                      <p className="mt-1 text-xs text-aurora-text-dim">{desc}</p>
                    </button>
                  ))}
                </div>
              </div>
              <button
                onClick={() => void generateQuiz()}
                disabled={!topic.trim() || isLoading}
                className="w-full rounded-2xl px-4 py-3 text-sm font-medium text-white disabled:opacity-60 transition-all"
                style={{ background: 'linear-gradient(135deg,#06b6d4,#8b5cf6)', boxShadow: '0 0 20px rgba(6,182,212,0.3)' }}
              >
                {isLoading ? 'Génération en cours...' : 'Générer le quiz'}
              </button>
            </>
          )}

          {/* Exercices ludiques */}
          {!isExamMode && (
            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-aurora-text-dim">Exercices de fin d'apprentissage</p>
              <div className="grid gap-2 sm:grid-cols-3">
                {([
                  { id: 'words' as const, label: 'Mots cachés', icon: Lightbulb, desc: 'Indice progressif', color: '#06b6d4' },
                  { id: 'pairs' as const, label: 'Relie les paires', icon: Zap, desc: 'Terme ↔ définition', color: '#8b5cf6' },
                  { id: 'fillblank' as const, label: 'Texte à trous', icon: Target, desc: 'Complète le passage', color: '#f97316' },
                ] as const).map(({ id, label, icon: Icon, desc, color }) => (
                  <button
                    key={id}
                    onClick={() => { setExerciseMode(exerciseMode === id ? null : id); setIsExamMode(false) }}
                    className="rounded-2xl border p-3 text-left transition-all"
                    style={{
                      background: exerciseMode === id ? `${color}18` : 'rgba(255,255,255,0.03)',
                      border: `1px solid ${exerciseMode === id ? `${color}50` : 'rgba(255,255,255,0.07)'}`,
                    }}
                  >
                    <Icon size={18} style={{ color: exerciseMode === id ? color : '#64748b' }} />
                    <p className="mt-2 text-xs font-medium text-aurora-text">{label}</p>
                    <p className="mt-0.5 text-[10px] text-aurora-text-dim">{desc}</p>
                  </button>
                ))}
              </div>
              {exerciseMode && (
                <button
                  onClick={() => void generateGame()}
                  disabled={!topic.trim() || isLoading}
                  className="mt-3 w-full rounded-2xl px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60"
                  style={{ background: 'linear-gradient(135deg,#f97316,#8b5cf6)' }}
                >
                  {isLoading ? 'Génération...' : `Lancer le jeu "${exerciseMode === 'words' ? 'Mots cachés' : exerciseMode === 'pairs' ? 'Paires' : 'Texte à trous'}"`}
                </button>
              )}
            </div>
          )}

          {/* Mode Examen blanc */}
          <div>
            <button
              onClick={() => { setIsExamMode(!isExamMode); setExerciseMode(null) }}
              className="w-full rounded-2xl border p-4 text-left transition-all"
              style={{
                background: isExamMode ? 'rgba(249,127,61,0.1)' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${isExamMode ? 'rgba(249,127,61,0.5)' : 'rgba(255,255,255,0.08)'}`,
              }}
            >
              <div className="flex items-center gap-2">
                <Swords size={18} style={{ color: isExamMode ? '#f97f3d' : '#64748b' }} />
                <p className="text-sm font-medium text-aurora-text">Mode Examen blanc</p>
              </div>
              <p className="mt-1 text-xs text-aurora-text-dim">Conditions réelles, timer compte à rebours, corrigé complet</p>
            </button>
            {isExamMode && (
              <div className="mt-3 space-y-3">
                <div className="flex flex-wrap gap-2">
                  {[60, 120, 180, 240].map((d) => (
                    <button
                      key={d}
                      onClick={() => setExamDuration(d)}
                      className="rounded-lg px-3 py-1.5 text-xs transition-all"
                      style={{ background: examDuration === d ? 'rgba(249,127,61,0.2)' : 'rgba(255,255,255,0.05)', border: `1px solid ${examDuration === d ? 'rgba(249,127,61,0.5)' : 'rgba(255,255,255,0.1)'}`, color: examDuration === d ? '#f97f3d' : '#94a3b8' }}
                    >
                      {d} min
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => void generateQuiz()}
                  disabled={!topic.trim() || isLoading}
                  className="w-full rounded-2xl px-4 py-3 text-sm font-medium text-white disabled:opacity-60"
                  style={{ background: 'linear-gradient(135deg,#f97f3d,#8b5cf6)', boxShadow: '0 0 20px rgba(249,127,61,0.3)' }}
                >
                  {isLoading ? 'Préparation de l\'examen...' : `Démarrer l'examen blanc (${examDuration} min)`}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center gap-3 py-12">
          <Loader2 size={24} className="animate-spin text-aurora-accent" />
          <span className="text-aurora-text-dim">Le module se prépare en local...</span>
        </div>
      )}

      {/* Rendu mini-jeux */}
      {gameRunning && gameData && exerciseMode === 'words' && gameData.terms && (
        <div className="mx-auto max-w-3xl space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-aurora-text flex items-center gap-2"><Lightbulb size={16} className="text-aurora-accent" /> Mots cachés — {topic}</p>
            <button onClick={() => { setGameRunning(false); setGameData(null); setExerciseMode(null) }} className="text-xs text-aurora-text-dim hover:text-aurora-text transition-colors">Quitter</button>
          </div>
          <WordsGame data={gameData.terms} onDone={(s) => { setGameScore(s); addXp(s * 5); setGameRunning(false) }} />
        </div>
      )}
      {gameRunning && gameData && exerciseMode === 'pairs' && gameData.terms && (
        <div className="mx-auto max-w-3xl space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-aurora-text flex items-center gap-2"><Zap size={16} className="text-aurora-accent" /> Paires — {topic}</p>
            <button onClick={() => { setGameRunning(false); setGameData(null); setExerciseMode(null) }} className="text-xs text-aurora-text-dim hover:text-aurora-text transition-colors">Quitter</button>
          </div>
          <PairsGame data={gameData.terms} onDone={(s) => { setGameScore(s); addXp(s * 5); setGameRunning(false) }} />
        </div>
      )}
      {gameRunning && gameData && exerciseMode === 'fillblank' && gameData.passage && (
        <div className="mx-auto max-w-3xl space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-aurora-text flex items-center gap-2"><Target size={16} className="text-aurora-accent" /> Texte à trous — {topic}</p>
            <button onClick={() => { setGameRunning(false); setGameData(null); setExerciseMode(null) }} className="text-xs text-aurora-text-dim hover:text-aurora-text transition-colors">Quitter</button>
          </div>
          <FillBlankGame data={gameData} onDone={(s) => { setGameScore(s); addXp(s * 5); setGameRunning(false) }} />
        </div>
      )}
      {!gameRunning && gameScore > 0 && !isLoading && exerciseMode && (
        <div className="mx-auto max-w-2xl rounded-2xl p-6 text-center" style={{ background: 'rgba(74,222,128,0.08)', border: '1px solid rgba(74,222,128,0.3)' }}>
          <Trophy size={32} className="mx-auto text-emerald-400" />
          <p className="mt-2 text-lg font-bold gradient-text">+{gameScore * 5} XP gagnés !</p>
          <button onClick={() => { setGameScore(0); setGameData(null); setExerciseMode(null) }} className="mt-3 rounded-lg border border-aurora-border px-4 py-1.5 text-xs text-aurora-text-dim hover:text-aurora-text transition-colors">Nouveau sujet</button>
        </div>
      )}

      {/* Rendu examen blanc */}
      {examRunning && questions.length > 0 && (
        <div className="mx-auto max-w-3xl space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-aurora-text flex items-center gap-2"><Swords size={16} className="text-aurora-orange" /> Examen blanc — {topic}</p>
          </div>
          <ExamTimerSession
            questions={questions}
            durationMinutes={examDuration}
            onFinish={(correct, total) => {
              setExamRunning(false)
              addQuizResult(correct, total, `[EXAMEN] ${topic}`)
              if (correct === total && total > 0) unlockBadge('perfect_quiz')
              addXp(correct * 10)
            }}
          />
        </div>
      )}

      {currentQuestion && !quizDone && !examRunning && (
        <div className="mx-auto max-w-3xl space-y-4">
          {sources.length > 0 && (
            <SourcesPanel sources={sources} open={showSources} onToggle={() => setShowSources((v) => !v)} />
          )}

          <div className="glass rounded-2xl p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs text-aurora-text-dim">
                  Question {currentIndex + 1}/{questions.length}
                </span>
                {currentQuestion.concept && (
                  <span className="rounded-full border border-aurora-accent/30 bg-aurora-accent/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] text-aurora-accent">
                    {currentQuestion.concept}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4">
                {mode === 'duolingo' && (
                  <div className="flex gap-1">
                    {Array.from({ length: 5 }).map((_, index) => (
                      <Heart
                        key={index}
                        size={15}
                        className={index < hearts ? 'text-red-400 fill-red-400' : 'text-aurora-text-dim'}
                      />
                    ))}
                  </div>
                )}
                {mode === 'kahoot' && (
                  <div className="flex items-center gap-1 text-aurora-orange">
                    <Timer size={15} />
                    <span className={`text-sm font-semibold ${timeLeft <= 3 ? 'animate-pulse' : ''}`}>{timeLeft}s</span>
                  </div>
                )}
                {streak >= 2 && (
                  <motion.span
                    key={streak}
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="inline-flex items-center gap-1 rounded-full bg-aurora-orange/15 px-2 py-0.5 text-[11px] font-semibold text-aurora-orange"
                  >
                    <Flame size={12} />
                    Combo x{streak}
                  </motion.span>
                )}
                <span className="text-xs font-medium text-aurora-accent">Score: {score}</span>
              </div>
            </div>

            <div className="mt-4 h-2 overflow-hidden rounded-full bg-aurora-surface-2">
              <motion.div
                key={currentIndex}
                initial={{ width: `${((currentIndex) / questions.length) * 100}%` }}
                animate={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
                className="h-full gradient-accent rounded-full"
              />
            </div>

            {mode === 'kahoot' && answered === null && (
              <div className="mt-2 h-1 overflow-hidden rounded-full bg-aurora-surface-2">
                <motion.div
                  key={`timer-${currentIndex}`}
                  initial={{ width: '100%' }}
                  animate={{ width: `${(timeLeft / 12) * 100}%` }}
                  transition={{ duration: 0.3, ease: 'linear' }}
                  className={`h-full rounded-full ${timeLeft <= 3 ? 'bg-aurora-red' : 'bg-aurora-orange'}`}
                />
              </div>
            )}

            <p className="mt-5 text-lg font-medium text-aurora-text">{currentQuestion.question}</p>

            {answered === null && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  onClick={() => setShowHint((v) => !v)}
                  className="inline-flex items-center gap-1.5 rounded-full border border-aurora-border bg-aurora-surface-2 px-3 py-1 text-[11px] text-aurora-text-dim hover:text-aurora-text transition-colors"
                >
                  <Lightbulb size={12} />
                  <span>{showHint ? 'Masquer l indice' : 'Indice'}</span>
                </button>
                {currentQuestion.sourceHint && (
                  <span className="text-[11px] text-aurora-text-dim">Source: {currentQuestion.sourceHint}</span>
                )}
              </div>
            )}
            {showHint && answered === null && (
              <p className="mt-2 rounded-xl border border-aurora-orange/30 bg-aurora-orange/10 px-3 py-2 text-xs text-aurora-orange">
                Astuce: elimine les options impossibles puis raisonne en comparant les deux restantes.
              </p>
            )}
          </div>

          {currentQuestion.kind === 'open' ? (
            <OpenAnswerBlock
              question={currentQuestion}
              subject={topic}
              level={academicIntent?.level}
              model={activeModel}
              revealed={answered !== null}
              onSubmit={() => {
                // Open questions: revealing the model answer counts as "seen".
                // We use answered=0 as a sentinel so the existing flow
                // (explanation pane, next-question trigger) keeps working.
                if (answered === null) setAnswered(0)
              }}
              onNext={() => {
                setAnswered(null)
                setDraftOpenAnswer('')
                moveToNextQuestion(true)
              }}
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {currentQuestion.options.map((option, index) => {
                const isCorrect = index === currentQuestion.correctIndex
                const isChosen = answered === index
                let classes = 'border-aurora-border bg-aurora-surface-2 hover:border-aurora-border-light'
                if (answered !== null) {
                  if (isCorrect) classes = 'border-aurora-green bg-aurora-green/18'
                  else if (isChosen) classes = 'border-aurora-red bg-aurora-red/18'
                }

                return (
                  <motion.button
                    key={`${option}-${index}`}
                    whileTap={{ scale: 0.985 }}
                    onClick={() => answerQuestion(index)}
                    disabled={answered !== null}
                    className={`rounded-2xl border p-4 text-left text-sm transition-all ${classes}`}
                  >
                    <span className="font-mono text-[10px] text-aurora-text-dim mr-2">{String.fromCharCode(65 + index)}.</span>
                    <span className="text-aurora-text">{option}</span>
                  </motion.button>
                )
              })}
            </div>
          )}

          {answered === null && currentQuestion.kind !== 'open' && (
            <div className="flex justify-end">
              <button
                onClick={() => {
                  setAnswered(-1)
                  setWrongQuestions((value) => [...value, currentQuestion])
                  setStreak(0)
                  setStatus('Question passee sans reponse.')
                  moveToNextQuestion(false)
                }}
                className="inline-flex items-center gap-1.5 rounded-full border border-aurora-border bg-aurora-surface-2 px-3 py-1 text-[11px] text-aurora-text-dim hover:text-aurora-text transition-colors"
              >
                Passer
              </button>
            </div>
          )}

          <AnimatePresence>
            {answered !== null && answered !== -1 && currentQuestion.kind !== 'open' && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                className={`rounded-2xl border px-4 py-4 text-sm ${
                  currentQuestion.correctIndex === answered
                    ? 'border-aurora-green/30 bg-aurora-green/10 text-aurora-text'
                    : 'border-aurora-red/30 bg-aurora-red/10 text-aurora-text'
                }`}
              >
                <div className="flex items-center gap-2">
                  {currentQuestion.correctIndex === answered ? (
                    <Check size={16} className="text-aurora-green" />
                  ) : (
                    <span className="text-aurora-red" aria-hidden>×</span>
                  )}
                  <span className="text-[11px] font-semibold uppercase tracking-[0.18em]">
                    {currentQuestion.correctIndex === answered ? 'Bonne reponse' : 'Reponse attendue'}
                  </span>
                  {currentQuestion.sourceHint && (
                    <span className="ml-auto text-[10px] text-aurora-text-dim">Source: {currentQuestion.sourceHint}</span>
                  )}
                </div>
                {currentQuestion.correctIndex !== answered && (
                  <p className="mt-2 text-[12px] text-aurora-text-dim">
                    Reponse correcte: <strong className="text-aurora-text">{currentQuestion.options[currentQuestion.correctIndex]}</strong>
                  </p>
                )}
                <p className="mt-2 leading-relaxed">{currentQuestion.explanation}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {quizDone && (
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          className="mx-auto max-w-md rounded-3xl glass p-8 text-center"
        >
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full gradient-accent-pink">
            <Trophy size={34} className="text-white" />
          </div>
          <h3 className="mt-5 text-2xl font-semibold gradient-text">Quiz termine</h3>
          <p className="mt-3 text-4xl font-bold text-aurora-text">{score}/{questions.length}</p>
          <p className="mt-3 text-sm text-aurora-text-dim">
            {score === questions.length
              ? 'Excellent resultat, toutes les reponses sont correctes.'
              : score >= Math.ceil(questions.length * 0.8)
                ? 'Tres bon resultat, la comprehension est solide.'
                : 'La base est la, mais une nouvelle passe aidera a consolider.'}
          </p>
          {bestStreak >= 2 && (
            <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-aurora-orange/12 px-3 py-1 text-[11px] font-semibold text-aurora-orange">
              <Flame size={12} />
              <span>Combo record x{bestStreak}</span>
            </div>
          )}

          {wrongQuestions.length > 0 && (
            <div className="mt-4 rounded-2xl border border-aurora-orange/30 bg-aurora-orange/10 px-4 py-3 text-left">
              <p className="text-xs font-semibold text-aurora-orange">Concepts a retravailler</p>
              <ul className="mt-2 space-y-1 text-[11px] text-aurora-text-dim">
                {wrongQuestions.map((question, index) => (
                  <li key={`wrong-${index}`} className="line-clamp-1">
                    · {question.concept || question.question.slice(0, 60)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-5 flex flex-col gap-2">
            {wrongQuestions.length > 0 && (
              <button
                onClick={startReviewMode}
                className="inline-flex items-center justify-center gap-2 rounded-2xl border border-aurora-accent/40 bg-aurora-accent/10 px-5 py-3 text-sm font-medium text-aurora-accent hover:bg-aurora-accent/15 transition-colors"
              >
                <RefreshCw size={14} />
                <span>Revoir les {wrongQuestions.length} ratee(s)</span>
              </button>
            )}
            <button
              onClick={() => void generateQuiz()}
              className="inline-flex items-center justify-center gap-2 rounded-2xl bg-aurora-surface-2 border border-aurora-border px-5 py-3 text-sm text-aurora-text-dim hover:text-aurora-text transition-colors"
            >
              <RotateCcw size={14} />
              <span>Nouveau quiz</span>
            </button>
          </div>
        </motion.div>
      )}
    </div>
  )
}

export default QuizPanel
