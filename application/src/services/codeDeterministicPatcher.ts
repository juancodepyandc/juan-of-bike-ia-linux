// Patcher déterministe — fait UNE passe d'auto-correction sur les issues
// que les critics statiques ont remontées, sans appeler de LLM. Idéal
// comme premier étage de la boucle multi-pass : si on peut fixer une issue
// avec une regex propre, on évite de re-frapper le modèle.
//
// Stratégie : pour chaque type d'issue détecté, on applique une
// transformation conservative. Si on n'est pas sûr, on laisse passer
// (le LLM patcher prend la suite).

import type { CodeFile, CodeProject, CritiqueReport, PatcherFn } from './codeMultiPassCritique.ts'
import type { CodeIntent } from './codeIntent.ts'

export type PatchOutcome = {
  changed: boolean
  fixesApplied: string[]
}

/** Tries to fix a single file in-place. Returns the new content + log. */
function patchFile(file: CodeFile): { content: string; outcome: PatchOutcome } {
  let { content } = file
  const fixes: string[] = []

  // 1. <img sans alt> → ajoute alt=""
  const imgNoAlt = /<img\b((?:(?!alt\s*=)[^>])*)\/?>/g
  if (imgNoAlt.test(content)) {
    content = content.replace(imgNoAlt, (_m, attrs) => `<img${attrs} alt="" />`)
    fixes.push('img sans alt: alt="" ajouté')
  }

  // 2. <a> + onClick sans href → role="button" + tabIndex=0
  // Conservative : on garde le <a>, on n'ose pas changer en <button>.
  const aOnClickNoHref = /<a\b((?:(?!href)[^>])*)onClick=/g
  if (aOnClickNoHref.test(content)) {
    content = content.replace(aOnClickNoHref, (_m, attrs) => `<a${attrs}role="button" tabIndex={0} onClick=`)
    fixes.push('<a> + onClick sans href: role="button" + tabIndex=0')
  }

  // 3. document.write(...) → console.warn + log (commented out the original).
  if (/document\.write\s*\(/.test(content)) {
    content = content.replace(/document\.write\s*\(/g, '/* unsafe document.write — remplacer */ console.warn(')
    fixes.push('document.write commenté')
  }

  // 4. shell=True → shell=False
  if (/shell\s*=\s*True/.test(content)) {
    content = content.replace(/shell\s*=\s*True/g, 'shell=False')
    fixes.push('shell=True → shell=False')
  }

  // 5. verify=False → verify=True (TLS)
  if (/verify\s*=\s*False/i.test(content)) {
    content = content.replace(/verify\s*=\s*False/gi, 'verify=True')
    fixes.push('verify=False → verify=True')
  }

  // 6. hashlib.md5 → hashlib.sha256 (au moins ce n'est plus banni).
  // On ne migre PAS vers Argon2 automatiquement — nécessite la lib argon2-cffi
  // qu'on ne peut pas garantir installée.
  if (/hashlib\.md5\s*\(/.test(content)) {
    content = content.replace(/hashlib\.md5\s*\(/g, 'hashlib.sha256(')
    fixes.push('hashlib.md5 → hashlib.sha256 (préfère argon2id pour les mots de passe)')
  }

  // 7. Math.random() pour token/sel suspect → crypto.getRandomValues template.
  // Heuristique : seulement si le mot "token" ou "secret" est dans 80 chars autour.
  const mathRandomTokenRe = /^(.{0,80}(?:token|secret|salt|seed|key).{0,80})\bMath\.random\s*\(\s*\)/gim
  if (mathRandomTokenRe.test(content)) {
    content = content.replace(mathRandomTokenRe, (_m, prefix) => {
      return prefix + '(crypto.getRandomValues(new Uint32Array(1))[0] / 0xffffffff)'
    })
    fixes.push('Math.random près d\'un token: crypto.getRandomValues injecté')
  }

  return { content, outcome: { changed: fixes.length > 0, fixesApplied: fixes } }
}

/**
 * PatcherFn entry — boucle sur les fichiers, applique les corrections
 * déterministes. Compatible signature CritiqueLoop.PatcherFn.
 */
export const deterministicPatcher: PatcherFn = async (
  project: CodeProject,
  _intent: CodeIntent,
  _report: CritiqueReport,
): Promise<CodeProject> => {
  const nextFiles: CodeFile[] = []
  for (const file of project.files) {
    const { content, outcome } = patchFile(file)
    if (outcome.changed) {
      nextFiles.push({ ...file, content })
    } else {
      nextFiles.push(file)
    }
  }
  return { ...project, files: nextFiles }
}

/**
 * Variante qui retourne aussi le log de fixes appliqués — utile pour la trace UI.
 */
export async function patchWithLog(project: CodeProject, _intent: CodeIntent, _report: CritiqueReport): Promise<{ project: CodeProject; outcomes: Record<string, PatchOutcome> }> {
  const outcomes: Record<string, PatchOutcome> = {}
  const nextFiles: CodeFile[] = []
  for (const file of project.files) {
    const { content, outcome } = patchFile(file)
    outcomes[file.name] = outcome
    nextFiles.push(outcome.changed ? { ...file, content } : file)
  }
  return { project: { ...project, files: nextFiles }, outcomes }
}
