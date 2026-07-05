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

import type { Tab, SavedCourse, LessonRef, TocEntry } from './types'
import { buildLearningSystemPrompt, extractToc } from './utils'
import { ReadingProgress, SourcesPanel } from './sharedComponents'

const COURSES_STORAGE_KEY = 'aurora_saved_courses'

function CoursesPanel({
  recoveryPrompt,
  clearRecoveryPrompt,
  lessonContext,
}: {
  recoveryPrompt?: string | null
  clearRecoveryPrompt?: () => void
  lessonContext?: LessonRef | null
}) {
  const markCourseRead = useLessonProgressStore((state) => state.markCourseRead)
  const { mainModel, visionModel } = useAppStore()
  const { trackGeneration, completeGeneration, failGeneration } = useGenerationTrackerStore()
  const { executeWithRuntime } = useManagedRuntime()
  const activeTrackerIdRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  useEffect(() => () => { abortRef.current?.abort() }, [])
  const { pushMessage, getRecentMessages } = useModuleHistoryStore()
  const [contextFiles, setContextFiles] = useState<File[]>([])
  const { pack: assetPack, preparePack } = useModuleAssetPack({
    module: 'learning',
    title: 'Pack modele academie',
    assets: buildLearningModuleAssets(mainModel, visionModel, contextFiles.length > 0),
  })
  // Restore session state persisted across restarts
  const _savedCourses = useLearningSessionStore((s) => s.courses)
  const saveCourses = useLearningSessionStore((s) => s.saveCourses)
  const [topic, setTopic] = useState(_savedCourses?.topic ?? '')
  const [level, setLevel] = useState(_savedCourses?.level ?? 'intermediaire')
  const [courseContent, setCourseContent] = useState(_savedCourses?.courseContent ?? '')
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState('Aucun cours en cours.')
  const [clarification, setClarification] = useState<ClarificationRequest | null>(null)
  const [courseSummary, setCourseSummary] = useState(_savedCourses?.courseSummary ?? '')
  const [courseSources, setCourseSources] = useState<LearningSource[]>(_savedCourses?.sources ?? [])
  const [showCourseSources, setShowCourseSources] = useState(false)
  const [showSavedList, setShowSavedList] = useState(false)
  const [savedCourses, setSavedCourses] = useState<SavedCourse[]>(() => {
    try { return JSON.parse(localStorage.getItem(COURSES_STORAGE_KEY) ?? '[]') as SavedCourse[] }
    catch { return [] }
  })
  const activeModel = contextFiles.length > 0 ? visionModel : mainModel
  const contentRef = useRef<HTMLDivElement | null>(null)

  // Persist session state so it survives app restarts
  useEffect(() => {
    if (topic || courseContent) {
      saveCourses({ topic, level, courseContent, courseSummary, sources: courseSources })
    }
  }, [topic, level, courseContent, courseSummary, courseSources, saveCourses])

  // MEMORY-SAFE streaming: batch tokens behind a 400ms timer instead of a
  // rAF (~16ms). Each setCourseContent re-parses the full markdown via
  // react-markdown + KaTeX — 60 parses per second on a 50K-char course
  // freezes the UI. 400ms keeps the live preview responsive (2-3 flushes per
  // second) while cutting the re-parse cost by ~25×.
  const courseBufferRef = useRef<string[]>([])
  const courseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const flushCourseBuffer = useCallback(() => {
    courseTimerRef.current = null
    const toFlush = courseBufferRef.current.join('')
    courseBufferRef.current = []
    if (toFlush) setCourseContent((prev) => prev + toFlush)
  }, [])
  const scheduleCourseFlush = useCallback(() => {
    if (courseTimerRef.current !== null) return
    courseTimerRef.current = setTimeout(flushCourseBuffer, 400)
  }, [flushCourseBuffer])
  useEffect(() => () => {
    if (courseTimerRef.current !== null) clearTimeout(courseTimerRef.current)
    courseBufferRef.current = []
  }, [])
  const toc = useMemo(() => extractToc(courseContent), [courseContent])
  const [activeHeadingId, setActiveHeadingId] = useState<string | null>(null)
  const [copyFeedback, setCopyFeedback] = useState<'idle' | 'copied'>('idle')

  useEffect(() => {
    const root = contentRef.current
    if (!root || toc.length === 0) return
    const headings = Array.from(root.querySelectorAll<HTMLElement>('h1[id], h2[id], h3[id]'))
    if (headings.length === 0) return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible[0]?.target.id) {
          setActiveHeadingId(visible[0].target.id)
        }
      },
      { root, rootMargin: '0px 0px -70% 0px', threshold: [0, 0.1, 0.4, 1] },
    )
    headings.forEach((heading) => observer.observe(heading))
    return () => observer.disconnect()
  }, [courseContent, toc.length])

  const copyCourse = useCallback(async () => {
    if (!courseContent) return
    try {
      await navigator.clipboard.writeText(`# ${topic}\n\n${courseContent}`)
      setCopyFeedback('copied')
      window.setTimeout(() => setCopyFeedback('idle'), 1600)
    } catch {
      setCopyFeedback('idle')
    }
  }, [courseContent, topic])

  // Consume recovery prompt to pre-fill the topic
  useEffect(() => {
    if (recoveryPrompt) {
      setTopic(recoveryPrompt)
      clearRecoveryPrompt?.()
    }
  }, [recoveryPrompt, clearRecoveryPrompt])

  const generateCourse = useCallback(async () => {
    if (!topic.trim()) {
      return
    }

    setIsLoading(true)
    setCourseContent('')
    setCourseSources([])
    setCourseSummary('')
    setStatus('Preparation du cours...')

    activeTrackerIdRef.current = trackGeneration({
      module: 'learning',
      type: 'ollama_stream',
      prompt: `${topic.trim()} niveau ${level}`,
      startedAt: Date.now(),
    })

    abortRef.current?.abort()
    abortRef.current = new AbortController()

    try {
      await executeWithRuntime({
        module: 'learning',
        title: 'Generation cours academie',
        services: ['ollama'],
        prepare: async ({ setPhase }) => {
          await preparePack(setPhase)
        },
        ollamaModel: activeModel,
        job: async ({ setPhase }) => {
          const preparedContext = contextFiles.length > 0 ? await prepareContextFiles(contextFiles) : []
          const taskContext = await prepareTaskIntelligence({
            module: 'learning',
            prompt: `${topic} niveau ${level}`,
            model: preparedContext.some((file) => file.imageBase64) ? visionModel : activeModel,
            files: preparedContext,
            setPhase,
            phaseBase: 44,
            phaseSpan: 18,
          })

          if (taskContext.clarificationQuestion) {
            setPhase('Clarification utilisateur requise avant redaction du cours.', 56)
            const userAnswer = await new Promise<string | null>((resolve) => {
              setClarification({ question: taskContext.clarificationQuestion!, onRespond: resolve })
            })
            setClarification(null)
            if (userAnswer) {
              taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nPrecision utilisateur: ${userAnswer}`
            }
          }

          setPhase('Recherche de sources factuelles (Wikipedia + web)...', 58)
          setStatus('Ancrage du cours sur sources verifiees...')
          const research = await researchLearningTopic(topic.trim(), level)
          if (research.hasExternalSources) {
            setCourseSources(research.sources)
            setStatus(`Sources: ${summarizeSourcesForUI(research.sources)}${research.academicIntent.isExamFocus ? ` · Mode examen ${research.academicIntent.level}` : ''}`)
          }

          // v83: cours BAC enrichment - meme principe que v80 sur flashcards.
          // Quand isExamFocus, on rapatrie 4 sujets BAC reels via bac_resources
          // pour caler le format/progression/niveau du cours sur les annales
          // au lieu d en fabriquer un by-vibes.
          let bacEnrichmentBlock: string | null = null
          if (research.academicIntent.isExamFocus) {
            setPhase('Recuperation sujets BAC officiels (ecebac.fr)...', 62)
            try {
              const { buildBacEnrichment } = await import('../../services/bacResources')
              bacEnrichmentBlock = await buildBacEnrichment(`${topic} ${level}`.trim(), 4)
            } catch {
              // best-effort
            }
          }

          setPhase('Redaction du cours detaille...', 66)
          setStatus('Le cours se redige en direct.')

          // Historique: inclure les tours precedents pour continuite du cours
          const historyMessages = getRecentMessages('learning', 6).map((msg) => ({
            role: msg.role as 'user' | 'assistant',
            content: msg.content,
          }))

          const userContent = [
            `Sujet: ${taskContext.enrichedPrompt}`,
            `Niveau demande par l utilisateur: ${level}`,
            `Niveau academique detecte: ${research.academicIntent.level} (profondeur ${research.academicIntent.depth}${research.academicIntent.isExamFocus ? ', preparation d examen' : ''}).`,
            'Le cours doit etre exploitable, progressif et precis.',
            'Reprends les definitions, dates et formules directement des sources fournies quand elles existent.',
            'Si une affirmation n est appuyee par aucune source, indique-le clairement entre parentheses (ex: connaissance generale).',
            research.academicIntent.isExamFocus
              ? 'MODE EXAMEN ACTIF: inclure les sections ## Exercices types avec corriges, ## Attendus de l epreuve, ## Annales, ## Checklist jour J, et AU MOINS 3 exercices types entierement corriges.'
              : 'MODE COURS CLASSIQUE: inclure quand meme au moins 2 exercices corriges pour ancrer les notions.',
          ].join('\n')

          // Enregistrer le tour utilisateur
          pushMessage('learning', { role: 'user', content: userContent })

          const courseChunks: string[] = []
          // v82lm: academic course generation with research+exam enrichment
          // and BAC annales context produces a heavy first prompt (often
          // >6k tokens of system context). On a vision model with cold start
          // through the Cloudflare tunnel, TTFB can exceed 90s. Match the
          // parcours-bac fix to keep academic conversations from aborting.
          await ollamaChatStream(
            activeModel,
            [
              { role: 'system', content: buildLearningSystemPrompt('course', { academicIntent: research.academicIntent }) },
              ...(research.contextBlock
                ? [{ role: 'system' as const, content: research.contextBlock }]
                : []),
              ...(research.examContextBlock
                ? [{ role: 'system' as const, content: research.examContextBlock }]
                : []),
              ...(bacEnrichmentBlock
                ? [{ role: 'system' as const, content: bacEnrichmentBlock }]
                : []),
              ...historyMessages,
              {
                role: 'user',
                content: userContent,
                images: preparedContext.flatMap((file) => file.imageBase64 ? [file.imageBase64] : []),
              },
            ],
            (token) => {
              courseChunks.push(token)
              // 400ms-throttled setState: buffer tokens, flush periodically.
              courseBufferRef.current.push(token)
              scheduleCourseFlush()
            },
            () => undefined,
            { signal: abortRef.current?.signal ?? undefined, firstByteTimeoutMs: 240_000 },
          )
          // Stream closed: cancel any pending timer and flush the tail so
          // the last characters land in the UI without a 400ms delay.
          if (courseTimerRef.current !== null) {
            clearTimeout(courseTimerRef.current)
            courseTimerRef.current = null
          }
          flushCourseBuffer()
          const fullCourse = courseChunks.join('')

          // Enregistrer la reponse pour continuite
          pushMessage('learning', { role: 'assistant', content: fullCourse })

          // Auto-summary: first 3 non-empty lines
          const summary = fullCourse.split('\n').filter(Boolean).slice(0, 3).join(' ').slice(0, 280)
          setCourseSummary(summary)
          const newEntry: SavedCourse = {
            id: `course-${Date.now()}`,
            topic: topic.trim(),
            level,
            summary,
            content: fullCourse,
            date: Date.now(),
          }
          setSavedCourses((previous) => {
            const updated = [newEntry, ...previous.slice(0, 19)]
            localStorage.setItem(COURSES_STORAGE_KEY, JSON.stringify(updated))
            return updated
          })

          setPhase('Verification finale du cours...', 88)
          setStatus('Cours finalise et pret a etre relu.')
          if (lessonContext) {
            markCourseRead(lessonContext.pathId, lessonContext.nodeIndex)
          }
        },
      })

      if (activeTrackerIdRef.current) {
        completeGeneration(activeTrackerIdRef.current, {
          resultFilename: topic ? `cours sur ${topic.slice(0, 80)}` : undefined,
        })
        activeTrackerIdRef.current = null
      }
    } catch (error) {
      const errMsg = getErrorMessage(error, 'Echec de generation du cours.')
      if (activeTrackerIdRef.current) {
        failGeneration(activeTrackerIdRef.current, errMsg)
        activeTrackerIdRef.current = null
      }
      setStatus(errMsg)
    } finally {
      setIsLoading(false)
    }
  }, [activeModel, contextFiles, executeWithRuntime, level, preparePack, topic, visionModel, trackGeneration, completeGeneration, failGeneration])

  const exportMarkdown = useCallback(() => {
    if (!courseContent) return
    const blob = new Blob([`# ${topic}\n\n${courseContent}`], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `cours-${topic.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 40)}.md`
    anchor.click()
    URL.revokeObjectURL(url)
  }, [courseContent, topic])

  const deleteSavedCourse = useCallback((id: string) => {
    setSavedCourses((previous) => {
      const updated = previous.filter((c) => c.id !== id)
      localStorage.setItem(COURSES_STORAGE_KEY, JSON.stringify(updated))
      return updated
    })
  }, [])

  return (
    <div className="space-y-4 animate-fade-in">
      <ClarificationDialog request={clarification} />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_14rem]">
        <div className="glass rounded-2xl p-5">
          <label className="block text-xs text-aurora-text-dim">Sujet du cours</label>
          <div className="mt-2 flex items-center gap-2">
            <input
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              placeholder="Ex: reseaux neuronaux, photographie argentique, fiscalite micro-entreprise..."
              className="flex-1 rounded-xl border border-aurora-border bg-aurora-surface-2 px-4 py-3 text-sm text-aurora-text outline-none focus:border-aurora-accent/50"
              onKeyDown={(event) => event.key === 'Enter' && void generateCourse()}
            />
            <VoicePushToTalk
              onTranscript={(text) => setTopic((prev) => (prev?.trim() ? `${prev} ${text}` : text))}
              label="Dicter le sujet du cours"
              size={40}
            />
          </div>
          <div className="mt-4">
            <ContextFilesField
              files={contextFiles}
              onFilesChange={setContextFiles}
              accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.md,.json,.csv,.tsv,.xlsx,.xls,.xlsm"
              hint="Ajoute PDF natifs, images, notes ou tableurs pour enrichir le cours."
            />
          </div>
        </div>

        <div className="glass rounded-2xl p-5">
          <label className="block text-xs text-aurora-text-dim">Niveau vise</label>
          <select
            value={level}
            onChange={(event) => setLevel(event.target.value)}
            className="mt-2 w-full rounded-xl border border-aurora-border bg-aurora-surface-2 px-4 py-3 text-sm text-aurora-text outline-none"
          >
            <option value="debutant">Debutant</option>
            <option value="intermediaire">Intermediaire</option>
            <option value="avance">Avance</option>
          </select>
        </div>
      </div>

      <ModuleAssetPackCard pack={assetPack} />

      <div className="glass rounded-2xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <p className="text-sm text-aurora-text">{status}</p>
            {isLoading && (
              <button
                onClick={() => { abortRef.current?.abort(); abortRef.current = null }}
                className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/20 transition-colors"
              >
                ✕ Arrêter
              </button>
            )}
          </div>
          <button
            onClick={() => void generateCourse()}
            disabled={!topic.trim() || isLoading}
            className="rounded-2xl gradient-accent px-5 py-3 text-sm font-medium text-white disabled:opacity-60"
          >
            {isLoading ? 'Generation...' : 'Generer le cours'}
          </button>
        </div>
      </div>

      <div className="glass rounded-2xl p-6">
        {courseContent ? (
          <>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-aurora-text-dim">Contenu du cours</p>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-aurora-text-dim">{courseContent.split(/\s+/).filter(Boolean).length} mots · ~{Math.max(1, Math.round(courseContent.split(/\s+/).length / 200))} min</span>
                <button
                  onClick={copyCourse}
                  className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs transition-colors ${
                    copyFeedback === 'copied'
                      ? 'border-aurora-green/40 bg-aurora-green/10 text-aurora-green'
                      : 'border-aurora-border/50 bg-aurora-surface-2 text-aurora-text-dim hover:text-aurora-text'
                  }`}
                >
                  {copyFeedback === 'copied' ? <Check size={13} /> : <Shuffle size={13} />}
                  <span>{copyFeedback === 'copied' ? 'Copie !' : 'Copier'}</span>
                </button>
                <button
                  onClick={exportMarkdown}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/50 bg-aurora-surface-2 px-3 py-1.5 text-xs text-aurora-text-dim hover:text-aurora-text transition-colors"
                >
                  <Download size={13} />
                  <span>Exporter .md</span>
                </button>
              </div>
            </div>

            <div className="mb-3">
              <ReadingProgress targetRef={contentRef} />
            </div>

            {courseSummary && !isLoading && (
              <div className="mb-4 rounded-xl border border-aurora-accent/20 bg-aurora-accent/8 px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-aurora-accent/70">Resume auto</p>
                <p className="mt-1 text-xs leading-relaxed text-aurora-text-dim">{courseSummary}</p>
              </div>
            )}
            {courseSources.length > 0 && (
              <div className="mb-4">
                <SourcesPanel sources={courseSources} open={showCourseSources} onToggle={() => setShowCourseSources((v) => !v)} />
              </div>
            )}

            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_14rem]">
              <div
                ref={contentRef}
                className="max-h-[70vh] overflow-y-auto pr-2"
              >
                <MarkdownPro content={courseContent} idPrefix={`course-${savedCourses.length}`} />
                {isLoading && (
                  <span className="ml-1 inline-block h-4 w-1.5 animate-aurora-pulse rounded-sm bg-aurora-accent" />
                )}
              </div>
              {toc.length > 1 && (
                <aside className="hidden lg:block">
                  <div className="sticky top-2 rounded-xl border border-aurora-border/40 bg-aurora-surface-2/70 p-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-aurora-text-dim">Sommaire</p>
                    <nav className="mt-2 flex max-h-[60vh] flex-col gap-1 overflow-y-auto text-[11px]">
                      {toc.map((entry) => {
                        const isActive = entry.id === activeHeadingId
                        return (
                          <button
                            key={entry.id}
                            onClick={() => {
                              const target = contentRef.current?.querySelector(`#${entry.id}`)
                              if (target && contentRef.current) {
                                const topOffset = (target as HTMLElement).offsetTop - 8
                                contentRef.current.scrollTo({ top: topOffset, behavior: 'smooth' })
                              }
                            }}
                            className={`relative text-left transition-colors ${
                              entry.level === 3 ? 'pl-4' : 'pl-2'
                            } ${isActive ? 'font-semibold text-aurora-accent' : 'text-aurora-text-dim hover:text-aurora-accent'}`}
                          >
                            {isActive && (
                              <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-aurora-accent" aria-hidden />
                            )}
                            {entry.label}
                          </button>
                        )
                      })}
                    </nav>
                  </div>
                </aside>
              )}
            </div>
            <AskAboutContentBox
              className="mt-4"
              context={courseContent}
              subject={topic}
              model={activeModel}
              placeholder="Ex: peux-tu reformuler la partie sur... / donne un exemple supplementaire pour..."
            />
          </>
        ) : (
          <div className="grid min-h-[18rem] place-items-center text-center">
            <div>
              <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-[1.6rem] border border-aurora-border bg-aurora-surface-2">
                <BookOpen size={28} className="text-aurora-text-dim" />
              </div>
              <p className="mt-4 text-sm text-aurora-text-dim">
                Le cours detaille apparaitra ici avec resume, sections, exemples et revision.
              </p>
            </div>
          </div>
        )}
      </div>

      {savedCourses.length > 0 && (
        <div className="glass rounded-2xl p-5">
          <button
            onClick={() => setShowSavedList((v) => !v)}
            className="flex w-full items-center gap-2 text-sm font-medium text-aurora-text"
          >
            <BookOpen size={15} />
            <span>Mes cours ({savedCourses.length})</span>
            <ChevronDown size={13} className={`ml-auto transition-transform ${showSavedList ? 'rotate-180' : ''}`} />
          </button>
          <AnimatePresence>
            {showSavedList && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 space-y-2 overflow-hidden"
              >
                {savedCourses.map((course) => (
                  <div
                    key={course.id}
                    className="flex items-start justify-between gap-3 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-4 py-3"
                  >
                    <button
                      onClick={() => { setCourseContent(course.content); setCourseSummary(course.summary) }}
                      className="min-w-0 text-left"
                    >
                      <p className="truncate text-sm text-aurora-text">{course.topic}</p>
                      <p className="mt-0.5 text-[11px] text-aurora-text-dim">
                        {course.level} — {new Date(course.date).toLocaleDateString('fr-FR')}
                      </p>
                    </button>
                    <button
                      onClick={() => deleteSavedCourse(course.id)}
                      className="shrink-0 rounded-lg p-1.5 text-aurora-text-dim hover:text-aurora-red transition-colors"
                      title="Supprimer"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}

export default CoursesPanel
