// iter31 : page parcours dédiée full-screen pour la session BAC active.
//
// Conformément à la demande utilisateur (v82nu eval BAC STI2D Géo) :
//   - Page séparée, pas un panneau swipeable. position: fixed, inset: 0,
//     z-50 : tout l'écran lui appartient quand un parcours est généré.
//   - Header avec retour module + progress bar + step label + Prev/Next.
//   - Step-by-step nav intuitive : "Synthèse → Fiches → Exos → Examen".
//   - Auto-launch : quand on arrive sur Exos / Examen, ça démarre direct
//     (pas de bouton "ouvrir"). Pour l'examen, le timer démarre + le
//     beforeunload guard est armé.
//   - Exit guard pendant l'examen : "Voulez-vous vraiment partir ? Cet
//     essai ne sera pas pris en compte" (window.confirm + beforeunload).
//
// Le composant lit / pilote `useAcademyViewLogic` directement (le hook
// expose déjà parcoursPayload + tous les setters). Cela évite de muter
// la forme du store et reste compatible avec le bouton "Charger ma
// session géo" (v82m5) qui injecte un parcours pré-généré côté serveur.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence, type PanInfo } from 'framer-motion'
import { useIsMobile } from '../../hooks/useIsMobile'
import {
  ChevronLeft, ChevronRight, X, Clock, BookOpen, Layers, Target, Swords,
  CheckCircle2, AlertTriangle, Trophy, Mic, Flame, Sparkles, Shuffle,
} from 'lucide-react'
import type { UseAcademyViewLogic, AcademyParcoursExo } from '../../hooks/useAcademyViewLogic'
import { evaluateAnswerSemantically, regenerateSimilarExo, type SemanticEvalResult } from '../../services/learningSemanticEval'
import { LEARNING_EVAL_MODEL } from '../../config/models.ts'
import { getBridgeUrl } from '../../utils/runtime'
import { useLearningSessionStore } from '../../stores/learningSessionStore'
import MapPreview from './MapPreview'
import ParcoursAssistantBubble from './ParcoursAssistantBubble'

// iter32.K : nouvelle étape "menu d'entraînement" entre Fiches et Exos.
// iter33   : oral n'est PLUS un step séparé (cf clarification user) — c'est
//            un MODE qui modifie le parcours entier quand isOral est vrai
//            (matière langues, ETLV, ou prompt user "oral"). L'examen
//            devient alors une vraie passation orale (cf ExamOralStep).
type StepKind = 'synthese' | 'fiches' | 'menu' | 'exos' | 'exam'

// iter32.K : filtre des types d'exos quand l'utilisateur choisit un mode dans le menu
export type ExoFilter = 'all' | 'qcm' | 'mini' | 'flashcard'

type Step = {
  kind: StepKind
  label: string
  short: string
  icon: typeof BookOpen
}

const GOLD = 'oklch(0.74 0.13 90)'
const RED = 'oklch(0.55 0.18 25)'
const RED_FG = 'oklch(0.78 0.16 25)'
const GREEN_FG = 'oklch(0.78 0.16 145)'

