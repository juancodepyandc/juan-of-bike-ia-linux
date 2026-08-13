// ---------------------------------------------------------------------------
// codeCodegenDependencies — une dependance dont le coeur est un fichier GENERE
// n est pas selectionnable par un pipeline qui n execute aucune generation.
//
// Run 1111, mesure sur les fichiers reels:
//
//   package.json : "@tanstack/react-router": "1.42.13"
//   src/App.tsx  : import { routeTree } from './routeTree.gen'
//   fichiers routeTree* livres : AUCUN
//
// `routeTree.gen` est produit par le plugin de codegen de TanStack Router — un
// plugin qui n etait meme pas dans les devDependencies. Le modele ne pouvait
// donc ni l ecrire (il est genere), ni l obtenir (le generateur est absent). Il
// a rediagnostique correctement le meme symptome a chaque passe:
//
//   Passe 5 — importation manquante du fichier ./routeTree.gen dans src/App.tsx
//   Passe 6 — Le fichier routeTree.gen est requis par App.tsx mais n existe pas
//   Passe 7 — import manquant du fichier ./routeTree.gen dans src/App.tsx
//   Passe 8 — import manquant du fichier ./routeTree.gen dans src/App.tsx
//   Arret de la boucle : boucle infinie apres 9 passes.
//
// Diagnostic juste, reparation impossible: neuf passes perdues d avance. C est
// le troisieme membre de la meme famille — apres « mets le secret dans .env »
// sans backend (run 1031) et « ecris ce JPEG » a un modele de texte (run 1081).
//
// La regle: **on n interdit pas la bibliotheque, on interdit de la choisir sans
// son generateur.** Et quand elle est choisie, on donne un remplacant REEL —
// un conseil irrealisable est pire qu un silence.
// ---------------------------------------------------------------------------

export type CodegenDependency = {
  /** Nom du paquet tel qu il apparait dans package.json. */
  name: string
  /** Ce que le generateur produit, et que personne n ecrit a la main. */
  generates: string
  /** Remplacant equivalent SANS etape de generation, ou null s il n y en a pas. */
  substitute: string | null
  reason: string
}

const REGISTRY: CodegenDependency[] = [
  {
    name: '@tanstack/react-router',
    generates: 'routeTree.gen.ts',
    substitute: 'react-router-dom',
    reason: 'l arbre de routes est produit par le plugin de codegen TanStack, jamais ecrit a la main',
  },
  {
    name: '@tanstack/router-plugin',
    generates: 'routeTree.gen.ts',
    substitute: 'react-router-dom',
    reason: 'plugin de generation de l arbre de routes TanStack',
  },
  {
    name: '@tanstack/router-devtools',
    generates: 'routeTree.gen.ts',
    substitute: null,
    reason: 'outil de debug lie a un routeur genere',
  },
  {
    name: '@tanstack/router-cli',
    generates: 'routeTree.gen.ts',
    substitute: 'react-router-dom',
    reason: 'generateur en ligne de commande de l arbre de routes',
  },
  {
    name: '@prisma/client',
    generates: 'client Prisma (node_modules/.prisma)',
    substitute: 'better-sqlite3',
    reason: 'le client est produit par `prisma generate` a partir du schema',
  },
  {
    name: 'prisma',
    generates: 'client Prisma (node_modules/.prisma)',
    substitute: 'better-sqlite3',
    reason: 'le client est produit par `prisma generate` a partir du schema',
  },
  {
    name: 'react-relay',
    generates: '__generated__/*.graphql.ts',
    substitute: '@apollo/client',
    reason: 'les artefacts de requete sont produits par le compilateur Relay',
  },
  {
    name: 'relay-runtime',
    generates: '__generated__/*.graphql.ts',
    substitute: '@apollo/client',
    reason: 'les artefacts de requete sont produits par le compilateur Relay',
  },
  {
    name: '@graphql-codegen/cli',
    generates: 'types GraphQL generes',
    substitute: null,
    reason: 'les types sont produits par graphql-codegen',
  },
]

const BY_NAME = new Map(REGISTRY.map((entry) => [entry.name.toLowerCase(), entry]))

/** Cette dependance exige-t-elle une generation que le pipeline n execute pas ? */
export function findCodegenDependency(name: string | null | undefined): CodegenDependency | null {
  return BY_NAME.get(String(name ?? '').trim().toLowerCase()) ?? null
}

/**
 * Ce chemin designe-t-il un artefact GENERE ? Personne ne l ecrit a la main, donc
 * ni la file de generation ni le contrat de plan ne doivent le reclamer — meme
 * regle que pour les ressources binaires.
 */
