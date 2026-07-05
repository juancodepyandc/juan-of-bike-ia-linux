/**
 * v82fj : hook drag-and-drop fichier réutilisable.
 * Renvoie isDraggingOver + handlers à spreader sur l'élément cible.
 * onFile reçoit le premier fichier drop matchant les types acceptés
 * (filtré par extension/MIME).
 */
import { useCallback, useRef, useState } from 'react'

interface Options {
  /** v82fj : callback file-par-file (legacy, gardé pour compat). */
  onFile?: (file: File) => void
  /** v82fk : callback batch — reçoit tous les fichiers matchants en
   *  un seul appel. Si défini, prend le pas sur onFile. */
  onFiles?: (files: File[]) => void
  /** Extensions acceptées (en minuscule, sans point initial). Si vide, accepte tout. */
  accept?: string[]
  /** MIME prefixes acceptés (ex ['text/', 'application/pdf']). Vide = pas de filtre MIME. */
  acceptMime?: string[]
  disabled?: boolean
}

export function useFileDrop({ onFile, onFiles, accept = [], acceptMime = [], disabled = false }: Options) {
  const [isDraggingOver, setIsDraggingOver] = useState(false)
  // counter pour gérer les onDragLeave qui firent en boucle quand
  // l'utilisateur survole les enfants. On compte enter / leave.
  const counterRef = useRef(0)

  const matches = useCallback((file: File) => {
    if (accept.length === 0 && acceptMime.length === 0) return true
    const lower = (file.name || '').toLowerCase()
    if (accept.some((ext) => lower.endsWith(`.${ext}`))) return true
    if (acceptMime.some((m) => file.type === m || file.type.startsWith(m))) return true
    return false
  }, [accept, acceptMime])

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    if (disabled) return
    e.preventDefault()
    e.stopPropagation()
    counterRef.current++
    if (counterRef.current === 1) setIsDraggingOver(true)
  }, [disabled])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    if (disabled) return
    e.preventDefault()
    e.stopPropagation()
    counterRef.current = Math.max(0, counterRef.current - 1)
    if (counterRef.current === 0) setIsDraggingOver(false)
  }, [disabled])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    if (disabled) return
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = 'copy'
  }, [disabled])

  const handleDrop = useCallback((e: React.DragEvent) => {
    if (disabled) return
    e.preventDefault()
    e.stopPropagation()
    counterRef.current = 0
    setIsDraggingOver(false)
    const files = Array.from(e.dataTransfer.files || [])
    const matched = files.filter(matches)
    if (matched.length === 0) return
    if (onFiles) {
      onFiles(matched)
    } else if (onFile) {
      onFile(matched[0])
    }
  }, [disabled, matches, onFile, onFiles])

  return {
    isDraggingOver,
    bind: {
      onDragEnter: handleDragEnter,
      onDragLeave: handleDragLeave,
      onDragOver: handleDragOver,
      onDrop: handleDrop,
    },
  }
}
