// Garder en permanence le dernier etat connu des fichiers produits.
//
// Sans cela, une panne en cours de route rend `files: []` et le travail
// disparait (run 1041: 32 fichiers perdus sur un `fetch failed`).

import type { CodeFile } from './codeOrchestratorTypes.ts'

export type FileStateCapture = {
  /** Callback a passer au pipeline a la place de `onFilesUpdate`. */
  capture: (files: CodeFile[], notes: string) => void
  /** Dernier etat non vide observe. */
  snapshot: () => { files: CodeFile[]; notes: string }
}

export function createFileStateCapture(
  initialFiles: CodeFile[],
  onFilesUpdate: (files: CodeFile[], notes: string) => void,
): FileStateCapture {
  let files: CodeFile[] = initialFiles.slice()
  let notes = ''
  return {
    capture: (nextFiles, nextNotes) => {
      // Un lot vide n efface jamais un etat valide: c est precisement ce que
      // faisait l ancien gestionnaire fatal.
      if (nextFiles.length > 0) { files = nextFiles; notes = nextNotes }
      onFilesUpdate(nextFiles, nextNotes)
    },
    snapshot: () => ({ files, notes }),
  }
}
