/**
 * ExamBlancPanel — mode examen blanc pour une sous-catégorie Academy.
 *
 * Flow :
 *  1. Choisir durée (30 / 60 / 120 min) + nombre de questions (5..20)
 *  2. L'IA construit un packet : N questions variées tirées du niveau de la
 *     sous-catégorie (cours + fiches existantes comme contexte)
 *  3. Countdown timer. L'élève répond dans des textareas.
 *  4. Au temps zéro OU sur "Rendre la copie" : grading global via labAssistant
 *     + note simulée sur 20, forces/faiblesses, conseils de révision
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAppStore } from '../stores/appStore.ts'
import { ollamaChat } from '../hooks/useTauri.ts'
import MarkdownPro from './MarkdownPro.tsx'

interface Question {
  id: string
  prompt: string
  /** Internally stored expected-answer hint, never shown before grading. */
  solutionHint?: string
  /** Number of points allocated for the exam scale. */
  points: number
}

interface GradeReport {
  score20: number
  totalPoints: number
  acquired: number
  per: Array<{
    id: string
    verdict: 'correct' | 'partial' | 'incorrect' | 'off_topic'
    score: number
    feedback: string
    strengths: string[]
    gaps: string[]
  }>
  summary: string
  strongAreas: string[]
  weakAreas: string[]
  next_revision_plan: string
}

interface Props {
  subject: string
  catName: string
  subName: string
  /** Optional knowledge context (existing fiche/cours text merged) */
  context?: string
  onClose: () => void
}

const PRESETS = [
  { minutes: 30, questions: 5,  label: '⏱ Éclair 30 min · 5 Q' },
  { minutes: 60, questions: 10, label: '⏱ Standard 1 h · 10 Q' },
  { minutes: 120, questions: 15, label: '⏱ Long 2 h · 15 Q' },
]

