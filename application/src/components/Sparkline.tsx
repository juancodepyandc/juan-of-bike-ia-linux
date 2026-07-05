/**
 * Sparkline — mini graph SVG inline pour visualiser une série
 * temporelle (scores des runs Academy/Cyber par exemple).
 *
 * v82dk : évolution score sur les N derniers runs avec area
 * gradient + dernière valeur en évidence.
 */

interface Props {
  values: number[]
  width?: number
  height?: number
  color?: string
  /** v82ds : superpose une courbe moyenne mobile (window=7 par
   *  défaut) en plus pâle pour révéler la tendance. */
  smooth?: boolean
  smoothWindow?: number
  /** v82dz : annotations max/last à droite du sparkline. Visible
   *  seulement si width >= 100 pour ne pas chevaucher les courbes. */
  showAxis?: boolean
}

const GOLD = 'oklch(0.74 0.13 60)'

function movingAverage(values: number[], window: number): number[] {
  if (window <= 1 || values.length === 0) return values.slice()
  const out: number[] = []
  for (let i = 0; i < values.length; i++) {
    const start = Math.max(0, i - window + 1)
    const slice = values.slice(start, i + 1)
    const avg = slice.reduce((a, b) => a + b, 0) / slice.length
    out.push(avg)
  }
  return out
}

export default function Sparkline({
  values,
  width = 120,
  height = 28,
  color = GOLD,
  smooth = false,
  smoothWindow = 7,
  showAxis = false,
}: Props) {
  if (values.length === 0) {
    return null
  }
  if (values.length === 1) {
    // Un seul point → un dot centré
    return (
      <svg width={width} height={height}>
        <circle cx={width / 2} cy={height / 2} r={2.5} fill={color} />
      </svg>
    )
  }
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const range = max - min || 1
  const stepX = width / (values.length - 1)
  const points = values.map((v, i) => {
    const x = i * stepX
    const y = height - 2 - ((v - min) / range) * (height - 4)
    return [x, y] as const
  })
  const linePath = points
    .map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`)
    .join(' ')
  // Area path : line + close down to bottom
  const areaPath = `${linePath} L ${(width).toFixed(1)} ${height} L 0 ${height} Z`
  const last = points[points.length - 1]
  // v82ds : courbe lissée superposée si smooth=true et assez de points
  let smoothPath: string | null = null
  if (smooth && values.length >= 3) {
    const smoothValues = movingAverage(values, smoothWindow)
    const smoothPoints = smoothValues.map((v, i) => {
      const x = i * stepX
      const y = height - 2 - ((v - min) / range) * (height - 4)
      return [x, y] as const
    })
    smoothPath = smoothPoints
      .map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`)
      .join(' ')
  }

  return (
    <svg width={width} height={height} style={{ overflow: 'visible' }}>
      <defs>
        <linearGradient id="sparkline-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.4} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#sparkline-grad)" />
      {/* Brute curve : plus pâle si on superpose une smooth */}
      <path d={linePath} fill="none"
        stroke={color}
        strokeWidth={smoothPath ? 1.0 : 1.4}
        strokeOpacity={smoothPath ? 0.4 : 1}
        strokeLinejoin="round" strokeLinecap="round" />
      {/* Smooth curve par-dessus, plus épaisse / pleine opacité */}
      {smoothPath && (
        <path d={smoothPath} fill="none"
          stroke={color} strokeWidth={1.6}
          strokeLinejoin="round" strokeLinecap="round" />
      )}
      <circle cx={last[0]} cy={last[1]} r={2.2} fill={color} stroke="var(--bg, #0c0a09)" strokeWidth={0.8} />
      {/* v82dz : axe Y annotations max + last value, mono compact. */}
      {showAxis && width >= 100 && (
        <>
          <text
            x={width - 2} y={9}
            textAnchor="end"
            fontFamily="ui-monospace, monospace"
            fontSize={8}
            fill={color}
            opacity={0.85}>
            {Math.round(max)}
          </text>
          <text
            x={width - 2} y={height - 2}
            textAnchor="end"
            fontFamily="ui-monospace, monospace"
            fontSize={8}
            fill="currentColor"
            opacity={0.5}>
            {Math.round(min)}
          </text>
        </>
      )}
    </svg>
  )
}
