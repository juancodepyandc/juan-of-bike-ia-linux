import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronUp, Plug, Sparkles, Zap } from 'lucide-react'
import { getModuleRecommendations, type ModuleId } from '../services/moduleConnectorRecommendations.ts'
import { probeExtension } from '../services/auroraExtensionBridge.ts'

type Props = {
  module: ModuleId
  /** Render compact one-line tease to keep module headers light */
  compact?: boolean
  /** Optional extra class for custom positioning */
  className?: string
}

/**
 * Panel that surfaces, per module, which connectors and Aurora extension
 * capabilities would lift the result quality. Honors the user request:
 * "Tu peux recommander pour chaque module un connecteur a mettre et meme
 * non connecter il peut utiliser aurora extension si besoin pour aller
 * chercher n importe quel information possible pour avoir des meilleurs
 * resultats."
 *
 * Designed to NOT block: the module works fully without any connector;
 * this is purely informative and can be expanded/collapsed.
 */
export default function ConnectorRecommendationsPanel({ module, compact = false, className }: Props) {
  const [open, setOpen] = useState(!compact)
  const plan = useMemo(() => getModuleRecommendations(module), [module])
  const [extensionActive, setExtensionActive] = useState<boolean | null>(null)

  // Poll the bridge every 30s so the panel reflects whether Aurora-Connect
  // is currently reachable. The probe is cheap (no command dispatched) and
  // tolerates offline mode (returns null silently).
  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const info = await probeExtension()
        if (!cancelled) setExtensionActive(Boolean(info))
      } catch {
        if (!cancelled) setExtensionActive(false)
      }
    }
    void tick()
    const id = window.setInterval(tick, 30_000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [])

  if (!plan) return null

  const topConnector = plan.primary[0]
  const totalConnectors = plan.primary.length + plan.optional.length
  const totalExtensionCaps = plan.extensionFallback.length

  return (
    <div
      className={`rounded-2xl border border-aurora-border/60 bg-aurora-surface/60 backdrop-blur-md ${className ?? ''}`}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left text-xs text-aurora-text-dim hover:text-aurora-text transition-colors"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-aurora-accent" />
          <span className="font-medium">
            Connecteurs recommandes
          </span>
          {topConnector ? (
            <span className="hidden sm:inline rounded-full border border-aurora-border/60 bg-aurora-surface-2/40 px-2 py-0.5 text-[10px] uppercase tracking-wider text-aurora-text-dim">
              top: {topConnector.id}
            </span>
          ) : null}
          <span className="rounded-full border border-aurora-border/40 bg-aurora-surface-2/40 px-2 py-0.5 text-[10px] text-aurora-text-dim">
            {totalConnectors} connecteurs · {totalExtensionCaps} fallback Aurora Extension
          </span>
          {extensionActive !== null && (
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] ${
                extensionActive
                  ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
                  : 'border-aurora-border/40 bg-aurora-surface-2/40 text-aurora-text-dim'
              }`}
              title={extensionActive ? 'Extension Aurora-Connect detectee — les fallbacks sont utilisables.' : 'Extension non detectee — installe-la pour activer les fallbacks.'}
            >
              ext {extensionActive ? '●' : '○'}
            </span>
          )}
        </span>
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {open && (
        <div className="space-y-4 border-t border-aurora-border/40 px-4 py-3">
          {/* Primary recommendations */}
          <section>
            <h4 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-aurora-text">
              <Plug className="h-3 w-3" />
              Connecteurs principaux
            </h4>
            <ul className="space-y-2">
              {plan.primary.map((rec) => (
                <li key={rec.id} className="flex flex-col gap-1 rounded-xl border border-aurora-border/40 bg-aurora-surface-2/40 p-3">
                  <div className="flex items-center gap-2 text-xs">
                    <span className="rounded-md bg-aurora-accent/15 px-2 py-0.5 font-medium text-aurora-accent">
                      {rec.id}
                    </span>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase ${impactClasses(rec.impact)}`}>
                      {rec.impact}
                    </span>
                  </div>
                  <p className="text-[11px] leading-relaxed text-aurora-text-dim">{rec.reason}</p>
                  {rec.fallbackHint && (
                    <p className="rounded-md border border-amber-400/20 bg-amber-400/5 px-2 py-1 text-[10px] text-amber-200/80">
                      <span className="font-medium">Fallback:</span> {rec.fallbackHint}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </section>

          {/* Optional connectors */}
          {plan.optional.length > 0 && (
            <section>
              <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-aurora-text-dim">
                Bonus si dispo
              </h4>
              <ul className="grid gap-1.5 sm:grid-cols-2">
                {plan.optional.map((rec) => (
                  <li key={rec.id} className="flex flex-col gap-0.5 rounded-lg border border-aurora-border/30 bg-aurora-surface-2/30 px-2 py-1.5">
                    <span className="text-[11px] font-medium text-aurora-text">{rec.id}</span>
                    <span className="text-[10px] leading-snug text-aurora-text-dim">{rec.reason}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Aurora Extension fallback */}
          <section>
            <h4 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-aurora-text">
              <Zap className="h-3 w-3 text-aurora-accent" />
              Aurora Connect Extension (sans cle API)
            </h4>
            <ul className="space-y-1.5">
              {plan.extensionFallback.map((cap) => (
                <li key={cap.capability} className="rounded-lg border border-aurora-border/30 bg-aurora-surface-2/30 px-2 py-1.5">
                  <div className="text-[11px] font-medium text-aurora-text">{cap.capability}</div>
                  <div className="text-[10px] text-aurora-text-dim">{cap.description}</div>
                  <div className="mt-0.5 text-[10px] text-aurora-accent/85">
                    <span className="font-medium">Benefice:</span> {cap.benefits}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  )
}

function impactClasses(impact: 'transformative' | 'high' | 'medium') {
  switch (impact) {
    case 'transformative':
      return 'bg-emerald-400/15 text-emerald-300 border border-emerald-400/30'
    case 'high':
      return 'bg-blue-400/15 text-blue-300 border border-blue-400/30'
    case 'medium':
    default:
      return 'bg-aurora-surface-2/60 text-aurora-text-dim border border-aurora-border/40'
  }
}
