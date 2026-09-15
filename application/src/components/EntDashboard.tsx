/**
 * "Mon ENT" dashboard for the Academy view.
 *
 * The dashboard reads harvested Pronote/ENT data, shows grades and upcoming
 * work, and keeps import setup in Settings so the user does not have to manage
 * duplicate credential flows.
 */
import { useEffect, useMemo, useState } from 'react'
import { useEntSessionStore } from '../stores/entSessionStore.ts'
import { listHarvests, getHarvest, type HarvestNoteItem, type HarvestDevoirItem } from '../services/entHarvestService.ts'
import { analyzeAllSubjects, formatTrend, type SubjectTrend } from '../services/entNotesAnalysis.ts'
import { fastClassify } from '../services/entEvalDetector.ts'
import { readNotifPrefs, writeNotifPrefs, recomputeEvalNotifs, triggerTestNotif, type EntNotifPrefs } from '../services/entNotifScheduler.ts'
import { buildRevisionParcours, saveParcours, type RevisionParcours } from '../services/entRevisionBuilder.ts'
import { fullPipeline } from '../services/entCredentialBridge.ts'
import { ENT_ADAPTERS } from '../services/entAdapters.ts'
import { getBridgeUrl, isTauriRuntime } from '../utils/runtime.ts'

export default function EntDashboard() {
  const desktopNative = isTauriRuntime()
  const session = useEntSessionStore()
  const [notes, setNotes] = useState<HarvestNoteItem[]>([])
  const [devoirs, setDevoirs] = useState<HarvestDevoirItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notifPrefs, setNotifPrefs] = useState<EntNotifPrefs>(() => readNotifPrefs())
  const [building, setBuilding] = useState<string | null>(null)
  const [parcours, setParcours] = useState<RevisionParcours | null>(null)
  const [parcoursError, setParcoursError] = useState<string | null>(null)
  // Browser-only auto-login state. Desktop import is launched from Settings.
  const [autoLoginState, setAutoLoginState] = useState<{
    busy: boolean
    step?: string
    detail?: string
    lastError?: string
    lastResult?: { sections: number; total: number }
  }>({ busy: false })
  const [siteKey, setSiteKey] = useState('')
  const [adapterId, setAdapterId] = useState<string>('pronote')

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const all = await listHarvests()
      // Pour chaque section présente, charger les items.
      const notesH = all.filter((h) => h.section === 'notes')
      const devoirsH = all.filter((h) => h.section === 'devoirs')
      const notesArr: HarvestNoteItem[] = []
      for (const h of notesH) {
        const data = await getHarvest(h.adapter, h.section)
        if (data?.items) notesArr.push(...(data.items as HarvestNoteItem[]))
      }
      const devoirsArr: HarvestDevoirItem[] = []
      for (const h of devoirsH) {
        const data = await getHarvest(h.adapter, h.section)
        if (data?.items) devoirsArr.push(...(data.items as HarvestDevoirItem[]))
      }
      setNotes(notesArr)
      setDevoirs(devoirsArr)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lecture ENT')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh() }, [])

  // Re-compute notifs quand devoirs ou prefs changent.
  useEffect(() => {
    if (devoirs.length > 0) {
      recomputeEvalNotifs(devoirs)
    }
  }, [devoirs, notifPrefs])

  const trends = useMemo(() => analyzeAllSubjects(notes), [notes])
  const upcomingEvals = useMemo(() => {
    const now = Date.now()
    return devoirs
      .map((d) => ({ d, det: fastClassify(d) }))
      .filter((x) => x.det.isEval && x.d.date && new Date(x.d.date).getTime() > now)
      .sort((a, b) => new Date(a.d.date!).getTime() - new Date(b.d.date!).getTime())
      .slice(0, 8)
  }, [devoirs])

  const togglePrefEnabled = () => {
    const next = { ...notifPrefs, enabled: !notifPrefs.enabled }
    setNotifPrefs(next)
    writeNotifPrefs(next)
    if (next.enabled && typeof Notification !== 'undefined' && Notification.permission !== 'granted') {
      try { Notification.requestPermission() } catch { /* noop */ }
    }
  }

  const setLeadDays = (n: 1 | 3 | 7) => {
    const next = { ...notifPrefs, leadDays: n }
    setNotifPrefs(next)
    writeNotifPrefs(next)
  }

  const launchAutoLogin = async () => {
    if (desktopNative) {
      setAutoLoginState({
        busy: false,
        lastError: 'Dans l’app desktop, l’import Pronote se lance depuis Paramètres > Pronote / ENT. Pas besoin de siteKey ni d’extension navigateur.',
      })
      return
    }
    if (!siteKey.trim()) {
      setAutoLoginState({ busy: false, lastError: 'siteKey requis (ex: pronote-lycee-x)' })
      return
    }
    const adapter = ENT_ADAPTERS.find((a) => a.id === adapterId)
    if (!adapter) {
      setAutoLoginState({ busy: false, lastError: 'Adapter inconnu' })
      return
    }
    setAutoLoginState({ busy: true, step: 'init', detail: 'Récupération extension...' })
    // Get active extension id from bridge.
    let extId: string | null = null
    try {
      const r = await fetch(`${getBridgeUrl()}/api/cowork/extension/list`, {
        signal: AbortSignal.timeout(5000),
      })
      const text = await r.text()
      const data = JSON.parse(text || '{}') as { extensions?: Array<{ extId: string }> }
      extId = data.extensions?.[0]?.extId ?? null
    } catch { /* noop */ }
    if (!extId) {
      setAutoLoginState({ busy: false, lastError: 'Aurora-Connect non détectée. L’extension sert seulement au mode navigateur.' })
      return
    }
    const result = await fullPipeline({
      extId,
      siteKey: siteKey.trim(),
      adapter,
      sections: ['devoirs', 'notes'],
      onProgress: (step, detail) => setAutoLoginState({ busy: true, step, detail }),
    })
    if (!result.ok) {
      const reason = result.loginResult.reason
      let err = result.loginResult.message || 'Auto-login échoué'
      if (reason === 'captcha') err = '⚠ CAPTCHA détecté. Complète manuellement puis relance.'
      else if (reason === 'mfa') err = '⚠ Double-facteur détecté. Entre le code manuellement.'
      else if (reason === 'vault_locked') err = '🔒 Vault verrouillé. Ouvre l\'icône Aurora-Connect → Credentials → Déverrouille.'
      else if (reason === 'no_entry') err = `Aucune entrée pour "${siteKey}". Ajoute-la dans le vault.`
      setAutoLoginState({ busy: false, lastError: err })
      return
    }
    // Compute success stats.
    const total = Object.values(result.sectionResults).length
    const successful = Object.values(result.sectionResults).filter((r) => r.ok).length
    setAutoLoginState({
      busy: false,
      lastResult: { sections: successful, total },
    })
    // Refresh harvested data.
    void refresh()
  }

  const launchRevision = async (eval_: HarvestDevoirItem) => {
    setBuilding(eval_.title)
    setParcoursError(null)
    setParcours(null)
    try {
      const trend = trends.find((t) => t.subject === eval_.subject) || null
      const result = await buildRevisionParcours({ eval: eval_, trend })
      if (!result) {
        setParcoursError('Génération échouée. Le LLM Ollama est-il disponible ?')
      } else {
        setParcours(result)
        saveParcours(result)
      }
    } catch (err) {
      setParcoursError(err instanceof Error ? err.message : 'Erreur')
    } finally {
      setBuilding(null)
    }
  }

  return (
    <div style={{
      padding: '14px 18px', borderRadius: 8,
      background: 'var(--bg-card, rgba(255,255,255,0.03))',
      border: '1px solid var(--line, rgba(255,255,255,0.12))',
      display: 'flex', flexDirection: 'column', gap: 12,
      fontFamily: 'var(--font-sans, system-ui)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 18 }}>🏫</span>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: 'var(--fg, #f5f5f5)' }}>Mon ENT</h3>
        <span style={{ flex: 1 }} />
        <button type="button" onClick={() => void refresh()}
          disabled={loading}
          style={{
            padding: '4px 10px', fontSize: 11,
            background: 'transparent', cursor: 'pointer',
            border: '1px solid var(--line, rgba(255,255,255,0.18))',
            color: 'var(--fg-mute, #aaa)', borderRadius: 4,
            fontFamily: 'var(--font-mono, monospace)',
          }}>↻ {loading ? '...' : 'Rafraîchir'}</button>
      </div>

      {error && (
        <div style={{ fontSize: 11, color: 'oklch(0.78 0.16 25)' }}>⚠ {error}</div>
      )}

      {/* Import entry point */}
      <div style={{
        padding: 8, borderRadius: 4,
        background: 'var(--bg-raised, rgba(255,255,255,0.04))',
        border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
        display: 'flex', flexDirection: 'column', gap: 6,
      }}>
        <div style={{
          fontSize: 9, fontFamily: 'var(--font-mono, monospace)',
          letterSpacing: '0.22em', textTransform: 'uppercase',
          color: 'var(--fg-mute, #888)',
        }}>{desktopNative ? '🔐 Import centralisé' : '🔐 Auto-login + scrape'}</div>
        {desktopNative ? (
          <div style={{ fontSize: 11, color: 'var(--fg-mute, #aaa)', lineHeight: 1.45 }}>
            L’import Pronote desktop est centralisé dans Paramètres &gt; Pronote / ENT :
            lycée + ville, sélection Pronote, identifiant, mot de passe, puis import natif.
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 6, fontSize: 11, fontFamily: 'var(--font-mono, monospace)' }}>
            <select value={adapterId} onChange={(e) => setAdapterId(e.target.value)}
              style={{
                padding: '4px 8px', background: 'var(--bg-card, rgba(255,255,255,0.04))',
                color: 'var(--fg, #f5f5f5)',
                border: '1px solid var(--line, rgba(255,255,255,0.18))',
                borderRadius: 3, fontFamily: 'inherit', fontSize: 'inherit',
              }}>
              {ENT_ADAPTERS.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
            </select>
            <input type="text" value={siteKey}
              onChange={(e) => setSiteKey(e.target.value)}
              placeholder="siteKey (ex: pronote-lycee-voltaire)"
              style={{
                flex: 1, padding: '4px 8px',
                background: 'var(--bg-card, rgba(255,255,255,0.04))',
                color: 'var(--fg, #f5f5f5)',
                border: '1px solid var(--line, rgba(255,255,255,0.18))',
                borderRadius: 3, fontFamily: 'inherit', fontSize: 'inherit',
              }} />
            <button type="button" onClick={() => void launchAutoLogin()}
              disabled={autoLoginState.busy || !siteKey.trim()}
              style={{
                padding: '4px 10px',
                background: 'oklch(0.74 0.13 60 / 0.20)',
                color: 'oklch(0.78 0.16 60)',
                border: '1px solid oklch(0.74 0.13 60 / 0.45)',
                borderRadius: 3, cursor: autoLoginState.busy ? 'wait' : 'pointer',
                fontFamily: 'inherit', fontSize: 'inherit',
              }}>
              {autoLoginState.busy ? '⏳' : '🚀 Lancer'}
            </button>
          </div>
        )}
        {autoLoginState.busy && autoLoginState.step && (
          <div style={{ fontSize: 10, color: 'var(--fg-mute, #888)' }}>
            ⏳ {autoLoginState.step}: {autoLoginState.detail}
          </div>
        )}
        {autoLoginState.lastError && (
          <div style={{ fontSize: 11, color: 'oklch(0.78 0.16 25)' }}>{autoLoginState.lastError}</div>
        )}
        {autoLoginState.lastResult && (
          <div style={{ fontSize: 11, color: 'oklch(0.78 0.16 145)' }}>
            ✓ {autoLoginState.lastResult.sections}/{autoLoginState.lastResult.total} sections importées
          </div>
        )}
      </div>

      {!session.hasAnyHarvest ? (
        <div style={{ fontSize: 12, color: 'var(--fg-mute, #aaa)', lineHeight: 1.5 }}>
          {desktopNative
            ? 'Aucune donnée ENT importée. Ouvre Paramètres > Pronote / ENT pour lancer la session native et alimenter l’espace académique.'
            : 'Aucune donnée ENT importée. Configure le vault credentials via l’extension Aurora-Connect, puis lance l’auto-login ci-dessus.'}
        </div>
      ) : (
        <>
          {/* Trends par matière */}
          {trends.length > 0 && (
            <div>
              <div style={{
                fontSize: 9, fontFamily: 'var(--font-mono, monospace)',
                letterSpacing: '0.22em', textTransform: 'uppercase',
                color: 'var(--fg-mute, #888)', marginBottom: 6,
              }}>📊 Mes matières · priorité décroissante</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {trends.map((t) => <TrendCard key={t.subject} trend={t} />)}
              </div>
            </div>
          )}

          {/* Évals à venir */}
          {upcomingEvals.length > 0 && (
            <div>
              <div style={{
                fontSize: 9, fontFamily: 'var(--font-mono, monospace)',
                letterSpacing: '0.22em', textTransform: 'uppercase',
                color: 'var(--fg-mute, #888)', marginBottom: 6,
              }}>📅 Évals à venir</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {upcomingEvals.map((x, i) => (
                  <EvalCard key={i} item={x.d}
                    onPrepare={() => void launchRevision(x.d)}
                    busy={building === x.d.title} />
                ))}
              </div>
            </div>
          )}

          {/* Notif prefs */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px',
            background: 'var(--bg-raised, rgba(255,255,255,0.04))',
            borderRadius: 4, fontSize: 11,
            fontFamily: 'var(--font-mono, monospace)',
            color: 'var(--fg-mute, #aaa)',
          }}>
            <input type="checkbox" checked={notifPrefs.enabled}
              onChange={togglePrefEnabled}
              id="ent-notif-toggle"
              style={{ cursor: 'pointer' }} />
            <label htmlFor="ent-notif-toggle" style={{ cursor: 'pointer' }}>
              🔔 Notifs avant éval
            </label>
            {notifPrefs.enabled && (
              <>
                <span>·</span>
                <span>Préavis :</span>
                {[1, 3, 7].map((n) => (
                  <button key={n} type="button"
                    onClick={() => setLeadDays(n as 1 | 3 | 7)}
                    style={{
                      padding: '2px 8px', fontSize: 10,
                      background: notifPrefs.leadDays === n
                        ? 'oklch(0.74 0.13 60 / 0.20)' : 'transparent',
                      color: notifPrefs.leadDays === n
                        ? 'oklch(0.74 0.13 60)' : 'var(--fg-mute, #888)',
                      border: `1px solid ${notifPrefs.leadDays === n
                        ? 'oklch(0.74 0.13 60 / 0.45)'
                        : 'var(--line, rgba(255,255,255,0.12))'}`,
                      borderRadius: 3, cursor: 'pointer',
                      fontFamily: 'inherit',
                    }}>{n}j</button>
                ))}
                <span style={{ flex: 1 }} />
                <button type="button" onClick={() => triggerTestNotif()}
                  style={{
                    padding: '2px 8px', fontSize: 10,
                    background: 'transparent',
                    border: '1px solid var(--line, rgba(255,255,255,0.12))',
                    color: 'var(--fg-mute, #888)', borderRadius: 3,
                    cursor: 'pointer', fontFamily: 'inherit',
                  }}>Test</button>
              </>
            )}
          </div>

          {/* Parcours */}
          {parcoursError && (
            <div style={{ fontSize: 11, color: 'oklch(0.78 0.16 25)' }}>⚠ {parcoursError}</div>
          )}
          {parcours && <ParcoursDisplay parcours={parcours} onClose={() => setParcours(null)} />}
        </>
      )}

      <div style={{ fontSize: 9, color: 'var(--fg-mute, #777)', fontFamily: 'var(--font-mono, monospace)' }}>
        {session.activeAdapter ? `${session.activeAdapter} actif` : 'pas de session ENT'}
        {' · '}
        {trends.length} matière(s) · {upcomingEvals.length} éval(s)
      </div>
    </div>
  )
}

