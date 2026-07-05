/**
 * Petites utilités pour nettoyer un résumé technique avant de le lire en TTS.
 *
 * Objectif : éviter que la voix Aurora énonce des hash hex, des extensions de
 * fichier ou des chaînes de séparateurs (`abc_def-123.png`).
 */

/**
 * Nettoie un nom de fichier pour le rendre lisible par la TTS.
 *
 *  - retire l'extension finale (`.png`, `.glb`, `.mp4`…)
 *  - remplace les hash de 8+ caractères hex par `…`
 *  - normalise les séparateurs `_-` en espaces
 *  - tronque à `maxChars` caractères (60 par défaut)
 */
export function cleanFilenameForTTS(raw: string | null | undefined, maxChars = 60): string {
  if (!raw) return ''
  let s = raw
  s = s.replace(/\.[a-z0-9]{2,5}$/i, '')              // retire extension
  s = s.replace(/[0-9a-f]{8,}/gi, '…')                // hash → …
  s = s.replace(/[_-]{2,}/g, ' ').replace(/[_-]/g, ' ')// underscores/dashes
  s = s.replace(/\s+/g, ' ').trim()
  return s.length > maxChars ? s.slice(0, maxChars) + '…' : s
}
