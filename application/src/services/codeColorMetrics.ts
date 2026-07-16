export type RgbColor = { r: number; g: number; b: number }
export type LabColor = { l: number; a: number; b: number }
export type ParsedColor = { raw: string; rgb: RgbColor; lab: LabColor }

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value))
}

function clampRgb(value: number): number {
  return Math.max(0, Math.min(255, Math.round(value)))
}

function srgbToLinear(value: number): number {
  const c = clamp01(value / 255)
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

function linearToSrgb(value: number): number {
  const c = clamp01(value)
  const out = c <= 0.0031308 ? 12.92 * c : 1.055 * (c ** (1 / 2.4)) - 0.055
  return clampRgb(out * 255)
}

export function rgbToLab(rgb: RgbColor): LabColor {
  const r = srgbToLinear(rgb.r)
  const g = srgbToLinear(rgb.g)
  const b = srgbToLinear(rgb.b)

  const x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
  const y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / 1.00000
  const z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883
  const f = (value: number) => value > 0.008856 ? Math.cbrt(value) : (7.787 * value) + (16 / 116)
  const fx = f(x)
  const fy = f(y)
  const fz = f(z)
  return {
    l: (116 * fy) - 16,
    a: 500 * (fx - fy),
    b: 200 * (fy - fz),
  }
}

export function deltaE76(a: LabColor, b: LabColor): number {
  return Math.sqrt((a.l - b.l) ** 2 + (a.a - b.a) ** 2 + (a.b - b.b) ** 2)
}

function parseHex(raw: string): RgbColor | null {
  const hex = raw.trim().toLowerCase()
  const match = hex.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i)
  if (!match) return null
  const value = match[1]
  if (value.length === 3) {
    return {
      r: parseInt(value[0] + value[0], 16),
      g: parseInt(value[1] + value[1], 16),
      b: parseInt(value[2] + value[2], 16),
    }
  }
  return {
    r: parseInt(value.slice(0, 2), 16),
    g: parseInt(value.slice(2, 4), 16),
    b: parseInt(value.slice(4, 6), 16),
  }
}

function parseRgb(raw: string): RgbColor | null {
  const match = raw.match(/^rgba?\(\s*([\d.]+%?)\s*,?\s+([\d.]+%?)\s*,?\s+([\d.]+%?)/i)
    ?? raw.match(/^rgba?\(\s*([\d.]+%?)\s*,\s*([\d.]+%?)\s*,\s*([\d.]+%?)/i)
  if (!match) return null
  const channel = (value: string) => value.endsWith('%')
    ? clampRgb((parseFloat(value) / 100) * 255)
    : clampRgb(parseFloat(value))
  return { r: channel(match[1]), g: channel(match[2]), b: channel(match[3]) }
}

function oklchToRgb(lightness: number, chroma: number, hue: number): RgbColor {
  const h = (hue * Math.PI) / 180
  const a = chroma * Math.cos(h)
  const b = chroma * Math.sin(h)
  const lPrime = lightness + 0.3963377774 * a + 0.2158037573 * b
  const mPrime = lightness - 0.1055613458 * a - 0.0638541728 * b
  const sPrime = lightness - 0.0894841775 * a - 1.2914855480 * b
  const l = lPrime ** 3
  const m = mPrime ** 3
  const s = sPrime ** 3
  return {
    r: linearToSrgb(+4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    g: linearToSrgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    b: linearToSrgb(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s),
  }
}

function parseOklch(raw: string): RgbColor | null {
  const match = raw.match(/^oklch\(\s*([\d.]+%?)\s+([\d.]+)\s+([\d.]+)(?:deg)?/i)
  if (!match) return null
  const lightness = match[1].endsWith('%') ? parseFloat(match[1]) / 100 : parseFloat(match[1])
  return oklchToRgb(clamp01(lightness), Math.max(0, parseFloat(match[2])), parseFloat(match[3]))
}

export function parseCssColor(raw: string): ParsedColor | null {
  const rgb = parseHex(raw) ?? parseRgb(raw) ?? parseOklch(raw)
  return rgb ? { raw, rgb, lab: rgbToLab(rgb) } : null
}

export function extractCssColors(text: string): ParsedColor[] {
  const matches = text.match(/#[0-9a-f]{3,6}\b|rgba?\([^)]+\)|oklch\([^)]+\)/gi) ?? []
  const parsed = matches
    .map(parseCssColor)
    .filter((color): color is ParsedColor => Boolean(color))
  const seen = new Set<string>()
  return parsed.filter((color) => {
    const key = `${color.rgb.r},${color.rgb.g},${color.rgb.b}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function hasPerceptualColorMatch(text: string, target: string, maxDelta = 16): boolean {
  const normalizedTarget = /^([0-9a-f]{3}|[0-9a-f]{6})$/i.test(target.trim())
    ? `#${target.trim()}`
    : target
  const targetColor = parseCssColor(normalizedTarget)
  if (!targetColor) return false
  return extractCssColors(text).some((candidate) => deltaE76(candidate.lab, targetColor.lab) <= maxDelta)
}
