/**
 * Convertit le texte en version prononçable pour le TTS.
 * Passe 1: retirer le markdown
 * Passe 2: convertir TOUS les symboles/operateurs/formules en mots
 * Passe 3: alphabets étrangers (actuels et historiques)
 * Passe 4: formules physiques courantes
 */
export function cleanTextForVoice(text: string): string {
  if (!text) return ''

  let c = text
    // Markdown
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`]+`/g, ' ')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*{1,3}(.+?)\*{1,3}/g, '$1')
    .replace(/_{1,3}(.+?)_{1,3}/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^[-*+]\s+/gm, '')
    .replace(/^\d+\.\s+/gm, '')
    .replace(/^---+$/gm, '')
    .replace(/<think>[\s\S]*?<\/think>/g, '')

  // LaTeX
  c = c.replace(/\\frac\{(.+?)\}\{(.+?)\}/g, ' $1 sur $2 ')
  c = c.replace(/\\sqrt\[(\d+)\]\{(.+?)\}/g, ' racine $1-ieme de $2 ')
  c = c.replace(/\\sqrt\{(.+?)\}/g, ' racine de $1 ')
  c = c.replace(/\\text\{(.+?)\}/g, '$1')
  c = c.replace(/\\mathrm\{(.+?)\}/g, '$1')
  c = c.replace(/\\mathbb\{(.+?)\}/g, '$1')
  c = c.replace(/\\vec\{(.+?)\}/g, ' vecteur $1 ')
  c = c.replace(/\\overline\{(.+?)\}/g, ' $1 barre ')
  c = c.replace(/\\hat\{(.+?)\}/g, ' $1 chapeau ')
  c = c.replace(/\\dot\{(.+?)\}/g, ' $1 point ')
  c = c.replace(/\\ddot\{(.+?)\}/g, ' $1 deux points ')
  c = c.replace(/\\sum_\{(.+?)\}\^\{(.+?)\}/g, ' somme de $1 a $2 ')
  c = c.replace(/\\int_\{(.+?)\}\^\{(.+?)\}/g, ' integrale de $1 a $2 ')
  c = c.replace(/\\prod_\{(.+?)\}\^\{(.+?)\}/g, ' produit de $1 a $2 ')
  c = c.replace(/\\lim_\{(.+?)\}/g, ' limite quand $1 ')
  c = c.replace(/\\sum/g, ' somme ').replace(/\\int/g, ' integrale ').replace(/\\prod/g, ' produit ')
  c = c.replace(/\\lim/g, ' limite ').replace(/\\infty/g, " l'infini ")
  c = c.replace(/\\to|\\rightarrow|\\Rightarrow/g, ' vers ')
  c = c.replace(/\\Leftrightarrow/g, ' si et seulement si ')
  c = c.replace(/\\approx/g, ' environ ').replace(/\\neq/g, ' different de ')
  c = c.replace(/\\pm/g, ' plus ou moins ').replace(/\\times/g, ' fois ')
  c = c.replace(/\\div/g, ' divise par ').replace(/\\cdot/g, ' fois ')
  c = c.replace(/\\leq|\\le/g, ' inferieur ou egal a ').replace(/\\geq|\\ge/g, ' superieur ou egal a ')
  c = c.replace(/\\ll/g, ' tres inferieur a ').replace(/\\gg/g, ' tres superieur a ')
  c = c.replace(/\\forall/g, ' pour tout ').replace(/\\exists/g, ' il existe ')
  c = c.replace(/\\in\b/g, ' appartient a ').replace(/\\notin/g, " n'appartient pas a ")
  c = c.replace(/\\subset/g, ' inclus dans ').replace(/\\supset/g, ' contient ')
  c = c.replace(/\\cup/g, ' union ').replace(/\\cap/g, ' intersection ')
  c = c.replace(/\\emptyset|\\varnothing/g, ' ensemble vide ')
  c = c.replace(/\\partial/g, ' derivee partielle ').replace(/\\nabla/g, ' nabla ')
  c = c.replace(/\\left|\\right/g, '')
  c = c.replace(/\\binom\{(.+?)\}\{(.+?)\}/g, ' $1 parmi $2 ')
  c = c.replace(/\\log_\{(.+?)\}/g, ' logarithme base $1 ')

  // Lettres grecques LaTeX + Unicode — minuscules et majuscules
  const greekMap: [RegExp, string][] = [
    [/\\alpha|α/gi, ' alpha '], [/\\beta|β/gi, ' beta '],
    [/\\gamma|γ/gi, ' gamma '], [/\\Gamma|Γ/g, ' grand gamma '],
    [/\\delta|δ/gi, ' delta '], [/\\Delta|Δ/g, ' grand delta '],
    [/\\epsilon|\\varepsilon|ε/gi, ' epsilon '], [/\\theta|\\vartheta|θ/gi, ' theta '],
    [/\\Theta|Θ/g, ' grand theta '],
    [/\\lambda|λ/gi, ' lambda '], [/\\Lambda|Λ/g, ' grand lambda '],
    [/\\mu|μ/gi, ' mu '], [/\\nu|ν/gi, ' nu '],
    [/\\xi|ξ/gi, ' ksi '], [/\\Xi|Ξ/g, ' grand ksi '],
    [/\\pi|π/gi, ' pi '], [/\\Pi|Π/g, ' grand pi '],
    [/\\sigma|\\varsigma|σ|ς/gi, ' sigma '], [/\\Sigma|Σ/g, ' grand sigma '],
    [/\\tau|τ/gi, ' tau '], [/\\upsilon|υ/gi, ' upsilon '],
    [/\\phi|\\varphi|φ/gi, ' phi '], [/\\Phi|Φ/g, ' grand phi '],
    [/\\chi|χ/gi, ' chi '], [/\\psi|ψ/gi, ' psi '], [/\\Psi|Ψ/g, ' grand psi '],
    [/\\omega|ω/gi, ' omega '], [/\\Omega|Ω/g, ' grand omega '],
    [/\\rho|\\varrho|ρ/gi, ' ro '], [/\\kappa|κ/gi, ' kappa '],
    [/\\iota|ι/gi, ' iota '], [/\\zeta|ζ/gi, ' zeta '], [/\\eta|η/gi, ' eta '],
  ]
  for (const [re, txt] of greekMap) c = c.replace(re, txt)

  // Alphabets étrangers modernes et historiques
  // Hébreu
  c = c.replace(/א/g, ' aleph ').replace(/ב/g, ' beth ').replace(/ג/g, ' guimel ')
  c = c.replace(/ד/g, ' daleth ').replace(/ה/g, ' he ').replace(/ו/g, ' vav ')
  c = c.replace(/ז/g, ' zayin ').replace(/ח/g, ' heth ').replace(/ט/g, ' teth ')
  c = c.replace(/י/g, ' yod ').replace(/כ/g, ' kaph ').replace(/ל/g, ' lamed ')
  c = c.replace(/מ/g, ' mem ').replace(/נ/g, ' noun ').replace(/ס/g, ' samekh ')
  c = c.replace(/ע/g, ' ayin ').replace(/פ/g, ' pe ').replace(/צ/g, ' tsade ')
  c = c.replace(/ק/g, ' qoph ').replace(/ר/g, ' resh ').replace(/ש/g, ' shin ')
  c = c.replace(/ת/g, ' tav ')
  // Arabe (lettres isolées courantes en maths/physique)
  c = c.replace(/ع/g, ' ayn ').replace(/ح/g, ' ha ')
  // Cyrillique (noms de lettres pour formules)
  c = c.replace(/Ж/g, ' je ').replace(/Ш/g, ' cha ').replace(/Щ/g, ' chtcha ')
  // Japonais hiragana/katakana courants
  c = c.replace(/あ/g, ' a ').replace(/い/g, ' i ').replace(/う/g, ' ou ')
  c = c.replace(/え/g, ' e ').replace(/お/g, ' o ')

  // Puissances (avant operateurs)
  c = c.replace(/²/g, ' au carre ')
  c = c.replace(/³/g, ' au cube ')
  c = c.replace(/\^\{2\}/g, ' au carre ').replace(/\^\{3\}/g, ' au cube ')
  c = c.replace(/\^2(?=[^0-9]|$)/g, ' au carre ')
  c = c.replace(/\^3(?=[^0-9]|$)/g, ' au cube ')
  c = c.replace(/\^\{(\d+)\}/g, ' puissance $1 ')
  c = c.replace(/\^(\d+)/g, ' puissance $1 ')
  c = c.replace(/\^\{([a-zA-Z])\}/g, ' exposant $1 ')

  // Indices (subscripts)
  c = c.replace(/_{(\d+)}/g, ' indice $1 ')
  c = c.replace(/_(\d+)(?=[^0-9]|$)/g, ' indice $1 ')
  c = c.replace(/_{([a-zA-Z]+)}/g, ' indice $1 ')
  c = c.replace(/₀/g, ' indice 0 ').replace(/₁/g, ' indice 1 ').replace(/₂/g, ' indice 2 ')
  c = c.replace(/₃/g, ' indice 3 ').replace(/₄/g, ' indice 4 ').replace(/ₙ/g, ' indice n ')
  c = c.replace(/ᵢ/g, ' indice i ').replace(/ⱼ/g, ' indice j ')

  // Nettoyage LaTeX
  c = c.replace(/[{}\\]/g, ' ')
  c = c.replace(/\$/g, '')

  // Fonctions math — lecture naturelle et articulée
  c = c.replace(/\bsin\b/gi, 'sinus')
  c = c.replace(/\bcos\b/gi, 'cosinus')
  c = c.replace(/\btan\b/gi, 'tangente')
  c = c.replace(/\barcsin\b/gi, 'arc sinus')
  c = c.replace(/\barccos\b/gi, 'arc cosinus')
  c = c.replace(/\barctan\b/gi, 'arc tangente')
  c = c.replace(/\bsinh\b/gi, 'sinus hyperbolique')
  c = c.replace(/\bcosh\b/gi, 'cosinus hyperbolique')
  c = c.replace(/\btanh\b/gi, 'tangente hyperbolique')
  c = c.replace(/\bln\b/gi, 'logarithme neperien de')
  c = c.replace(/\blog\b/gi, 'logarithme de')
  c = c.replace(/\bexp\b/gi, 'exponentielle de')
  c = c.replace(/\bdet\b/gi, 'determinant')
  c = c.replace(/\btr\b/gi, 'trace')
  c = c.replace(/\bdim\b/gi, 'dimension')
  c = c.replace(/\bker\b/gi, 'noyau')
  c = c.replace(/\bmax\b/gi, 'maximum')
  c = c.replace(/\bmin\b/gi, 'minimum')
  c = c.replace(/\bsup\b/gi, 'supremum')
  c = c.replace(/\binf\b(?!\w)/gi, 'infimum')
  c = c.replace(/\bf'\b/g, 'f prime')
  c = c.replace(/\bf''\b/g, 'f seconde')
  c = c.replace(/\bgcd\b/gi, 'plus grand commun diviseur')
  c = c.replace(/\blcm\b/gi, 'plus petit commun multiple')
  c = c.replace(/\bmod\b/gi, 'modulo')

  // Formules physiques courantes — lecture naturelle
  c = c.replace(/\bE\s*=\s*mc²/gi, 'E egale m c au carre')
  c = c.replace(/\bE\s*=\s*mc\^2/gi, 'E egale m c au carre')
  c = c.replace(/\bF\s*=\s*ma\b/gi, 'F egale m a')
  c = c.replace(/\bPV\s*=\s*nRT\b/gi, 'P V egale n R T')
  c = c.replace(/\bV\s*=\s*IR\b/gi, 'V egale I R')
  c = c.replace(/\be\^(x|i)/gi, 'exponentielle $1')
  c = c.replace(/\bdy\/dx\b/gi, 'd y sur d x')
  c = c.replace(/\bdx\/dt\b/gi, 'd x sur d t')
  c = c.replace(/\bd²y\/dx²\b/gi, 'd 2 y sur d x au carre')

  // Notations scientifiques
  c = c.replace(/(\d+(?:\.\d+)?)\s*[×x]\s*10\^(\d+)/g, '$1 fois 10 puissance $2')
  c = c.replace(/(\d+(?:\.\d+)?)\s*[×x]\s*10\^\{(\d+)\}/g, '$1 fois 10 puissance $2')
  c = c.replace(/(\d+(?:\.\d+)?)[eE]\+?(\d+)/g, '$1 fois 10 puissance $2')

  // Symboles Unicode math
  c = c.replace(/≤/g, ' inferieur ou egal a ')
  c = c.replace(/≥/g, ' superieur ou egal a ')
  c = c.replace(/≠/g, ' different de ')
  c = c.replace(/≈/g, ' environ egal a ')
  c = c.replace(/≡/g, ' identique a ')
  c = c.replace(/±/g, ' plus ou moins ')
  c = c.replace(/∓/g, ' moins ou plus ')
  c = c.replace(/×/g, ' fois ')
  c = c.replace(/÷/g, ' divise par ')
  c = c.replace(/∞/g, " l'infini ")
  c = c.replace(/√/g, ' racine de ')
  c = c.replace(/∛/g, ' racine cubique de ')
  c = c.replace(/∑/g, ' somme ')
  c = c.replace(/∏/g, ' produit ')
  c = c.replace(/∫/g, ' integrale ')
  c = c.replace(/∬/g, ' double integrale ')
  c = c.replace(/∭/g, ' triple integrale ')
  c = c.replace(/∈/g, ' appartient a ')
  c = c.replace(/∉/g, " n'appartient pas a ")
  c = c.replace(/∀/g, ' pour tout ')
  c = c.replace(/∃/g, ' il existe ')
  c = c.replace(/∄/g, " il n'existe pas ")
  c = c.replace(/→/g, ' vers ')
  c = c.replace(/⇒/g, ' implique ')
  c = c.replace(/⇔/g, ' si et seulement si ')
  c = c.replace(/∧/g, ' et ')
  c = c.replace(/∨/g, ' ou ')
  c = c.replace(/¬/g, ' non ')
  c = c.replace(/∅/g, ' ensemble vide ')
  c = c.replace(/⊂/g, ' inclus dans ')
  c = c.replace(/⊃/g, ' contient ')
  c = c.replace(/∪/g, ' union ')
  c = c.replace(/∩/g, ' intersection ')
  c = c.replace(/⊕/g, ' somme directe ')
  c = c.replace(/⊗/g, ' produit tensoriel ')
  c = c.replace(/∝/g, ' proportionnel a ')
  c = c.replace(/∂/g, ' derivee partielle ')
  c = c.replace(/ℝ/g, ' R ')
  c = c.replace(/ℂ/g, ' C ')
  c = c.replace(/ℕ/g, ' N ')
  c = c.replace(/ℤ/g, ' Z ')
  c = c.replace(/ℚ/g, ' Q ')

  // Operateurs de base — convertir en mots
  c = c.replace(/=/g, ' egale ')
  c = c.replace(/\+/g, ' plus ')
  c = c.replace(/(?<=\d)\s*-\s*(?=\d)/g, ' moins ')
  c = c.replace(/(?<=\s)-(?=\d)/g, ' moins ')
  c = c.replace(/\//g, ' sur ')
  c = c.replace(/\*/g, ' fois ')
  c = c.replace(/\(/g, ', ')
  c = c.replace(/\)/g, ', ')

  // Monnaie
  c = c.replace(/(\d+)\s*€/g, '$1 euros ')
  c = c.replace(/(\d+)\s*\$/g, '$1 dollars ')
  c = c.replace(/(\d+)\s*£/g, '$1 livres ')
  c = c.replace(/(\d+)\s*¥/g, '$1 yens ')
  c = c.replace(/(\d+)\s*%/g, '$1 pour cent ')
  c = c.replace(/&/g, ' et ')
  c = c.replace(/@/g, ' arobase ')
  c = c.replace(/#/g, ' diese ')

  // Chimie — molécules courantes
  c = c.replace(/\bH2O\b/gi, 'H 2 O')
  c = c.replace(/\bCO2\b/gi, 'C O 2')
  c = c.replace(/\bO2\b/gi, 'O 2')
  c = c.replace(/\bN2\b/gi, 'N 2')
  c = c.replace(/\bH2\b/gi, 'H 2')
  c = c.replace(/\bNaCl\b/gi, 'N a C l')
  c = c.replace(/\bH2SO4\b/gi, 'H 2 S O 4')
  c = c.replace(/\bNaOH\b/gi, 'N a O H')
  c = c.replace(/\bCH4\b/gi, 'C H 4')
  c = c.replace(/\bC2H5OH\b/gi, 'C 2 H 5 O H')

  // Unités physiques
  c = c.replace(/\bm\/s²?\b/gi, 'metres par seconde au carre')
  c = c.replace(/\bm\/s\b/gi, 'metres par seconde')
  c = c.replace(/\bkm\/h\b/gi, 'kilometres par heure')
  c = c.replace(/\bkg\b/gi, 'kilogrammes')
  c = c.replace(/\bmol\b/gi, 'moles')
  c = c.replace(/\bHz\b/g, 'hertz')
  c = c.replace(/\bkHz\b/g, 'kilohertz')
  c = c.replace(/\bMHz\b/g, 'megahertz')
  c = c.replace(/\bGHz\b/g, 'gigahertz')

  // Emojis
  c = c.replace(/[\u{1F000}-\u{1FFFF}]|[\u{2600}-\u{27BF}]|[\u{2300}-\u{23FF}]/gu, '')

  // Nettoyage final — espaces multiples, points de suspension
  c = c.replace(/\.{3,}/g, '. ')
  c = c.replace(/\s+/g, ' ').trim()
  return c
}
