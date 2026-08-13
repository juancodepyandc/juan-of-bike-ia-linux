// ---------------------------------------------------------------------------
// codeBinaryAssetPaths — ce qu un modele de TEXTE ne peut pas ecrire.
//
// Run 1081, mesure sur le flux reel: le plan d architecture a mis des images
// binaires dans la file de generation WS3, et l executor a demande a
// qwen3-coder d en ECRIRE le contenu.
//
//   public/team-photo.jpg   -> 42 297 octets de base64 tape a la main
//   public/coffee-hero.jpg  ->    388 octets, un JPEG tronque des l en-tete
//
// Le second n est meme pas une image valide. Le premier a coute des dizaines de
// milliers de jetons pour produire un fichier tout aussi mort. Puis le 30e et
// dernier element de la file a rendu une reponse dont il ne restait rien:
// `action_protocol_invalid:protocol_marker_missing`, et le run est mort a
// 29/30 fichiers — apres presque une heure.
//
// Ce n est pas un defaut de tolerance du parseur: aucune consigne, aucune
// relance, aucun repli ne fera ecrire un JPEG valide a un modele de texte. La
// seule reponse juste est de NE PAS POSER LA QUESTION. Les images d Aurora
// viennent de la phase d assets inter-modules, qui appelle le module Image.
//
// Le meme predicat sert des DEUX cotes, sinon on cree une contradiction: la
// file ne produit plus le fichier, et le contrat de plan le reclame toujours.
// ---------------------------------------------------------------------------

/**
 * Extensions dont le contenu est binaire. `.svg` en est volontairement absent:
 * c est du XML, un modele l ecrit tres bien (run 1081: `public/logo.svg` a ete
 * produit valide). Le critere est « binaire », pas « ressource ».
 */
const BINARY_ASSET_EXTENSIONS = new Set([
  // images
  'png', 'apng', 'jpg', 'jpeg', 'jfif', 'gif', 'webp', 'avif', 'bmp', 'tif', 'tiff',
  'ico', 'icns', 'heic', 'psd', 'ai', 'xcf',
  // audio / video
  'mp3', 'wav', 'ogg', 'oga', 'flac', 'aac', 'm4a', 'opus',
  'mp4', 'webm', 'mov', 'avi', 'mkv', 'm4v',
  // polices
  'woff', 'woff2', 'ttf', 'otf', 'eot',
  // archives et documents opaques
  'zip', 'gz', 'bz2', 'xz', 'tar', '7z', 'rar', 'pdf',
  // 3D et binaires d execution
  'glb', 'fbx', 'blend', 'usdz', 'wasm', 'exe', 'dll', 'so', 'dylib', 'jar', 'class',
  // bases et blobs
  'db', 'sqlite', 'sqlite3', 'bin', 'dat',
])

function extensionOf(path: string): string {
  const clean = path.replace(/\\/g, '/').split('/').pop() ?? path
  const dot = clean.lastIndexOf('.')
  return dot > 0 ? clean.slice(dot + 1).toLowerCase() : ''
}

/**
 * Le contenu de ce chemin est-il binaire — donc impossible a AUTEUR par un
 * modele de texte ?
 */
export function isBinaryAssetPath(path: string): boolean {
  return BINARY_ASSET_EXTENSIONS.has(extensionOf(path))
}

/** Note attachee a un asset binaire ecarte, pour que le saut soit lisible. */
export function describeBinaryAssetSkip(paths: string[]): string {
  if (paths.length === 0) return ''
  return [
    `${paths.length} ressource(s) binaire(s) hors file de generation: ${paths.slice(0, 8).join(', ')}`,
    'Un modele de texte ne peut pas ecrire un binaire valide; ces fichiers relevent de la phase d assets.',
  ].join(' ')
}