export default function ParcoursActiveSession({
  academy,
  onClose,
}: {
  academy: UseAcademyViewLogic
  onClose: () => void
}) {
  const payload = academy.parcoursPayload
  const correction = academy.parcoursCorrection

  // iter32.J + N : exos peuvent être mutés (regen ciblé après échec, regen
  // global, insert "exo similaire"). On les tient en state local pour ne pas
  // muter le payload du hook.
  const [exosOverride, setExosOverride] = useState<AcademyParcoursExo[] | null>(null)
  const exosResolved: AcademyParcoursExo[] = useMemo(() => {
    if (exosOverride) return exosOverride
    return payload?.exos_apprentissage ?? []
  }, [exosOverride, payload])

  // iter32.K : filtre choisi depuis le menu — affecte ExosStep
  const [exoFilter, setExoFilter] = useState<ExoFilter>('all')

  // iter35.B : aptitude tracking — l'examen reste verrouillé tant que
  // l'apprenant n'a pas démontré une maîtrise suffisante en entraînement.
  // Critères (l'un OU l'autre suffit) :
  //   * 70% de bonnes réponses sur les 3 derniers exos (prise rapide)
  //   * 80% sur ≥5 exos consécutifs (validation longue)
  // Tant que `learnerReady === false`, le footer Suivant vers l'examen
  // reste désactivé avec un tooltip explicatif. L'utilisateur peut
  // toujours sauter directement au menu/exos via la timeline (le gating
  // ne concerne QUE l'examen — les fiches/synthèse restent libres).
  const [recentResults, setRecentResults] = useState<boolean[]>([])
  const learnerReady = useMemo(() => {
    if (recentResults.length === 0) return false
    const last3 = recentResults.slice(-3)
    if (last3.length === 3 && last3.filter(Boolean).length / 3 >= 0.70) return true
    const last5 = recentResults.slice(-5)
    if (last5.length >= 5 && last5.filter(Boolean).length / last5.length >= 0.80) return true
    return false
  }, [recentResults])
  const aptitudePct = useMemo(() => {
    if (recentResults.length === 0) return 0
    const last5 = recentResults.slice(-5)
    return Math.round((last5.filter(Boolean).length / last5.length) * 100)
  }, [recentResults])

  // v83d — mode jeu/enquête : si l'apprenant a choisi `examFormat === 'jeu'`
  // dans l'intake wizard, on re-skin l'enchaînement des étapes en manches
  // d'une aventure, et le contrôle final devient le « Boss final ». Le contenu
  // pédagogique sous-jacent ne change pas — seul l'habillage évolue, ce qui
  // colle au prompt de génération (cf ParcoursPanel : fil narratif, paliers,
  // boss final). Reste un fallback total si profile ou format manquent.
  const examFormat = useLearningSessionStore((s) => s.parcours?.profile?.examFormat)
  const isGameMode = examFormat === 'jeu'

  const steps: Step[] = useMemo(() => {
    const out: Step[] = isGameMode
      ? [
          { kind: 'synthese', label: '🗺️ Préparation · Manche 1', short: 'Préparation', icon: BookOpen },
          { kind: 'fiches',   label: '📓 Carnet de bord · Manche 2', short: 'Carnet',     icon: Layers },
        ]
      : [
          { kind: 'synthese', label: 'Synthèse 20/20', short: 'Synthèse', icon: BookOpen },
          { kind: 'fiches',   label: 'Fiches stylisées', short: 'Fiches',  icon: Layers },
        ]
    if (exosResolved.length > 0) {
      if (isGameMode) {
        out.push({ kind: 'menu', label: '🎲 Choix de l\'épreuve · Manche 3', short: 'Choix', icon: Sparkles })
        out.push({ kind: 'exos', label: '⚔️ Défis · Manche 4',                short: 'Défis', icon: Target })
      } else {
        // iter32.K : menu d'entraînement avant les exos
        out.push({ kind: 'menu',  label: "Mode d'entraînement", short: 'Menu', icon: Sparkles })
        out.push({ kind: 'exos',  label: "Exos d'apprentissage", short: 'Exos', icon: Target })
      }
    }
    // iter33 : si is_oral, l'examen final est une PASSATION ORALE (cf
    // ExamOralStep) — sinon examen écrit classique (ExamStep).
    out.push({
      kind: 'exam',
      label: isGameMode
        ? (payload?.is_oral ? '🏆 Boss final · à l\'oral' : '🏆 Boss final')
        : (payload?.is_oral ? 'Passation orale' : 'Examen blanc'),
      short: isGameMode ? 'Boss' : (payload?.is_oral ? 'Oral' : 'Examen'),
      icon: payload?.is_oral ? Mic : (isGameMode ? Trophy : Swords),
    })
    return out
  }, [exosResolved.length, payload?.is_oral, isGameMode])

  const [stepIndex, setStepIndex] = useState(0)
  const currentStep = steps[Math.min(stepIndex, steps.length - 1)]

  // v83e — état "jeu" : on suit la manche la plus loin atteinte (= clé
  // débloquée), et on déclenche un toast festif quand une nouvelle manche
  // s'ouvre. Tout est inactif si !isGameMode → zéro impact sur le flux
  // classique. La "boss key" finale n'est conférée que si learnerReady.
  const [maxReached, setMaxReached] = useState(0)
  const [unlockToast, setUnlockToast] = useState<{ key: number; manche: number; label: string } | null>(null)
  // v83g — célébration "Boss vaincu" : déclenchée une seule fois quand la
  // correction de l'examen arrive en mode jeu. Confettis si réussi.
  const [bossCelebration, setBossCelebration] = useState<null | { won: boolean; score: number; max: number; mention: string }>(null)
  useEffect(() => {
    if (!isGameMode) return
    if (!correction) return
    const max = correction.total_max || 20
    const score = correction.total ?? 0
    const won = max > 0 && score / max >= 0.5
    setBossCelebration((prev) => prev ? prev : { won, score, max, mention: correction.mention ?? '' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [correction, isGameMode])
  useEffect(() => {
    if (stepIndex > maxReached) {
      const newMax = stepIndex
      setMaxReached(newMax)
      if (isGameMode) {
        const s = steps[newMax]
        const isBoss = s?.kind === 'exam'
        setUnlockToast({
          key: Date.now(),
          manche: newMax + 1,
          label: isBoss
            ? `🏆 Boss final débloqué — à toi de jouer !`
            : `🔓 Manche ${newMax + 1} débloquée · +1 🔑`,
        })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepIndex])
  useEffect(() => {
    if (!unlockToast) return
    const t = window.setTimeout(() => setUnlockToast(null), 2600)
    return () => window.clearTimeout(t)
  }, [unlockToast])
  // Clés "gagnées" : 1 par manche atteinte avant le boss. La clé du boss
  // n'apparaît qu'à partir du moment où on l'a effectivement débloqué.
  const totalKeys = Math.max(0, steps.length - 1) // toutes sauf le boss
  const keysEarned = (() => {
    if (!isGameMode) return 0
    const nonBossReached = steps.slice(0, maxReached + 1).filter((s) => s.kind !== 'exam').length
    return Math.min(totalKeys, nonBossReached)
  })()
  // Une manche est verrouillée si on n'y est pas encore parvenu ET ce n'est
  // pas la prochaine "lisible". L'examen reste en plus gated par learnerReady.
  const isLockedStep = (i: number) => {
    if (!isGameMode) return false
    if (i <= maxReached) return false
    if (i === maxReached + 1) {
      // prochaine manche jouable… sauf si c'est le boss et pas encore prêt.
      if (steps[i]?.kind === 'exam' && !learnerReady) return true
      return false
    }
    return true
  }

  // iter31 : Auto-launch quand l'utilisateur arrive sur l'étape "exam".
  // Le timer démarre direct (pas de clic "Démarrer le contrôle") — la
  // session devient un vrai examen blanc en conditions réelles.
  // On ne le re-arme pas si l'examen a déjà été démarré OU corrigé.
  useEffect(() => {
    if (!payload) return
    if (currentStep.kind !== 'exam') return
    if (academy.parcoursControleStartedAt !== null) return
    if (correction) return
    academy.startParcoursControle()
  }, [currentStep.kind, payload, academy.parcoursControleStartedAt, correction, academy])

  // iter31 : Exit guard pendant l'examen (et seulement pendant). Tant
  // que l'utilisateur est dans l'étape "exam", qu'il a démarré le
  // timer, et qu'il n'a pas encore soumis pour correction, on
  // intercepte beforeunload + on confirme avant de quitter via le
  // bouton retour ou de changer d'étape vers une autre.
  const examGuardActive = currentStep.kind === 'exam'
    && academy.parcoursControleStartedAt !== null
    && !correction
  useEffect(() => {
    if (!examGuardActive) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
      return ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [examGuardActive])

  const guardedSetStep = (next: number) => {
    if (examGuardActive && next !== stepIndex) {
      const ok = window.confirm(
        'Voulez-vous vraiment quitter l\'examen ?\n\n'
        + 'Cet essai ne sera pas pris en compte (le timer continue de courir).\n'
        + 'Tu pourras reprendre la même étape, mais sans annuler la pénalité de temps.',
      )
      if (!ok) return
    }
    // v83e — en mode jeu, on ne saute pas par-dessus une manche verrouillée :
    // toast festif pour expliquer, et on reste sur place.
    if (isLockedStep(next)) {
      const s = steps[next]
      const isBossLocked = s?.kind === 'exam'
      setUnlockToast({
        key: Date.now(),
        manche: next + 1,
        label: isBossLocked
          ? `🔒 Boss final · entraîne-toi un peu plus (3/5 bonnes réponses) pour le débloquer`
          : `🔒 Manche ${next + 1} verrouillée — termine la manche en cours pour débloquer`,
      })
      return
    }
    setStepIndex(Math.max(0, Math.min(steps.length - 1, next)))
  }
  const guardedClose = () => {
    if (examGuardActive) {
      const ok = window.confirm(
        'Voulez-vous vraiment quitter l\'examen blanc ?\n\n'
        + 'Cet essai ne sera pas pris en compte. Tu peux revenir et soumettre,\n'
        + 'mais le timer ne s\'arrête pas.',
      )
      if (!ok) return
    }
    onClose()
  }

  // Auto-advance à la prochaine étape une fois la correction reçue,
  // pour que l'utilisateur voie immédiatement son verdict (sans bouton).
  const correctionRef = useRef(correction)
  useEffect(() => {
    if (!correctionRef.current && correction) {
      // déjà à l'étape exam, on reste — c'est là qu'est rendu le résultat.
    }
    correctionRef.current = correction
  }, [correction])

  if (!payload) {
    // Sécurité — ne devrait jamais s'afficher : le parent ne mount le
    // composant que quand parcoursPayload est non-null. Mais on garde
    // un fallback minimal pour ne pas crasher si la condition tombe à
    // false en plein montage (ex: reset() pendant l'effet de mount).
    return null
  }

  const completedSteps = correction
    ? steps.length
    : currentStep.kind === 'exam' && academy.parcoursControleStartedAt !== null
      ? stepIndex
      : stepIndex
  const progressPct = (completedSteps / steps.length) * 100

  const isMobile = useIsMobile(720)

  // iter40 : swipe via framer-motion drag — fonctionne en touch ET en
  // souris (drag), bien plus fiable que touchstart/end manuel sur
  // certains WebViews. Désactivé pendant l'examen pour ne pas casser
  // une rédaction en cours.
  const handleDragEnd = (_e: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (currentStep.kind === 'exam') return
    const { offset, velocity } = info
    // Critère : > 80px ou vélocité > 350px/s en horizontal, et pas de
    // dérive verticale dominante.
    if (Math.abs(offset.x) < 80 && Math.abs(velocity.x) < 350) return
    if (Math.abs(offset.y) > Math.abs(offset.x) * 0.8) return
    if (offset.x < 0 || velocity.x < -250) guardedSetStep(stepIndex + 1)
    else if (offset.x > 0 || velocity.x > 250) guardedSetStep(stepIndex - 1)
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      className="parcoursSession"
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        display: 'flex', flexDirection: 'column',
        background: 'var(--bg, #0c0a09)',
        color: 'var(--fg, #f5f5f5)',
        fontFamily: 'var(--font-sans, system-ui)',
      }}
      role="dialog"
      aria-label="Session de parcours BAC active"
      aria-modal="true"
    >
      {/* iter40 : refonte mobile-first — pas de chevauchement, fonts
          scalées, paddings doux, header simplifié, footer compact. */}
      <style>{`
        @media (max-width: 720px) {
          .parcoursSession .pSessionHeader {
            padding: 10px 12px !important;
            gap: 8px !important;
            flex-wrap: wrap !important;
            align-items: center !important;
          }
          .parcoursSession .pSessionHeader > div { min-width: 0 !important; }
          .parcoursSession .pSessionHeader .pSessionTitle {
            font-size: 17px !important;
            white-space: normal !important;
            line-height: 1.15 !important;
          }
          .parcoursSession .pSessionTimeline { display: none !important; }
          .parcoursSession .pSessionContent { padding: 14px !important; }
          .parcoursSession .pSessionContent h2 { font-size: 24px !important; line-height: 1.15 !important; }
          .parcoursSession .pSessionContent h3 { font-size: 17px !important; }
          .parcoursSession .pSessionFooter { padding: 10px 12px !important; gap: 6px !important; }
          .parcoursSession .pSessionFooter span { display: none; }
          .parcoursSession .pSessionStepBadge { font-size: 10px !important; padding: 3px 8px !important; }
          /* Synthese cartes : single column sur mobile */
          .parcoursSession .pSessionContent > div > div[style*="grid-template-columns"] {
            grid-template-columns: 1fr !important;
          }
        }
        .parcoursSession .pSessionContent { touch-action: pan-y; }

        /* iter40 : indicateur "swipe" qui guide la première fois */
        @keyframes swipeHint {
          0%, 100% { transform: translateX(0); opacity: 0.45; }
          50%      { transform: translateX(8px); opacity: 0.85; }
        }
      `}</style>

      {/* v83e — toast festif (mode jeu) : nouvelle manche débloquée, ou
          tentative sur une manche verrouillée. Glisse depuis le haut, se
          retire seule après 2,6 s. AnimatePresence pour une sortie propre. */}
      <AnimatePresence>
        {unlockToast && (
          <motion.div key={unlockToast.key}
            initial={{ y: -32, opacity: 0, scale: 0.92 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: -16, opacity: 0, scale: 0.96 }}
            transition={{ type: 'spring', stiffness: 320, damping: 26 }}
            style={{
              position: 'fixed', top: 18, left: '50%', transform: 'translateX(-50%)',
              zIndex: 80, pointerEvents: 'none',
              padding: '10px 18px', borderRadius: 99,
              background: unlockToast.label.startsWith('🔒')
                ? 'oklch(0.18 0.02 280 / 0.96)'
                : 'linear-gradient(135deg, oklch(0.78 0.18 85 / 0.95), oklch(0.74 0.15 75 / 0.92))',
              color: unlockToast.label.startsWith('🔒') ? 'oklch(0.92 0.06 80)' : 'oklch(0.18 0.05 70)',
              border: `1px solid ${unlockToast.label.startsWith('🔒') ? 'oklch(0.55 0.10 80 / 0.55)' : 'oklch(0.92 0.14 88)'}`,
              boxShadow: '0 8px 32px rgba(0,0,0,0.4), 0 0 24px oklch(0.78 0.18 85 / 0.35)',
              fontFamily: 'var(--font-sans, system-ui)', fontSize: 14, fontWeight: 700,
              letterSpacing: '0.01em',
            }}>
            {unlockToast.label}
          </motion.div>
        )}
      </AnimatePresence>

      {/* v83g — célébration plein écran « Boss vaincu » (mode jeu). */}
      <AnimatePresence>
        {bossCelebration && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setBossCelebration(null)}
            style={{
              position: 'fixed', inset: 0, zIndex: 90, cursor: 'pointer',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              background: 'oklch(0.08 0.02 280 / 0.72)', backdropFilter: 'blur(3px)',
              overflow: 'hidden',
            }}>
            {/* confettis (uniquement si réussi) */}
            {bossCelebration.won && Array.from({ length: 28 }).map((_, i) => {
              const colors = ['oklch(0.86 0.18 75)', 'oklch(0.78 0.16 145)', 'oklch(0.62 0.22 295)', 'oklch(0.72 0.13 195)', 'oklch(0.7 0.2 25)']
              const left = Math.random() * 100
              const delay = Math.random() * 0.6
              const dur = 1.6 + Math.random() * 1.6
              const size = 7 + Math.random() * 8
              return (
                <motion.div key={i}
                  initial={{ y: -40, x: 0, opacity: 1, rotate: 0 }}
                  animate={{ y: '100vh', x: (Math.random() - 0.5) * 160, opacity: [1, 1, 0.2], rotate: 360 * (Math.random() > 0.5 ? 1 : -1) }}
                  transition={{ duration: dur, delay, ease: 'easeIn' }}
                  style={{
                    position: 'absolute', top: 0, left: `${left}%`,
                    width: size, height: size * (Math.random() > 0.5 ? 1 : 0.4),
                    background: colors[i % colors.length], borderRadius: 2,
                  }} />
              )
            })}
            <motion.div
              initial={{ scale: 0.7, y: 12 }} animate={{ scale: 1, y: 0 }}
              transition={{ type: 'spring', stiffness: 260, damping: 18 }}
              style={{
                padding: '22px 32px', borderRadius: 18, textAlign: 'center',
                background: bossCelebration.won
                  ? 'linear-gradient(135deg, oklch(0.78 0.18 85 / 0.96), oklch(0.74 0.15 75 / 0.92))'
                  : 'oklch(0.20 0.02 280 / 0.97)',
                border: `1px solid ${bossCelebration.won ? 'oklch(0.92 0.14 88)' : 'oklch(0.55 0.10 280 / 0.5)'}`,
                color: bossCelebration.won ? 'oklch(0.16 0.05 70)' : 'var(--fg, #f5f5f5)',
                boxShadow: '0 20px 80px rgba(0,0,0,0.5)', maxWidth: 'min(440px, 90vw)',
              }}>
              <div style={{ fontSize: 44, lineHeight: 1, marginBottom: 6 }}>{bossCelebration.won ? '🏆' : '💪'}</div>
              <div style={{
                fontFamily: 'var(--font-display, "Cormorant Garamond", serif)', fontStyle: 'italic',
                fontSize: 30, marginBottom: 4,
              }}>
                {bossCelebration.won ? 'Boss vaincu !' : 'Combat terminé'}
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>
                {bossCelebration.score}/{bossCelebration.max}{bossCelebration.mention ? ` · ${bossCelebration.mention}` : ''}
              </div>
              <div style={{ fontSize: 12.5, opacity: 0.85, lineHeight: 1.5 }}>
                {bossCelebration.won
                  ? 'Tu as bouclé l\'aventure et collecté toutes les clés. Bien joué — relance un parcours pour enchaîner.'
                  : 'Tu y étais presque. Refais quelques manches d\'entraînement et retente le boss : tu vas le passer.'}
              </div>
              <div style={{ marginTop: 14, fontSize: 11, fontFamily: 'var(--font-mono, monospace)', opacity: 0.6 }}>
                (clique pour fermer)
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* HEADER : retour modules + progress + step label */}
      <div className="pSessionHeader" style={{
        flexShrink: 0,
        display: 'flex', alignItems: 'center', gap: 16,
        padding: '14px 24px',
        borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
        background: 'var(--bg-raised, rgba(255,255,255,0.03))',
      }}>
        <button type="button" onClick={guardedClose}
          title="Retour aux modules"
          style={{
            width: 36, height: 36, borderRadius: 8,
            background: 'transparent',
            border: '1px solid var(--line, rgba(255,255,255,0.18))',
            color: 'var(--fg, #f5f5f5)',
            cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          }}>
          <X size={16} />
        </button>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0, flex: 1 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12, minWidth: 0, flexWrap: 'wrap',
          }}>
            {/* iter37 : badge step ludique avec emoji-emotion + couleur vive */}
            <span className="pSessionStepBadge" style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '4px 10px', borderRadius: 99,
              background: currentStep.kind === 'exam'
                ? `linear-gradient(135deg, ${RED_FG}33, ${RED_FG}55)`
                : `linear-gradient(135deg, ${GOLD}22, oklch(0.62 0.22 295 / 0.25))`,
              border: `1px solid ${currentStep.kind === 'exam' ? RED_FG + '66' : GOLD + '66'}`,
              fontFamily: 'var(--font-mono, monospace)',
              fontSize: 11, letterSpacing: '0.08em',
              color: currentStep.kind === 'exam' ? RED_FG : GOLD,
              fontWeight: 700,
            }}>
              {(() => {
                const totalNoExam = steps.filter(s => s.kind !== 'exam').length
                const isExam = currentStep.kind === 'exam'
                if (isGameMode) {
                  if (isExam) return '🏆 BOSS FINAL'
                  const manche = stepIndex + 1
                  if (currentStep.kind === 'synthese') return `🗺️ Manche ${manche}/${totalNoExam} · Préparation`
                  if (currentStep.kind === 'fiches')   return `📓 Manche ${manche}/${totalNoExam} · Carnet de bord`
                  if (currentStep.kind === 'menu')     return `🎲 Manche ${manche}/${totalNoExam} · Choix de l'épreuve`
                  if (currentStep.kind === 'exos')     return `⚔️ Manche ${manche}/${totalNoExam} · Défis`
                  return `Manche ${manche}/${steps.length}`
                }
                if (isExam) return '🎯 Le grand jour'
                if (currentStep.kind === 'synthese') return `🌅 On démarre · 1/${totalNoExam}`
                if (currentStep.kind === 'fiches') return `📖 On bosse · ${stepIndex + 1}/${totalNoExam}`
                if (currentStep.kind === 'menu') return `🕹 On choisit · ${stepIndex + 1}/${totalNoExam}`
                if (currentStep.kind === 'exos') return `🎮 On joue · ${stepIndex + 1}/${totalNoExam}`
                return `Étape ${stepIndex + 1}/${steps.length}`
              })()}
            </span>
            <span className="pSessionTitle" style={{
              fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
              fontSize: 22, fontStyle: 'italic',
              color: currentStep.kind === 'exam' ? RED_FG : GOLD,
              letterSpacing: '-0.01em',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              minWidth: 0,
            }}>
              {currentStep.label}
            </span>
            {isGameMode && (
              <>
                <span title="Mode jeu / enquête actif — le parcours est un fil narratif découpé en manches."
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                    padding: '2px 9px', borderRadius: 99,
                    fontSize: 10, fontFamily: 'var(--font-mono, monospace)',
                    background: 'oklch(0.74 0.15 75 / 0.18)', color: 'oklch(0.85 0.16 80)',
                    border: '1px solid oklch(0.74 0.15 75 / 0.55)', fontWeight: 700,
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                  }}>
                  🎮 mode jeu
                </span>
                <span title={`Clés gagnées : ${keysEarned} sur ${totalKeys}. Chaque manche réussie = 1 🔑 (le Boss final s'ouvre quand tu es prêt).`}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 5,
                    padding: '2px 10px', borderRadius: 99,
                    fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                    background: 'oklch(0.78 0.18 85 / 0.16)', color: 'oklch(0.92 0.14 88)',
                    border: '1px solid oklch(0.78 0.18 85 / 0.55)', fontWeight: 700,
                    boxShadow: keysEarned > 0 ? '0 0 14px oklch(0.78 0.18 85 / 0.35)' : 'none',
                    transition: 'box-shadow 240ms ease',
                  }}>
                  🔑 {keysEarned}/{totalKeys}
                </span>
                {steps[steps.length - 1]?.kind === 'exam' && (
                  <span title={learnerReady ? 'Boss final accessible !' : `Le Boss final s'ouvre quand tu as ${recentResults.length === 0 ? 'fait quelques défis' : 'assez d\'aptitude (3/3 ou 4/5)'}.`}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 4,
                      padding: '2px 9px', borderRadius: 99,
                      fontSize: 10, fontFamily: 'var(--font-mono, monospace)',
                      background: learnerReady ? 'oklch(0.55 0.18 25 / 0.18)' : 'rgba(255,255,255,0.04)',
                      color: learnerReady ? RED_FG : 'var(--fg-mute, #777)',
                      border: `1px solid ${learnerReady ? RED + '88' : 'var(--line, rgba(255,255,255,0.14))'}`,
                      fontWeight: 700, letterSpacing: '0.08em',
                    }}>
                    {learnerReady ? '🏆 boss ready' : '🔒 boss'}
                  </span>
                )}
              </>
            )}
            {examGuardActive && (
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                padding: '2px 8px', borderRadius: 99,
                fontSize: 10, fontFamily: 'var(--font-mono, monospace)',
                background: `${RED} / 0.15`, color: RED_FG,
                border: `1px solid ${RED}55`,
              }} title="Tu es dans un examen chronométré : quitter compte comme essai non valide.">
                <AlertTriangle size={10} /> {isGameMode ? 'BOSS LIVE' : 'EXAM LIVE'}
              </span>
            )}
          </div>
          {/* Progress bar */}
          <div style={{
            height: 4, borderRadius: 99,
            background: 'var(--ink-800, rgba(255,255,255,0.06))',
            overflow: 'hidden',
          }}>
            <div style={{
              width: `${progressPct}%`, height: '100%',
              background: currentStep.kind === 'exam'
                ? `linear-gradient(90deg, ${GOLD}, ${RED})`
                : `linear-gradient(90deg, ${GOLD} 0%, oklch(0.78 0.16 145) 100%)`,
              transition: 'width 200ms ease',
            }} />
          </div>
          {/* Étape suivante hint */}
          {stepIndex < steps.length - 1 && (
            <span style={{
              fontSize: 10, fontFamily: 'var(--font-mono, monospace)',
              color: 'var(--fg-mute, #777)',
            }}>
              Suivante : {steps[stepIndex + 1].short}
            </span>
          )}
        </div>

        {/* Stepper dots compact pour cliquer directement (caché sur mobile).
            v83e — en mode jeu : 🔒 pour les manches verrouillées, lueur dorée
            pour la prochaine débloquée, ✓ vert pour les manches faites. */}
        <div className="pSessionTimeline" style={{ display: 'flex', gap: 6 }}>
          {steps.map((s, i) => {
            const Icon = s.icon
            const active = i === stepIndex
            const done = i < stepIndex || (correction && s.kind === 'exam')
            const locked = isLockedStep(i)
            const nextPlayable = isGameMode && !locked && !done && !active && i === maxReached + 1
            return (
              <button key={s.kind} type="button"
                onClick={() => guardedSetStep(i)}
                title={locked ? `🔒 ${s.label} — verrouillée` : (isGameMode ? `Manche ${i + 1} · ${s.label}` : s.label)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  padding: '6px 10px', borderRadius: 99,
                  border: `1px solid ${
                    locked ? 'var(--line, rgba(255,255,255,0.10))'
                    : active ? GOLD
                    : nextPlayable ? `${GOLD}88`
                    : 'var(--line, rgba(255,255,255,0.12))'
                  }`,
                  background: locked
                    ? 'rgba(255,255,255,0.02)'
                    : active
                      ? `${GOLD}1A`
                      : nextPlayable
                        ? `${GOLD}10`
                        : done
                          ? 'oklch(0.78 0.16 145 / 0.10)'
                          : 'transparent',
                  color: locked
                    ? 'var(--fg-mute, #666)'
                    : active
                      ? GOLD
                      : nextPlayable
                        ? GOLD
                        : done
                          ? GREEN_FG
                          : 'var(--fg-dim, #aaa)',
                  fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                  cursor: locked ? 'not-allowed' : 'pointer',
                  opacity: locked ? 0.55 : 1,
                  boxShadow: nextPlayable ? `0 0 0 2px ${GOLD}22, 0 0 14px ${GOLD}44` : 'none',
                  transition: 'box-shadow 200ms ease, background 160ms',
                }}>
                {locked ? <span aria-label="verrouillé">🔒</span>
                  : done ? <CheckCircle2 size={11} />
                  : <Icon size={11} />}
                <span>{isGameMode ? (s.kind === 'exam' ? '🏆 Boss' : `M${i + 1}`) : s.short}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* CONTENT (scrollable per-step) */}
      <div className="pSessionContent" style={{
        flex: 1, overflowY: 'auto',
        padding: '24px 32px',
      }}>
        <AnimatePresence mode="wait">
          <motion.div key={currentStep.kind}
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -24 }}
            transition={{ duration: 0.22 }}
            drag={isMobile && currentStep.kind !== 'exam' ? 'x' : false}
            dragConstraints={{ left: 0, right: 0 }}
            dragElastic={0.18}
            onDragEnd={handleDragEnd}
            style={{ touchAction: 'pan-y' }}>
            {currentStep.kind === 'synthese' && <SyntheseStep payload={payload} />}
            {currentStep.kind === 'fiches' && <FichesStep payload={payload} />}
            {currentStep.kind === 'menu' && (
              <MenuStep
                onChoose={(filter, target) => {
                  setExoFilter(filter)
                  setStepIndex(steps.findIndex((s) => s.kind === target))
                }}
                hasExos={exosResolved.length > 0}
                stepKinds={steps.map((s) => s.kind)}
              />
            )}
            {currentStep.kind === 'exos' && (
              <ExosStep
                payload={payload}
                exos={exosResolved}
                filter={exoFilter}
                subject={(academy.subjectLabels as Record<string, string>)[academy.subject as string] || 'général'}
                onRegenAll={(fresh) => setExosOverride(fresh)}
                onInsertSimilar={(afterIdx, ex) => {
                  setExosOverride((prev) => {
                    const base = prev ?? exosResolved
                    const copy = [...base]
                    copy.splice(afterIdx + 1, 0, ex)
                    return copy
                  })
                }}
                onAnswerResult={(ok) => setRecentResults((rr) => [...rr.slice(-9), ok])}
                aptitudePct={aptitudePct}
                learnerReady={learnerReady}
                onProceedToExam={() => {
                  const examIdx = steps.findIndex((s) => s.kind === 'exam')
                  if (examIdx >= 0) setStepIndex(examIdx)
                }}
              />
            )}
            {currentStep.kind === 'exam' && (
              payload.is_oral
                ? <ExamOralStep
                    academy={academy}
                    subjectLabel={(academy.subjectLabels as Record<string, string>)[academy.subject as string] || 'général'}
                  />
                : <ExamStep academy={academy} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* FOOTER : Prev / Next */}
      <div className="pSessionFooter" style={{
        flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
        padding: '14px 24px',
        borderTop: '1px solid var(--line, rgba(255,255,255,0.12))',
        background: 'var(--bg-raised, rgba(255,255,255,0.03))',
      }}>
        <button type="button"
          onClick={() => guardedSetStep(stepIndex - 1)}
          disabled={stepIndex === 0}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '8px 14px', borderRadius: 8,
            background: 'transparent',
            border: '1px solid var(--line, rgba(255,255,255,0.18))',
            color: stepIndex === 0 ? 'var(--fg-mute, #555)' : 'var(--fg, #f5f5f5)',
            cursor: stepIndex === 0 ? 'not-allowed' : 'pointer',
            opacity: stepIndex === 0 ? 0.5 : 1,
            fontSize: 12, fontFamily: 'var(--font-mono, monospace)',
          }}>
          <ChevronLeft size={14} /> Précédent
        </button>

        <span style={{
          fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
          color: 'var(--fg-mute, #888)', letterSpacing: '0.1em',
        }}>
          {currentStep.kind === 'exam' && academy.parcoursControleStartedAt !== null
            ? 'Soumets pour le verdict'
            : currentStep.kind === 'exam'
              ? 'Examen lancé'
              : isMobile
                ? <span style={{ animation: 'swipeHint 1.6s ease-in-out infinite', display: 'inline-block' }}>← swipe →</span>
                : 'Scroll · Suivant pour avancer'}
        </span>

        {(() => {
          const nextStep = steps[stepIndex + 1]
          const goesToExam = nextStep?.kind === 'exam'
          // iter35.B : verrou aptitude — l'examen reste fermé tant que
          // l'élève n'a pas validé l'entraînement (learnerReady=true).
          // Exception : si aucun exo n'a été tenté (recentResults vide) ET
          // l'utilisateur arrive sur Menu/Exos pour la première fois, le
          // bouton vers exam est verrouillé. Si recentResults non vide
          // mais sous le seuil, on affiche le pourcentage actuel.
          const aptitudeLocked = goesToExam && !learnerReady
          const lastIdx = stepIndex >= steps.length - 1
          const disabled = lastIdx || aptitudeLocked
          return (
            <button type="button"
              onClick={() => guardedSetStep(stepIndex + 1)}
              disabled={disabled}
              title={aptitudeLocked
                ? `Tu n'es pas encore prêt pour l'examen — score actuel ${aptitudePct}% (objectif 70% sur 3 derniers ou 80% sur 5 consécutifs).`
                : undefined}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '8px 14px', borderRadius: 8,
                background: disabled ? 'transparent' : `${GOLD}1A`,
                border: `1px solid ${disabled ? 'var(--line, rgba(255,255,255,0.12))' : GOLD + '88'}`,
                color: disabled ? 'var(--fg-mute, #555)' : GOLD,
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.5 : 1,
                fontSize: 12, fontFamily: 'var(--font-mono, monospace)',
                fontWeight: 600,
              }}>
              {(() => {
                if (!nextStep) return 'Suivant'
                if (goesToExam && aptitudeLocked) return `Examen verrouillé · ${aptitudePct}%`
                if (goesToExam) return payload?.is_oral ? 'Passer à l\'oral · Apte' : '🎓 Passer à l\'examen réel'
                if (nextStep.kind === 'menu') return 'Choisir un mode'
                return 'Suivant'
              })()} <ChevronRight size={14} />
            </button>
          )
        })()}
      </div>

      {/* iter37 : bubble assistant IA flottante. Auto-ouvre ~1.2s après
          l'arrivée sur la session, contexte = parcours complet, accessible
          depuis tous les steps. L'élève demande à développer un point. */}
      <ParcoursAssistantBubble
        payload={payload}
        subjectLabel={(academy.subjectLabels as Record<string, string>)[academy.subject as string] || 'général'}
        currentStep={currentStep.kind}
        gameMode={isGameMode}
      />
    </motion.div>
  )
}

// ============================================================
// Step renderers — extraits du ParcoursBacRenderer existant
// ============================================================

