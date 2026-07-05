import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Check,
  Heart,
  RotateCcw,
  Sparkles,
  Trophy,
  Volume2,
  X,
  Zap,
} from 'lucide-react'
import { useGamificationStore } from '../../stores/gamificationStore'

// Mini-banque locale de leçons style Duolingo (FR/EN/Math/SVT/Histoire)
// Pas besoin du LLM pour la mini-leçon — instantané, mobile, jouable hors ligne.
type Exercise =
  | { kind: 'translate'; prompt: string; answer: string; pool: string[]; lang?: string }
  | { kind: 'mcq'; prompt: string; options: string[]; correct: number; explanation?: string }
  | { kind: 'pair'; prompt: string; pairs: Array<{ left: string; right: string }> }
  | { kind: 'fill'; prompt: string; sentence: string; blank: string; options: string[] }

interface Track {
  id: string
  label: string
  emoji: string
  color: string
  exercises: Exercise[]
}

const TRACKS: Track[] = [
  {
    id: 'en-basics',
    label: 'Anglais — basiques',
    emoji: '🇬🇧',
    color: 'from-cyan-400 to-blue-500',
    exercises: [
      {
        kind: 'translate',
        prompt: 'Traduis : « Le chat boit du lait »',
        answer: 'The cat drinks milk',
        pool: ['The', 'cat', 'eats', 'drinks', 'milk', 'water', 'a', 'is'],
      },
      {
        kind: 'mcq',
        prompt: 'Quel est le pluriel de « child » ?',
        options: ['childs', 'childen', 'children', 'childes'],
        correct: 2,
        explanation: '« Children » est un pluriel irrégulier.',
      },
      {
        kind: 'fill',
        prompt: 'Complète',
        sentence: 'She ___ to school every day.',
        blank: 'goes',
        options: ['go', 'goes', 'going', 'gone'],
      },
      {
        kind: 'pair',
        prompt: 'Associe',
        pairs: [
          { left: 'red', right: 'rouge' },
          { left: 'blue', right: 'bleu' },
          { left: 'green', right: 'vert' },
          { left: 'yellow', right: 'jaune' },
        ],
      },
      {
        kind: 'mcq',
        prompt: 'Quel verbe est irrégulier ?',
        options: ['walk', 'play', 'go', 'talk'],
        correct: 2,
        explanation: '« go » → « went » → « gone »',
      },
    ],
  },
  {
    id: 'math-bases',
    label: 'Maths — calcul mental',
    emoji: '➗',
    color: 'from-violet-400 to-purple-500',
    exercises: [
      { kind: 'mcq', prompt: 'Combien font 7 × 8 ?', options: ['54', '56', '58', '64'], correct: 1 },
      { kind: 'mcq', prompt: 'Racine carrée de 144 ?', options: ['10', '11', '12', '14'], correct: 2 },
      { kind: 'mcq', prompt: '15 % de 200 ?', options: ['20', '25', '30', '40'], correct: 2 },
      { kind: 'fill', prompt: 'Complète', sentence: '3² + 4² = ___', blank: '25', options: ['7', '12', '25', '49'] },
      { kind: 'mcq', prompt: 'Quel nombre est premier ?', options: ['9', '15', '21', '23'], correct: 3 },
    ],
  },
  {
    id: 'svt-cell',
    label: 'SVT — la cellule',
    emoji: '🧬',
    color: 'from-emerald-400 to-teal-500',
    exercises: [
      {
        kind: 'mcq',
        prompt: "Quelle est l'unité fonctionnelle du vivant ?",
        options: ['Atome', 'Molécule', 'Cellule', 'Organe'],
        correct: 2,
      },
      {
        kind: 'pair',
        prompt: 'Associe l’organite à sa fonction',
        pairs: [
          { left: 'Mitochondrie', right: 'Énergie' },
          { left: 'Noyau', right: 'ADN' },
          { left: 'Ribosome', right: 'Protéines' },
          { left: 'Chloroplaste', right: 'Photosynthèse' },
        ],
      },
      {
        kind: 'mcq',
        prompt: "Quel ADN double brin se trouve où ?",
        options: ['Cytoplasme', 'Membrane', 'Noyau', 'Lysosome'],
        correct: 2,
      },
      { kind: 'fill', prompt: 'Complète', sentence: "L'ADN code pour ___", blank: 'protéines', options: ['lipides', 'protéines', 'glucides', 'sels'] },
      {
        kind: 'mcq',
        prompt: 'La membrane plasmique est composée de…',
        options: ['Cellulose', 'Phospholipides', 'Glucose', 'Acides aminés'],
        correct: 1,
      },
    ],
  },
  {
    id: 'histoire-rev',
    label: 'Histoire — Révolution française',
    emoji: '🏛️',
    color: 'from-orange-400 to-rose-500',
    exercises: [
      { kind: 'mcq', prompt: 'Année de la prise de la Bastille ?', options: ['1769', '1789', '1792', '1799'], correct: 1 },
      { kind: 'mcq', prompt: 'Qui a été guillotiné en 1793 ?', options: ['Napoléon', 'Louis XIV', 'Louis XVI', 'Robespierre'], correct: 2 },
      { kind: 'pair', prompt: 'Associe', pairs: [
        { left: 'Bastille', right: '14 juillet 1789' },
        { left: 'Robespierre', right: 'Terreur' },
        { left: 'Napoléon', right: 'Empire' },
        { left: 'Louis XVI', right: 'Roi' },
      ]},
      { kind: 'fill', prompt: 'Complète', sentence: 'La devise: « Liberté, Égalité, ___ »', blank: 'Fraternité', options: ['Justice', 'Vérité', 'Fraternité', 'Patrie'] },
      { kind: 'mcq', prompt: 'Le Tiers État représentait…', options: ['Le clergé', 'La noblesse', 'Le peuple', 'Le roi'], correct: 2 },
    ],
  },
  {
    id: 'phy-meca',
    label: 'Physique — mécanique',
    emoji: '⚙️',
    color: 'from-blue-400 to-indigo-500',
    exercises: [
      { kind: 'mcq', prompt: "Unité SI de la force ?", options: ['Joule', 'Watt', 'Newton', 'Pascal'], correct: 2 },
      { kind: 'mcq', prompt: 'F = m × a est la …', options: ['1ʳᵉ loi de Newton', '2ᵉ loi de Newton', '3ᵉ loi de Newton', 'Loi d’Archimède'], correct: 1 },
      { kind: 'fill', prompt: 'Complète', sentence: 'L’accélération de la pesanteur sur Terre vaut ___ m/s²', blank: '9.81', options: ['1.6', '9.81', '20', '100'] },
      { kind: 'mcq', prompt: 'L’énergie cinétique vaut…', options: ['m·g·h', '½·m·v²', 'F·d', 'm·v'], correct: 1 },
      { kind: 'mcq', prompt: 'L’unité de puissance est…', options: ['Joule', 'Newton', 'Watt', 'Pascal'], correct: 2 },
    ],
  },
  {
    id: 'es-bases',
    label: 'Espagnol — basiques',
    emoji: '🇪🇸',
    color: 'from-red-400 to-yellow-400',
    exercises: [
      { kind: 'translate', prompt: 'Traduis : « Je veux de l’eau »', answer: 'Quiero agua', pool: ['Quiero', 'agua', 'leche', 'comida', 'tengo', 'la', 'el'] },
      { kind: 'mcq', prompt: '« Bonjour » en espagnol ?', options: ['Hola', 'Adiós', 'Gracias', 'Por favor'], correct: 0 },
      { kind: 'pair', prompt: 'Associe couleurs', pairs: [{ left: 'rojo', right: 'rouge' }, { left: 'azul', right: 'bleu' }, { left: 'amarillo', right: 'jaune' }, { left: 'verde', right: 'vert' }] },
      { kind: 'fill', prompt: 'Complète', sentence: 'Yo ___ estudiante.', blank: 'soy', options: ['soy', 'eres', 'es', 'somos'] },
      { kind: 'mcq', prompt: 'Singulier de « los libros » ?', options: ['el libro', 'la libro', 'los libro', 'el libros'], correct: 0 },
    ],
  },
  {
    id: 'astro-bases',
    label: 'Astronomie — système solaire',
    emoji: '🪐',
    color: 'from-indigo-400 to-violet-500',
    exercises: [
      { kind: 'mcq', prompt: 'Combien de planètes dans le système solaire ?', options: ['7', '8', '9', '10'], correct: 1 },
      { kind: 'mcq', prompt: 'Plus grosse planète ?', options: ['Saturne', 'Neptune', 'Jupiter', 'Terre'], correct: 2 },
      { kind: 'pair', prompt: 'Associe', pairs: [{ left: 'Mercure', right: 'plus proche du Soleil' }, { left: 'Mars', right: 'planète rouge' }, { left: 'Saturne', right: 'anneaux' }, { left: 'Vénus', right: 'plus chaude' }] },
      { kind: 'fill', prompt: 'Complète', sentence: 'La Lune fait le tour de la Terre en ~ ___ jours.', blank: '29', options: ['7', '15', '29', '90'] },
      { kind: 'mcq', prompt: 'Étoile la plus proche après le Soleil ?', options: ['Sirius', 'Polaris', 'Proxima Centauri', 'Bételgeuse'], correct: 2 },
    ],
  },
  {
    id: 'cs-prog',
    label: 'Programmation — Python',
    emoji: '🐍',
    color: 'from-yellow-400 to-emerald-400',
    exercises: [
      { kind: 'mcq', prompt: 'Comment afficher "Salut" en Python ?', options: ['echo "Salut"', 'print("Salut")', 'console.log("Salut")', 'puts "Salut"'], correct: 1 },
      { kind: 'mcq', prompt: 'len([1,2,3]) renvoie…', options: ['1', '2', '3', 'erreur'], correct: 2 },
      { kind: 'fill', prompt: 'Complète', sentence: 'for i in ___(5): print(i)', blank: 'range', options: ['list', 'range', 'iter', 'count'] },
      { kind: 'mcq', prompt: 'Type de 3.14 ?', options: ['int', 'float', 'str', 'bool'], correct: 1 },
      { kind: 'mcq', prompt: 'Quel mot-clé définit une fonction ?', options: ['function', 'def', 'fn', 'lambda'], correct: 1 },
    ],
  },
  {
    id: 'culture-gen',
    label: 'Culture générale',
    emoji: '🌍',
    color: 'from-fuchsia-400 to-pink-500',
    exercises: [
      { kind: 'mcq', prompt: 'Capitale de l’Australie ?', options: ['Sydney', 'Melbourne', 'Canberra', 'Perth'], correct: 2 },
      { kind: 'mcq', prompt: 'Combien d’os dans le corps humain adulte ?', options: ['106', '186', '206', '306'], correct: 2 },
      { kind: 'pair', prompt: 'Associe œuvre/auteur', pairs: [{ left: 'La Joconde', right: 'Léonard de Vinci' }, { left: 'Les Misérables', right: 'Victor Hugo' }, { left: '5ᵉ symphonie', right: 'Beethoven' }, { left: 'Le Penseur', right: 'Rodin' }] },
      { kind: 'fill', prompt: 'Complète', sentence: 'L’ONU a été fondée en ___', blank: '1945', options: ['1919', '1945', '1957', '1989'] },
      { kind: 'mcq', prompt: 'Plus long fleuve du monde ?', options: ['Amazone', 'Nil', 'Yangtsé', 'Mississippi'], correct: 1 },
    ],
  },
]

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

