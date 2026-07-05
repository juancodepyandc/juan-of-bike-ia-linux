/**
 * v82co : DOCX extraction client-side via mammoth.js.
 * Renvoie le texte brut (rawText) — on évite convertToHtml pour
 * pas spammer l'IA avec du markup. Fallback si mammoth crash.
 *
 * Mammoth supporte .docx (OOXML). Pas .doc (binaire MSWord
 * 97-2003), pas .odt. Pour ces formats, retour graceful avec
 * message clair.
 */
export async function extractDocxText(file: File): Promise<string> {
  const mammoth = (await import('mammoth')).default ?? (await import('mammoth'))
  const buffer = await file.arrayBuffer()
  const result = await (mammoth as { extractRawText: (input: { arrayBuffer: ArrayBuffer }) => Promise<{ value: string; messages: unknown[] }> })
    .extractRawText({ arrayBuffer: buffer })
  return result.value || ''
}