function TrendCard({ trend }: { trend: SubjectTrend }) {
  const arrow = trend.direction === 'up' ? '▲' : trend.direction === 'down' ? '▼' : '→'
  const arrowColor = trend.direction === 'up' ? 'oklch(0.70 0.15 145)'
    : trend.direction === 'down' ? 'oklch(0.62 0.20 25)'
    : 'var(--fg-mute, #888)'
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '120px 1fr auto',
      gap: 8, alignItems: 'center', padding: '4px 8px',
      fontSize: 12, fontFamily: 'var(--font-mono, monospace)',
      borderRadius: 3,
    }}>
      <span style={{ color: 'var(--fg, #f5f5f5)' }}>{trend.subject}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ color: arrowColor, fontWeight: 700 }}>{arrow}</span>
        <span style={{ color: 'var(--fg-mute, #aaa)' }}>{formatTrend(trend)}</span>
      </div>
      <span style={{
        padding: '1px 6px', fontSize: 10,
        background: trend.priority > 60 ? 'oklch(0.62 0.20 25 / 0.15)'
          : trend.priority > 30 ? 'oklch(0.78 0.16 80 / 0.15)'
          : 'oklch(0.70 0.13 145 / 0.15)',
        color: trend.priority > 60 ? 'oklch(0.78 0.16 25)'
          : trend.priority > 30 ? 'oklch(0.78 0.16 80)'
          : 'oklch(0.70 0.13 145)',
        borderRadius: 3,
      }}>p{trend.priority}</span>
    </div>
  )
}