function SyntheseStep({ payload }: { payload: NonNullable<UseAcademyViewLogic['parcoursPayload']> }) {
  const s = payload.synthese_20_20
  // v83d : mode jeu/enquête → habillage narratif au lieu du registre académique.
  const isGameMode = useLearningSessionStore((s2) => s2.parcours?.profile?.examFormat === 'jeu')
  return (
    <div style={{
      maxWidth: 920, margin: '0 auto',
      display: 'flex', flexDirection: 'column', gap: 18,
    }}>
      {/* iter37 : bandeau ludique d'accueil */}
      <div style={{
        padding: '12px 16px', borderRadius: 12,
        background: 'linear-gradient(135deg, oklch(0.62 0.22 295 / 0.20), oklch(0.86 0.18 75 / 0.18))',
        border: '1px solid oklch(0.62 0.22 295 / 0.4)',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <span style={{ fontSize: 28 }}>{isGameMode ? '🗺️' : '🎯'}</span>
        <div style={{ flex: 1, fontSize: 13, color: 'rgba(255,255,255,0.9)', lineHeight: 1.5 }}>
          {isGameMode ? (
            <><strong>Briefing de la mission !</strong> Voici le scénario et
            les enjeux. Lis tranquille, prends des notes mentales — les
            manches suivantes s'appuient dessus. Le coach 🪄 (en bas à droite)
            est là si tu coinces.</>
          ) : (
            <><strong>Bienvenue dans ton parcours !</strong> On commence par la
            synthèse — tout ce qu'il faut savoir pour cartonner. Prends ton
            temps, le coach 🪄 (en bas à droite) est là si tu as besoin.</>
          )}
        </div>
      </div>
      <div>
        <div style={{
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          letterSpacing: '0.18em', textTransform: 'uppercase',
          color: 'oklch(0.86 0.18 75)', marginBottom: 8,
        }}>
          {isGameMode ? '🗺️ Briefing de la mission · Manche 1' : '🌅 Synthèse essentielle'}
        </div>
        <h2 style={{
          fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
          fontStyle: 'italic', fontWeight: 400, fontSize: 38,
          letterSpacing: '-0.02em', margin: 0,
          color: 'var(--fg, #f5f5f5)',
        }}>{s.titre}</h2>
      </div>

      <div style={{
        padding: 18, borderRadius: 8,
        background: `${GOLD}10`, border: `1px solid ${GOLD}55`,
      }}>
        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10, color: 'oklch(0.78 0.16 90)' }}>
          ⚡ Ce que tu DOIS savoir absolument
        </div>
        <ul style={{ margin: 0, paddingLeft: 22, fontSize: 14, lineHeight: 1.65 }}>
          {s.ce_qu_il_faut_savoir.map((line, i) => <li key={i} style={{ marginBottom: 4 }}>{line}</li>)}
        </ul>
      </div>

      {s.pieges_classiques?.length > 0 && (
        <div style={{
          padding: 16, borderRadius: 8,
          background: `${RED}10`, border: `1px solid ${RED}55`,
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, color: RED_FG }}>
            ⚠ Pièges classiques à éviter
          </div>
          <ul style={{ margin: 0, paddingLeft: 22, fontSize: 13, lineHeight: 1.55, color: 'var(--fg-dim, #aaa)' }}>
            {s.pieges_classiques.map((p, i) => <li key={i} style={{ marginBottom: 4 }}>{p}</li>)}
          </ul>
        </div>
      )}

      {s.vocabulaire_a_maitriser?.length > 0 && (
        <div style={{
          padding: 16, borderRadius: 8,
          background: 'var(--bg-card, rgba(255,255,255,0.03))',
          border: '1px solid var(--line, rgba(255,255,255,0.12))',
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>
            📖 Vocabulaire à maîtriser
          </div>
          <div style={{
            display: 'grid', gap: 10,
            gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
          }}>
            {s.vocabulaire_a_maitriser.map((v, i) => (
              <div key={i} style={{
                padding: 10, borderRadius: 6,
                background: 'var(--bg-raised, rgba(255,255,255,0.02))',
                border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
              }}>
                <strong style={{ color: 'oklch(0.78 0.16 90)' }}>{v.terme}</strong>
                <div style={{ marginTop: 4, fontSize: 12, color: 'var(--fg-dim, #aaa)' }}>{v.definition_exacte}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* iter35.C : croquis cartographiques (géographie / géopolitique) */}
      {payload.cartes && payload.cartes.length > 0 && (
        <div>
          <div style={{
            fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
            letterSpacing: '0.18em', textTransform: 'uppercase',
            color: 'var(--fg-mute, #888)', marginBottom: 12,
          }}>
            Croquis & cartes ({payload.cartes.length})
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {payload.cartes.map((carte, i) => (
              <MapPreview key={i} carte={carte} />
            ))}
          </div>
        </div>
      )}

      {/* v83e — aperçu du Boss final : visible dès la 1ʳᵉ manche pour donner
          un horizon clair (« où tu vas, combien ça pèse »). Mode jeu only. */}
      {isGameMode && payload.controle && (
        <div style={{
          marginTop: 6, padding: '14px 18px', borderRadius: 12,
          background: 'linear-gradient(135deg, oklch(0.55 0.18 25 / 0.10), oklch(0.78 0.18 85 / 0.10))',
          border: '1px dashed oklch(0.78 0.16 25 / 0.5)',
          display: 'flex', alignItems: 'flex-start', gap: 12,
        }}>
          <span style={{ fontSize: 32, lineHeight: 1 }}>🏆</span>
          <div style={{ flex: 1 }}>
            <div style={{
              fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
              letterSpacing: '0.18em', textTransform: 'uppercase',
              color: 'oklch(0.85 0.16 80)', marginBottom: 4,
            }}>
              Au bout du parcours · ta quête finale
            </div>
            <div style={{
              fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
              fontStyle: 'italic', fontSize: 20, color: 'var(--fg, #f5f5f5)', marginBottom: 4,
            }}>
              Boss final · {payload.controle.duration_min} min · {payload.controle.points_questions + payload.controle.points_developpement} pts
            </div>
            <div style={{ fontSize: 12, color: 'var(--fg-dim, #aaa)', lineHeight: 1.5 }}>
              Tu enchaînes les manches (carnet, choix, défis), tu collectes des 🔑 clés,
              tu débloques le Boss quand ton aptitude est prête (3/3 ou 4/5 bonnes
              réponses). C'est ta « finale » — entraîne-toi avec ce qu'il faut pour y arriver serein.
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function FichesStep({ payload }: { payload: NonNullable<UseAcademyViewLogic['parcoursPayload']> }) {
  const isGameMode = useLearningSessionStore((s2) => s2.parcours?.profile?.examFormat === 'jeu')
  // iter31.F.1: print/PDF export. Ouvre une window dédiée avec layout
  // print-friendly + auto-trigger window.print() — l'utilisateur peut alors
  // soit imprimer papier soit "Save as PDF" via la dialog browser standard.
  const handlePrint = () => {
    const w = window.open('', '_blank', 'width=900,height=1100')
    if (!w) {
      window.alert("Le navigateur a bloqué l'ouverture. Autorise les pop-ups pour ce site.")
      return
    }
    const ficheHtml = payload.fiches.map((f) => `
      <div class="fiche">
        <h3>${(f.icone || '📄')} ${escapeHtml(f.titre)}</h3>
        <p class="def"><em>${escapeHtml(f.definition)}</em></p>
        ${f.developpement_court ? `<p class="dev">${escapeHtml(f.developpement_court)}</p>` : ''}
        <ul>${f.idees_cles.map((k) => `<li>${escapeHtml(k)}</li>`).join('')}</ul>
        ${f.schema_ascii_ou_data ? `<pre>${escapeHtml(f.schema_ascii_ou_data)}</pre>` : ''}
        ${f.mnemonique ? `<div class="mnemo">💡 ${escapeHtml(f.mnemonique)}</div>` : ''}
      </div>`).join('')
    w.document.write(`<!doctype html><html><head><meta charset="utf-8">
<title>${escapeHtml(payload.synthese_20_20.titre)} — Fiches de révision</title>
<style>
  @page { size: A4; margin: 12mm; }
  * { box-sizing: border-box; }
  body { font-family: Georgia, "Cormorant Garamond", serif; color: #111; max-width: 800px; margin: 0 auto; padding: 16px; line-height: 1.45; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .subtitle { font-size: 12px; color: #555; margin: 0 0 16px; letter-spacing: 0.15em; text-transform: uppercase; }
  .fiche { break-inside: avoid; page-break-inside: avoid; margin-bottom: 14px; padding: 10px 14px; border: 1px solid #999; border-radius: 4px; }
  .fiche h3 { font-size: 15px; margin: 0 0 6px; }
  .fiche .def { font-size: 12px; margin: 0 0 8px; color: #333; }
  .fiche .dev { font-size: 12px; line-height: 1.5; margin: 6px 0; padding: 6px 10px; background: #eaf3f7; border-left: 3px solid #2b6f86; text-align: justify; }
  .fiche ul { margin: 4px 0 6px 16px; padding: 0; font-size: 12px; }
  .fiche pre { margin: 6px 0; padding: 6px; background: #f6f6f0; border-radius: 3px; font-size: 10px; white-space: pre-wrap; }
  .fiche .mnemo { margin-top: 6px; padding: 4px 8px; background: #fff7d6; border-left: 3px solid #c0a500; font-size: 11px; font-style: italic; }
  @media print { .toolbar { display: none; } body { padding: 0; } }
  .toolbar { position: sticky; top: 0; background: #fff; padding: 6px 0 12px; border-bottom: 1px solid #ddd; margin-bottom: 12px; }
  .toolbar button { font-family: inherit; font-size: 12px; padding: 6px 14px; cursor: pointer; border-radius: 4px; border: 1px solid #888; background: #fff; }
</style></head><body>
<div class="toolbar">
  <button onclick="window.print()">🖨 Imprimer / Save as PDF</button>
  <button onclick="window.close()">Fermer</button>
</div>
<h1>${escapeHtml(payload.synthese_20_20.titre)}</h1>
<p class="subtitle">Fiches de révision · ${payload.fiches.length} fiches</p>
${ficheHtml}
<script>setTimeout(() => window.print(), 400)</script>
</body></html>`)
    w.document.close()
  }

  return (
    <div style={{
      maxWidth: 1100, margin: '0 auto',
      display: 'flex', flexDirection: 'column', gap: 18,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <div style={{
            fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
            letterSpacing: '0.18em', textTransform: 'uppercase',
            color: 'var(--fg-mute, #888)', marginBottom: 8,
          }}>
            {isGameMode ? `📓 Carnet de bord · Manche 2 · ${payload.fiches.length} entrées` : `Fiches de révision · ${payload.fiches.length}`}
          </div>
          <h2 style={{
            fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
            fontStyle: 'italic', fontWeight: 400, fontSize: 32,
            margin: 0, color: 'var(--fg, #f5f5f5)',
          }}>{isGameMode ? 'Carnet de bord' : 'Fiches stylisées'}</h2>
          <p style={{ marginTop: 6, fontSize: 13, color: 'var(--fg-dim, #aaa)' }}>
            {isGameMode
              ? "Les notes de terrain qui vont t'aider aux manches suivantes. Définitions, indices, idées clés. Parcours-les avant de passer au défi."
              : 'Définitions, idées clés, mnémoniques. Scroll pour les parcourir, Suivant pour passer aux exos.'}
          </p>
        </div>
        {/* iter31.F.1: bouton Imprimer / PDF */}
        <button type="button" onClick={handlePrint}
          title="Ouvre une fenêtre print-friendly — utilise « Save as PDF » dans le dialog d'impression pour exporter."
          style={{
            flexShrink: 0,
            padding: '10px 16px',
            background: GOLD, color: '#0a0a0a',
            border: 'none', fontSize: 12, fontWeight: 600,
            cursor: 'pointer', borderRadius: 6,
            fontFamily: 'var(--font-sans, system-ui)',
            display: 'inline-flex', alignItems: 'center', gap: 6,
          }}>
          🖨 Imprimer / PDF
        </button>
      </div>

      <div style={{
        display: 'grid', gap: 14,
        gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
      }}>
        {payload.fiches.map((f, i) => (
          <div key={i} style={{
            padding: 14, borderRadius: 8,
            background: 'var(--bg-card, rgba(255,255,255,0.04))',
            border: '1px solid oklch(0.72 0.12 200 / 0.30)',
          }}>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6 }}>
              {f.icone || '📄'} {f.titre}
            </div>
            <div style={{ fontSize: 12, fontStyle: 'italic', color: 'var(--fg-dim, #aaa)', marginBottom: 8 }}>
              {f.definition}
            </div>
            {/* iter32.I — paragraphe de développement détaillé */}
            {f.developpement_court && (
              <p style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--fg, #f5f5f5)', margin: '8px 0', textAlign: 'justify' }}>
                {f.developpement_court}
              </p>
            )}
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.5 }}>
              {f.idees_cles.map((k, j) => <li key={j}>{k}</li>)}
            </ul>
            {f.schema_ascii_ou_data && (
              <pre style={{
                marginTop: 8, fontSize: 10, padding: 8,
                background: 'var(--bg-raised, rgba(255,255,255,0.02))',
                borderRadius: 4, overflow: 'auto', maxHeight: 200,
              }}>{f.schema_ascii_ou_data}</pre>
            )}
            {f.mnemonique && (
              <div style={{
                marginTop: 8, padding: 6, fontSize: 11, fontStyle: 'italic',
                background: `${GOLD}26`, borderRadius: 4,
              }}>
                💡 {f.mnemonique}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// iter31.F.1 helper
function escapeHtml(s: string): string {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// iter32.K + J + N : ExosStep avec filtre, regen ciblée par concept faible,
// regen globale, streak counter, confetti animation, et badges.
function ExosStep({
  payload,
  exos,
  filter,
  subject,
  onRegenAll,
  onInsertSimilar,
  onAnswerResult,
  aptitudePct,
  learnerReady,
  onProceedToExam,
}: {
  payload: NonNullable<UseAcademyViewLogic['parcoursPayload']>
  exos: AcademyParcoursExo[]
  filter: ExoFilter
  subject: string
  onRegenAll: (fresh: AcademyParcoursExo[]) => void
  onInsertSimilar: (afterIdx: number, ex: AcademyParcoursExo) => void
  onAnswerResult?: (ok: boolean) => void
  aptitudePct?: number
  learnerReady?: boolean
  onProceedToExam?: () => void
}) {
  // iter32.K : filtre les exos selon le mode choisi dans le menu.
  const filteredExos = useMemo(() => {
    if (filter === 'all') return exos
    return exos.filter((e) => {
      const t = (e.type || 'flashcard').toLowerCase()
      const k: ExoFilter = /qcm/.test(t) ? 'qcm'
        : /mini[-_ ]?exo|exercice|développement/.test(t) ? 'mini'
        : 'flashcard'
      return k === filter
    })
  }, [exos, filter])

  const [idx, setIdx] = useState(0)
  // iter32.M : score étendu avec streak (réponses ok consécutives)
  const [score, setScore] = useState({ ok: 0, ko: 0, points: 0, streak: 0, bestStreak: 0 })
  // iter32.M : confetti trigger sur bonne réponse — auto-clear après 1.4s
  const [confettiKey, setConfettiKey] = useState(0)
  // iter32.N : regen globale en cours
  const [regeningAll, setRegeningAll] = useState(false)
  const [regenError, setRegenError] = useState<string | null>(null)

  const total = filteredExos.length
  if (total === 0) {
    return (
      <div style={{ maxWidth: 700, margin: '0 auto', textAlign: 'center', padding: 40 }}>
        <p style={{ color: 'var(--fg-dim, #aaa)' }}>
          Aucun exercice {filter !== 'all' ? `de type "${filter}"` : ''} dans ce parcours.
        </p>
        {filter !== 'all' && (
          <p style={{ color: 'var(--fg-mute, #888)', fontSize: 12 }}>
            Reviens au menu pour choisir un autre mode, ou clique sur Régénérer pour de nouveaux exos.
          </p>
        )}
      </div>
    )
  }
  const current = filteredExos[idx]
  const next = () => setIdx((i) => Math.min(total - 1, i + 1))
  const prev = () => setIdx((i) => Math.max(0, i - 1))

  // Normalize type
  const t = (current.type || 'flashcard').toLowerCase()
  const kind: 'flashcard' | 'qcm' | 'mini' =
    /qcm/.test(t) ? 'qcm' : /mini[-_ ]?exo|exercice|développement/.test(t) ? 'mini' : 'flashcard'

  // iter32.M : enregistre une bonne / mauvaise réponse + déclenche confetti si ok
  // iter35.B : remonte aussi le résultat au parent pour calculer l'aptitude.
  const recordResult = useCallback((ok: boolean, pts: number) => {
    if (ok) setConfettiKey((k) => k + 1)
    setScore((s) => {
      const nextStreak = ok ? s.streak + 1 : 0
      return {
        ok: s.ok + (ok ? 1 : 0),
        ko: s.ko + (ok ? 0 : 1),
        points: s.points + pts,
        streak: nextStreak,
        bestStreak: Math.max(s.bestStreak, nextStreak),
      }
    })
    onAnswerResult?.(ok)
  }, [onAnswerResult])

  // iter32.J : insert un exo similaire ciblé sur les concepts faibles, après l'exo courant
  const insertSimilar = useCallback(async (weakConcepts: string[]) => {
    // L'index réel dans la liste full (non-filtrée) — on utilise question+type comme clé
    const realIdx = exos.findIndex((e) => e.question === current.question && e.type === current.type)
    const fresh = await regenerateSimilarExo({
      prevQuestion: current.question,
      prevType: kind === 'mini' ? 'mini-exo' : kind,
      weakConcepts,
      subject,
    })
    if (!fresh || !fresh.question || fresh.error) {
      setRegenError(fresh?.error || 'Régénération échouée')
      return
    }
    onInsertSimilar(realIdx >= 0 ? realIdx : exos.length - 1, {
      type: fresh.type || current.type,
      question: fresh.question,
      reponse: fresh.reponse,
      indice: fresh.indice,
      choix: fresh.choix,
      bonnes_reponses: fresh.bonnes_reponses,
      duree_sec: fresh.duree_sec,
    })
    setRegenError(null)
  }, [current, exos, kind, subject, onInsertSimilar])

  // iter32.N : régénère tout le set d'exos (LLM + nouvelles questions)
  const regenAll = useCallback(async () => {
    setRegeningAll(true)
    setRegenError(null)
    try {
      const prevQuestions = exos.map((e) => e.question).slice(0, 20)
      const sys = `Tu génères un nouveau set d'exercices BAC pour réviser, sur le MÊME sujet que les précédents mais avec des QUESTIONS DIFFÉRENTES.

Format strict : un objet JSON avec un champ "exos" qui est un array de 8 à 12 objets {type, question, reponse, indice, choix, bonnes_reponses, duree_sec} où type ∈ {flashcard, qcm, mini-exo}.

Règles :
- Les questions DOIVENT toutes être différentes des questions déjà posées.
- Mélange types (flashcard, qcm, mini-exo) avec une distribution naturelle.
- Pour qcm : 4 choix avec 1+ bonnes_reponses (index 0-based).
- Varie les angles : connaissances, application, analyse, cas réels.
- Pas de markdown, juste le JSON pur.`
      const usr = `Sujet : ${payload.synthese_20_20.titre}

Matière : ${subject}

QUESTIONS DÉJÀ POSÉES (à NE PAS répéter) :
${prevQuestions.map((q, i) => `${i + 1}. ${q}`).join('\n')}

Génère 8-12 nouveaux exercices avec des questions COMPLÈTEMENT différentes.
Réponds en JSON {"exos": [...]}.`
      const bridge = (() => { try { return getBridgeUrl() } catch { return '' } })()
      const url = bridge ? `${bridge}/proxy/ollama/api/chat` : '/api/ollama/chat'
      const ctrl = new AbortController()
      // iter34 : bump regen-all 180s → 240s pour aligner sur firstByteTimeoutMs
      // de useAcademyViewLogic — cold-start gemma3:12b peut tenir 50-90s avant
      // TTFB, et la génération de 12 exos JSON peut consommer 60-150s en plus.
      const timer = setTimeout(() => ctrl.abort('timeout'), 240_000)
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: LEARNING_EVAL_MODEL,
          messages: [
            { role: 'system', content: sys },
            { role: 'user', content: usr },
          ],
          stream: false,
          options: { temperature: 0.7, num_ctx: 8192, num_predict: 3000 },
        }),
        signal: ctrl.signal,
      })
      clearTimeout(timer)
      if (!resp.ok) {
        setRegenError(`HTTP ${resp.status}`)
        return
      }
      const data = await resp.json() as { message?: { content?: string }; response?: string }
      const text = data?.message?.content ?? data?.response ?? ''
      const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/)
      const candidate = fenced ? fenced[1] : text
      const a = candidate.indexOf('{'); const b = candidate.lastIndexOf('}')
      if (a === -1 || b <= a) { setRegenError('JSON introuvable dans la réponse'); return }
      const obj = JSON.parse(candidate.slice(a, b + 1)) as { exos?: AcademyParcoursExo[] }
      if (!Array.isArray(obj.exos) || obj.exos.length === 0) {
        setRegenError('Aucun exo retourné')
        return
      }
      onRegenAll(obj.exos)
      setIdx(0)
      setScore({ ok: 0, ko: 0, points: 0, streak: 0, bestStreak: 0 })
    } catch (e) {
      setRegenError(e instanceof Error ? e.message : String(e))
    } finally {
      setRegeningAll(false)
    }
  }, [exos, payload, subject, onRegenAll])

  return (
    <div style={{
      maxWidth: 760, margin: '0 auto',
      display: 'flex', flexDirection: 'column', gap: 20,
      position: 'relative',
    }}>
      {/* iter32.M : confetti overlay */}
      {confettiKey > 0 && <ConfettiBurst key={confettiKey} />}

      {/* Header avec score + streak + regen-all */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '4px 10px', borderRadius: 99,
            background: `linear-gradient(135deg, ${GOLD}22, oklch(0.62 0.22 295 / 0.20))`,
            border: `1px solid ${GOLD}55`,
            fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
            letterSpacing: '0.1em',
            color: GOLD, fontWeight: 700,
            marginBottom: 8,
          }}>
            🎮 Manche {idx + 1} / {total}
            {filter !== 'all' && (
              <span style={{ marginLeft: 8 }}>· {filter}</span>
            )}
          </div>
          <h2 style={{
            fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
            fontStyle: 'italic', fontWeight: 400, fontSize: 32,
            margin: 0, color: 'var(--fg, #f5f5f5)',
          }}>{score.streak >= 3 ? `🔥 Tu enchaînes !` : score.ok > 0 ? `Bien joué, on continue` : `C'est parti !`}</h2>
          <p style={{ marginTop: 6, fontSize: 13, color: 'var(--fg-dim, #aaa)', display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
            <span>Mode <strong>{kind}</strong></span>
            <span><span style={{ color: GREEN_FG }}>{score.ok} ✓</span> / <span style={{ color: RED_FG }}>{score.ko} ✗</span></span>
            <span style={{ color: GOLD, fontWeight: 700 }}>{score.points} pts</span>
            {/* iter32.M : streak compteur visible quand >= 2 */}
            {score.streak >= 2 && (
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                padding: '2px 8px', borderRadius: 99,
                background: `${GOLD}33`, color: GOLD,
                fontWeight: 700, fontSize: 12,
                border: `1px solid ${GOLD}88`,
                animation: 'streakPulse 0.6s ease',
              }}>
                <Flame size={11} /> streak {score.streak}
              </span>
            )}
            {/* iter32.M : badges */}
            {score.bestStreak >= 3 && score.streak === 0 && (
              <span style={{ fontSize: 11, color: GOLD }}>🏆 best streak {score.bestStreak}</span>
            )}
            {score.ok >= 5 && score.ko === 0 && (
              <span style={{ fontSize: 11, color: GREEN_FG }}>💎 perfect 5</span>
            )}
          </p>
        </div>
        {/* iter32.N : bouton regen all */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button type="button" onClick={() => void regenAll()} disabled={regeningAll}
            title="Génère un nouveau set d'exos avec des questions différentes (peut prendre 30-90s)."
            style={{
              padding: '8px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
              background: regeningAll ? 'var(--bg-card, rgba(255,255,255,0.04))' : `${GOLD}22`,
              color: GOLD, border: `1px solid ${GOLD}66`,
              cursor: regeningAll ? 'wait' : 'pointer', opacity: regeningAll ? 0.6 : 1,
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}>
            <Shuffle size={12} /> {regeningAll ? 'Régénération…' : 'Régénérer ces exos'}
          </button>
          {/* Progress dots */}
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', maxWidth: 280 }}>
            {filteredExos.map((_, i) => (
              <button key={i} onClick={() => setIdx(i)} title={`Exo ${i + 1}`}
                style={{
                  width: 18, height: 18, borderRadius: 4, cursor: 'pointer',
                  border: 'none',
                  background: i === idx ? GOLD : i < idx ? `${GREEN_FG}40` : 'var(--bg-card, rgba(255,255,255,0.06))',
                }} />
            ))}
          </div>
        </div>
      </div>

      {regenError && (
        <div style={{
          padding: 10, borderRadius: 6, fontSize: 12,
          background: `${RED}20`, color: RED_FG,
          border: `1px solid ${RED}55`,
        }}>
          ⚠ {regenError}
        </div>
      )}

      {/* iter35.B : bandeau aptitude — sépare visuellement entraînement et
          examen. Quand l'apprenant atteint 70%/80%, le bouton "Passer à
          l'examen réel" devient actif et lui propose de quitter le mode
          entraînement pour passer le contrôle corrigé. */}
      {typeof aptitudePct === 'number' && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 14, padding: '10px 14px', borderRadius: 10,
          background: learnerReady ? `${GREEN_FG}18` : 'rgba(255,255,255,0.04)',
          border: `1px solid ${learnerReady ? GREEN_FG : 'rgba(255,255,255,0.12)'}66`,
          flexWrap: 'wrap',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
            <span style={{
              fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
              letterSpacing: '0.12em', textTransform: 'uppercase',
              color: learnerReady ? GREEN_FG : 'var(--fg-mute, #888)',
              fontWeight: 700,
            }}>
              {learnerReady ? '✓ Apte à l\'examen' : 'Aptitude entraînement'}
            </span>
            <div style={{
              flex: 1, minWidth: 80, maxWidth: 240, height: 6, borderRadius: 3,
              background: 'rgba(255,255,255,0.08)', overflow: 'hidden',
            }}>
              <div style={{
                width: `${aptitudePct}%`, height: '100%',
                background: aptitudePct >= 70 ? GREEN_FG : aptitudePct >= 50 ? GOLD : RED_FG,
                transition: 'width 0.4s ease, background 0.4s ease',
              }} />
            </div>
            <span style={{
              fontSize: 12, fontFamily: 'var(--font-mono, monospace)',
              fontWeight: 700, color: learnerReady ? GREEN_FG : 'var(--fg-dim, #aaa)',
              minWidth: 40, textAlign: 'right',
            }}>
              {aptitudePct}%
            </span>
          </div>
          <button type="button"
            onClick={() => onProceedToExam?.()}
            disabled={!learnerReady}
            title={learnerReady
              ? 'Lance l\'examen blanc corrigé'
              : `Continue l'entraînement — objectif 70% sur 3 derniers ou 80% sur 5 consécutifs.`}
            style={{
              padding: '8px 14px', borderRadius: 8,
              background: learnerReady
                ? `linear-gradient(135deg, ${GREEN_FG}AA, ${GOLD}AA)`
                : 'transparent',
              color: learnerReady ? '#0a0a0a' : 'var(--fg-mute, #555)',
              border: `1px solid ${learnerReady ? GREEN_FG : 'rgba(255,255,255,0.18)'}`,
              cursor: learnerReady ? 'pointer' : 'not-allowed',
              opacity: learnerReady ? 1 : 0.55,
              fontSize: 12, fontWeight: 700,
              fontFamily: 'var(--font-mono, monospace)',
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}>
            🎓 {learnerReady ? 'Passer à l\'examen réel' : 'Examen verrouillé'}
          </button>
        </div>
      )}

      {/* Per-type renderer — iter32.J : passe insertSimilar pour bouton "Refaire similaire" */}
      {kind === 'flashcard' && (
        <FlashcardExo
          key={`${idx}-${current.question.slice(0, 30)}`}
          exo={current}
          onAnswer={(ok) => recordResult(ok, ok ? 50 : 0)}
          onRequestSimilar={() => void insertSimilar([])}
        />
      )}
      {kind === 'qcm' && (
        <QcmExo
          key={`${idx}-${current.question.slice(0, 30)}`}
          exo={current}
          subject={subject}
          onAnswer={(ok, pts) => recordResult(ok, pts)}
          onRequestSimilar={(weak) => void insertSimilar(weak)}
        />
      )}
      {kind === 'mini' && (
        <MiniExo
          key={`${idx}-${current.question.slice(0, 30)}`}
          exo={current}
          subject={subject}
          onScored={(ok, pts) => recordResult(ok, pts)}
          onRequestSimilar={(weak) => void insertSimilar(weak)}
          /* iter33.D : passe language pour que le micro STT cale Voxtral */
          language={payload.language}
        />
      )}

      {/* Exo-level nav */}
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginTop: 8 }}>
        <button type="button" onClick={prev} disabled={idx === 0}
          style={{
            padding: '8px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
            background: 'transparent', color: 'var(--fg, #f5f5f5)',
            border: '1px solid var(--line, rgba(255,255,255,0.18))',
            cursor: idx === 0 ? 'not-allowed' : 'pointer', opacity: idx === 0 ? 0.4 : 1,
          }}>← Précédent</button>
        <button type="button" onClick={next} disabled={idx >= total - 1}
          style={{
            padding: '8px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
            background: idx >= total - 1 ? 'transparent' : GOLD,
            color: idx >= total - 1 ? 'var(--fg, #f5f5f5)' : '#0a0a0a',
            border: idx >= total - 1 ? '1px solid var(--line, rgba(255,255,255,0.18))' : 'none',
            cursor: idx >= total - 1 ? 'not-allowed' : 'pointer', opacity: idx >= total - 1 ? 0.4 : 1,
          }}>Exo suivant →</button>
      </div>
    </div>
  )
}

// iter31.F.2 — Flashcard recto/verso flip card · iter32.J : bouton "exo similaire"
function FlashcardExo({ exo, onAnswer, onRequestSimilar }: {
  exo: { question: string; reponse: string; indice?: string }
  onAnswer: (ok: boolean) => void
  onRequestSimilar?: () => void
}) {
  const [revealed, setRevealed] = useState(false)
  const [graded, setGraded] = useState<'ok' | 'ko' | null>(null)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div onClick={() => !graded && setRevealed((r) => !r)}
        style={{
          minHeight: 220, padding: 24, borderRadius: 12,
          background: revealed ? `${GREEN_FG}10` : 'var(--bg-card, rgba(255,255,255,0.04))',
          border: `2px solid ${revealed ? GREEN_FG : 'oklch(0.72 0.12 200 / 0.40)'}`,
          cursor: graded ? 'default' : 'pointer',
          display: 'flex', flexDirection: 'column', justifyContent: 'center',
          gap: 12, transition: 'background 0.2s, border 0.2s',
        }}>
        <div style={{
          fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
          letterSpacing: '0.20em', textTransform: 'uppercase',
          color: 'var(--fg-mute, #888)',
        }}>
          {revealed ? '✓ Réponse' : '🃏 Flashcard — clique pour retourner'}
        </div>
        <div style={{ fontSize: 18, lineHeight: 1.5, fontWeight: revealed ? 400 : 600 }}>
          {revealed ? exo.reponse : exo.question}
        </div>
        {revealed && exo.indice && (
          <div style={{ fontSize: 12, fontStyle: 'italic', color: 'var(--fg-mute, #888)' }}>
            💡 {exo.indice}
          </div>
        )}
      </div>
      {revealed && !graded && (
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => { setGraded('ok'); onAnswer(true) }}
            style={{ flex: 1, padding: '10px 14px', borderRadius: 6, fontSize: 13, fontWeight: 600, background: `${GREEN_FG}30`, color: GREEN_FG, border: `1px solid ${GREEN_FG}80`, cursor: 'pointer' }}>
            ✓ Je savais
          </button>
          <button onClick={() => { setGraded('ko'); onAnswer(false) }}
            style={{ flex: 1, padding: '10px 14px', borderRadius: 6, fontSize: 13, fontWeight: 600, background: `${RED_FG}30`, color: RED_FG, border: `1px solid ${RED_FG}80`, cursor: 'pointer' }}>
            ✗ À revoir
          </button>
        </div>
      )}
      {graded && (
        <div style={{ fontSize: 12, color: graded === 'ok' ? GREEN_FG : RED_FG, fontWeight: 600, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span>{graded === 'ok' ? '✓ Validé — passe au suivant.' : '✗ Marqué à revoir — passe au suivant et reviens dessus.'}</span>
          {/* iter32.J : bouton "Refaire un similaire" si l'utilisateur a marqué KO */}
          {graded === 'ko' && onRequestSimilar && (
            <button onClick={onRequestSimilar}
              style={{
                padding: '6px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                background: `${GOLD}22`, color: GOLD, border: `1px solid ${GOLD}66`,
                cursor: 'pointer',
              }}>
              🔄 Refaire un similaire
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// iter31.G — QCM Kahoot-style : 4 cases A/B/C/D cliquables, single ou multi,
// timer countdown + bonus vitesse, points calculés selon temps restant.
// iter32.J + H : bouton "Refaire similaire" + semantic eval pour réponse libre.
function QcmExo({ exo, onAnswer, subject, onRequestSimilar }: {
  exo: AcademyParcoursExo
  subject?: string
  onRequestSimilar?: (weakConcepts: string[]) => void
  onAnswer: (ok: boolean, points: number) => void
}) {
  // Fallback : si le LLM n'a pas généré de choix (anciens parcours), on
  // construit 3 distracteurs basiques à partir du texte de la réponse.
  const [choices, correctIndexes] = useMemo<[string[], number[]]>(() => {
    if (Array.isArray(exo.choix) && exo.choix.length >= 2 && Array.isArray(exo.bonnes_reponses) && exo.bonnes_reponses.length > 0) {
      return [exo.choix, exo.bonnes_reponses]
    }
    // Fallback synth: 1 vraie + 3 distracteurs génériques. Le user verra
    // que c'est une session legacy, mais l'UI reste utilisable.
    const truth = exo.reponse
    const distractors = [
      `Aucune des autres réponses`,
      `Plusieurs des autres réponses`,
      `Réponse contraire à « ${truth.slice(0, 40)}${truth.length > 40 ? '…' : ''} »`,
    ]
    const all = [truth, ...distractors]
    // shuffle stable per exo (use question hash)
    let seed = 0
    for (let i = 0; i < exo.question.length; i++) seed = (seed * 31 + exo.question.charCodeAt(i)) | 0
    const order = [0, 1, 2, 3].sort((a, b) => ((seed * (a + 1)) % 7) - ((seed * (b + 1)) % 7))
    const shuffled = order.map((i) => all[i])
    const correct = order.indexOf(0)
    return [shuffled, [correct]]
  }, [exo])

  const isMulti = correctIndexes.length > 1
  const totalSec = Math.max(8, Math.min(60, exo.duree_sec ?? 20))
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [submitted, setSubmitted] = useState(false)
  const [secLeft, setSecLeft] = useState(totalSec)
  const [verdict, setVerdict] = useState<'ok' | 'partial' | 'ko' | 'timeout' | null>(null)
  const [pointsEarned, setPointsEarned] = useState(0)

  // Timer countdown
  useEffect(() => {
    if (submitted) return
    if (secLeft <= 0) {
      setSubmitted(true)
      setVerdict('timeout')
      onAnswer(false, 0)
      return
    }
    const id = setTimeout(() => setSecLeft((s) => s - 1), 1000)
    return () => clearTimeout(id)
  }, [secLeft, submitted, onAnswer])

  const toggle = (i: number) => {
    if (submitted) return
    setSelected((prev) => {
      const next = new Set(prev)
      if (isMulti) {
        if (next.has(i)) next.delete(i); else next.add(i)
      } else {
        next.clear(); next.add(i)
      }
      return next
    })
  }

  // iter36 : crédit partiel + verdict 'partial' quand l'apprenant a sélectionné
  // un sous-ensemble strict des bonnes réponses (aucun faux positif). Permet
  // de ne pas pénaliser à 0 quand 2 réponses étaient attendues mais qu'on n'en
  // a vu qu'une — tout en restant exigeant si une mauvaise est cochée.
  const handleSubmit = () => {
    if (submitted || selected.size === 0) return
    const sel = Array.from(selected).sort()
    const exp = [...correctIndexes].sort()
    const fullMatch = sel.length === exp.length && sel.every((v, i) => v === exp[i])
    const allSelectedAreCorrect = sel.every((i) => correctIndexes.includes(i))
    const correctSelectedCount = sel.filter((i) => correctIndexes.includes(i)).length
    let outcome: 'ok' | 'partial' | 'ko'
    let pts: number
    if (fullMatch) {
      outcome = 'ok'
      const base = 100
      const bonus = Math.floor((secLeft / totalSec) * 50)
      pts = base + bonus
    } else if (allSelectedAreCorrect && correctSelectedCount > 0 && exp.length > 1) {
      // Sous-ensemble strict des bonnes réponses (aucun faux positif) : crédit
      // partiel proportionnel.
      outcome = 'partial'
      pts = Math.round((correctSelectedCount / exp.length) * 100 * 0.6)  // max 60% en partiel
    } else {
      outcome = 'ko'
      pts = 0
    }
    setPointsEarned(pts)
    setSubmitted(true)
    setVerdict(outcome === 'ok' ? 'ok' : outcome === 'partial' ? 'partial' : 'ko')
    // Pour l'aptitude tracking : partial compte comme demi-réussite (ok=false
    // mais évite d'envoyer un signal trop pessimiste — onAnswer reçoit false
    // mais avec des points non-nuls donc le score visible reflète l'effort).
    onAnswer(outcome === 'ok', pts)
  }

  const letter = (i: number) => String.fromCharCode(65 + i)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Timer + indicateur multi (iter36 : count visible + couleur forte
          quand multi pour éviter qu'on croit qu'une seule réponse suffit) */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: isMulti ? '4px 10px' : 0, borderRadius: 99,
          background: isMulti ? 'oklch(0.74 0.13 90 / 0.18)' : 'transparent',
          border: isMulti ? `1px solid oklch(0.74 0.13 90 / 0.5)` : 'none',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          letterSpacing: '0.16em', textTransform: 'uppercase',
          color: isMulti ? 'oklch(0.86 0.16 90)' : 'oklch(0.78 0.16 60)',
          fontWeight: 700,
        }}>
          🎯 QCM · {isMulti
            ? `${correctIndexes.length} bonnes réponses à cocher`
            : `Une seule bonne réponse`}
        </div>
        <div style={{
          padding: '4px 12px', borderRadius: 999,
          background: secLeft < 5 ? `${RED_FG}30` : secLeft < totalSec / 2 ? `${GOLD}30` : 'var(--bg-card, rgba(255,255,255,0.06))',
          color: secLeft < 5 ? RED_FG : 'var(--fg, #f5f5f5)',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 13, fontWeight: 700,
          border: `1px solid ${secLeft < 5 ? RED_FG : 'var(--line, rgba(255,255,255,0.18))'}`,
        }}>
          ⏱ {secLeft}s
        </div>
      </div>

      <div style={{
        padding: 20, borderRadius: 10,
        background: 'var(--bg-card, rgba(255,255,255,0.04))',
        border: `1px solid oklch(0.78 0.16 60 / 0.40)`,
      }}>
        <div style={{ fontSize: 16, lineHeight: 1.5, fontWeight: 600, marginBottom: 16 }}>
          {exo.question}
        </div>

        {/* 4 cases cliquables */}
        <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(2, 1fr)' }}>
          {choices.map((c, i) => {
            const isSelected = selected.has(i)
            const isCorrect = correctIndexes.includes(i)
            const showResult = submitted
            let bg = 'var(--bg-raised, rgba(255,255,255,0.05))'
            let bord = 'var(--line, rgba(255,255,255,0.18))'
            if (showResult) {
              if (isCorrect) { bg = `${GREEN_FG}25`; bord = GREEN_FG }
              else if (isSelected && !isCorrect) { bg = `${RED_FG}25`; bord = RED_FG }
            } else if (isSelected) {
              bg = `${GOLD}25`; bord = GOLD
            }
            return (
              <button key={i} type="button" onClick={() => toggle(i)} disabled={submitted}
                style={{
                  textAlign: 'left', padding: '14px 16px', borderRadius: 8,
                  background: bg, border: `2px solid ${bord}`,
                  color: 'var(--fg, #f5f5f5)', fontFamily: 'inherit',
                  fontSize: 14, lineHeight: 1.4,
                  cursor: submitted ? 'default' : 'pointer',
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                  transition: 'background 0.15s, border 0.15s',
                }}>
                <span style={{
                  flexShrink: 0, width: 26, height: 26, borderRadius: 6,
                  background: showResult ? (isCorrect ? GREEN_FG : isSelected ? RED_FG : 'transparent') : isSelected ? GOLD : 'var(--bg-input, rgba(255,255,255,0.06))',
                  color: showResult && (isCorrect || isSelected) ? '#0a0a0a' : isSelected ? '#0a0a0a' : 'var(--fg-dim, #aaa)',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: 700, fontSize: 13,
                }}>{showResult && isCorrect ? '✓' : showResult && isSelected ? '✗' : letter(i)}</span>
                <span>{c}</span>
              </button>
            )
          })}
        </div>

        {!submitted ? (
          <>
            {/* iter36 : aide au comptage des sélections vs attendues */}
            {isMulti && (
              <div style={{
                marginTop: 12, padding: '8px 12px', borderRadius: 6,
                background: selected.size === correctIndexes.length
                  ? `${GREEN_FG}10`
                  : selected.size > 0
                    ? `oklch(0.74 0.13 90 / 0.10)`
                    : 'transparent',
                border: `1px dashed ${selected.size === correctIndexes.length ? GREEN_FG : 'rgba(255,255,255,0.18)'}66`,
                fontSize: 11, color: 'var(--fg-dim, #aaa)',
                fontFamily: 'var(--font-mono, monospace)',
                letterSpacing: '0.06em',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8,
              }}>
                <span>
                  {selected.size === 0
                    ? `Sélectionne ${correctIndexes.length} cases.`
                    : selected.size < correctIndexes.length
                      ? `${selected.size} / ${correctIndexes.length} cochées — il en manque ${correctIndexes.length - selected.size}.`
                      : selected.size === correctIndexes.length
                        ? `✓ Tu as coché ${correctIndexes.length} cases — tu peux valider.`
                        : `Trop de cases (${selected.size}) — n'en garde que ${correctIndexes.length}.`}
                </span>
              </div>
            )}
            <button onClick={handleSubmit} disabled={selected.size === 0}
              style={{
                marginTop: 10, width: '100%', padding: '10px 14px', borderRadius: 6, fontSize: 13, fontWeight: 600,
                background: GOLD, color: '#0a0a0a', border: 'none', cursor: 'pointer',
                opacity: selected.size === 0 ? 0.4 : 1,
              }}>
              Valider {isMulti && selected.size > 0 ? `(${selected.size}/${correctIndexes.length})` : ''}
            </button>
          </>
        ) : (
          <div style={{ marginTop: 14 }}>
            <div style={{
              padding: 12, borderRadius: 6,
              background:
                verdict === 'ok' ? `${GREEN_FG}15` :
                verdict === 'partial' ? `${GOLD}18` :
                `${RED_FG}15`,
              fontSize: 13, fontWeight: 600,
              color:
                verdict === 'ok' ? GREEN_FG :
                verdict === 'partial' ? GOLD :
                RED_FG,
              display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8,
              border: `1px solid ${verdict === 'partial' ? `${GOLD}55` : 'transparent'}`,
            }}>
              <span>
                {verdict === 'ok' ? `✓ Bonne réponse ! +${pointsEarned} pts` :
                 verdict === 'partial' ? `~ Partiel : tu as eu ${pointsEarned} pts (sous-ensemble correct mais incomplet — il fallait ${correctIndexes.length} cases)` :
                 verdict === 'timeout' ? '⏱ Temps écoulé' : '✗ Mauvaise réponse'}
              </span>
              {verdict === 'ok' && pointsEarned > 100 && (
                <span style={{ fontSize: 11, color: GOLD }}>⚡ Bonus vitesse +{pointsEarned - 100}</span>
              )}
            </div>
            {exo.indice && verdict !== 'ok' && (
              <div style={{ marginTop: 8, padding: 8, fontSize: 11, fontStyle: 'italic', color: 'var(--fg-mute, #888)', background: `${GOLD}10`, borderRadius: 4 }}>
                💡 Indice : {exo.indice}
              </div>
            )}
            {/* iter32.J : si verdict KO ou timeout, propose un exo similaire */}
            {(verdict === 'ko' || verdict === 'timeout') && onRequestSimilar && (
              <button onClick={() => onRequestSimilar([exo.question.split(' ').slice(0, 4).join(' ')])}
                style={{
                  marginTop: 10, padding: '8px 12px', borderRadius: 4, fontSize: 12, fontWeight: 600,
                  background: `${GOLD}22`, color: GOLD, border: `1px solid ${GOLD}66`,
                  cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6,
                }}>
                🔄 Refaire un exo similaire (différente question)
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// iter32.H + J — Mini-exo avec eval LLM sémantique (pas exact match)
// + bouton "Refaire un similaire" si score < 70.
// iter33.D : si exo.speak === true, l'UI rend un bouton micro au lieu d'une
// textarea. L'audio est enregistré via MediaRecorder, transcrit via Voxtral
// STT (/api/voice/stt), puis le transcript devient la "réponse écrite" qui
// est évaluée sémantiquement comme avant.
function MiniExo({ exo, onScored, subject, onRequestSimilar, language }: {
  exo: { question: string; reponse: string; indice?: string; speak?: boolean }
  onScored: (ok: boolean, points: number) => void
  subject?: string
  onRequestSimilar?: (weakConcepts: string[]) => void
  /** iter33.D : langue cible pour STT (ex: 'anglais' → 'en'). Si absent, fr. */
  language?: string
}) {
  const [draft, setDraft] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [evalResult, setEvalResult] = useState<SemanticEvalResult | null>(null)

  // iter33.D : état audio
  const [recording, setRecording] = useState(false)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [transcribing, setTranscribing] = useState(false)
  const [recError, setRecError] = useState<string | null>(null)
  const [recSec, setRecSec] = useState(0)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioStreamRef = useRef<MediaStream | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const recTickRef = useRef<number | null>(null)

  // Cleanup à l'unmount
  useEffect(() => () => {
    try { mediaRecorderRef.current?.stop() } catch {}
    audioStreamRef.current?.getTracks().forEach((t) => t.stop())
    if (recTickRef.current) window.clearInterval(recTickRef.current)
    if (audioUrl) URL.revokeObjectURL(audioUrl)
  }, [audioUrl])

  const langIsoMap: Record<string, string> = {
    anglais: 'en', english: 'en',
    espagnol: 'es', spanish: 'es',
    italien: 'it', italian: 'it',
    allemand: 'de', german: 'de',
    portugais: 'pt', portuguese: 'pt',
    chinois: 'zh', chinese: 'zh', mandarin: 'zh',
    japonais: 'ja', japanese: 'ja',
    arabe: 'ar', arabic: 'ar',
    russe: 'ru', russian: 'ru',
    français: 'fr', francais: 'fr', french: 'fr', fle: 'fr',
  }
  const sttLang = language ? (langIsoMap[language.toLowerCase().trim()] || 'fr') : 'fr'

  const startRec = useCallback(async () => {
    setRecError(null)
    if (audioUrl) { URL.revokeObjectURL(audioUrl); setAudioUrl(null) }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioStreamRef.current = stream
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      audioChunksRef.current = []
      mr.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data) }
      mr.start(1000)
      mediaRecorderRef.current = mr
      setRecording(true)
      setRecSec(0)
      recTickRef.current = window.setInterval(() => setRecSec((s) => s + 1), 1000)
    } catch (e) {
      setRecError(`Mic refusé : ${e instanceof Error ? e.message : String(e)}`)
    }
  }, [audioUrl])

  const stopRec = useCallback(async () => {
    setRecording(false)
    if (recTickRef.current) { window.clearInterval(recTickRef.current); recTickRef.current = null }
    const mr = mediaRecorderRef.current
    if (!mr || mr.state === 'inactive') return
    await new Promise<void>((resolve) => {
      const handler = () => { mr.removeEventListener('stop', handler); resolve() }
      mr.addEventListener('stop', handler)
      mr.stop()
    })
    audioStreamRef.current?.getTracks().forEach((t) => t.stop())
    audioStreamRef.current = null
    const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
    setAudioUrl(URL.createObjectURL(blob))
    // STT
    setTranscribing(true)
    try {
      const fd = new FormData()
      fd.append('audio', blob, 'mini-speak.webm')
      fd.append('language', sttLang)
      const bridge = (() => { try { return getBridgeUrl() } catch { return '' } })()
      const url = bridge ? `${bridge}/api/voice/stt` : '/api/voice/stt'
      const r = await fetch(url, { method: 'POST', body: fd })
      const data = await r.json() as { ok?: boolean; text?: string; error?: string }
      if (data.ok !== false && data.text) {
        setDraft(data.text)
      } else {
        setRecError(`STT : ${data.error || 'pas de transcription'}`)
      }
    } catch (e) {
      setRecError(`STT injoignable : ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setTranscribing(false)
    }
  }, [sttLang])

  const handleSubmit = async () => {
    if (submitting || !draft.trim()) return
    setSubmitting(true)
    try {
      const r = await evaluateAnswerSemantically({
        question: exo.question, expected: exo.reponse,
        userAnswer: draft, subject, indice: exo.indice,
      })
      setEvalResult(r)
      // iter32.H : points proportionnels au score sémantique. 0..100 → 0..100 pts.
      onScored(r.ok, Math.round(r.score))
    } finally {
      setSubmitting(false)
    }
  }
  const speakMode = !!exo.speak
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{
        padding: 20, borderRadius: 10,
        background: 'var(--bg-card, rgba(255,255,255,0.04))',
        border: `1px solid ${speakMode ? GOLD : RED_FG}40`,
      }}>
        <div style={{
          fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
          letterSpacing: '0.20em', textTransform: 'uppercase',
          color: speakMode ? GOLD : RED_FG, marginBottom: 8,
        }}>
          {speakMode
            ? `🎤 Mini-exo oral · réponds à voix haute${language ? ` en ${language}` : ''}`
            : '✍ Mini-exercice de rédaction (corrigé par IA, pas par mots exacts)'}
        </div>
        <div style={{ fontSize: 16, lineHeight: 1.5, fontWeight: 600, marginBottom: 14 }}>
          {exo.question}
        </div>

        {/* iter33.D : bloc micro pour speakMode, sinon textarea classique */}
        {speakMode ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {recError && (
              <div style={{ padding: 8, borderRadius: 4, fontSize: 11, background: `${RED}20`, color: RED_FG }}>
                ⚠ {recError}
              </div>
            )}
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              {!recording && !audioUrl && (
                <button onClick={() => void startRec()} disabled={!!evalResult || transcribing}
                  style={{
                    padding: '10px 18px', borderRadius: 99, fontSize: 13, fontWeight: 700,
                    background: `${GOLD}33`, color: GOLD, border: `1px solid ${GOLD}88`,
                    cursor: evalResult || transcribing ? 'not-allowed' : 'pointer',
                    display: 'inline-flex', alignItems: 'center', gap: 8,
                  }}>
                  <Mic size={14} /> Enregistrer ma réponse
                </button>
              )}
              {recording && (
                <>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: 8,
                    padding: '6px 12px', borderRadius: 99,
                    background: `${RED}33`, color: RED_FG,
                    fontFamily: 'var(--font-mono, monospace)', fontSize: 13, fontWeight: 700,
                  }}>
                    <span style={{ width: 10, height: 10, borderRadius: 99, background: RED_FG, animation: 'streakPulse 1s infinite' }} />
                    {String(Math.floor(recSec / 60)).padStart(2, '0')}:{String(recSec % 60).padStart(2, '0')} en cours
                  </span>
                  <button onClick={() => void stopRec()}
                    style={{
                      padding: '8px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                      background: `${GREEN_FG}30`, color: GREEN_FG,
                      border: `1px solid ${GREEN_FG}80`, cursor: 'pointer',
                    }}>
                    ✓ Stop & transcrire
                  </button>
                </>
              )}
              {!recording && audioUrl && (
                <>
                  <audio controls src={audioUrl} style={{ height: 32 }} />
                  <button onClick={() => void startRec()} disabled={!!evalResult}
                    style={{
                      padding: '6px 12px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                      background: 'transparent', color: 'var(--fg-dim, #aaa)',
                      border: '1px solid var(--line, rgba(255,255,255,0.18))',
                      cursor: evalResult ? 'not-allowed' : 'pointer',
                    }}>
                    🔄 Refaire
                  </button>
                </>
              )}
            </div>
            {transcribing && (
              <div style={{ fontSize: 12, color: 'var(--fg-dim, #aaa)' }}>
                ⏳ Transcription via Voxtral…
              </div>
            )}
            {draft && (
              <div style={{
                padding: 10, fontSize: 13, lineHeight: 1.5, borderRadius: 6,
                background: 'var(--bg-input, rgba(255,255,255,0.04))',
                border: `1px solid ${GREEN_FG}33`,
              }}>
                <div style={{ fontSize: 10, color: 'var(--fg-mute, #888)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.18em' }}>
                  Transcription
                </div>
                {draft}
              </div>
            )}
            {/* L'élève peut éditer la transcription si STT a mal compris */}
            {draft && !evalResult && (
              <textarea value={draft} onChange={(e) => setDraft(e.target.value)}
                placeholder="Édite si la transcription est imprécise"
                disabled={submitting} rows={3}
                style={{
                  width: '100%', padding: 8, fontSize: 12, borderRadius: 6,
                  background: 'var(--bg-input, rgba(255,255,255,0.04))',
                  color: 'var(--fg, #f5f5f5)',
                  border: '1px solid var(--line, rgba(255,255,255,0.18))',
                  fontFamily: 'inherit', resize: 'vertical',
                }} />
            )}
          </div>
        ) : (
          <textarea value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="Rédige ta réponse en tes propres mots — l'IA évalue le sens, pas les mots exacts. (3-5 lignes)"
            disabled={submitting || !!evalResult} rows={5}
            style={{
              width: '100%', padding: 10, fontSize: 13, borderRadius: 6,
              background: 'var(--bg-input, rgba(255,255,255,0.04))',
              color: 'var(--fg, #f5f5f5)',
              border: `1px solid var(--line, rgba(255,255,255,0.18))`,
              fontFamily: 'inherit', resize: 'vertical',
            }} />
        )}

        {!evalResult ? (
          <button onClick={handleSubmit} disabled={!draft.trim() || submitting || recording || transcribing}
            style={{
              marginTop: 10, padding: '8px 14px', borderRadius: 6, fontSize: 13, fontWeight: 600,
              background: GOLD, color: '#0a0a0a', border: 'none', cursor: 'pointer',
              opacity: !draft.trim() || submitting || recording || transcribing ? 0.4 : 1,
            }}>{submitting ? 'L\'IA évalue ta réponse…' : 'Soumettre pour correction IA'}</button>
        ) : (
          <div style={{ marginTop: 12 }}>
            <div style={{
              padding: 12, borderRadius: 6, marginBottom: 8,
              background: evalResult.score >= 70 ? `${GREEN_FG}15` : evalResult.score >= 40 ? `${GOLD}15` : `${RED_FG}15`,
              fontSize: 13,
              color: evalResult.score >= 70 ? GREEN_FG : evalResult.score >= 40 ? 'oklch(0.74 0.13 90)' : RED_FG,
              fontWeight: 600,
            }}>
              Score IA : <span style={{ fontSize: 18 }}>{evalResult.score}/100</span> {evalResult.score >= 70 ? '✓' : evalResult.score >= 40 ? '~' : '✗'}
            </div>
            {evalResult.feedback && (
              <div style={{ fontSize: 12, padding: 10, borderRadius: 6, background: 'var(--bg-input, rgba(255,255,255,0.04))', marginBottom: 8, lineHeight: 1.5 }}>
                <strong>Retour IA :</strong> {evalResult.feedback}
              </div>
            )}
            <div style={{ fontSize: 13, padding: 10, borderRadius: 6, background: `${GREEN_FG}10`, marginBottom: 8 }}>
              <strong style={{ color: GREEN_FG }}>Correction attendue :</strong>
              <div style={{ marginTop: 4 }}>{exo.reponse}</div>
            </div>
            {evalResult.weakConcepts.length > 0 && (
              <div style={{ fontSize: 11, padding: 8, borderRadius: 4, background: `${RED_FG}10`, marginBottom: 8 }}>
                <strong style={{ color: RED_FG }}>À retravailler :</strong> {evalResult.weakConcepts.join(', ')}
              </div>
            )}
            {exo.indice && (
              <div style={{ marginBottom: 8, fontSize: 11, fontStyle: 'italic', color: 'var(--fg-mute, #888)' }}>
                💡 {exo.indice}
              </div>
            )}
            {/* iter32.J : score < 70 → propose un nouvel exo ciblé */}
            {evalResult.score < 70 && onRequestSimilar && (
              <button
                onClick={() => onRequestSimilar(evalResult.weakConcepts || [])}
                style={{
                  marginTop: 4, padding: '8px 12px', borderRadius: 4, fontSize: 12, fontWeight: 600,
                  background: `${GOLD}22`, color: GOLD, border: `1px solid ${GOLD}66`,
                  cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6,
                }}>
                🔄 Refaire un exo similaire {evalResult.weakConcepts.length > 0 ? `(ciblé : ${evalResult.weakConcepts.slice(0, 2).join(', ')})` : ''}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// iter32.K — Menu "Mode d'entraînement" : cards cliquables qui choisissent
// un sous-ensemble d'exos (ou l'oral / l'examen) au lieu de tout enchaîner.
function MenuStep({
  onChoose,
  hasExos,
  stepKinds,
}: {
  onChoose: (filter: ExoFilter, target: StepKind) => void
  hasExos: boolean
  stepKinds: StepKind[]
}) {
  type Card = {
    icon: string
    title: string
    sub: string
    filter: ExoFilter
    target: StepKind
    color: string
    enabled: boolean
  }
  const cards: Card[] = [
    {
      icon: '🎯',
      title: 'QCM rapide',
      sub: 'Kahoot-style · 4 cases · timer · bonus vitesse',
      filter: 'qcm',
      target: 'exos',
      color: 'oklch(0.78 0.16 60)',
      enabled: hasExos,
    },
    {
      icon: '✍',
      title: 'Mini-exos rédaction',
      sub: 'Réponse libre · IA évalue le SENS, pas les mots exacts',
      filter: 'mini',
      target: 'exos',
      color: RED_FG,
      enabled: hasExos,
    },
    {
      icon: '🃏',
      title: 'Flashcards révision',
      sub: 'Recto/verso · auto-grade je-savais / à-revoir',
      filter: 'flashcard',
      target: 'exos',
      color: 'oklch(0.72 0.12 200)',
      enabled: hasExos,
    },
    // iter35.B : carte "Examen blanc" RETIRÉE du menu d'entraînement.
    // L'examen est maintenant un step séparé verrouillé par aptitude
    // — on y accède via le bouton "Passer à l'examen réel" dans la
    // barre d'aptitude (ExosStep) ou via Suivant en footer (gated).
    {
      icon: '🔄',
      title: 'Tout mélanger',
      sub: 'Tous les types d\'exos dans l\'ordre du payload',
      filter: 'all',
      target: 'exos',
      color: GOLD,
      enabled: hasExos,
    },
  ]
  void stepKinds  // (kept for backward-compat callers)
  const isGameMode = useLearningSessionStore((s2) => s2.parcours?.profile?.examFormat === 'jeu')
  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '4px 10px', borderRadius: 99,
          background: 'oklch(0.62 0.22 295 / 0.2)',
          border: '1px solid oklch(0.62 0.22 295 / 0.5)',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          letterSpacing: '0.1em',
          color: 'oklch(0.78 0.16 295)', fontWeight: 700,
          marginBottom: 10,
        }}>
          {isGameMode ? '🎲 Choix de l\'épreuve · Manche 3' : '🕹 Choisis ton terrain de jeu'}
        </div>
        <h2 style={{
          fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
          fontStyle: 'italic', fontWeight: 400, fontSize: 38,
          margin: 0, color: 'var(--fg, #f5f5f5)',
        }}>
          {isGameMode ? 'Quelle épreuve veux-tu affronter ?' : "Allez, on s'amuse un peu ?"}
        </h2>
        <p style={{ marginTop: 6, fontSize: 13, color: 'var(--fg-dim, #aaa)' }}>
          {isGameMode
            ? "Le carnet de bord est plié, à toi de jouer. Choisis l'épreuve qui te tente — chaque succès te rapproche du Boss final."
            : "Tu as digéré les fiches 💪. Maintenant on transforme ça en réflexes. Pas de panique — tu peux revenir au menu à tout moment, et le coach 🪄 t'aide si tu coinces."}
        </p>
      </div>

      <div style={{
        display: 'grid', gap: 14,
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
      }}>
        {cards.map((c) => (
          <button
            key={`${c.title}-${c.target}-${c.filter}`}
            type="button"
            disabled={!c.enabled}
            onClick={() => c.enabled && onChoose(c.filter, c.target)}
            style={{
              padding: 18, borderRadius: 10, textAlign: 'left',
              background: c.enabled ? 'var(--bg-card, rgba(255,255,255,0.04))' : 'var(--bg-card, rgba(255,255,255,0.02))',
              border: `2px solid ${c.enabled ? `${c.color}55` : 'var(--line, rgba(255,255,255,0.10))'}`,
              cursor: c.enabled ? 'pointer' : 'not-allowed', opacity: c.enabled ? 1 : 0.4,
              color: 'var(--fg, #f5f5f5)',
              fontFamily: 'inherit',
              transition: 'transform 0.15s, border 0.15s, background 0.15s',
              display: 'flex', flexDirection: 'column', gap: 8,
              minHeight: 130,
            }}
            onMouseEnter={(e) => { if (c.enabled) (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)' }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.transform = '' }}
          >
            <div style={{ fontSize: 32 }}>{c.icon}</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: c.color }}>{c.title}</div>
            <div style={{ fontSize: 12, color: 'var(--fg-dim, #aaa)', lineHeight: 1.4 }}>{c.sub}</div>
            {!c.enabled && (
              <div style={{ fontSize: 10, color: RED_FG, fontStyle: 'italic' }}>
                Indisponible (pas d'exos générés)
              </div>
            )}
          </button>
        ))}
      </div>

      <div style={{
        padding: 14, borderRadius: 8,
        background: `${GOLD}10`, border: `1px solid ${GOLD}44`,
        fontSize: 12, color: 'var(--fg-dim, #ccc)', lineHeight: 1.5,
      }}>
        💡 <strong>Astuce :</strong> dans chaque mode, si tu rates un exo, l'IA te propose
        d'en refaire un similaire mais avec une question différente — pour t'entraîner sur
        le concept jusqu'à ce qu'il soit acquis.
      </div>
    </div>
  )
}

// iter32.M — burst de confetti CSS pur (pas de dep canvas-confetti).
// Génère 24 particules aléatoires qui retombent en 1.4s. La key parente
// re-monte à chaque trigger, donc l'animation est rejouée à chaque hit.
function ConfettiBurst() {
  const particles = useMemo(() => {
    const colors = ['#ffd44d', '#ff6a3d', '#3dd17a', '#3da9ff', '#d83dff', '#fff04d']
    return Array.from({ length: 28 }, (_, i) => ({
      id: i,
      left: Math.random() * 100,
      delay: Math.random() * 0.15,
      duration: 1.0 + Math.random() * 0.6,
      color: colors[Math.floor(Math.random() * colors.length)],
      rotate: Math.random() * 360,
      drift: (Math.random() - 0.5) * 200,
    }))
  }, [])
  return (
    <>
      <style>{`
        @keyframes confettiFall {
          0% { transform: translate(0, -20px) rotate(0deg); opacity: 1; }
          100% { transform: translate(var(--drift, 0px), 100vh) rotate(720deg); opacity: 0; }
        }
        @keyframes streakPulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.18); }
        }
      `}</style>
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden',
        zIndex: 100,
      }}>
        {particles.map((p) => (
          <div key={p.id} style={{
            position: 'absolute', top: 30,
            left: `${p.left}%`,
            width: 8, height: 12,
            background: p.color,
            transform: `rotate(${p.rotate}deg)`,
            animation: `confettiFall ${p.duration}s cubic-bezier(0.4, 0.6, 0.6, 1) ${p.delay}s forwards`,
            // @ts-expect-error CSS custom prop
            '--drift': `${p.drift}px`,
            borderRadius: 2,
          }} />
        ))}
      </div>
    </>
  )
}

// iter33 — ExamOralStep : VRAIE PASSATION ORALE BAC ETLV / langue.
// (Repurposed from iter32.L OralStep — l'oral n'est plus un step en plus,
// c'est l'EXAMEN final quand is_oral est true.)
//
// Le support de référence (lessonText / photo de la feuille) est affiché
// en haut comme "ce sur quoi tu vas être interrogé". Le timer reflète
// duration_min de payload.controle. À la fin, gemma3:12b évalue la
// présentation selon une grille /20 (compréhension, structure, vocab,
// pronunciation, relances) et retourne note + ventilation par critère.
function ExamOralStep({
  academy,
  subjectLabel,
}: {
  academy: UseAcademyViewLogic
  subjectLabel: string
}) {
  const payload = academy.parcoursPayload
  if (!payload) return null
  const language = payload.language || 'la langue cible'
  const durationMinFromPayload = payload.controle?.duration_min || 10
  const supportText = academy.lessonText || ''
  const supportName = academy.lessonName || null
  // iter34 : prefer payload.questions_relance (set by classifier when format=mixed),
  // sinon fallback sur les questions du contrôle (back-compat iter32/33).
  const questionsRelance = (
    payload.questions_relance && payload.questions_relance.length > 0
      ? payload.questions_relance
      : (payload.controle?.questions || []).map((q) => q.q)
  ).filter(Boolean)
  const sujetPresentation = payload.controle?.developpement?.consigne
    || `Présente ${payload.synthese_20_20.titre} en ${language}, comme à un oral d'examen.`
  // iter34 : oral_format pilote la flow (full = présentation seule, mixed =
  // présentation + Q&A live, questions_only = juste Q&A sans présentation).
  const oralFormat: 'full' | 'mixed' | 'questions_only' = (
    payload.oral_format === 'mixed' || payload.oral_format === 'questions_only' || payload.oral_format === 'full'
  ) ? payload.oral_format : 'full'

  // iter34 : nouvelle phase 'qa' insérée entre recording et evaluating quand
  // format=mixed. Le user voit UNE question à la fois, répond voix ou texte,
  // l'IA évalue chaque réponse, puis on passe à evaluating pour la note finale.
  type OralPhase = 'config' | 'recording' | 'qa' | 'evaluating' | 'done'
  const [phase, setPhase] = useState<OralPhase>('config')
  // iter34 : Q&A state — index courant + transcripts + scores
  type QAEntry = { question: string; answerText: string; score?: number; feedback?: string; viaVoice?: boolean }
  const [qaEntries, setQaEntries] = useState<QAEntry[]>([])
  const [qaIdx, setQaIdx] = useState(0)
  const [qaCurrentAnswer, setQaCurrentAnswer] = useState('')
  const [qaRecording, setQaRecording] = useState(false)
  const [qaEvaluating, setQaEvaluating] = useState(false)
  const qaMediaRef = useRef<MediaRecorder | null>(null)
  const qaChunksRef = useRef<Blob[]>([])
  const qaStreamRef = useRef<MediaStream | null>(null)
  const [durationMin, setDurationMin] = useState(durationMinFromPayload)
  const [scriptText, setScriptText] = useState('')
  const [scriptName, setScriptName] = useState<string | null>(null)
  const [consigne, setConsigne] = useState(sujetPresentation)
  const [cameraOn, setCameraOn] = useState(false)

  const [secLeft, setSecLeft] = useState(0)
  const [transcript, setTranscript] = useState('')
  const [evalResult, setEvalResult] = useState<{
    note_20?: number
    feedback?: string
    bien?: string[]
    manques?: string[]
    voix?: string
    feedback_par_critere?: {
      comprehension?: { score: number; max: number; commentaire: string }
      structure?: { score: number; max: number; commentaire: string }
      vocabulary?: { score: number; max: number; commentaire: string }
      pronunciation?: { score: number; max: number; commentaire: string }
      relances?: { score: number; max: number; commentaire: string }
    }
    mots_manques?: string[]
    hesitations_count?: number
    conseils_amelioration?: string[]
    raw?: string
    error?: string
  } | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Refs pour cleanup
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioStreamRef = useRef<MediaStream | null>(null)
  const videoStreamRef = useRef<MediaStream | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const tickRef = useRef<number | null>(null)
  const finishCalledRef = useRef(false)
  // Ref vers la closure finishRecording pour qu'elle soit accessible depuis
  // setInterval déclenché dans startRecording (sans use-before-define).
  const finishRecordingRef = useRef<() => Promise<void>>(async () => {})

  const cleanup = useCallback(() => {
    try { mediaRecorderRef.current?.stop() } catch {}
    audioStreamRef.current?.getTracks().forEach((t) => t.stop())
    videoStreamRef.current?.getTracks().forEach((t) => t.stop())
    audioStreamRef.current = null
    videoStreamRef.current = null
    if (tickRef.current) { window.clearInterval(tickRef.current); tickRef.current = null }
    // iter34 : cleanup Q&A media stream too
    try { qaMediaRef.current?.stop() } catch {}
    qaStreamRef.current?.getTracks().forEach((t) => t.stop())
    qaStreamRef.current = null
  }, [])

  useEffect(() => () => cleanup(), [cleanup])

  // Lecture du script uploadé (texte / pdf via le PDF extractor existant)
  const onScriptFile = useCallback(async (file: File) => {
    setScriptName(file.name)
    if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
      try {
        const { extractPdfText } = await import('../../utils/pdfExtract')
        const txt = await extractPdfText(file)
        setScriptText(txt)
      } catch (e) {
        setError(`Lecture PDF échouée : ${e instanceof Error ? e.message : String(e)}`)
      }
    } else {
      try {
        const txt = await file.text()
        setScriptText(txt)
      } catch (e) {
        setError(`Lecture fichier échouée : ${e instanceof Error ? e.message : String(e)}`)
      }
    }
  }, [])

  // Démarre l'enregistrement
  const startRecording = useCallback(async () => {
    setError(null)
    finishCalledRef.current = false
    try {
      const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioStreamRef.current = audioStream
      if (cameraOn) {
        try {
          const videoStream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 } })
          videoStreamRef.current = videoStream
          if (videoRef.current) {
            videoRef.current.srcObject = videoStream
            await videoRef.current.play().catch(() => {})
          }
        } catch (e) {
          setError(`Caméra indispo (l'audio continue) : ${e instanceof Error ? e.message : String(e)}`)
        }
      }
      const mr = new MediaRecorder(audioStream, { mimeType: 'audio/webm' })
      audioChunksRef.current = []
      mr.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data) }
      mr.start(1000)
      mediaRecorderRef.current = mr
      setSecLeft(durationMin * 60)
      setPhase('recording')
      // tick
      tickRef.current = window.setInterval(() => {
        setSecLeft((s) => {
          if (s <= 1) {
            if (!finishCalledRef.current) {
              finishCalledRef.current = true
              window.setTimeout(() => void finishRecordingRef.current(), 0)
            }
            return 0
          }
          return s - 1
        })
      }, 1000)
    } catch (e) {
      setError(`Mic refusé / indispo : ${e instanceof Error ? e.message : String(e)}`)
      cleanup()
    }
  }, [durationMin, cameraOn, cleanup])

  const finishRecording = useCallback(async () => {
    if (phase === 'evaluating' || phase === 'done' || phase === 'qa') return
    // iter34 : si format=mixed, on a une présentation, mais APRÈS on doit
    // faire le Q&A live (questions de relance une par une). On reste sur
    // 'recording' pour le moment, puis on bascule sur 'qa' après STT
    // (pour montrer le transcript pendant que l'élève prépare ses réponses
    // aux relances).
    setPhase('evaluating')
    if (tickRef.current) { window.clearInterval(tickRef.current); tickRef.current = null }
    // Stop recording, await final ondataavailable
    const mr = mediaRecorderRef.current
    if (mr && mr.state !== 'inactive') {
      await new Promise<void>((resolve) => {
        const handler = () => { mr.removeEventListener('stop', handler); resolve() }
        mr.addEventListener('stop', handler)
        mr.stop()
      })
    }
    audioStreamRef.current?.getTracks().forEach((t) => t.stop())
    videoStreamRef.current?.getTracks().forEach((t) => t.stop())

    // STT via bridge — la langue cible peut être différente du français
    // pour ETLV / langues vivantes. payload.language donne 'anglais',
    // 'espagnol', etc. Voxtral attend un code ISO court.
    const langIsoMap: Record<string, string> = {
      anglais: 'en', english: 'en', english_us: 'en',
      espagnol: 'es', spanish: 'es',
      italien: 'it', italian: 'it',
      allemand: 'de', german: 'de',
      portugais: 'pt', portuguese: 'pt',
      chinois: 'zh', chinese: 'zh', mandarin: 'zh',
      japonais: 'ja', japanese: 'ja',
      arabe: 'ar', arabic: 'ar',
      russe: 'ru', russian: 'ru',
      français: 'fr', francais: 'fr', french: 'fr', fle: 'fr',
    }
    const sttLang = langIsoMap[(payload.language || '').toLowerCase().trim()] || 'fr'
    const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
    const audioElapsedSec = (durationMin * 60) - secLeft
    let transcriptText = ''
    try {
      const fd = new FormData()
      fd.append('audio', blob, 'oral.webm')
      fd.append('language', sttLang)
      const bridge = (() => { try { return getBridgeUrl() } catch { return '' } })()
      const url = bridge ? `${bridge}/api/voice/stt` : '/api/voice/stt'
      const r = await fetch(url, { method: 'POST', body: fd })
      const data = await r.json() as { ok?: boolean; text?: string; error?: string }
      if (data.ok !== false && data.text) {
        transcriptText = data.text
      } else {
        setError(`STT échoué : ${data.error || 'pas de transcription'}`)
      }
    } catch (e) {
      setError(`STT injoignable : ${e instanceof Error ? e.message : String(e)}`)
    }
    setTranscript(transcriptText)

    // iter34 : fork — si format=mixed et qu'on a des questions de relance,
    // on passe en phase 'qa' AVANT de noter. L'élève va répondre aux
    // relances une par une, puis l'éval finale combine présentation + Q&A.
    if (oralFormat === 'mixed' && questionsRelance.length > 0) {
      // Initialise la liste Q&A à partir des questions de relance.
      const initialEntries: QAEntry[] = questionsRelance.slice(0, 5).map((q) => ({
        question: q, answerText: '', viaVoice: false,
      }))
      setQaEntries(initialEntries)
      setQaIdx(0)
      setQaCurrentAnswer('')
      setPhase('qa')
      return
    }

    // Eval LLM — vraie passation orale BAC ETLV / langue. Grille /20
    // ventilée en 5 critères, conformément à iter33.E.
    const sys = `ÉVALUATION ORALE BAC — ${subjectLabel} / ${language}.
L'élève vient de présenter à l'oral pendant ${durationMin} min sur un sujet
fourni. Tu corriges comme un examinateur de jury BAC : strict mais juste.
Tu évalues la PRÉSENTATION ORALE, pas un écrit récité.

Grille de notation (sur 20) :
- Compréhension du sujet (5pt) : a-t-il compris ce qu'on attend ?
- Structure (4pt) : intro / parties / conclusion claires ?
- Vocabulary attendu utilisé (4pt) : mots-clés thématiques en ${language} ?
- Pronunciation / fluidité (3pt) : débit, hésitations, mots de remplissage.
- Réponse aux relances prévues (4pt) : couvre-t-il les questions de relance ?

Tu retournes UNIQUEMENT un JSON pur (pas de markdown) :
{
  "note_20": <0-20>,
  "feedback": "<3-5 phrases globales>",
  "feedback_par_critere": {
    "comprehension": {"score": <0-5>, "max": 5, "commentaire": "<...>"},
    "structure":     {"score": <0-4>, "max": 4, "commentaire": "<...>"},
    "vocabulary":    {"score": <0-4>, "max": 4, "commentaire": "<...>"},
    "pronunciation": {"score": <0-3>, "max": 3, "commentaire": "<...>"},
    "relances":      {"score": <0-4>, "max": 4, "commentaire": "<...>"}
  },
  "bien": ["<3 points forts>"],
  "manques": ["<3 points faibles>"],
  "mots_manques": ["<vocab clé non utilisé>"],
  "hesitations_count": <nombre approximatif d'hésitations détectées>,
  "voix": "<1 phrase analyse débit/fluidité>",
  "conseils_amelioration": ["<conseil 1>", "<conseil 2>"]
}`
    const usr = [
      `### CONSIGNE / SUJET DE PRÉSENTATION\n${consigne}`,
      supportText ? `### SUPPORT DE RÉFÉRENCE (${supportName || 'document utilisateur'})\n${supportText.slice(0, 4000)}` : '',
      scriptText ? `### NOTES PERSO ÉLÈVE\n${scriptText.slice(0, 2000)}` : '',
      questionsRelance.length > 0
        ? `### QUESTIONS DE RELANCE PRÉVUES\n${questionsRelance.map((q, i) => `${i + 1}. ${q}`).join('\n')}`
        : '',
      `### TRANSCRIPTION DE L'ORAL (langue : ${language}, durée parlée ≈ ${audioElapsedSec}s sur ${durationMin * 60}s prévues)\n${transcriptText || '(transcription vide ou échouée)'}`,
      `Évalue maintenant en JSON strict.`,
    ].filter(Boolean).join('\n\n')
    try {
      const bridge = (() => { try { return getBridgeUrl() } catch { return '' } })()
      const url = bridge ? `${bridge}/proxy/ollama/api/chat` : '/api/ollama/chat'
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: LEARNING_EVAL_MODEL,
          messages: [
            { role: 'system', content: sys },
            { role: 'user', content: usr },
          ],
          stream: false,
          options: { temperature: 0.3, num_ctx: 8192, num_predict: 800 },
        }),
      })
      const data = await r.json() as { message?: { content?: string }; response?: string }
      const text = data?.message?.content ?? data?.response ?? ''
      const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/)
      const candidate = fenced ? fenced[1] : text
      const a = candidate.indexOf('{'); const b = candidate.lastIndexOf('}')
      let parsed: {
        note_20?: number
        score?: number
        feedback?: string
        bien?: string[]
        manques?: string[]
        voix?: string
        feedback_par_critere?: {
          comprehension?: { score: number; max: number; commentaire: string }
          structure?: { score: number; max: number; commentaire: string }
          vocabulary?: { score: number; max: number; commentaire: string }
          pronunciation?: { score: number; max: number; commentaire: string }
          relances?: { score: number; max: number; commentaire: string }
        }
        mots_manques?: string[]
        hesitations_count?: number
        conseils_amelioration?: string[]
      } = {}
      if (a !== -1 && b > a) {
        try { parsed = JSON.parse(candidate.slice(a, b + 1)) } catch {}
      }
      // back-compat : si LLM a retourné `score` au lieu de `note_20`
      if (parsed.note_20 === undefined && typeof parsed.score === 'number') {
        parsed.note_20 = parsed.score
      }
      setEvalResult({ ...parsed, raw: text })
    } catch (e) {
      setEvalResult({ error: e instanceof Error ? e.message : String(e), feedback: 'Évaluation LLM indisponible.' })
    }
    setPhase('done')
  }, [phase, durationMin, subjectLabel, language, consigne, scriptText, supportText, supportName, questionsRelance, secLeft, oralFormat, payload.language])

  // Sync la ref pour que setInterval dans startRecording puisse appeler la closure courante
  useEffect(() => { finishRecordingRef.current = finishRecording }, [finishRecording])

  // iter34 : helpers Q&A live ------------------------------------------------
  // STT ciblé pour 1 réponse Q&A (utilise le même endpoint /api/voice/stt).
  const transcribeBlob = useCallback(async (blob: Blob, sttLang: string): Promise<string> => {
    try {
      const fd = new FormData()
      fd.append('audio', blob, 'qa.webm')
      fd.append('language', sttLang)
      const bridge = (() => { try { return getBridgeUrl() } catch { return '' } })()
      const url = bridge ? `${bridge}/api/voice/stt` : '/api/voice/stt'
      const r = await fetch(url, { method: 'POST', body: fd })
      const data = await r.json() as { ok?: boolean; text?: string; error?: string }
      return (data.ok !== false && data.text) ? data.text : ''
    } catch {
      return ''
    }
  }, [])

  // Démarre l'enregistrement de la réponse à la question Q&A courante
  const startQaRecord = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      qaStreamRef.current = stream
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      qaChunksRef.current = []
      mr.ondataavailable = (e) => { if (e.data.size > 0) qaChunksRef.current.push(e.data) }
      mr.start(1000)
      qaMediaRef.current = mr
      setQaRecording(true)
    } catch (e) {
      setError(`Mic refusé : ${e instanceof Error ? e.message : String(e)}`)
    }
  }, [])

  // Stop l'enregistrement Q&A + STT + remplit qaCurrentAnswer
  const stopQaRecord = useCallback(async () => {
    setQaRecording(false)
    const mr = qaMediaRef.current
    if (mr && mr.state !== 'inactive') {
      await new Promise<void>((resolve) => {
        const handler = () => { mr.removeEventListener('stop', handler); resolve() }
        mr.addEventListener('stop', handler)
        mr.stop()
      })
    }
    qaStreamRef.current?.getTracks().forEach((t) => t.stop())
    qaStreamRef.current = null
    const langIsoMap: Record<string, string> = {
      anglais: 'en', english: 'en',
      espagnol: 'es', spanish: 'es',
      italien: 'it', italian: 'it',
      allemand: 'de', german: 'de',
      portugais: 'pt', portuguese: 'pt',
      chinois: 'zh', chinese: 'zh', mandarin: 'zh',
      japonais: 'ja', japanese: 'ja',
      arabe: 'ar', arabic: 'ar',
      russe: 'ru', russian: 'ru',
      français: 'fr', francais: 'fr', french: 'fr', fle: 'fr',
    }
    const sttLang = langIsoMap[(payload.language || '').toLowerCase().trim()] || 'fr'
    const blob = new Blob(qaChunksRef.current, { type: 'audio/webm' })
    qaChunksRef.current = []
    const text = await transcribeBlob(blob, sttLang)
    setQaCurrentAnswer((prev) => prev ? `${prev}\n${text}` : text)
  }, [payload.language, transcribeBlob])

  // Valide la réponse à la question courante : éval rapide + passe à la suivante
  const submitQaAnswer = useCallback(async () => {
    if (qaEvaluating) return
    const cur = qaEntries[qaIdx]
    if (!cur) return
    setQaEvaluating(true)
    // Éval rapide locale par gemma3:12b (note 0-100 + 1 phrase)
    const sys = `Tu évalues UNE réponse brève à une question de relance d'oral BAC en ${language}.
Tu retournes UNIQUEMENT un JSON pur :
{"score": <0-100>, "feedback": "<1 phrase courte en français>"}
Critères : pertinence, exactitude, vocabulaire en ${language}, structure de phrase. Réponse vide ou hors-sujet → score < 30.`
    const usr = `Question (en ${language}) : ${cur.question}\n\nRéponse de l'élève (transcription voix ou texte) :\n${qaCurrentAnswer || '(vide)'}`
    let parsed: { score?: number; feedback?: string } = {}
    try {
      const bridge = (() => { try { return getBridgeUrl() } catch { return '' } })()
      const url = bridge ? `${bridge}/proxy/ollama/api/chat` : '/api/ollama/chat'
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: LEARNING_EVAL_MODEL,
          messages: [
            { role: 'system', content: sys },
            { role: 'user', content: usr },
          ],
          stream: false,
          options: { temperature: 0.3, num_ctx: 2048, num_predict: 200 },
        }),
        signal: AbortSignal.timeout(60_000),
      })
      const data = await r.json() as { message?: { content?: string }; response?: string }
      const text = data?.message?.content ?? data?.response ?? ''
      const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/)
      const candidate = fenced ? fenced[1] : text
      const a = candidate.indexOf('{'); const b = candidate.lastIndexOf('}')
      if (a !== -1 && b > a) {
        try { parsed = JSON.parse(candidate.slice(a, b + 1)) } catch {}
      }
    } catch {}
    const updated: QAEntry = {
      ...cur,
      answerText: qaCurrentAnswer,
      score: typeof parsed.score === 'number' ? Math.max(0, Math.min(100, Math.round(parsed.score))) : 50,
      feedback: parsed.feedback || '(éval indisponible)',
    }
    setQaEntries((arr) => arr.map((e, i) => i === qaIdx ? updated : e))
    setQaCurrentAnswer('')
    setQaEvaluating(false)
    setQaIdx((i) => i + 1)
  }, [qaEntries, qaIdx, qaCurrentAnswer, language, qaEvaluating])

  // Une fois toutes les Q&A traitées, on lance l'éval finale combinée
  // (présentation + Q&A) — réutilise la grille /20 existante de finishRecording.
  const runFinalEvaluation = useCallback(async () => {
    setPhase('evaluating')
    const audioElapsedSec = (durationMin * 60) - secLeft
    const sys = `ÉVALUATION ORALE BAC — ${subjectLabel} / ${language}.
L'élève vient de présenter à l'oral pendant ${durationMin} min sur un sujet
fourni, PUIS de répondre aux questions de relance du jury en direct.
Tu corriges comme un examinateur de jury BAC : strict mais juste.

Grille de notation (sur 20) :
- Compréhension du sujet (5pt) : a-t-il compris ce qu'on attend ?
- Structure (4pt) : intro / parties / conclusion claires ?
- Vocabulary attendu utilisé (4pt) : mots-clés thématiques en ${language} ?
- Pronunciation / fluidité (3pt) : débit, hésitations.
- Réponse aux relances (4pt) : précision et pertinence des réponses Q&A.

Tu retournes UNIQUEMENT un JSON pur (pas de markdown) :
{
  "note_20": <0-20>,
  "feedback": "<3-5 phrases globales>",
  "feedback_par_critere": {
    "comprehension": {"score": <0-5>, "max": 5, "commentaire": "<...>"},
    "structure":     {"score": <0-4>, "max": 4, "commentaire": "<...>"},
    "vocabulary":    {"score": <0-4>, "max": 4, "commentaire": "<...>"},
    "pronunciation": {"score": <0-3>, "max": 3, "commentaire": "<...>"},
    "relances":      {"score": <0-4>, "max": 4, "commentaire": "<...>"}
  },
  "bien": ["<3 points forts>"],
  "manques": ["<3 points faibles>"],
  "mots_manques": ["<vocab clé non utilisé>"],
  "hesitations_count": <nombre approximatif d'hésitations détectées>,
  "voix": "<1 phrase analyse débit/fluidité>",
  "conseils_amelioration": ["<conseil 1>", "<conseil 2>"]
}`
    const qaBlock = qaEntries.map((e, i) =>
      `Q${i + 1} (${language}) : ${e.question}\nRéponse élève : ${e.answerText || '(vide)'}\nScore Q&A : ${e.score ?? '—'}/100`,
    ).join('\n\n')
    const usr = [
      `### CONSIGNE / SUJET DE PRÉSENTATION\n${consigne}`,
      supportText ? `### SUPPORT DE RÉFÉRENCE (${supportName || 'document utilisateur'})\n${supportText.slice(0, 4000)}` : '',
      scriptText ? `### NOTES PERSO ÉLÈVE\n${scriptText.slice(0, 2000)}` : '',
      `### TRANSCRIPTION DE LA PRÉSENTATION (langue : ${language}, durée parlée ≈ ${audioElapsedSec}s sur ${durationMin * 60}s)\n${transcript || '(transcription vide ou échouée)'}`,
      `### Q&A LIVE (questions de relance)\n${qaBlock || '(aucune)'}`,
      `Évalue maintenant en JSON strict. Note la présentation ET les relances dans la grille.`,
    ].filter(Boolean).join('\n\n')
    try {
      const bridge = (() => { try { return getBridgeUrl() } catch { return '' } })()
      const url = bridge ? `${bridge}/proxy/ollama/api/chat` : '/api/ollama/chat'
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: LEARNING_EVAL_MODEL,
          messages: [
            { role: 'system', content: sys },
            { role: 'user', content: usr },
          ],
          stream: false,
          options: { temperature: 0.3, num_ctx: 8192, num_predict: 800 },
        }),
        signal: AbortSignal.timeout(180_000),
      })
      const data = await r.json() as { message?: { content?: string }; response?: string }
      const text = data?.message?.content ?? data?.response ?? ''
      const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/)
      const candidate = fenced ? fenced[1] : text
      const a = candidate.indexOf('{'); const b = candidate.lastIndexOf('}')
      let parsed: {
        note_20?: number; score?: number; feedback?: string
        bien?: string[]; manques?: string[]; voix?: string
        feedback_par_critere?: {
          comprehension?: { score: number; max: number; commentaire: string }
          structure?: { score: number; max: number; commentaire: string }
          vocabulary?: { score: number; max: number; commentaire: string }
          pronunciation?: { score: number; max: number; commentaire: string }
          relances?: { score: number; max: number; commentaire: string }
        }
        mots_manques?: string[]; hesitations_count?: number
        conseils_amelioration?: string[]
      } = {}
      if (a !== -1 && b > a) {
        try { parsed = JSON.parse(candidate.slice(a, b + 1)) } catch {}
      }
      if (parsed.note_20 === undefined && typeof parsed.score === 'number') {
        parsed.note_20 = parsed.score
      }
      setEvalResult({ ...parsed, raw: text })
    } catch (e) {
      setEvalResult({ error: e instanceof Error ? e.message : String(e), feedback: 'Évaluation LLM indisponible.' })
    }
    setPhase('done')
  }, [durationMin, subjectLabel, language, consigne, scriptText, supportText, supportName, transcript, qaEntries, secLeft])

  // Auto-trigger l'éval finale quand l'utilisateur a fini toutes les Q&A
  useEffect(() => {
    if (phase !== 'qa') return
    if (qaEntries.length === 0) return
    if (qaIdx >= qaEntries.length) {
      void runFinalEvaluation()
    }
  }, [phase, qaEntries.length, qaIdx, runFinalEvaluation])

  const fmtTime = (s: number) => {
    const m = Math.floor(s / 60), sec = s % 60
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  }

  return (
    <div style={{ maxWidth: 920, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div>
        <div style={{
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          letterSpacing: '0.18em', textTransform: 'uppercase',
          color: RED_FG, marginBottom: 8,
        }}>
          Passation orale · examen final · {language}
        </div>
        <h2 style={{
          fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
          fontStyle: 'italic', fontWeight: 400, fontSize: 38,
          margin: 0, color: 'var(--fg, #f5f5f5)',
        }}>
          {payload.synthese_20_20.titre}
        </h2>
        <p style={{ marginTop: 6, fontSize: 13, color: 'var(--fg-dim, #aaa)' }}>
          C'est ton examen oral. Le support sur lequel tu es interrogé est ci-dessous.
          Démarre le timer, parle en {language}. À la fin, l'IA note ta présentation /20
          (compréhension, structure, vocabulary, pronunciation, relances).
        </p>
      </div>

      {/* iter33.E + 33.F : support de référence affiché en haut. C'est ce
         sur quoi l'élève est interrogé (photo de la feuille / fichier
         uploadé). Vision qwen3-vl extrait déjà le texte côté useAcademyViewLogic
         via `lessonImages` — on l'expose via lessonText. */}
      {(supportText || (academy.lessonImages && academy.lessonImages.length > 0)) && phase === 'config' && (
        <div style={{
          padding: 14, borderRadius: 8,
          background: `${GOLD}10`, border: `1px solid ${GOLD}55`,
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8, color: GOLD }}>
            📄 Support fourni · {supportName || 'document utilisateur'}
          </div>
          {academy.lessonImages && academy.lessonImages.length > 0 && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
              {academy.lessonImages.map((im, i) => (
                <img key={i} src={im.dataUrl} alt={im.name}
                  style={{ width: 110, height: 110, objectFit: 'cover', borderRadius: 6, border: `1px solid ${GOLD}55` }} />
              ))}
            </div>
          )}
          {supportText && (
            <details>
              <summary style={{ cursor: 'pointer', fontSize: 11, color: 'var(--fg-dim, #aaa)' }}>
                Voir le contenu extrait ({supportText.length} chars)
              </summary>
              <div style={{
                marginTop: 8, padding: 10, fontSize: 12, lineHeight: 1.5,
                background: 'var(--bg-card, rgba(255,255,255,0.03))',
                borderRadius: 6, maxHeight: 240, overflow: 'auto',
                whiteSpace: 'pre-wrap',
              }}>
                {supportText.slice(0, 4000)}
                {supportText.length > 4000 ? '\n\n[...tronqué]' : ''}
              </div>
            </details>
          )}
        </div>
      )}

      {/* iter33.E : questions de relance prévues affichées comme un brief
         "voilà ce que l'examinateur peut te demander". L'élève les connaît
         pour pouvoir les anticiper, comme dans une vraie session BAC. */}
      {questionsRelance.length > 0 && phase === 'config' && (
        <div style={{
          padding: 12, borderRadius: 8,
          background: 'var(--bg-card, rgba(255,255,255,0.04))',
          border: '1px solid oklch(0.72 0.12 200 / 0.30)',
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6, color: 'oklch(0.78 0.13 200)' }}>
            🎙 Questions de relance prévues
          </div>
          <ol style={{ margin: 0, paddingLeft: 22, fontSize: 12, lineHeight: 1.55 }}>
            {questionsRelance.slice(0, 6).map((q, i) => <li key={i}>{q}</li>)}
          </ol>
        </div>
      )}

      {error && (
        <div style={{
          padding: 10, borderRadius: 6, fontSize: 12,
          background: `${RED}20`, color: RED_FG, border: `1px solid ${RED}55`,
        }}>
          ⚠ {error}
        </div>
      )}

      {phase === 'config' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Durée */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>Durée de la présentation</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {[5, 10, 15].map((m) => (
                <button key={m} type="button"
                  onClick={() => setDurationMin(m)}
                  style={{
                    padding: '8px 16px', borderRadius: 6, fontSize: 13, fontWeight: 600,
                    background: durationMin === m ? GOLD : 'var(--bg-card, rgba(255,255,255,0.04))',
                    color: durationMin === m ? '#0a0a0a' : 'var(--fg, #f5f5f5)',
                    border: `1px solid ${durationMin === m ? GOLD : 'var(--line, rgba(255,255,255,0.12))'}`,
                    cursor: 'pointer',
                  }}>
                  {m} min
                </button>
              ))}
            </div>
          </div>

          {/* Consigne */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>Sujet / consigne</div>
            <textarea value={consigne} onChange={(e) => setConsigne(e.target.value)}
              rows={2}
              style={{
                width: '100%', padding: 10, fontSize: 13, borderRadius: 6,
                background: 'var(--bg-input, rgba(255,255,255,0.04))',
                color: 'var(--fg, #f5f5f5)',
                border: `1px solid var(--line, rgba(255,255,255,0.18))`,
                fontFamily: 'inherit', resize: 'vertical',
              }} />
          </div>

          {/* Script fichier */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>
              Script / fiche papier (optionnel — texte ou PDF)
            </div>
            <input type="file" accept=".txt,.md,.pdf" onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) void onScriptFile(f)
            }}
              style={{ fontSize: 12, color: 'var(--fg, #f5f5f5)' }} />
            {scriptName && (
              <div style={{ marginTop: 6, fontSize: 11, color: GREEN_FG }}>
                ✓ {scriptName} ({scriptText.length} chars chargés)
              </div>
            )}
          </div>

          {/* Caméra */}
          <div>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
              <input type="checkbox" checked={cameraOn} onChange={(e) => setCameraOn(e.target.checked)} />
              <span>Activer la caméra (preview seulement, pas d'enregistrement vidéo persistant)</span>
            </label>
          </div>

          {/* iter34 : si format=questions_only, le user n'a PAS de présentation
             à faire, juste répondre aux questions de relance. On lui propose
             un bouton qui saute directement la phase recording. */}
          {oralFormat === 'questions_only' && questionsRelance.length > 0 ? (
            <button type="button"
              onClick={() => {
                const initialEntries: QAEntry[] = questionsRelance.slice(0, 5).map((q) => ({
                  question: q, answerText: '', viaVoice: false,
                }))
                setQaEntries(initialEntries)
                setQaIdx(0)
                setQaCurrentAnswer('')
                setTranscript('')
                setPhase('qa')
              }}
              style={{
                padding: '12px 24px', borderRadius: 99, fontWeight: 700,
                background: 'oklch(0.74 0.13 90 / 0.20)', color: 'oklch(0.78 0.16 90)',
                border: '1px solid oklch(0.74 0.13 90 / 0.55)',
                fontSize: 14, cursor: 'pointer', alignSelf: 'flex-start',
                display: 'inline-flex', alignItems: 'center', gap: 8,
              }}>
              <Mic size={16} /> Démarrer l'interrogation ({questionsRelance.length} questions)
            </button>
          ) : (
            <button type="button" onClick={() => void startRecording()}
              style={{
                padding: '12px 24px', borderRadius: 99, fontWeight: 700,
                background: 'oklch(0.74 0.13 90 / 0.20)', color: 'oklch(0.78 0.16 90)',
                border: '1px solid oklch(0.74 0.13 90 / 0.55)',
                fontSize: 14, cursor: 'pointer', alignSelf: 'flex-start',
                display: 'inline-flex', alignItems: 'center', gap: 8,
              }}>
              <Mic size={16} /> {oralFormat === 'mixed'
                ? `Démarrer la présentation (${durationMin} min) puis Q&A`
                : `Démarrer l'oral (${durationMin} min)`}
            </button>
          )}
        </div>
      )}

      {phase === 'recording' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 14,
            padding: '14px 20px', borderRadius: 10,
            background: secLeft < 30 ? `${RED}33` : `${GOLD}22`,
            border: `1px solid ${secLeft < 30 ? RED : GOLD}88`,
          }}>
            <div style={{
              width: 14, height: 14, borderRadius: 99,
              background: RED_FG, animation: 'streakPulse 1s infinite',
            }} />
            <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 28, fontWeight: 700 }}>
              {fmtTime(secLeft)}
            </span>
            <span style={{ fontSize: 12, color: 'var(--fg-dim, #aaa)' }}>
              en train d'enregistrer · parle clairement
            </span>
          </div>

          {cameraOn && (
            <video ref={videoRef} muted autoPlay playsInline
              style={{
                width: 320, height: 240, borderRadius: 10,
                background: '#000', border: `1px solid ${GOLD}55`,
                alignSelf: 'flex-start',
              }} />
          )}

          <div style={{ fontSize: 13, padding: 10, borderRadius: 6, background: 'var(--bg-card, rgba(255,255,255,0.04))' }}>
            <strong>Sujet :</strong> {consigne}
          </div>

          <button type="button" onClick={() => void finishRecording()}
            style={{
              padding: '10px 18px', borderRadius: 6, fontSize: 13, fontWeight: 600,
              background: `${GREEN_FG}30`, color: GREEN_FG,
              border: `1px solid ${GREEN_FG}80`, cursor: 'pointer',
              alignSelf: 'flex-start',
            }}>
            ✓ Terminer maintenant
          </button>
        </div>
      )}

      {/* iter34 : phase Q&A live (format=mixed). Une question à la fois, voix
         ou texte, IA évalue chaque réponse, puis bascule vers eval finale. */}
      {phase === 'qa' && qaEntries.length > 0 && qaIdx < qaEntries.length && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{
            padding: 14, borderRadius: 10,
            background: `${GOLD}1A`, border: `1px solid ${GOLD}55`,
          }}>
            <div style={{
              fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
              letterSpacing: '0.18em', textTransform: 'uppercase',
              color: GOLD, marginBottom: 6,
            }}>
              Q&A live · question {qaIdx + 1}/{qaEntries.length} · {language}
            </div>
            <div style={{
              fontSize: 18, fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
              fontStyle: 'italic', lineHeight: 1.4,
            }}>
              {qaEntries[qaIdx].question}
            </div>
            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--fg-dim, #aaa)' }}>
              Réponds en {language} comme à un vrai jury. Voix ou texte au choix.
            </div>
          </div>

          {/* Bouton micro + textarea */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <button type="button"
              onClick={() => qaRecording ? void stopQaRecord() : void startQaRecord()}
              style={{
                padding: '10px 14px', borderRadius: 8, fontSize: 13, fontWeight: 600,
                background: qaRecording ? `${RED}40` : `${GOLD}22`,
                color: qaRecording ? RED_FG : GOLD,
                border: `1px solid ${qaRecording ? RED : GOLD}88`,
                cursor: 'pointer', flexShrink: 0,
                display: 'inline-flex', alignItems: 'center', gap: 6,
                animation: qaRecording ? 'streakPulse 1s infinite' : undefined,
              }}>
              <Mic size={14} /> {qaRecording ? 'Stop + transcrire' : 'Réponse voix'}
            </button>
            <textarea value={qaCurrentAnswer} onChange={(e) => setQaCurrentAnswer(e.target.value)}
              placeholder={`Réponse en ${language} (texte) ou clique 🎤 pour voix…`}
              rows={3}
              disabled={qaEvaluating}
              style={{
                flex: 1, padding: 10, fontSize: 13, borderRadius: 6,
                background: 'var(--bg-input, rgba(255,255,255,0.04))',
                color: 'var(--fg, #f5f5f5)',
                border: `1px solid var(--line, rgba(255,255,255,0.18))`,
                fontFamily: 'inherit', resize: 'vertical',
              }} />
          </div>

          {/* Feedback de la question PRÉCÉDENTE (si on en a une) */}
          {qaIdx > 0 && qaEntries[qaIdx - 1].feedback && (
            <div style={{
              padding: 10, borderRadius: 6, fontSize: 12, lineHeight: 1.5,
              background: 'var(--bg-card, rgba(255,255,255,0.03))',
              border: `1px solid ${(qaEntries[qaIdx - 1].score ?? 0) >= 70 ? GREEN_FG : (qaEntries[qaIdx - 1].score ?? 0) >= 40 ? GOLD : RED_FG}40`,
            }}>
              <strong style={{
                color: (qaEntries[qaIdx - 1].score ?? 0) >= 70 ? GREEN_FG : (qaEntries[qaIdx - 1].score ?? 0) >= 40 ? GOLD : RED_FG,
              }}>
                Feedback Q{qaIdx} · {qaEntries[qaIdx - 1].score ?? '—'}/100 :
              </strong> {qaEntries[qaIdx - 1].feedback}
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button type="button"
              onClick={() => void submitQaAnswer()}
              disabled={qaEvaluating || qaRecording}
              style={{
                padding: '10px 18px', borderRadius: 6, fontSize: 13, fontWeight: 700,
                background: qaEvaluating ? `${GOLD}33` : `${GREEN_FG}30`,
                color: qaEvaluating ? GOLD : GREEN_FG,
                border: `1px solid ${qaEvaluating ? GOLD : GREEN_FG}80`,
                cursor: qaEvaluating ? 'wait' : 'pointer',
              }}>
              {qaEvaluating ? '⏳ Éval…' : qaIdx === qaEntries.length - 1 ? '✓ Dernière → terminer' : '→ Question suivante'}
            </button>
            <span style={{ fontSize: 11, color: 'var(--fg-mute, #888)' }}>
              {qaIdx === qaEntries.length - 1 ? 'Après celle-ci, l\'IA donne ta note finale' : `Reste ${qaEntries.length - qaIdx - 1} question(s)`}
            </span>
          </div>
        </div>
      )}

      {phase === 'evaluating' && (
        <div style={{ padding: 24, textAlign: 'center', color: 'var(--fg-dim, #aaa)' }}>
          ⏳ STT + évaluation IA en cours… (10-30s)
        </div>
      )}

      {phase === 'done' && evalResult && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{
            padding: 18, borderRadius: 10,
            background: 'var(--bg-card, rgba(255,255,255,0.04))',
            border: `1px solid ${(evalResult.note_20 ?? 0) >= 14 ? GREEN_FG : (evalResult.note_20 ?? 0) >= 10 ? GOLD : RED_FG}55`,
          }}>
            <div style={{
              fontSize: 48, fontWeight: 900,
              fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
              color: (evalResult.note_20 ?? 0) >= 14 ? GREEN_FG : (evalResult.note_20 ?? 0) >= 10 ? GOLD : RED_FG,
            }}>
              {evalResult.note_20 ?? '—'}/20
            </div>
            {evalResult.feedback && (
              <div style={{ marginTop: 10, fontSize: 14, lineHeight: 1.5 }}>{evalResult.feedback}</div>
            )}
          </div>

          {/* iter33.E : ventilation par critère */}
          {evalResult.feedback_par_critere && (
            <div style={{
              display: 'grid', gap: 8,
              gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            }}>
              {(['comprehension', 'structure', 'vocabulary', 'pronunciation', 'relances'] as const).map((k) => {
                const c = evalResult.feedback_par_critere?.[k]
                if (!c) return null
                const labelMap: Record<typeof k, string> = {
                  comprehension: 'Compréhension',
                  structure: 'Structure',
                  vocabulary: 'Vocabulary',
                  pronunciation: 'Pronunciation',
                  relances: 'Relances',
                }
                const ratio = c.max > 0 ? c.score / c.max : 0
                const tone = ratio >= 0.7 ? GREEN_FG : ratio >= 0.5 ? GOLD : RED_FG
                return (
                  <div key={k} style={{
                    padding: 10, borderRadius: 6,
                    background: 'var(--bg-card, rgba(255,255,255,0.04))',
                    border: `1px solid ${tone}40`,
                  }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: tone, marginBottom: 4 }}>
                      {labelMap[k]} · {c.score}/{c.max}
                    </div>
                    <div style={{ fontSize: 11, lineHeight: 1.45, color: 'var(--fg-dim, #ccc)' }}>
                      {c.commentaire}
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {evalResult.bien && evalResult.bien.length > 0 && (
            <div style={{ padding: 12, borderRadius: 6, background: `${GREEN_FG}10`, border: `1px solid ${GREEN_FG}33` }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: GREEN_FG, marginBottom: 6 }}>✓ Ce que tu as bien fait</div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.5 }}>
                {evalResult.bien.map((b, i) => <li key={i}>{b}</li>)}
              </ul>
            </div>
          )}
          {evalResult.manques && evalResult.manques.length > 0 && (
            <div style={{ padding: 12, borderRadius: 6, background: `${RED_FG}10`, border: `1px solid ${RED_FG}33` }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: RED_FG, marginBottom: 6 }}>✗ Ce que tu as oublié</div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.5 }}>
                {evalResult.manques.map((m, i) => <li key={i}>{m}</li>)}
              </ul>
            </div>
          )}
          {evalResult.mots_manques && evalResult.mots_manques.length > 0 && (
            <div style={{ padding: 10, borderRadius: 6, background: `${GOLD}10`, border: `1px solid ${GOLD}33`, fontSize: 12 }}>
              <strong style={{ color: GOLD }}>Vocab clé non utilisé :</strong> {evalResult.mots_manques.join(', ')}
            </div>
          )}
          {evalResult.conseils_amelioration && evalResult.conseils_amelioration.length > 0 && (
            <div style={{ padding: 12, borderRadius: 6, background: 'var(--bg-card, rgba(255,255,255,0.04))', border: '1px solid oklch(0.72 0.12 200 / 0.30)' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'oklch(0.78 0.13 200)', marginBottom: 6 }}>➤ Conseils pour la prochaine fois</div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.5 }}>
                {evalResult.conseils_amelioration.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}
          {evalResult.voix && (
            <div style={{ padding: 10, borderRadius: 6, background: 'var(--bg-input, rgba(255,255,255,0.04))', fontSize: 12, fontStyle: 'italic' }}>
              🎙 Voix : {evalResult.voix}{typeof evalResult.hesitations_count === 'number' ? ` · ${evalResult.hesitations_count} hésitation(s)` : ''}
            </div>
          )}

          {transcript && (
            <details>
              <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--fg-dim, #aaa)' }}>
                Voir la transcription ({transcript.length} chars)
              </summary>
              <div style={{ marginTop: 8, padding: 10, fontSize: 12, lineHeight: 1.4, background: 'var(--bg-card, rgba(255,255,255,0.03))', borderRadius: 6, maxHeight: 200, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
                {transcript}
              </div>
            </details>
          )}

          <button type="button" onClick={() => {
            setPhase('config')
            setEvalResult(null)
            setTranscript('')
            setSecLeft(0)
            audioChunksRef.current = []
            // iter34 : reset Q&A state aussi
            setQaEntries([])
            setQaIdx(0)
            setQaCurrentAnswer('')
            setQaRecording(false)
            setQaEvaluating(false)
          }}
            style={{
              padding: '8px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
              background: `${GOLD}22`, color: GOLD, border: `1px solid ${GOLD}66`,
              cursor: 'pointer', alignSelf: 'flex-start',
            }}>
            🔄 Refaire un autre oral
          </button>
        </div>
      )}
    </div>
  )
}

