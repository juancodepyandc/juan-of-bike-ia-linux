/**
 * speakify(raw) — prépare un texte pour le moteur TTS français.
 * Corrige les symboles mathématiques, chimiques, grecs, scientifiques,
 * historiques, biologiques et littéraires qui sont mal lus en synthèse vocale.
 */

// --- Greek letters -----------------------------------------------------------
const GREEK_MAP: Record<string, string> = {
  'α': 'alpha', 'β': 'bêta', 'γ': 'gamma', 'δ': 'delta',
  'ε': 'epsilon', 'ζ': 'dzêta', 'η': 'êta', 'θ': 'thêta',
  'ι': 'iota', 'κ': 'kappa', 'λ': 'lambda', 'μ': 'mu',
  'ν': 'nu', 'ξ': 'ksi', 'π': 'pi', 'ρ': 'rhô',
  'σ': 'sigma', 'τ': 'tau', 'υ': 'upsilon', 'φ': 'phi',
  'χ': 'khi', 'ψ': 'psi', 'ω': 'oméga',
  'Α': 'alpha', 'Β': 'bêta', 'Γ': 'gamma majuscule', 'Δ': 'delta majuscule',
  'Σ': 'somme', 'Π': 'produit', 'Ω': 'oméga majuscule',
  'Θ': 'thêta majuscule', 'Λ': 'lambda majuscule', 'Φ': 'phi majuscule', 'Ψ': 'psi majuscule',
}

// --- Math / physics / logic symbols -----------------------------------------
const SYMBOL_MAP: Record<string, string> = {
  '∑': 'somme de',
  '∏': 'produit de',
  '∫': 'intégrale de',
  '∂': 'dérivée partielle',
  '∇': 'nabla',
  '√': 'racine carrée de',
  '∞': 'infini',
  '≈': 'environ égal à',
  '≠': 'différent de',
  '≤': 'inférieur ou égal à',
  '≥': 'supérieur ou égal à',
  '<': 'inférieur à',
  '>': 'supérieur à',
  '±': 'plus ou moins',
  '∓': 'moins ou plus',
  '×': 'fois',
  '÷': 'divisé par',
  '·': ' fois ',
  '⋅': ' fois ',
  '∘': 'rond',
  '∈': 'appartient à',
  '∉': "n'appartient pas à",
  '∋': 'contient',
  '⊂': 'inclus dans',
  '⊃': 'contient',
  '⊆': 'inclus ou égal à',
  '⊇': 'contient ou égal à',
  '∪': 'union',
  '∩': 'intersection',
  '∅': 'ensemble vide',
  '∀': 'pour tout',
  '∃': 'il existe',
  '¬': 'non',
  '∧': 'et',
  '∨': 'ou',
  '⇒': 'implique',
  '⇔': 'équivalent à',
  '→': 'va vers',
  '←': 'flèche depuis',
  '↔': 'double flèche',
  '↦': 'a pour image',
  '°': ' degré',
  '′': ' prime',
  '″': ' seconde',
  '‰': ' pour mille',
  '%': ' pour cent',
  '€': ' euros',
  '$': ' dollars',
  '£': ' livres',
  'ℝ': 'l\'ensemble des réels',
  'ℕ': 'l\'ensemble des entiers naturels',
  'ℤ': 'l\'ensemble des entiers relatifs',
  'ℚ': 'l\'ensemble des rationnels',
  'ℂ': 'l\'ensemble des complexes',
  '⊕': 'somme directe',
  '⊗': 'produit tensoriel',
  '∥': 'parallèle à',
  '⊥': 'perpendiculaire à',
  '∠': 'angle',
  '△': 'triangle',
  '□': 'carré',
  '○': 'cercle',
}

// --- Sub/superscripts -------------------------------------------------------
const SUPERSCRIPT_MAP: Record<string, string> = {
  '⁰': '0', '¹': '1', '²': ' au carré', '³': ' au cube',
  '⁴': ' puissance 4', '⁵': ' puissance 5', '⁶': ' puissance 6',
  '⁷': ' puissance 7', '⁸': ' puissance 8', '⁹': ' puissance 9',
  '⁺': ' plus', '⁻': ' moins', 'ⁿ': ' puissance n',
}
const SUBSCRIPT_MAP: Record<string, string> = {
  '₀': ' zéro', '₁': ' un', '₂': ' deux', '₃': ' trois',
  '₄': ' quatre', '₅': ' cinq', '₆': ' six',
  '₇': ' sept', '₈': ' huit', '₉': ' neuf',
  '₊': ' plus', '₋': ' moins', 'ₙ': ' n',
}

