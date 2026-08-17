// ---------------------------------------------------------------------------
// codeMissingRouterProvider — des routes montees hors de tout routeur.
//
// Run 1181, mesure sur le livrable reel (36 fichiers). L acceptation
// comportementale sort 0/2 et le rendu 10/100, sur une page vide:
//
//   TypeError: Cannot destructure property 'basename' of 'y.useContext(...)'
//              as it is null.
//   FAIL renders-content: 0 caracteres, 0 controles, 0 surfaces.
//
// C est l erreur canonique de React Router: un composant de routage lit un
// contexte que personne n a fourni. Verification faite fichier par fichier:
//
//   src/main.tsx          rend <App /> — aucun routeur
//   src/App.tsx           rend <Navigation /> et <AppRoutes /> — aucun routeur
//   src/routes/AppRoutes  utilise <Routes>, <Route>, <Navigate>
//   AUCUN fichier du projet ne contient BrowserRouter, HashRouter,
//   MemoryRouter, RouterProvider ni createBrowserRouter.
//
// Le fournisseur n est pas mal place: il est ABSENT. L application ne monte
// donc jamais, et les six criteres de style que le juge declarait en echec
// n etaient que les consequences de cette unique cause.
//
// Pourquoi ce module et pas une passe de modele: la passe ciblee a corrige
// `AppRoutes.tsx` — le fichier NOMME par la trace — et le rendu est reste a
// 10/100. La cause vit dans le point d entree, pas dans le fichier qui plante.
// Envelopper l arbre monte dans un routeur est mecanique: un seul endroit
// possible (l appel a `render`), une seule forme possible. Donc pas de modele.
// ---------------------------------------------------------------------------

export type RouterFile = { name: string; language: string; content: string }

/** Composants et hooks qui EXIGENT un routeur au-dessus d eux. */
const ROUTER_CONSUMERS = /\b(?:Routes|Route|Link|NavLink|Navigate|Outlet|useNavigate|useParams|useLocation|useSearchParams|useRoutes|useMatch)\b/

/** Toutes les facons de fournir ce contexte. */
const ROUTER_PROVIDERS = /\b(?:BrowserRouter|HashRouter|MemoryRouter|RouterProvider|createBrowserRouter|createHashRouter|createMemoryRouter|StaticRouter|unstable_HistoryRouter)\b/

function importsRouterDom(content: string): boolean {
  return /from\s*['"]react-router(?:-dom)?['"]/.test(content)
}

/** Le projet consomme-t-il un routeur sans qu aucun fichier n en fournisse un ? */
export function detectMissingRouterProvider(files: RouterFile[]): { consumers: string[]; hasProvider: boolean } {
  const consumers: string[] = []
  let hasProvider = false
  for (const file of files) {
    if (!/\.(tsx|jsx|ts|js)$/i.test(file.name)) continue
    if (ROUTER_PROVIDERS.test(file.content)) hasProvider = true
    if (importsRouterDom(file.content) && ROUTER_CONSUMERS.test(file.content)) consumers.push(file.name)
  }
  return { consumers, hasProvider }
}

/** Contenu entre la parenthese ouvrante d un appel et sa fermante appariee. */
function balancedArgument(content: string, openIndex: number): { inner: string; end: number } | null {
  let depth = 0
  for (let i = openIndex; i < content.length; i++) {
    const char = content[i]
    if (char === '(') depth += 1
    else if (char === ')') {
      depth -= 1
      if (depth === 0) return { inner: content.slice(openIndex + 1, i), end: i }
    }
  }
  return null
}

/**
 * Point d entree: le fichier qui monte reellement l application.
 *
 * On ne tente PAS de decrire l appel en une seule expression reguliere. Le
 * gabarit reel s ecrit `createRoot(document.getElementById('root')!).render(` —
 * une parenthese imbriquee y suffit a faire echouer un `[^)]*`, et c est
 * exactement ce qui est arrive au premier jet de ce module. On reconnait le
 * FICHIER, puis on cherche l appel `.render(` et on apparie les parentheses.
 */
function findEntry(files: RouterFile[]): RouterFile | null {
  return files.find((file) =>
    /\.(tsx|jsx)$/i.test(file.name)
    && /\bcreateRoot\b|\bReactDOM\s*\.\s*render\b|\bhydrateRoot\b/.test(file.content)
    && /\.\s*render\s*\(|ReactDOM\s*\.\s*render\s*\(/.test(file.content),
  ) ?? null
}

/** Position de la parenthese ouvrante de l appel de montage. */
function findRenderCall(content: string): number | null {
  const match = /(?:\.\s*render|ReactDOM\s*\.\s*render|hydrateRoot)\s*\(/.exec(content)
  return match ? match.index + match[0].length - 1 : null
}

function addRouterImport(content: string): string {
  const existing = /(\bimport\s+)(\{[^}]*\})(\s*from\s*['"]react-router-dom['"])/.exec(content)
  if (existing) {
    const inner = existing[2].slice(1, -1).trim()
    if (/\bBrowserRouter\b/.test(inner)) return content
    return content.replace(existing[0], `${existing[1]}{ ${inner ? `${inner}, ` : ''}BrowserRouter }${existing[3]}`)
  }
  const lastImport = [...content.matchAll(/^import .*$/gm)].pop()
  const line = "import { BrowserRouter } from 'react-router-dom'"
  if (!lastImport) return `${line}\n${content}`
  const at = lastImport.index! + lastImport[0].length
  return `${content.slice(0, at)}\n${line}${content.slice(at)}`
}

/**
 * Enveloppe l arbre monte dans un `<BrowserRouter>`. Ne fait rien si le projet
 * n a pas de routes, s il a deja un routeur, ou si le point d entree n est pas
 * reconnaissable — le doute profite au livrable, comme partout ici.
 */
export function repairMissingRouterProvider(
  files: RouterFile[],
): { files: RouterFile[]; entry: string | null; consumers: string[] } {
  const { consumers, hasProvider } = detectMissingRouterProvider(files)
  if (hasProvider || consumers.length === 0) return { files, entry: null, consumers }

  const entry = findEntry(files)
  if (!entry) return { files, entry: null, consumers }

  const openIndex = findRenderCall(entry.content)
  if (openIndex === null) return { files, entry: null, consumers }
  const argument = balancedArgument(entry.content, openIndex)
  if (!argument) return { files, entry: null, consumers }

  const inner = argument.inner
  if (inner.trim().length === 0) return { files, entry: null, consumers }
  // On preserve la virgule finale et l indentation d origine: on enveloppe, on
  // ne reformate pas le fichier de quelqu un d autre.
  const trailing = /,\s*$/.exec(inner)?.[0] ?? ''
  const body = trailing ? inner.slice(0, inner.length - trailing.length) : inner
  const wrapped = `\n  <BrowserRouter>${body.replace(/\n/g, '\n  ')}\n  </BrowserRouter>${trailing || '\n'}`

  const nextContent = addRouterImport(
    entry.content.slice(0, openIndex + 1) + wrapped + entry.content.slice(argument.end),
  )

  return {
    files: files.map((file) => (file.name === entry.name ? { ...file, content: nextContent } : file)),
    entry: entry.name,
    consumers,
  }
}
