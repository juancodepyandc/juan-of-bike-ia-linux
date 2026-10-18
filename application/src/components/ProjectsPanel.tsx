import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { getBridgeUrl } from '../utils/runtime.ts'
import { bridgeFetch, readBridgeKey } from '../utils/bridgeAuth.ts'
import { useAppStore } from '../stores/appStore.ts'

type Schedule = {
  queue_position: number
  ahead_count: number
  elapsed_seconds: number
  estimated_duration_seconds: number | null
  remaining_seconds: number | null
  wait_seconds: number | null
  estimate_sample_count: number
}

type Project = {
  assemblies?: { name: string; url: string }[]
  resumable?: boolean
  viewer_url?: string | null
  result?: string | null
  id: string
  module?: string
  design_id?: string
  title: string
  status: string
  steps: number
  verified_count: number
  criteria_count: number
  scheduling: Schedule
  liveDetail?: string
  liveProgress?: number
  isFrontendLive?: boolean
}

export function duration(seconds: number | null | undefined) {
  return seconds == null
    ? 'Estimation en préparation'
    : seconds < 60
      ? `${Math.ceil(seconds)} s`
      : `≈ ${Math.ceil(seconds / 60)} min`
}

const labels: Record<string, string> = {
  queued: 'En attente',
  planning: 'Accepté · préparation',
  running: 'Calcul et tests en cours',
  stopping: 'Arrêt en cours',
  completed: 'Terminé',
  failed: 'Erreur · preuves conservées',
  interrupted: 'Interrompu · travail à vérifier',
  blocked: 'À résoudre',
  stopped: 'Arrêté',
  cancelled: 'Arrêté par l’utilisateur',
}

const MODULE_ACCENTS: Record<string, string> = {
  conversation: '#8B5CF6',
  image: '#F472B6',
  code: '#22D3EE',
  video: '#F59E0B',
  drawing: '#A3E635',
  '3d': '#60A5FA',
  learning: '#10B981',
  cyber: '#F43F5E',
  business: '#38BDF8',
}

function statusTone(status: string): { bg: string; border: string; text: string; dot: string } {
  if (status === 'running' || status === 'planning') {
    return {
      bg: 'rgba(56, 189, 248, 0.14)',
      border: 'rgba(56, 189, 248, 0.45)',
      text: '#BAE6FD',
      dot: '#38BDF8',
    }
  }
  if (status === 'queued') {
    return {
      bg: 'rgba(245, 158, 11, 0.14)',
      border: 'rgba(245, 158, 11, 0.45)',
      text: '#FDE68A',
      dot: '#F59E0B',
    }
  }
  if (status === 'completed') {
    return {
      bg: 'rgba(16, 185, 129, 0.14)',
      border: 'rgba(52, 211, 153, 0.45)',
      text: '#A7F3D0',
      dot: '#10B981',
    }
  }
  if (status === 'failed' || status === 'blocked') {
    return {
      bg: 'rgba(244, 63, 94, 0.15)',
      border: 'rgba(244, 63, 94, 0.45)',
      text: '#FECDD3',
      dot: '#F43F5E',
    }
  }
  return {
    bg: 'rgba(148, 163, 184, 0.12)',
    border: 'rgba(148, 163, 184, 0.3)',
    text: '#CBD5E1',
    dot: '#94A3B8',
  }
}

