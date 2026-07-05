import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Atom,
  BookOpen,
  Brain,
  CircuitBoard,
  Crown,
  Film,
  Flame,
  FlaskConical,
  Gem,
  Globe,
  GraduationCap,
  Heart,
  Layers,
  Library,
  Lightbulb,
  Map as MapIcon,
  Medal,
  Plane,
  Sparkles,
  Star,
  Sigma,
  Target,
  TreePine,
  Trophy,
  Zap,
} from 'lucide-react'
import { useFlashcardsStore } from '../../stores/flashcardsStore'
import { useGamificationStore } from '../../stores/gamificationStore'
import type { Tab } from './types'

interface HubProps {
  onNavigate: (tab: Tab) => void
}

// Confetti component used on streak milestones
function Confetti({ trigger }: { trigger: number }) {
  const colors = ['#a78bfa', '#22d3ee', '#34d399', '#fde047', '#fb923c', '#ec4899']
  return (
    <AnimatePresence>
      {trigger > 0 && (
        <div className="pointer-events-none absolute inset-0">
          {Array.from({ length: 22 }).map((_, i) => {
            const angle = (Math.random() * 360 * Math.PI) / 180
            const dist = 90 + Math.random() * 140
            return (
              <motion.span
                key={`${trigger}-${i}`}
                initial={{ x: 0, y: 0, scale: 0, opacity: 1 }}
                animate={{
                  x: Math.cos(angle) * dist,
                  y: Math.sin(angle) * dist - 40,
                  scale: 1,
                  opacity: 0,
                  rotate: 720,
                }}
                transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
                className="absolute left-1/2 top-1/2 h-2.5 w-2.5 rounded-sm"
                style={{ background: colors[i % colors.length] }}
              />
            )
          })}
        </div>
      )}
    </AnimatePresence>
  )
}

function StreakBadge({ value }: { value: number }) {
  return (
    <div className="relative inline-flex items-center gap-2 rounded-2xl border border-orange-400/40 bg-gradient-to-br from-orange-500/20 via-pink-500/15 to-amber-500/15 px-3 py-2 animate-streak-glow">
      <Flame size={18} className="text-orange-300 animate-streak-flame" />
      <div>
        <div className="text-xs uppercase tracking-widest text-orange-200/80">Série</div>
        <div className="text-lg font-bold text-orange-50">{value}<span className="text-xs text-orange-200/70 ml-0.5">j</span></div>
      </div>
    </div>
  )
}

function HeartLives({ count = 5, max = 5 }: { count?: number; max?: number }) {
  return (
    <div className="inline-flex items-center gap-1 rounded-2xl border border-pink-400/30 bg-pink-500/10 px-3 py-2">
      <Heart size={16} className="text-pink-300 fill-pink-400/70" />
      <span className="text-sm font-bold text-pink-100">{count}</span>
      <span className="text-xs text-pink-200/60">/ {max}</span>
    </div>
  )
}

function LevelOrb({ level, xp, xpForNext }: { level: number; xp: number; xpForNext: number }) {
  const pct = Math.min(100, (xp / Math.max(1, xpForNext)) * 100)
  const r = 56
  const c = 2 * Math.PI * r
  return (
    <div className="relative h-[140px] w-[140px]">
      <svg viewBox="0 0 140 140" className="absolute inset-0 -rotate-90">
        <defs>
          <linearGradient id="orbGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#a78bfa" />
            <stop offset="50%" stopColor="#22d3ee" />
            <stop offset="100%" stopColor="#34d399" />
          </linearGradient>
        </defs>
        <circle cx="70" cy="70" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="8" />
        <motion.circle
          cx="70" cy="70" r={r} fill="none"
          stroke="url(#orbGrad)" strokeWidth="8" strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c - (c * pct) / 100 }}
          transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <Crown size={20} className="text-yellow-300 mb-1 drop-shadow" />
        <div className="text-3xl font-black gradient-text-cosmic">{level}</div>
        <div className="text-[10px] uppercase tracking-widest text-aurora-text-dim">Niveau</div>
      </div>
    </div>
  )
}

interface SkillNode {
  id: string
  label: string
  icon: typeof BookOpen
  tab: Tab
  status: 'locked' | 'available' | 'in-progress' | 'mastered'
  color: string
  description: string
}