function ExamStep({ academy }: { academy: UseAcademyViewLogic }) {
  const payload = academy.parcoursPayload
  const isGameMode = useLearningSessionStore((s2) => s2.parcours?.profile?.examFormat === 'jeu')
  if (!payload) return null
  const correction = academy.parcoursCorrection
  const timeLeft = academy.parcoursControleTimeLeftSec
  const formatTime = (s: number | null) => {
    if (s == null) return '--:--'
    const m = Math.floor(s / 60), sec = s % 60
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  }

  return (
    <div style={{
      maxWidth: 920, margin: '0 auto',
      display: 'flex', flexDirection: 'column', gap: 18,
    }}>
      <div>
        <div style={{
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          letterSpacing: '0.18em', textTransform: 'uppercase',
          color: RED_FG, marginBottom: 8,
        }}>
          {isGameMode ? '🏆 Boss final · combat de synthèse' : 'Examen blanc · conditions réelles'}
        </div>
        <h2 style={{
          fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
          fontStyle: 'italic', fontWeight: 400, fontSize: 38,
          margin: 0, color: 'var(--fg, #f5f5f5)',
        }}>
          {isGameMode ? '🏆 ' : ''}{isGameMode ? 'Boss final' : 'Contrôle'} ({payload.controle.duration_min} min · {payload.controle.points_questions + payload.controle.points_developpement} pts)
        </h2>
      </div>

      {/* Timer en haut, sticky-feel */}
      {academy.parcoursControleStartedAt !== null && !correction && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '10px 16px', borderRadius: 8,
          background: timeLeft != null && timeLeft < 300 ? `${RED}33` : 'var(--bg-raised, rgba(255,255,255,0.04))',
          border: `1px solid ${timeLeft != null && timeLeft < 300 ? RED : 'var(--line, rgba(255,255,255,0.12))'}`,
        }}>
          <Clock size={16} color={timeLeft != null && timeLeft < 300 ? RED_FG : 'var(--fg, #f5f5f5)'} />
          <span style={{
            fontFamily: 'var(--font-mono, monospace)', fontSize: 22, fontWeight: 700,
            color: timeLeft != null && timeLeft < 300 ? RED_FG : 'var(--fg, #f5f5f5)',
          }}>
            {formatTime(timeLeft)}
          </span>
          <span style={{ fontSize: 12, color: 'var(--fg-dim, #aaa)' }}>temps restant</span>
        </div>
      )}

      {/* Si on n'a PAS encore démarré le contrôle (cas où autostart a échoué) */}
      {academy.parcoursControleStartedAt === null && !correction && (
        <button type="button"
          onClick={() => academy.startParcoursControle()}
          style={{
            padding: '12px 24px', borderRadius: 99, fontWeight: 700,
            background: `${RED}33`, color: RED_FG,
            border: `1px solid ${RED}88`, fontSize: 14, cursor: 'pointer',
            alignSelf: 'flex-start',
          }}>
          🏁 Démarrer l'examen ({payload.controle.duration_min} min)
        </button>
      )}

      {/* Questions courtes */}
      {academy.parcoursControleStartedAt !== null && !correction && (
        <>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>
              Partie 1 — Questions courtes ({payload.controle.points_questions} pts)
            </div>
            {payload.controle.questions.map((q) => (
              <div key={q.id} style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 13, marginBottom: 6, lineHeight: 1.4 }}>
                  <strong>Q{q.id}</strong> ({q.points} pts) — {q.q}
                </label>
                <textarea
                  value={academy.parcoursAnswers[q.id] || ''}
                  onChange={(e) => academy.setParcoursAnswer(q.id, e.target.value)}
                  rows={2}
                  style={{
                    width: '100%', padding: 8, fontSize: 13,
                    background: 'var(--bg-card, rgba(255,255,255,0.04))',
                    color: 'var(--fg, #f5f5f5)',
                    border: '1px solid var(--line, rgba(255,255,255,0.12))',
                    borderRadius: 6, fontFamily: 'inherit', resize: 'vertical',
                  }} />
              </div>
            ))}
          </div>

          {/* Développement */}
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 8 }}>
              Partie 2 — Développement construit ({payload.controle.points_developpement} pts)
            </div>
            <div style={{
              padding: 10, fontSize: 13, fontStyle: 'italic',
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              borderRadius: 6, marginBottom: 8,
            }}>
              <strong>Sujet :</strong> {payload.controle.developpement.consigne}
            </div>
            {payload.controle.developpement.plan_indicatif?.length > 0 && (
              <div style={{ fontSize: 12, color: 'var(--fg-dim, #aaa)', marginBottom: 8 }}>
                Plan indicatif : {payload.controle.developpement.plan_indicatif.join(' · ')}
              </div>
            )}
            <textarea
              value={academy.parcoursDevAnswer}
              onChange={(e) => academy.setParcoursDevAnswer(e.target.value)}
              rows={14}
              placeholder="Rédige ici ton développement (intro, axes, conclusion)…"
              style={{
                width: '100%', padding: 10, fontSize: 13,
                background: 'var(--bg-card, rgba(255,255,255,0.04))',
                color: 'var(--fg, #f5f5f5)',
                border: '1px solid var(--line, rgba(255,255,255,0.12))',
                borderRadius: 6, fontFamily: 'inherit', resize: 'vertical',
                minHeight: 240,
              }} />
          </div>

          <button type="button"
            onClick={() => void academy.submitParcoursControle()}
            disabled={academy.parcoursCorrecting}
            style={{
              padding: '12px 24px', borderRadius: 99, fontWeight: 700,
              background: 'oklch(0.65 0.18 145 / 0.20)', color: GREEN_FG,
              border: '1px solid oklch(0.65 0.18 145 / 0.55)',
              fontSize: 14, cursor: academy.parcoursCorrecting ? 'wait' : 'pointer',
              alignSelf: 'flex-start',
            }}>
            {academy.parcoursCorrecting ? '⏳ Correction en cours…' : '✓ Soumettre pour correction'}
          </button>
        </>
      )}

      {/* Verdict */}
      {correction && (
        <div style={{
          padding: 18, borderRadius: 10,
          background: 'var(--bg-card, rgba(255,255,255,0.04))',
          border: '1px solid oklch(0.65 0.18 145 / 0.45)',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 18,
            paddingBottom: 12, marginBottom: 12,
            borderBottom: '1px solid var(--line-soft, rgba(255,255,255,0.10))',
          }}>
            <Trophy size={28} color={correction.total >= 12 ? GREEN_FG : 'oklch(0.78 0.16 80)'} />
            <div>
              <div style={{
                fontSize: 44, fontWeight: 900,
                fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
                color: correction.total >= 16 ? GREEN_FG
                  : correction.total >= 12 ? 'oklch(0.78 0.16 80)'
                    : RED_FG,
              }}>
                {correction.total}/{correction.total_max}
              </div>
              <div style={{ fontSize: 16, fontWeight: 700, marginTop: 2 }}>Mention : {correction.mention}</div>
              <div style={{ fontSize: 12, color: 'var(--fg-dim, #aaa)' }}>
                Questions : {correction.questions_score}/{payload.controle.points_questions}
                · Développement : {correction.developpement_score}/{payload.controle.points_developpement}
              </div>
            </div>
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>Détail par question</div>
          {correction.questions_breakdown.map((qb) => (
            <div key={qb.id} style={{
              fontSize: 12, marginBottom: 6, padding: 6,
              background: 'var(--bg-raised, rgba(255,255,255,0.02))', borderRadius: 4,
            }}>
              <strong>Q{qb.id}</strong> {qb.awarded}/{qb.max} — {qb.comment}
            </div>
          ))}
          <div style={{ fontSize: 13, fontWeight: 700, marginTop: 14, marginBottom: 6 }}>Développement</div>
          <div style={{
            fontSize: 12, padding: 8,
            background: 'var(--bg-raised, rgba(255,255,255,0.02))', borderRadius: 4,
          }}>
            <div style={{
              display: 'flex', gap: 14, marginBottom: 6,
              fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
              color: 'var(--fg-dim, #aaa)',
            }}>
              <span>plan {correction.developpement_breakdown.plan_score}</span>
              <span>contenu {correction.developpement_breakdown.contenu_score}</span>
              <span>rigueur {correction.developpement_breakdown.rigueur_score}</span>
              <span>expression {correction.developpement_breakdown.expression_score}</span>
            </div>
            <div style={{ marginBottom: 8 }}>{correction.developpement_breakdown.feedback}</div>
            {correction.developpement_breakdown.erreurs?.length > 0 && (
              <div style={{ color: RED_FG, fontSize: 11, marginBottom: 6 }}>
                ⚠ {correction.developpement_breakdown.erreurs.join(' · ')}
              </div>
            )}
            <div style={{ fontStyle: 'italic', color: GREEN_FG }}>
              ➤ {correction.developpement_breakdown.progression}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