function EvalCard({ item, onPrepare, busy }: {
  item: HarvestDevoirItem; onPrepare: () => void; busy: boolean
}) {
  const dueIn = item.date ? Math.ceil((new Date(item.date).getTime() - Date.now()) / (24 * 3600 * 1000)) : null
  const urgency = dueIn === null ? 'unknown' : dueIn <= 1 ? 'imminent' : dueIn <= 3 ? 'soon' : 'far'
  const color = urgency === 'imminent' ? 'oklch(0.62 0.20 25)'
    : urgency === 'soon' ? 'oklch(0.78 0.16 80)'
    : 'oklch(0.70 0.13 145)'
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '70px 1fr auto',
      gap: 8, alignItems: 'center', padding: '4px 8px',
      fontSize: 12, fontFamily: 'var(--font-mono, monospace)',
      background: 'var(--bg-raised, rgba(255,255,255,0.02))',
      borderRadius: 3,
    }}>
      <span style={{ color, fontWeight: 700 }}>
        {dueIn !== null ? `${dueIn > 0 ? `J-${dueIn}` : 'aujourd\'hui'}` : '—'}
      </span>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <span style={{ color: 'var(--fg, #f5f5f5)', fontSize: 12 }}>
          {item.subject ? `${item.subject} · ` : ''}{item.title}
        </span>
        {item.date && (
          <span style={{ color: 'var(--fg-mute, #888)', fontSize: 10 }}>
            {new Date(item.date).toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit', month: '2-digit' })}
          </span>
        )}
      </div>
      <button type="button" onClick={onPrepare} disabled={busy}
        style={{
          padding: '4px 10px', fontSize: 11,
          background: busy ? 'var(--bg-card, rgba(255,255,255,0.04))' : 'oklch(0.74 0.13 60 / 0.10)',
          color: busy ? 'var(--fg-mute, #888)' : 'oklch(0.74 0.13 60)',
          border: `1px solid ${busy ? 'var(--line, rgba(255,255,255,0.12))' : 'oklch(0.74 0.13 60 / 0.45)'}`,
          borderRadius: 4, cursor: busy ? 'wait' : 'pointer',
          fontFamily: 'inherit',
        }}>
        {busy ? '⏳ génération...' : '🎯 Préparer'}
      </button>
    </div>
  )
}

