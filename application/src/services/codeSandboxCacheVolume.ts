// ---------------------------------------------------------------------------
// codeSandboxCacheVolume — le cache des gestionnaires de paquets appartient au
// DISQUE, jamais a la RAM.
//
// Cause racine du blocage du run 1191, reproduite a froid, machine au repos,
// aucun modele resident — donc pas « sous charge » comme on le croyait:
//
//   npm error code ENOSPC — no space left on device
//
//   tmpfs           256M  256M   80K 100% /home/aurora   <- PLEIN
//   tmpfs           256M  2.6M  254M   1% /tmp
//   /dev/nvme0n1p2  915G  855G   14G  99% /workspace     <- 14 Go libres
//
// Le disque hote n a JAMAIS ete le probleme. `NPM_CONFIG_CACHE` pointait sous
// `/home/aurora`, un tmpfs de 256 Mio monte pour donner a npm un HOME
// inscriptible (codeSandboxIsolation). Personne n avait mesure ce que npm y
// depose: pour le livrable reel du run 1191 (React 19, Vite, TypeScript, Jest,
// Testing Library, framer-motion, cssnano), le cache pese
//
//   284 Mio  — mesure, `du -sh` sur le cache apres installation reussie
//
// soit plus que le plafond, quoi qu il arrive. Ce n est pas un alea: c est une
// limite posee sans mesurer ce qu elle devait contenir. Meme faute que partout
// ailleurs dans ce module, appliquee a un montage au lieu d une porte.
//
// Preuve avant/apres sur le MEME package.json:
//   cache sur tmpfs 256 Mio  -> ENOSPC, exit 1, 0 paquet
//   cache sur volume disque  -> « added 403 packages in 16s »
//
// Agrandir le tmpfs serait le mauvais correctif: un tmpfs est adosse a la RAM
// et compte dans le plafond `--memory 2g` du conteneur. Un cache d un gibioctet
// mangerait la moitie du budget memoire pour ne stocker que des archives
// jetables. Un cache va sur un volume.
//
// Le volume est PROPRE A CHAQUE SANDBOX et detruit avec lui: pas de cache
// partage entre deux livrables, donc pas de contamination d un run par un
// autre. Le cout est de re-telecharger a chaque run — c est le prix de
// l isolation, et il est paye en secondes.
// ---------------------------------------------------------------------------

/** Racine du cache DANS le conteneur. Hors de `/home`, qui reste un tmpfs. */
export const CONTAINER_CACHE_PATH = '/aurora-cache'

export function sandboxCacheVolumeName(sandboxRoot: string): string {
  const suffix = sandboxRoot.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').slice(-48)
  return `aurora-code-cache-${suffix || Date.now()}`
}

export function buildPodmanCacheVolumeCreateArgs(sandboxRoot: string): string[] {
  return [
    'volume',
    'create',
    '--ignore',
    '--label',
    'aurora.role=code-sandbox-cache',
    sandboxCacheVolumeName(sandboxRoot),
  ]
}

export function buildPodmanCacheVolumeRemoveArgs(sandboxRoot: string): string[] {
  return ['volume', 'rm', '-f', sandboxCacheVolumeName(sandboxRoot)]
}

/**
 * Montage + variables d environnement du cache.
 *
 * Le suffixe `,U` demande a Podman de donner le volume a l utilisateur du
 * conteneur. Sans lui, et avec `--userns keep-id`, le volume neuf appartient a
 * root: npm ne peut pas y ecrire et l installation echoue — en remplacant une
 * panne de place par une panne de droits.
 *
 * Chaque outil a sa propre variable: npm ignore `XDG_CACHE_HOME`, pip et go
 * ignorent `NPM_CONFIG_CACHE`. Les poser toutes evite qu un langage retombe en
 * silence sur le tmpfs — c est exactement ainsi que le defaut est ne.
 */
export function buildPodmanCacheVolumeArgs(sandboxRoot: string): string[] {
  return [
    '--volume',
    `${sandboxCacheVolumeName(sandboxRoot)}:${CONTAINER_CACHE_PATH}:rw,U`,
    '--env',
    `NPM_CONFIG_CACHE=${CONTAINER_CACHE_PATH}/npm`,
    '--env',
    `YARN_CACHE_FOLDER=${CONTAINER_CACHE_PATH}/yarn`,
    '--env',
    `XDG_CACHE_HOME=${CONTAINER_CACHE_PATH}/xdg`,
    '--env',
    `PIP_CACHE_DIR=${CONTAINER_CACHE_PATH}/pip`,
    '--env',
    `CARGO_HOME=${CONTAINER_CACHE_PATH}/cargo`,
    '--env',
    `GOMODCACHE=${CONTAINER_CACHE_PATH}/go/pkg/mod`,
    '--env',
    `GOCACHE=${CONTAINER_CACHE_PATH}/go/build`,
  ]
}
