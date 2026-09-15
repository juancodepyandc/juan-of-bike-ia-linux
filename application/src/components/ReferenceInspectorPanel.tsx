import { useMemo } from 'react'
import { Eye, Palette, RefreshCcw, Type } from 'lucide-react'
import type { ColorOverride, VisualReferenceAnalysis } from '../services/visualReferenceAnalyzer.ts'

export type ReferenceInspectorProps = {
  analysis: VisualReferenceAnalysis | null
  referenceImageUrl: string | null
  focusEntityIndex: number
  onFocusEntityChange: (index: number) => void
  manualOverrides: ColorOverride[]
  onManualOverridesChange: (overrides: ColorOverride[]) => void
  onReanalyze?: () => void
  isAnalyzing?: boolean
}

function hexToRgbText(hex: string): string {
  const match = hex.replace('#', '').match(/^([a-f0-9]{2})([a-f0-9]{2})([a-f0-9]{2})$/i)
  if (!match) return 'rgb'
  return `rgb(${parseInt(match[1], 16)}, ${parseInt(match[2], 16)}, ${parseInt(match[3], 16)})`
}

export default function ReferenceInspectorPanel({
  analysis,
  referenceImageUrl,
  focusEntityIndex,
  onFocusEntityChange,
  manualOverrides,
  onManualOverridesChange,
  onReanalyze,
  isAnalyzing = false,
}: ReferenceInspectorProps) {
  const entities = analysis?.entities ?? []
  const palette = analysis?.palette ?? []
  const visibleText = analysis?.visibleText ?? []
  const effectiveFocus = focusEntityIndex >= 0 && focusEntityIndex < entities.length
    ? focusEntityIndex
    : analysis?.dominantEntityIndex ?? -1

  const combinedPalette = useMemo(() => {
    const byZone = new Map<string, { hex: string; zone: string; source: 'analyzer' | 'user' }>()
    for (const entry of palette) byZone.set(entry.zone, { hex: entry.hex, zone: entry.zone, source: 'analyzer' })
    for (const override of manualOverrides) byZone.set(override.zone, { hex: override.hex, zone: override.zone, source: 'user' })
    return Array.from(byZone.values())
  }, [palette, manualOverrides])

  const updateOverride = (zone: string, hex: string) => {
    const next: ColorOverride[] = manualOverrides.filter((o) => o.zone !== zone)
    next.push({ zone, hex: hex.toLowerCase(), source: 'user' })
    onManualOverridesChange(next)
  }

  const removeOverride = (zone: string) => {
    onManualOverridesChange(manualOverrides.filter((o) => o.zone !== zone))
  }

  const addCustomZone = () => {
    const zoneName = window.prompt('Nom de la zone (ex: pales, boitier, cheveux, yeux)')
    if (!zoneName) return
    const normalized = zoneName.trim().toLowerCase()
    if (!normalized) return
    updateOverride(normalized, combinedPalette[0]?.hex ?? '#888888')
  }

  return (
    <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-4 text-sm text-aurora-text">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Inspecteur de reference</p>
          <p className="mt-2 text-xs text-aurora-text-dim">
            Verifie ce que l IA a compris de la reference avant la reconstruction 3D.
          </p>
        </div>
        {onReanalyze && (
          <button
            onClick={onReanalyze}
            disabled={isAnalyzing}
            className="inline-flex items-center gap-2 rounded-xl border border-aurora-border/35 bg-aurora-surface px-3 py-2 text-xs text-aurora-text-dim transition-colors hover:text-aurora-text disabled:opacity-40"
          >
            <RefreshCcw size={13} className={isAnalyzing ? 'animate-spin' : ''} />
            Re-analyser
          </button>
        )}
      </div>

      {referenceImageUrl && entities.length > 0 && (
        <div className="mt-4">
          <p className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">
            <Eye size={13} />
            Sujets detectes ({entities.length})
          </p>
          <div className="relative mt-2 overflow-hidden rounded-xl border border-aurora-border/35 bg-black/40">
            <img src={referenceImageUrl} alt="Reference" className="block w-full" />
            <svg
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              className="pointer-events-none absolute inset-0 h-full w-full"
              aria-hidden="true"
            >
              {entities.map((entity, index) => {
                const isFocus = index === effectiveFocus
                const color = isFocus ? '#4dd5a4' : '#ff6a3d'
                return (
                  <g key={`${entity.label}-${index}`}>
                    <rect
                      x={entity.bbox.x * 100}
                      y={entity.bbox.y * 100}
                      width={entity.bbox.w * 100}
                      height={entity.bbox.h * 100}
                      fill="none"
                      stroke={color}
                      strokeWidth={isFocus ? 1 : 0.5}
                      strokeDasharray={isFocus ? '0' : '1.5 1'}
                      vectorEffect="non-scaling-stroke"
                    />
                  </g>
                )
              })}
            </svg>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {entities.map((entity, index) => {
              const isFocus = index === effectiveFocus
              return (
                <button
                  key={`${entity.label}-${index}`}
                  onClick={() => onFocusEntityChange(index)}
                  className={`rounded-lg border px-2 py-1 text-xs transition-colors ${
                    isFocus
                      ? 'border-emerald-400/60 bg-emerald-500/15 text-emerald-200'
                      : 'border-aurora-border/35 bg-aurora-surface text-aurora-text-dim hover:text-aurora-text'
                  }`}
                >
                  {entity.label}
                  <span className="ml-1 opacity-60">{Math.round(entity.confidence * 100)}%</span>
                </button>
              )
            })}
          </div>
          {effectiveFocus >= 0 && entities[effectiveFocus]?.description && (
            <p className="mt-2 text-xs text-aurora-text-dim">
              {entities[effectiveFocus].description}
            </p>
          )}
        </div>
      )}

      <div className="mt-4">
        <p className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">
          <Palette size={13} />
          Palette ({combinedPalette.length})
        </p>
        {combinedPalette.length > 0 ? (
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {combinedPalette.map((entry) => (
              <label
                key={entry.zone}
                className="flex items-center gap-2 rounded-xl border border-aurora-border/35 bg-aurora-surface px-2 py-2"
                title={hexToRgbText(entry.hex)}
              >
                <input
                  type="color"
                  value={entry.hex}
                  onChange={(e) => updateOverride(entry.zone, e.target.value)}
                  className="h-7 w-7 cursor-pointer rounded-md border border-aurora-border/25 bg-transparent"
                />
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-xs font-medium text-aurora-text">{entry.zone}</span>
                  <span className="truncate text-[10px] text-aurora-text-dim">
                    {entry.hex}
                    {entry.source === 'user' && <span className="ml-1 text-emerald-300">override</span>}
                  </span>
                </div>
                {entry.source === 'user' && (
                  <button
                    onClick={() => removeOverride(entry.zone)}
                    className="text-[10px] text-aurora-text-dim hover:text-aurora-text"
                    title="Revenir a la couleur detectee"
                  >
                    reset
                  </button>
                )}
              </label>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-xs text-aurora-text-dim">
            Aucune couleur detectee pour l instant. Lance &laquo; Analyser &raquo; ci-dessus ou ajoute manuellement une zone ci-dessous — les valeurs choisies seront imposees a FLUX et aux vues multi-angles.
          </p>
        )}
        <button
          onClick={addCustomZone}
          className="mt-2 w-full rounded-xl border border-dashed border-aurora-border/35 bg-aurora-surface/50 px-3 py-2 text-xs text-aurora-text-dim transition-colors hover:text-aurora-text"
        >
          + Ajouter une zone (pales, boitier, iris, ecran, led...)
        </button>
      </div>

      {visibleText.length > 0 && (
        <div className="mt-4">
          <p className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">
            <Type size={13} />
            Textes a retranscrire ({visibleText.length})
          </p>
          <ul className="mt-2 space-y-1">
            {visibleText.slice(0, 8).map((entry, index) => (
              <li key={`${entry.text}-${index}`} className="rounded-lg border border-aurora-border/25 bg-aurora-surface px-2 py-1 text-xs">
                <span className="font-mono text-aurora-text">{entry.text}</span>
                <span className="ml-2 text-[10px] uppercase tracking-wide text-aurora-text-dim">{entry.family}</span>
                {entry.location && <div className="text-[10px] text-aurora-text-dim">{entry.location}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {analysis?.notes && (
        <p className="mt-3 rounded-lg border border-aurora-border/25 bg-aurora-surface/60 px-2 py-2 text-[11px] text-aurora-text-dim">
          {analysis.notes}
        </p>
      )}
    </div>
  )
}
