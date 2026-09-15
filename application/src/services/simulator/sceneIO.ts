import type { SceneSnapshot } from './types.ts'

export const SCENE_FILE_EXTENSION = '.aurora-scene.json'

export function serializeScene(snapshot: SceneSnapshot): string {
  return JSON.stringify(snapshot, null, 2)
}

export function parseScene(text: string): SceneSnapshot {
  const data = JSON.parse(text) as SceneSnapshot
  if (!data.version || !Array.isArray(data.entities)) throw new Error('Scene invalide: format non reconnu')
  return data
}

export function downloadSceneJson(snapshot: SceneSnapshot, filename = `aurora-scene-${Date.now()}${SCENE_FILE_EXTENSION}`) {
  const blob = new Blob([serializeScene(snapshot)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export async function readSceneFile(file: File): Promise<SceneSnapshot> {
  const text = await file.text()
  return parseScene(text)
}

export async function exportSceneToGlb(scene: unknown, filename = `aurora-scene-${Date.now()}.glb`): Promise<Blob> {
  const { GLTFExporter } = await import('three/examples/jsm/exporters/GLTFExporter.js')
  const exporter = new GLTFExporter()
  const result = await exporter.parseAsync(scene as never, { binary: true })
  const blob = result instanceof ArrayBuffer ? new Blob([result], { type: 'model/gltf-binary' }) : new Blob([JSON.stringify(result)], { type: 'model/gltf+json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  return blob
}

export function triggerFilePicker(accept: string): Promise<File | null> {
  return new Promise((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = accept
    input.onchange = () => resolve(input.files && input.files.length > 0 ? input.files[0] : null)
    input.click()
  })
}
