type VisualFallbackOptions = {
  width?: string | number | null
  height?: string | number | null
}

function toPositiveInt(value: string | number | null | undefined, fallback: number) {
  const parsed = typeof value === 'number' ? value : Number.parseInt(String(value || ''), 10)
  return Number.isFinite(parsed) && parsed > 0 ? Math.min(Math.round(parsed), 4096) : fallback
}

function escapeXml(text: string) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function hashSeed(seed: string) {
  let hash = 2166136261
  for (let i = 0; i < seed.length; i += 1) {
    hash ^= seed.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

export function buildAuroraInlineSvgDataUri(seedText: string, options: VisualFallbackOptions = {}) {
  const label = (seedText || 'Aurora visual').replace(/\s+/g, ' ').trim().slice(0, 72) || 'Aurora visual'
  const width = toPositiveInt(options.width, 1600)
  const height = toPositiveInt(options.height, 900)
  const hash = hashSeed(label)
  const hueA = hash % 360
  const hueB = (hueA + 48 + (hash % 54)) % 360
  const hueC = (hueA + 168) % 360
  const safeLabel = escapeXml(label)
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 1600 900" role="img" aria-label="${safeLabel}"><defs><linearGradient id="aurora-bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="hsl(${hueA} 72% 52%)"/><stop offset=".58" stop-color="hsl(${hueB} 72% 34%)"/><stop offset="1" stop-color="hsl(${hueC} 65% 18%)"/></linearGradient><radialGradient id="aurora-light" cx="32%" cy="20%" r="68%"><stop offset="0" stop-color="rgba(255,255,255,.52)"/><stop offset=".42" stop-color="rgba(255,255,255,.16)"/><stop offset="1" stop-color="rgba(255,255,255,0)"/></radialGradient><filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="3" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncA type="table" tableValues="0 .16"/></feComponentTransfer></filter></defs><rect width="1600" height="900" fill="url(#aurora-bg)"/><rect width="1600" height="900" fill="url(#aurora-light)"/><g opacity=".26" fill="none" stroke="rgba(255,255,255,.82)" stroke-width="2"><path d="M-80 650C260 490 418 720 760 540S1260 210 1690 350"/><path d="M-120 520C300 390 520 560 840 390S1280 150 1680 260"/></g><rect width="1600" height="900" filter="url(#grain)" opacity=".42"/><g fill="white" font-family="Inter, ui-sans-serif, system-ui, sans-serif"><text x="96" y="760" font-size="42" font-weight="700" opacity=".92">${safeLabel}</text><text x="98" y="812" font-size="20" opacity=".68">Visuel de secours generatif local</text></g></svg>`
  const encoded = encodeURIComponent(svg).replace(/[!'()*]/g, (char) => `%${char.charCodeAt(0).toString(16).toUpperCase()}`)
  return `data:image/svg+xml;utf8,${encoded}`
}
