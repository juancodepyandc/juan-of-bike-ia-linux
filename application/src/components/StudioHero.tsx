import type { LucideIcon } from 'lucide-react'
import { Gauge, Radar, ShieldCheck } from 'lucide-react'
import type { StudioDiagnostics, StudioRequirementTone } from '../hooks/useStudioDiagnostics.ts'

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

function toneDot(tone: StudioRequirementTone = 'default') {
  if (tone === 'good') return '#10B981'
  if (tone === 'warn') return '#F59E0B'
  return '#64748B'
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
    <div
      className="manga-hero"
      style={{
        margin: '12px 16px 4px',
        padding: '16px 20px',
        borderRadius: 18,
        background: 'linear-gradient(160deg, rgba(15, 23, 42, 0.78), rgba(8, 12, 24, 0.88))',
        border: '1px solid rgba(255, 255, 255, 0.09)',
        boxShadow: '0 14px 40px rgba(0, 0, 0, 0.35)',
        backdropFilter: 'blur(18px)',
      }}
    >
      <div
        className="manga-hero-top"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          flexWrap: 'wrap',
        }}
      >
        <div
          className="manga-hero-badge"
          aria-hidden="true"
          style={{
            width: 42,
            height: 42,
            borderRadius: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, rgba(34, 211, 238, 0.2), rgba(139, 92, 246, 0.24))',
            border: '1px solid rgba(139, 92, 246, 0.42)',
            color: '#E2E8F0',
            flexShrink: 0,
          }}
        >
          <Icon size={19} strokeWidth={2.2} />
        </div>
        <div className="manga-hero-ident" style={{ flex: 1, minWidth: 200 }}>
          <div
            className="manga-hero-eyebrow"
            style={{
              fontFamily: "'Cascadia Code',Consolas,monospace",
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.18em',
              textTransform: 'uppercase',
              color: '#38BDF8',
            }}
          >
            {eyebrow}
          </div>
          <h1
            className="manga-hero-title"
            style={{
              margin: '3px 0 0',
              fontSize: 18,
              fontWeight: 800,
              letterSpacing: '-0.015em',
              color: '#F8FAFC',
            }}
          >
            {title}
          </h1>
        </div>
        <div
          className={`manga-hero-ready ${isReady ? 'is-ok' : ''}`}
          title={diagnostics.summary}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '5px 11px',
            borderRadius: 999,
            background: isReady ? 'rgba(16, 185, 129, 0.14)' : 'rgba(245, 158, 11, 0.14)',
            border: `1px solid ${isReady ? 'rgba(52, 211, 153, 0.4)' : 'rgba(245, 158, 11, 0.4)'}`,
            color: isReady ? '#6EE7B7' : '#FDE68A',
            fontFamily: "'Cascadia Code',Consolas,monospace",
            fontSize: 11,
            fontWeight: 700,
          }}
        >
          {isReady ? <ShieldCheck size={13} strokeWidth={2.3} /> : <Radar size={13} strokeWidth={2.3} />}
          <span> Système {ready}%</span>
        </div>
      </div>

      {description && (
        <p
          className="manga-hero-desc"
          style={{
            margin: '10px 0 0',
            fontSize: 12.5,
            color: '#94A3B8',
            lineHeight: 1.5,
          }}
        >
          {description}
        </p>
      )}

      {stats.length > 0 && (
        <div
          className="manga-hero-stats"
          style={{
            marginTop: 12,
            display: 'flex',
            flexWrap: 'wrap',
            gap: 8,
          }}
        >
          {stats.map((stat) => (
            <div
              key={`${stat.label}-${stat.value}`}
              className="manga-hero-stat"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '4px 10px',
                borderRadius: 999,
                background: 'rgba(2, 6, 23, 0.55)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                fontSize: 11,
              }}
            >
              <span
                className="manga-hero-stat-dot"
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: toneDot(stat.tone),
                  boxShadow: `0 0 6px ${toneDot(stat.tone)}`,
                }}
              />
              <span className="manga-hero-stat-label" style={{ color: '#94A3B8', fontWeight: 600 }}>
                {stat.label}:
              </span>
              <span
                className="manga-hero-stat-value"
                style={{
                  color: '#F1F5F9',
                  fontFamily: "'Cascadia Code',Consolas,monospace",
                  fontWeight: 700,
                }}
              >
                {stat.value}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function StudioDiagnosticsPanel({
  diagnostics,
  title = 'Contrôle Préflight & Télémétrie',
}: {
  diagnostics: StudioDiagnostics
  title?: string
}) {
  return (
    <div
      className="manga-diag"
      style={{
        padding: 14,
        borderRadius: 15,
        background: 'rgba(15, 23, 42, 0.65)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
      }}
    >
      <div
        className="manga-diag-head"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 8,
        }}
      >
        <Gauge size={14} strokeWidth={2.2} style={{ color: '#38BDF8' }} />
        <span className="manga-diag-title" style={{ fontSize: 12, fontWeight: 800, color: '#F1F5F9' }}>
          {title}
        </span>
        <span
          className="manga-diag-ready"
          style={{
            marginLeft: 'auto',
            fontFamily: "'Cascadia Code',Consolas,monospace",
            fontSize: 11,
            fontWeight: 700,
            color: '#6EE7B7',
          }}
        >
          {Math.round(diagnostics.readiness)}%
        </span>
      </div>

      <p className="manga-diag-summary" style={{ margin: '0 0 10px', fontSize: 11.5, color: '#94A3B8' }}>
        {diagnostics.summary}
      </p>

      <div className="manga-diag-list" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {diagnostics.requirements.map((item) => (
          <div
            key={item.id}
            className={`manga-diag-row tone-${item.tone}`}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 8,
              padding: '6px 9px',
              borderRadius: 9,
              background: 'rgba(2, 6, 23, 0.5)',
              border: '1px solid rgba(255, 255, 255, 0.05)',
            }}
          >
            <span
              className="manga-diag-dot"
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                marginTop: 5,
                flexShrink: 0,
                background: toneDot(item.tone),
              }}
            />
            <div className="manga-diag-row-body">
              <p className="manga-diag-row-label" style={{ margin: 0, fontSize: 11.5, fontWeight: 700, color: '#E2E8F0' }}>
                {item.label}
              </p>
              <p className="manga-diag-row-detail" style={{ margin: '2px 0 0', fontSize: 10.5, color: '#94A3B8' }}>
                {item.detail}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