function buildSkillTree(progress: { quizCount: number; deckCount: number; pathCount: number; mastered: number; level: number }): SkillNode[] {
  const { quizCount, deckCount, pathCount } = progress
  return [
    { id: 'lang', label: 'Daily', icon: Zap, tab: 'daily', status: 'available', color: 'from-yellow-400 to-orange-400', description: 'Mini-leçon du jour' },
    { id: 'library', label: 'Bibliothèque', icon: Library, tab: 'library', status: 'available', color: 'from-amber-400 to-orange-500', description: '10 cours rédigés' },
    { id: 'quiz', label: 'Quiz', icon: Target, tab: 'quiz', status: quizCount > 0 ? 'mastered' : 'available', color: 'from-cyan-400 to-blue-500', description: 'Teste-toi' },
    { id: 'fiches', label: 'Fiches', icon: Layers, tab: 'fiches', status: deckCount > 0 ? 'in-progress' : 'available', color: 'from-violet-400 to-purple-500', description: 'Cartes mémoire' },
    { id: 'cours', label: 'Cours IA', icon: BookOpen, tab: 'courses', status: 'available', color: 'from-emerald-400 to-teal-500', description: 'Génère un cours' },
    { id: 'parcours', label: 'Parcours', icon: MapIcon, tab: 'parcours', status: pathCount > 0 ? 'in-progress' : 'available', color: 'from-purple-400 to-pink-500', description: 'Itinéraire complet' },
    { id: 'physique', label: 'Physique', icon: Atom, tab: 'physics', status: 'available', color: 'from-blue-400 to-indigo-500', description: 'Lab interactif' },
    { id: 'chimie', label: 'Chimie', icon: FlaskConical, tab: 'chemistry', status: 'available', color: 'from-green-400 to-emerald-500', description: 'Tableau + molécules' },
    { id: 'sin', label: 'SIN', icon: CircuitBoard, tab: 'electronics', status: 'available', color: 'from-orange-400 to-red-500', description: 'Arduino simulé' },
    { id: 'maths', label: 'Maths', icon: Sigma, tab: 'math', status: 'available', color: 'from-pink-400 to-rose-500', description: 'Plotter, géométrie' },
    { id: 'astro', label: 'Astro', icon: Globe, tab: 'astronomy', status: 'available', color: 'from-indigo-400 to-blue-500', description: 'Système solaire' },
    { id: 'modeling', label: 'Modèles', icon: TreePine, tab: 'modeling', status: 'available', color: 'from-emerald-400 to-cyan-500', description: 'SIR, Lotka, IA' },
    { id: 'modelism', label: 'Modélisme', icon: Plane, tab: 'modelism', status: 'available', color: 'from-rose-400 to-orange-500', description: 'Avion/Auto/Train RC' },
    { id: 'video', label: 'Vidéo', icon: Film, tab: 'video', status: 'available', color: 'from-fuchsia-400 to-pink-500', description: 'Analyse cours filmés' },
  ]
}

function SkillBubble({ node, onClick, index }: { node: SkillNode; onClick: () => void; index: number }) {
  const Icon = node.icon
  const offset = (index % 2 === 0 ? -1 : 1) * 18
  const isLocked = node.status === 'locked'
  const isMastered = node.status === 'mastered'
  return (
    <motion.div
      initial={{ opacity: 0, y: 30, scale: 0.7 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: index * 0.05, type: 'spring', stiffness: 200, damping: 18 }}
      style={{ transform: `translateX(${offset}px)` }}
      className="relative flex flex-col items-center"
    >
      <motion.button
        whileHover={!isLocked ? { y: -6, scale: 1.06 } : undefined}
        whileTap={!isLocked ? { scale: 0.96 } : undefined}
        onClick={isLocked ? undefined : onClick}
        disabled={isLocked}
        className={`relative h-20 w-20 rounded-full p-[3px] transition-all ${
          isLocked ? 'opacity-40 grayscale cursor-not-allowed' : 'cursor-pointer'
        }`}
        style={{
          background: isLocked
            ? 'rgba(255,255,255,0.08)'
            : `linear-gradient(135deg, var(--tw-gradient-stops))`,
        }}
      >
        <div className={`relative h-full w-full rounded-full bg-gradient-to-br ${node.color} flex items-center justify-center shadow-2xl ${!isLocked ? 'animate-glow-pulse' : ''}`}>
          <Icon size={28} className="text-white drop-shadow" />
          {isMastered && (
            <div className="absolute -top-1 -right-1 h-7 w-7 rounded-full bg-gradient-to-br from-yellow-300 to-orange-400 flex items-center justify-center text-[10px] shadow-lg border-2 border-aurora-bg">
              <Star size={12} className="text-white fill-white" />
            </div>
          )}
          {node.status === 'in-progress' && (
            <div className="absolute -top-1 -right-1 h-6 w-6 rounded-full bg-cyan-400 flex items-center justify-center shadow border-2 border-aurora-bg animate-aurora-pulse">
              <Zap size={11} className="text-white" />
            </div>
          )}
        </div>
      </motion.button>
      <div className="mt-2 text-center">
        <div className="text-xs font-semibold text-aurora-text">{node.label}</div>
        <div className="text-[10px] text-aurora-text-dim mt-0.5 max-w-[100px]">{node.description}</div>
      </div>
    </motion.div>
  )
}