export default function ProjectsPanel() {
  const panel = useRef<HTMLElement | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const [open, setOpen] = useState(false)
  const [projects, setProjects] = useState<Project[]>([])
  const [error, setError] = useState('')
  const [workspaceError, setWorkspaceError] = useState('')
  const [connected, setConnected] = useState(true)
  const generationJobs = useAppStore((s) => s.generationJobs)
  const runtimeTask = useAppStore((s) => s.runtimeTask)

  useEffect(() => {
    const show = () => setOpen(true)
    window.addEventListener('aurora:projects', show)
    let busy = false
    let alive = true
    const poll = async () => {
      if (busy || document.hidden) return
      busy = true
      try {
        const key = readBridgeKey()
        const s = await fetch(getBridgeUrl() + '/api/devices/session', {
          headers: key ? { Authorization: `Bearer ${key}` } : {},
        })
        const sessionInfo = await s.json()
        if (alive) setConnected(Boolean(sessionInfo.connected))
        if (!sessionInfo.connected) return
        const check = await bridgeFetch(getBridgeUrl() + '/api/projects/reconcile', { method: 'POST' })
        if (!check.ok) throw Error('La vérification de la file est momentanément indisponible.')
        const r = await bridgeFetch(getBridgeUrl() + '/api/projects')
        if (!r.ok) throw Error('Le PC est momentanément injoignable.')
        const d = await r.json()
        if (alive) {
          setProjects(d.projects || [])
          setError('')
        }
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : 'Connexion interrompue.')
      } finally {
        busy = false
      }
    }
    void poll()
    const timer = setInterval(() => void poll(), 3000)
    return () => {
      alive = false
      clearInterval(timer)
      window.removeEventListener('aurora:projects', show)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    panel.current?.querySelector<HTMLButtonElement>('button')?.focus()
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        setOpen(false)
      } else if (event.key === 'Tab') {
        const buttons = Array.from(
          panel.current?.querySelectorAll<HTMLButtonElement>('button,a[href]') || [],
        ).filter((el) => !el.disabled)
        const first = buttons[0]
        const last = buttons[buttons.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last?.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first?.focus()
        }
      }
    }
    window.addEventListener('keydown', close, true)
    return () => {
      window.removeEventListener('keydown', close, true)
      previous?.focus()
    }
  }, [open])

  useEffect(() => {
    const warn = (event: Event) => {
      setWorkspaceError((event as CustomEvent).detail)
      setOpen(true)
    }
    window.addEventListener('aurora:workspace-error', warn)
    return () => window.removeEventListener('aurora:workspace-error', warn)
  }, [])

  const mergedProjects = useMemo(() => {
    const now = Date.now()
    const byId = new Map<string, Project>()
    for (const p of projects) {
      byId.set(p.id, p)
    }
    for (const job of generationJobs) {
      const isJobActive = job.status === 'running' || job.status === 'queued'
      const elapsedSec = Math.max(1, Math.floor(((job.finishedAt ?? now) - (job.startedAt ?? now)) / 1000))
      const existing = Array.from(byId.values()).find(
        (p) =>
          p.id === job.id ||
          (p.module === job.module && ['running', 'queued', 'planning'].includes(p.status) && isJobActive),
      )
      if (existing) {
        byId.set(existing.id, {
          ...existing,
          liveDetail: job.detail,
          liveProgress: job.progress,
          steps: Math.max(existing.steps || 0, job.progress > 0 ? Math.ceil(job.progress / 20) : 1),
        })
      } else {
        byId.set(job.id, {
          id: job.id,
          module: job.module,
          title: job.title,
          status:
            job.status === 'cancelled'
              ? 'stopped'
              : job.status === 'done'
                ? 'completed'
                : job.status === 'error'
                  ? 'failed'
                  : job.status,
          steps: job.progress > 0 ? Math.max(1, Math.ceil(job.progress / 20)) : 1,
          verified_count: job.status === 'done' ? 5 : Math.floor((job.progress || 0) / 20),
          criteria_count: 5,
          result: job.error || job.detail,
          liveDetail: job.detail,
          liveProgress: job.progress,
          isFrontendLive: true,
          scheduling: {
            queue_position: 1,
            ahead_count: 0,
            elapsed_seconds: elapsedSec,
            estimated_duration_seconds: 45,
            remaining_seconds: isJobActive
              ? Math.max(4, Math.round(45 * (1 - Math.min(0.95, (job.progress || 10) / 100))))
              : 0,
            wait_seconds: 0,
            estimate_sample_count: 1,
          },
        })
      }
    }
    if (runtimeTask.active && runtimeTask.module) {
      const hasActiveForMod = Array.from(byId.values()).some(
        (p) => p.module === runtimeTask.module && ['running', 'queued', 'planning'].includes(p.status),
      )
      if (!hasActiveForMod) {
        const elapsedSec = runtimeTask.startedAt ? Math.max(1, Math.floor((now - runtimeTask.startedAt) / 1000)) : 1
        byId.set(`live-${runtimeTask.module}`, {
          id: `live-${runtimeTask.module}`,
          module: runtimeTask.module,
          title: runtimeTask.title || `Mission ${runtimeTask.module.toUpperCase()} en cours`,
          status: 'running',
          steps: Math.max(1, runtimeTask.history?.length || 1),
          verified_count: Math.min(5, Math.floor((runtimeTask.progress || 10) / 20)),
          criteria_count: 5,
          liveDetail: runtimeTask.detail,
          liveProgress: runtimeTask.progress,
          isFrontendLive: true,
          scheduling: {
            queue_position: 1,
            ahead_count: 0,
            elapsed_seconds: elapsedSec,
            estimated_duration_seconds: 45,
            remaining_seconds: Math.max(5, 45 - elapsedSec),
            wait_seconds: 0,
            estimate_sample_count: 1,
          },
        })
      }
    }
    return Array.from(byId.values())
  }, [projects, generationJobs, runtimeTask])

  const active = mergedProjects.filter((p) => ['queued', 'planning', 'running', 'stopping'].includes(p.status))
  const historyList = mergedProjects.filter((p) => !active.includes(p))

  async function connectDevice() {
    try {
      setError('')
      const r = await bridgeFetch(getBridgeUrl() + '/api/projects')
      if (!r.ok) throw Error('Le PC est momentanément injoignable.')
      const d = await r.json()
      setProjects(d.projects || [])
      setConnected(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Connexion annulée.')
    }
  }

  async function cancel(project: Project) {
    if (project.module) {
      window.dispatchEvent(new CustomEvent('aurora-fx-stop', { detail: { module: project.module } }))
    }
    if (project.isFrontendLive) {
      useAppStore.getState().setGenerationJob(project.id, {
        status: 'cancelled',
        phase: 'done',
        progress: 100,
        finishedAt: Date.now(),
        detail: 'Arrêté depuis Projets et file d’attente.',
      })
      if (useAppStore.getState().runtimeTask.module === project.module) {
        useAppStore.getState().resetRuntimeTask()
      }
      return
    }
    try {
      const r = await bridgeFetch(getBridgeUrl() + '/api/projects/' + project.id + '/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(project.status === 'queued' ? {} : { force: true }),
      })
      const d = await r.json()
      if (!r.ok && r.status !== 409) throw Error(d.error)
      setProjects((p) => p.map((x) => (x.id === project.id ? { ...x, status: 'stopped' } : x)))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Arrêt demandé au module.')
    }
  }

  async function deleteProject(project: Project) {
    if (project.isFrontendLive) {
      useAppStore.getState().setGenerationJob(project.id, { status: 'cancelled' })
      useAppStore.getState().pruneGenerationJobs()
      return
    }
    try {
      const r = await bridgeFetch(getBridgeUrl() + '/api/projects/' + project.id, { method: 'DELETE' })
      if (!r.ok) throw Error('Suppression refusée.')
      setProjects((p) => p.filter((x) => x.id !== project.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Suppression refusée.')
    }
  }

  async function resume(project: Project) {
    try {
      const r = await bridgeFetch(getBridgeUrl() + '/api/projects/' + project.id + '/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      })
      const d = await r.json()
      if (!r.ok) throw Error(d.error)
      setProjects((p) => p.map((x) => (x.id === project.id ? { ...x, status: d.status, resumable: false } : x)))
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reprise refusée.')
    }
  }

  function view(project: Project) {
    if (
      project.module &&
      !project.design_id &&
      ['conversation', 'image', 'code', 'video', 'drawing', '3d', 'learning', 'cyber', 'business'].includes(
        project.module,
      )
    ) {
      useAppStore
        .getState()
        .setActiveModule(project.module as Parameters<ReturnType<typeof useAppStore.getState>['setActiveModule']>[0])
      window.dispatchEvent(new CustomEvent('aurora:navigate', { detail: { module: project.module, workspace: 'model' } }))
    }
    if (project.design_id) {
      try {
        localStorage.setItem('aurora.engineering-objective.v1.selected', project.design_id)
        localStorage.setItem('aurora.3d.workspace', 'assembly')
      } catch {
        // ignore storage quota
      }
      useAppStore.getState().setActiveModule('3d')
      window.dispatchEvent(new CustomEvent('aurora:navigate', { detail: { module: '3d', workspace: 'assembly' } }))
    }
    setOpen(false)
  }

  const displayedList = showHistory ? historyList : active

  return (
    <>
      <style>{`
        @keyframes aurora-job-spin { to { transform: rotate(360deg) } }
        .aurora-job-spinner { display: inline-block; animation: aurora-job-spin 1.2s linear infinite; }
        @media (prefers-reduced-motion: reduce) { .aurora-job-spinner { animation: none; } }
        @media (max-width: 900px) { .aurora-projects-label { display: none; } }
      `}</style>

      <button
        type="button"
        aria-label="Projets et file d’attente"
        onClick={() => setOpen(true)}
        style={{
          minHeight: 34,
          padding: '5px 11px',
          borderRadius: 10,
          border: active.length > 0 ? '1px solid rgba(56, 189, 248, 0.55)' : '1px solid rgba(139, 92, 246, 0.35)',
          background:
            active.length > 0
              ? 'linear-gradient(135deg, rgba(14, 165, 233, 0.22), rgba(139, 92, 246, 0.22))'
              : 'rgba(139, 92, 246, 0.14)',
          color: '#E2E8F0',
          fontSize: 11.5,
          fontWeight: 700,
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          whiteSpace: 'nowrap',
          cursor: 'pointer',
          transition: 'all .18s ease',
        }}
      >
        <span
          aria-hidden="true"
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: active.length > 0 ? '#38BDF8' : '#A78BFA',
            boxShadow: active.length > 0 ? '0 0 8px #38BDF8' : 'none',
          }}
        />
        <span className="aurora-projects-label">Projets</span>
        {active.length > 0 ? (
          <span
            style={{
              padding: '1px 6px',
              borderRadius: 999,
              background: 'rgba(56, 189, 248, 0.25)',
              color: '#BAE6FD',
              fontFamily: "'Cascadia Code',Consolas,monospace",
              fontSize: 10,
            }}
          >
            {active.length} actif{active.length > 1 ? 's' : ''}
          </span>
        ) : (
          <span
            style={{
              padding: '1px 6px',
              borderRadius: 999,
              background: 'rgba(255,255,255,0.07)',
              color: '#94A3B8',
              fontFamily: "'Cascadia Code',Consolas,monospace",
              fontSize: 9.5,
            }}
          >
            {mergedProjects.length}
          </span>
        )}
      </button>

      {open &&
        createPortal(
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Projets sur le PC"
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 100010,
              background: 'rgba(3, 6, 14, 0.82)',
              backdropFilter: 'blur(14px)',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              padding: 16,
            }}
            onClick={() => setOpen(false)}
          >
            <section
              ref={panel}
              style={{
                background: 'linear-gradient(165deg, #0E1528 0%, #080C18 100%)',
                border: '1px solid rgba(139, 92, 246, 0.42)',
                borderRadius: 22,
                padding: 22,
                width: 'min(760px, 100%)',
                maxHeight: '86dvh',
                display: 'flex',
                flexDirection: 'column',
                gap: 14,
                overflow: 'hidden',
                color: '#E6EAF5',
                boxShadow: '0 28px 90px rgba(0, 0, 0, 0.8), 0 0 50px rgba(139, 92, 246, 0.15)',
                fontFamily: "'Inter','Segoe UI Variable',system-ui,sans-serif",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  gap: 12,
                  paddingBottom: 12,
                  borderBottom: '1px solid rgba(255,255,255,0.08)',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: 999,
                        background: 'rgba(139, 92, 246, 0.2)',
                        border: '1px solid rgba(167, 139, 250, 0.4)',
                        color: '#DDD6FE',
                        fontFamily: "'Cascadia Code',Consolas,monospace",
                        fontSize: 10,
                        fontWeight: 700,
                      }}
                    >
                      ORCHESTRATEUR DE MISSIONS
                    </span>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: 999,
                        background: connected ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                        color: connected ? '#6EE7B7' : '#FDE68A',
                        fontFamily: "'Cascadia Code',Consolas,monospace",
                        fontSize: 10,
                        fontWeight: 700,
                      }}
                    >
                      {connected ? '● Bridge :3001 Connecté' : '○ Appareil non appairé'}
                    </span>
                  </div>
                  <h2 style={{ margin: '6px 0 2px', fontSize: 18, fontWeight: 800, color: '#F8FAFC' }}>
                    Projets sur le PC ({active.length} actif{active.length > 1 ? 's' : ''})
                  </h2>
                  <p style={{ margin: 0, fontSize: 12, color: '#94A3B8' }}>
                    Suivi temps réel des générations locales, contrôle d’arrêt atomique et reprise sur incident.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Fermer les projets"
                  style={{
                    minHeight: 36,
                    padding: '6px 13px',
                    borderRadius: 10,
                    border: '1px solid rgba(255,255,255,0.14)',
                    background: 'rgba(255,255,255,0.05)',
                    color: '#E2E8F0',
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  ✕ Fermer
                </button>
              </div>

              {!connected && (
                <button
                  type="button"
                  onClick={() => void connectDevice()}
                  style={{
                    minHeight: 42,
                    padding: '8px 14px',
                    borderRadius: 12,
                    border: '1px solid rgba(245, 158, 11, 0.5)',
                    background: 'rgba(245, 158, 11, 0.15)',
                    color: '#FDE68A',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Connecter cet appareil au PC (Tunnel / Mobile)
                </button>
              )}

              {workspaceError && (
                <p
                  role="alert"
                  style={{
                    margin: 0,
                    padding: '9px 12px',
                    borderRadius: 10,
                    background: 'rgba(244, 63, 94, 0.15)',
                    border: '1px solid rgba(244, 63, 94, 0.4)',
                    color: '#FECDD3',
                    fontSize: 12,
                  }}
                >
                  {workspaceError}
                </p>
              )}
              {error && (
                <p
                  role="alert"
                  style={{
                    margin: 0,
                    padding: '9px 12px',
                    borderRadius: 10,
                    background: 'rgba(244, 63, 94, 0.15)',
                    border: '1px solid rgba(244, 63, 94, 0.4)',
                    color: '#FECDD3',
                    fontSize: 12,
                  }}
                >
                  {error}
                </p>
              )}

              {/* Segmented Filter Bar */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                <div
                  style={{
                    display: 'inline-flex',
                    padding: 3,
                    borderRadius: 11,
                    background: 'rgba(2, 6, 23, 0.65)',
                    border: '1px solid rgba(255,255,255,0.08)',
                  }}
                >
                  <button
                    type="button"
                    onClick={() => setShowHistory(false)}
                    style={{
                      padding: '6px 13px',
                      borderRadius: 8,
                      border: 'none',
                      background: !showHistory ? 'rgba(139, 92, 246, 0.3)' : 'transparent',
                      color: !showHistory ? '#F8FAFC' : '#94A3B8',
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    En cours & File ({active.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowHistory(true)}
                    style={{
                      padding: '6px 13px',
                      borderRadius: 8,
                      border: 'none',
                      background: showHistory ? 'rgba(139, 92, 246, 0.3)' : 'transparent',
                      color: showHistory ? '#F8FAFC' : '#94A3B8',
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    Voir l’historique ({historyList.length})
                  </button>
                </div>
              </div>

              {/* Project List */}
              <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, paddingRight: 4 }}>
                {!displayedList.length && (
                  <div
                    style={{
                      padding: '32px 20px',
                      borderRadius: 16,
                      background: 'rgba(15, 23, 42, 0.45)',
                      border: '1px dashed rgba(255,255,255,0.1)',
                      textAlign: 'center',
                      color: '#94A3B8',
                      fontSize: 13,
                    }}
                  >
                    {showHistory
                      ? 'Aucune mission terminée dans l’historique.'
                      : 'Aucun projet actif ni en attente. Lancez une génération depuis n’importe quel module.'}
                  </div>
                )}

                {displayedList.map((p) => {
                  const tone = statusTone(p.status)
                  const modAccent = (p.module && MODULE_ACCENTS[p.module]) || '#8B5CF6'
                  const pct =
                    typeof p.liveProgress === 'number' && p.liveProgress > 0
                      ? Math.min(100, Math.round(p.liveProgress))
                      : p.criteria_count > 0
                        ? Math.min(100, Math.round((p.verified_count / p.criteria_count) * 100))
                        : p.status === 'completed'
                          ? 100
                          : 0

                  return (
                    <article
                      key={p.id}
                      style={{
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: 16,
                        padding: 16,
                        background: 'rgba(15, 23, 42, 0.68)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 10,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          {p.module && (
                            <span
                              style={{
                                fontSize: 10,
                                fontWeight: 800,
                                padding: '2px 8px',
                                borderRadius: 999,
                                background: `${modAccent}22`,
                                border: `1px solid ${modAccent}55`,
                                color: modAccent,
                                textTransform: 'uppercase',
                                fontFamily: "'Cascadia Code',Consolas,monospace",
                              }}
                            >
                              {p.module}
                            </span>
                          )}
                          <strong style={{ fontSize: 14, color: '#F8FAFC' }}>{p.title}</strong>
                        </div>

                        <span
                          role="status"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            padding: '3px 9px',
                            borderRadius: 999,
                            background: tone.bg,
                            border: `1px solid ${tone.border}`,
                            color: tone.text,
                            fontSize: 11,
                            fontWeight: 700,
                          }}
                        >
                          {['running', 'planning'].includes(p.status) ? (
                            <span className="aurora-job-spinner" aria-label="Travail en cours">
                              ◌
                            </span>
                          ) : (
                            <span style={{ width: 6, height: 6, borderRadius: '50%', background: tone.dot }} />
                          )}
                          <span>
                            {labels[p.status] || p.status}
                            {pct > 0 && ['running', 'planning'].includes(p.status) ? ` · ${pct}%` : ''}
                            {p.status === 'queued' ? ` · position ${p.scheduling.queue_position}` : ''}
                          </span>
                        </span>
                      </div>

                      {/* Progress bar when active or completed */}
                      {(pct > 0 || ['running', 'planning'].includes(p.status)) && (
                        <div
                          style={{
                            height: 6,
                            borderRadius: 999,
                            background: 'rgba(255,255,255,0.07)',
                            overflow: 'hidden',
                          }}
                        >
                          <div
                            style={{
                              width: `${Math.max(6, pct)}%`,
                              height: '100%',
                              borderRadius: 999,
                              background: `linear-gradient(90deg, ${modAccent}, #38BDF8)`,
                              transition: 'width .35s ease',
                            }}
                          />
                        </div>
                      )}

                      {p.liveDetail && (
                        <p
                          style={{
                            color: '#F472B6',
                            fontFamily: "'Cascadia Code',Consolas,monospace",
                            fontSize: 11.5,
                            margin: 0,
                            padding: '6px 10px',
                            borderRadius: 8,
                            background: 'rgba(2, 6, 23, 0.55)',
                          }}
                        >
                          ▸ {p.liveDetail}
                        </p>
                      )}

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, fontSize: 11.5, color: '#94A3B8' }}>
                        {p.status === 'queued' && (
                          <span>
                            Attente : {duration(p.scheduling.wait_seconds)} · durée estimée :{' '}
                            {duration(p.scheduling.estimated_duration_seconds)}
                          </span>
                        )}
                        {p.status === 'running' && (
                          <span>
                            Écoulé : {duration(p.scheduling.elapsed_seconds)} · restant :{' '}
                            {duration(p.scheduling.remaining_seconds)}
                          </span>
                        )}
                        {p.criteria_count > 0 && (
                          <span>
                            {p.verified_count} / {p.criteria_count} étapes vérifiées · {p.steps} phase(s) exécutée(s)
                          </span>
                        )}
                      </div>

                      {p.result && ['failed', 'blocked', 'interrupted'].includes(p.status) && (
                        <pre
                          style={{
                            margin: 0,
                            padding: 10,
                            borderRadius: 10,
                            background: 'rgba(2, 6, 23, 0.7)',
                            border: '1px solid rgba(244, 63, 94, 0.25)',
                            color: '#FECDD3',
                            fontSize: 11,
                            whiteSpace: 'pre-wrap',
                            fontFamily: "'Cascadia Code',Consolas,monospace",
                            maxHeight: 140,
                            overflowY: 'auto',
                          }}
                        >
                          {p.result.slice(0, 1500)}
                        </pre>
                      )}

                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginTop: 2 }}>
                        {['queued', 'running', 'planning'].includes(p.status) && (
                          <button
                            type="button"
                            onClick={() => void cancel(p)}
                            style={{
                              minHeight: 36,
                              padding: '6px 12px',
                              borderRadius: 10,
                              border: '1px solid rgba(248, 113, 113, 0.5)',
                              background: 'rgba(127, 29, 29, 0.35)',
                              color: '#FECACA',
                              fontSize: 11.5,
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
                          >
                            ■ Arrêter la mission
                          </button>
                        )}
                        {p.resumable && (
                          <button
                            type="button"
                            onClick={() => void resume(p)}
                            style={{
                              minHeight: 36,
                              padding: '6px 12px',
                              borderRadius: 10,
                              border: '1px solid rgba(52, 211, 153, 0.45)',
                              background: 'rgba(16, 185, 129, 0.16)',
                              color: '#A7F3D0',
                              fontSize: 11.5,
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
                          >
                            ↻ Reprendre ce projet et ses preuves
                          </button>
                        )}
                        {(p.design_id || p.module) && (
                          <button
                            type="button"
                            onClick={() => view(p)}
                            style={{
                              minHeight: 36,
                              padding: '6px 12px',
                              borderRadius: 10,
                              border: '1px solid rgba(196, 181, 253, 0.35)',
                              background: 'rgba(139, 92, 246, 0.16)',
                              color: '#DDD6FE',
                              fontSize: 11.5,
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
                          >
                            ↗ Ouvrir ce module
                          </button>
                        )}
                        {p.viewer_url && (
                          <a
                            href={getBridgeUrl() + p.viewer_url}
                            target="_blank"
                            rel="noopener"
                            style={{
                              minHeight: 36,
                              padding: '6px 12px',
                              borderRadius: 10,
                              border: '1px solid rgba(96, 165, 250, 0.4)',
                              background: 'rgba(37, 99, 235, 0.18)',
                              color: '#BFDBFE',
                              fontSize: 11.5,
                              fontWeight: 700,
                              textDecoration: 'none',
                              display: 'inline-flex',
                              alignItems: 'center',
                            }}
                          >
                            🌐 Voir le résultat 3D à 360°
                          </a>
                        )}
                        {p.assemblies?.map((a) => (
                          <a
                            key={a.url}
                            href={getBridgeUrl() + a.url}
                            target="_blank"
                            rel="noopener"
                            style={{
                              minHeight: 36,
                              padding: '6px 12px',
                              borderRadius: 10,
                              border: '1px solid rgba(56, 189, 248, 0.4)',
                              background: 'rgba(14, 165, 233, 0.16)',
                              color: '#BAE6FD',
                              fontSize: 11.5,
                              fontWeight: 700,
                              textDecoration: 'none',
                              display: 'inline-flex',
                              alignItems: 'center',
                            }}
                          >
                            🔩 Assemblage, éclaté et plaques · {a.name}
                          </a>
                        ))}
                        {['completed', 'failed', 'stopped', 'interrupted', 'blocked'].includes(p.status) && (
                          <button
                            type="button"
                            onClick={() => void deleteProject(p)}
                            style={{
                              minHeight: 36,
                              padding: '6px 11px',
                              borderRadius: 10,
                              border: '1px solid rgba(255,255,255,0.12)',
                              background: 'rgba(255,255,255,0.04)',
                              color: '#94A3B8',
                              fontSize: 11.5,
                              fontWeight: 600,
                              cursor: 'pointer',
                              marginLeft: 'auto',
                            }}
                          >
                            🗑 Supprimer
                          </button>
                        )}
                      </div>
                    </article>
                  )
                })}
              </div>
            </section>
          </div>,
          document.body,
        )}
    </>
  )
}
