// Time-series recorder for the simulator.
// Lets the view layer build live graphs (recharts) and lets the learner
// export raw data as CSV for BAC/STI2D dossiers.
//
// Pure compute: no DOM, no Three.js. Bounded memory via ring buffer.

export type Channel = {
  /** Identifier matched against series payloads. */
  id: string
  /** Human label for the legend. */
  label: string
  /** Unit string (SI, e.g. "m", "m/s", "J", "K", "Pa"). Optional but recommended. */
  unit?: string
  /** Suggested color for the plot. */
  color?: string
}

export type SamplePoint = {
  t: number
  values: Record<string, number>
}

export type RecorderOptions = {
  /** Max number of samples kept. Older ones drop off (ring buffer). */
  maxSamples?: number
  /** Optional minimum gap between accepted samples (s). Useful at high fps. */
  minDtSeconds?: number
}

const DEFAULT_MAX_SAMPLES = 4096
const DEFAULT_MIN_DT = 0

/**
 * DataRecorder — append-only time-series storage with bounded memory.
 *
 * Usage:
 *   const rec = new DataRecorder([
 *     { id: 'theta', label: 'angle', unit: 'rad', color: '#3aa4ff' },
 *     { id: 'omega', label: 'vitesse angulaire', unit: 'rad/s' },
 *   ])
 *   rec.push(t, { theta: 0.3, omega: 1.2 })
 *   const csv = rec.toCsv()
 *   const series = rec.getSeries() // for <LineChart data={...} />
 */
export class DataRecorder {
  private channels: Channel[]
  private samples: SamplePoint[] = []
  private maxSamples: number
  private minDt: number
  private lastSampleT = -Infinity

  constructor(channels: Channel[], opts: RecorderOptions = {}) {
    if (channels.length === 0) throw new Error('DataRecorder: at least one channel required')
    const ids = new Set<string>()
    for (const ch of channels) {
      if (ids.has(ch.id)) throw new Error(`DataRecorder: duplicate channel id "${ch.id}"`)
      ids.add(ch.id)
    }
    this.channels = channels.map((c) => ({ ...c }))
    this.maxSamples = Math.max(8, opts.maxSamples ?? DEFAULT_MAX_SAMPLES)
    this.minDt = Math.max(0, opts.minDtSeconds ?? DEFAULT_MIN_DT)
  }

  /** Push a sample. Silently dropped if minDt gate not satisfied. */
  push(t: number, values: Record<string, number>): boolean {
    if (!Number.isFinite(t)) return false
    if (t - this.lastSampleT < this.minDt) return false
    const clean: Record<string, number> = {}
    for (const ch of this.channels) {
      const v = values[ch.id]
      clean[ch.id] = Number.isFinite(v) ? v : NaN
    }
    this.samples.push({ t, values: clean })
    this.lastSampleT = t
    if (this.samples.length > this.maxSamples) {
      // Drop oldest in chunks of 64 to avoid O(n) splice per push.
      this.samples.splice(0, this.samples.length - this.maxSamples)
    }
    return true
  }

  reset(): void {
    this.samples = []
    this.lastSampleT = -Infinity
  }

  size(): number {
    return this.samples.length
  }

  getChannels(): readonly Channel[] {
    return this.channels
  }

  /** Flat array suitable for `<LineChart data={...}>` from recharts. */
  getSeries(): Array<Record<string, number>> {
    return this.samples.map((s) => ({ t: s.t, ...s.values }))
  }

  /** Last sample (or null if empty). */
  latest(): SamplePoint | null {
    return this.samples.length === 0 ? null : this.samples[this.samples.length - 1]
  }

  /** Downsample to at most N points using simple stride decimation. */
  decimate(maxPoints: number): SamplePoint[] {
    if (maxPoints <= 0) return []
    if (this.samples.length <= maxPoints) return this.samples.slice()
    const stride = this.samples.length / maxPoints
    const out: SamplePoint[] = []
    for (let i = 0; i < maxPoints; i += 1) {
      const idx = Math.min(this.samples.length - 1, Math.floor(i * stride))
      out.push(this.samples[idx])
    }
    return out
  }

