// ---------------------------------------------------------------------------
// stack_resolve — rend une trace runtime LISIBLE par le correcteur.
//
// Run 1101, ce que la boucle recevait:
//
//   TypeError: Cannot read properties of undefined (reading 'map')
//       at hd (http://127.0.0.1:34141/assets/index-C-nmfp7n.js:8:193411)
//
// Une position dans un bundle minifie ne nomme ni le fichier source, ni la
// ligne, ni le composant. Le modele ne peut que deviner — et il a devine, neuf
// fois, en retouchant des CSS. C est exactement le trou deja bouche cote
// compilateur (« il disait QU il y a une erreur, jamais OU »), mais cote
// navigateur.
//
// Avec la carte emise a cote du bundle, la meme trace devient:
//
//   TypeError: Cannot read properties of undefined (reading 'map')
//       at hd (src/pages/Markets.tsx:42:18)
//
// La resolution ne peut PAS echouer bruyamment: une trace non resolue reste
// meilleure que pas de trace du tout, donc chaque etape retombe sur l original.
// ---------------------------------------------------------------------------

/** `http://host:port/assets/x.js:LIGNE:COLONNE` ou `/assets/x.js:LIGNE:COLONNE`. */
const FRAME_RE = /(?:https?:\/\/[^\s/)]+)?\/?((?:[\w.@/-]+)\.(?:m?js|cjs)):(\d+):(\d+)/g

function normalize(name) {
  return String(name || '').replace(/\\/g, '/').replace(/^\.?\//, '')
}

/**
 * Construit les lecteurs de cartes a partir des fichiers dist.
 * Retourne une Map<cheminBundle, TraceMap> — vide si aucune carte n est fournie.
 */
async function buildTraceMaps(distFiles) {
  const maps = new Map()
  const byName = new Map((distFiles ?? []).map((f) => [normalize(f.name), f.content ?? '']))
  let TraceMap = null
  for (const [name, content] of byName) {
    if (!name.endsWith('.map')) continue
    const bundleName = name.slice(0, -4)
    if (!byName.has(bundleName)) continue
    try {
      if (!TraceMap) ({ TraceMap } = await import('@jridgewell/trace-mapping'))
      maps.set(bundleName, new TraceMap(JSON.parse(content)))
    } catch {
      /* une carte illisible ne doit pas empecher de rendre la trace brute */
    }
  }
  return maps
}

/**
 * Remplace chaque position de bundle par sa position SOURCE quand la carte le
 * permet. Le texte est rendu tel quel si rien ne peut etre resolu.
 */
export async function resolveStackToSources(text, distFiles) {
  const input = String(text ?? '')
  if (!input) return input
  const maps = await buildTraceMaps(distFiles)
  if (maps.size === 0) return input

  let originalPositionFor = null
  try {
    ({ originalPositionFor } = await import('@jridgewell/trace-mapping'))
  } catch {
    return input
  }

  return input.replace(FRAME_RE, (whole, bundlePath, line, column) => {
    const map = maps.get(normalize(bundlePath))
    if (!map) return whole
    try {
      const pos = originalPositionFor(map, { line: Number(line), column: Number(column) })
      if (!pos || !pos.source || pos.line == null) return whole
      const source = normalize(pos.source).replace(/^(\.\.\/)+/, '')
      return `${source}:${pos.line}:${pos.column ?? 0}`
    } catch {
      return whole
    }
  })
}

/**
 * Resout une liste d erreurs et signale explicitement quand rien n a pu l etre:
 * un correcteur doit savoir qu il regarde une position de bundle, pas une
 * position source, sinon il « corrige » un fichier au hasard.
 */
export async function resolveConsoleErrors(errors, distFiles) {
  const list = Array.isArray(errors) ? errors : []
  if (list.length === 0) return list
  const out = []
  for (const error of list) {
    const resolved = await resolveStackToSources(error, distFiles)
    out.push(resolved === error && FRAME_RE.test(String(error))
      ? `${error}\n[position de bundle non resolue: aucune source map exploitable — ne devine pas le fichier]`
      : resolved)
    FRAME_RE.lastIndex = 0
  }
  return out
}
