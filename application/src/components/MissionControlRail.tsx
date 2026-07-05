import { type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { Bot, Cpu, Gauge, Sparkles, TimerReset, Waypoints } from 'lucide-react'
import { selectCodeModelForHardware } from '../config/models'
import { useAppStore } from '../stores/appStore'

const PHASE_LABELS = {
  idle: 'En attente',
  prepare: 'Preparation',
  generate: 'Generation',
  cleanup: 'Liberation',
  done: 'Termine',
  error: 'Erreur',
} as const

const MODULE_LABELS = {
  conversation: 'Copilote',
  image: 'Image',
  code: 'Code',
  video: 'Video',
  drawing: 'Dessin',
  '3d': '3D',
  learning: 'Academie',
} as const

function RailCard({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div className="cut-panel-soft border border-white/10 bg-white/[0.04] px-4 py-4">
      <p className="mono-kicker text-[9px] text-aurora-text-dim">{title}</p>
      <div className="mt-3">{children}</div>
    </div>
  )
}

function Meter({
  value,
}: {
  value: number
}) {
  return (
    <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/[0.08]">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${value}%` }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="h-full rounded-full bg-[linear-gradient(90deg,#74e8ff,#ff6b3d)]"
      />
    </div>
  )
}

function ProgressRing({
  value,
  tone,
}: {
  value: number
  tone: 'queued' | 'running' | 'done' | 'error' | 'cancelled'
}) {
  const color =
    tone === 'done'
      ? '#4dd5a4'
      : tone === 'error'
        ? '#ef4444'
        : tone === 'cancelled'
          ? '#9ca3af'
          : tone === 'queued'
            ? '#f59e0b'
            : '#74e8ff'

  return (
    <div
      className="relative h-10 w-10 rounded-full"
      style={{
        background: `conic-gradient(${color} ${Math.max(0, Math.min(100, value))}%, rgba(255,255,255,0.08) 0%)`,
      }}
    >
      <div className="absolute inset-[4px] grid place-items-center rounded-full bg-[#0b1018] text-[10px] text-aurora-text">
        {Math.round(value)}%
      </div>
    </div>
  )
}

export default function MissionControlRail() {
  const { activeModule, codeModel, generationJobs, hardware, installedModels, mainModel, runtimeServices, runtimeTask, visionModel } = useAppStore()
  const startedLabel = runtimeTask.startedAt
    ? new Date(runtimeTask.startedAt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    : 'Aucune session'
  const elapsedLabel = runtimeTask.startedAt
    ? `${Math.max(1, Math.round((Date.now() - runtimeTask.startedAt) / 1000))}s`
    : '0s'
  const recentHistory = [...runtimeTask.history].reverse().slice(0, 5)
  const trackedJobs = [...generationJobs]
    .sort((a, b) => {
      const aActive = a.status === 'running' || a.status === 'queued'
      const bActive = b.status === 'running' || b.status === 'queued'
      if (aActive !== bActive) {
        return aActive ? -1 : 1
      }

      const aTime = a.finishedAt || a.startedAt || a.createdAt
      const bTime = b.finishedAt || b.startedAt || b.createdAt
      return bTime - aTime
    })
    .slice(0, 6)
  const effectiveCodeModel = selectCodeModelForHardware(hardware, installedModels, codeModel)
  const displayedModel =
    activeModule === 'code'
      ? effectiveCodeModel
      : activeModule === 'image' || activeModule === 'drawing' || activeModule === 'video' || activeModule === '3d'
        ? visionModel
        : mainModel

  return (
    <div className="glass-strong h-full overflow-y-auto px-4 py-4 scroll-shell">
      <div className="grid gap-3">
        <RailCard title="IA locale">
          <div className="flex items-center gap-3">
            <div className="status-orb flex h-11 w-11 items-center justify-center text-white">
              <Bot size={16} />
            </div>
            <div>
              <p className="text-sm font-medium text-aurora-text">Aurora IA</p>
              <p className="text-xs text-aurora-text-dim">Tauri natif</p>
            </div>
          </div>
        </RailCard>

        <RailCard title="Execution">
          <p className="text-sm text-aurora-text">{runtimeTask.active ? runtimeTask.detail : 'Aucune charge'}</p>
          <p className="mt-2 text-[11px] text-aurora-text-dim">
            {runtimeTask.active ? `Demarre a ${startedLabel}` : `Module actif: ${activeModule}`}
          </p>
          <p className="mt-1 text-[11px] text-aurora-text-dim">
            {runtimeTask.active ? `Temps reel: ${elapsedLabel}` : `Session: ${runtimeTask.title || 'aucune'}`}
          </p>
          <Meter value={runtimeTask.progress} />
        </RailCard>

        <RailCard title="File Jobs">
          {trackedJobs.length > 0 ? (
            <div className="space-y-3">
              {trackedJobs.map((job) => (
                <div key={job.id} className="rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-3">
                  <div className="flex items-start gap-3">
                    <ProgressRing value={job.progress} tone={job.status} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="truncate text-sm text-aurora-text">{job.title}</p>
                        <span className="text-[10px] uppercase tracking-[0.18em] text-aurora-text-dim">
                          {job.status === 'queued'
                            ? 'File'
                            : job.status === 'running'
                              ? PHASE_LABELS[job.phase]
                              : job.status === 'done'
                                ? 'Termine'
                                : job.status === 'cancelled'
                                  ? 'Stop'
                                  : 'Erreur'}
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-aurora-text-dim">
                        {(MODULE_LABELS as any)[job.module] || job.module}
                        {job.model ? ` • ${job.model}` : ''}
                      </p>
                      <p className="mt-2 line-clamp-2 text-xs text-aurora-text">{job.detail}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-aurora-text-dim">
              Les generations en file d attente et en cours apparaitront ici.
            </p>
          )}
        </RailCard>

        <RailCard title="Phase">
          <div className="flex items-center gap-2 text-[11px] text-aurora-text-dim">
            <Waypoints size={12} />
            <span>{PHASE_LABELS[runtimeTask.phase]}</span>
          </div>
        </RailCard>

        <RailCard title="Machine">
          <div className="flex items-center gap-2 text-[11px] text-aurora-text-dim">
            <Cpu size={12} />
            <span>{hardware ? `${hardware.cores} coeurs / ${Math.round(hardware.ram_gb)} Go` : 'Detection'}</span>
          </div>
          <p className="mt-2 text-xs text-aurora-text-dim">{hardware?.gpu || 'GPU en attente'}</p>
        </RailCard>

        <RailCard title="Modele">
          <p className="text-sm text-aurora-text">{displayedModel}</p>
          <p className="mt-2 text-xs text-aurora-text-dim">{installedModels.length} modele(s)</p>
        </RailCard>

        <RailCard title="Services">
          <div className="space-y-3 text-sm">
            {/* Section Ollama */}
            <div className="flex items-center justify-between gap-3">
              <span className="text-aurora-text">Ollama</span>
              <span className={runtimeServices?.ollama?.running ? 'text-aurora-green' : runtimeServices?.ollama?.available ? 'text-aurora-orange' : 'text-aurora-red'}>
                {runtimeServices?.ollama?.running ? 'actif' : runtimeServices?.ollama?.available ? 'pret' : 'absent'}
              </span>
            </div>
            <p className="text-[11px] leading-relaxed text-aurora-text-dim">
              {runtimeServices?.ollama?.detail || "Service non détecté en mode Web"}
            </p>
            <Meter value={runtimeServices?.ollama?.progress || 0} />

            {/* Section ComfyUI */}
            <div className="flex items-center justify-between gap-3">
              <span className="text-aurora-text">ComfyUI</span>
              <span className={runtimeServices?.comfyui?.running ? 'text-aurora-green' : runtimeServices?.comfyui?.available ? 'text-aurora-orange' : 'text-aurora-red'}>
                {runtimeServices?.comfyui?.running ? 'actif' : runtimeServices?.comfyui?.available ? 'pret' : 'absent'}
              </span>
            </div>
            <p className="text-[11px] leading-relaxed text-aurora-text-dim">
              {runtimeServices?.comfyui?.detail || "Service non détecté en mode Web"}
            </p>
            <Meter value={runtimeServices?.comfyui?.progress || 0} />
          </div>
        </RailCard>

        <RailCard title="Historique">
          {recentHistory.length > 0 ? (
            <div className="space-y-3">
              {recentHistory.map((entry) => (
                <div key={entry.id} className="border-l border-white/10 pl-3">
                  <div className="flex items-center justify-between gap-3 text-[10px] text-aurora-text-dim">
                    <span>{PHASE_LABELS[entry.phase]}</span>
                    <span>
                      {new Date(entry.timestamp).toLocaleTimeString('fr-FR', {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-aurora-text">{entry.detail}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-aurora-text-dim">Les etapes runtime s afficheront ici pendant une vraie execution.</p>
          )}
        </RailCard>

        <RailCard title="Sortie">
          <div className="flex items-center gap-2 text-[11px] text-aurora-text-dim">
            <TimerReset size={12} />
            <span>Ressources liberees apres job</span>
          </div>
        </RailCard>

        <RailCard title="Principe">
          <div className="flex items-center gap-2 text-[11px] text-aurora-text-dim">
            <Gauge size={12} />
            <span>Comprendre puis produire</span>
          </div>
        </RailCard>

        <RailCard title="Fidelite">
          <div className="flex items-center gap-2 text-[11px] text-aurora-text-dim">
            <Sparkles size={12} />
            <span>Progression alignee sur le runtime reel</span>
          </div>
        </RailCard>
      </div>
    </div>
  )
}
