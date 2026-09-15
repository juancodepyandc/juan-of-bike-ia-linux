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

export default function LearningView() {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [recoveryPrompt, setRecoveryPrompt] = useState<string | null>(null)
  const [lessonContext, setLessonContext] = useState<LessonRef | null>(null)
  const visitedRef = useRef<Set<Tab>>(new Set(['dashboard']))
  const [, forceUpdate] = useState(0)
  const recovery = useGenerationRecovery('learning')

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
        <div className="flex items-center gap-3 mb-3 sm:mb-4">
          <div className={`rounded-2xl bg-gradient-to-br ${activeTab.gradient} p-2.5 shadow-lg`}>
            <GraduationCap size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-black gradient-text leading-none">Académie Aurora</h1>
            <p className="text-[11px] text-aurora-text-dim mt-0.5">Quiz · Cours · Fiches · Parcours · Labs Duolingo · Physique · Chimie · SIN · Maths</p>
          </div>
        </div>

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
