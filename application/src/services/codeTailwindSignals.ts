// Reconnaitre en Tailwind ce que la porte cherchait en CSS ecrit a la main.
//
// Mesure reelle (run 1031, brulerie): 64/100, refuse. Les echecs reprochaient
// l absence d arrondis, de survols et de degrades. Or le projet en a — mesure
// dans ses fichiers:
//
//   rounded-lg x21 · rounded-md x3 · rounded-full x1
//   hover:text-olive x3 · hover:bg-amber-* x3 · hover:bg-olive x1
//
// La porte cherchait `border-radius:` et `:hover` dans du CSS. Tailwind
// n ecrit jamais ces proprietes: elles sont generees au build depuis les
// classes utilitaires. Le projet etait donc condamne pour l absence de choses
// qu il POSSEDE, simplement exprimees autrement — et comme le `index.css` d un
// projet Tailwind ne contient que trois directives `@tailwind`, aucune de ces
// regles ne pouvait jamais passer sur une SPA moderne.
//
// C est le meme defaut que le reste de cette refonte: juger la FORME de la
// reponse au lieu de sa substance.

/** Le projet passe-t-il par Tailwind ? */
export function usesTailwind(files: Array<{ name: string; content: string }>): boolean {
  return files.some((file) => {
    const name = file.name.toLowerCase()
    if (/tailwind\.config\.[cm]?[jt]s$/.test(name)) return true
    if (/(^|\/)package\.json$/.test(name) && /"tailwindcss"/.test(file.content)) return true
    if (/(^|\/)postcss\.config\.[cm]?js$/.test(name) && /tailwind/.test(file.content)) return true
    if (/\.css$/.test(name) && /@tailwind\s+(?:base|components|utilities)|@import\s+["']tailwindcss/.test(file.content)) return true
    return false
  })
}

// Les equivalents utilitaires des proprietes que la porte controle.
// `rounded` seul vaut 4px (sous la barre des 10px): on exige une taille nommee.
export const TW_RADIUS = /\b(?:rounded-(?:md|lg|xl|2xl|3xl|full)|rounded-[trbl][lr]?-(?:md|lg|xl|2xl|3xl|full))\b/
export const TW_HOVER = /\bhover:[a-z0-9[\]/.:-]+/
export const TW_GRADIENT = /\b(?:bg-gradient-to-[trbl]{1,2}|bg-\[linear-gradient|bg-\[radial-gradient|from-[a-z]+-\d{2,3}|via-[a-z]+-\d{2,3})\b/
export const TW_DEPTH = /\b(?:backdrop-blur(?:-[a-z]+)?|blur-(?:sm|md|lg|xl|2xl|3xl)|shadow-(?:md|lg|xl|2xl))\b/
export const TW_CLAMP = /\btext-\[clamp\(/
export const TW_ANIMATION = /\b(?:animate-[a-z0-9-]+|transition(?:-[a-z]+)?|duration-\d+)\b/

/**
 * Une section, dans un projet a composants, n est pas forcement une balise
 * `<section>`: chaque composant de page EST une section. Le run 1031 comptait
 * « 2 sections » sur 14 composants — dont About, CoffeeList, Contact, Admin.
 */
export const TW_SECTION_COMPONENT = /\.(?:jsx|tsx|vue|svelte|astro)$/i
