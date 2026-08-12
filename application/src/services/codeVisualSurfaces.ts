// Surfaces de lecture du juge visuel: quel texte represente le MARKUP, le CSS
// et le JS d un projet. Extrait de codeVisualFidelity pour tenir la limite de
// 400 lignes par unite de production.

type CodeFile = { name: string; language: string; content: string }

export function findHtml(files: CodeFile[]): string {
  return files.filter((f) => /\.(html|htm)$/i.test(f.name)).map((f) => f.content).join('\n')
}

/**
 * Surface de MARKUP a juger.
 *
 * Mesure reelle (run 960): un site React+Vite de 33 fichiers a ete note
 * « 0 section trouvee, 0 ko de HTML, 50/100 » — parce que cette porte ne lisait
 * que les `.html`, et que dans un projet a composants l `index.html` de Vite est
 * une coquille de 223 octets autour de `<div id="root">`. Le markup vit dans les
 * `.tsx` / `.vue` / `.svelte`. Juger la coquille revenait a juger le carton d un
 * livre. Sur un `static_web` la liste des composants est vide: comportement
 * strictement inchange.
 */
export function findComponentMarkup(files: CodeFile[]): string {
  return files
    .filter((f) => /\.(jsx|tsx|vue|svelte|astro)$/i.test(f.name))
    .map((f) => f.content)
    .join('\n')
}
export function findCss(files: CodeFile[]): string {
  return files.filter((f) => /\.(css|scss|less)$/i.test(f.name)).map((f) => f.content).join('\n')
}
export function findJs(files: CodeFile[]): string {
  return files.filter((f) => /\.(js|mjs|jsx|tsx|ts)$/i.test(f.name)).map((f) => f.content).join('\n')
}
export function aggregateAll(files: CodeFile[]): string {
  return files.map((f) => f.content).join('\n')
}
