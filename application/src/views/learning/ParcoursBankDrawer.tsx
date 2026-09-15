/**
 * iter35.D — Banque de générations académiques.
 *
 * Drawer qui remplace le floating button "Reprendre la session". Liste tous
 * les parcours générés persistés (zustand persist), regroupés par matière,
 * triés par date desc, avec actions Reprendre/Supprimer. Auto-alimenté via
 * useAcademyViewLogic à chaque génération réussie.
 *
 * UX cohérente avec les autres modules (image / video) qui ont leur dossier
 * de générations accessible depuis le module.
 */
import React, { useMemo } from 'react'
import { useLearningSessionStore, type ParcoursBankEntry } from '../../stores/learningSessionStore.ts'

const GOLD = 'oklch(0.86 0.18 75)'
const PANEL_BG = 'oklch(0.16 0.018 70 / 0.96)'

interface Props {
  open: boolean
  onClose: () => void
  onResume: (entry: ParcoursBankEntry) => void
}

export default function ParcoursBankDrawer({ open, onClose, onResume }: Props) {
  const bank = useLearningSessionStore(s => s.parcoursBank)
  const remove = useLearningSessionStore(s => s.removeFromParcoursBank)

  const grouped = useMemo(() => {
    const map = new Map<string, ParcoursBankEntry[]>()
    for (const e of bank) {
      const key = (e.subject || 'Autre').toLowerCase()
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(e)
    }
    for (const arr of map.values()) arr.sort((a, b) => b.createdAt - a.createdAt)
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]))
  }, [bank])

  if (!open) return null

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 60,
          background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)',
        }}
      />
      <aside className="parcoursBankDrawer" style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: 'min(560px, 92vw)', zIndex: 61,
        background: PANEL_BG,
        borderLeft: `1px solid ${GOLD}55`,
        display: 'flex', flexDirection: 'column',
        boxShadow: '-12px 0 60px rgba(0,0,0,0.6)',
      }}>
        {/* iter38 : sur mobile, drawer plein écran (un panneau étroit
            est inutilisable au tactile). */}
        <style>{`
          @media (max-width: 720px) {
            .parcoursBankDrawer { width: 100% !important; }
          }
        `}</style>
        <header style={{
          padding: '18px 24px', borderBottom: '1px solid rgba(255,255,255,0.1)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div>
            <div style={{
              fontSize: 11, letterSpacing: 1.4, color: GOLD, textTransform: 'uppercase',
              fontFamily: 'var(--font-mono, monospace)',
            }}>
              Module Académie
            </div>
            <h2 style={{ fontSize: 22, margin: '4px 0 0', color: '#fff' }}>
              Banque de générations
            </h2>
          </div>
          <button type="button" onClick={onClose} style={{
            background: 'transparent', color: '#aaa', border: '1px solid rgba(255,255,255,0.2)',
            padding: '6px 12px', borderRadius: 8, cursor: 'pointer', fontSize: 12,
          }}>
            Fermer
          </button>
        </header>

        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px' }}>
          {bank.length === 0 ? (
            <div style={{
              padding: 40, textAlign: 'center', color: 'rgba(255,255,255,0.55)',
              fontSize: 14, lineHeight: 1.6,
            }}>
              <div style={{ fontSize: 38, marginBottom: 12 }}>📚</div>
              Aucune génération encore.<br/>
              Lance ton premier parcours BAC depuis le formulaire à gauche
              et il apparaîtra ici, classé par matière.
            </div>
          ) : grouped.map(([subjectKey, entries]) => (
            <section key={subjectKey} style={{ marginBottom: 24 }}>
              <h3 style={{
                fontSize: 13, color: GOLD, textTransform: 'uppercase',
                letterSpacing: 1.2, fontWeight: 700, marginBottom: 10,
                paddingBottom: 6, borderBottom: '1px solid rgba(255,255,255,0.08)',
                fontFamily: 'var(--font-mono, monospace)',
              }}>
                {entries[0]?.subject || subjectKey} ({entries.length})
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {entries.map(entry => (
                  <BankCard
                    key={entry.id}
                    entry={entry}
                    onResume={() => { onResume(entry); onClose() }}
                    onRemove={() => {
                      if (window.confirm(`Supprimer "${entry.topic}" de la banque ?`)) {
                        remove(entry.id)
                      }
                    }}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      </aside>
    </>
  )
}

function BankCard({ entry, onResume, onRemove }: {
  entry: ParcoursBankEntry
  onResume: () => void
  onRemove: () => void
}) {
  const date = new Date(entry.createdAt)
  const dateStr = date.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
  const timeStr = date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  const score = entry.outcome?.finalScorePct
  return (
    <div style={{
      padding: 14, borderRadius: 10,
      background: 'rgba(255,255,255,0.04)',
      border: '1px solid rgba(255,255,255,0.08)',
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#fff', marginBottom: 4 }}>
            {entry.topic}
          </div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', fontFamily: 'var(--font-mono, monospace)' }}>
            {dateStr} · {timeStr}
            {entry.lessonName ? ` · ${entry.lessonName}` : ''}
            {entry.payload?.is_oral ? ` · 🎤 Oral ${entry.payload.language || ''}` : ''}
          </div>
        </div>
        {typeof score === 'number' && (
          <div style={{
            padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 700,
            background: score >= 80 ? 'rgba(46,204,113,0.18)' : score >= 60 ? 'rgba(241,196,15,0.18)' : 'rgba(231,76,60,0.18)',
            color: score >= 80 ? '#2ecc71' : score >= 60 ? '#f1c40f' : '#e74c3c',
            fontFamily: 'var(--font-mono, monospace)',
          }}>
            {Math.round(score)}%
          </div>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8, fontSize: 11, color: 'rgba(255,255,255,0.6)' }}>
        <span>📘 {entry.payload?.fiches?.length ?? 0} fiches</span>
        <span>·</span>
        <span>📝 {entry.payload?.exos_apprentissage?.length ?? 0} exos</span>
        <span>·</span>
        <span>🎯 {entry.payload?.controle?.questions?.length ?? 0} questions</span>
        {entry.payload?.cartes && entry.payload.cartes.length > 0 && (
          <>
            <span>·</span>
            <span>🗺 {entry.payload.cartes.length} carte{entry.payload.cartes.length > 1 ? 's' : ''}</span>
          </>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <button type="button" onClick={onResume} style={{
          flex: 1, padding: '8px 12px', borderRadius: 8,
          background: `linear-gradient(135deg, ${GOLD}AA, oklch(0.78 0.16 60 / 0.7))`,
          color: '#0a0a0a', border: `1px solid ${GOLD}`,
          fontSize: 12, fontWeight: 700, cursor: 'pointer',
          fontFamily: 'var(--font-mono, monospace)',
        }}>
          Reprendre
        </button>
        <button type="button" onClick={onRemove} style={{
          padding: '8px 12px', borderRadius: 8,
          background: 'transparent', color: 'rgba(231,76,60,0.85)',
          border: '1px solid rgba(231,76,60,0.4)',
          fontSize: 12, cursor: 'pointer',
          fontFamily: 'var(--font-mono, monospace)',
        }}>
          Supprimer
        </button>
      </div>
    </div>
  )
}
