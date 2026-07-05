/**
 * blobStore — tiny IndexedDB wrapper for persisting generated blobs
 * (images, audio, small videos) across page reloads.
 *
 * Why not localStorage: a single FLUX PNG is 1-3 MB; 10 images blow past
 * the 5 MB localStorage quota. IndexedDB is the supported path for binary.
 *
 * Why not Cache API: requires a service worker to own the origin, which we
 * don't want to force on every user. IndexedDB works anywhere (Safari iOS
 * included) with no permissions.
 */

const DB_NAME = 'aurora-blobs'
const DB_VERSION = 4
const STORE = 'blobs'

type Entry = {
  id: string
  blob: Blob
  mime: string
  size: number
  addedAt: number
  /** Free-form tag so callers can prune by module ('image', 'video', …) */
  tag?: string
}

let dbPromise: Promise<IDBDatabase> | null = null

function openUncached(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'id' })
        store.createIndex('tag', 'tag', { unique: false })
        store.createIndex('addedAt', 'addedAt', { unique: false })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
    // If a newer version already exists (e.g. from a prior dev session that
    // accidentally bumped it), re-open without a version number — IDB will
    // pick up whatever is there, and we tolerate the store either way.
    req.onblocked = () => reject(req.error)
  })
}

function open(): Promise<IDBDatabase> {
  if (!dbPromise) dbPromise = openUncached()
  return dbPromise
}

function tx<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return open().then((db) => new Promise<T>((resolve, reject) => {
    const t = db.transaction(STORE, mode)
    const s = t.objectStore(STORE)
    const req = fn(s)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  }))
}

/**
 * Persist a blob under a stable id and return an object URL for the current
 * page. Callers should also save the id (not the url) so they can re-hydrate
 * after reload via `loadBlobUrl(id)`.
 */
export async function saveBlob(id: string, blob: Blob, tag?: string): Promise<string> {
  const entry: Entry = {
    id, blob, mime: blob.type || 'application/octet-stream',
    size: blob.size, addedAt: Date.now(), tag,
  }
  await tx('readwrite', (s) => s.put(entry))
  return URL.createObjectURL(blob)
}

/** Load a saved blob and return a fresh object URL for it. */
export async function loadBlobUrl(id: string): Promise<string | null> {
  try {
    const entry = await tx<Entry | undefined>('readonly', (s) => s.get(id))
    if (!entry?.blob) return null
    return URL.createObjectURL(entry.blob)
  } catch {
    return null
  }
}

export async function deleteBlob(id: string): Promise<void> {
  try { await tx('readwrite', (s) => s.delete(id)) } catch { /* best effort */ }
}

/** Prune entries older than the N most recent for a given tag. Keeps IDB
 * footprint bounded without forcing callers to count. */
export async function pruneOldBlobs(tag: string, keepLatest = 24): Promise<void> {
  try {
    const all = await tx<Entry[]>('readonly', (s) => {
      const idx = s.index('tag')
      return idx.getAll(tag)
    })
    if (!all || all.length <= keepLatest) return
    const toRemove = [...all].sort((a, b) => b.addedAt - a.addedAt).slice(keepLatest)
    for (const e of toRemove) await deleteBlob(e.id)
  } catch { /* best effort */ }
}
