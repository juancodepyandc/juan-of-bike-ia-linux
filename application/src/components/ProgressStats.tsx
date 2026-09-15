/**
 * ProgressStats — dashboard of mastery per category for Academy.
 *
 * Aggregates :
 *   - total items per kind (cours / exo / fiche / quiz)
 *   - quizHistory scores grouped by topic (via gamificationStore)
 *   - items marked as seen via moduleHistory (optional)
 *
 * Surfaced in the category aside as a foldable panel so the student sees
 * at a glance where they're strong and where they should spend time.
 */
import { useMemo } from 'react'
import { useGamificationStore } from '../stores/gamificationStore.ts'
import { useAcademyStore, type Category } from '../stores/academyStore.ts'

interface Props {
  category: Category
  onClose?: () => void
}

export default function ProgressStats({ category, onClose }: Props) {
  const allQuizHistory = useGamificationStore((s) => s.quizHistory)
  const academyCategories = useAcademyStore((s) => s.categories)

  const stats = useMemo(() => {
    const items = category.items
    const perKind = { cours: 0, exo: 0, fiche: 0, quiz: 0 }
    items.forEach((it) => { perKind[it.kind] = (perKind[it.kind] || 0) + 1 })

    // Topic match : quizHistory records `topic` as a free string. We match
    // on whichever subCategory name appears.
    const subNames = category.subCategories.map((s) => s.name.toLowerCase())
    const relevant = allQuizHistory.filter((q) =>
      subNames.some((sn) => q.topic.toLowerCase().includes(sn))
      || q.topic.toLowerCase().includes(category.name.toLowerCase())
    )
    const avgPct = relevant.length > 0
      ? Math.round((relevant.reduce((s, q) => s + (q.score / q.total), 0) / relevant.length) * 100)
      : null

    const perSub = category.subCategories.map((sub) => {
      const subItems = items.filter((it) => it.subCategoryId === sub.id)
      const subQuizzes = relevant.filter((q) => q.topic.toLowerCase().includes(sub.name.toLowerCase()))
      const mastery = subQuizzes.length > 0
        ? Math.round((subQuizzes.reduce((s, q) => s + (q.score / q.total), 0) / subQuizzes.length) * 100)
        : null
      return { id: sub.id, name: sub.name, itemCount: subItems.length, quizAttempts: subQuizzes.length, mastery }
    })

    return { perKind, perSub, totalItems: items.length, totalQuizzes: relevant.length, avgPct }
  }, [category, allQuizHistory])

  return (
    <div className="ps-panel">
      <div className="ps-head">
        <span className="ps-kicker">PROGRESSION</span>
        <span className="ps-title">{category.name}</span>
        {onClose && <button type="button" className="ps-close" onClick={onClose}>✕</button>}
      </div>

      <div className="ps-overview">
        <div className="ps-mastery">
          <div className="ps-mastery-big">{stats.avgPct ?? '—'}<span>%</span></div>
          <div className="ps-mastery-label">maîtrise</div>
        </div>
        <div className="ps-counts">
          <div>📘 {stats.perKind.cours} cours</div>
          <div>🗂 {stats.perKind.fiche} fiches</div>
          <div>✍ {stats.perKind.exo} exos</div>
          <div>❓ {stats.perKind.quiz} quiz</div>
          <div>📊 {stats.totalQuizzes} quiz faits</div>
        </div>
      </div>

      <div className="ps-sub-list">
        {stats.perSub.map((s) => {
          const hue = s.mastery === null ? 'none' : s.mastery >= 75 ? 'ok' : s.mastery >= 50 ? 'mid' : 'low'
          return (
            <div key={s.id} className={`ps-sub ${hue}`}>
              <div className="ps-sub-name">{s.name}</div>
              <div className="ps-sub-meta">{s.itemCount} fiches · {s.quizAttempts} quiz</div>
              <div className="ps-sub-bar"><span style={{ width: `${s.mastery ?? 0}%` }} /></div>
              <div className="ps-sub-pct">{s.mastery === null ? '—' : `${s.mastery}%`}</div>
            </div>
          )
        })}
      </div>

      <div className="ps-foot">
        {stats.perSub.filter((s) => s.mastery !== null && s.mastery < 50).length > 0 && (
          <span className="ps-weak">
            ⚠ {stats.perSub.filter((s) => s.mastery !== null && s.mastery < 50).length} sous-catégorie(s) à retravailler
          </span>
        )}
      </div>
    </div>
  )
}