function ParcoursDisplay({ parcours, onClose }: { parcours: RevisionParcours; onClose: () => void }) {
  return (
    <div style={{
      padding: 12, borderRadius: 6,
      background: 'oklch(0.74 0.13 60 / 0.06)',
      border: '1px solid oklch(0.74 0.13 60 / 0.30)',
      display: 'flex', flexDirection: 'column', gap: 8,
      fontFamily: 'var(--font-sans, system-ui)', fontSize: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 14 }}>🎯</span>
        <strong style={{ color: 'oklch(0.78 0.16 60)' }}>
          Parcours révision · {parcours.meta.subject} · {parcours.meta.chapter}
        </strong>
        <span style={{ flex: 1 }} />
        <button type="button" onClick={onClose}
          style={{
            padding: '2px 8px', fontSize: 10,
            background: 'transparent', cursor: 'pointer',
            border: '1px solid var(--line, rgba(255,255,255,0.18))',
            color: 'var(--fg-mute, #888)', borderRadius: 3,
            fontFamily: 'var(--font-mono, monospace)',
          }}>×</button>
      </div>
      <div style={{ fontSize: 10, color: 'var(--fg-mute, #888)' }}>
        Calibrage : {parcours.meta.calibratedFor} · {parcours.fiches.length} fiches · {parcours.flashcards.length} flashcards · {parcours.exercises.length} exos
      </div>
      {parcours.fiches.length > 0 && (
        <div>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>📑 Fiches</div>
          {parcours.fiches.map((f, i) => (
            <div key={i} style={{ marginBottom: 6, paddingLeft: 8, borderLeft: '2px solid oklch(0.74 0.13 60 / 0.4)' }}>
              <div style={{ fontWeight: 600 }}>{f.title}</div>
              <div style={{ color: 'var(--fg-mute, #aaa)', fontSize: 11 }}>{f.summary}</div>
              {f.definitions?.length > 0 && (
                <ul style={{ margin: '4px 0 0', paddingLeft: 16, fontSize: 11 }}>
                  {f.definitions.map((d, j) => (
                    <li key={j}><strong>{d.term}</strong> : {d.def}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
      {parcours.flashcards.length > 0 && (
        <div>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>🃏 Flashcards</div>
          {parcours.flashcards.map((c, i) => (
            <details key={i} style={{ marginBottom: 4, fontSize: 11 }}>
              <summary style={{ cursor: 'pointer', color: 'var(--fg, #f5f5f5)' }}>{c.question}</summary>
              <div style={{ paddingLeft: 12, paddingTop: 4, color: 'var(--fg-mute, #aaa)' }}>{c.answer}</div>
            </details>
          ))}
        </div>
      )}
      {parcours.exercises.length > 0 && (
        <div>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>✏️ Exercices</div>
          {parcours.exercises.map((e, i) => (
            <details key={i} style={{ marginBottom: 4, fontSize: 11 }}>
              <summary style={{ cursor: 'pointer', color: 'var(--fg, #f5f5f5)' }}>
                [{e.difficulty}] {e.question}
              </summary>
              <ol style={{ paddingLeft: 18, marginTop: 4, color: 'var(--fg-mute, #aaa)' }}>
                {e.steps?.map((s, j) => <li key={j}>{s}</li>)}
              </ol>
              {e.finalAnswer && (
                <div style={{ paddingLeft: 12, color: 'oklch(0.70 0.13 145)' }}>
                  → {e.finalAnswer}
                </div>
              )}
            </details>
          ))}
        </div>
      )}
    </div>
  )
}