interface LessonState {
  trackId: string | null
  index: number
  hearts: number
  correct: number
  wrong: number
  finished: boolean
}

const INITIAL: LessonState = { trackId: null, index: 0, hearts: 5, correct: 0, wrong: 0, finished: false }

export default function DailyChallenge() {
  const [state, setState] = useState<LessonState>(INITIAL)
  const [animKey, setAnimKey] = useState(0)
  const [feedback, setFeedback] = useState<'right' | 'wrong' | null>(null)
  const { addXp, updateStreak, addQuizResult, unlockBadge } = useGamificationStore()

  const track = useMemo(() => TRACKS.find((t) => t.id === state.trackId) || null, [state.trackId])
  const exercise = track ? track.exercises[state.index] : null
  const total = track ? track.exercises.length : 0

  const onCorrect = () => {
    setFeedback('right')
    setTimeout(() => {
      setFeedback(null)
      setState((s) => {
        const next = { ...s, correct: s.correct + 1, index: s.index + 1 }
        if (next.index >= (track?.exercises.length || 0)) {
          // finish
          return { ...next, finished: true }
        }
        return next
      })
      setAnimKey((k) => k + 1)
    }, 700)
  }

  const onWrong = () => {
    setFeedback('wrong')
    setTimeout(() => {
      setFeedback(null)
      setState((s) => {
        const next = { ...s, wrong: s.wrong + 1, hearts: Math.max(0, s.hearts - 1), index: s.index + 1 }
        if (next.hearts <= 0 || next.index >= (track?.exercises.length || 0)) {
          return { ...next, finished: true }
        }
        return next
      })
      setAnimKey((k) => k + 1)
    }, 900)
  }

  // Persist results once finished
  useEffect(() => {
    if (!state.finished || !track) return
    const xpGained = state.correct * 10 + (state.hearts > 0 ? 25 : 0)
    addXp(xpGained)
    updateStreak()
    addQuizResult(state.correct, total, `Daily — ${track.label}`)
    if (state.correct === total) unlockBadge('perfect_quiz')
    if (state.correct >= 1) unlockBadge('first_quiz')
  }, [state.finished])

  const reset = () => setState(INITIAL)
  const choosTrack = (id: string) => setState({ ...INITIAL, trackId: id })

  // SCREEN: track picker
  if (!track) {
    return (
      <div className="space-y-5 animate-fade-in-up">
        <div className="text-center space-y-1">
          <div className="mono-kicker text-[10px] text-aurora-text-dim">Mini-leçon du jour</div>
          <h1 className="text-3xl font-black gradient-text-fire">Choisis ta piste</h1>
          <p className="text-sm text-aurora-text-dim max-w-md mx-auto">5 questions chronométrées · gagne XP, perds des cœurs si tu te trompes. Style Duolingo.</p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {TRACKS.map((t, i) => (
            <motion.button
              key={t.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              whileHover={{ y: -4, scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => choosTrack(t.id)}
              className="group relative overflow-hidden rounded-2xl text-left p-5"
              style={{ background: `linear-gradient(135deg, var(--tw-gradient-stops))` }}
            >
              <div className={`absolute inset-0 bg-gradient-to-br ${t.color} opacity-90`} />
              <div className="absolute inset-0 dot-grid opacity-20" />
              <div className="relative flex items-center gap-4">
                <div className="text-5xl drop-shadow">{t.emoji}</div>
                <div className="flex-1">
                  <div className="text-lg font-bold text-white drop-shadow">{t.label}</div>
                  <div className="text-xs text-white/80 mt-1">{t.exercises.length} exercices · ~3 min</div>
                </div>
                <div className="rounded-full bg-white/20 backdrop-blur p-3 group-hover:scale-110 transition-transform">
                  <Zap size={18} className="text-white" />
                </div>
              </div>
            </motion.button>
          ))}
        </div>
      </div>
    )
  }

  // SCREEN: finished
  if (state.finished || !exercise) {
    const xpGained = state.correct * 10 + (state.hearts > 0 ? 25 : 0)
    const success = state.correct >= 3
    return (
      <div className="flex flex-col items-center justify-center py-10 animate-fade-in-up text-center space-y-6">
        <motion.div
          initial={{ scale: 0, rotate: -180 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{ type: 'spring', stiffness: 200, damping: 14 }}
          className={`relative h-32 w-32 rounded-full bg-gradient-to-br ${success ? 'from-yellow-400 via-orange-400 to-pink-500' : 'from-slate-500 to-slate-700'} flex items-center justify-center shadow-2xl animate-glow-pulse`}
        >
          <Trophy size={56} className="text-white drop-shadow-2xl" />
          <div className="absolute -inset-2 rounded-full bg-white/20 blur-xl pointer-events-none animate-aurora-pulse" />
        </motion.div>

        <div>
          <h1 className="text-3xl font-black gradient-text-cosmic">
            {success ? 'Bien joué !' : 'Continue d’essayer !'}
          </h1>
          <p className="text-sm text-aurora-text-dim mt-2">
            {state.correct} / {total} bonnes réponses · {state.hearts} cœurs restants
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <div className="chip-xp text-base px-4 py-2"><Sparkles size={14} /> +{xpGained} XP</div>
          {state.correct === total && (
            <div className="chip-streak text-base px-4 py-2 animate-streak-glow">⭐ Sans faute</div>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <button onClick={reset} className="btn-aurora">
            <RotateCcw size={16} /> Choisir une autre piste
          </button>
        </div>
      </div>
    )
  }

  // SCREEN: lesson
  const progressPct = Math.min(100, (state.index / total) * 100)
  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Header bar */}
      <div className="flex items-center gap-3">
        <button
          onClick={reset}
          className="rounded-full p-2 bg-white/5 hover:bg-white/10 border border-white/10 text-aurora-text-dim hover:text-aurora-text transition-colors"
        >
          <X size={18} />
        </button>
        <div className="flex-1">
          <div className="progress-aurora">
            <motion.div
              className="progress-aurora-fill progress-warm-fill"
              initial={false}
              animate={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
        <HeartCount value={state.hearts} />
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={animKey}
          initial={{ opacity: 0, x: 20, scale: 0.96 }}
          animate={{ opacity: 1, x: 0, scale: 1 }}
          exit={{ opacity: 0, x: -20, scale: 0.96 }}
          transition={{ duration: 0.28 }}
          className={`holo-card p-6 sm:p-8 ${feedback === 'right' ? 'neon-outline-green' : feedback === 'wrong' ? 'neon-outline-pink animate-shake-x' : ''}`}
        >
          <div className="mono-kicker text-[10px] text-aurora-text-dim mb-4">
            Question {state.index + 1} / {total}
          </div>

          {exercise.kind === 'mcq' && (
            <McqCard ex={exercise} onCorrect={onCorrect} onWrong={onWrong} />
          )}
          {exercise.kind === 'translate' && (
            <TranslateCard ex={exercise} onCorrect={onCorrect} onWrong={onWrong} />
          )}
          {exercise.kind === 'pair' && (
            <PairCard ex={exercise} onCorrect={onCorrect} onWrong={onWrong} />
          )}
          {exercise.kind === 'fill' && (
            <FillCard ex={exercise} onCorrect={onCorrect} onWrong={onWrong} />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

function HeartCount({ value }: { value: number }) {
  return (
    <div className="inline-flex items-center gap-1 rounded-2xl border border-pink-400/30 bg-pink-500/10 px-3 py-2">
      <Heart size={16} className="text-pink-300 fill-pink-400/70 animate-aurora-pulse" />
      <span className="text-sm font-bold text-pink-100">{value}</span>
    </div>
  )
}

function McqCard({ ex, onCorrect, onWrong }: { ex: Extract<Exercise, { kind: 'mcq' }>; onCorrect: () => void; onWrong: () => void }) {
  const [picked, setPicked] = useState<number | null>(null)
  const handle = (i: number) => {
    if (picked !== null) return
    setPicked(i)
    if (i === ex.correct) onCorrect()
    else onWrong()
  }
  return (
    <div className="space-y-5">
      <h2 className="text-xl sm:text-2xl font-bold text-aurora-text">{ex.prompt}</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {ex.options.map((opt, i) => {
          const isCorrect = i === ex.correct && picked !== null
          const isWrong = picked === i && i !== ex.correct
          return (
            <motion.button
              key={i}
              whileHover={picked === null ? { y: -2, scale: 1.01 } : undefined}
              whileTap={picked === null ? { scale: 0.97 } : undefined}
              onClick={() => handle(i)}
              disabled={picked !== null}
              className={`relative rounded-2xl border-2 p-4 text-left text-sm font-medium transition-all ${
                isCorrect
                  ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100'
                  : isWrong
                    ? 'border-rose-400 bg-rose-500/15 text-rose-100'
                    : picked !== null
                      ? 'border-white/8 bg-white/3 text-aurora-text-dim opacity-60'
                      : 'border-white/12 bg-white/5 text-aurora-text hover:border-violet-400/40 hover:bg-violet-500/10'
              }`}
            >
              <span className="mr-3 inline-flex h-7 w-7 items-center justify-center rounded-full bg-white/10 text-xs font-bold">
                {String.fromCharCode(65 + i)}
              </span>
              {opt}
              {isCorrect && <Check size={18} className="absolute right-3 top-1/2 -translate-y-1/2 text-emerald-300" />}
              {isWrong && <X size={18} className="absolute right-3 top-1/2 -translate-y-1/2 text-rose-300" />}
            </motion.button>
          )
        })}
      </div>
      {picked !== null && ex.explanation && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-cyan-400/25 bg-cyan-500/10 p-3 text-sm text-cyan-100"
        >
          <Sparkles size={13} className="inline mr-1.5" />
          {ex.explanation}
        </motion.div>
      )}
    </div>
  )
}

function TranslateCard({ ex, onCorrect, onWrong }: { ex: Extract<Exercise, { kind: 'translate' }>; onCorrect: () => void; onWrong: () => void }) {
  const [picked, setPicked] = useState<string[]>([])
  const [submitted, setSubmitted] = useState<null | 'right' | 'wrong'>(null)
  const pool = useMemo(() => shuffle(ex.pool), [ex])
  const togglePick = (w: string) => {
    if (submitted) return
    setPicked((p) => (p.includes(w) ? p.filter((x) => x !== w) : [...p, w]))
  }
  const submit = () => {
    if (submitted) return
    const ok = picked.join(' ') === ex.answer
    setSubmitted(ok ? 'right' : 'wrong')
    setTimeout(() => (ok ? onCorrect() : onWrong()), 200)
  }
  return (
    <div className="space-y-5">
      <h2 className="text-xl sm:text-2xl font-bold text-aurora-text">{ex.prompt}</h2>
      <div className="min-h-[3.5rem] rounded-2xl border-2 border-dashed border-white/10 bg-white/3 px-4 py-3 text-base text-aurora-text">
        {picked.length === 0 ? <span className="text-aurora-text-dim italic">Construis ta phrase…</span> : picked.join(' ')}
      </div>
      <div className="flex flex-wrap gap-2">
        {pool.map((w, i) => (
          <button
            key={`${w}-${i}`}
            onClick={() => togglePick(w)}
            disabled={!!submitted}
            className={`rounded-xl border-2 px-3 py-2 text-sm font-medium transition-all ${
              picked.includes(w)
                ? 'border-violet-400/60 bg-violet-500/20 text-violet-100'
                : 'border-white/10 bg-white/5 text-aurora-text hover:border-cyan-400/40'
            }`}
          >
            {w}
          </button>
        ))}
      </div>
      <button
        onClick={submit}
        disabled={picked.length === 0 || !!submitted}
        className="btn-aurora w-full justify-center disabled:opacity-50"
      >
        {submitted === 'right' ? '✓ Bravo' : submitted === 'wrong' ? '✗ Réponse: ' + ex.answer : 'Vérifier'}
      </button>
    </div>
  )
}

function PairCard({ ex, onCorrect, onWrong }: { ex: Extract<Exercise, { kind: 'pair' }>; onCorrect: () => void; onWrong: () => void }) {
  const lefts = useMemo(() => shuffle(ex.pairs.map((p) => p.left)), [ex])
  const rights = useMemo(() => shuffle(ex.pairs.map((p) => p.right)), [ex])
  const [selectedLeft, setSelectedLeft] = useState<string | null>(null)
  const [matched, setMatched] = useState<Record<string, string>>({})
  const [wrongFlash, setWrongFlash] = useState<string | null>(null)
  const finished = Object.keys(matched).length === ex.pairs.length

  useEffect(() => {
    if (finished) {
      setTimeout(onCorrect, 350)
    }
  }, [finished])

  const pickLeft = (l: string) => {
    if (matched[l]) return
    setSelectedLeft(l)
  }
  const pickRight = (r: string) => {
    if (Object.values(matched).includes(r)) return
    if (!selectedLeft) return
    const ok = ex.pairs.find((p) => p.left === selectedLeft && p.right === r)
    if (ok) {
      setMatched((m) => ({ ...m, [selectedLeft]: r }))
      setSelectedLeft(null)
    } else {
      setWrongFlash(`${selectedLeft}|${r}`)
      setTimeout(() => setWrongFlash(null), 350)
      setSelectedLeft(null)
      onWrong()
    }
  }

  return (
    <div className="space-y-5">
      <h2 className="text-xl sm:text-2xl font-bold text-aurora-text">{ex.prompt}</h2>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          {lefts.map((l) => {
            const isMatched = !!matched[l]
            const isSelected = selectedLeft === l
            return (
              <button
                key={l}
                onClick={() => pickLeft(l)}
                disabled={isMatched}
                className={`w-full rounded-xl border-2 px-4 py-3 text-sm font-semibold transition-all ${
                  isMatched
                    ? 'border-emerald-400/50 bg-emerald-500/10 text-emerald-100 line-through opacity-70'
                    : isSelected
                      ? 'border-violet-400 bg-violet-500/20 text-violet-50'
                      : 'border-white/10 bg-white/5 text-aurora-text hover:border-violet-400/40'
                }`}
              >
                {l}
              </button>
            )
          })}
        </div>
        <div className="space-y-2">
          {rights.map((r) => {
            const isMatched = Object.values(matched).includes(r)
            const isWrong = wrongFlash?.endsWith(`|${r}`)
            return (
              <button
                key={r}
                onClick={() => pickRight(r)}
                disabled={isMatched}
                className={`w-full rounded-xl border-2 px-4 py-3 text-sm font-semibold transition-all ${
                  isMatched
                    ? 'border-emerald-400/50 bg-emerald-500/10 text-emerald-100 opacity-70'
                    : isWrong
                      ? 'border-rose-400 bg-rose-500/20 text-rose-100 animate-shake-x'
                      : 'border-white/10 bg-white/5 text-aurora-text hover:border-cyan-400/40'
                }`}
              >
                {r}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function FillCard({ ex, onCorrect, onWrong }: { ex: Extract<Exercise, { kind: 'fill' }>; onCorrect: () => void; onWrong: () => void }) {
  const [picked, setPicked] = useState<string | null>(null)
  const handle = (opt: string) => {
    if (picked) return
    setPicked(opt)
    if (opt === ex.blank) onCorrect()
    else onWrong()
  }
  const parts = ex.sentence.split('___')
  return (
    <div className="space-y-5">
      <h2 className="text-xl sm:text-2xl font-bold text-aurora-text">{ex.prompt}</h2>
      <div className="rounded-2xl border-2 border-dashed border-white/10 bg-white/3 p-5 text-lg text-aurora-text">
        {parts[0]}
        <span className={`mx-2 inline-block min-w-[6rem] rounded-lg border-2 px-3 py-1 text-center ${
          picked === ex.blank ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100' : picked && picked !== ex.blank ? 'border-rose-400 bg-rose-500/15 text-rose-100' : 'border-violet-400/40 bg-violet-500/10 text-violet-100'
        }`}>
          {picked || '___'}
        </span>
        {parts[1] || ''}
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {ex.options.map((opt) => (
          <button
            key={opt}
            onClick={() => handle(opt)}
            disabled={!!picked}
            className={`rounded-xl border-2 px-4 py-3 text-sm font-medium transition-all ${
              picked === opt && opt === ex.blank
                ? 'border-emerald-400 bg-emerald-500/15 text-emerald-100'
                : picked === opt
                  ? 'border-rose-400 bg-rose-500/15 text-rose-100'
                  : 'border-white/10 bg-white/5 text-aurora-text hover:border-violet-400/40'
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  )
}