export default function Hub({ onNavigate }: HubProps) {
  const { xp, level, streak, badges, quizHistory } = useGamificationStore()
  const { decks, cards } = useFlashcardsStore()
  const xpForNext = Math.max(100, level * level * 100)
  const dueCards = cards.filter((c) => c.dueAt <= Date.now()).length
  const masteredCards = cards.filter((c) => c.box >= 4).length

  const [confettiKey, setConfettiKey] = useState(0)
  const prevStreak = useRef(streak)
  useEffect(() => {
    if (streak > prevStreak.current && streak > 0) {
      setConfettiKey((k) => k + 1)
    }
    prevStreak.current = streak
  }, [streak])

  const skillNodes = useMemo(
    () => buildSkillTree({
      quizCount: quizHistory.length,
      deckCount: decks.length,
      pathCount: 0,
      mastered: masteredCards,
      level,
    }),
    [quizHistory.length, decks.length, masteredCards, level],
  )

  const dailyGoalProgress = Math.min(100, (xp % 50) * 2)

  return (
    <div className="relative space-y-6 animate-fade-in-up">
      <Confetti trigger={confettiKey} />

      {/* HERO BAR — Streak / Level / Hearts / XP */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="holo-card holo-card-cyan relative overflow-hidden p-5 sm:p-6"
      >
        <div className="absolute inset-0 aurora-mesh opacity-60 pointer-events-none" />
        <div className="absolute -top-20 -right-20 h-60 w-60 rounded-full bg-cyan-400/20 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-20 -left-20 h-60 w-60 rounded-full bg-violet-500/20 blur-3xl pointer-events-none" />

        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-5">
            <LevelOrb level={level} xp={xp} xpForNext={xpForNext} />
            <div className="space-y-2">
              <div className="mono-kicker text-[10px] text-cyan-300/80">Académie Aurora</div>
              <h1 className="text-3xl font-black tracking-tight gradient-text">
                Bonjour, prêt à apprendre&nbsp;?
              </h1>
              <p className="text-sm text-aurora-text-muted">
                {xp} XP · prochain niveau dans {Math.max(0, xpForNext - xp)} XP
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <StreakBadge value={streak} />
            <HeartLives count={5} max={5} />
            <div className="chip-xp">
              <Gem size={12} />
              <span>{xp} XP</span>
            </div>
            <div className="rounded-2xl border border-violet-400/30 bg-violet-500/10 px-3 py-2">
              <div className="text-xs uppercase tracking-widest text-violet-200/80">Badges</div>
              <div className="text-lg font-bold text-violet-50">{badges.length}</div>
            </div>
          </div>
        </div>

        {/* Daily Goal */}
        <div className="relative mt-5">
          <div className="flex items-center justify-between text-xs mb-1.5">
            <span className="text-aurora-text-muted inline-flex items-center gap-1.5">
              <Target size={12} className="text-cyan-300" />
              Objectif quotidien · {Math.min(50, xp % 50)} / 50 XP
            </span>
            <span className="text-aurora-text-dim">{dailyGoalProgress}%</span>
          </div>
          <div className="progress-aurora">
            <motion.div
              className="progress-aurora-fill"
              initial={{ width: 0 }}
              animate={{ width: `${dailyGoalProgress}%` }}
            />
          </div>
        </div>
      </motion.div>

      {/* Daily Challenge CTA */}
      <motion.button
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        whileHover={{ y: -3, scale: 1.005 }}
        whileTap={{ scale: 0.99 }}
        onClick={() => onNavigate('daily')}
        className="group relative w-full overflow-hidden rounded-2xl text-left"
        style={{ background: 'linear-gradient(135deg, #fde047 0%, #fb923c 50%, #ec4899 100%)' }}
      >
        <div className="absolute inset-0 opacity-30 mix-blend-overlay">
          <div className="absolute inset-0 dot-grid" />
        </div>
        <div className="relative flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="rounded-2xl bg-white/25 p-3.5 backdrop-blur shadow-xl">
              <Zap size={32} className="text-white drop-shadow" />
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-[0.22em] text-white/80 font-semibold">Mission éclair</div>
              <h2 className="text-2xl font-black text-white drop-shadow-sm">Mini-leçon du jour</h2>
              <p className="text-sm text-white/85 mt-0.5">5 questions chronométrées · style Duolingo · +25 XP garantis</p>
            </div>
          </div>
          <div className="rounded-2xl bg-white/95 px-5 py-3 font-bold text-orange-600 shadow-2xl group-hover:scale-105 transition-transform">
            Commencer →
          </div>
        </div>
      </motion.button>

      {/* CONTINUE ACTIONS */}
      {(dueCards > 0 || quizHistory.length > 0) && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {dueCards > 0 && (
            <motion.button
              whileHover={{ y: -3 }}
              onClick={() => onNavigate('fiches')}
              className="holo-card holo-card-pink p-4 text-left"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-gradient-to-br from-pink-400 to-rose-500 p-2.5 shadow-lg">
                  <Layers size={18} className="text-white" />
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-pink-300/80">À réviser</div>
                  <div className="text-lg font-bold text-aurora-text">{dueCards} fiche{dueCards > 1 ? 's' : ''}</div>
                </div>
              </div>
            </motion.button>
          )}
          {quizHistory[0] && (
            <motion.button
              whileHover={{ y: -3 }}
              onClick={() => onNavigate('quiz')}
              className="holo-card holo-card-cyan p-4 text-left"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-gradient-to-br from-cyan-400 to-blue-500 p-2.5 shadow-lg">
                  <Target size={18} className="text-white" />
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-cyan-300/80">Refaire</div>
                  <div className="text-sm font-semibold text-aurora-text truncate max-w-[170px]">{quizHistory[0].topic}</div>
                </div>
              </div>
            </motion.button>
          )}
          <motion.button
            whileHover={{ y: -3 }}
            onClick={() => onNavigate('parcours')}
            className="holo-card holo-card-warm p-4 text-left"
          >
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 p-2.5 shadow-lg">
                <MapIcon size={18} className="text-white" />
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-widest text-orange-300/80">Tracer</div>
                <div className="text-lg font-bold text-aurora-text">Nouveau parcours</div>
              </div>
            </div>
          </motion.button>
        </div>
      )}

      {/* SKILL TREE */}
      <div className="holo-card p-5 sm:p-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <div className="mono-kicker text-[10px] text-aurora-text-dim">Arbre des compétences</div>
            <h2 className="text-xl font-bold gradient-text mt-1">Choisis ta voie</h2>
          </div>
          <div className="hidden sm:flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-aurora-text-dim">
            <Sparkles size={12} className="text-violet-300" />
            <span>{skillNodes.length} disciplines</span>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-y-7 sm:grid-cols-4 lg:grid-cols-5 gap-x-2 px-2">
          {skillNodes.map((node, i) => (
            <SkillBubble key={node.id} node={node} index={i} onClick={() => onNavigate(node.tab)} />
          ))}
        </div>
      </div>

      {/* STATS GRID */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Star} label="Niveau" value={`${level}`} gradient="from-yellow-400 to-orange-400" />
        <StatCard icon={Trophy} label="Badges" value={`${badges.length}`} gradient="from-violet-400 to-purple-500" />
        <StatCard icon={Layers} label="Fiches" value={`${masteredCards}/${cards.length}`} gradient="from-cyan-400 to-blue-500" />
        <StatCard icon={Brain} label="Quiz passés" value={`${quizHistory.length}`} gradient="from-emerald-400 to-teal-500" />
      </div>

      {/* BADGES SHOWCASE */}
      {badges.length > 0 && (
        <div className="holo-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2">
              <Medal size={16} className="text-yellow-300" />
              Badges débloqués
            </h3>
            <span className="text-[11px] text-aurora-text-dim">{badges.length} obtenus</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {badges.map((badge, i) => (
              <motion.div
                key={badge.id}
                initial={{ opacity: 0, scale: 0.6 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.05, type: 'spring' }}
                className="group relative flex items-center gap-2 rounded-2xl border border-yellow-300/30 bg-gradient-to-br from-yellow-300/10 to-orange-400/10 px-3 py-2 hover:border-yellow-300/60 transition-colors"
              >
                <span className="text-xl">{badge.icon}</span>
                <span className="text-xs font-medium text-aurora-text">{badge.label}</span>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ icon: Icon, label, value, gradient }: { icon: typeof Star; label: string; value: string; gradient: string }) {
  return (
    <motion.div
      whileHover={{ y: -4 }}
      className="holo-card p-4"
    >
      <div className="flex items-center gap-3">
        <div className={`rounded-xl bg-gradient-to-br ${gradient} p-2.5 shadow-lg`}>
          <Icon size={18} className="text-white" />
        </div>
        <div>
          <div className="text-2xl font-black gradient-text leading-none">{value}</div>
          <div className="text-[10px] uppercase tracking-widest text-aurora-text-dim mt-1">{label}</div>
        </div>
      </div>
    </motion.div>
  )
}
