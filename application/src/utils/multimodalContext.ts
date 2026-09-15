import { fsMkdir, fsReadBinary, fsWriteBinary, getWorkspacePath, ollamaChat, runPythonScript } from '../hooks/useTauri.ts'
import type { ModuleId } from '../types/app.ts'
import { isTauriRuntime, getBridgeUrl } from './runtime.ts'
import { pickPrimaryPreparedImage } from './referenceMedia.ts'

export type PreparedContextFile = {
  id: string
  name: string
  kind: 'image' | 'pdf' | 'spreadsheet' | 'text' | 'other'
  size: number
  imageBase64?: string
  extractedText?: string
  stagedPath?: string
}

function extensionOf(file: File) {
  const parts = file.name.toLowerCase().split('.')
  return parts.length > 1 ? parts.pop() || '' : ''
}

function inferKind(file: File): PreparedContextFile['kind'] {
  const extension = extensionOf(file)
  const mime = file.type.toLowerCase()

  // Liste ALIGNEE sur estImage (ModelView) — la divergence classait un .heic
  // ou .avif au MIME vide comme document et l'envoyait a l'extracteur de
  // texte. Une seule definition d'« image » pour toute la chaine.
  if (mime.startsWith('image/') || ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'avif', 'tif', 'tiff', 'heic', 'heif', 'jfif', 'svg'].includes(extension)) {
    return 'image'
  }
  if (mime.includes('pdf') || extension === 'pdf') {
    return 'pdf'
  }
  if (['xlsx', 'xls', 'xlsm', 'csv', 'tsv'].includes(extension)) {
    return 'spreadsheet'
  }
  if (
    mime.startsWith('text/')
    || ['md', 'txt', 'json', 'yaml', 'yml', 'xml', 'log', 'py', 'ts', 'tsx', 'js', 'jsx', 'rs', 'sql', 'html', 'css'].includes(extension)
  ) {
    return 'text'
  }

  return 'other'
}

function stripDataUrlPrefix(dataUrl: string) {
  return dataUrl.replace(/^data:.*?;base64,/, '')
}

function bytesToBase64(bytes: number[]) {
  const chunkSize = 0x8000
  let binary = ''

  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.slice(index, index + chunkSize))
  }

  return btoa(binary)
}

async function fileToDataUrl(file: File) {
  const bytes = await file.arrayBuffer()
  const binary = Array.from(new Uint8Array(bytes)).map((byte) => String.fromCharCode(byte)).join('')
  const base64 = btoa(binary)
  const mime = file.type || 'application/octet-stream'
  return `data:${mime};base64,${base64}`
}

async function stageFile(file: File) {
  const workspacePath = await getWorkspacePath()
  const contextDir = `${workspacePath}/output/context`
  await fsMkdir(contextDir)

  const safeName = file.name.replace(/[^\w.\-]+/g, '_')
  const stagedPath = `${contextDir}/${Date.now()}_${safeName}`
  const bytes = Array.from(new Uint8Array(await file.arrayBuffer()))
  await fsWriteBinary(stagedPath, bytes)
  return stagedPath
}

function clipText(text: string, limit = 12000) {
  const normalized = text.replace(/\r/g, '').trim()
  if (normalized.length <= limit) {
    return normalized
  }
  return `${normalized.slice(0, limit)}\n...[contenu tronque pour garder une taille exploitable]`
}

function extractJsonFromPython(output: string) {
  const lines = output.split('\n').map((line) => line.trim()).filter(Boolean)
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    try {
      return JSON.parse(lines[index]) as { ok?: boolean; text?: string; error?: string; preview_paths?: string[] }
    } catch {
      // Continue until a valid JSON payload is found.
    }
  }

  return null
}

async function extractBrowserText(file: File) {
  const bytes = await file.arrayBuffer()
  return clipText(new TextDecoder().decode(bytes))
}