// --- Units ------------------------------------------------------------------
const UNIT_MAP: Record<string, string> = {
  'km/h': 'kilomètres par heure',
  'm/s': 'mètres par seconde',
  'km': 'kilomètres',
  'cm': 'centimètres',
  'mm': 'millimètres',
  'µm': 'micromètres',
  'nm': 'nanomètres',
  'kg': 'kilogrammes',
  'mg': 'milligrammes',
  'µg': 'microgrammes',
  'mL': 'millilitres',
  'cL': 'centilitres',
  'dL': 'décilitres',
  'Hz': 'hertz',
  'kHz': 'kilohertz',
  'MHz': 'mégahertz',
  'GHz': 'gigahertz',
  'kWh': 'kilowattheures',
  'mV': 'millivolts',
  'kV': 'kilovolts',
  'mA': 'milliampères',
  'kΩ': 'kiloohms',
  'MΩ': 'mégaohms',
  'µF': 'microfarads',
  'pF': 'picofarads',
  'nF': 'nanofarads',
  'mol': 'moles',
  '°C': ' degrés Celsius',
  '°F': ' degrés Fahrenheit',
  'K': 'kelvins',
}

// --- Chemistry expansion (CH4, H2O, Fe2O3...) -------------------------------
function expandChemical(text: string): string {
  // Detect pattern like CH4, H2O, Fe2O3, C6H12O6
  return text.replace(/\b([A-Z][a-z]?)(\d+)/g, (_, el: string, num: string) => `${el} ${num}`)
    .replace(/\b([A-Z][a-z]?)\b/g, (m: string) => m)
}

// --- LaTeX (inline $...$ and block $$...$$) ---------------------------------
function expandLatex(latex: string): string {
  let s = latex
  // \frac{a}{b} → a sur b
  s = s.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, '($1) sur ($2)')
  // \sqrt{x} → racine carrée de x
  s = s.replace(/\\sqrt\{([^{}]+)\}/g, 'racine carrée de ($1)')
  // \sqrt[n]{x} → racine n-ième de x
  s = s.replace(/\\sqrt\[(\d+)\]\{([^{}]+)\}/g, 'racine $1-ième de ($2)')
  // \int_a^b, \sum_{a}^{b}
  s = s.replace(/\\int(_[^\s]+)?(\^[^\s]+)?/g, 'intégrale')
  s = s.replace(/\\sum(_[^\s]+)?(\^[^\s]+)?/g, 'somme')
  s = s.replace(/\\prod(_[^\s]+)?(\^[^\s]+)?/g, 'produit')
  s = s.replace(/\\lim(_[^\s]+)?/g, 'limite')
  s = s.replace(/\\log/g, 'logarithme')
  s = s.replace(/\\ln/g, 'logarithme népérien')
  s = s.replace(/\\exp/g, 'exponentielle')
  s = s.replace(/\\sin/g, 'sinus')
  s = s.replace(/\\cos/g, 'cosinus')
  s = s.replace(/\\tan/g, 'tangente')
  s = s.replace(/\\cot/g, 'cotangente')
  // LaTeX commands for greek letters
  const latexGreek: Record<string, string> = {
    'alpha': 'alpha', 'beta': 'bêta', 'gamma': 'gamma', 'delta': 'delta',
    'epsilon': 'epsilon', 'zeta': 'dzêta', 'eta': 'êta', 'theta': 'thêta',
    'iota': 'iota', 'kappa': 'kappa', 'lambda': 'lambda', 'mu': 'mu',
    'nu': 'nu', 'xi': 'ksi', 'pi': 'pi', 'rho': 'rhô',
    'sigma': 'sigma', 'tau': 'tau', 'upsilon': 'upsilon', 'phi': 'phi',
    'chi': 'khi', 'psi': 'psi', 'omega': 'oméga',
  }
  for (const [k, v] of Object.entries(latexGreek)) {
    s = s.replace(new RegExp(`\\\\${k}\\b`, 'g'), v)
    s = s.replace(new RegExp(`\\\\${k.charAt(0).toUpperCase() + k.slice(1)}\\b`, 'g'), v + ' majuscule')
  }
  // Power: x^2 → x au carré, x^{n} → x puissance n
  s = s.replace(/([A-Za-z0-9\)\]]+)\^\{([^{}]+)\}/g, '$1 puissance $2')
  s = s.replace(/([A-Za-z0-9\)\]]+)\^2\b/g, '$1 au carré')
  s = s.replace(/([A-Za-z0-9\)\]]+)\^3\b/g, '$1 au cube')
  s = s.replace(/([A-Za-z0-9\)\]]+)\^([A-Za-z0-9])/g, '$1 puissance $2')
  // Subscripts: x_1 → x indice 1, x_{n} → x indice n
  s = s.replace(/([A-Za-z])_\{([^{}]+)\}/g, '$1 indice $2')
  s = s.replace(/([A-Za-z])_([A-Za-z0-9])/g, '$1 indice $2')
  // \cdot → fois
  s = s.replace(/\\cdot/g, ' fois ')
  s = s.replace(/\\times/g, ' fois ')
  s = s.replace(/\\div/g, ' divisé par ')
  s = s.replace(/\\pm/g, ' plus ou moins ')
  s = s.replace(/\\leq|\\le\b/g, ' inférieur ou égal à ')
  s = s.replace(/\\geq|\\ge\b/g, ' supérieur ou égal à ')
  s = s.replace(/\\neq/g, ' différent de ')
  s = s.replace(/\\approx/g, ' environ égal à ')
  s = s.replace(/\\rightarrow|\\to/g, ' implique ')
  s = s.replace(/\\Leftrightarrow|\\iff/g, ' équivaut à ')
  s = s.replace(/\\forall/g, ' pour tout ')
  s = s.replace(/\\exists/g, ' il existe ')
  s = s.replace(/\\in\b/g, ' appartient à ')
  s = s.replace(/\\notin/g, ' n\'appartient pas à ')
  s = s.replace(/\\subset/g, ' inclus dans ')
  s = s.replace(/\\cup/g, ' union ')
  s = s.replace(/\\cap/g, ' intersection ')
  s = s.replace(/\\emptyset/g, ' ensemble vide ')
  s = s.replace(/\\infty/g, ' infini ')
  s = s.replace(/\\mathbb\{R\}/g, 'l\'ensemble des réels')
  s = s.replace(/\\mathbb\{N\}/g, 'l\'ensemble des entiers naturels')
  s = s.replace(/\\mathbb\{Z\}/g, 'l\'ensemble des entiers relatifs')
  s = s.replace(/\\mathbb\{Q\}/g, 'l\'ensemble des rationnels')
  s = s.replace(/\\mathbb\{C\}/g, 'l\'ensemble des complexes')
  // Remove any remaining braces and backslashes
  s = s.replace(/[\\{}]/g, ' ')
  return s
}