function formatTimer(seconds: number): string {
  const mm = Math.max(0, Math.floor(seconds / 60))
  const ss = Math.max(0, seconds % 60)
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

export default function ExamBlancPanel({ subject, catName, subName, context, onClose }: Props) {
  const mainModel = useAppStore((s) => s.mainModel)
  const [phase, setPhase] = useState<'setup' | 'generating' | 'running' | 'grading' | 'done'>('setup')
  const [minutes, setMinutes] = useState(60)
  const [nQuestions, setNQuestions] = useState(10)
  const [questions, setQuestions] = useState<Question[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [secondsLeft, setSecondsLeft] = useState(0)
  const [report, setReport] = useState<GradeReport | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Countdown
  useEffect(() => {
    if (phase !== 'running') return
    tickRef.current = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          clearInterval(tickRef.current!)
          void submit()
          return 0
        }
        return s - 1
      })
    }, 1000)
    return () => { if (tickRef.current) clearInterval(tickRef.current) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase])

  const launch = useCallback(async () => {
    setPhase('generating')
    setErr(null)
    try {
      const prompt = [
        `Construis un EXAMEN BLANC (${nQuestions} questions) pour ${subject} — catégorie ${catName} / sous-catégorie ${subName}.`,
        'Le barème total fait 20 points. Répartis les points en fonction de la difficulté (sommaire = 1 pt, cas appliqué = 3 pts, problème = 5 pts).',
        'Varie les formats : QCM discursif impossible (l\'élève répond librement), petits calculs, explication, cas pratique, application numérique.',
        'Inclus AU MOINS 1 question piège/ouverture.',
        '',
        context ? `CONTEXTE (cours/fiches déjà étudiés, à respecter pour le niveau) :\n${context.slice(0, 5000)}\n` : '',
        '',
        'Réponds UNIQUEMENT par ce JSON dans un bloc ```json :',
        '{',
        '  "questions": [',
        '    { "id": "q1", "prompt": "énoncé avec markdown + latex $...$ si besoin", "points": 2, "solutionHint": "ce que l\'élève devrait produire (gardé côté correcteur)" }',
        '  ]',
        '}',
        '',
        'Contrainte : somme de tous les `points` doit faire EXACTEMENT 20.',
      ].filter(Boolean).join('\n')

      const res: any = await ollamaChat(mainModel, [
        { role: 'system', content: 'Tu es un enseignant qui conçoit des examens blancs de lycée / BAC. Tu es rigoureux, pas de blabla, uniquement le JSON demandé.' },
        { role: 'user', content: prompt },
      ], 0.35)
      const raw: string = res?.message?.content ?? res?.response ?? ''
      const fence = raw.match(/```(?:json)?\s*([\s\S]+?)```/)
      const body = fence ? fence[1] : raw
      const parsed = JSON.parse(body.slice(body.indexOf('{'), body.lastIndexOf('}') + 1))
      if (!Array.isArray(parsed.questions) || parsed.questions.length === 0) {
        throw new Error('IA n\'a pas produit de questions')
      }
      setQuestions(parsed.questions.map((q: any, i: number) => ({
        id: q.id || `q${i + 1}`,
        prompt: String(q.prompt || ''),
        points: Math.max(1, Math.round(Number(q.points) || 2)),
        solutionHint: q.solutionHint || q.solution_hint || '',
      })))
      setAnswers({})
      setSecondsLeft(minutes * 60)
      setPhase('running')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
      setPhase('setup')
    }
  }, [context, catName, mainModel, minutes, nQuestions, subName, subject])

  const submit = useCallback(async () => {
    if (phase === 'grading' || phase === 'done') return
    setPhase('grading')
    try {
      const mod = await import('../services/labAssistant')
      const per: GradeReport['per'] = []
      let acquired = 0
      const totalPoints = questions.reduce((s, q) => s + q.points, 0)
      for (const q of questions) {
        const ans = (answers[q.id] || '').trim()
        // Empty answer -> 0 immediately
        if (!ans) {
          per.push({ id: q.id, verdict: 'off_topic', score: 0, feedback: 'Question non traitée', strengths: [], gaps: ['rien écrit'] })
          continue
        }
        const g = await mod.gradeAnswer(mainModel, q.prompt, ans, {
          subject: `${subject} · ${subName}`,
          solutionHint: q.solutionHint,
        })
        acquired += (q.points * g.score) / 100
        per.push({
          id: q.id,
          verdict: g.verdict,
          score: g.score,
          feedback: g.summary,
          strengths: g.strengths,
          gaps: g.gaps,
        })
      }
      const score20 = Math.round((acquired / (totalPoints || 1)) * 20 * 10) / 10
      // Strong / weak areas : simple aggregation of strengths/gaps
      const strongAreas = Array.from(new Set(per.flatMap((p) => p.strengths))).slice(0, 5)
      const weakAreas   = Array.from(new Set(per.flatMap((p) => p.gaps))).slice(0, 5)
      // Ask the model for a tailored revision plan
      let plan = 'Refais les questions à score < 50% et reprends les fiches correspondantes.'
      try {
        const planRes: any = await ollamaChat(mainModel, [
          { role: 'system', content: 'Tu es un enseignant qui conseille un plan de révision court (3-5 lignes) basé sur les lacunes données. Pas de disclaimer.' },
          { role: 'user', content: `Sujet : ${subject} · ${subName}\nNote : ${score20}/20\nFaiblesses : ${weakAreas.join(', ')}\nForces : ${strongAreas.join(', ')}\n\nDonne un plan de révision actionnable en 3-5 lignes.` },
        ], 0.3)
        const raw: string = planRes?.message?.content ?? ''
        if (raw.trim()) plan = raw.trim().slice(0, 800)
      } catch { /* keep default */ }

      setReport({
        score20, totalPoints, acquired,
        per, summary: `${per.filter((p) => p.verdict === 'correct').length}/${per.length} questions traitées correctement`,
        strongAreas, weakAreas,
        next_revision_plan: plan,
      })
      setPhase('done')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
      setPhase('running')
    }
  }, [answers, mainModel, phase, questions, subject, subName])

  // ------------------------- RENDER --------------------------------------

  return (
    <div className="exam-blanc-overlay" role="dialog">
      <div className="exam-blanc-panel">
        <header className="exam-blanc-head">
          <div>
            <div className="exam-blanc-kicker">EXAMEN BLANC · {catName}</div>
            <div className="exam-blanc-title">{subName}</div>
          </div>
          {phase === 'running' && (
            <div className={`exam-blanc-timer ${secondsLeft < 60 ? 'is-urgent' : ''}`}>
              ⏱ {formatTimer(secondsLeft)}
            </div>
          )}
          <button type="button" onClick={onClose} className="exam-blanc-close">✕</button>
        </header>

        {err && <div className="exam-blanc-err">⚠ {err}</div>}

        {phase === 'setup' && (
          <div className="exam-blanc-setup">
            <div className="exam-blanc-presets">
              {PRESETS.map((p) => (
                <button key={p.label} type="button"
                  className={`exam-preset ${minutes === p.minutes && nQuestions === p.questions ? 'is-active' : ''}`}
                  onClick={() => { setMinutes(p.minutes); setNQuestions(p.questions) }}>
                  {p.label}
                </button>
              ))}
            </div>
            <div className="exam-blanc-custom">
              <label>Minutes : <input type="number" min={10} max={240} value={minutes} onChange={(e) => setMinutes(Math.max(5, Math.min(240, Number(e.target.value) || 60)))} /></label>
              <label>Questions : <input type="number" min={3} max={30} value={nQuestions} onChange={(e) => setNQuestions(Math.max(3, Math.min(30, Number(e.target.value) || 10)))} /></label>
            </div>
            <button type="button" className="exam-blanc-launch" onClick={launch}>
              🎯 Lancer l'examen blanc
            </button>
            <p className="exam-blanc-hint">
              Le barème sera sur <b>20 points</b>. Tu répondras dans des cases, et au temps 0 (ou dès que tu rends la copie) l'IA notera chaque réponse, calculera ta note, et te donnera un plan de révision ciblé.
            </p>
          </div>
        )}

        {phase === 'generating' && (
          <div className="exam-blanc-busy">📝 L'enseignant prépare ton épreuve…</div>
        )}

        {phase === 'running' && (
          <div className="exam-blanc-running">
            <div className="exam-blanc-progress">
              Répondu : {Object.values(answers).filter((v) => v.trim()).length} / {questions.length}
            </div>
            <ol className="exam-blanc-questions">
              {questions.map((q, i) => (
                <li key={q.id} className="exam-blanc-q">
                  <div className="exam-blanc-q-head">
                    <span className="exam-blanc-q-num">Q{i + 1}</span>
                    <span className="exam-blanc-q-pts">{q.points} pt{q.points > 1 ? 's' : ''}</span>
                  </div>
                  <div className="exam-blanc-q-prompt">
                    <MarkdownPro content={q.prompt} idPrefix={`eb-${q.id}`} />
                  </div>
                  <textarea
                    rows={4}
                    value={answers[q.id] || ''}
                    onChange={(e) => setAnswers((p) => ({ ...p, [q.id]: e.target.value }))}
                    placeholder="Ta réponse, calculs, raisonnement…"
                  />
                </li>
              ))}
            </ol>
            <button type="button" className="exam-blanc-launch" onClick={() => void submit()}>
              ✅ Rendre la copie
            </button>
          </div>
        )}

        {phase === 'grading' && (
          <div className="exam-blanc-busy">🧠 Correction en cours — l'enseignant évalue chaque réponse…</div>
        )}

        {phase === 'done' && report && (
          <div className="exam-blanc-report">
            <div className="exam-blanc-score">
              <div className="exam-blanc-score-big">{report.score20}<span>/20</span></div>
              <div className="exam-blanc-score-meta">{report.summary}</div>
            </div>
            {report.strongAreas.length > 0 && (
              <div className="exam-blanc-sec is-ok">
                <b>Points forts</b>
                <ul>{report.strongAreas.map((s, i) => <li key={i}>✓ {s}</li>)}</ul>
              </div>
            )}
            {report.weakAreas.length > 0 && (
              <div className="exam-blanc-sec is-gap">
                <b>Points à retravailler</b>
                <ul>{report.weakAreas.map((s, i) => <li key={i}>△ {s}</li>)}</ul>
              </div>
            )}
            <div className="exam-blanc-plan">
              <b>Plan de révision</b>
              <div>{report.next_revision_plan}</div>
            </div>
            <details className="exam-blanc-detail">
              <summary>Détail par question</summary>
              <ol>
                {report.per.map((p) => (
                  <li key={p.id} className={`verdict-${p.verdict}`}>
                    <b>{p.id.toUpperCase()}</b> — {p.score}/100 · {p.feedback}
                  </li>
                ))}
              </ol>
            </details>
            <button type="button" className="exam-blanc-launch" onClick={onClose}>Fermer</button>
          </div>
        )}
      </div>
    </div>
  )
}
