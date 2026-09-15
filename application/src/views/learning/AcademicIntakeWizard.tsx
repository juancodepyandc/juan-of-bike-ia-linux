// v82nu : pre-questionnaire (4 steps) avant la generation d un parcours
// academique. L objectif est l intuitivite totale demandee par le user :
//   1. Comment tu travailles le mieux ?  (workStyle)
//   2. Format de l eval ?               (examFormat)
//   3. Duree + date de l eval ?         (examDurationMinutes + examDate)
//   4. Concepts precis a maitriser ?    (focusConcepts) — pre-rempli depuis
//      les PDFs deja extraits cote ParcoursPanel.
//
// Le composant est volontairement DETACHE de ParcoursPanel pour rester
// reutilisable (Quiz/Fiches pourraient l utiliser plus tard) et pour eviter
// d alourdir un fichier deja gros.
//
// Conformement aux regles du module : pas d emoji, pas de /no_think.

import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BookOpen, Calendar, ChevronLeft, ChevronRight, Clock, Eye, Hand,
  Headphones, Layers, Sparkles, Target, X,
} from 'lucide-react'
import type { LearnerProfile } from '../../stores/learningSessionStore.ts'

type Props = {
  open: boolean
  initial?: LearnerProfile
  /** Concepts deduits par l UI (depuis les PDFs deja parses) — pre-remplit le step 4. */
  suggestedConcepts?: string
  onCancel: () => void
  onComplete: (profile: LearnerProfile) => void
}

const WORK_STYLES: Array<{ id: NonNullable<LearnerProfile['workStyle']>; label: string; hint: string; icon: typeof Headphones }> = [
  { id: 'audio',    label: 'Audio',    hint: 'Podcasts, oral, écoute',          icon: Headphones },
  { id: 'visuel',   label: 'Visuel',   hint: 'Schemas, mind maps, infographies',icon: Eye },
  { id: 'lecture',  label: 'Lecture',  hint: 'Textes denses, fiches synthese',  icon: BookOpen },
  { id: 'pratique', label: 'Pratique', hint: 'Exercices, redaction, manipulation', icon: Hand },
  { id: 'mixte',    label: 'Mixte',    hint: 'Un peu de tout',                  icon: Layers },
]

const EXAM_FORMATS: Array<{ id: NonNullable<LearnerProfile['examFormat']>; label: string; hint: string }> = [
  { id: 'qcm',          label: 'QCM',          hint: 'Questions a choix multiples' },
  { id: 'dissertation', label: 'Dissertation', hint: 'Redaction longue, argumentee' },
  { id: 'oral',         label: 'Oral',         hint: 'Presentation + questions du jury' },
  { id: 'mixte',        label: 'Mixte',        hint: 'QCM + redaction + analyse de doc' },
  // v83a : format ludique — le parcours devient une enquête / escape game /
  // suite de défis narratifs, pas un simple QCM. Idéal pour réviser autrement.
  { id: 'jeu',          label: 'Jeu / Enquête', hint: 'Escape game, enquete, defis narratifs a etapes' },
]

const DURATIONS: Array<{ value: number; label: string }> = [
  { value: 30,  label: '30 min' },
  { value: 60,  label: '1 h' },
  { value: 120, label: '2 h' },
  { value: 180, label: '3 h' },
  { value: 240, label: '4 h' },
]

