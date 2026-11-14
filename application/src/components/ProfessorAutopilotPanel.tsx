/**
 * ProfessorAutopilotPanel — « Améliorer l'IA » : starts, stops and follows the professor autopilot on the PC.
 *
 * The autopilot trains on Kaggle (one machine trains, a separate one examines), installs a reinforced model only
 * if it beats the one in use, and activates it only if it wins the same exam again as served by Ollama. Status is
 * polled with a plain fetch after a device-session check, so a background poll never opens the pairing dialog;
 * actions go through bridgeFetch, which asks for the connection when the bridge refuses a public request.
 */
import React, { useEffect, useState } from 'react'
import { getBridgeUrl } from '../utils/runtime.ts'
import { bridgeFetch, readBridgeKey } from '../utils/bridgeAuth.ts'
import { describeStatus, type ProfessorStatus } from '../utils/professorStatus.ts'

const POLL_MS = 15000

async function readError(response: Response): Promise<string> {
  const data = await response.json().catch(() => null) as { error?: string } | null
  return data?.error || `Le PC a répondu ${response.status}.`
}

export default function ProfessorAutopilotPanel() {
  const [status, setStatus] = useState<ProfessorStatus | null>(null)
  const [connected, setConnected] = useState(true)
  const [error, setError] = useState('')
  const [pending, setPending] = useState('')
  const [activate, setActivate] = useState(true)

  useEffect(() => {
    let alive = true
    let busy = false
    const poll = async () => {
      if (busy || document.hidden) return
      busy = true
      try {
        const key = readBridgeKey()
        const session = await fetch(getBridgeUrl() + '/api/devices/session', {
          headers: key ? { Authorization: `Bearer ${key}` } : {},
          signal: AbortSignal.timeout(8000),
        }).then((r) => r.json()).catch(() => ({ connected: true }))
        if (!alive) return
        setConnected(Boolean(session.connected))
        if (!session.connected) return
        const response = await fetch(getBridgeUrl() + '/api/professor/autopilot', {
          headers: key ? { Authorization: `Bearer ${key}` } : {},
          signal: AbortSignal.timeout(8000),
        })
        if (!response.ok) throw new Error(await readError(response))
        const data = await response.json() as ProfessorStatus
        if (alive) { setStatus(data); setError('') }
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : 'Le PC est momentanément injoignable.')
      } finally {
        busy = false
      }
    }
    void poll()
    const timer = setInterval(() => void poll(), POLL_MS)
    return () => { alive = false; clearInterval(timer) }
  }, [])

  const act = async (path: string, body: Record<string, unknown> = {}) => {
    if (pending) return
    setPending(path)
    try {
      const response = await bridgeFetch(getBridgeUrl() + `/api/professor/autopilot/${path}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      if (!response.ok && response.status !== 409) throw new Error(await readError(response))
      setError('')
      const refreshed = await bridgeFetch(getBridgeUrl() + '/api/professor/autopilot')
      if (refreshed.ok) setStatus(await refreshed.json() as ProfessorStatus)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action impossible.')
    } finally {
      setPending('')
    }
  }

  const view = describeStatus(status)
  return (
    <div className="sp-sec" aria-label="Améliorer l'IA">
      <label className="sp-label">Améliorer l'IA (autopilote professeur)</label>
      <div className="sp-hint">
        Kaggle entraîne sur une machine et examine sur une autre ; un modèle n'est installé que s'il bat celui en place,
        et activé seulement s'il regagne l'examen tel que servi par Ollama.
      </div>
      {!connected && <div className="sp-hint">Connecte cet appareil au PC pour suivre l'autopilote.</div>}
      {status && <div className="sp-hint" role="status">{view.headline}</div>}
      {status && view.supported && <div className="sp-hint">{view.quota}</div>}
      {view.students.map((student) => (
        <div key={student.tag} className="sp-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}>
          <strong>{student.tag}</strong>
          <span className="sp-hint">
            {student.phase}{student.detail ? ` · ${student.detail}` : ''} · meilleur vérifié : {student.best} · actif sur ce PC : {student.installed}
          </span>
          {student.warning && (
            <button type="button" className="sp-btn" disabled={Boolean(pending)} onClick={() => void act('resume', { student: student.tag })}>
              Reprendre {student.tag}
            </button>
          )}
        </div>
      ))}
      <div className="sp-row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <button type="button" className="sp-btn is-primary" disabled={!view.canStart || Boolean(pending)}
          onClick={() => void act('start', { activate })}>
          {pending === 'start' ? 'Démarrage…' : 'Démarrer'}
        </button>
        <button type="button" className="sp-btn is-danger" disabled={!view.canStop || Boolean(pending)} onClick={() => void act('stop')}>
          {pending === 'stop' ? 'Arrêt demandé…' : 'Arrêter'}
        </button>
        <label className="sp-hint" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <input type="checkbox" checked={activate} onChange={(e) => setActivate(e.target.checked)} />
          activer automatiquement un modèle vérifié
        </label>
      </div>
      {error && <div className="sp-hint" role="alert">{error}</div>}
      {view.events.length > 0 && (
        <details>
          <summary className="sp-hint">Derniers événements</summary>
          <ul className="sp-hint" style={{ margin: 0, paddingLeft: 18 }}>
            {view.events.map((event, index) => <li key={index}>{event.when} — {event.text}</li>)}
          </ul>
        </details>
      )}
    </div>
  )
}