// --- Math-step pauses -------------------------------------------------------
// For lines like "c² = 25 + 49 - 70×0,5" or "c² = 74 - 35 = 39"
// we want the TTS to breathe between steps, and to say "soit égal à"
// for the 2nd (and further) = inside the same line.
function addMathPauses(text: string): string {
  const lines = text.split('\n')
  const out: string[] = []
  const hasEq = /=/
  const hasOp = /[\d+\-*/×÷()√²³⁴⁵⁶⁷⁸⁹⁰¹]/

  const processSegment = (segment: string): string => {
    if (!hasEq.test(segment) || !hasOp.test(segment)) return segment
    const parts = segment.split('=')
    if (parts.length <= 2) return segment
    let rebuilt = parts[0].replace(/\s+$/, '') + ' égale ' + parts[1].trim()
    for (let j = 2; j < parts.length; j++) {
      rebuilt += ', soit égal à ' + parts[j].trim()
    }
    return rebuilt
  }

  for (const raw of lines) {
    const line = raw
    const isCalcish = hasEq.test(line) && hasOp.test(line)
    if (!isCalcish) {
      out.push(line)
      continue
    }
    // Split line into sentences so a multi-= chain is only applied within a
    // single sentence; otherwise "Donc c = 5" following ". c² = 5² = 74"
    // would get erroneously chained together.
    const sentences = line.split(/(?<=[.!?])\s+/)
    const rebuiltSentences = sentences.map(processSegment)
    let rebuiltLine = rebuiltSentences.join(' ')
    // Terminate final sentence so chunker treats it as one
    const trimmed = rebuiltLine.replace(/\s+$/, '')
    rebuiltLine = /[.!?;:]$/.test(trimmed) ? trimmed : trimmed + '.'
    out.push(rebuiltLine)
    out.push('') // paragraph break -> narrate splits on \n\n for breathing
  }
  // Logical connector pause: "Donc X" → "Donc, X"
  let joined = out.join('\n')
  joined = joined.replace(/(^|[\s.!?])Donc\s+/g, '$1Donc, ')
  joined = joined.replace(/(^|[\s.!?])Ainsi\s+/g, '$1Ainsi, ')
  joined = joined.replace(/(^|[\s.!?])Or\s+/g, '$1Or, ')
  joined = joined.replace(/(^|[\s.!?])(Par conséquent|En conclusion|Finalement)\s+/g, '$1$2, ')
  return joined
}

