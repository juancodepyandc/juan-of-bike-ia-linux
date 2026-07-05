import { Paperclip, Trash2, X } from 'lucide-react'

export default function ContextFilesField({
  files,
  onFilesChange,
  accept,
  label = 'Pieces jointes',
  hint = 'Images, PDF, tableurs et textes de contexte.',
}: {
  files: File[]
  onFilesChange: (files: File[]) => void
  accept?: string
  label?: string
  hint?: string
}) {
  const removeAt = (indexToRemove: number) => {
    onFilesChange(files.filter((_, index) => index !== indexToRemove))
  }

  return (
    <div className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface-2/60 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">{label}</p>
          <p className="mt-2 text-sm text-aurora-text">{hint}</p>
        </div>

        {files.length > 0 && (
          <button
            onClick={() => onFilesChange([])}
            className="inline-flex items-center gap-2 rounded-xl border border-aurora-border/35 bg-aurora-surface px-3 py-2 text-xs text-aurora-text-dim transition-colors hover:text-aurora-text"
          >
            <Trash2 size={13} />
            Vider
          </button>
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-2 sm:mt-4">
        <label className="flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-2xl border border-dashed border-aurora-border/45 bg-aurora-surface/65 px-3 py-3 text-xs text-aurora-text transition-colors hover:border-aurora-accent/45 active:bg-aurora-surface/80 sm:px-4 sm:py-4 sm:text-sm">
          <Paperclip size={16} />
          <span>Ajouter des fichiers</span>
          <input
            type="file"
            multiple
            accept={accept}
            className="hidden"
            onChange={(event) => {
              const additions = Array.from(event.target.files || [])
              const existingKeys = new Set(files.map((file) => `${file.name}-${file.size}-${file.lastModified}`))
              const merged = [
                ...files,
                ...additions.filter((file) => !existingKeys.has(`${file.name}-${file.size}-${file.lastModified}`)),
              ]
              onFilesChange(merged)
              event.currentTarget.value = ''
            }}
          />
        </label>

        {/* Bouton camera direct pour mobile */}
        <label className="flex cursor-pointer items-center justify-center gap-2 rounded-2xl border border-dashed border-aurora-cyan/30 bg-aurora-cyan/[0.06] px-3 py-3 text-xs text-aurora-cyan transition-colors hover:border-aurora-cyan/50 active:bg-aurora-cyan/[0.12] sm:px-4 sm:py-4 sm:text-sm">
          <span>Photo</span>
          <input
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(event) => {
              const additions = Array.from(event.target.files || [])
              if (additions.length > 0) {
                onFilesChange([...files, ...additions])
              }
              event.currentTarget.value = ''
            }}
          />
        </label>
      </div>

      {files.length > 0 && (
        <div className="mt-4 space-y-2">
          {files.map((file, index) => (
            <div
              key={`${file.name}-${index}-${file.size}`}
              className="rounded-xl border border-aurora-border/35 bg-aurora-surface px-3 py-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm text-aurora-text">{file.name}</p>
                  <p className="mt-1 text-[11px] text-aurora-text-dim">
                    {(file.size / 1024 / 1024).toFixed(file.size > 1024 * 1024 ? 2 : 3)} Mo
                  </p>
                </div>

                <button
                  onClick={() => removeAt(index)}
                  className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-aurora-border/35 bg-aurora-surface-2 text-aurora-text-dim transition-colors hover:text-aurora-text"
                  aria-label={`Retirer ${file.name}`}
                >
                  <X size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
