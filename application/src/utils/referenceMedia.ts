import { fsMkdir, fsWriteBinary, getWorkspacePath } from '../hooks/useTauri'
import type { PreparedContextFile } from './multimodalContext'

function sanitizeFilename(name: string) {
  return name.replace(/[^\w.\-]+/g, '_')
}

function timestampedName(prefix: string, extension: string, originalName?: string) {
  const safeOriginal = originalName ? sanitizeFilename(originalName) : `${prefix}.${extension}`
  return `${Date.now()}_${safeOriginal}`
}

function inferImageExtension(file: File) {
  const lowerName = file.name.toLowerCase()
  if (lowerName.endsWith('.jpg') || lowerName.endsWith('.jpeg')) {
    return 'jpg'
  }

  if (lowerName.endsWith('.webp')) {
    return 'webp'
  }

  return 'png'
}

export function isImageLikeFile(file: File) {
  return file.type.startsWith('image/') || /\.(png|jpe?g|webp|gif|bmp)$/i.test(file.name)
}

export function pickPrimaryImageFile(files: File[]) {
  return files.find((file) => isImageLikeFile(file)) || null
}

export function pickPrimaryPreparedImage(files: PreparedContextFile[]) {
  return files.find((file) => file.kind === 'image') || null
}

export async function stageBrowserFileToWorkspace(
  file: File,
  relativeDir: string,
  prefix: string,
) {
  const workspacePath = await getWorkspacePath()
  const directory = `${workspacePath}/${relativeDir}`.replace(/\\/g, '/')
  await fsMkdir(directory)
  const filename = timestampedName(prefix, inferImageExtension(file), file.name)
  const absolutePath = `${directory}/${filename}`.replace(/\\/g, '/')
  const bytes = Array.from(new Uint8Array(await file.arrayBuffer()))
  await fsWriteBinary(absolutePath, bytes)
  return { filename, absolutePath }
}

export async function stageBrowserFileToComfyInput(
  file: File,
  comfyuiPath: string,
  prefix: string,
) {
  const inputDir = `${comfyuiPath.replace(/\\/g, '/')}/input`
  await fsMkdir(inputDir)
  const filename = timestampedName(prefix, inferImageExtension(file), file.name)
  const absolutePath = `${inputDir}/${filename}`.replace(/\\/g, '/')
  const bytes = Array.from(new Uint8Array(await file.arrayBuffer()))
  await fsWriteBinary(absolutePath, bytes)
  return { filename, absolutePath }
}

export async function stageBlobToComfyInput(
  blob: Blob,
  comfyuiPath: string,
  prefix: string,
  extension = 'png',
) {
  const inputDir = `${comfyuiPath.replace(/\\/g, '/')}/input`
  await fsMkdir(inputDir)
  const filename = `${Date.now()}_${sanitizeFilename(prefix)}.${extension}`
  const absolutePath = `${inputDir}/${filename}`.replace(/\\/g, '/')
  const bytes = Array.from(new Uint8Array(await blob.arrayBuffer()))
  await fsWriteBinary(absolutePath, bytes)
  return { filename, absolutePath }
}
