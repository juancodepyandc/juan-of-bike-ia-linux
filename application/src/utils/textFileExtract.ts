/**
 * v82er : extraction texte universelle pour fichiers leçon/notes.
 * Partagé par Academy (lessonText) et Cyber (notesText).
 * Supporte : .txt, .md, .markdown, .pdf, .docx + fallback générique.
 * Refus graceful : .doc binaire, .odt, .rtf.
 *
 * v82ed : guard taille — fichiers > 50 MB rejetés en amont pour
 * protéger le navigateur (mammoth.js et pdfjs allouent toute
 * l'arrayBuffer en mémoire).
 */
export const MAX_TEXT_FILE_SIZE = 50 * 1024 * 1024 // 50 MB
// v82ee : limite image (référence FLUX, base canvas, vision multimodale)
export const MAX_IMAGE_FILE_SIZE = 10 * 1024 * 1024 // 10 MB

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * v82ee : valide une image avant upload/canvas/IP-Adapter.
 * Renvoie null si OK, sinon un message d'erreur prêt à afficher.
 */
export function validateImageFile(file: File): string | null {
  if (file.size > MAX_IMAGE_FILE_SIZE) {
    return `Image "${file.name}" trop volumineuse : ${formatBytes(file.size)} > ${formatBytes(MAX_IMAGE_FILE_SIZE)}. Compresse-la ou redimensionne-la avant upload.`
  }
  return null
}

export async function readTextFile(file: File): Promise<string> {
  // v82ed : rejet précoce si trop gros
  if (file.size > MAX_TEXT_FILE_SIZE) {
    return `(fichier "${file.name}" trop volumineux : ${formatBytes(file.size)} > ${formatBytes(MAX_TEXT_FILE_SIZE)}. Découpe-le ou compresse-le avant d'essayer.)`
  }
  const lower = (file.name || '').toLowerCase()
  if (
    lower.endsWith('.txt')
    || lower.endsWith('.md')
    || lower.endsWith('.markdown')
    || file.type.startsWith('text/')
  ) {
    return file.text()
  }
  if (lower.endsWith('.pdf') || file.type === 'application/pdf') {
    try {
      const { extractPdfText } = await import('./pdfExtract')
      const text = await extractPdfText(file, 30)
      if (text.trim().length > 0) return text
      return `(PDF "${file.name}" lu mais sans texte extractible — c'est peut-être un PDF scanné.)`
    } catch (e) {
      return `(échec extraction PDF "${file.name}" : ${e instanceof Error ? e.message : String(e)})`
    }
  }
  if (
    lower.endsWith('.docx')
    || file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ) {
    try {
      const { extractDocxText } = await import('./docxExtract')
      const text = await extractDocxText(file)
      if (text.trim().length > 0) return text
      return `(DOCX "${file.name}" lu mais vide — vérifie le fichier ou exporte-le en PDF.)`
    } catch (e) {
      return `(échec extraction DOCX "${file.name}" : ${e instanceof Error ? e.message : String(e)})`
    }
  }
  if (lower.endsWith('.doc') || lower.endsWith('.odt') || lower.endsWith('.rtf')) {
    return `(format "${lower.slice(lower.lastIndexOf('.'))}" non supporté en navigateur — convertis le fichier en .docx, .pdf, .md ou .txt et réessaye.)`
  }
  try {
    return await file.text()
  } catch {
    return `(fichier "${file.name}" non lisible côté navigateur — formats supportés : .txt, .md, .pdf, .docx, ou image via le bouton dédié)`
  }
}