export function isGeneratedArtifactPath(path: string): boolean {
  const clean = String(path ?? '').replace(/\\/g, '/').toLowerCase()
  // Avec extension (chemin de fichier) OU sans (specificateur d import: le code
  // reel du run 1111 ecrit `from './routeTree.gen'`, sans `.ts`).
  if (/\.gen(\.[cm]?[jt]sx?)?$/.test(clean)) return true
  if (/\.generated(\.[cm]?[jt]sx?)?$/.test(clean)) return true
  if (/(^|\/)__generated__\//.test(clean)) return true
  if (/(^|\/)generated\//.test(clean)) return true
  return false
}

/** Les dependances a generateur presentes dans une liste de noms. */
export function selectedCodegenDependencies(names: readonly string[]): CodegenDependency[] {
  const seen = new Set<string>()
  const found: CodegenDependency[] = []
  for (const name of names) {
    const entry = findCodegenDependency(name)
    if (!entry || seen.has(entry.name)) continue
    seen.add(entry.name)
    found.push(entry)
  }
  return found
}

/** Consigne pour le planificateur: nommer l interdit ET son remplacant. */
export function buildCodegenDependencyBan(): string {
  const lines = REGISTRY
    .filter((entry) => entry.substitute)
    .map((entry) => `- ${entry.name} -> utilise ${entry.substitute} (${entry.reason})`)
  return [
    'DEPENDANCES INTERDITES — elles exigent une etape de GENERATION DE CODE que ce pipeline n execute pas.',
    'Choisir l une d elles produit un projet qui ne peut PAS etre repare: le fichier manquant est genere,',
    'donc ni toi ni la boucle de correction ne pouvez l ecrire.',
    ...lines,
    'N importe aucun fichier en `.gen.ts`, `.generated.ts`, `__generated__/` ou `generated/`:',
    'ces chemins designent des artefacts produits par un generateur absent.',
  ].join('\n')
}

/**
 * Remediation REALISABLE pour un import d artefact genere. Le conseil par defaut
 * (« ajoute le fichier ») est impossible a suivre: il faut changer de
 * bibliotheque, pas ecrire un fichier que seul un generateur produit.
 */
export function describeGeneratedImportRemediation(args: {
  importPath: string
  dependencyNames: readonly string[]
}): string | null {
  if (!isGeneratedArtifactPath(args.importPath)) return null
  const selected = selectedCodegenDependencies(args.dependencyNames)
  const culprit = selected.find((entry) => entry.substitute) ?? selected[0] ?? null
  const head = `\`${args.importPath}\` est un artefact GENERE: aucun modele ne peut l ecrire, et ce pipeline n execute pas de generation de code.`
  if (!culprit) {
    return `${head} Retire cet import et implemente la fonctionnalite sans artefact genere.`
  }
  return culprit.substitute
    ? `${head} Il vient de ${culprit.name} (${culprit.reason}). REMPLACE ${culprit.name} par ${culprit.substitute} — dependance, imports et code d appel — au lieu d essayer de creer le fichier.`
    : `${head} Il vient de ${culprit.name} (${culprit.reason}). Retire ${culprit.name} et implemente la fonctionnalite sans lui.`
}

type NamedDependency = { name: string; version?: string; reason?: string }

/**
 * Substitue, de facon DETERMINISTE, toute dependance a generateur par son
 * equivalent sans generation. Une dependance sans remplacant est retiree: mieux
 * vaut une fonctionnalite implementee autrement qu un projet irreparable.
 */
export function substituteCodegenDependencies<T extends NamedDependency>(
  dependencies: readonly T[],
): { dependencies: T[]; replacements: string[] } {
  const replacements: string[] = []
  const out: T[] = []
  for (const dependency of dependencies) {
    const codegen = findCodegenDependency(dependency.name)
    if (!codegen) {
      out.push(dependency)
      continue
    }
    replacements.push(codegen.substitute ? `${codegen.name} -> ${codegen.substitute}` : `${codegen.name} retiree`)
    if (!codegen.substitute) continue
    out.push({
      ...dependency,
      name: codegen.substitute,
      version: '',
      reason: `remplace ${codegen.name}: ${codegen.reason}, et ce pipeline n execute pas de generation de code`,
    })
  }
  return { dependencies: out, replacements }
}

/** Retire les fichiers que seul un generateur pourrait produire. */
export function rejectGeneratedArtifactFiles<T extends { path: string }>(
  files: readonly T[],
): { files: T[]; removed: string[] } {
  const removed: string[] = []
  const out: T[] = []
  for (const file of files) {
    if (isGeneratedArtifactPath(file.path)) {
      removed.push(file.path)
      continue
    }
    out.push(file)
  }
  return { files: out, removed }
}