  /**
   * Compute scalar diagnostics over the captured window.
   * Returns min/max/mean/std/last per channel — used to display "péak vitesse"
   * style readouts and detect numerical blow-ups.
   */
  diagnostics(): Record<string, { min: number; max: number; mean: number; std: number; last: number; count: number }> {
    const out: Record<string, { min: number; max: number; mean: number; std: number; last: number; count: number }> = {}
    for (const ch of this.channels) {
      let min = Infinity
      let max = -Infinity
      let sum = 0
      let sumSq = 0
      let n = 0
      let last = NaN
      for (const sample of this.samples) {
        const v = sample.values[ch.id]
        if (!Number.isFinite(v)) continue
        if (v < min) min = v
        if (v > max) max = v
        sum += v
        sumSq += v * v
        last = v
        n += 1
      }
      const mean = n > 0 ? sum / n : NaN
      const variance = n > 1 ? Math.max(0, sumSq / n - mean * mean) : 0
      out[ch.id] = {
        min: n > 0 ? min : NaN,
        max: n > 0 ? max : NaN,
        mean,
        std: Math.sqrt(variance),
        last,
        count: n,
      }
    }
    return out
  }

  /**
   * RFC 4180-ish CSV with a header that includes units in parentheses.
   * Numbers are written with up to 9 significant digits, NaN as empty cell —
   * matches what Excel/LibreOffice import cleanly.
   */
  toCsv(): string {
    const header = ['t (s)', ...this.channels.map((c) => c.unit ? `${c.label} (${c.unit})` : c.label)]
    const lines: string[] = [header.map(escapeCsv).join(',')]
    for (const sample of this.samples) {
      const row = [formatNumber(sample.t)]
      for (const ch of this.channels) row.push(formatNumber(sample.values[ch.id]))
      lines.push(row.join(','))
    }
    return lines.join('\n')
  }

  /**
   * CSV "rapport" : commence par des lignes de commentaires (préfixées #)
   * avec un résumé statistique par canal, puis le CSV brut.
   *
   * Format adapté aux dossiers BAC STI2D où on demande "données + analyse".
   * Excel et LibreOffice savent ignorer les lignes commencent par # avec
   * le bon paramètre d'import ; sinon elles apparaissent comme texte.
   */
  toCsvReport(meta: { phenomenon?: string; integrator?: string; durationS?: number; params?: Record<string, number> } = {}): string {
    const diag = this.diagnostics()
    const head: string[] = []
    head.push(`# Aurora simulator export`)
    if (meta.phenomenon) head.push(`# Phenomène : ${meta.phenomenon}`)
    if (meta.integrator) head.push(`# Intégrateur : ${meta.integrator}`)
    if (meta.durationS != null) head.push(`# Durée simulée : ${meta.durationS.toFixed(3)} s`)
    head.push(`# Samples : ${this.samples.length}`)
    if (meta.params) {
      const formatted = Object.entries(meta.params)
        .map(([k, v]) => `${k}=${formatNumber(v)}`)
        .join(', ')
      if (formatted) head.push(`# Paramètres : ${formatted}`)
    }
    head.push(`#`)
    head.push(`# Résumé statistique par canal :`)
    head.push(`# channel, min, max, mean, std, last, count`)
    for (const ch of this.channels) {
      const d = diag[ch.id]
      head.push(`# ${ch.label}${ch.unit ? ' (' + ch.unit + ')' : ''}, ${formatNumber(d.min)}, ${formatNumber(d.max)}, ${formatNumber(d.mean)}, ${formatNumber(d.std)}, ${formatNumber(d.last)}, ${d.count}`)
    }
    head.push(`#`)
    return head.join('\n') + '\n' + this.toCsv()
  }
}

function escapeCsv(value: string): string {
  if (/[",\r\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`
  }
  return value
}

function formatNumber(v: number): string {
  if (!Number.isFinite(v)) return ''
  // Match Excel-friendly precision without trailing junk.
  const abs = Math.abs(v)
  if (abs !== 0 && (abs < 1e-4 || abs >= 1e9)) return v.toExponential(6)
  return Number(v.toPrecision(9)).toString()
}

/** Trigger a CSV download in the browser. Returns true if launched. */
export function downloadCsv(recorder: DataRecorder, filename: string): boolean {
  if (typeof document === 'undefined' || typeof URL === 'undefined') return false
  const csv = recorder.toCsv()
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  // Defer revoke so Safari/older Edge can finish the download.
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return true
}
