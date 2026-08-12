// Que dire a un modele qui a mis un secret en dur — sans lui mentir.
//
// Mesure reelle (run 1031, brulerie): 8 passes de correction, dont les passes
// 5, 6, 7 et 8 bloquees sur « Secret en dur dans src/lib/auth.ts ». Le conseil
// donne etait « Deplacer vers .env / variable d environnement ».
//
// Ce conseil est FAUX sur ce projet. C est une SPA Vite sans le moindre fichier
// serveur (verifie: 0 fichier backend sur 31). Dans un bundle front,
// `import.meta.env.VITE_MOT_DE_PASSE` est inline au build: la valeur part chez
// le visiteur exactement comme avant. Le modele appliquait donc le conseil, le
// probleme restait, la regle se redeclenchait — quatre passes perdues dans une
// boucle qu aucun modele ne pouvait sortir, parce que la sortie proposee
// n existait pas.
//
// Un conseil irrealisable est pire qu un silence: il transforme une porte de
// qualite en piege. La remediation doit dependre de l ARCHITECTURE reelle.

import type { CodeFile } from './codeMultiPassCritique.ts'

/** Le projet a-t-il un cote serveur capable de garder un secret ? */
export function hasServerSide(files: CodeFile[]): boolean {
  return files.some((file) => {
    const name = file.name.toLowerCase()
    if (/(^|\/)(server|backend|api|functions|routes|controllers)\//.test(name)) return true
    if (/(^|\/)(server|app|main|index)\.(js|ts|py|go|rb|php)$/.test(name) && /express|fastify|flask|fastapi|django|gin|rails/i.test(file.content)) return true
    if (/\.(py|go|rb|php|java|cs)$/.test(name)) return true
    if (/(^|\/)(dockerfile|docker-compose\.ya?ml)$/.test(name)) return true
    if (/(^|\/)(netlify|vercel)\/functions?\//.test(name)) return true
    return false
  })
}

/**
 * Le conseil realisable, selon ce que le projet PEUT faire.
 *
 * Sans backend, la seule reponse honnete est qu un front ne garde aucun secret
 * — ni en dur, ni dans une variable d environnement de build. Le dire
 * explicitement evite au modele de tourner sur la fausse piste `.env`.
 */
export function secretRemediation(files: CodeFile[]): string {
  if (hasServerSide(files)) {
    return [
      'Deplacer la valeur hors du code: lecture depuis une variable d environnement',
      'cote SERVEUR (process.env / os.environ), jamais dans un fichier livre au',
      'navigateur. Ajouter la cle dans .env.example SANS sa valeur.',
    ].join(' ')
  }
  return [
    'ATTENTION — ce projet n a AUCUN cote serveur: une variable d environnement',
    'de build (VITE_*, NEXT_PUBLIC_*, REACT_APP_*) est INLINE dans le bundle et',
    'reste lisible par tout visiteur. La deplacer ne corrige donc RIEN.',
    'Deux sorties valables, au choix:',
    '(1) retirer la fonctionnalite qui exige ce secret — un acces protege',
    'cote client seul est decoratif, il ne protege rien;',
    '(2) si l acces doit vraiment etre protege, il faut un backend qui verifie,',
    'ce qui depasse le cadre d un site statique: le signaler dans le README',
    'plutot que de simuler une protection inexistante.',
  ].join(' ')
}
