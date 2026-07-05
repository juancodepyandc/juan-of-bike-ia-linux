// Analyseur d'entropie + patterns — zxcvbn-light maison.

const COMMON_PASSWORDS = new Set([
  'password', '123456', '123456789', 'qwerty', 'abc123', 'motdepasse', 'azerty',
  'admin', 'welcome', 'letmein', 'monkey', 'dragon', 'football', 'baseball',
  'iloveyou', 'superman', 'princess', 'shadow', 'master', 'sunshine',
])

const KEYBOARD_ROWS = [
  '1234567890', 'qwertyuiop', 'azertyuiop', 'asdfghjkl', 'qsdfghjklm', 'zxcvbnm', 'wxcvbn',
]

export interface PasswordStrength {
  entropy: number
  score: 0 | 1 | 2 | 3 | 4
  crackTimeSec: number
  crackTimeHuman: string
  feedback: string[]
  patterns: string[]
  charsetSize: number
  length: number
}

function charsetSize(pw: string) {
  let size = 0
  if (/[a-z]/.test(pw)) size += 26
  if (/[A-Z]/.test(pw)) size += 26
  if (/[0-9]/.test(pw)) size += 10
  if (/[^a-zA-Z0-9]/.test(pw)) size += 32
  return size || 1
}

function detectPatterns(pw: string) {
  const patterns: string[] = []
  const lc = pw.toLowerCase()
  if (COMMON_PASSWORDS.has(lc)) patterns.push('commun')
  if (/^\d+$/.test(pw)) patterns.push('tous chiffres')
  if (/^(.)\1+$/.test(pw)) patterns.push('caractère répété')
  if (/(.)\1{2,}/.test(pw)) patterns.push('triple répétition')
  for (const row of KEYBOARD_ROWS) {
    for (let i = 0; i < row.length - 2; i++) {
      const seq = row.substr(i, 3)
      if (lc.includes(seq)) { patterns.push(`séquence clavier "${seq}"`); break }
    }
  }
  const years = pw.match(/(19|20)\d{2}/)
  if (years) patterns.push(`année ${years[0]}`)
  if (/^[a-zA-Z]+\d+$/.test(pw)) patterns.push('mot + chiffres')
  if (/^[a-zA-Z]+!$/.test(pw)) patterns.push('mot + !')
  if (/password|admin|azerty|qwerty|login|secret/i.test(pw)) patterns.push('mot commun intégré')
  return patterns
}

export function analyzePassword(pw: string): PasswordStrength {
  if (!pw) {
    return {
      entropy: 0, score: 0, crackTimeSec: 0, crackTimeHuman: 'instantané',
      feedback: ['entre un mot de passe'], patterns: [], charsetSize: 0, length: 0,
    }
  }
  const size = charsetSize(pw)
  const rawEntropy = pw.length * Math.log2(size)
  const patterns = detectPatterns(pw)
  const penalty = patterns.length * 10
  const entropy = Math.max(0, rawEntropy - penalty)
  const guessesPerSec = 1e10 // GPU moderne pour hash rapide
  const crackTimeSec = Math.pow(2, entropy) / (2 * guessesPerSec)

  let score: 0 | 1 | 2 | 3 | 4 = 0
  if (entropy >= 28) score = 1
  if (entropy >= 40) score = 2
  if (entropy >= 60) score = 3
  if (entropy >= 80) score = 4

  const feedback: string[] = []
  if (pw.length < 12) feedback.push('allonger à 12+ caractères')
  if (!/[A-Z]/.test(pw)) feedback.push('ajouter une majuscule')
  if (!/[a-z]/.test(pw)) feedback.push('ajouter une minuscule')
  if (!/\d/.test(pw)) feedback.push('ajouter un chiffre')
  if (!/[^a-zA-Z0-9]/.test(pw)) feedback.push('ajouter un symbole')
  if (patterns.length > 0) feedback.push('éviter les motifs détectés')
  if (COMMON_PASSWORDS.has(pw.toLowerCase())) feedback.push('mot de passe trop connu')

  return {
    entropy: Math.round(entropy * 10) / 10,
    score,
    crackTimeSec,
    crackTimeHuman: humanTime(crackTimeSec),
    feedback,
    patterns,
    charsetSize: size,
    length: pw.length,
  }
}

function humanTime(sec: number) {
  if (sec < 1e-6) return 'instantané'
  if (sec < 1) return `${(sec * 1000).toFixed(1)} ms`
  if (sec < 60) return `${sec.toFixed(1)} s`
  if (sec < 3600) return `${(sec / 60).toFixed(1)} min`
  if (sec < 86400) return `${(sec / 3600).toFixed(1)} h`
  if (sec < 2592000) return `${(sec / 86400).toFixed(1)} j`
  if (sec < 31536000) return `${(sec / 2592000).toFixed(1)} mois`
  const years = sec / 31536000
  if (years < 1000) return `${years.toFixed(1)} ans`
  if (years < 1e6) return `${(years / 1000).toFixed(1)} mille ans`
  if (years < 1e9) return `${(years / 1e6).toFixed(1)} millions d'années`
  return `${(years / 1e9).toFixed(1)} milliards d'années`
}

const LOWER = 'abcdefghijklmnopqrstuvwxyz'
const UPPER = LOWER.toUpperCase()
const DIGITS = '0123456789'
const SYMBOLS = '!@#$%^&*()-_=+[]{};:,.<>?/|~`'
const AMBIGUOUS = 'il1Lo0O'

export interface GenerateOptions {
  length: number
  lower: boolean
  upper: boolean
  digits: boolean
  symbols: boolean
  excludeAmbiguous: boolean
}

export function generatePassword(opts: GenerateOptions) {
  let pool = ''
  if (opts.lower) pool += LOWER
  if (opts.upper) pool += UPPER
  if (opts.digits) pool += DIGITS
  if (opts.symbols) pool += SYMBOLS
  if (opts.excludeAmbiguous) {
    for (const ch of AMBIGUOUS) pool = pool.split(ch).join('')
  }
  if (!pool) return ''
  const buf = new Uint32Array(opts.length)
  crypto.getRandomValues(buf)
  let out = ''
  for (const n of buf) out += pool[n % pool.length]
  return out
}

// Diceware EFF wordlist courte — 50 mots échantillon. En production: charger EFF 7776.
const DICEWARE_SHORT = [
  'abacus', 'abbey', 'accent', 'access', 'accord', 'acetate', 'acrobat', 'acute',
  'adapter', 'addict', 'addition', 'adorable', 'advance', 'affair', 'agent', 'airlock',
  'album', 'alert', 'alkaline', 'almond', 'alpaca', 'alpha', 'alter', 'amazon',
  'amber', 'ammonia', 'amnesia', 'amphibia', 'amuse', 'analyst', 'anchor', 'android',
  'anemone', 'angel', 'angular', 'anime', 'ankle', 'announce', 'antler', 'anvil',
  'applause', 'apricot', 'aquarium', 'archer', 'arctic', 'argument', 'armadillo', 'armchair',
  'arrival', 'artist',
]

export function generateDiceware(words = 5, separator = '-') {
  const buf = new Uint32Array(words)
  crypto.getRandomValues(buf)
  return Array.from(buf).map((n) => DICEWARE_SHORT[n % DICEWARE_SHORT.length]).join(separator)
}