// --- Markdown stripping -----------------------------------------------------
function stripMarkdown(text: string): string {
  let s = text
  // Strip code blocks entirely (read them is noisy)
  s = s.replace(/```[\s\S]*?```/g, ' (bloc de code) ')
  s = s.replace(/`([^`]+)`/g, ' $1 ')
  // Headings # ## ### ...
  s = s.replace(/^#{1,6}\s+/gm, '')
  // Lists -, *, +
  s = s.replace(/^\s*[-*+]\s+/gm, '')
  // Ordered lists
  s = s.replace(/^\s*\d+\.\s+/gm, '')
  // Blockquote >
  s = s.replace(/^\s*>\s?/gm, '')
  // Bold **text**, __text__
  s = s.replace(/\*\*([^*]+)\*\*/g, '$1')
  s = s.replace(/__([^_]+)__/g, '$1')
  // Italic *text*, _text_ (simple, careful not to eat maths)
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1$2')
  s = s.replace(/(^|[^_])_([^_\n]+)_/g, '$1$2')
  // Strike ~~
  s = s.replace(/~~([^~]+)~~/g, '$1')
  // Links [text](url)
  s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
  // Images ![alt](url)
  s = s.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
  // Raw URLs
  s = s.replace(/https?:\/\/[^\s]+/g, '')
  // Horizontal rules
  s = s.replace(/^-{3,}$/gm, '')
  // Tables pipe chars
  s = s.replace(/\|/g, ', ')
  return s
}

// --- Expand units like 12 km/h, 3 m/s, 25 °C -------------------------------
function expandUnits(text: string): string {
  let s = text
  // Order matters: longer patterns first
  const sortedUnits = Object.entries(UNIT_MAP).sort((a, b) => b[0].length - a[0].length)
  for (const [unit, label] of sortedUnits) {
    // Word boundary on numeric side
    const regex = new RegExp(`([\\d,.]+)\\s*${unit.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'g')
    s = s.replace(regex, (_m, num: string) => `${num} ${label}`)
  }
  return s
}

// --- Abbreviations historical / literary ------------------------------------
const ABBREV_MAP: Record<string, string> = {
  'av\\. J\\.?-?C\\.?': 'avant Jésus-Christ',
  'ap\\. J\\.?-?C\\.?': 'après Jésus-Christ',
  'ex\\.\\s': 'par exemple ',
  'c\\.-à-d\\.': 'c\'est-à-dire',
  'etc\\.': 'et cetera',
  'M\\.\\s': 'monsieur ',
  'Mme\\s': 'madame ',
  'Mr\\.?\\s': 'monsieur ',
  'Dr\\.?\\s': 'docteur ',
  'Pr\\.?\\s': 'professeur ',
  'p\\.': 'page',
  'pp\\.': 'pages',
  'n°': 'numéro',
  '§': 'paragraphe',
}

function expandAbbreviations(text: string): string {
  let s = text
  for (const [pat, label] of Object.entries(ABBREV_MAP)) {
    s = s.replace(new RegExp(pat, 'g'), label)
  }
  return s
}

// --- Main export ------------------------------------------------------------
export function speakify(raw: string): string {
  if (!raw) return ''

  let s = raw

  // Extract and process LaTeX blocks first
  s = s.replace(/\$\$([\s\S]+?)\$\$/g, (_m, inner: string) => ` ${expandLatex(inner)} `)
  s = s.replace(/\$([^$\n]+)\$/g, (_m, inner: string) => ` ${expandLatex(inner)} `)

  // Strip markdown noise
  s = stripMarkdown(s)

  // Expand abbreviations (before we mess with dots)
  s = expandAbbreviations(s)

  // Expand unit tokens (km, mg, °C, etc.)
  s = expandUnits(s)

  // Replace supra/sub Unicode
  for (const [k, v] of Object.entries(SUPERSCRIPT_MAP)) {
    s = s.replaceAll(k, v)
  }
  for (const [k, v] of Object.entries(SUBSCRIPT_MAP)) {
    s = s.replaceAll(k, v)
  }

  // Replace Greek letters
  for (const [k, v] of Object.entries(GREEK_MAP)) {
    s = s.replaceAll(k, ' ' + v + ' ')
  }

  // Replace math symbols
  for (const [k, v] of Object.entries(SYMBOL_MAP)) {
    s = s.replaceAll(k, ' ' + v + ' ')
  }

  // Chemistry formulas like H2O, CH4 → "H 2 O", "C H 4" so TTS reads each element
  s = expandChemical(s)

  // Math-step pauses: split multi-= chains, terminate calc lines with period,
  // force a paragraph break so the TTS engine breathes between steps.
  s = addMathPauses(s)

  // Collapse whitespace (preserve paragraph breaks \n\n)
  s = s.replace(/[ \t]+/g, ' ')
       .replace(/[ \t]+\n/g, '\n')
       .replace(/\n{3,}/g, '\n\n')
       .trim()

  return s
}

export default speakify
