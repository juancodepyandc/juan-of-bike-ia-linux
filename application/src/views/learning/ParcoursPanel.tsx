import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLearningSessionStore, type LearnerProfile } from '../../stores/learningSessionStore'
import type { ReactNode, RefObject } from 'react'
import AcademicIntakeWizard from './AcademicIntakeWizard'
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

import type { Tab, LessonRef, LearningPathNode } from './types'
import { buildLearningSystemPrompt, extractJsonArray } from './utils'
import { SourcesPanel } from './sharedComponents'

function ParcoursPanel({
  recoveryPrompt,
  clearRecoveryPrompt,
  onLaunchStep,
  onExitLesson,
}: {
  recoveryPrompt?: string | null
  clearRecoveryPrompt?: () => void
  onLaunchStep?: (
    topic: string,
    target: Extract<Tab, 'quiz' | 'courses' | 'fiches'>,
    lessonRef?: LessonRef,
  ) => void
  onExitLesson?: () => void
}) {
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
  const { addLearningPath, learningPaths } = useGamificationStore()
  const progressMap = useLessonProgressStore((state) => state.progress)
  const resetPath = useLessonProgressStore((state) => state.resetPath)
  // Restore session state persisted across restarts
  const _savedParcours = useLearningSessionStore((s) => s.parcours)
  const saveParcours = useLearningSessionStore((s) => s.saveParcours)
  const [goal, setGoal] = useState(_savedParcours?.goal ?? '')
  const [parcours, setParcours] = useState<LearningPathNode[]>(_savedParcours?.parcours ?? [])
  const [activePathId, setActivePathId] = useState<string | null>(_savedParcours?.activePathId ?? null)
  const [parcoursSources, setParcoursSources] = useState<LearningSource[]>(_savedParcours?.sources ?? [])
  // v82nu: profil utilisateur persiste pour la generation + l offre "meme format"
  const [profile, setProfile] = useState<LearnerProfile>(_savedParcours?.profile ?? {})
  const [wizardOpen, setWizardOpen] = useState(false)
  // v82nu: extraits PDF (concept hint) deduits dynamiquement quand le user
  // ajoute des fichiers, pour pre-remplir l etape 4 du wizard.
  const [extractedConceptHint, setExtractedConceptHint] = useState<string>('')
  const [showParcoursSources, setShowParcoursSources] = useState(false)
  const [expandedNodeIndex, setExpandedNodeIndex] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState('Aucun parcours genere.')
  const [clarification, setClarification] = useState<ClarificationRequest | null>(null)
  // v82lm: elapsed-time tick during parcours generation so the user sees the
  // app is alive when the model is in cold-start (10-180s on vision models).
  const [genStartedAt, setGenStartedAt] = useState<number | null>(null)
  const [genNow, setGenNow] = useState<number>(Date.now())
  useEffect(() => {
    if (!isLoading || genStartedAt === null) return
    const id = window.setInterval(() => setGenNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [isLoading, genStartedAt])
  const elapsedSec = genStartedAt === null ? 0 : Math.max(0, Math.floor((genNow - genStartedAt) / 1000))
  const activeModel = contextFiles.length > 0 ? visionModel : mainModel

  // Persist session state so it survives app restarts
  useEffect(() => {
    if (goal || parcours.length > 0 || Object.keys(profile).length > 0) {
      saveParcours({ goal, parcours, activePathId, sources: parcoursSources, profile })
    }
  }, [goal, parcours, activePathId, parcoursSources, profile, saveParcours])

  // v82nu: dès que l utilisateur ajoute des PDFs/textes, on pre-extrait pour
  // proposer un hint de concepts dans le wizard. Best-effort : si l extraction
  // echoue (offline, fichier corrompu), on retombe a vide.
  useEffect(() => {
    let cancelled = false
    if (contextFiles.length === 0) {
      setExtractedConceptHint('')
      return
    }
    void (async () => {
      try {
        const prepared = await prepareContextFiles(contextFiles)
        if (cancelled) return
        // Heuristique simple : on prend les 6 premieres lignes non vides de
        // chaque document pour donner un teaser au user. Pas d appel LLM ici.
        const teaser: string[] = []
        for (const file of prepared) {
          const lines = (file.extractedText ?? '')
            .split('\n')
            .map((l) => l.trim())
            .filter((l) => l.length > 8 && l.length < 220)
          for (const line of lines.slice(0, 6)) teaser.push(`- ${line}`)
        }
        setExtractedConceptHint(teaser.slice(0, 14).join('\n'))
      } catch {
        if (!cancelled) setExtractedConceptHint('')
      }
    })()
    return () => { cancelled = true }
  }, [contextFiles])


  const getNodeProgress = useCallback(
    (nodeIndex: number) => {
      if (!activePathId) return null
      return progressMap[`${activePathId}::${nodeIndex}`] ?? null
    },
    [activePathId, progressMap],
  )

  const isNodeComplete = useCallback(
    (nodeIndex: number) => {
      const progress = getNodeProgress(nodeIndex)
      return Boolean(progress?.courseRead && progress?.fichesSeen && progress?.quizPassed)
    },
    [getNodeProgress],
  )

  const isNodeUnlocked = useCallback(
    (nodeIndex: number) => {
      if (nodeIndex === 0) return true
      return isNodeComplete(nodeIndex - 1)
    },
    [isNodeComplete],
  )

  useEffect(() => {
    onExitLesson?.()
    // Exit lesson context whenever the parcours panel mounts/reset
  }, [onExitLesson])

  // Consume recovery prompt to pre-fill the goal
  useEffect(() => {
    if (recoveryPrompt) {
      setGoal(recoveryPrompt)
      clearRecoveryPrompt?.()
    }
  }, [recoveryPrompt, clearRecoveryPrompt])

  const generateParcours = useCallback(async (overrideProfile?: LearnerProfile) => {
    const activeProfile: LearnerProfile = overrideProfile ?? profile
    // v82nu: si pas de goal mais on a des PDFs + concepts, on synthetise un goal
    // par defaut depuis le profil pour ne JAMAIS bloquer le user.
    let workingGoal = goal.trim()
    if (!workingGoal) {
      if (contextFiles.length > 0 && activeProfile.focusConcepts) {
        workingGoal = `Maitriser les notions cles : ${activeProfile.focusConcepts.split(/\n|,/).slice(0, 5).join(', ')}`
      } else {
        return
      }
    }

    setIsLoading(true)
    setParcoursSources([])
    setExpandedNodeIndex(null)
    setStatus('Preparation du parcours...')
    setGenStartedAt(Date.now())
    setGenNow(Date.now())

    activeTrackerIdRef.current = trackGeneration({
      module: 'learning',
      type: 'ollama_stream',
      prompt: workingGoal,
      startedAt: Date.now(),
    })

    abortRef.current?.abort()
    abortRef.current = new AbortController()

    try {
      await executeWithRuntime({
        module: 'learning',
        title: 'Generation parcours academie',
        services: ['ollama'],
        prepare: async ({ setPhase }) => {
          await preparePack(setPhase)
        },
        ollamaModel: activeModel,
        job: async ({ setPhase }) => {
          const preparedContext = contextFiles.length > 0 ? await prepareContextFiles(contextFiles) : []
          const taskContext = await prepareTaskIntelligence({
            module: 'learning',
            prompt: workingGoal,
            model: preparedContext.some((file) => file.imageBase64) ? visionModel : activeModel,
            files: preparedContext,
            setPhase,
            phaseBase: 48,
            phaseSpan: 18,
          })

          if (taskContext.clarificationQuestion) {
            setPhase('Clarification utilisateur requise avant construction du parcours.', 60)
            const userAnswer = await new Promise<string | null>((resolve) => {
              setClarification({ question: taskContext.clarificationQuestion!, onRespond: resolve })
            })
            setClarification(null)
            if (userAnswer) {
              taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nPrecision utilisateur: ${userAnswer}`
            }
          }

          setPhase('Recherche de sources factuelles (Wikipedia + web)...', 60)
          // v82nu: enrichir la query de recherche avec le niveau scolaire et
          // les concepts cibles pour mieux ancrer les sources externes.
          const researchExtras = [
            activeProfile.schoolLevel ?? '',
            activeProfile.focusConcepts ?? '',
          ].filter(Boolean).join(' ')
          const research = await researchLearningTopic(workingGoal, researchExtras)
          if (research.hasExternalSources) {
            setParcoursSources(research.sources)
          }

          setPhase('Construction du parcours progressif...', 72)

          // v82nu: PRIORITE ABSOLUE aux fichiers utilisateur. Le user a
          // explicitement demande "ils sont prioritaires a la comprehension".
          // On construit donc un bloc PDF dedie place AVANT tout contexte web,
          // et on rappelle dans le prompt user que les PDFs sont la verite.
          const userDocsBlock = preparedContext
            .map((f, i) => {
              const head = `[USER-DOC ${i + 1}] ${f.name}`
              const body = (f.extractedText ?? '').slice(0, 8000).trim()
              return body ? `${head}\n${body}` : ''
            })
            .filter(Boolean)
            .join('\n\n---\n\n')

          const userDocsSystemBlock = userDocsBlock
            ? [
                'DOCUMENTS UTILISATEUR — PRIORITE ABSOLUE.',
                'Les blocs ci-dessous sont fournis par l apprenant. Ils representent SA matiere, le programme reel auquel il sera evalue.',
                'Tu DOIS aligner le parcours, le vocabulaire, les exemples et les exercices sur ces documents AVANT toute autre source.',
                'Si une source externe (Wikipedia, web) contredit ces documents, IGNORE-LA et fais confiance aux documents utilisateur.',
                '',
                userDocsBlock,
              ].join('\n')
            : ''

          // v82nu: profile-derived steering — duree, format, mode de travail,
          // date de l eval. On le passe en system message pour que le modele
          // calibre les exercices et le test final.
          const profileBlock: string[] = []
          if (activeProfile.workStyle) profileBlock.push(`Mode de travail prefere : ${activeProfile.workStyle}.`)
          if (activeProfile.examFormat) profileBlock.push(`Format de l epreuve : ${activeProfile.examFormat}.`)
          if (activeProfile.examDurationMinutes) profileBlock.push(`Duree de l epreuve cible : ${activeProfile.examDurationMinutes} min.`)
          if (activeProfile.examDate) profileBlock.push(`Date de l epreuve : ${activeProfile.examDate}.`)
          if (activeProfile.schoolLevel) profileBlock.push(`Niveau scolaire utilisateur : ${activeProfile.schoolLevel}.`)
          if (activeProfile.focusConcepts) profileBlock.push(`Concepts a maitriser en priorite : ${activeProfile.focusConcepts}.`)
          // v83a : si l apprenant a choisi le format "jeu", le parcours doit etre
          // ludique de bout en bout — pas un QCM deguise.
          const isGameFormat = activeProfile.examFormat === 'jeu'
          const profileSystemBlock = profileBlock.length > 0
            ? [
                'PROFIL APPRENANT — directives obligatoires :',
                ...profileBlock.map((l) => `- ${l}`),
                '- Adapte les exercices au mode de travail (audio = podcasts/oral, visuel = schemas, lecture = QCM/fiches, pratique = redaction/manipulation).',
                '- Si une duree d epreuve est fixee, l examen blanc final DOIT correspondre exactement a cette duree (pas plus, pas moins).',
                isGameFormat
                  ? [
                      '- FORMAT JEU EDUCATIF (impose) : transforme le parcours en aventure pedagogique, PAS un simple QCM.',
                      '  - Donne au parcours un fil narratif (enquete, escape game, mission, expedition...) ou chaque etape est une "salle"/"manche"/"niveau".',
                      '  - Chaque etape mele plusieurs micro-formats : enigme, manipulation, dessin/schema a completer, mini-defi de calcul, question ouverte courte, choix a embranchement. Varie a chaque etape.',
                      '  - Introduit des elements de jeu : indices a debloquer, "cles"/points gagnes, palier de difficulte croissant, twist a mi-parcours.',
                      '  - La derniere etape est le "boss final" : un defi de synthese qui reutilise tout ce qui precede.',
                      "  - Le savoir reste rigoureux et conforme au programme : le jeu est l emballage, pas un pretexte a diluer le contenu.",
                    ].join('\n')
                  : '- Si un format est fixe (QCM/dissertation/oral/mixte), les questions du parcours doivent suivre ce format en majorite.',
              ].join('\n')
            : ''

          const rawChunks: string[] = []
          // v82lm: academic generations on a vision model + research context
          // routinely exceed the 90s default TTFB on first call (cold start +
          // long system prompt + images). 4 min mirrors the parcours-bac fix
          // from v82lg so the user never sees a misleading AbortError.
          await ollamaChatStream(
            activeModel,
            [
              { role: 'system', content: buildLearningSystemPrompt('path', { academicIntent: research.academicIntent }) },
              // v82nu: doc utilisateur EN PREMIER pour la priorite cognitive
              ...(userDocsSystemBlock ? [{ role: 'system' as const, content: userDocsSystemBlock }] : []),
              ...(profileSystemBlock ? [{ role: 'system' as const, content: profileSystemBlock }] : []),
              ...(research.contextBlock
                ? [{ role: 'system' as const, content: `(Sources externes complementaires, secondaires aux documents utilisateur)\n${research.contextBlock}` }]
                : []),
              ...(research.examContextBlock
                ? [{ role: 'system' as const, content: research.examContextBlock }]
                : []),
              {
                role: 'user',
                content: [
                  `Objectif: ${taskContext.enrichedPrompt}`,
                  `Niveau academique detecte: ${research.academicIntent.level} (profondeur ${research.academicIntent.depth}${research.academicIntent.isExamFocus ? ', mode preparation examen' : ''}).`,
                  userDocsBlock ? 'Les documents utilisateur (USER-DOC 1, 2, ...) sont la verite. Calque le parcours dessus.' : '',
                  activeProfile.examDurationMinutes
                    ? (isGameFormat
                        ? `La derniere etape est le "BOSS FINAL" : un grand defi de synthese ludique d environ ${activeProfile.examDurationMinutes} min qui reutilise tout le parcours.`
                        : `La derniere etape doit etre un EXAMEN BLANC d exactement ${activeProfile.examDurationMinutes} min, format ${activeProfile.examFormat ?? 'mixte'}.`)
                    : '',
                  'Format JSON strict:',
                  '[{"title":"...","objective":"...","deliverable":"...","estimatedMinutes":45,"resources":["..."]}]',
                ].filter(Boolean).join('\n'),
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

          setPhase('Validation du parcours et des etapes...', 86)
          const steps = extractJsonArray<{
            title: string
            objective?: string
            deliverable?: string
            estimatedMinutes?: number
            resources?: string[]
          }>(raw)
          const examFocus = Boolean(research.academicIntent?.isExamFocus) || Boolean(activeProfile.examDurationMinutes)
          const nodes: LearningPathNode[] = steps.map((step, index) => {
            const isLast = index === steps.length - 1
            const isExamFinal = examFocus && isLast
            // v82nu: si l utilisateur a fixe une duree d examen via le wizard,
            // on la verrouille ici (priorite sur ce que le modele a propose).
            const examDuration = isExamFinal
              ? (activeProfile.examDurationMinutes
                  ?? (step.estimatedMinutes && step.estimatedMinutes >= 60 ? Math.min(240, step.estimatedMinutes) : 120))
              : undefined
            return {
              title: isExamFinal ? `Examen blanc — ${step.title}` : step.title,
              status: index === 0 ? 'active' : 'todo',
              objective: step.objective,
              deliverable: step.deliverable,
              estimatedMinutes: typeof step.estimatedMinutes === 'number' ? step.estimatedMinutes : undefined,
              resources: Array.isArray(step.resources) ? step.resources.slice(0, 4) : undefined,
              isExamFinal,
              examDurationMinutes: examDuration,
            }
          })

          setParcours(nodes)
          const newPathId = `path-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
          setActivePathId(newPathId)
          // v82nu: la session s ouvre AUTOMATIQUEMENT a l etape 1, pas de
          // bouton "voir le parcours" intermediaire. C est la demande #4 du
          // user : tout sur la meme page, immediatement actionnable.
          setExpandedNodeIndex(0)
          addLearningPath({
            id: newPathId,
            title: workingGoal,
            nodes,
          })
          // v82nu: sauvegarde profile + goal updated dans le store
          if (overrideProfile) setProfile(overrideProfile)
          if (workingGoal !== goal) setGoal(workingGoal)
          setStatus('Parcours genere — la premiere etape est ouverte ci-dessous.')
        },
      })

      if (activeTrackerIdRef.current) {
        completeGeneration(activeTrackerIdRef.current, {})
        activeTrackerIdRef.current = null
      }
    } catch (error) {
      const errMsg = getErrorMessage(error, 'Echec de generation du parcours.')
      if (activeTrackerIdRef.current) {
        failGeneration(activeTrackerIdRef.current, errMsg)
        activeTrackerIdRef.current = null
      }
      setStatus(errMsg)
    } finally {
      setIsLoading(false)
      setGenStartedAt(null)
    }
  }, [activeModel, addLearningPath, contextFiles, executeWithRuntime, goal, preparePack, profile, visionModel, trackGeneration, completeGeneration, failGeneration])

  // v82lm: compute the active step (first non-complete node from index 0) so
  // we can render a global "Étape X / N" banner that's always visible even
  // when the parcours node list is collapsed. Avoids the user needing to
  // hunt down where they are in the parcours.
  const activeStepIndex = useMemo(() => {
    if (parcours.length === 0) return -1
    for (let i = 0; i < parcours.length; i++) {
      if (!isNodeComplete(i)) return i
    }
    return parcours.length // all done
  }, [parcours, isNodeComplete])
  const completedCount = useMemo(
    () => parcours.reduce((n, _, idx) => n + (isNodeComplete(idx) ? 1 : 0), 0),
    [parcours, isNodeComplete],
  )

  return (
    <div className="space-y-4 animate-fade-in">
      <ClarificationDialog request={clarification} />
      <AcademicIntakeWizard
        open={wizardOpen}
        initial={profile}
        suggestedConcepts={extractedConceptHint}
        onCancel={() => setWizardOpen(false)}
        onComplete={(p) => {
          setWizardOpen(false)
          setProfile(p)
          // v82nu: lance la generation immediatement avec le profil collecte
          void generateParcours(p)
        }}
      />
      <div className="glass rounded-2xl p-5">
        <div className="flex flex-col gap-4 lg:flex-row">
          <div className="flex-1 space-y-4">
            <div className="flex items-center gap-2">
              <input
                value={goal}
                onChange={(event) => setGoal(event.target.value)}
                placeholder="Ex: devenir autonome en Python pour l automatisation et l analyse de donnees"
                className="flex-1 rounded-xl border border-aurora-border bg-aurora-surface-2 px-4 py-3 text-sm text-aurora-text outline-none focus:border-aurora-accent/50"
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && (goal.trim() || contextFiles.length > 0) && !isLoading) {
                    setWizardOpen(true)
                  }
                }}
              />
              <VoicePushToTalk
                onTranscript={(t) => setGoal((prev) => (prev?.trim() ? `${prev} ${t}` : t))}
                label="Dicter l'objectif d'apprentissage"
                size={40}
              />
            </div>
            <ContextFilesField
              files={contextFiles}
              onFilesChange={setContextFiles}
              accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.md,.json,.csv,.tsv,.xlsx,.xls,.xlsm"
              hint="Ajoute programmes, PDF, images ou tableurs pour construire le parcours."
            />

            <ModuleAssetPackCard pack={assetPack} />
          </div>
          <div className="flex flex-col gap-2">
            <button
              onClick={() => {
                // v82nu: ouvre toujours le wizard avant la generation (sauf si
                // l utilisateur regenere avec EXACTEMENT le meme profil — voir
                // bouton "Meme format que la derniere fois" plus bas).
                if (!goal.trim() && contextFiles.length === 0) return
                setWizardOpen(true)
              }}
              disabled={(!goal.trim() && contextFiles.length === 0) || isLoading}
              className="rounded-2xl gradient-accent px-6 py-4 text-base font-semibold text-white shadow-lg shadow-aurora-accent/30 transition-all hover:shadow-xl hover:shadow-aurora-accent/50 disabled:opacity-60 disabled:shadow-none"
              title="Pose 4 questions rapides puis genere fiches + mind map + exos + test"
            >
              {isLoading ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 size={16} className="animate-spin" />
                  Génération… {elapsedSec}s
                </span>
              ) : (
                <span className="inline-flex items-center gap-2">
                  <Sparkles size={14} />
                  {parcours.length > 0 ? 'Régénérer le parcours' : 'Créer mon parcours'}
                </span>
              )}
            </button>
            {/* v82nu: raccourci "meme format que la derniere fois" si on a un
                profil sauvegarde — repond directement a la demande user
                "la prochaine fois est-ce qu on veut la meme chose". */}
            {!isLoading && Object.keys(profile).length > 0 && (
              <button
                onClick={() => void generateParcours(profile)}
                disabled={!goal.trim() && contextFiles.length === 0}
                className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-[11px] font-medium text-emerald-300 hover:bg-emerald-500/20 transition-colors disabled:opacity-40"
                title="Reutilise le profil precedent : mode, format, duree"
              >
                Meme format que la derniere fois
              </button>
            )}
            {isLoading && (
              <button
                onClick={() => { abortRef.current?.abort(); abortRef.current = null }}
                className="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-2 text-xs font-medium text-red-400 hover:bg-red-500/20 transition-colors"
              >
                Annuler la generation
              </button>
            )}
          </div>
        </div>
        {/* v82lm: status row now bigger and shows elapsed clock when streaming */}
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className={isLoading ? 'text-aurora-accent' : 'text-aurora-text-dim'}>
            {status}
          </span>
          {isLoading && elapsedSec > 5 && (
            <span className="rounded-full bg-aurora-surface-2 px-2 py-0.5 text-[10px] font-mono text-aurora-text-dim">
              ⏱ {elapsedSec}s — la première sortie peut prendre 30-180 s sur un modèle vision
            </span>
          )}
        </div>
        {/* v82nu: empty-state guide updated to reflect the new intake flow.
            The user lands here with a clear 4-step plan visible BEFORE click. */}
        {parcours.length === 0 && !isLoading && (
          <div className="mt-4 rounded-xl border border-aurora-border/40 bg-aurora-surface-2/40 p-3 text-[11px] text-aurora-text-dim">
            <p className="mb-2 font-semibold text-aurora-text">Comment ca marche</p>
            <ol className="space-y-1 list-decimal list-inside">
              <li><span className="font-medium text-aurora-text">Televerse tes documents</span> (PDFs, fiches, cours) — ils sont prioritaires sur la recherche web.</li>
              <li><span className="font-medium text-aurora-text">Decris ton objectif</span> et clique <em>Creer mon parcours</em>.</li>
              <li><span className="font-medium text-aurora-text">Reponds a 4 questions rapides</span> : mode de travail, format de l eval, duree, concepts cibles.</li>
              <li>L IA genere fiches + parcours + exos + <span className="text-orange-400">examen blanc</span> a la duree que tu as fixee. La premiere etape s ouvre direct ci-dessous.</li>
            </ol>
          </div>
        )}
        {/* v82nu: badge profil actif quand on a deja repondu au wizard, pour
            que le user voie clairement les parametres en cours. */}
        {parcours.length === 0 && !isLoading && Object.keys(profile).length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[10px]">
            <span className="text-aurora-text-dim">Profil enregistre :</span>
            {profile.workStyle && <span className="rounded-full border border-violet-400/30 bg-violet-500/10 px-2 py-0.5 text-violet-200">mode {profile.workStyle}</span>}
            {profile.examFormat === 'jeu'
              ? <span className="rounded-full border border-amber-400/40 bg-amber-500/15 px-2 py-0.5 text-amber-200">🎮 mode jeu / enquete</span>
              : profile.examFormat && <span className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-2 py-0.5 text-cyan-200">format {profile.examFormat}</span>}
            {profile.examDurationMinutes && <span className="rounded-full border border-emerald-400/30 bg-emerald-500/10 px-2 py-0.5 text-emerald-200">{profile.examDurationMinutes} min</span>}
            {profile.examDate && <span className="rounded-full border border-orange-400/30 bg-orange-500/10 px-2 py-0.5 text-orange-200">le {profile.examDate}</span>}
          </div>
        )}
      </div>

      {parcoursSources.length > 0 && (
        <SourcesPanel sources={parcoursSources} open={showParcoursSources} onToggle={() => setShowParcoursSources((v) => !v)} />
      )}

      {/* v82lm: persistent active-step banner — always visible when a parcours
          exists, so the user instantly sees where they are without scrolling. */}
      {parcours.length > 0 && activeStepIndex >= 0 && activeStepIndex < parcours.length && (
        <div className="rounded-2xl border border-aurora-accent/30 bg-aurora-accent/5 px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs">
              <span className="rounded-full bg-aurora-accent px-2 py-0.5 text-[10px] font-bold text-white">
                ÉTAPE {activeStepIndex + 1}/{parcours.length}
              </span>
              <span className="font-medium text-aurora-text truncate">
                {parcours[activeStepIndex].title}
              </span>
            </div>
            <button
              onClick={() => setExpandedNodeIndex(activeStepIndex)}
              className="rounded-full border border-aurora-accent/40 bg-aurora-accent/10 px-3 py-1 text-[11px] font-medium text-aurora-accent transition-colors hover:bg-aurora-accent/20"
            >
              Aller à l'étape →
            </button>
          </div>
          {parcours[activeStepIndex].objective && (
            <p className="mt-1.5 text-[11px] text-aurora-text-dim line-clamp-2">
              {parcours[activeStepIndex].objective}
            </p>
          )}
          <div className="mt-2 flex items-center gap-2 text-[10px] text-aurora-text-dim">
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-aurora-surface-2">
              <div
                className="h-full gradient-accent rounded-full transition-all"
                style={{ width: `${(completedCount / parcours.length) * 100}%` }}
              />
            </div>
            <span>{completedCount} / {parcours.length} terminées</span>
          </div>
        </div>
      )}
      {parcours.length > 0 && activeStepIndex === parcours.length && (
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-300">
          <span className="font-semibold">🎉 Parcours terminé</span> — toutes les étapes sont validées. Tu peux régénérer un nouveau parcours ou en charger un précédent.
        </div>
      )}

      {parcours.length > 0 && (
        <div className="glass rounded-2xl p-6">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h3 className="text-sm font-semibold gradient-text">Parcours actif</h3>
            <div className="flex items-center gap-3 text-[11px] text-aurora-text-dim">
              {(() => {
                const completedNodes = parcours.reduce(
                  (acc, _node, idx) => acc + (isNodeComplete(idx) ? 1 : 0),
                  0,
                )
                const completedPct = parcours.length === 0 ? 0 : (completedNodes / parcours.length) * 100
                return (
                  <>
                    <span>
                      Avancement: {completedNodes}/{parcours.length}
                    </span>
                    <div className="h-1.5 w-32 overflow-hidden rounded-full bg-aurora-surface-2">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${completedPct}%` }}
                        className="h-full gradient-accent rounded-full"
                      />
                    </div>
                    <span>
                      ~
                      {parcours.reduce((sum, node) => sum + (node.estimatedMinutes ?? 0), 0)} min
                    </span>
                    {activePathId && completedNodes > 0 && (
                      <button
                        onClick={() => {
                          if (confirm('Reinitialiser la progression de ce parcours ?')) {
                            resetPath(activePathId)
                          }
                        }}
                        className="text-aurora-text-dim hover:text-aurora-red transition-colors"
                        title="Reinitialiser la progression"
                      >
                        <RotateCcw size={12} />
                      </button>
                    )}
                  </>
                )
              })()}
            </div>
          </div>
          <div className="relative mt-5 space-y-3">
            <div className="pointer-events-none absolute left-[1.125rem] top-4 bottom-4 w-0.5 bg-gradient-to-b from-aurora-accent/60 via-aurora-accent/30 to-aurora-border/60" aria-hidden />
            {parcours.map((node, index) => {
              const isExpanded = expandedNodeIndex === index
              const complete = isNodeComplete(index)
              const unlocked = isNodeUnlocked(index)
              return (
                <div key={`${node.title}-${index}`} className="relative space-y-2">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => {
                        if (!unlocked) return
                        setExpandedNodeIndex((value) => (value === index ? null : index))
                      }}
                      className={`relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-transform hover:scale-105 ring-4 ring-aurora-surface ${
                        complete
                          ? 'bg-aurora-green/20 text-aurora-green'
                          : !unlocked
                            ? 'bg-aurora-surface-2 text-aurora-text-dim/60'
                            : isExpanded
                              ? 'gradient-accent text-white shadow-lg shadow-aurora-accent/40'
                              : 'bg-aurora-surface-2 text-aurora-text-dim'
                      }`}
                      title={!unlocked ? 'Etape verrouillee' : complete ? 'Etape validee' : 'Ouvrir cette etape'}
                    >
                      {complete ? (
                        <Check size={16} />
                      ) : !unlocked ? (
                        <span className="text-[10px]">🔒</span>
                      ) : (
                        <span className="text-xs font-semibold">{index + 1}</span>
                      )}
                    </button>
                    <button
                      onClick={() => setExpandedNodeIndex((value) => (value === index ? null : index))}
                      className={`flex-1 rounded-2xl px-4 py-3 text-left text-sm transition-all ${
                        node.status === 'active'
                          ? 'glass border border-aurora-accent/30 text-aurora-text'
                          : 'bg-aurora-surface-2 text-aurora-text-dim hover:text-aurora-text'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="flex items-center gap-2">
                          {node.isExamFinal && (
                            <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-widest" style={{ background: 'rgba(249,127,61,0.15)', color: '#f97f3d', border: '1px solid rgba(249,127,61,0.4)' }}>
                              <Swords size={9} /> Examen blanc
                            </span>
                          )}
                          {node.title}
                        </span>
                        <div className="flex items-center gap-2 text-[11px] text-aurora-text-dim">
                          {node.isExamFinal && node.examDurationMinutes ? (
                            <span className="inline-flex items-center gap-1 font-semibold" style={{ color: '#f97f3d' }}>
                              <Clock size={11} />
                              {node.examDurationMinutes} min
                            </span>
                          ) : typeof node.estimatedMinutes === 'number' && (
                            <span className="inline-flex items-center gap-1">
                              <Timer size={11} />
                              {node.estimatedMinutes} min
                            </span>
                          )}
                          <ChevronDown size={12} className={`transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                        </div>
                      </div>
                    </button>
                  </div>
                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="ml-12 overflow-hidden rounded-2xl border border-aurora-border/30 bg-aurora-surface-2/80 px-4 py-3 text-xs"
                      >
                        {node.objective && (
                          <div className="mb-2">
                            <p className="text-[10px] uppercase tracking-[0.2em] text-aurora-text-dim">Objectif</p>
                            <p className="mt-0.5 text-aurora-text">{node.objective}</p>
                          </div>
                        )}
                        {node.deliverable && (
                          <div className="mb-2">
                            <p className="text-[10px] uppercase tracking-[0.2em] text-aurora-text-dim">Livrable</p>
                            <p className="mt-0.5 text-aurora-text">{node.deliverable}</p>
                          </div>
                        )}
                        {node.resources && node.resources.length > 0 && (
                          <div className="mb-3">
                            <p className="text-[10px] uppercase tracking-[0.2em] text-aurora-text-dim">Ressources suggerees</p>
                            <ul className="mt-1 list-inside list-disc space-y-0.5 text-aurora-text-dim">
                              {node.resources.map((resource, resIndex) => (
                                <li key={`res-${index}-${resIndex}`}>{resource}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {onLaunchStep && activePathId && (
                          (() => {
                            const nodeProgress = getNodeProgress(index)
                            const unlocked = isNodeUnlocked(index)
                            const lessonTopic = `${goal} — ${node.title}`
                            const lessonRef: LessonRef = { pathId: activePathId, nodeIndex: index }
                            const stepItem = (
                              label: string,
                              icon: typeof BookOpen,
                              target: Extract<Tab, 'quiz' | 'courses' | 'fiches'>,
                              completed: boolean,
                              extra?: string,
                            ) => {
                              const Icon = icon
                              return (
                                <button
                                  disabled={!unlocked}
                                  onClick={() => onLaunchStep(lessonTopic, target, lessonRef)}
                                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] transition-colors ${
                                    !unlocked
                                      ? 'border-aurora-border/40 bg-aurora-surface-2/50 text-aurora-text-dim/60 cursor-not-allowed'
                                      : completed
                                        ? 'border-aurora-green/40 bg-aurora-green/10 text-aurora-green hover:bg-aurora-green/15'
                                        : 'border-aurora-border bg-aurora-surface-2 text-aurora-text-dim hover:text-aurora-accent hover:border-aurora-accent/40'
                                  }`}
                                >
                                  {completed ? <Check size={11} /> : <Icon size={11} />}
                                  <span>{label}</span>
                                  {extra && <span className="text-[9px] opacity-70">{extra}</span>}
                                </button>
                              )
                            }
                            const quizScoreLabel = nodeProgress?.quizScore != null
                              ? `${nodeProgress.quizScore}%`
                              : undefined
                            if (node.isExamFinal) {
                              return (
                                <div className="mt-2 border-t border-aurora-border/30 pt-3">
                                  <div className="rounded-xl p-4" style={{ background: 'linear-gradient(135deg, rgba(249,127,61,0.08), rgba(139,92,246,0.08))', border: '1px solid rgba(249,127,61,0.3)' }}>
                                    <p className="text-[11px] font-bold uppercase tracking-widest" style={{ color: '#f97f3d' }}>Examen blanc en conditions réelles</p>
                                    <p className="mt-1 text-xs text-aurora-text">Temps limité ({node.examDurationMinutes ?? 120} min), format de l'épreuve, corrigé détaillé en fin de session.</p>
                                    <button
                                      disabled={!unlocked}
                                      onClick={() => onLaunchStep(`[EXAMEN ${node.examDurationMinutes ?? 120}MIN] ${lessonTopic}`, 'quiz', lessonRef)}
                                      className="mt-3 w-full rounded-xl px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
                                      style={{ background: 'linear-gradient(135deg,#f97f3d,#8b5cf6)', boxShadow: '0 0 16px rgba(249,127,61,0.25)' }}
                                    >
                                      <Swords size={14} className="inline mr-1.5" />
                                      Démarrer l'examen blanc
                                    </button>
                                  </div>
                                  {isNodeComplete(index) && (
                                    <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-aurora-green/15 px-2 py-0.5 text-[10px] font-semibold text-aurora-green">
                                      <Check size={11} /> Examen validé
                                    </span>
                                  )}
                                </div>
                              )
                            }
                            return (
                              <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-aurora-border/30 pt-2">
                                <p className="w-full text-[10px] uppercase tracking-[0.2em] text-aurora-text-dim">
                                  {!unlocked ? 'Termine l etape precedente pour debloquer' : 'Faire cette lecon'}
                                </p>
                                {stepItem('Cours', BookOpen, 'courses', Boolean(nodeProgress?.courseRead))}
                                {stepItem('Fiches', Layers, 'fiches', Boolean(nodeProgress?.fichesSeen))}
                                {stepItem('Quiz', Target, 'quiz', Boolean(nodeProgress?.quizPassed), quizScoreLabel)}
                                {isNodeComplete(index) && (
                                  <span className="inline-flex items-center gap-1 rounded-full bg-aurora-green/15 px-2 py-0.5 text-[10px] font-semibold text-aurora-green">
                                    <Check size={11} /> Etape validee
                                  </span>
                                )}
                              </div>
                            )
                          })()
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )
            })}
          </div>
          <AskAboutContentBox
            className="mt-4"
            label="Je ne comprends pas une etape du parcours"
            subject={goal}
            model={activeModel}
            context={[
              `Objectif: ${goal}`,
              ...parcours.map((node, idx) => [
                `Etape ${idx + 1}: ${node.title}`,
                node.objective ? `Objectif: ${node.objective}` : '',
                node.deliverable ? `Livrable: ${node.deliverable}` : '',
                node.estimatedMinutes ? `Duree estimee: ${node.estimatedMinutes} min` : '',
                node.resources && node.resources.length > 0 ? `Ressources: ${node.resources.join(' | ')}` : '',
              ].filter(Boolean).join(' — ')),
            ].join('\n')}
            placeholder="Ex: que dois-je faire exactement pour l etape 3 ? / quelle ressource utiliser pour..."
          />
        </div>
      )}

      {learningPaths.length > 0 && (
        <div className="glass rounded-2xl p-5">
          <h3 className="text-sm font-semibold text-aurora-text">Parcours sauvegardes ({learningPaths.length})</h3>
          <div className="mt-4 space-y-2">
            {learningPaths.map((path) => {
              const nodes = path.nodes as LearningPathNode[]
              const done = nodes.filter((node) => node?.status === 'done').length
              return (
                <button
                  key={path.id}
                  onClick={() => {
                    setParcours(
                      nodes.map((node, idx) => ({
                        ...node,
                        status: node?.status ?? (idx === 0 ? 'active' : 'todo'),
                      })),
                    )
                    setGoal(path.title)
                    setActivePathId(path.id)
                    setExpandedNodeIndex(0)
                    setStatus(`Parcours "${path.title}" recharge.`)
                  }}
                  className="flex w-full items-center gap-3 rounded-xl bg-aurora-surface-2 px-3 py-3 text-left transition-colors hover:border hover:border-aurora-accent/30"
                >
                  <div className="flex-1 min-w-0">
                    <p className="truncate text-sm font-medium text-aurora-text">{path.title}</p>
                    <p className="text-[11px] text-aurora-text-dim">{done}/{nodes.length} etapes</p>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default ParcoursPanel
