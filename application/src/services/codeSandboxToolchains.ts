// Chaines de compilation supplementaires montees dans le bac isole.
//
// Le sandbox choisit une image par langage. Kotlin et Swift n en avaient
// aucune: ils retombaient sur `debian:bookworm-slim`, ou ni `kotlinc` ni
// `swift` n existent. Un projet Kotlin genere echouait donc sur « command not
// found » — pas parce que le code etait faux, mais parce que l outil n etait
// nulle part. La matrice de capacite l a rendu visible: l HOTE sait compiler du
// Kotlin (APK signe de 610 Ko prouve), le SANDBOX non.
//
// Plutot que de tirer de nouvelles images (egress coupe par defaut, WS7), on
// monte en LECTURE SEULE la chaine deja installee dans le dossier prive
// d Aurora et on l ajoute au PATH du conteneur. L isolation est preservee: le
// montage est `ro`, et il ne concerne que le repertoire de l outil.

export type SandboxToolchainMount = {
  /** Chemin hote de la chaine, tel qu installe sous le dossier outils Aurora. */
  hostPath: string
  /** Point de montage dans le conteneur. */
  containerPath: string
  /** Repertoire a ajouter au PATH du conteneur. */
  binPath: string
}

/** Racine des outils prives d Aurora (surchargeable pour les tests). */
export const AURORA_TOOL_ROOT = '~/.local/share/auroraia/tools'

const TOOLCHAINS: Record<string, { dir: string; bin: string }> = {
  kotlin: { dir: 'kotlinc', bin: 'kotlinc/bin' },
  swift: { dir: 'swift-5.10.1', bin: 'swift-5.10.1/usr/bin' },
}

export function resolveToolRoot(homeDir: string): string {
  return `${homeDir.replace(/\/+$/, '')}/.local/share/auroraia/tools`
}

/**
 * Montage necessaire pour un langage, ou `null` quand l image du sandbox
 * fournit deja l outil (node, python, rust, go, java, c, cpp...).
 */
export function toolchainMountForLanguage(lang: string, homeDir: string): SandboxToolchainMount | null {
  const entry = TOOLCHAINS[lang]
  if (!entry) return null
  const root = resolveToolRoot(homeDir)
  return {
    hostPath: `${root}/${entry.dir}`,
    containerPath: `/opt/aurora-toolchains/${entry.dir}`,
    binPath: `/opt/aurora-toolchains/${entry.bin}`,
  }
}

/**
 * Arguments podman a inserer pour rendre la chaine disponible.
 * Retourne un tableau vide quand rien n est a monter — l appelant reste simple.
 */
export function toolchainPodmanArgs(mount: SandboxToolchainMount | null): string[] {
  if (!mount) return []
  return ['--volume', `${mount.hostPath}:${mount.containerPath}:ro`, '--env', `PATH=${mount.binPath}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`]
}

/** Image la plus adaptee quand une chaine est montee (Kotlin a besoin d une JVM). */
export function imageOverrideForToolchain(lang: string): string | null {
  if (lang === 'kotlin') return 'docker.io/library/eclipse-temurin:21'
  return null
}