export async function prepareContextFiles(files: File[]) {
  const prepared = await Promise.all(files.map(async (file, index) => {
    const kind = inferKind(file)
    const item: PreparedContextFile = {
      id: `ctx-${Date.now()}-${index}`,
      name: file.name,
      kind,
      size: file.size,
    }

    if (kind === 'image') {
      item.imageBase64 = stripDataUrlPrefix(await fileToDataUrl(file))
      // 30/07 (audit): le staging etait garde par isTauriRuntime() alors que
      // fsWriteBinary a un repli bridge (/api/fs/write-binary) — en tunnel la
      // photo n'avait JAMAIS de stagedPath et le flux photo-seule mourait
      // avec « Votre photo n'a pas pu etre preparee ». Meme chemin partout.
      try {
        item.stagedPath = await stageFile(file)
      } catch {
        // sans staging la generation refusera avec le nom du fichier — mieux
        // qu'un echec silencieux plus loin.
      }
      return item
    }

    if (kind === 'text') {
      item.extractedText = await extractBrowserText(file)
      return item
    }

    if ((kind === 'pdf' || kind === 'spreadsheet' || kind === 'other') && isTauriRuntime()) {
      const stagedPath = await stageFile(file)
      item.stagedPath = stagedPath
      const workspacePath = await getWorkspacePath()
      const previewDir = `${workspacePath}/output/context/previews`
      const output = await runPythonScript(`${workspacePath}/python-services/document_extract.py`, ['--input', stagedPath, '--preview-dir', previewDir])
      const parsed = extractJsonFromPython(output)
      if (!parsed?.ok) {
        throw new Error(parsed?.error || `Extraction impossible pour ${file.name}.`)
      }
      item.extractedText = clipText(parsed.text || '')
      const previewPath = parsed.preview_paths?.[0]
      if (previewPath) {
        const previewBytes = await fsReadBinary(previewPath)
        item.imageBase64 = bytesToBase64(previewBytes)
      }
      return item
    }

    // v82nt: tunnel/cloud mode also needs PDF + spreadsheet extraction. The user
    // explicitly asks "fichiers téléversés sont prioritaires à la compréhension"
    // so we cannot return a placeholder string. Upload to /api/upload then run
    // document_extract.py via /api/python/run-async (already cloud-safe).
    if (kind === 'pdf' || kind === 'spreadsheet' || kind === 'other') {
      try {
        const base = getBridgeUrl()
        const form = new FormData()
        form.append('file', file)
        form.append('targetDir', 'output/context')
        const uploadResp = await fetch(`${base}/api/upload`, { method: 'POST', body: form })
        if (!uploadResp.ok) {
          item.extractedText = `[${file.name}] upload bridge a echoue (HTTP ${uploadResp.status}).`
          return item
        }
        const uploaded = await uploadResp.json() as { path?: string; name?: string }
        if (!uploaded.path) {
          item.extractedText = `[${file.name}] upload bridge sans chemin.`
          return item
        }
        item.stagedPath = uploaded.path
        const previewDir = 'output/context/previews'
        const output = await runPythonScript('python-services/document_extract.py', ['--input', uploaded.path, '--preview-dir', previewDir])
        const stdout = typeof output === 'string' ? output : (output as { output?: string }).output ?? ''
        const parsed = extractJsonFromPython(stdout)
        if (!parsed?.ok) {
          item.extractedText = parsed?.error
            ? `[${file.name}] extraction impossible: ${parsed.error}`
            : `[${file.name}] extraction impossible (sortie inattendue).`
          return item
        }
        item.extractedText = clipText(parsed.text || '')
        // Pas d'image preview en tunnel — pas de fsReadBinary disponible.
        return item
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error)
        item.extractedText = `[${file.name}] extraction tunnel a echoue: ${msg.slice(0, 240)}`
        return item
      }
    }

    item.extractedText = ''
    return item
  }))

  return prepared
}

export function summarizePreparedContext(files: PreparedContextFile[]) {
  const blocks = files
    .filter((file) => file.extractedText)
    .map((file) => `### ${file.name}\n${file.extractedText}`)

  return blocks.length > 0 ? blocks.join('\n\n') : ''
}

export function hasImageContext(files: PreparedContextFile[]) {
  return files.some((file) => Boolean(file.imageBase64))
}

export async function analyzeMultimodalContext({
  module,
  prompt,
  model,
  files,
}: {
  module: ModuleId
  prompt: string
  model: string
  files: PreparedContextFile[]
}) {
  if (files.length === 0) {
    return ''
  }

  const documentContext = summarizePreparedContext(files)
  const images = files.flatMap((file) => file.imageBase64 ? [file.imageBase64] : [])
  const hasImageReference = Boolean(pickPrimaryPreparedImage(files))

  const response = await ollamaChat(model, [
    {
      role: 'system',
      content: [
        '/no_think',
        `Tu es un analyseur multimodal pour le module ${module}.`,
        'Tu dois convertir les pieces jointes en contraintes utiles, precises et directement exploitables.',
        'Ne fais aucune invention.',
        'Si un document contient du bruit, garde seulement ce qui aide a la tache.',
        hasImageReference
          ? 'Si une image est jointe, separe clairement ce qui doit etre preserve, ce qui doit changer, les couleurs explicites, la pose/action, le cadrage et les details de matiere.'
          : 'Si aucune image n est jointe, concentre-toi uniquement sur les contraintes fiables venues des documents.',
        'Si la demande parle de realisme, priorise texture, matieres, lumiere believable, anatomie et coherence physique.',
        'Si la demande cite des couleurs ou demande de coloriser, ne propose jamais un rendu noir et blanc par defaut.',
        'Reponds en texte clair, structure en:',
        '1. elements fiables',
        '2. elements a preserver',
        '3. changements demandes',
        '4. details a prioriser',
      ].join('\n'),
    },
    {
      role: 'user',
      content: [
        `Demande utilisateur: ${prompt}`,
        documentContext ? `Contexte documents:\n${documentContext}` : 'Contexte documents: aucun',
      ].join('\n\n'),
      images: images.length > 0 ? images.slice(0, 6) : undefined,
    },
  ], 0.1)

  const content = response?.message?.content?.trim() || ''
  if (!content && !documentContext) {
    return ''
  }

  return [
    'Contexte pieces jointes:',
    content || 'Aucun complement visuel utile.',
    documentContext ? `Extraits documents:\n${documentContext}` : '',
  ].filter(Boolean).join('\n\n')
}