export default function AcademicIntakeWizard({ open, initial, suggestedConcepts, onCancel, onComplete }: Props) {
  const [step, setStep] = useState(0)
  const [profile, setProfile] = useState<LearnerProfile>({
    workStyle: initial?.workStyle ?? 'lecture',
    examFormat: initial?.examFormat ?? 'mixte',
    examDurationMinutes: initial?.examDurationMinutes ?? 120,
    examDate: initial?.examDate ?? '',
    focusConcepts: initial?.focusConcepts ?? suggestedConcepts ?? '',
    schoolLevel: initial?.schoolLevel ?? '',
  })

  // Quand le wizard s ouvre / change de pre-rempli, reset au step 0 et
  // synchronise la valeur initiale avec ce que l UI propose.
  useEffect(() => {
    if (open) {
      setStep(0)
      setProfile((p) => ({
        ...p,
        workStyle:           initial?.workStyle           ?? p.workStyle           ?? 'lecture',
        examFormat:          initial?.examFormat          ?? p.examFormat          ?? 'mixte',
        examDurationMinutes: initial?.examDurationMinutes ?? p.examDurationMinutes ?? 120,
        examDate:            initial?.examDate            ?? p.examDate            ?? '',
        focusConcepts:       initial?.focusConcepts       ?? p.focusConcepts       ?? suggestedConcepts ?? '',
        schoolLevel:         initial?.schoolLevel         ?? p.schoolLevel         ?? '',
      }))
    }
  }, [open, initial, suggestedConcepts])

  const totalSteps = 4
  const progressPct = useMemo(() => Math.round(((step + 1) / totalSteps) * 100), [step])

  if (!open) return null

  const next = () => setStep((s) => Math.min(totalSteps - 1, s + 1))
  const prev = () => setStep((s) => Math.max(0, s - 1))
  const finish = () => onComplete(profile)

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0 }}
        className="relative w-full max-w-2xl max-h-[90vh] overflow-hidden rounded-3xl border border-aurora-border bg-aurora-surface shadow-2xl"
      >
        <button
          onClick={onCancel}
          className="absolute right-4 top-4 z-10 rounded-full bg-aurora-surface-2 p-2 text-aurora-text-dim hover:text-aurora-text"
          title="Fermer"
        >
          <X size={16} />
        </button>

        <div className="border-b border-aurora-border/40 bg-gradient-to-r from-violet-500/10 via-cyan-500/10 to-emerald-500/10 px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-gradient-to-br from-violet-400 to-cyan-400 p-2.5 shadow-lg">
              <Sparkles size={18} className="text-white" />
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-[0.22em] text-aurora-text-dim">Avant de generer ton parcours</p>
              <h3 className="text-lg font-bold text-aurora-text">Comment tu apprends le mieux ?</h3>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 text-[10px] text-aurora-text-dim">
            <span>Etape {step + 1} / {totalSteps}</span>
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-aurora-surface-2">
              <motion.div
                animate={{ width: `${progressPct}%` }}
                className="h-full bg-gradient-to-r from-violet-400 to-cyan-400 rounded-full"
              />
            </div>
            <span>{progressPct}%</span>
          </div>
        </div>

        <div className="px-6 py-6 max-h-[60vh] overflow-y-auto">
          <AnimatePresence mode="wait">
            {step === 0 && (
              <motion.div
                key="step0"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                className="space-y-3"
              >
                <p className="text-sm text-aurora-text font-semibold">Comment tu travailles le mieux ?</p>
                <p className="text-xs text-aurora-text-dim">L IA adapte le format des exercices a ton mode preferе.</p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {WORK_STYLES.map((opt) => {
                    const Icon = opt.icon
                    const active = profile.workStyle === opt.id
                    return (
                      <button
                        key={opt.id}
                        onClick={() => setProfile((p) => ({ ...p, workStyle: opt.id }))}
                        className={`rounded-2xl border px-3 py-3 text-left transition-all ${
                          active
                            ? 'border-violet-400/60 bg-violet-500/15 text-aurora-text shadow-lg shadow-violet-500/20'
                            : 'border-aurora-border bg-aurora-surface-2 text-aurora-text-dim hover:border-violet-400/30 hover:text-aurora-text'
                        }`}
                      >
                        <Icon size={16} className={active ? 'text-violet-300 mb-1.5' : 'text-aurora-text-dim mb-1.5'} />
                        <p className="text-sm font-semibold">{opt.label}</p>
                        <p className="text-[10px] text-aurora-text-dim">{opt.hint}</p>
                      </button>
                    )
                  })}
                </div>
              </motion.div>
            )}

            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                className="space-y-3"
              >
                <p className="text-sm text-aurora-text font-semibold">Format de l evaluation ?</p>
                <p className="text-xs text-aurora-text-dim">L IA cale les exercices et le test final sur ce format.</p>
                <div className="grid grid-cols-2 gap-2">
                  {EXAM_FORMATS.map((opt) => {
                    const active = profile.examFormat === opt.id
                    return (
                      <button
                        key={opt.id}
                        onClick={() => setProfile((p) => ({ ...p, examFormat: opt.id }))}
                        className={`rounded-2xl border px-4 py-3 text-left transition-all ${
                          active
                            ? 'border-cyan-400/60 bg-cyan-500/15 text-aurora-text shadow-lg shadow-cyan-500/20'
                            : 'border-aurora-border bg-aurora-surface-2 text-aurora-text-dim hover:border-cyan-400/30 hover:text-aurora-text'
                        }`}
                      >
                        <p className="text-sm font-semibold">{opt.label}</p>
                        <p className="text-[11px] text-aurora-text-dim mt-0.5">{opt.hint}</p>
                      </button>
                    )
                  })}
                </div>
              </motion.div>
            )}

            {step === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                className="space-y-4"
              >
                <div>
                  <p className="text-sm text-aurora-text font-semibold flex items-center gap-2">
                    <Clock size={14} /> Duree de l evaluation
                  </p>
                  <p className="text-xs text-aurora-text-dim">Le test final du parcours respectera ce format-la.</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {DURATIONS.map((d) => {
                      const active = profile.examDurationMinutes === d.value
                      return (
                        <button
                          key={d.value}
                          onClick={() => setProfile((p) => ({ ...p, examDurationMinutes: d.value }))}
                          className={`rounded-full border px-4 py-2 text-xs font-medium transition-all ${
                            active
                              ? 'border-emerald-400/60 bg-emerald-500/20 text-emerald-200'
                              : 'border-aurora-border bg-aurora-surface-2 text-aurora-text-dim hover:text-aurora-text'
                          }`}
                        >
                          {d.label}
                        </button>
                      )
                    })}
                  </div>
                </div>
                <div>
                  <p className="text-sm text-aurora-text font-semibold flex items-center gap-2">
                    <Calendar size={14} /> Date de l evaluation (optionnel)
                  </p>
                  <p className="text-xs text-aurora-text-dim">Permet a l IA de calibrer le rythme du parcours.</p>
                  <input
                    type="date"
                    value={profile.examDate ?? ''}
                    onChange={(e) => setProfile((p) => ({ ...p, examDate: e.target.value }))}
                    className="mt-2 w-full rounded-xl border border-aurora-border bg-aurora-surface-2 px-3 py-2 text-sm text-aurora-text outline-none focus:border-aurora-accent/50"
                  />
                </div>
                <div>
                  <p className="text-sm text-aurora-text font-semibold">Niveau scolaire (optionnel)</p>
                  <input
                    type="text"
                    value={profile.schoolLevel ?? ''}
                    onChange={(e) => setProfile((p) => ({ ...p, schoolLevel: e.target.value }))}
                    placeholder="Ex: Terminale Techno, Master 1, Prepa MPSI..."
                    className="mt-1 w-full rounded-xl border border-aurora-border bg-aurora-surface-2 px-3 py-2 text-sm text-aurora-text outline-none focus:border-aurora-accent/50"
                  />
                </div>
              </motion.div>
            )}

            {step === 3 && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                className="space-y-3"
              >
                <p className="text-sm text-aurora-text font-semibold flex items-center gap-2">
                  <Target size={14} /> Concepts precis a maitriser
                </p>
                <p className="text-xs text-aurora-text-dim">
                  {suggestedConcepts
                    ? 'On a pre-rempli depuis tes documents. Edite si besoin.'
                    : 'Liste les notions cles ou colle ta table des matieres. L IA priorisera ces concepts.'}
                </p>
                <textarea
                  value={profile.focusConcepts ?? ''}
                  onChange={(e) => setProfile((p) => ({ ...p, focusConcepts: e.target.value }))}
                  rows={6}
                  placeholder="Ex: dynamiques territoriales, mondialisation, mers et oceans, etudes de cas Chine et Etats-Unis..."
                  className="w-full rounded-xl border border-aurora-border bg-aurora-surface-2 px-3 py-2 text-sm text-aurora-text outline-none focus:border-aurora-accent/50"
                />
                <div className="rounded-xl border border-emerald-400/30 bg-emerald-500/5 px-3 py-2 text-[11px] text-emerald-300">
                  Pret. Le parcours generera dans la foulee : fiches synthese + mind map + exercices au format choisi + test final calibre sur la duree.
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="flex items-center justify-between gap-2 border-t border-aurora-border/40 bg-aurora-surface-2/40 px-6 py-4">
          <button
            onClick={prev}
            disabled={step === 0}
            className="inline-flex items-center gap-1 rounded-xl border border-aurora-border bg-aurora-surface px-3 py-2 text-xs text-aurora-text-dim transition-colors hover:text-aurora-text disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronLeft size={14} /> Retour
          </button>
          {step < totalSteps - 1 ? (
            <button
              onClick={next}
              className="inline-flex items-center gap-1 rounded-xl gradient-accent px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-aurora-accent/30 hover:shadow-xl"
            >
              Continuer <ChevronRight size={14} />
            </button>
          ) : (
            <button
              onClick={finish}
              className="inline-flex items-center gap-1 rounded-xl bg-gradient-to-r from-violet-500 to-cyan-500 px-4 py-2 text-xs font-semibold text-white shadow-lg hover:shadow-xl"
            >
              <Sparkles size={14} /> Lancer la generation
            </button>
          )}
        </div>
      </motion.div>
    </div>
  )
}
