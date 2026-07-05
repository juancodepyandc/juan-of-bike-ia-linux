import type { LucideIcon } from 'lucide-react'
import { Gauge, Radar } from 'lucide-react'
import type { StudioDiagnostics, StudioRequirementTone } from '../hooks/useStudioDiagnostics'

type StudioStat = {
  label: string
  value: string
  tone?: StudioRequirementTone
}

type StudioHeroProps = {
  icon: LucideIcon
  eyebrow: string
  title: string
  description: string
  diagnostics: StudioDiagnostics
  stats: StudioStat[]
}

// =============================================================================
// StudioHero — MANGA compact banner variant.
// Replaces the dark "active module" hero with a minimal Fairy Tail header that
// uses the manga palette (paper + ink border + offset shadow + Bangers title).
// Shared by: Image, Video, Code, Drawing, 3D, Cyber, Voice modules.
// =============================================================================

function toneDot(tone: StudioRequirementTone = 'default') {
  if (tone === 'good') return 'var(--ft-ok)'
  if (tone === 'warn') return 'var(--ft-warn)'
  return 'var(--ft-muted)'
}

export function StudioHero({
  icon: Icon,
  eyebrow,
  title,
  description,
  diagnostics,
  stats,
}: StudioHeroProps) {
  const ready = Math.round(diagnostics.readiness)
  const isReady = ready >= 80

  return (
    <div className="manga-hero">
      <div className="manga-hero-top">
        <div className="manga-hero-badge" aria-hidden="true">
          <Icon size={18} strokeWidth={2.4} />
        </div>
        <div className="manga-hero-ident">
          <div className="manga-hero-eyebrow">{eyebrow}</div>
          <h1 className="manga-hero-title">{title}</h1>
        </div>
        <div className={`manga-hero-ready ${isReady ? 'is-ok' : ''}`} title={diagnostics.summary}>
          <Radar size={12} strokeWidth={2.4} />
          <span>{ready}%</span>
        </div>
      </div>

      {description && (
        <p className="manga-hero-desc">{description}</p>
      )}

      {stats.length > 0 && (
        <div className="manga-hero-stats">
          {stats.map((stat) => (
            <div key={`${stat.label}-${stat.value}`} className="manga-hero-stat">
              <span className="manga-hero-stat-dot" style={{ background: toneDot(stat.tone) }} />
              <span className="manga-hero-stat-label">{stat.label}</span>
              <span className="manga-hero-stat-value">{stat.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function StudioDiagnosticsPanel({
  diagnostics,
  title = 'Preflight',
}: {
  diagnostics: StudioDiagnostics
  title?: string
}) {
  return (
    <div className="manga-diag">
      <div className="manga-diag-head">
        <Gauge size={13} strokeWidth={2.4} />
        <span className="manga-diag-title">{title}</span>
        <span className="manga-diag-ready">{Math.round(diagnostics.readiness)}%</span>
      </div>

      <p className="manga-diag-summary">{diagnostics.summary}</p>

      <div className="manga-diag-list">
        {diagnostics.requirements.map((item) => (
          <div key={item.id} className={`manga-diag-row tone-${item.tone}`}>
            <span className="manga-diag-dot" style={{ background: toneDot(item.tone) }} />
            <div className="manga-diag-row-body">
              <p className="manga-diag-row-label">{item.label}</p>
              <p className="manga-diag-row-detail">{item.detail}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
